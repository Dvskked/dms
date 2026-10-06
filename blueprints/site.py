"""Blueprint publico: la pagina de la liga con todas sus secciones."""
from __future__ import annotations

from collections import defaultdict
from datetime import date

from flask import Blueprint, abort, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from extensions import db
from forms import SuggestionForm
from mailer import notify_staff_new_suggestion
from models import (
    Article,
    Category,
    Division,
    Donation,
    Link,
    LinkKind,
    LiveStream,
    Match,
    MatchReport,
    MuseumItem,
    Player,
    Regulation,
    Role,
    Room,
    SUGGESTION_CATEGORIES,
    Suggestion,
    SuggestionStatus,
    Team,
    User,
    division_standings,
    donation_goal,
    log_activity,
    player_stat_rows,
    stat_leaders,
)
from utils import nulls_last, rich_text

bp = Blueprint("site", __name__)


# --------------------------------------------------------------------------- #
# Consultas reutilizables
# --------------------------------------------------------------------------- #
def published(kind: str, limit: int | None = None):
    """Articulos publicados de un tipo, con los fijados arriba."""
    q = (
        Article.query.filter_by(kind=kind, is_published=True)
        .order_by(Article.is_pinned.desc(), *nulls_last(Article.published_at, descending=False))
    )
    return q.limit(limit) if limit else q.all()


def active_divisions() -> list[Division]:
    return Division.query.order_by(Division.level, Division.name).all()


def staff_members() -> list[User]:
    """El equipo de administracion vive en ``users`` (columnas publicas)."""
    return (
        User.query.filter(
            User.is_public.is_(True),
            User.is_active_account.is_(True),
            User.role.in_(Role.TEAM),
        )
        .order_by(User.is_leader.desc(), User.sort_order, User.display_name)
        .all()
    )


def links_of(kind: str, active_only: bool = True):
    """Alianzas, redes o metodos de donacion (todos en ``links``)."""
    q = Link.query.filter_by(kind=kind)
    if active_only:
        q = q.filter_by(is_active=True)
    return q.order_by(Link.sort_order, Link.label).all()


def group_by(rows, attr: str) -> dict:
    """Agrupa filas por el valor de un atributo (para los bloques de la home)."""
    out: dict = defaultdict(list)
    for row in rows:
        out[getattr(row, attr) or "liga"].append(row)
    return dict(out)


def division_bundle(division: Division) -> dict:
    """Todo el contenido que necesita una division en las pestanas de LIGA."""
    matches = (
        Match.query.filter_by(division_id=division.id)
        .order_by(Match.journey, *nulls_last(Match.played_on, descending=False), Match.kickoff)
        .all()
    )
    grouped: dict[int, list] = defaultdict(list)
    for match in matches:
        grouped[match.journey].append(match)

    calendar = []
    for journey in sorted(grouped):
        items = grouped[journey]
        dates = [m.played_on for m in items if m.played_on]
        if dates:
            lo, hi = min(dates), max(dates)
            rango = f"{lo:%d/%m} · {hi:%d/%m}" if lo != hi else f"{lo:%d/%m/%Y}"
        else:
            rango = "Fecha por definir"
        calendar.append({"journey": journey, "matches": items, "range": rango})

    rows = division_standings(division.id)
    teams = (
        Team.query.filter_by(division_id=division.id, is_active=True)
        .order_by(Team.sort_order, Team.name)
        .all()
    )
    stats = player_stat_rows(division_id=division.id)

    return {
        "division": division,
        "teams": teams,
        "calendar": calendar,
        "standings": rows,
        "phases": division.phases,
        "base_rules": division.base_rules,
        "moves": division.moves,
        "scorers": stat_leaders(division.id, "goals"),
        "assistants": stat_leaders(division.id, "assists"),
        "keepers": stat_leaders(division.id, "clean_sheets"),
        "own_goalers": stat_leaders(division.id, "own_goals", order="asc", limit=8),
        "players": stats,
        "total_matches": len(matches),
        "goals_total": sum(s.goals or 0 for s in stats),
        "assists_total": sum(s.assists or 0 for s in stats),
    }


# --------------------------------------------------------------------------- #
# Pagina principal (unica, con anclas por seccion del header)
# --------------------------------------------------------------------------- #
@bp.route("/")
def index():
    divisions = active_divisions()
    divisions_data = [division_bundle(d) for d in divisions]

    rooms = Room.query.filter_by(is_open=True).order_by(Room.sort_order, Room.code).all()
    museum = (
        MuseumItem.query.order_by(MuseumItem.sort_order, *nulls_last(MuseumItem.awarded_on),
                                  MuseumItem.id.desc())
        .all()
    )
    news = published(Category.NEWS)
    announcements = published(Category.ANNOUNCEMENT)
    reports = published(Category.REPORT)

    alliances = links_of(LinkKind.ALLIANCE, active_only=False)
    featured_alliance = next((a for a in alliances if a.is_featured), None)

    socials = links_of(LinkKind.SOCIAL)
    socials_by_owner = group_by(socials, "group")

    staff = staff_members()

    live_streams = (
        LiveStream.query.order_by(LiveStream.is_live.desc(), LiveStream.is_featured.desc(),
                                  LiveStream.sort_order)
        .all()
    )
    featured_live = (
        next((s for s in live_streams if s.is_live and s.is_featured), None)
        or next((s for s in live_streams if s.is_live), None)
    )

    donation_channels = links_of(LinkKind.DONATION)
    goal = donation_goal()
    donations = (
        Donation.query.filter_by(is_public=True).order_by(Donation.donated_at.desc()).limit(8).all()
    )

    rules = (
        Regulation.query.filter(Regulation.scope.in_(("discord", "comunidad")))
        .order_by(Regulation.scope, Regulation.position)
        .all()
    )
    sanctions = (
        Regulation.query.filter_by(scope="sanciones").order_by(Regulation.position).all()
    )

    today = date.today()
    next_match = (
        Match.query.filter(
            Match.played_on.isnot(None),
            Match.played_on >= today,
            Match.status.in_((Match.SCHEDULED, Match.LIVE)),
        )
        .order_by(Match.played_on, Match.kickoff)
        .first()
    )
    stats = {
        "teams": Team.query.filter_by(is_active=True).count(),
        "rooms": len(rooms),
        "museum": len(museum),
        "matches": Match.query.count(),
        "players": Player.query.filter_by(is_active=True).count(),
        "members": len(staff),
        "next_match": next_match,
    }

    return render_template(
        "site/index.html",
        divisions=divisions,
        division=divisions[0] if divisions else None,
        divisions_data=divisions_data,
        teams=divisions_data[0]["teams"] if divisions_data else [],
        rooms=rooms,
        museum=museum,
        museum_categories=MuseumItem.CATEGORIES,
        museum_labels=MuseumItem.CATEGORY_LABELS,
        news=news,
        announcements=announcements,
        reports=reports,
        alliances=alliances,
        featured_alliance=featured_alliance,
        socials=socials,
        socials_by_owner=socials_by_owner,
        staff=staff,
        live_streams=live_streams,
        featured_live=featured_live,
        donation_channels=donation_channels,
        donation_goal=goal,
        donations=donations,
        rules=rules,
        sanctions=sanctions,
        stats=stats,
        awards=[m for m in museum if m.category == "premios"],
        champions=[m for m in museum if m.category == "campeones"],
        rankings=[m for m in museum if m.category == "rankings"],
        today=today,
        site_stats={
            "rooms_open": len(rooms),
            "museum_total": len(museum),
            "socials_total": len(socials),
            "live_total": len(live_streams),
        },
    )


# --------------------------------------------------------------------------- #
# Detalle de articulo
# --------------------------------------------------------------------------- #
@bp.route("/noticias/<slug>")
def article_detail(slug: str):
    item = Article.query.filter_by(slug=slug).first_or_404()
    if not item.is_live_now and not current_user.is_staff:
        abort(404)
    item.views = (item.views or 0) + 1
    db.session.commit()
    related = (
        Article.query.filter(Article.kind == item.kind, Article.id != item.id,
                             Article.is_published.is_(True))
        .order_by(*nulls_last(Article.published_at, descending=False)).limit(3).all()
    )
    return render_template("site/article.html", item=item,
                           body=rich_text(item.body or ""), related=related)


# --------------------------------------------------------------------------- #
# Live de futbol: /live/<id> (pagina dedicada tipo Kick / Twitch)
# --------------------------------------------------------------------------- #
@bp.route("/live/<int:stream_id>")
def live_room(stream_id: int):
    stream = db.session.get(LiveStream, stream_id) or abort(404)
    others = (
        LiveStream.query.filter(LiveStream.id != stream.id)
        .order_by(LiveStream.is_live.desc(), LiveStream.sort_order).limit(6).all()
    )
    upcoming = (
        Match.query.filter(Match.played_on >= date.today())
        .order_by(*nulls_last(Match.played_on, descending=False), Match.kickoff)
        .limit(6).all()
    )
    return render_template("site/live_room.html", stream=stream, others=others, upcoming=upcoming)


# --------------------------------------------------------------------------- #
# Informe publico de un partido
# --------------------------------------------------------------------------- #
@bp.route("/partidos/<int:pk>")
def match_report(pk: int):
    """Foto del partido, resultado, goleadores y tabla de estadisticas."""
    match = db.session.get(Match, pk) or abort(404)
    report = match.report

    if report is not None and not report.is_published and not current_user.is_staff:
        abort(404)

    journey_matches = (
        Match.query.filter_by(division_id=match.division_id, journey=match.journey)
        .order_by(Match.kickoff).all()
    )

    return render_template(
        "site/match_report.html",
        match=match,
        report=report,
        home_stats=match.stats_for(match.home_team_id),
        away_stats=match.stats_for(match.away_team_id),
        scorers=match.scorers,
        others=[m for m in journey_matches if m.id != match.id],
        computed=(match.home_goals_from_stats, match.away_goals_from_stats),
    )


# --------------------------------------------------------------------------- #
# Estadisticas generales: tabla de las divisiones + tabla de jugadores
# --------------------------------------------------------------------------- #
@bp.route("/estadisticas")
def stats():
    """Tabla de las divisiones y tabla de estadisticas individuales."""
    divisions = active_divisions()
    tables = [
        {
            "division": division,
            "standings": division_standings(division.id),
            "teams": (
                Team.query.filter_by(division_id=division.id, is_active=True)
                .order_by(Team.sort_order, Team.name).all()
            ),
            "players": player_stat_rows(division_id=division.id),
            "calendar": (
                Match.query.filter_by(division_id=division.id)
                .order_by(Match.journey.desc()).limit(6).all()
            ),
        }
        for division in divisions
    ]
    return render_template(
        "site/stats.html",
        divisions=divisions,
        tables=tables,
        scorers=player_stat_rows(limit=15),
        recent_reports=(
            Match.query.join(MatchReport, MatchReport.match_id == Match.id)
            .filter(MatchReport.is_published.is_(True))
            .order_by(*nulls_last(Match.played_on, descending=False))
            .limit(6)
            .all()
        ),
    )


# --------------------------------------------------------------------------- #
# Sugerencias: canal de la comunidad con votos en una sola columna
# --------------------------------------------------------------------------- #
@bp.route("/sugerencias", methods=["GET", "POST"])
@login_required
def suggestions():
    """Canal de sugerencias: los jugadores dejan su opinion y se guarda en la base."""
    form = SuggestionForm()
    if form.validate_on_submit():
        suggestion = Suggestion(
            user_id=current_user.id,
            category=form.category.data,
            title=form.title.data.strip(),
            body=form.body.data.strip(),
            status=SuggestionStatus.NEW,
        )
        db.session.add(suggestion)
        db.session.flush()
        log_activity(current_user, "crear", "sugerencia", suggestion.id,
                     f"{suggestion.category_label}: {suggestion.title}")
        db.session.commit()

        notify_staff_new_suggestion(suggestion, current_user)
        flash("Gracias por opinar. Tu sugerencia ya esta en el canal del staff.", "success")
        return redirect(url_for("site.suggestions"))

    categoria = request.args.get("categoria", "").strip()
    estado = request.args.get("estado", "").strip()
    consulta = Suggestion.query
    if categoria in SUGGESTION_CATEGORIES:
        consulta = consulta.filter(Suggestion.category == categoria)
    if estado in SuggestionStatus.ALL:
        consulta = consulta.filter(Suggestion.status == estado)

    filas = (
        consulta.order_by(Suggestion.created_at.desc())
        .paginate(page=request.args.get("pagina", 1, type=int), per_page=15, error_out=False)
    )
    return render_template(
        "site/suggestions.html",
        form=form,
        rows=filas,
        categorias=SUGGESTION_CATEGORIES,
        categoria=categoria,
        estado=estado,
    )


@bp.route("/sugerencias/<int:pk>/voto", methods=["POST"])
@login_required
def suggestion_like(pk: int):
    """Un voto por usuario y sugerencia (los ids guardados en ``voted_by``)."""
    suggestion = db.session.get(Suggestion, pk) or abort(404)
    liked = suggestion.toggle_vote(current_user.id)
    db.session.commit()
    flash("Voto registrado." if liked else "Voto quitado.", "info")
    return redirect(request.referrer or url_for("site.suggestions"))


# --------------------------------------------------------------------------- #
# API ligera para el JS (filtros del calendario)
# --------------------------------------------------------------------------- #
@bp.route("/api/matches")
def api_matches():
    division_id = request.args.get("division", type=int)
    journey = request.args.get("journey", type=int)
    q = Match.query
    if division_id:
        q = q.filter_by(division_id=division_id)
    if journey:
        q = q.filter_by(journey=journey)
    rows = (
        q.order_by(Match.journey, *nulls_last(Match.played_on, descending=False), Match.kickoff)
        .limit(200).all()
    )
    return {
        "matches": [
            {
                "id": m.id,
                "journey": m.journey,
                "stage": m.stage,
                "date": m.played_on.isoformat() if m.played_on else None,
                "kickoff": m.kickoff,
                "home": m.home_team.name if m.home_team else "Por definir",
                "away": m.away_team.name if m.away_team else "Por definir",
                "score": m.score_text,
                "status": m.status,
                "status_label": m.status_label,
            }
            for m in rows
        ]
    }
