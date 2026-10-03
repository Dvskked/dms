"""Blueprint del panel de administracion.

Un CRUD generico por recurso (definido en RESOURCES) + un dashboard con metricas.
Todo lo que cuelga de /admin exige rol admin o staff segun el recurso.
"""
from __future__ import annotations

import secrets
from datetime import date, datetime, timedelta
from functools import wraps

from flask import Blueprint, abort, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required
from sqlalchemy import func, or_
from wtforms.fields import FileField, SelectField

from extensions import db
from forms import (
    AllianceForm, ArticleForm, BooleanOnlyForm, DonationChannelForm, DonationForm, DivisionForm,
    FlaskForm, LiveStreamForm, MatchForm, MuseumForm, PlayerForm, RoomForm, RuleForm, SanctionLevelForm,
    SocialForm, StaffForm, TeamForm, UserForm,
)
from forms import MatchReportForm, PlayerStatForm, RosterPlayerForm, SuggestionReplyForm, TeamCrestForm
from models import (
    Alliance, Article, Category, Division, Donation, DonationChannel, EmailLog, LiveStream, Match,
    MatchReport, MuseumItem, Player, PlayerMatchStat, Role, Room, RuleEntry, SanctionLevel, SiteSetting,
    SocialLink, StaffMember, Standing, Suggestion, SuggestionStatus, Team, User, current_season,
    log_activity, recompute_player_stats, set_setting,
)
from utils import delete_upload, nulls_last, save_upload, slugify, utcnow

bp = Blueprint("admin", __name__, url_prefix="/admin")


# --------------------------------------------------------------------------- #
# Guards
# --------------------------------------------------------------------------- #
@bp.before_request
@login_required
def _guard():
    if not current_user.is_staff:
        abort(403)
    if request.endpoint in ADMIN_ONLY_ENDPOINTS and not current_user.is_admin:
        abort(403)


# Rutas reservadas al administrador (no al resto del staff).
ADMIN_ONLY_ENDPOINTS = {
    "admin.promote", "admin.recalculate_standings", "admin.recalculate_player_stats",
    "admin.settings", "admin.settings_save", "admin.duplicate_article", "admin.email_log",
    "admin.email_log_resend",
}


# --------------------------------------------------------------------------- #
# Configuracion de recursos
# --------------------------------------------------------------------------- #
RESOURCES: dict[str, dict] = {
    "avisos": dict(
        model=Article, form=ArticleForm, icon="01", title="Avisos y novedades",
        subtitle="Comunicados, inscripciones y alertas de la liga.",
        fields=["id", "title", "category", "is_pinned", "is_published", "published_at", "actions"],
        search=["title", "summary"],
        filters={"kind": Category.ANNOUNCEMENT},
        order=(Article.is_pinned.desc(), Article.is_published.desc(), Article.published_at.desc()),
        icon_name="megaphone",
    ),
    "noticias": dict(
        model=Article, form=ArticleForm, icon="02", title="Noticias y reportarias",
        subtitle="Todo el contenido editorial reciente de la liga.",
        fields=["id", "title", "category", "is_featured", "is_published", "published_at", "actions"],
        search=["title", "summary"],
        filters={"kind": Category.NEWS},
        order=(Article.is_featured.desc(), Article.published_at.desc()),
    ),
    "informes": dict(
        model=Article, form=ArticleForm, icon="03", title="Informes",
        subtitle="Reportes, resumenes de jornada y documentos internos.",
        fields=["id", "title", "category", "is_published", "published_at", "actions"],
        search=["title", "summary", "body"],
        filters={"kind": Category.REPORT},
        order=(Article.published_at.desc(),),
    ),
    "equipos": dict(
        model=Team, form=TeamForm, icon="04", title="Equipos",
        subtitle="Plantillas, escudos y division de cada club.",
        fields=["id", "name", "crest", "division", "coach", "player_count", "is_active", "actions"],
        search=["name", "short", "coach", "captain"],
        order=(Team.sort_order, Team.name),
    ),
    "jugadores": dict(
        model=Player, form=PlayerForm, icon="05", title="Jugadores",
        subtitle="Nominas, posiciones y estadisticas individuales.",
        fields=["id", "username", "team", "position", "goals", "assists", "is_active", "actions"],
        search=["username", "haxball_id"],
        order=(Player.username,),
    ),
    "calendario": dict(
        model=Match, form=MatchForm, icon="06", title="Calendario y partidos",
        subtitle="Fechas, jornadas, marcadores y enlaces de sala.",
        fields=["id", "journey", "played_on", "home_team", "away_team", "score_text", "status", "actions"],
        search=["stage"],
        order=(Match.journey, *nulls_last(Match.played_on, descending=False), Match.kickoff),
    ),
    "salas": dict(
        model=Room, form=RoomForm, icon="07", title="Salas de HaxBall (PUBS)",
        subtitle="Links publicos de las salas de la liga.",
        fields=["id", "code", "name", "region", "max_players", "is_open", "actions"],
        search=["code", "name", "description"],
        order=(Room.sort_order, Room.code),
    ),
    "museo": dict(
        model=MuseumItem, form=MuseumForm, icon="08", title="Museo de premios",
        subtitle="Premios, rankings, campeones y trofeos entregados.",
        fields=["id", "title", "category", "division_short", "recipient", "awarded_on", "actions"],
        search=["title", "recipient", "description"],
        order=(MuseumItem.sort_order, *nulls_last(MuseumItem.awarded_on)),
    ),
    "alianzas": dict(
        model=Alliance, form=AllianceForm, icon="09", title="Alianzas",
        subtitle="Partners, afiliados y proximas afiliaciones.",
        fields=["id", "name", "kind", "status", "starts_on", "is_featured", "actions"],
        search=["name", "tagline", "description"],
        order=(Alliance.sort_order, Alliance.name),
    ),
    "redes": dict(
        model=SocialLink, form=SocialForm, icon="10", title="Redes sociales",
        subtitle="Cuentas oficiales de la liga, streamers y equipo.",
        fields=["id", "label", "platform", "owner", "is_primary", "is_active", "actions"],
        search=["label", "handle", "platform"],
        order=(SocialLink.owner, SocialLink.sort_order),
    ),
    "equipo": dict(
        model=StaffMember, form=StaffForm, icon="11", title="Equipo de administracion",
        subtitle="Owner, master y staff de The Diamonds League.",
        fields=["id", "name", "role", "is_leader", "is_active", "sort_order", "actions"],
        search=["name", "username", "role"],
        order=(StaffMember.is_leader.desc(), StaffMember.sort_order),
    ),
    "live": dict(
        model=LiveStream, form=LiveStreamForm, icon="12", title="Live Futbol",
        subtitle="Transmisiones de futbol real estilo Kick / Twitch.",
        fields=["id", "title", "platform", "league", "is_live", "viewers", "actions"],
        search=["title", "league", "competition", "channel"],
        order=(LiveStream.is_live.desc(), LiveStream.sort_order),
    ),
    "donacion-canales": dict(
        model=DonationChannel, form=DonationChannelForm, icon="13", title="Metodos de donacion",
        subtitle="Alias, cuentas y links de apoyo a la liga.",
        fields=["id", "label", "method", "account", "is_active", "sort_order", "actions"],
        search=["label", "account"],
        order=(DonationChannel.sort_order,),
    ),
    "donaciones": dict(
        model=Donation, form=DonationForm, icon="14", title="Donaciones recibidas",
        subtitle="Registro de apoyos economicos de la comunidad.",
        fields=["id", "donor_name", "amount", "channel", "donated_at", "is_public", "actions"],
        search=["donor_name", "message"],
        order=(Donation.donated_at.desc(),),
    ),
    "divisiones": dict(
        model=Division, form=DivisionForm, icon="15", title="Divisiones y formato",
        subtitle="Configuracion de cada division de la temporada.",
        fields=["id", "name", "short", "teams_count", "journeys_count", "actions"],
        search=["name", "short"],
        order=(Division.level,),
    ),
    "reglas": dict(
        model=RuleEntry, form=RuleForm, icon="16", title="Reglamento",
        subtitle="Normas de Discord, comunidad y Conducta.",
        fields=["id", "title", "scope", "position", "actions"],
        search=["title", "body"],
        order=(RuleEntry.scope, RuleEntry.position),
    ),
    "sanciones": dict(
        model=SanctionLevel, form=SanctionLevelForm, icon="17", title="Escala de sanciones",
        subtitle="Niveles disciplinarios aplicados por el staff.",
        fields=["id", "name", "color", "note", "sort_order", "actions"],
        search=["name"],
        order=(SanctionLevel.sort_order,),
    ),
    "usuarios": dict(
        model=User, form=UserForm, icon="18", title="Usuarios",
        subtitle="Cuentas registradas, roles y accesos.",
        fields=["id", "username", "email", "role", "is_active_account", "actions"],
        search=["username", "email", "display_name"],
        order=(User.created_at.desc(),),
        admin_only=True,
    ),
}


# --------------------------------------------------------------------------- #
# Utilidades de listado
# --------------------------------------------------------------------------- #
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


def _page(query, endpoint: str, per_page: int = 20):
    page = request.args.get("page", 1, type=int)
    total = query.order_by(None).count()
    pages = max(1, (total + per_page - 1) // per_page)
    page = max(1, min(page, pages))
    return query.limit(per_page).offset((page - 1) * per_page).all(), {"page": page, "pages": pages, "total": total}


def _allowed(resource: str) -> bool:
    cfg = RESOURCES[resource]
    return not cfg.get("admin_only") or current_user.is_admin


# --------------------------------------------------------------------------- #
# Dashboard
# --------------------------------------------------------------------------- #
@bp.route("/")
def dashboard():
    today = date.today()
    now = utcnow()
    season = current_season()
    division = season.divisions[0] if season and season.divisions else Division.query.first()

    stats = {
        "usuarios": User.query.count(),
        "usuarios_7d": User.query.filter(User.created_at >= now - timedelta(days=7)).count(),
        "articulos": Article.query.filter(Article.is_published.is_(True)).count(),
        "avisos": Article.query.filter_by(kind=Category.ANNOUNCEMENT).count(),
        "noticias": Article.query.filter_by(kind=Category.NEWS).count(),
        "informes": Article.query.filter_by(kind=Category.REPORT).count(),
        "equipos": Team.query.count(),
        "equipos_sin_escudo": Team.query.filter(or_(Team.crest.is_(None), Team.crest == "")).count(),
        "jugadores": Player.query.count(),
        "partidos": Match.query.count(),
        "informes_partido": MatchReport.query.count(),
        "proximos": Match.query.filter(Match.played_on >= today).count(),
        "salas": Room.query.filter_by(is_open=True).count(),
        "museo": MuseumItem.query.count(),
        "alianzas": Alliance.query.count(),
        "redes": SocialLink.query.count(),
        "staff": StaffMember.query.count(),
        "live": LiveStream.query.filter_by(is_live=True).count(),
        "donaciones": Donation.query.count(),
        "donado": float(db.session.query(func.coalesce(func.sum(Donation.amount), 0)).scalar() or 0),
    }

    upcoming = (
        Match.query.filter(Match.played_on.isnot(None), Match.played_on >= today)
        .order_by(Match.played_on, Match.kickoff).limit(8).all()
    )
    recent_articles = Article.query.order_by(Article.created_at.desc()).limit(8).all()
    recent_users = User.query.order_by(User.created_at.desc()).limit(6).all()
    top_teams = (
        Standing.query.filter_by(division_id=division.id).order_by(Standing.points.desc()).limit(5).all()
        if division else []
    )
    logged_in_today = db.session.query(User).filter(func.date(User.last_login) == today).count()
    pending_reports = (
        Match.query.filter(Match.status == "finished")
        .outerjoin(MatchReport, MatchReport.match_id == Match.id)
        .filter(MatchReport.id.is_(None))
        .order_by(*nulls_last(Match.played_on))
        .limit(6)
        .all()
    )
    recent_emails = EmailLog.query.order_by(EmailLog.sent_at.desc()).limit(6).all()

    return render_template(
        "admin/dashboard.html",
        stats=stats,
        season=season,
        division=division,
        upcoming=upcoming,
        recent_articles=recent_articles,
        recent_users=recent_users,
        top_teams=top_teams,
        logged_in_today=logged_in_today,
        resources=RESOURCES,
        today=today,
        pending_reports=pending_reports,
        recent_emails=recent_emails,
    )


# --------------------------------------------------------------------------- #
# Listado
# --------------------------------------------------------------------------- #
@bp.route("/<resource>/")
def list_resource(resource: str):
    if resource not in RESOURCES or not _allowed(resource):
        abort(404)
    cfg = RESOURCES[resource]
    query, term = _query_for(resource)
    rows, meta = _page(query, f"admin.list_resource")
    return render_template(
        "admin/list.html", resource=resource, cfg=cfg, rows=rows, meta=meta, term=term,
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
    _populate_choices(form)

    if form.validate_on_submit():
        obj = cfg["model"]()
        _assign(form, obj, cfg, creating=True)
        db.session.add(obj)
        db.session.flush()
        log_activity(current_user, "crear", resource, obj.id, str(obj)[:120])
        db.session.commit()
        flash(f"Registro creado correctamente.", "success")
        return redirect(url_for("admin.list_resource", resource=resource))

    return render_template("admin/form.html", resource=resource, cfg=cfg, form=form, obj=None)


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
    _populate_choices(form)

    if form.validate_on_submit():
        _assign(form, obj, cfg, creating=False)
        log_activity(current_user, "editar", resource, obj.id, str(obj)[:120])
        db.session.commit()
        flash("Cambios guardados.", "success")
        return redirect(url_for("admin.list_resource", resource=resource))

    return render_template("admin/form.html", resource=resource, cfg=cfg, form=form, obj=obj)


# --------------------------------------------------------------------------- #
# Eliminar
# --------------------------------------------------------------------------- #
@bp.route("/<resource>/<int:pk>/eliminar", methods=["POST"])
def delete(resource: str, pk: int):
    if resource not in RESOURCES or not _allowed(resource):
        abort(404)
    cfg = RESOURCES[resource]
    obj = db.session.get(cfg["model"], pk) or abort(404)

    # No permitir borrar la propia cuenta admin.
    if cfg["model"] is User and obj.id == current_user.id:
        flash("No puedes eliminar tu propia cuenta.", "error")
        return redirect(url_for("admin.list_resource", resource=resource))

    label = getattr(obj, "title", None) or getattr(obj, "name", None) or getattr(obj, "label", None) \
        or getattr(obj, "username", None) or str(obj)
    for attr in ("cover", "avatar", "banner", "crest", "image", "thumbnail", "attachment"):
        delete_upload(getattr(obj, attr, None))

    if isinstance(obj, Team):
        extra = _cascade_team_counts(obj)
        _purge_team(obj)
    else:
        extra = 0
        db.session.delete(obj)

    log_activity(current_user, "eliminar", resource, pk, str(label)[:120])
    db.session.commit()
    suffix = f" junto con {extra} registro(s) dependiente(s)." if extra else ""
    flash(f"�{label}� fue eliminado{suffix}", "info")
    return redirect(url_for("admin.list_resource", resource=resource))


def _cascade_team_counts(team: Team) -> int:
    """Cuantos registros extra se van a borrar con el equipo."""
    match_ids = [
        row[0] for row in db.session.query(Match.id).filter(
            (Match.home_team_id == team.id) | (Match.away_team_id == team.id)
        ).all()
    ]
    count = len(match_ids) + len(team.players or [])
    count += Standing.query.filter_by(team_id=team.id).count()
    count += MuseumItem.query.filter_by(team_id=team.id).count()
    if match_ids:
        count += PlayerMatchStat.query.filter(PlayerMatchStat.match_id.in_(match_ids)).count()
        count += MatchReport.query.filter(MatchReport.match_id.in_(match_ids)).count()
    return count


@bp.route("/<resource>/<int:pk>/toggle", methods=["POST"])
def toggle(resource: str, pk: int):
    """Activa/desactiva un registro rapido desde la tabla."""
    if resource not in RESOURCES or not _allowed(resource):
        abort(404)
    cfg = RESOURCES[resource]
    obj = db.session.get(cfg["model"], pk) or abort(404)
    form = BooleanOnlyForm()
    if not form.validate_on_submit():
        abort(400)

    for attr in ("is_published", "is_active", "is_open", "is_active_account", "is_live", "is_public"):
        if hasattr(obj, attr):
            setattr(obj, attr, not getattr(obj, attr))
            break
    db.session.commit()
    flash("Estado actualizado.", "success")
    return redirect(request.referrer or url_for("admin.list_resource", resource=resource))


# --------------------------------------------------------------------------- #
# Equipos: escudo, plantilla y borrado en cascada
# --------------------------------------------------------------------------- #
@bp.route("/equipos/<int:pk>")
def team_detail(pk: int):
    """Ficha del equipo: escudo, plantilla, partidos y estadisticas."""
    team = db.session.get(Team, pk) or abort(404)

    crest_form = TeamCrestForm()
    player_form = RosterPlayerForm()
    player_form.team_id = team.id

    matches = (
        Match.query.filter((Match.home_team_id == team.id) | (Match.away_team_id == team.id))
        .order_by(*nulls_last(Match.played_on), Match.journey.desc())
        .limit(30)
        .all()
    )
    standing = Standing.query.filter_by(team_id=team.id).first()

    return render_template(
        "admin/team_detail.html",
        team=team,
        crest_form=crest_form,
        player_form=player_form,
        matches=matches,
        standing=standing,
        totals=team.totals,
    )


@bp.route("/equipos/<int:pk>/escudo", methods=["POST"])
def team_crest(pk: int):
    """Sube o quita el logo del equipo sin tocar el resto de datos."""
    team = db.session.get(Team, pk) or abort(404)
    form = TeamCrestForm()
    if not form.validate_on_submit():
        flash("No se pudo guardar el escudo. Revisa que sea una imagen.", "error")
        return redirect(url_for("admin.team_detail", pk=team.id))

    if form.remove_crest.data and not form.crest.data:
        delete_upload(team.crest)
        team.crest = None
        db.session.commit()
        flash("Escudo eliminado.", "info")
        return redirect(url_for("admin.team_detail", pk=team.id))

    saved = save_upload(form.crest.data, subfolder="escudos")
    if saved:
        delete_upload(team.crest)
        team.crest = saved
        db.session.commit()
        log_activity(current_user, "escudo", "equipos", team.id, f"escudo de {team.name}")
        flash("Escudo actualizado.", "success")
    return redirect(url_for("admin.team_detail", pk=team.id))


@bp.route("/equipos/<int:pk>/jugadores", methods=["POST"])
def team_add_player(pk: int):
    """Agrega un jugador a la plantilla del equipo desde su ficha."""
    team = db.session.get(Team, pk) or abort(404)
    form = RosterPlayerForm()
    if not form.validate_on_submit():
        flash("Revisa los datos del jugador.", "error")
        return redirect(url_for("admin.team_detail", pk=team.id))

    username = form.username.data.strip()
    existing = Player.query.filter(
        db.func.lower(Player.username) == username.lower(), Player.team_id == team.id
    ).first()
    if existing is not None:
        flash(f"�{username}� ya esta en la plantilla de {team.name}.", "error")
        return redirect(url_for("admin.team_detail", pk=team.id))

    player = Player(
        team_id=team.id,
        username=username,
        haxball_id=(form.haxball_id.data or "").strip() or None,
        position=form.position.data or "MF",
        number=form.number.data or 0,
        country=(form.country.data or "").strip() or None,
        is_captain=bool(form.is_captain.data),
        is_active=True,
    )
    db.session.add(player)
    log_activity(current_user, "anadir_jugador", "equipos", team.id, f"{username} -> {team.name}")
    db.session.commit()
    flash(f"�{username}� se sumo a la plantilla de {team.name}.", "success")
    return redirect(url_for("admin.team_detail", pk=team.id))


@bp.route("/equipos/<int:pk>/jugadores/<int:player_id>/quitar", methods=["POST"])
def team_remove_player(pk: int, player_id: int):
    """Saca a un jugador de la plantilla (borra sus datos si no tiene historial)."""
    team = db.session.get(Team, pk) or abort(404)
    player = db.session.get(Player, player_id) or abort(404)
    if player.team_id != team.id:
        abort(404)

    form = BooleanOnlyForm()
    if not form.validate_on_submit():
        abort(400)

    name = player.username
    has_history = PlayerMatchStat.query.filter_by(player_id=player.id).count()
    if has_history:
        # Hay partidos registrados: se marca inactivo para no romper los informes.
        player.team_id = team.id
        player.is_active = False
        db.session.commit()
        flash(
            f"�{name}� salio de la plantilla activa; su historial de {has_history} partidos se conserva.",
            "info",
        )
    else:
        _purge_player(player)
        db.session.commit()
        flash(f"�{name}� fue eliminado de la plantilla.", "info")
    return redirect(url_for("admin.team_detail", pk=team.id))


def _purge_player(player: Player) -> None:
    """Borra al jugador y todo lo que cuelga de el."""
    MatchReport.query.filter_by(mvp_player_id=player.id).update({"mvp_player_id": None})
    db.session.delete(player)


def _bulk_delete(model, *criteria) -> int:
    """Borrado masivo solo si queda algo: evita el SAWarning de filas ya borradas."""
    ids = [row[0] for row in db.session.query(model.id).filter(*criteria).all()]
    if not ids:
        return 0
    return model.query.filter(model.id.in_(ids)).delete(synchronize_session=False)


def _purge_team(team: Team) -> None:
    """Borrado en cascada explicito de un equipo.

    SQLite no aplica los ON DELETE CASCADE del esquema, y en MySQL dependen del
    motor; por seguridad se borra explicitamente y en el orden correcto.
    """
    match_ids = [
        row[0] for row in db.session.query(Match.id).filter(
            (Match.home_team_id == team.id) | (Match.away_team_id == team.id)
        ).all()
    ]
    if match_ids:
        _bulk_delete(PlayerMatchStat, PlayerMatchStat.match_id.in_(match_ids))
        _bulk_delete(MatchReport, MatchReport.match_id.in_(match_ids))
        _bulk_delete(Match, Match.id.in_(match_ids))

    # `Team.players`, `Player.match_stats` y `Team.match_stats` llevan
    # cascade="all, delete-orphan": el borrado del equipo arrastra jugadores y
    # sus estadisticas. Aqui solo hay que soltar las referencias que no borran.
    player_ids = [p.id for p in team.players]
    if player_ids:
        MatchReport.query.filter(MatchReport.mvp_player_id.in_(player_ids)).update({"mvp_player_id": None})

    _bulk_delete(Standing, Standing.team_id == team.id)
    MuseumItem.query.filter(MuseumItem.team_id == team.id).update({"team_id": None}, synchronize_session=False)
    delete_upload(team.crest)
    # Esas colecciones se cargaron con `selectin` y siguen apuntando a objetos
    # que el DELETE masivo ya borro. Sin refrescarlas, la cascada delete-orphan
    # los vuelve a marcar y el ORM emite un segundo DELETE que ya no hace falta.
    db.session.expire(team, ["match_stats", "players"])
    for player in team.players:
        db.session.expire(player, ["match_stats"])
    db.session.delete(team)



# --------------------------------------------------------------------------- #
# Acciones especiales
# --------------------------------------------------------------------------- #
@bp.route("/articulos/<int:pk>/duplicar", methods=["POST"])
def duplicate_article(pk: int):
    form = BooleanOnlyForm()
    if not form.validate_on_submit() or not current_user.is_admin:
        abort(403)
    src = db.session.get(Article, pk) or abort(404)
    clone = Article(
        kind=src.kind, category=src.category, title=f"{src.title} (copia)",
        summary=src.summary, body=src.body, cover=src.cover, is_published=False,
        author_id=current_user.id, division_id=src.division_id,
    )
    clone.slug = f"{slugify(clone.title)}-{secrets.token_hex(3)}"
    db.session.add(clone)
    db.session.commit()
    flash("Articulo duplicado como borrador.", "success")
    return redirect(url_for("admin.edit", resource="noticias", pk=clone.id))


@bp.route("/usuarios/<int:pk>/toggle-admin", methods=["POST"])
def promote(pk: int):
    form = BooleanOnlyForm()
    if not form.validate_on_submit():
        abort(400)
    user = db.session.get(User, pk) or abort(404)
    if user.id == current_user.id:
        flash("No puedes quitarte a ti mismo el acceso de administrador.", "error")
        return redirect(request.referrer or url_for("admin.list_resource", resource="usuarios"))

    admins = User.query.filter_by(is_admin=True).count()
    if user.is_admin and admins <= 1:
        flash("Debe quedar al menos un administrador activo.", "error")
        return redirect(request.referrer or url_for("admin.list_resource", resource="usuarios"))

    user.is_admin = not user.is_admin
    user.role = Role.ADMIN if user.is_admin else (Role.STAFF if user.role == Role.ADMIN else user.role)
    db.session.commit()
    flash(f"{user.label} ahora {'es' if user.is_admin else 'ya no es'} administrador.", "success")
    return redirect(request.referrer or url_for("admin.list_resource", resource="usuarios"))


@bp.route("/partidos/recalcular", methods=["POST"])
def recalculate_standings():
    """Recalcula puntos y posiciones desde los resultados cargados."""
    form = BooleanOnlyForm()
    if not form.validate_on_submit() or not current_user.is_admin:
        abort(403)

    touched = 0
    for division in Division.query.all():
        rows = {s.team_id: s for s in Standing.query.filter_by(division_id=division.id).all()}
        team_ids = {t.id for t in Team.query.filter_by(division_id=division.id).all()}
        for team_id in team_ids:
            if team_id not in rows:
                rows[team_id] = Standing(division_id=division.id, team_id=team_id)
                db.session.add(rows[team_id])

        for row in rows.values():
            row.won = row.drawn = row.lost = row.goals_for = row.goals_against = 0

        for match in Match.query.filter_by(division_id=division.id).all():
            if match.status != "finished" or match.home_score is None or match.away_score is None:
                continue
            home, away = rows.get(match.home_team_id), rows.get(match.away_team_id)
            if not home or not away:
                continue
            touched += 1
            home.goals_for += match.home_score
            home.goals_against += match.away_score
            away.goals_for += match.away_score
            away.goals_against += match.home_score
            if match.home_score > match.away_score:
                home.won += 1
                away.lost += 1
            elif match.home_score < match.away_score:
                away.won += 1
                home.lost += 1
            else:
                home.drawn += 1
                away.drawn += 1

        for row in rows.values():
            row.recompute()

        ordered = sorted(rows.values(), key=lambda r: (-r.points, -(r.goals_for - r.goals_against), r.team.name or ""))
        for index, row in enumerate(ordered, start=1):
            row.position = index

    db.session.commit()
    flash(f"Tablas recalculadas con {touched} partidos finalizados.", "success")
    return redirect(request.referrer or url_for("admin.dashboard"))


@bp.route("/estadisticas/recalcular", methods=["POST"])
def recalculate_player_stats():
    """Rehace los acumulados de cada jugador desde los partidos informados."""
    form = BooleanOnlyForm()
    if not form.validate_on_submit() or not current_user.is_admin:
        abort(403)

    updated = recompute_player_stats()
    flash(f"Estadisticas de {updated} jugadores recalculadas desde los informes.", "success")
    return redirect(request.referrer or url_for("admin.dashboard"))


# --------------------------------------------------------------------------- #
# Informe de partido: foto, resultado y estadisticas individuales
# --------------------------------------------------------------------------- #
def _roster_for_match(match: Match, used: set[int]) -> list[Player]:
    """Jugadores de los dos equipos que aun no tienen fila en el informe."""
    roster = (match.home_team.players or []) + (match.away_team.players or []) \
        if match.home_team and match.away_team else []
    return [p for p in roster if p.id not in used]


def _populate_stat_choices(form: PlayerStatForm, match: Match) -> None:
    form.player_id.choices = [("", "� elige un jugador �")] + [
        (str(p.id), f"{p.username} � {p.position or 'MF'} � {p.team.name if p.team else 'sin equipo'}")
        for p in _roster_for_match(match, set())
    ]


@bp.route("/partidos/<int:pk>/informe", methods=["GET", "POST"])
def match_report(pk: int):
    """Editor del informe: foto, titular, cronica y MVP."""
    match = db.session.get(Match, pk) or abort(404)
    is_new = match.report is None
    report = match.report or MatchReport(match_id=match.id)

    form = MatchReportForm(obj=report)

    # Las opciones del MVP deben existir ANTES de validar: un SelectField sin
    # `choices` lanza TypeError en cuanto se envia el formulario por POST.
    used = {stat.player_id for stat in match.player_stats}
    available = _roster_for_match(match, used)
    _populate_choices(form)
    # El MVP actual puede no estar entre los disponibles: se mantiene como opci�n.
    mvp_choices = [("", "� sin MVP �")] + [
        (str(p.id), f"{p.username} � {p.team.short if p.team else ''}") for p in available
    ]
    if report.mvp_player_id and str(report.mvp_player_id) not in {c[0] for c in mvp_choices}:
        current = db.session.get(Player, report.mvp_player_id)
        if current is not None:
            mvp_choices.append((str(current.id), f"{current.username} � (MVP guardado)"))
    form.mvp_player_id.choices = mvp_choices

    if form.validate_on_submit():
        _save_report(form, report, match, creating=is_new)
        flash("Informe guardado.", "success")
        return redirect(url_for("admin.match_report", pk=match.id))

    stat_form = PlayerStatForm()
    stat_form.player_id.choices = [("", "� elige un jugador �")] + [
        (str(p.id), f"{p.username} � {p.position or 'MF'} � {p.team.name if p.team else 'sin equipo'}")
        for p in available
    ]

    return render_template(
        "admin/match_report.html",
        match=match,
        report=report,
        form=form,
        stat_form=stat_form,
        home_stats=match.stats_for(match.home_team_id),
        away_stats=match.stats_for(match.away_team_id),
        scorers=match.scorers,
        computed=(match.home_goals_from_stats, match.away_goals_from_stats),
    )


def _save_report(form: MatchReportForm, report: MatchReport, match: Match, creating: bool) -> None:
    # Solo columnas reales del modelo: `csrf_token` y `submit` no existen en la tabla.
    skip = {"photo", "remove_photo", "csrf_token", "submit"}
    columns = {c.name for c in MatchReport.__table__.columns}
    payload = {
        name: field.data for name, field in form._fields.items()
        if name not in skip and name in columns
    }
    for name, value in payload.items():
        if isinstance(value, str):
            value = value.strip() or None
        setattr(report, name, value)

    if form.photo.data:
        saved = save_upload(form.photo.data, subfolder="partidos")
        if saved:
            delete_upload(report.photo)
            report.photo = saved
    if form.remove_photo.data and not form.photo.data:
        delete_upload(report.photo)
        report.photo = None

    if not report.author_id:
        report.author_id = current_user.id

    if creating:
        db.session.add(report)
    log_activity(current_user, "informe", "partidos", match.id, match.headline)
    db.session.commit()


@bp.route("/partidos/<int:pk>/informe/estadistica", methods=["POST"])
def match_stat_add(pk: int):
    """Agrega una fila a la tabla de estadisticas del partido."""
    match = db.session.get(Match, pk) or abort(404)
    form = PlayerStatForm()
    # `choices` debe existir antes de validar o el SelectField lanza TypeError.
    _populate_stat_choices(form, match)
    if not form.validate_on_submit():
        flash("Revisa la fila de estadisticas.", "error")
        return redirect(url_for("admin.match_report", pk=match.id))

    player = db.session.get(Player, form.player_id.data) or abort(404)
    if player.team_id not in (match.home_team_id, match.away_team_id):
        flash("Ese jugador no disputa este partido.", "error")
        return redirect(url_for("admin.match_report", pk=match.id))

    if PlayerMatchStat.query.filter_by(match_id=match.id, player_id=player.id).first():
        flash(f"�{player.username}� ya tiene una fila en este informe.", "error")
        return redirect(url_for("admin.match_report", pk=match.id))

    stat = PlayerMatchStat(
        match_id=match.id,
        player_id=player.id,
        team_id=player.team_id,
        goals=form.goals.data or 0,
        assists=form.assists.data or 0,
        clean_sheets=form.clean_sheets.data or 0,
        clean_sheet_seconds=form.clean_sheet_seconds.data or 0,
        own_goals=form.own_goals.data or 0,
        yellow_cards=form.yellow_cards.data or 0,
        red_cards=form.red_cards.data or 0,
        minutes=form.minutes.data or 0,
        is_mvp=bool(form.is_mvp.data),
        note=(form.note.data or "").strip() or None,
    )
    db.session.add(stat)
    db.session.flush()

    # El MVP del informe sigue al jugador marcado como MVP en la tabla.
    report = match.report or MatchReport(match_id=match.id)
    report.mvp_player_id = player.id if stat.is_mvp else report.mvp_player_id
    if db.session.is_modified(report):
        db.session.add(report)

    log_activity(current_user, "estadistica", "partidos", match.id, player.username)
    db.session.commit()
    flash(f"Estadisticas de �{player.username}� anadidas.", "success")
    return redirect(url_for("admin.match_report", pk=match.id))


@bp.route("/partidos/<int:pk>/informe/estadistica/<int:stat_id>/quitar", methods=["POST"])
def match_stat_remove(pk: int, stat_id: int):
    match = db.session.get(Match, pk) or abort(404)
    stat = db.session.get(PlayerMatchStat, stat_id) or abort(404)
    if stat.match_id != match.id:
        abort(404)

    form = BooleanOnlyForm()
    if not form.validate_on_submit():
        abort(400)

    name = stat.player.username if stat.player else "jugador"
    if match.report and match.report.mvp_player_id == stat.player_id:
        match.report.mvp_player_id = None
    db.session.delete(stat)
    db.session.commit()
    flash(f"Fila de �{name}� eliminada del informe.", "info")
    return redirect(url_for("admin.match_report", pk=match.id))


@bp.route("/partidos/<int:pk>/informe/resultado", methods=["POST"])
def match_sync_score(pk: int):
    """Calcula el marcador del partido a partir de las estadisticas cargadas."""
    match = db.session.get(Match, pk) or abort(404)
    form = BooleanOnlyForm()
    if not form.validate_on_submit():
        abort(400)

    if not match.player_stats:
        flash("Anade al menos una fila de estadisticas antes de calcular el resultado.", "error")
        return redirect(url_for("admin.match_report", pk=match.id))

    match.home_score = match.home_goals_from_stats
    match.away_score = match.away_goals_from_stats
    if match.status in ("scheduled", "live"):
        match.status = "finished"
    db.session.commit()
    flash(f"Resultado actualizado a {match.score_text}.", "success")
    return redirect(url_for("admin.match_report", pk=match.id))


@bp.route("/correos")
def email_log():
    """Historial de correos enviados por la aplicacion."""
    query = EmailLog.query.order_by(EmailLog.sent_at.desc(), EmailLog.id.desc())
    term = (request.args.get("q") or "").strip()
    if term:
        query = query.filter(
            db.or_(EmailLog.to_email.ilike(f"%{term}%"), EmailLog.subject.ilike(f"%{term}%"))
        )
    rows = query.limit(120).all()
    return render_template(
        "admin/email_log.html", rows=rows, term=term,
        failed=EmailLog.query.filter_by(status="failed").count(),
        sent=EmailLog.query.filter_by(status="sent").count(),
    )


@bp.route("/correos/<int:pk>/reenviar", methods=["POST"])
def email_log_resend(pk: int):
    """Reenvia un correo que fallo (p. ej. tras arreglar el SMTP)."""
    from mailer import send_email

    record = db.session.get(EmailLog, pk) or abort(404)
    form = BooleanOnlyForm()
    if not form.validate_on_submit():
        abort(400)
    if record.status == "sent":
        flash("Ese correo ya se habia enviado.", "info")
        return redirect(url_for("admin.email_log"))

    ok = send_email(record.to_email, record.subject, _fallback_body(record), user=record.user,
                    template=record.template)
    if ok:
        record.status = "sent"
        record.error = None
        db.session.commit()
        flash("Correo reenviado.", "success")
    else:
        flash("El correo vuelve a fallar. Revisa MAIL_USERNAME y MAIL_PASSWORD.", "error")
    return redirect(url_for("admin.email_log"))


def _fallback_body(record: EmailLog) -> str:
    return (
        f'<div style="font-family:Inter,sans-serif;color:#c3c9d6;background:#101218;'
        f'padding:24px;border-radius:12px">'
        f'<p style="margin:0 0 10px;color:#1bebf2;font:700 12px/1 IBM Plex Mono,monospace;'
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
        ("league_season", "Temporada actual", "text"),
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


@bp.route("/sugerencias")
def suggestions():
    """Todo lo que opinaron los jugadores, para responderlo desde el panel."""
    query = Suggestion.query.order_by(Suggestion.created_at.desc(), Suggestion.id.desc())
    estado = (request.args.get("estado") or "").strip()
    if estado in SuggestionStatus.ALL:
        query = query.filter(Suggestion.status == estado)
    rows = query.limit(200).all()
    return render_template(
        "admin/suggestions.html",
        rows=rows,
        estado=estado,
        total=Suggestion.query.count(),
        nuevas=Suggestion.query.filter_by(status=SuggestionStatus.NEW).count(),
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
    log_activity(current_user, "elimina", "sugerencia", suggestion.id, suggestion.title)
    db.session.delete(suggestion)
    db.session.commit()
    flash("Sugerencia eliminada.", "info")
    return redirect(request.referrer or url_for("admin.suggestions"))


@bp.route("/ajustes", methods=["GET"])
def settings():
    if not current_user.is_admin:
        abort(403)
    rows = SiteSetting.query.order_by(SiteSetting.group, SiteSetting.key).all()
    by_group: dict[str, list] = {}
    for row in rows:
        by_group.setdefault(row.group or "general", []).append(row)
    return render_template("admin/settings.html", groups=SETTINGS_GROUPS, values=by_group)


@bp.route("/ajustes", methods=["POST"])
def settings_save():
    if not current_user.is_admin:
        abort(403)
    payload = request.form.get("values") or "{}"
    try:
        import json
        data = json.loads(payload)
    except ValueError:
        data = {}

    for group, (_, fields) in SETTINGS_GROUPS.items():
        for key, _label, _kind in fields:
            if key not in data:
                continue
            value = "1" if data[key] is True else ("" if data[key] is None else str(data[key]))
            set_setting(key, value, group=group, label=dict((k, l) for k, l, _ in fields).get(key, key))
    db.session.commit()
    flash("Ajustes guardados.", "success")
    return redirect(url_for("admin.settings"))


# --------------------------------------------------------------------------- #
# Form helpers
# --------------------------------------------------------------------------- #
def _populate_choices(form) -> None:
    """Inyecta opciones dinamicas en los SelectField."""
    for field_name in getattr(form, "_fields", {}):
        field = form._fields[field_name]
        if not isinstance(field, SelectField) or field.choices:
            continue
        if field_name == "division_id":
            field.choices = [("", "� sin division �")] + [
                (str(d.id), f"{d.short} � {d.name}") for d in Division.query.order_by(Division.level).all()
            ]
        elif field_name in ("team_id", "home_team_id", "away_team_id"):
            field.choices = [
                (str(t.id), f"{t.name} ({t.division.short if t.division else 'sin division'})")
                for t in Team.query.order_by(Team.sort_order, Team.name).all()
            ]
        elif field_name == "kind":
            field.choices = [("news", "Noticia"), ("announcement", "Anuncio"), ("report", "Informe")]


def _assign(form, obj, cfg: dict, creating: bool) -> None:
    resource = None
    for name, conf in RESOURCES.items():
        if conf is cfg:
            resource = name
            break

    for name, field in form._fields.items():
        if isinstance(field, FileField):
            continue
        data = field.data
        if isinstance(data, str):
            data = data.strip() or None
            if name in ("title", "name", "label", "username") and data is None:
                continue
        setattr(obj, name, data)

    # Slug automatico
    if hasattr(obj, "slug") and not getattr(obj, "slug", None):
        obj.slug = slugify(getattr(obj, "title", None) or getattr(obj, "name", "registro"))

    # Uploads
    for name, field in form._fields.items():
        if not isinstance(field, FileField):
            continue
        subfolder = resource or "misc"
        if field.data:
            saved = save_upload(field.data, subfolder=subfolder)
            if saved:
                old = getattr(obj, name, None)
                setattr(obj, name, saved)
                if not creating:
                    delete_upload(old)
        if getattr(form, f"remove_{name}", None) and getattr(form, f"remove_{name}").data:
            delete_upload(getattr(obj, name, None))
            setattr(obj, name, None)

    # Filtros por tipo de recurso
    if cfg.get("filters"):
        for key, value in cfg["filters"].items():
            setattr(obj, key, value)

    # Password de usuarios (solo al crear o si se escribe una nueva)
    if isinstance(obj, User):
        raw = form.password.data
        if raw:
            obj.set_password(raw)
        if obj.role == "admin":
            obj.is_admin = True
        elif not creating and obj.is_admin and not current_user.is_admin:
            obj.is_admin = False

    # Article: defaults y slug unico
    if isinstance(obj, Article):
        obj.title = (obj.title or "").strip()
        if creating or not obj.slug:
            obj.slug = _unique_slug(Article, obj.title or "articulo", obj.id)
        if not obj.published_at:
            obj.published_at = utcnow()
        if obj.author_id is None:
            obj.author_id = current_user.id

    if isinstance(obj, Donation) and not obj.donated_at:
        obj.donated_at = utcnow()

    if isinstance(obj, Standing):
        obj.recompute()


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
    return {"resources": RESOURCES, "now": datetime.now, "Role": Role}


