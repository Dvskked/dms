"""Blueprint publico: la pagina de la liga con todas sus secciones."""
from __future__ import annotations

from collections import defaultdict
from datetime import date, timedelta

from flask import Blueprint, abort, current_app, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required
from sqlalchemy import func

from extensions import db
from forms import SuggestionForm
from mailer import notify_staff_new_suggestion
from models import (
    Alliance, Article, Category, Division, Donation, DonationChannel, DonationGoal,
    LiveStream, Match, MatchReport, MuseumItem, Player, PlayerMatchStat, PromotionSlot, Room,
    RuleEntry, SanctionLevel, Season, SocialLink, StaffMember, Standing, Suggestion,
    SuggestionStatus, SUGGESTION_CATEGORIES, Team, current_season,
    division_standings, log_activity, player_stat_rows, setting,
)
from utils import excerpt, nulls_last, rich_text

bp = Blueprint("site", __name__)


# --------------------------------------------------------------------------- #
# Consultas reutilizables
# --------------------------------------------------------------------------- #
def published(kind: str, limit: int | None = None):
    q = (
        Article.query.filter_by(kind=kind, is_published=True)
        .order_by(Article.is_pinned.desc(), Article.published_at.desc())
    )
    return q.limit(limit) if limit else q.all()


def current_division() -> Division | None:
    season = current_season()
    if not season:
        return Division.query.order_by(Division.level).first()
    return season.divisions[0] if season.divisions else Division.query.order_by(Division.level).first()


def stat_leaders(team_ids, column: str, order: str = "desc", limit: int = 10):
    if not list(team_ids):
        return []
    q = (
        Player.query.filter(Player.team_id.in_(list(team_ids)), Player.is_active.is_(True))
        .order_by(getattr(Player, column).desc() if order == "desc" else getattr(Player, column).asc())
    )
    return q.limit(limit).all()


def division_bundle(division: Division) -> dict:
    """Todo el contenido que necesita una division en las pestanas de LIGA."""
    team_ids = [t.id for t in Team.query.filter_by(division_id=division.id).order_by(Team.sort_order, Team.name).all()]

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
            rango = f"{lo.strftime('%d/%m')} · {hi.strftime('%d/%m')}" if lo != hi else lo.strftime("%d/%m/%Y")
        else:
            rango = "Fecha por definir"
        calendar.append({"journey": journey, "matches": items, "range": rango})

    rows = division_standings(division.id)
    teams = Team.query.filter_by(division_id=division.id, is_active=True).order_by(Team.sort_order, Team.name).all()

    stats = player_stat_rows(division_id=division.id)

    return {
        "division": division,
        "teams": teams,
        "calendar": calendar,
        "standings": rows,
        "scorers": stat_leaders(team_ids, "goals"),
        "assistants": stat_leaders(team_ids, "assists"),
        "keepers": stat_leaders(team_ids, "clean_sheets"),
        "own_goalers": stat_leaders(team_ids, "own_goals", order="asc", limit=8),
        "players": stats,
        "total_matches": len(matches),
        "goals_total": sum(s.goals or 0 for s in stats),
        "assists_total": sum(s.assists or 0 for s in stats),
    }


def published_articles(kind: str):
    return published(kind)


# --------------------------------------------------------------------------- #
# Pagina principal (unica, con anclas por seccion del header)
# --------------------------------------------------------------------------- #
@bp.route("/")
def index():
    season = current_season()
    divisions = Division.query.order_by(Division.level).all() if season else []
    division = divisions[0] if divisions else None

    rooms = Room.query.filter_by(is_open=True).order_by(Room.sort_order, Room.code).all()
    museum = (
        MuseumItem.query.order_by(MuseumItem.sort_order, *nulls_last(MuseumItem.awarded_on), MuseumItem.id.desc())
        .all()
    )
    news = published(Category.NEWS)
    announcements = published(Category.ANNOUNCEMENT)
    reports = published(Category.REPORT)

    alliances = Alliance.query.order_by(Alliance.sort_order, Alliance.name).all()
    featured_alliance = next((a for a in alliances if a.is_featured), None)

    socials = (
        SocialLink.query.filter_by(is_active=True).order_by(SocialLink.owner, SocialLink.sort_order).all()
    )
    socials_by_owner = defaultdict(list)
    for link in socials:
        socials_by_owner[link.owner].append(link)

    staff = StaffMember.query.filter_by(is_active=True).order_by(StaffMember.is_leader.desc(), StaffMember.sort_order).all()

    live_streams = (
        LiveStream.query.order_by(LiveStream.is_live.desc(), LiveStream.is_featured.desc(), LiveStream.sort_order)
        .all()
    )
    featured_live = next((s for s in live_streams if s.is_live and s.is_featured), None) \
        or next((s for s in live_streams if s.is_live), None)

    donation_channels = (
        DonationChannel.query.filter_by(is_active=True).order_by(DonationChannel.sort_order).all()
    )
    donation_goal = DonationGoal.query.filter_by(is_active=True).first()
    donations = Donation.query.filter_by(is_public=True).order_by(Donation.donated_at.desc()).limit(8).all()

    divisions_data = [division_bundle(d) for d in divisions]

    rules = (
        RuleEntry.query.filter_by(scope="discord").order_by(RuleEntry.position).all()
        + RuleEntry.query.filter_by(scope="comunidad").order_by(RuleEntry.position).all()
    )
    sanctions = SanctionLevel.query.order_by(SanctionLevel.sort_order).all()

    today = date.today()
    stats = {
        "teams": Team.query.filter_by(is_active=True).count(),
        "rooms": len(rooms),
        "museum": len(museum),
        "matches": Match.query.count(),
        "players": Player.query.filter_by(is_active=True).count(),
        "members": len(staff),
        "next_match": (
            Match.query.filter(
                Match.played_on.isnot(None), Match.played_on >= today, Match.status.in_(("scheduled", "live"))
            ).order_by(Match.played_on, Match.kickoff).first()
        ),
    }

    return render_template(
        "site/index.html",
        season=season,
        divisions=divisions,
        division=division,
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
        socials_by_owner=dict(socials_by_owner),
        staff=staff,
        live_streams=live_streams,
        featured_live=featured_live,
        donation_channels=donation_channels,
        donation_goal=donation_goal,
        donations=donations,
        divisions_data=divisions_data,
        rules=rules,
        sanctions=sanctions,
        stats=stats,
        teams=divisions_data[0]["teams"] if divisions_data else [],
        awards=MuseumItem.query.filter(MuseumItem.category == "premios").order_by(MuseumItem.sort_order).all(),
        champions=MuseumItem.query.filter(MuseumItem.category == "campeones").order_by(MuseumItem.sort_order).all(),
        rankings=MuseumItem.query.filter(MuseumItem.category == "rankings").order_by(MuseumItem.sort_order).all(),
        today=today,
        site_stats=dict(
            rooms_open=len(rooms),
            museum_total=len(museum),
            socials_total=len(socials),
            live_total=len(live_streams),
        ),
    )


# --------------------------------------------------------------------------- #
# Detalle de articulo
# --------------------------------------------------------------------------- #
@bp.route("/noticias/<slug>")
def article_detail(slug: str):
    item = Article.query.filter_by(slug=slug, is_published=True).first_or_404()
    if not item.is_live_now and item.id != getattr(current_user, "id", None):
        pass
    item.views = (item.views or 0) + 1
    db.session.commit()
    related = (
        Article.query.filter(Article.kind == item.kind, Article.id != item.id, Article.is_published.is_(True))
        .order_by(Article.published_at.desc()).limit(3).all()
    )
    return render_template("site/article.html", item=item, body=rich_text(item.body or ""), related=related)


# --------------------------------------------------------------------------- #
# Live de futbol: /live/<id> (pagina dedicada tipo Kick / Twitch)
# --------------------------------------------------------------------------- #
@bp.route("/live/<int:stream_id>")
def live_room(stream_id: int):
    stream = db.session.get(LiveStream, stream_id) or abort(404)
    others = (
        LiveStream.query.filter(LiveStream.id != stream.id).order_by(LiveStream.is_live.desc(), LiveStream.sort_order).limit(6).all()
    )
    upcoming = (
        Match.query
        .filter(Match.played_on >= date.today())
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
        # Solo el staff ve borradores; un jugador registrado tampoco.
        abort(404)

    home_stats = match.stats_for(match.home_team_id)
    away_stats = match.stats_for(match.away_team_id)

    journey_matches = (
        Match.query.filter_by(division_id=match.division_id, journey=match.journey)
        .order_by(Match.kickoff)
        .all()
    )
    others = [m for m in journey_matches if m.id != match.id]

    return render_template(
        "site/match_report.html",
        match=match,
        report=report,
        home_stats=home_stats,
        away_stats=away_stats,
        scorers=match.scorers,
        others=others,
        computed=(match.home_goals_from_stats, match.away_goals_from_stats),
    )


# --------------------------------------------------------------------------- #
# Estadisticas generales: tabla de las divisiones + tabla de jugadores
# --------------------------------------------------------------------------- #
@bp.route("/estadisticas")
def stats():
    """Tabla de las divisiones y tabla de estadisticas individuales."""
    season = current_season()
    divisions = (
        Division.query.filter_by(season_id=season.id).order_by(Division.level).all()
        if season else []
    )
    tables = [
        {
            "division": division,
            "standings": division_standings(division.id),
            "teams": Team.query.filter_by(division_id=division.id, is_active=True)
                             .order_by(Team.sort_order, Team.name).all(),
            "players": player_stat_rows(division_id=division.id),
            "calendar": Match.query.filter_by(division_id=division.id)
                                   .order_by(Match.journey.desc()).limit(6).all(),
        }
        for division in divisions
    ]
    return render_template(
        "site/stats.html",
        season=season,
        divisions=divisions,
        tables=tables,
        scorers=player_stat_rows(limit=15, season_id=season.id if season else None),
        recent_reports=(
            Match.query.join(MatchReport, MatchReport.match_id == Match.id)
            .filter(MatchReport.is_published.is_(True))
            .order_by(*nulls_last(Match.played_on))
            .limit(6)
            .all()
        ),
    )


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

        # Aviso al staff por correo: aviso al canal de sugerencias.
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
    """Un voto por usuario y sugerencia (se controla con la tabla de votos)."""
    suggestion = db.session.get(Suggestion, pk) or abort(404)
    from models import SuggestionVote

    existing = SuggestionVote.query.filter_by(
        suggestion_id=suggestion.id, user_id=current_user.id
    ).first()
    if existing:
        db.session.delete(existing)
        suggestion.likes = max((suggestion.likes or 1) - 1, 0)
        liked = False
    else:
        db.session.add(SuggestionVote(suggestion_id=suggestion.id, user_id=current_user.id))
        suggestion.likes = (suggestion.likes or 0) + 1
        liked = True
    db.session.commit()
    flash("Voto registrado." if liked else "Voto quitado.", "info")
    return redirect(request.referrer or url_for("site.suggestions"))


# --------------------------------------------------------------------------- #
# API ligera para el JS (filtros y calificacion en vivo)
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
    rows = q.order_by(Match.journey, *nulls_last(Match.played_on, descending=False), Match.kickoff).limit(200).all()
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
            }
            for m in rows
        ]
    }