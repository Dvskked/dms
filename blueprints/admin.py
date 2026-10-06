"""Blueprint del panel de administracion.

El panel esta agrupado en 5 secciones (SECTIONS) sobre un CRUD generico por
recurso (RESOURCES). Ademas:

- buscador global que barre las 19 tablas del esquema,
- borrado en cascada explicito (equipo, jugador, partido, division, usuario),
- informe de partido en UN solo formulario: texto, foto, marcador y la rejilla
  de estadisticas individuales.

Todo lo que cuelga de /admin exige rol admin o staff; algunas rutas son solo del
administrador (ADMIN_ONLY_ENDPOINTS) y algunos recursos marcan ``admin_only``.
"""
from __future__ import annotations

import secrets
from datetime import date, timedelta
from decimal import Decimal, InvalidOperation

from flask import Blueprint, abort, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required
from sqlalchemy import func, or_
from wtforms.fields import FileField, SelectField

from extensions import db
from forms import (
    ArticleForm, BooleanOnlyForm, DivisionForm, DivisionNoteForm, DonationForm, DonationGoalForm,
    LinkForm, LiveStreamForm, MatchForm, MatchReportForm, MuseumForm, PlayerForm, RegulationForm,
    RoomForm, RosterPlayerForm, SearchForm, SuggestionReplyForm, TeamCrestForm, TeamForm, UserForm,
)
from models import (
    Article, Category, Division, DivisionNote, Donation, Link, LinkKind, LiveStream, Log, LogKind,
    Match, MatchReport, MatchStat, MuseumItem, PasswordResetToken, Player, Regulation, Role, Room,
    SUGGESTION_CATEGORIES, Setting, Suggestion, SuggestionStatus, Team, User, current_division,
    division_standings, donation_goal, log_activity, recalculate_player_stats, set_setting,
    setting, team_standing,
)
from utils import delete_upload, nulls_last, save_upload, slugify, utcnow

bp = Blueprint("admin", __name__, url_prefix="/admin")


# --------------------------------------------------------------------------- #
# Guards
# --------------------------------------------------------------------------- #
#: Rutas reservadas al administrador (el resto del staff no puede entrar).
ADMIN_ONLY_ENDPOINTS = {
    "admin.promote", "admin.recalculate_stats", "admin.settings", "admin.settings_save",
    "admin.duplicate_article", "admin.email_log", "admin.email_log_resend",
    "admin.donation_goal_settings",
}


@bp.before_request
@login_required
def _guard():
    if not current_user.is_staff:
        abort(403)
    if request.endpoint in ADMIN_ONLY_ENDPOINTS and not current_user.is_admin:
        abort(403)


# --------------------------------------------------------------------------- #
# Recursos del panel
# --------------------------------------------------------------------------- #
#: ``fields``  columnas que muestra la tabla del listado.
#: ``search``  columnas por las que busca el input de la cabecera.
#: ``files``   campo del formulario -> columna del modelo (imagen local y URL).
#: ``row``     endpoint alterno al boton de edicion (ficha de equipo, informe...).
#: ``filters`` valores fijos que se imponen al guardar (el recurso es una vista).
RESOURCES: dict[str, dict] = {
    "divisiones": dict(
        model=Division, form=DivisionForm, icon="01", title="Divisiones",
        subtitle="Formato, temporada y estado de inscripcion de cada division.",
        fields=["name", "short", "level", "season_label", "teams_count", "journeys_count",
                "is_current", "actions"],
        search=["name", "short", "key", "description"],
        order=(Division.level, Division.season_number, Division.name),
    ),
    "notas": dict(
        model=DivisionNote, form=DivisionNoteForm, icon="02", title="Fases y notas",
        subtitle="Fases, reglas y ascensos o descensos de cada division.",
        fields=["title", "scope_label", "division", "tag", "position", "actions"],
        search=["title", "body", "tag", "highlight"],
        order=(DivisionNote.division_id, DivisionNote.scope, DivisionNote.position),
    ),
    "reglamento": dict(
        model=Regulation, form=RegulationForm, icon="03", title="Reglamento",
        subtitle="Normas de Discord, comunidad y escala de sanciones.",
        fields=["title", "scope", "color", "position", "actions"],
        search=["title", "body", "note"],
        order=(Regulation.scope, Regulation.position),
    ),
    "equipos": dict(
        model=Team, form=TeamForm, icon="04", title="Equipos",
        subtitle="Escudos, division y plantilla de cada club.",
        fields=["name", "crest", "division", "coach", "player_count", "is_active", "actions"],
        search=["name", "short", "coach", "captain", "description"],
        order=(Team.sort_order, Team.name),
        files={"crest": "image", "crest_url": "image_url"},
        row="admin.team_detail",
    ),
    "jugadores": dict(
        model=Player, form=PlayerForm, icon="05", title="Jugadores",
        subtitle="Nominas, posiciones y acumulados individuales.",
        fields=["username", "team", "position_label", "matches", "goals", "assists", "is_active",
                "actions"],
        search=["username", "haxball_id", "country"],
        order=(Player.username,),
    ),
    "calendario": dict(
        model=Match, form=MatchForm, icon="06", title="Calendario",
        subtitle="Jornadas, resultados y enlaces de sala y replay.",
        fields=["journey", "played_on", "home_team", "away_team", "score_text", "status", "actions"],
        search=["stage", "notes"],
        order=(Match.journey, *nulls_last(Match.played_on, descending=False), Match.kickoff),
        row="admin.match_report",
    ),
    "salas": dict(
        model=Room, form=RoomForm, icon="07", title="Salas",
        subtitle="Links publicos de las salas de HaxBall.",
        fields=["code", "name", "region", "mode", "max_players", "is_open", "actions"],
        search=["code", "name", "description", "map_name"],
        order=(Room.sort_order, Room.code),
        files={"image": "image", "image_url": "image_url"},
    ),
    "live": dict(
        model=LiveStream, form=LiveStreamForm, icon="08", title="Live",
        subtitle="Transmisiones de futbol en vivo y upcoming.",
        fields=["title", "platform_label", "competition", "is_live", "viewers", "actions"],
        search=["title", "league", "competition", "channel"],
        order=(LiveStream.is_live.desc(), LiveStream.sort_order),
        files={"thumbnail": "image", "thumbnail_url": "image_url"},
    ),
    "noticias": dict(
        model=Article, form=ArticleForm, icon="09", title="Noticias",
        subtitle="Reportarias y contenido editorial reciente.",
        fields=["title", "category_label", "author_label", "is_featured", "is_published",
                "published_at", "actions"],
        search=["title", "summary", "body"],
        filters={"kind": Category.NEWS},
        order=(Article.is_featured.desc(), *nulls_last(Article.published_at)),
        files={"cover": "image", "cover_url": "image_url"},
        skip_fields=["kind"],
    ),
    "avisos": dict(
        model=Article, form=ArticleForm, icon="10", title="Avisos",
        subtitle="Comunicados, inscripciones y alertas de la liga.",
        fields=["title", "category_label", "is_pinned", "is_published", "published_at", "actions"],
        search=["title", "summary", "body"],
        filters={"kind": Category.ANNOUNCEMENT},
        order=(Article.is_pinned.desc(), *nulls_last(Article.published_at)),
        files={"cover": "image", "cover_url": "image_url"},
        skip_fields=["kind"],
    ),
    "informes": dict(
        model=Article, form=ArticleForm, icon="11", title="Informes",
        subtitle="Reportes, resumenes de jornada y documentos internos.",
        fields=["title", "category_label", "author_label", "is_published", "published_at", "actions"],
        search=["title", "summary", "body"],
        filters={"kind": Category.REPORT},
        order=(*nulls_last(Article.published_at),),
        files={"cover": "image", "cover_url": "image_url"},
        skip_fields=["kind"],
    ),
    "museo": dict(
        model=MuseumItem, form=MuseumForm, icon="12", title="Museo",
        subtitle="Premios, rankings, campeones y trofeos entregados.",
        fields=["title", "category_label", "division_label", "holder", "place", "awarded_on",
                "actions"],
        search=["title", "recipient", "description"],
        order=(MuseumItem.sort_order, *nulls_last(MuseumItem.awarded_on)),
        files={"image": "image", "image_url": "image_url"},
    ),
    "usuarios": dict(
        model=User, form=UserForm, icon="13", title="Usuarios",
        subtitle="Cuentas, roles y ficha publica del equipo de administracion.",
        fields=["username", "email", "role", "title", "is_public", "is_active_account", "actions"],
        search=["username", "email", "display_name", "title"],
        order=(User.is_leader.desc(), User.sort_order, User.username),
        files={"avatar": "image", "avatar_url": "image_url",
               "banner": "banner", "banner_url": "banner_url"},
        admin_only=True,
    ),
    "enlaces": dict(
        model=Link, form=LinkForm, icon="14", title="Enlaces",
        subtitle="Alianzas, redes sociales y metodos de donacion.",
        fields=["label", "kind_label", "kind_sub_label", "group", "is_active", "actions"],
        search=["label", "tagline", "body", "handle", "account", "url"],
        order=(Link.kind, Link.sort_order, Link.label),
    ),
    "donaciones": dict(
        model=Donation, form=DonationForm, icon="15", title="Donaciones",
        subtitle="Registro de apoyos economicos de la comunidad.",
        fields=["donor_name", "amount_text", "channel", "donated_at", "is_public", "actions"],
        search=["donor_name", "message"],
        order=(*nulls_last(Donation.donated_at),),
    ),
}


#: Las 5 secciones del panel. ``keys`` son recursos de RESOURCES y ``pages`` son
#: pantallas propias (informes de partido, sugerencias, meta, correo, ajustes).
SECTIONS: list[dict] = [
    {
        "slug": "competicion",
        "title": "COMPETICION",
        "subtitle": "Divisiones, formato, reglamento y plantillas.",
        "keys": ["divisiones", "notas", "reglamento", "equipos", "jugadores"],
    },
    {
        "slug": "partidos",
        "title": "PARTIDOS",
        "subtitle": "Calendario, salas y transmisiones.",
        "keys": ["calendario", "salas", "live"],
        "pages": [{"endpoint": "admin.match_reports", "label": "Informes de partido", "icon": "▣"}],
    },
    {
        "slug": "contenido",
        "title": "CONTENIDO",
        "subtitle": "Noticias, avisos, informes y museo.",
        "keys": ["noticias", "avisos", "informes", "museo"],
    },
    {
        "slug": "comunidad",
        "title": "COMUNIDAD",
        "subtitle": "Cuentas, sugerencias, enlaces y donaciones.",
        "keys": ["usuarios", "enlaces", "donaciones"],
        "pages": [{"endpoint": "admin.suggestions", "label": "Sugerencias", "icon": "✦"}],
    },
    {
        "slug": "sistema",
        "title": "SISTEMA",
        "subtitle": "Meta de donacion, correo, actividad y ajustes.",
        "keys": [],
        "pages": [
            {"endpoint": "admin.donation_goal_settings", "label": "Meta de donacion", "icon": "$",
             "admin_only": True},
            {"endpoint": "admin.email_log", "label": "Correo y actividad", "icon": "✉",
             "admin_only": True},
            {"endpoint": "admin.settings", "label": "Ajustes del sitio", "icon": "⚙",
             "admin_only": True},
        ],
    },
]

SECTION_BY_KEY = {key: section for section in SECTIONS for key in section["keys"]}


# --------------------------------------------------------------------------- #
# Utilidades de listado
# --------------------------------------------------------------------------- #
def _as_decimal(raw, fallback: Decimal = Decimal("0")) -> Decimal:
    """Convierte a ``Decimal`` sin reventar si viene de ``settings`` (texto)."""
    if raw is None or raw == "":
        return fallback
    if isinstance(raw, Decimal):
        return raw
    try:
        return Decimal(str(raw).replace(",", "."))
    except (InvalidOperation, ValueError, TypeError):
        return fallback


def _query_for(resource: str):
    cfg = RESOURCES[resource]
    query = cfg["model"].query
    if cfg.get("filters"):
        query = query.filter_by(**cfg["filters"])

    term = (request.args.get("q") or "").strip()
    if term and cfg.get("search"):
        clauses = [getattr(cfg["model"], col).ilike(f"%{term}%") for col in cfg["search"]]
        query = query.filter(func.or_(*clauses))

    if cfg.get("order") is not None:
        query = query.order_by(*cfg["order"])
    return query, term


def _page(query, per_page: int = 20):
    page = request.args.get("page", 1, type=int)
    total = query.order_by(None).count()
    pages = max(1, (total + per_page - 1) // per_page)
    page = max(1, min(page, pages))
    rows = query.limit(per_page).offset((page - 1) * per_page).all()
    return rows, {"page": page, "pages": pages, "total": total}


def _allowed(resource: str) -> bool:
    cfg = RESOURCES[resource]
    return not cfg.get("admin_only") or current_user.is_admin


def _label_of(obj) -> str:
    """Texto corto para identificar un registro en mensajes y buscador."""
    for attr in ("name", "title", "label", "username", "donor_name", "code", "short"):
        value = getattr(obj, attr, None)
        if value:
            return str(value)
    return str(obj)


def _delete_images(obj) -> None:
    """Borra del disco las imagenes locales que cuelgan de un registro."""
    columns = {c.name for c in type(obj).__table__.columns}
    for attr in ("image", "banner"):
        if attr in columns:
            delete_upload(getattr(obj, attr, None))


# --------------------------------------------------------------------------- #
# Dashboard
# --------------------------------------------------------------------------- #
@bp.route("/")
def dashboard():
    today = date.today()
    now = utcnow()
    division = current_division()
    goal = donation_goal()

    stats = {
        "usuarios": User.query.count(),
        "usuarios_7d": User.query.filter(User.created_at >= now - timedelta(days=7)).count(),
        "staff": User.query.filter(User.role.in_(Role.TEAM), User.is_active_account.is_(True)).count(),
        "contenido": Article.query.filter(Article.is_published.is_(True)).count(),
        "noticias": Article.query.filter_by(kind=Category.NEWS).count(),
        "avisos": Article.query.filter_by(kind=Category.ANNOUNCEMENT).count(),
        "informes": Article.query.filter_by(kind=Category.REPORT).count(),
        "equipos": Team.query.count(),
        "equipos_sin_escudo": Team.query.filter(Team.image.is_(None), Team.image_url.is_(None)).count(),
        "jugadores": Player.query.count(),
        "partidos": Match.query.count(),
        "finalizados": Match.query.filter_by(status=Match.FINISHED).count(),
        "proximos": Match.query.filter(Match.played_on.isnot(None), Match.played_on >= today).count(),
        "salas": Room.query.filter_by(is_open=True).count(),
        "museo": MuseumItem.query.count(),
        "alianzas": Link.query.filter_by(kind=LinkKind.ALLIANCE).count(),
        "redes": Link.query.filter_by(kind=LinkKind.SOCIAL).count(),
        "live": LiveStream.query.filter_by(is_live=True).count(),
        "sugerencias": Suggestion.query.filter_by(status=SuggestionStatus.NEW).count(),
        "donaciones": Donation.query.count(),
        "donado": float(db.session.query(func.coalesce(func.sum(Donation.amount), 0)).scalar() or 0),
    }

    upcoming = (
        Match.query.filter(Match.played_on.isnot(None), Match.played_on >= today)
        .order_by(Match.played_on, Match.kickoff).limit(8).all()
    )
    top_teams = division_standings(division.id)[:5] if division else []
    recent_articles = Article.query.order_by(Article.created_at.desc()).limit(6).all()
    recent_users = User.query.order_by(User.created_at.desc()).limit(6).all()
    recent_activity = (
        Log.query.filter_by(kind=LogKind.ACTIVITY).order_by(Log.created_at.desc()).limit(8).all()
    )
    recent_emails = (
        Log.query.filter_by(kind=LogKind.EMAIL).order_by(Log.created_at.desc()).limit(6).all()
    )
    logged_in_today = db.session.query(User).filter(func.date(User.last_login) == today).count()
    pending_reports = (
        Match.query.filter(Match.status == Match.FINISHED)
        .outerjoin(MatchReport, MatchReport.match_id == Match.id)
        .filter(MatchReport.id.is_(None))
        .order_by(*nulls_last(Match.played_on))
        .limit(6)
        .all()
    )

    return render_template(
        "admin/dashboard.html",
        stats=stats,
        goal=goal,
        division=division,
        upcoming=upcoming,
        top_teams=top_teams,
        recent_articles=recent_articles,
        recent_users=recent_users,
        recent_activity=recent_activity,
        recent_emails=recent_emails,
        logged_in_today=logged_in_today,
        pending_reports=pending_reports,
        today=today,
    )


# --------------------------------------------------------------------------- #
# Buscador global
# --------------------------------------------------------------------------- #
@bp.route("/buscar", methods=["GET", "POST"])
def search():
    """Un solo campo de busqueda que barre todas las tablas del esquema."""
    form = SearchForm()
    term = (form.q.data or request.args.get("q") or "").strip()
    groups: list[dict] = []

    if len(term) >= 2:
        like = f"%{term}%"

        def hits(model, columns, limit=8):
            clauses = [getattr(model, col).ilike(like) for col in columns]
            return model.query.filter(or_(*clauses)).limit(limit).all()

        def entry(resource, obj, label=None):
            row = RESOURCES[resource]
            if row.get("row"):
                href = url_for(row["row"], pk=obj.id)
            elif _allowed(resource):
                href = url_for("admin.edit", resource=resource, pk=obj.id)
            else:
                href = url_for("admin.search", q=term)
            return (label or _label_of(obj), href)

        if not _allowed("usuarios"):
            visible_users = []
        else:
            visible_users = hits(User, ["username", "email", "display_name", "title"], 6)
        teams = hits(Team, ["name", "short", "coach"], 6)
        divisions = hits(Division, ["name", "short", "key"], 4)

        buckets = [
            ("Divisiones", [entry("divisiones", d) for d in divisions]),
            ("Equipos", [entry("equipos", t) for t in teams]),
            ("Jugadores", [entry("jugadores", p) for p in
                           hits(Player, ["username", "haxball_id"], 8)]),
            ("Articulos", [entry(Category.RESOURCE[a.kind], a) for a in
                           hits(Article, ["title", "summary", "body"], 8)]),
            ("Partidos", [entry("calendario", m, m.headline) for m in
                          hits(Match, ["stage", "notes"], 6)]),
            ("Museo", [entry("museo", i) for i in
                       hits(MuseumItem, ["title", "recipient"], 5)]),
            ("Salas", [entry("salas", r) for r in hits(Room, ["code", "name"], 5)]),
            ("Enlaces", [entry("enlaces", link) for link in
                        hits(Link, ["label", "handle", "account", "url"], 6)]),
            ("Live", [entry("live", stream) for stream in
                      hits(LiveStream, ["title", "league", "channel"], 5)]),
            ("Usuarios", [entry("usuarios", u, f"{u.label} · {u.email}") for u in visible_users]),
            ("Sugerencias", [(s.title, url_for("admin.suggestions", q=s.title))
                             for s in hits(Suggestion, ["title", "body"], 5)]),
            ("Donaciones", [entry("donaciones", d) for d in
                            hits(Donation, ["donor_name", "message"], 5)]),
        ]
        groups = [{"title": title, "rows": rows} for title, rows in buckets if rows]

    total = sum(len(group["rows"]) for group in groups)
    return render_template("admin/search.html", form=form, term=term, groups=groups, total=total)


# --------------------------------------------------------------------------- #
# Listado
# --------------------------------------------------------------------------- #
@bp.route("/<resource>/")
def list_resource(resource: str):
    if resource not in RESOURCES or not _allowed(resource):
        abort(404)
    cfg = RESOURCES[resource]
    rows, meta = _page(_query_for(resource)[0])
    return render_template(
        "admin/list.html",
        resource=resource,
        cfg=cfg,
        rows=rows,
        meta=meta,
        term=(request.args.get("q") or "").strip(),
    )


# --------------------------------------------------------------------------- #
# Crear
# --------------------------------------------------------------------------- #
@bp.route("/<resource>/nuevo", methods=["GET", "POST"])
def create(resource: str):
    if resource not in RESOURCES or not _allowed(resource):
        abort(404)
    cfg = RESOURCES[resource]
    form = cfg["form"]()
    _populate_choices(form, cfg)
    _preselect(form, cfg)

    if form.validate_on_submit():
        obj = cfg["model"]()
        _assign(form, obj, cfg, creating=True)
        db.session.add(obj)
        db.session.flush()
        log_activity(current_user, "crear", resource, obj.id, _label_of(obj)[:120])
        db.session.commit()
        flash(f"{_label_of(obj)} creado correctamente.", "success")
        return redirect(url_for("admin.list_resource", resource=resource))

    return render_template(
        "admin/form.html", resource=resource, cfg=cfg, form=form, obj=None,
        skip_fields=cfg.get("skip_fields", ()),
    )


# --------------------------------------------------------------------------- #
# Editar
# --------------------------------------------------------------------------- #
@bp.route("/<resource>/<int:pk>/editar", methods=["GET", "POST"])
def edit(resource: str, pk: int):
    if resource not in RESOURCES or not _allowed(resource):
        abort(404)
    cfg = RESOURCES[resource]
    obj = db.session.get(cfg["model"], pk) or abort(404)
    form = cfg["form"](obj=obj)
    _populate_choices(form, cfg, obj)
    _prefill_files(form, obj, cfg)

    if form.validate_on_submit():
        _assign(form, obj, cfg, creating=False)
        log_activity(current_user, "editar", resource, obj.id, _label_of(obj)[:120])
        db.session.commit()
        flash("Cambios guardados.", "success")
        return redirect(url_for("admin.list_resource", resource=resource))

    return render_template(
        "admin/form.html", resource=resource, cfg=cfg, form=form, obj=obj,
        skip_fields=cfg.get("skip_fields", ()),
    )


# --------------------------------------------------------------------------- #
# Eliminar (con cascadas explicitas)
# --------------------------------------------------------------------------- #
@bp.route("/<resource>/<int:pk>/eliminar", methods=["POST"])
def delete(resource: str, pk: int):
    if resource not in RESOURCES or not _allowed(resource):
        abort(404)
    cfg = RESOURCES[resource]
    obj = db.session.get(cfg["model"], pk) or abort(404)

    if isinstance(obj, User) and obj.id == current_user.id:
        flash("No puedes eliminar tu propia cuenta.", "error")
        return redirect(url_for("admin.list_resource", resource=resource))

    label = _label_of(obj)
    extra = _cascade(obj)
    log_activity(current_user, "eliminar", resource, pk, label[:120])
    db.session.commit()

    suffix = f" junto con {extra} registro(s) dependiente(s)." if extra else ""
    flash(f"{label} fue eliminado{suffix}", "info")
    return redirect(request.referrer or url_for("admin.list_resource", resource=resource))


def _cascade(obj) -> int:
    """Prepara el borrado en cascada y devuelve cuantos registros arrastra."""
    if isinstance(obj, Team):
        return _purge_team(obj)
    if isinstance(obj, Player):
        return _purge_player(obj)
    if isinstance(obj, Match):
        return _purge_match(obj)
    if isinstance(obj, Division):
        return _purge_division(obj)
    if isinstance(obj, User):
        return _purge_user(obj)

    _delete_images(obj)
    db.session.delete(obj)
    return 0


def _purge_match(match: Match) -> int:
    """Borra el partido con su informe y sus filas de estadisticas."""
    extra = len(match.player_stats or []) + (1 if match.report else 0)
    db.session.delete(match)  # report y player_stats van en delete-orphan
    return extra


def _purge_player(player: Player) -> int:
    extra = MatchStat.query.filter_by(player_id=player.id).count()
    MatchReport.query.filter(MatchReport.mvp_player_id == player.id).update(
        {"mvp_player_id": None}, synchronize_session=False)
    db.session.delete(player)  # sus match_stats van en delete-orphan
    return extra


def _purge_team(team: Team) -> int:
    """Un equipo se lleva su plantilla, sus partidos, informes y estadisticas."""
    players = list(team.players)
    player_ids = [p.id for p in players]
    match_ids = [row[0] for row in db.session.query(Match.id).filter(
        or_(Match.home_team_id == team.id, Match.away_team_id == team.id)).all()]

    extra = len(players)
    if player_ids:
        extra += MatchStat.query.filter(MatchStat.player_id.in_(player_ids)).count()
        MatchReport.query.filter(MatchReport.mvp_player_id.in_(player_ids)).update(
            {"mvp_player_id": None}, synchronize_session=False)
    if match_ids:
        extra += len(match_ids)
        extra += MatchReport.query.filter(MatchReport.match_id.in_(match_ids)).count()
        for match in db.session.query(Match).filter(Match.id.in_(match_ids)).all():
            db.session.delete(match)

    MuseumItem.query.filter(MuseumItem.team_id == team.id).update(
        {"team_id": None}, synchronize_session=False)

    for player in players:
        db.session.delete(player)
    delete_upload(team.image)
    db.session.delete(team)  # sus match_stats van en delete-orphan
    return extra


def _purge_division(division: Division) -> int:
    """Una division se lleva sus notas y partidos; los equipos quedan sin division."""
    matches = db.session.query(Match).filter(Match.division_id == division.id).all()
    match_ids = [m.id for m in matches]
    teams = Team.query.filter_by(division_id=division.id).count()

    extra = len(division.notes) + len(matches) + teams
    if match_ids:
        extra += MatchReport.query.filter(MatchReport.match_id.in_(match_ids)).count()
        extra += MatchStat.query.filter(MatchStat.match_id.in_(match_ids)).count()

    Article.query.filter(Article.division_id == division.id).update(
        {"division_id": None}, synchronize_session=False)
    Team.query.filter(Team.division_id == division.id).update(
        {"division_id": None}, synchronize_session=False)
    for match in matches:
        db.session.delete(match)
    for note in list(division.notes):
        db.session.delete(note)
    db.session.delete(division)
    return extra


def _purge_user(user: User) -> int:
    """Las sugerencias son de la persona, el resto de rastros se desatacan."""
    Suggestion.query.filter(Suggestion.replied_by_id == user.id).update(
        {"replied_by_id": None}, synchronize_session=False)
    extra = Suggestion.query.filter_by(user_id=user.id).count()
    Suggestion.query.filter_by(user_id=user.id).delete(synchronize_session=False)
    PasswordResetToken.query.filter_by(user_id=user.id).delete(synchronize_session=False)
    Log.query.filter(Log.user_id == user.id).update({"user_id": None}, synchronize_session=False)
    Article.query.filter(Article.author_id == user.id).update(
        {"author_id": None}, synchronize_session=False)
    MatchReport.query.filter(MatchReport.author_id == user.id).update(
        {"author_id": None}, synchronize_session=False)

    delete_upload(user.image)
    delete_upload(user.banner)
    db.session.delete(user)
    return extra


# --------------------------------------------------------------------------- #
# Activar / desactivar rapido
# --------------------------------------------------------------------------- #
TOGGLE_FLAGS = ("is_published", "is_active", "is_open", "is_active_account", "is_live",
                "is_public", "is_featured", "is_pinned", "is_highlight")


@bp.route("/<resource>/<int:pk>/toggle", methods=["POST"])
def toggle(resource: str, pk: int):
    if resource not in RESOURCES or not _allowed(resource):
        abort(404)
    cfg = RESOURCES[resource]
    obj = db.session.get(cfg["model"], pk) or abort(404)
    if not BooleanOnlyForm().validate_on_submit():
        abort(400)

    for attr in TOGGLE_FLAGS:
        if hasattr(obj, attr):
            setattr(obj, attr, not getattr(obj, attr))
            break
    db.session.commit()
    flash("Estado actualizado.", "success")
    return redirect(request.referrer or url_for("admin.list_resource", resource=resource))


# --------------------------------------------------------------------------- #
# Equipos: ficha, escudo, plantilla y borrado en cascada
# --------------------------------------------------------------------------- #
@bp.route("/equipos/<int:pk>")
def team_detail(pk: int):
    team = db.session.get(Team, pk) or abort(404)

    crest_form = TeamCrestForm(obj={"crest_url": team.image_url or ""})
    roster_form = RosterPlayerForm()

    matches = (
        Match.query.filter(or_(Match.home_team_id == team.id, Match.away_team_id == team.id))
        .order_by(*nulls_last(Match.played_on, descending=False), Match.journey.desc())
        .limit(30)
        .all()
    )

    return render_template(
        "admin/team_detail.html",
        team=team,
        crest_form=crest_form,
        roster_form=roster_form,
        matches=matches,
        standing=team_standing(team.id),
        totals=team.totals,
    )


@bp.route("/equipos/<int:pk>/escudo", methods=["POST"])
def team_crest(pk: int):
    """Sube, cambia o quita el escudo sin tocar el resto de la ficha."""
    team = db.session.get(Team, pk) or abort(404)
    form = TeamCrestForm()
    if not form.validate_on_submit():
        flash("No se pudo guardar el escudo. Revisa que sea una imagen.", "error")
        return redirect(url_for("admin.team_detail", pk=team.id))

    if form.remove_crest.data and not form.crest.data:
        delete_upload(team.image)
        team.image = team.image_url = None
        db.session.commit()
        flash("Escudo eliminado.", "info")
        return redirect(url_for("admin.team_detail", pk=team.id))

    if form.crest_url.data:
        team.image_url = form.crest_url.data.strip() or None

    if form.crest.data:
        saved = save_upload(form.crest.data, subfolder="escudos")
        if saved:
            delete_upload(team.image)
            team.image = saved

    db.session.commit()
    log_activity(current_user, "escudo", "equipos", team.id, f"escudo de {team.name}")
    flash("Escudo actualizado.", "success")
    return redirect(url_for("admin.team_detail", pk=team.id))


@bp.route("/equipos/<int:pk>/jugadores", methods=["POST"])
def team_add_player(pk: int):
    """Da de alta la plantilla pegando los usuarios de HaxBall, uno por linea."""
    team = db.session.get(Team, pk) or abort(404)
    form = RosterPlayerForm()
    if not form.validate_on_submit():
        flash("Escribe al menos un usuario.", "error")
        return redirect(url_for("admin.team_detail", pk=team.id))

    existing = {p.username.lower() for p in team.players}
    added, skipped = [], []
    for raw in (form.usernames.data or "").splitlines():
        username = raw.strip().replace(" ", "_")
        if not username or username.lower() in existing:
            if username:
                skipped.append(username)
            continue
        existing.add(username.lower())
        db.session.add(Player(
            team_id=team.id,
            username=username,
            position=form.position.data or "MF",
            is_active=bool(form.activate.data),
        ))
        added.append(username)

    if added:
        db.session.flush()
        log_activity(current_user, "anadir_jugador", "equipos", team.id,
                     f"{len(added)} -> {team.name}")
    db.session.commit()

    flash(f"{len(added)} jugador(es) anadidos a {team.name}"
          + (f"; {len(skipped)} ya estaban." if skipped else "."), "success")
    return redirect(url_for("admin.team_detail", pk=team.id))


@bp.route("/equipos/<int:pk>/jugadores/<int:player_id>/quitar", methods=["POST"])
def team_remove_player(pk: int, player_id: int):
    """Saca a un jugador de la plantilla (conserva su historial)."""
    team = db.session.get(Team, pk) or abort(404)
    player = db.session.get(Player, player_id) or abort(404)
    if player.team_id != team.id:
        abort(404)
    if not BooleanOnlyForm().validate_on_submit():
        abort(400)

    history = MatchStat.query.filter_by(player_id=player.id).count()
    if history:
        player.is_active = False
        db.session.commit()
        flash(f"{player.username} salio de la plantilla activa; "
              f"su historial de {history} partidos se conserva.", "info")
    else:
        _purge_player(player)
        db.session.commit()
        flash(f"{player.username} fue eliminado de la plantilla.", "info")
    return redirect(url_for("admin.team_detail", pk=team.id))


# --------------------------------------------------------------------------- #
# Acciones especiales
# --------------------------------------------------------------------------- #
@bp.route("/articulos/<int:pk>/duplicar", methods=["POST"])
def duplicate_article(pk: int):
    if not BooleanOnlyForm().validate_on_submit():
        abort(400)
    src = db.session.get(Article, pk) or abort(404)
    clone = Article(
        kind=src.kind, category=src.category, title=f"{src.title} (copia)",
        summary=src.summary, body=src.body, image=src.image, image_url=src.image_url,
        is_published=False, author_id=current_user.id, division_id=src.division_id,
    )
    clone.slug = f"{slugify(clone.title)}-{secrets.token_hex(3)}"
    db.session.add(clone)
    db.session.commit()
    flash("Articulo duplicado como borrador.", "success")
    return redirect(url_for("admin.edit", resource=Category.RESOURCE[clone.kind], pk=clone.id))


@bp.route("/usuarios/<int:pk>/toggle-admin", methods=["POST"])
def promote(pk: int):
    if not BooleanOnlyForm().validate_on_submit():
        abort(400)
    user = db.session.get(User, pk) or abort(404)
    if user.id == current_user.id:
        flash("No puedes quitarte a ti mismo el acceso de administrador.", "error")
        return redirect(request.referrer or url_for("admin.list_resource", resource="usuarios"))

    if user.is_admin:
        admins = User.query.filter(User.is_admin.is_(True)).count()
        if admins <= 1:
            flash("Debe quedar al menos un administrador activo.", "error")
            return redirect(request.referrer or url_for("admin.list_resource", resource="usuarios"))

    user.is_admin = not user.is_admin
    if user.is_admin:
        user.role = Role.ADMIN
    elif user.role == Role.ADMIN:
        user.role = Role.STAFF
    db.session.commit()
    flash(f"{user.label} ahora {'es' if user.is_admin else 'ya no es'} administrador.", "success")
    return redirect(request.referrer or url_for("admin.list_resource", resource="usuarios"))


@bp.route("/estadisticas/recalcular", methods=["POST"])
def recalculate_stats():
    """Rehace los acumulados de cada jugador desde ``match_stats``."""
    if not BooleanOnlyForm().validate_on_submit():
        abort(400)
    updated = recalculate_player_stats()
    flash(f"Estadisticas de {updated} jugadores recalculadas desde los informes.", "success")
    return redirect(request.referrer or url_for("admin.dashboard"))


# --------------------------------------------------------------------------- #
# Informes de partido: cola + formulario unico
# --------------------------------------------------------------------------- #
@bp.route("/informes-partido")
def match_reports():
    """Partidos finalizados y estado de su informe, para no dejar ninguno sin texto."""
    state = (request.args.get("estado") or "").strip()
    query = Match.query
    if state == "sin_informe":
        query = query.filter(Match.status == Match.FINISHED).outerjoin(
            MatchReport, MatchReport.match_id == Match.id).filter(MatchReport.id.is_(None))
    elif state == "con_informe":
        query = query.join(MatchReport, MatchReport.match_id == Match.id)
    elif state == Match.FINISHED:
        query = query.filter(Match.status == Match.FINISHED)

    rows = query.order_by(*nulls_last(Match.played_on, descending=False)).limit(80).all()
    return render_template(
        "admin/match_reports.html",
        rows=rows,
        state=state,
        total=Match.query.count(),
        pending=Match.query.filter(Match.status == Match.FINISHED).outerjoin(
            MatchReport, MatchReport.match_id == Match.id).filter(MatchReport.id.is_(None)).count(),
    )


#: Columnas de la rejilla de estadisticas: (columna, etiqueta corta, maximo).
STAT_FIELDS = (
    ("goals", "G", 99),
    ("assists", "A", 99),
    ("clean_sheets", "CS", 9),
    ("own_goals", "AG", 99),
    ("yellow_cards", "TA", 9),
    ("red_cards", "TR", 9),
    ("minutes", "MIN", 200),
)


def _stat_grid(match: Match) -> list[dict]:
    """Una fila por jugador de la plantilla, con sus numeros cargados."""
    existing = {stat.player_id: stat for stat in (match.player_stats or [])}
    grid = []
    for player in match.roster:
        stat = existing.get(player.id)
        grid.append({
            "player": player,
            "stat": stat,
            "values": {name: (getattr(stat, name, 0) if stat else 0) or 0
                       for name, _label, _limit in STAT_FIELDS},
        })
    return grid


@bp.route("/partidos/<int:pk>/informe", methods=["GET", "POST"])
def match_report(pk: int):
    """Informe de partido completo en un solo formulario.

    En la misma pantalla se guardan la foto y la cronica, el jugador del partido
    y toda la rejilla de estadisticas; el marcador sale de esas fichas.
    """
    match = db.session.get(Match, pk) or abort(404)
    report = match.report or MatchReport(match_id=match.id)
    form = MatchReportForm(obj=report)
    if not form.is_submitted():
        # El campo del formulario se llama `photo_url` y la columna `image_url`.
        form.photo_url.data = report.image_url or ""
    form.mvp_player_id.choices = [("", "Sin jugador del partido")] + [
        (str(p.id), f"{p.username} · {p.position or 'MF'} · "
                   f"{p.team.short if p.team else 'sin equipo'}")
        for p in match.roster
    ]
    if report.mvp_player_id and not any(
            str(report.mvp_player_id) == value for value, _ in form.mvp_player_id.choices):
        guardado = db.session.get(Player, report.mvp_player_id)
        if guardado is not None:
            form.mvp_player_id.choices.append(
                (str(guardado.id), f"{guardado.username} · (MVP guardado)"))

    if form.validate_on_submit():
        _save_report(form, report, match, creating=match.report is None)
        cambios = _apply_stat_grid(match, form.mvp_player_id.data)
        db.session.commit()
        recalculate_player_stats()  # hace commit de los acumulados
        log_activity(current_user, "informe", "partidos", match.id, match.headline)
        db.session.commit()

        detalle = ", ".join(
            f"{n} {texto}" for texto, n in (
                ("nuevas", cambios["created"]), ("editadas", cambios["updated"]),
                ("borradas", cambios["removed"])) if n)
        flash(f"Informe guardado ({detalle or 'sin cambios en las estadisticas'}). "
              f"Resultado: {match.score_text}.", "success")
        return redirect(url_for("admin.match_report", pk=match.id))

    return render_template(
        "admin/match_report.html",
        match=match,
        report=report,
        form=form,
        grid=_stat_grid(match),
        stat_fields=STAT_FIELDS,
        home_stats=match.stats_for(match.home_team_id),
        away_stats=match.stats_for(match.away_team_id),
        scorers=match.scorers,
        computed=(match.home_goals_from_stats, match.away_goals_from_stats),
    )


def _save_report(form: MatchReportForm, report: MatchReport, match: Match, creating: bool) -> None:
    """Guarda los campos del informe y su foto (subida o URL)."""
    columns = {c.name for c in MatchReport.__table__.columns}
    skip = {"photo", "photo_url", "remove_photo", "csrf_token", "submit", "mvp_player_id"}
    for name, field in form._fields.items():
        if name in skip or name not in columns:
            continue
        value = field.data
        if isinstance(value, str):
            value = value.strip() or None
        setattr(report, name, value)

    if form.photo_url.data:
        report.image_url = form.photo_url.data.strip() or None
    if form.photo.data:
        saved = save_upload(form.photo.data, subfolder="partidos")
        if saved:
            delete_upload(report.image)
            report.image = saved
    if form.remove_photo.data and not form.photo.data:
        delete_upload(report.image)
        report.image = None

    if not report.author_id:
        report.author_id = current_user.id
    report.mvp_player_id = form.mvp_player_id.data or None
    if creating:
        db.session.add(report)


def _clamp_int(raw, limit: int) -> int:
    try:
        return max(0, min(int(str(raw).strip() or 0), limit))
    except (TypeError, ValueError):
        return 0


def _apply_stat_grid(match: Match, mvp_player_id: int | None) -> dict[str, int]:
    """Lee la rejilla de estadisticas del formulario y la refleja en la tabla.

    Los nombres de los inputs son ``stat-<player_id>-<columna>``: una fila a cero
    (y sin MVP) borra la ficha existente, y las que tengan numeros se crean o se
    actualizan. El MVP se marca desde el select del propio formulario.
    """
    existing = {stat.player_id: stat for stat in (match.player_stats or [])}
    counts = {"created": 0, "updated": 0, "removed": 0}

    for player in match.roster:
        prefix = f"stat-{player.id}-"
        values = {name: _clamp_int(request.form.get(prefix + name), limit)
                  for name, _label, limit in STAT_FIELDS}
        stat = existing.pop(player.id, None)

        if not any(values.values()) and stat is None:
            continue
        if not any(values.values()):
            db.session.delete(stat)
            counts["removed"] += 1
            continue

        if stat is None:
            stat = MatchStat(match=match, player_id=player.id, team_id=player.team_id)
            db.session.add(stat)
            counts["created"] += 1
        else:
            counts["updated"] += 1
        for name, value in values.items():
            setattr(stat, name, value)
        stat.is_mvp = bool(mvp_player_id) and stat.player_id == mvp_player_id

    # El MVP tambien se propaga a las fichas que ya existian.
    for stat in match.player_stats or []:
        stat.is_mvp = bool(mvp_player_id) and stat.player_id == mvp_player_id

    match.sync_score_from_stats()
    return counts


# --------------------------------------------------------------------------- #
# Sugerencias de la comunidad
# --------------------------------------------------------------------------- #
@bp.route("/sugerencias")
def suggestions():
    """Todo lo que opinaron los jugadores, para responderlo desde el panel."""
    query = Suggestion.query
    estado = (request.args.get("estado") or "").strip()
    categoria = (request.args.get("categoria") or "").strip()
    term = (request.args.get("q") or "").strip()

    if estado in SuggestionStatus.ALL:
        query = query.filter(Suggestion.status == estado)
    if categoria in SUGGESTION_CATEGORIES:
        query = query.filter(Suggestion.category == categoria)
    if term:
        query = query.filter(or_(Suggestion.title.ilike(f"%{term}%"),
                                 Suggestion.body.ilike(f"%{term}%")))

    rows = query.order_by(Suggestion.created_at.desc(), Suggestion.id.desc()).limit(120).all()
    return render_template(
        "admin/suggestions.html",
        rows=rows,
        estado=estado,
        categoria=categoria,
        term=term,
        total=Suggestion.query.count(),
        nuevas=Suggestion.query.filter_by(status=SuggestionStatus.NEW).count(),
        categories=SUGGESTION_CATEGORIES,
    )


@bp.route("/sugerencias/<int:pk>/responder", methods=["POST"])
def suggestion_reply(pk: int):
    """Responde a una sugerencia y avisa al jugador por correo."""
    from mailer import send_suggestion_reply_email

    suggestion = db.session.get(Suggestion, pk) or abort(404)
    form = SuggestionReplyForm()
    if not form.validate_on_submit():
        abort(400)

    suggestion.status = form.status.data
    suggestion.staff_reply = (form.staff_reply.data or "").strip() or None
    suggestion.replied_by_id = current_user.id
    suggestion.replied_at = utcnow() if suggestion.staff_reply else None
    log_activity(current_user, "responde", "sugerencia", suggestion.id, suggestion.status)
    db.session.commit()

    if suggestion.staff_reply:
        send_suggestion_reply_email(suggestion)
    flash("Respuesta guardada y enviada al jugador.", "success")
    return redirect(request.referrer or url_for("admin.suggestions"))


@bp.route("/sugerencias/<int:pk>/eliminar", methods=["POST"])
def suggestion_delete(pk: int):
    suggestion = db.session.get(Suggestion, pk) or abort(404)
    if not BooleanOnlyForm().validate_on_submit():
        abort(400)
    log_activity(current_user, "elimina", "sugerencia", suggestion.id, suggestion.title)
    db.session.delete(suggestion)
    db.session.commit()
    flash("Sugerencia eliminada.", "info")
    return redirect(request.referrer or url_for("admin.suggestions"))


# --------------------------------------------------------------------------- #
# Meta de donacion (vive en settings)
# --------------------------------------------------------------------------- #
@bp.route("/meta-donacion", methods=["GET", "POST"])
def donation_goal_settings():
    form = DonationGoalForm()
    if not form.is_submitted():
        form.title.data = setting("donation_goal_title", "Meta de la temporada")
        form.target.data = _as_decimal(setting("donation_goal_target", ""), Decimal("0"))
        form.note.data = setting("donation_goal_note", "")
        form.link.data = setting("donation_goal_link", "")

    if form.validate_on_submit():
        set_setting("donation_goal_title", (form.title.data or "").strip(),
                    group="donacion", label="Titulo de la meta", input_type="text")
        set_setting("donation_goal_target", str(form.target.data or 0),
                    group="donacion", label="Meta de la temporada", input_type="number")
        set_setting("donation_goal_note", (form.note.data or "").strip(),
                    group="donacion", label="Nota de la meta", input_type="textarea")
        set_setting("donation_goal_link", (form.link.data or "").strip(),
                    group="donacion", label="Enlace de pago", input_type="url")
        db.session.commit()
        flash("Meta de donacion actualizada.", "success")
        return redirect(url_for("admin.donation_goal_settings"))

    return render_template("admin/donation_goal.html", form=form, goal=donation_goal())


# --------------------------------------------------------------------------- #
# Correo y actividad (tabla unificada ``logs``)
# --------------------------------------------------------------------------- #
@bp.route("/correos")
def email_log():
    """Historial unificado: correos enviados por la app y actividad del panel."""
    vista = (request.args.get("vista") or "correos").strip()
    kind = LogKind.EMAIL if vista != "actividad" else LogKind.ACTIVITY
    term = (request.args.get("q") or "").strip()

    query = Log.query.filter_by(kind=kind)
    if term:
        query = query.filter(or_(Log.to_email.ilike(f"%{term}%"),
                                 Log.subject.ilike(f"%{term}%"),
                                 Log.detail.ilike(f"%{term}%"),
                                 Log.entity.ilike(f"%{term}%")))
    rows = query.order_by(Log.created_at.desc(), Log.id.desc()).limit(150).all()

    return render_template(
        "admin/email_log.html",
        rows=rows,
        term=term,
        vista=vista,
        failed=Log.query.filter_by(kind=LogKind.EMAIL, status="failed").count(),
        sent=Log.query.filter_by(kind=LogKind.EMAIL, status="sent").count(),
    )


@bp.route("/correos/<int:pk>/reenviar", methods=["POST"])
def email_log_resend(pk: int):
    """Reenvia un correo que fallo (p. ej. tras arreglar el SMTP)."""
    from mailer import send_email

    record = db.session.get(Log, pk) or abort(404)
    if not BooleanOnlyForm().validate_on_submit():
        abort(400)
    if record.kind != LogKind.EMAIL or record.status == "sent":
        flash("Ese correo ya se habia enviado.", "info")
        return redirect(url_for("admin.email_log"))

    ok = send_email(record.to_email, record.subject, _fallback_body(record),
                    user=record.user, template=record.template)
    record.status = "sent" if ok else "failed"
    if ok:
        record.error = None
    db.session.commit()
    flash("Correo reenviado." if ok else
          "El correo vuelve a fallar. Revisa MAIL_USERNAME y MAIL_PASSWORD.",
          "success" if ok else "error")
    return redirect(url_for("admin.email_log"))


def _fallback_body(record: Log) -> str:
    from models import PALETTE

    return (
        f'<div style="font-family:Inter,sans-serif;color:#F2F4FB;background:{PALETTE["bg_deep"]};'
        f'padding:24px;border-radius:12px">'
        f'<p style="margin:0 0 10px;color:{PALETTE["secondary"]};font:700 12px/1 IBM Plex Mono,monospace;'
        f'letter-spacing:.2em;text-transform:uppercase">The Diamonds League</p>'
        f'<h1 style="margin:0 0 14px;color:#fff">{record.subject}</h1>'
        f'<p style="margin:0">Este es el contenido reenviado del aviso de {record.to_email}.</p>'
        f'</div>'
    )


# --------------------------------------------------------------------------- #
# Ajustes del sitio
# --------------------------------------------------------------------------- #
SETTINGS_GROUPS = {
    "liga": ("Datos de la liga", [
        ("league_name", "Nombre de la liga", "text"),
        ("league_tagline", "Bajada / eslogan", "text"),
        ("league_modality", "Modalidad", "text"),
        ("league_status", "Estado de la liga", "text"),
        ("league_description", "Descripcion", "textarea"),
    ]),
    "streams": ("Live de futbol", [
        ("live_headline", "Titulo del bloque LIVE FUTBOL", "text"),
        ("live_description", "Descripcion", "textarea"),
    ]),
    "donacion": ("Bloque DONACION", [
        ("donation_headline", "Titulo", "text"),
        ("donation_description", "Descripcion", "textarea"),
        ("donation_note", "Nota al pie", "text"),
    ]),
    "avances": ("Opciones de la interfaz", [
        ("show_premium_panel", "Mostrar bloque premium en la pagina publica", "bool"),
        ("show_admin_shortcut", "Mostrar acceso rapido al panel", "bool"),
        ("maintenance_mode", "Modo mantenimiento", "bool"),
    ]),
}


@bp.route("/ajustes", methods=["GET"])
def settings():
    rows = Setting.query.order_by(Setting.group, Setting.key).all()
    by_group: dict[str, list] = {}
    for row in rows:
        by_group.setdefault(row.group or "general", []).append(row)
    return render_template("admin/settings.html", groups=SETTINGS_GROUPS, values=by_group)


@bp.route("/ajustes", methods=["POST"])
def settings_save():
    payload = request.form.get("values") or "{}"
    try:
        import json

        data = json.loads(payload)
    except ValueError:
        data = {}

    for group, (_title, fields) in SETTINGS_GROUPS.items():
        for key, label, _kind in fields:
            if key not in data:
                continue
            value = "1" if data[key] is True else ("" if data[key] is None else str(data[key]))
            set_setting(key, value, group=group, label=label)
    db.session.commit()
    flash("Ajustes guardados.", "success")
    return redirect(url_for("admin.settings"))


# --------------------------------------------------------------------------- #
# Form helpers
# --------------------------------------------------------------------------- #
def _populate_choices(form, cfg: dict | None = None, obj=None) -> None:
    """Inyecta opciones dinamicas en los SelectField que llegan vacios."""
    for name, field in form._fields.items():
        if not isinstance(field, SelectField) or field.choices:
            continue
        if name == "division_id":
            field.choices = [("", "Sin division")] + [
                (str(d.id), f"{d.short} · {d.name}") for d in
                Division.query.order_by(Division.level, Division.name).all()
            ]
        elif name in ("team_id", "home_team_id", "away_team_id"):
            field.choices = [
                (str(t.id), f"{t.name} ({t.division.short if t.division else 'sin division'})")
                for t in Team.query.order_by(Team.sort_order, Team.name).all()
            ]
        elif name in ("group", "subkind") and cfg is not None and cfg["model"] is Link:
            kind = (getattr(obj, "kind", None) or form.kind.data or LinkKind.SOCIAL)
            field.choices = _link_choices(name, kind)


def _link_choices(field_name: str, kind: str) -> list[tuple[str, str]]:
    if field_name == "subkind":
        if kind == LinkKind.ALLIANCE:
            return [("partner", "Servidor partner"), ("affiliate", "Afiliado")]
        if kind == LinkKind.DONATION:
            return [("", "Sin metodo")] + [(m, Link.PAYMENT_LABELS[m])
                                            for m in Link.PAYMENT_METHODS]
        return [("", "Sin plataforma")] + [(p, label) for p, label in Link.PLATFORM_LABELS.items()]
    if kind == LinkKind.ALLIANCE:
        return [("", "Sin estado")] + [(s, label) for s, label in
                                       Link.ALLIANCE_STATUS_LABELS.items()]
    return [("", "Sin dueno")] + [(o, label) for o, label in Link.OWNER_LABELS.items()]


def _preselect(form, cfg: dict) -> None:
    """Valores por defecto del formulario de alta."""
    if cfg["model"] is Match:
        division = current_division()
        if division is not None:
            form.division_id.data = division.id


def _prefill_files(form, obj, cfg: dict) -> None:
    """Rellena los campos de URL de imagen con lo que ya tiene el registro.

    El formulario llama ``crest_url`` a la columna ``image_url``, asi que
    WTForms no encuentra el valor por su cuenta y lo borraria al guardar.
    """
    for name, column in (cfg.get("files") or {}).items():
        field = form._fields.get(name)
        if field is None or isinstance(field, FileField):
            continue
        value = getattr(obj, column, None)
        if value:
            field.data = value


def _assign(form, obj, cfg: dict, creating: bool) -> None:
    """Vuelca el formulario en el modelo: columnas, imagenes y reglas por tipo."""
    model = cfg["model"]
    columns = {c.name for c in model.__table__.columns}
    files = cfg.get("files", {})

    for name, field in form._fields.items():
        if isinstance(field, FileField) or name in files:
            continue  # las imagenes se resuelven al final
        if name.startswith("remove_") or name not in columns:
            continue
        data = field.data
        if isinstance(data, str):
            data = data.strip() or None
            if data is None and name in ("title", "name", "label", "username"):
                continue
        setattr(obj, name, data)

    _assign_files(form, obj, cfg, columns, files, creating)

    for key, value in (cfg.get("filters") or {}).items():
        setattr(obj, key, value)

    if isinstance(obj, User):
        _assign_user(form, obj, creating)
    elif isinstance(obj, Article):
        _assign_article(obj, creating)
    elif isinstance(obj, Donation) and not obj.donated_at:
        obj.donated_at = utcnow()
    elif isinstance(obj, Division) and obj.is_current:
        Division.query.filter(Division.is_current.is_(True),
                              Division.id != obj.id).update(
            {"is_current": False}, synchronize_session=False)


def _assign_files(form, obj, cfg: dict, columns: set[str], files: dict, creating: bool) -> None:
    """Sube los archivos del formulario y guarda tambien la version por URL."""
    for name, column in files.items():
        field = form._fields.get(name)
        if field is None or column not in columns:
            continue
        if isinstance(field, FileField):
            if field.data:
                saved = save_upload(field.data, subfolder=cfg["title"].lower())
                if saved:
                    old = getattr(obj, column, None)
                    setattr(obj, column, saved)
                    if not creating:
                        delete_upload(old)
            remove = form._fields.get(f"remove_{name}")
            if remove is not None and remove.data and not field.data:
                delete_upload(getattr(obj, column, None))
                setattr(obj, column, None)
        else:
            setattr(obj, column, (field.data or "").strip() or None)


def _assign_user(form, obj: User, creating: bool) -> None:
    """Contrasena y coherencia entre ``role`` e ``is_admin``."""
    raw = form.password.data
    if raw:
        obj.set_password(raw)
    obj.is_admin = obj.role == Role.ADMIN
    if obj.role != Role.ADMIN and obj.is_admin and not current_user.is_admin:
        obj.role = Role.STAFF


def _assign_article(obj: Article, creating: bool) -> None:
    obj.title = (obj.title or "").strip()
    if creating or not obj.slug:
        obj.slug = _unique_slug(Article, obj.title or "articulo", obj.id)
    if not obj.published_at:
        obj.published_at = utcnow()
    if obj.author_id is None:
        obj.author_id = current_user.id


def _unique_slug(model, title: str, ignore_id: int | None = None) -> str:
    base = slugify(title)
    candidate, index = base, 2
    while True:
        existing = model.query.filter_by(slug=candidate).first()
        if existing is None or (ignore_id and existing.id == ignore_id):
            return candidate
        candidate = f"{base}-{index}"
        index += 1


@bp.app_context_processor
def inject_helpers():
    return {
        "resources": RESOURCES,
        "sections": SECTIONS,
        "section_by_key": SECTION_BY_KEY,
        "now": utcnow,
        "Role": Role,
    }
