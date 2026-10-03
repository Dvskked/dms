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
from sqlalchemy import func
from wtforms.fields import FileField, SelectField

from extensions import db
from forms import (
    AllianceForm, ArticleForm, BooleanOnlyForm, DonationChannelForm, DonationForm, DivisionForm,
    FlaskForm, LiveStreamForm, MatchForm, MuseumForm, PlayerForm, RoomForm, RuleForm, SanctionLevelForm,
    SocialForm, StaffForm, TeamForm, UserForm,
)
from models import (
    Alliance, Article, Category, Division, Donation, DonationChannel, LiveStream, Match,
    MuseumItem, Player, Role, Room, RuleEntry, SanctionLevel, SiteSetting, SocialLink, StaffMember,
    Standing, Team, User, current_season, log_activity, set_setting,
)
from utils import delete_upload, save_upload, slugify, utcnow

bp = Blueprint("admin", __name__, url_prefix="/admin")


# --------------------------------------------------------------------------- #
# Guards
# --------------------------------------------------------------------------- #
@bp.before_request
@login_required
def _guard():
    if not current_user.is_staff:
        abort(403)
    if request.endpoint in {"admin.promote", "admin.recalculate_standings", "admin.settings",
                            "admin.settings_save", "admin.duplicate_article"} and not current_user.is_admin:
        abort(403)


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
        subtitle="Plantillas, escudos ydivision de cada club.",
        fields=["id", "name", "division", "coach", "player_count", "is_active", "actions"],
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
        order=(Match.journey, Match.played_on.asc().nullslast(), Match.kickoff),
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
        order=(MuseumItem.sort_order, MuseumItem.awarded_on.desc().nullslast()),
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
        "jugadores": Player.query.count(),
        "partidos": Match.query.count(),
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

    db.session.delete(obj)
    log_activity(current_user, "eliminar", resource, pk, str(label)[:120])
    db.session.commit()
    flash(f"«{label}» fue eliminado.", "info")
    return redirect(url_for("admin.list_resource", resource=resource))


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
            field.choices = [("", "— sin division —")] + [
                (str(d.id), f"{d.short} · {d.name}") for d in Division.query.order_by(Division.level).all()
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


