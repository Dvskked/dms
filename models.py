"""Modelos de datos de The Diamonds League.

Un solo conjunto de modelos sirve para SQLite (desarrollo) y para MySQL /
PostgreSQL (produccion): solo cambia DATABASE_URL en .env
"""
from __future__ import annotations

from datetime import date, datetime
from typing import Optional

from flask_login import AnonymousUserMixin, UserMixin
from sqlalchemy import CheckConstraint, Index, UniqueConstraint, func

from extensions import db, login_manager
from utils import hash_password, slugify, utcnow, verify_password


# --------------------------------------------------------------------------- #
# Mezclas
# --------------------------------------------------------------------------- #
class TimestampMixin:
    created_at = db.Column(db.DateTime, default=utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=utcnow, onupdate=utcnow, nullable=False)


# --------------------------------------------------------------------------- #
# Usuarios
# --------------------------------------------------------------------------- #
class Role:
    ADMIN = "admin"
    STAFF = "staff"
    USER = "user"

    ALL = (ADMIN, STAFF, USER)
    LABELS = {ADMIN: "Administrador", STAFF: "Staff", USER: "Jugador"}


class User(UserMixin, TimestampMixin, db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(24), unique=True, nullable=False, index=True)
    email = db.Column(db.String(160), unique=True, nullable=False, index=True)
    password = db.Column(db.String(255), nullable=False)

    role = db.Column(db.String(16), nullable=False, default=Role.USER, index=True)
    is_admin = db.Column(db.Boolean, nullable=False, default=False)
    is_premium = db.Column(db.Boolean, nullable=False, default=False)
    is_active_account = db.Column(db.Boolean, nullable=False, default=True)

    display_name = db.Column(db.String(60))
    bio = db.Column(db.String(400))
    haxball_id = db.Column(db.String(40))
    avatar = db.Column(db.String(255))
    google_email = db.Column(db.String(160))
    country = db.Column(db.String(60))

    last_login = db.Column(db.DateTime)
    login_count = db.Column(db.Integer, nullable=False, default=0)

    __table_args__ = (
        CheckConstraint("role in ('admin','staff','user')", name="role_valid"),
    )

    # -- passwords ---------------------------------------------------------- #
    def set_password(self, raw: str) -> None:
        self.password = hash_password(raw)

    def check_password(self, raw: str) -> bool:
        return verify_password(self.password, raw)

    # -- flask-login -------------------------------------------------------- #
    @property
    def is_active(self) -> bool:  # type: ignore[override]
        return bool(self.is_active_account)

    @property
    def is_staff(self) -> bool:
        return self.is_admin or self.role == Role.STAFF

    @property
    def label(self) -> str:
        return self.display_name or self.username

    @property
    def initials(self) -> str:
        text = self.label.strip()
        parts = [p for p in text.replace("_", " ").split() if p]
        return (parts[0][:1] + (parts[1][:1] if len(parts) > 1 else "")).upper() or "?"

    @property
    def avatar_url(self) -> str:
        return self.avatar or "img/logo-mark.png"

    def public_dict(self) -> dict:
        return {
            "id": self.id,
            "username": self.username,
            "display_name": self.label,
            "role": self.role,
            "role_label": Role.LABELS.get(self.role, self.role),
            "avatar": self.avatar_url,
            "premium": self.is_premium,
        }

    def __repr__(self) -> str:  # pragma: no cover
        return f"<User {self.username} role={self.role}>"


class AnonymousUser(AnonymousUserMixin):
    """Visitante sin sesion: expone los mismos atributos que `User`.

    Sin esto, `current_user.is_staff` revienta con AttributeError en las
    plantillas y vistas que lo consultan sin comprobar antes `is_authenticated`.
    """

    is_admin = False
    is_premium = False
    is_staff = False


login_manager.anonymous_user = AnonymousUser


@login_manager.user_loader
def load_user(user_id: str):
    try:
        return db.session.get(User, int(user_id))
    except (TypeError, ValueError):
        return None


# --------------------------------------------------------------------------- #
# Estructura de liga
# --------------------------------------------------------------------------- #
class Season(TimestampMixin, db.Model):
    __tablename__ = "seasons"

    id = db.Column(db.Integer, primary_key=True)
    number = db.Column(db.Integer, nullable=False)
    name = db.Column(db.String(60), nullable=False)
    year = db.Column(db.String(12))
    is_current = db.Column(db.Boolean, nullable=False, default=False, index=True)
    starts_on = db.Column(db.Date)
    ends_on = db.Column(db.Date)
    registration_opens = db.Column(db.Date)
    is_registration_open = db.Column(db.Boolean, nullable=False, default=False)
    notes = db.Column(db.Text)

    divisions = db.relationship("Division", back_populates="season", cascade="all, delete-orphan", lazy="selectin")
    __table_args__ = (UniqueConstraint("number", name="uq_season_number"),)

    @property
    def label(self) -> str:
        return f"Temporada {self.number}"

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Season T{self.number}>"


class Division(TimestampMixin, db.Model):
    __tablename__ = "divisions"

    id = db.Column(db.Integer, primary_key=True)
    season_id = db.Column(db.Integer, db.ForeignKey("seasons.id", ondelete="CASCADE"), nullable=False, index=True)
    key = db.Column(db.String(40), unique=True, nullable=False)   # division-one, division-two
    name = db.Column(db.String(80), nullable=False)                # "Division 1"
    short = db.Column(db.String(8), nullable=False)                # "D1"
    level = db.Column(db.Integer, nullable=False, default=1)

    teams_count = db.Column(db.Integer, nullable=False, default=0)
    journeys_count = db.Column(db.Integer, nullable=False, default=0)
    playoffs_slots = db.Column(db.Integer, nullable=False, default=4)
    relegation_slots = db.Column(db.Integer, nullable=False, default=0)
    promotion_slots = db.Column(db.Integer, nullable=False, default=0)

    modality = db.Column(db.String(60), default="5 VS 5 · X5")
    duration = db.Column(db.String(80), default="Dos tiempos de 10:00 + ultima jugada")
    map_name = db.Column(db.String(80), default="5v5 Diamonds League")
    server = db.Column(db.String(60), default="X Hosting")
    tolerance = db.Column(db.String(80), default="15 minutos")

    description = db.Column(db.Text)
    schedule_note = db.Column(db.String(200))
    document_url = db.Column(db.String(255))

    season = db.relationship("Season", back_populates="divisions")
    phases = db.relationship("Phase", back_populates="division", cascade="all, delete-orphan",
                             order_by="Phase.order", lazy="selectin")
    teams = db.relationship("Team", back_populates="division", lazy="selectin")
    base_rules = db.relationship("DivisionRule", back_populates="division", cascade="all, delete-orphan",
                                  order_by="DivisionRule.position", lazy="selectin")
    moves = db.relationship("PromotionSlot", back_populates="division", cascade="all, delete-orphan",
                            lazy="selectin")

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Division {self.name}>"


class Phase(TimestampMixin, db.Model):
    __tablename__ = "phases"

    id = db.Column(db.Integer, primary_key=True)
    division_id = db.Column(db.Integer, db.ForeignKey("divisions.id", ondelete="CASCADE"), nullable=False, index=True)
    order = db.Column(db.Integer, nullable=False, default=1)
    tag = db.Column(db.String(24), nullable=False)      # "FASE 1"
    title = db.Column(db.String(80), nullable=False)    # "LIGA REGULAR"
    body = db.Column(db.Text)
    highlight = db.Column(db.String(255))

    division = db.relationship("Division", back_populates="phases")


class DivisionRule(TimestampMixin, db.Model):
    __tablename__ = "division_rules"

    id = db.Column(db.Integer, primary_key=True)
    division_id = db.Column(db.Integer, db.ForeignKey("divisions.id", ondelete="CASCADE"), nullable=False, index=True)
    position = db.Column(db.Integer, nullable=False, default=1)
    title = db.Column(db.String(80), nullable=False)
    body = db.Column(db.Text)

    division = db.relationship("Division", back_populates="base_rules")


class PromotionSlot(TimestampMixin, db.Model):
    """Ascensos / descensos de una division."""
    __tablename__ = "promotion_slots"

    id = db.Column(db.Integer, primary_key=True)
    division_id = db.Column(db.Integer, db.ForeignKey("divisions.id", ondelete="CASCADE"), nullable=False, index=True)
    kind = db.Column(db.String(16), nullable=False)     # "promotion" | "relegation"
    tag = db.Column(db.String(40), nullable=False)
    title = db.Column(db.String(80), nullable=False)
    body = db.Column(db.String(255))

    division = db.relationship("Division", back_populates="moves")


# --------------------------------------------------------------------------- #
# Equipos, jugadores, tabla, partidos
# --------------------------------------------------------------------------- #
class Team(TimestampMixin, db.Model):
    __tablename__ = "teams"

    id = db.Column(db.Integer, primary_key=True)
    division_id = db.Column(db.Integer, db.ForeignKey("divisions.id", ondelete="SET NULL"), nullable=True, index=True)
    name = db.Column(db.String(80), nullable=False, unique=True)
    short = db.Column(db.String(20), nullable=False, default="")
    slug = db.Column(db.String(90), unique=True, nullable=False, index=True)
    crest = db.Column(db.String(255))
    coach = db.Column(db.String(60))
    captain = db.Column(db.String(60))
    country = db.Column(db.String(60))
    founded_year = db.Column(db.String(12))
    is_active = db.Column(db.Boolean, nullable=False, default=True, index=True)
    sort_order = db.Column(db.Integer, nullable=False, default=100)
    description = db.Column(db.Text)
    color = db.Column(db.String(16), default="#1bebf2")

    division = db.relationship("Division", back_populates="teams")
    players = db.relationship("Player", back_populates="team", cascade="all, delete-orphan", lazy="selectin")
    match_stats = db.relationship("PlayerMatchStat", back_populates="team", cascade="all, delete-orphan",
                                  lazy="selectin")

    def __init__(self, **kwargs):
        kwargs.setdefault("slug", slugify(kwargs.get("name", "equipo")))
        super().__init__(**kwargs)

    @property
    def initials(self) -> str:
        words = [w for w in (self.short or self.name).split() if w]
        return "".join(w[:1] for w in words[:2]).upper() or "EQ"

    @property
    def crest_url(self) -> str:
        return self.crest or "img/logo-mark.png"

    @property
    def has_crest(self) -> bool:
        return bool(self.crest)

    @property
    def player_count(self) -> int:
        return len([p for p in self.players if p.is_active])

    @property
    def squad_size(self) -> int:
        return len(self.players or [])

    @property
    def totals(self) -> dict:
        """Suma de la liga para el equipo (goles, asistencias, CS, autogoles)."""
        rows = {"goals": 0, "assists": 0, "clean_sheets": 0, "own_goals": 0,
                "yellow_cards": 0, "red_cards": 0, "matches": 0}
        for stat in self.match_stats or []:
            rows["goals"] += stat.goals or 0
            rows["assists"] += stat.assists or 0
            rows["clean_sheets"] += stat.clean_sheets or 0
            rows["own_goals"] += stat.own_goals or 0
            rows["yellow_cards"] += stat.yellow_cards or 0
            rows["red_cards"] += stat.red_cards or 0
        rows["matches"] = len({s.match_id for s in (self.match_stats or [])})
        return rows

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Team {self.name}>"


class Player(TimestampMixin, db.Model):
    __tablename__ = "players"

    id = db.Column(db.Integer, primary_key=True)
    team_id = db.Column(db.Integer, db.ForeignKey("teams.id", ondelete="CASCADE"), nullable=False, index=True)
    username = db.Column(db.String(60), nullable=False)
    haxball_id = db.Column(db.String(40))
    position = db.Column(db.String(24), default="MF")
    number = db.Column(db.Integer, default=0)
    country = db.Column(db.String(60))
    is_captain = db.Column(db.Boolean, nullable=False, default=False)
    is_active = db.Column(db.Boolean, nullable=False, default=True, index=True)

    matches = db.Column(db.Integer, nullable=False, default=0)
    goals = db.Column(db.Integer, nullable=False, default=0)
    assists = db.Column(db.Integer, nullable=False, default=0)
    clean_sheets = db.Column(db.Integer, nullable=False, default=0)
    clean_sheet_seconds = db.Column(db.Integer, nullable=False, default=0)
    own_goals = db.Column(db.Integer, nullable=False, default=0)
    yellow_cards = db.Column(db.Integer, nullable=False, default=0)
    red_cards = db.Column(db.Integer, nullable=False, default=0)

    team = db.relationship("Team", back_populates="players")

    match_stats = db.relationship(
        "PlayerMatchStat", back_populates="player",
        cascade="all, delete-orphan", lazy="selectin",
    )

    @property
    def display(self) -> str:
        return self.username

    @property
    def position_label(self) -> str:
        return {"GK": "Portero", "DF": "Defensa", "MF": "Medio", "MC": "Mediocampo",
                "FW": "Delantero"}.get(self.position, self.position or "—")

    @property
    def goals_per_match(self) -> float:
        return round((self.goals or 0) / self.matches, 2) if self.matches else 0.0

    @property
    def contribution(self) -> int:
        return (self.goals or 0) * 2 + (self.assists or 0)

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Player {self.username}>"


class Standing(TimestampMixin, db.Model):
    __tablename__ = "standings"

    id = db.Column(db.Integer, primary_key=True)
    division_id = db.Column(db.Integer, db.ForeignKey("divisions.id", ondelete="CASCADE"), nullable=False, index=True)
    team_id = db.Column(db.Integer, db.ForeignKey("teams.id", ondelete="CASCADE"), nullable=False, index=True)

    played = db.Column(db.Integer, nullable=False, default=0)
    won = db.Column(db.Integer, nullable=False, default=0)
    drawn = db.Column(db.Integer, nullable=False, default=0)
    lost = db.Column(db.Integer, nullable=False, default=0)
    goals_for = db.Column(db.Integer, nullable=False, default=0)
    goals_against = db.Column(db.Integer, nullable=False, default=0)
    points = db.Column(db.Integer, nullable=False, default=0)
    position = db.Column(db.Integer, nullable=False, default=0)
    note = db.Column(db.String(80))

    division = db.relationship("Division")
    team = db.relationship("Team", lazy="joined")

    __table_args__ = (UniqueConstraint("division_id", "team_id", name="uq_standing_division_team"),)

    @property
    def goal_difference(self) -> int:
        return self.goals_for - self.goals_against

    def recompute(self) -> None:
        self.played = self.won + self.drawn + self.lost
        self.points = self.won * 3 + self.drawn

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Standing {self.team_id} pts={self.points}>"


class Match(TimestampMixin, db.Model):
    __tablename__ = "matches"

    id = db.Column(db.Integer, primary_key=True)
    division_id = db.Column(db.Integer, db.ForeignKey("divisions.id", ondelete="CASCADE"), nullable=False, index=True)
    journey = db.Column(db.Integer, nullable=False, default=1, index=True)
    stage = db.Column(db.String(40), nullable=False, default="Liga regular")
    played_on = db.Column(db.Date, index=True)
    kickoff = db.Column(db.String(5), default="19:00")

    home_team_id = db.Column(db.Integer, db.ForeignKey("teams.id", ondelete="CASCADE"), nullable=False, index=True)
    away_team_id = db.Column(db.Integer, db.ForeignKey("teams.id", ondelete="CASCADE"), nullable=False, index=True)

    home_score = db.Column(db.Integer)
    away_score = db.Column(db.Integer)
    status = db.Column(db.String(16), nullable=False, default="scheduled", index=True)  # scheduled|live|finished|wo
    room_url = db.Column(db.String(255))
    replay_url = db.Column(db.String(255))
    stream_url = db.Column(db.String(255))
    notes = db.Column(db.Text)

    home_team = db.relationship("Team", foreign_keys=[home_team_id], lazy="joined")
    away_team = db.relationship("Team", foreign_keys=[away_team_id], lazy="joined")
    division = db.relationship("Division", lazy="joined")

    report = db.relationship(
        "MatchReport", back_populates="match", uselist=False,
        cascade="all, delete-orphan", lazy="selectin",
    )
    player_stats = db.relationship(
        "PlayerMatchStat", back_populates="match",
        cascade="all, delete-orphan", lazy="selectin",
        order_by="PlayerMatchStat.goals.desc(), PlayerMatchStat.player_id",
    )

    __table_args__ = (
        Index("ix_match_division_journey", "division_id", "journey"),
        CheckConstraint("status in ('scheduled','live','finished','wo','postponed')", name="status_valid"),
    )

    @property
    def is_finished(self) -> bool:
        return self.status == "finished"

    @property
    def score_text(self) -> str:
        if self.home_score is None or self.away_score is None:
            return "vs"
        return f"{self.home_score} - {self.away_score}"

    @property
    def headline(self) -> str:
        """'LOS DIAMONDS 3 - 1 RIVER FC' para listados y cabeceras."""
        home = self.home_team.name if self.home_team else "Local"
        away = self.away_team.name if self.away_team else "Visitante"
        return f"{home} {self.score_text} {away}"

    def result_for(self, team_id: int) -> Optional[str]:
        if not self.is_finished:
            return None
        if self.home_team_id == team_id:
            if self.home_score > self.away_score:
                return "W"
            return "D" if self.home_score == self.away_score else "L"
        if self.away_score > self.home_score:
            return "W"
        return "D" if self.home_score == self.away_score else "L"

    # -- Informe ----------------------------------------------------------- #
    def stats_for(self, team_id: int) -> list["PlayerMatchStat"]:
        return [s for s in (self.player_stats or []) if s.team_id == team_id]

    @property
    def has_report(self) -> bool:
        return self.report is not None and bool(self.report.has_content)

    def _goals_for(self, team_id: int) -> int:
        """Goles a favor de `team_id` segun las fichas de los jugadores.

        Los autogoles se anotan al jugador que los cometio (para sus
        estadisticas) pero el gol suma al equipo contrario.
        """
        stats = self.player_stats or []
        scored = sum(s.goals or 0 for s in stats if s.team_id == team_id)
        rival_own = sum(s.own_goals or 0 for s in stats if s.team_id != team_id)
        return scored + rival_own

    @property
    def home_goals_from_stats(self) -> int:
        """Goles del local = goles de sus jugadores + autogoles del rival."""
        return self._goals_for(self.home_team_id)

    @property
    def away_goals_from_stats(self) -> int:
        """Goles del visitante = goles de sus jugadores + autogoles del local."""
        return self._goals_for(self.away_team_id)

    @property
    def scorers(self) -> list["PlayerMatchStat"]:
        return [s for s in (self.player_stats or []) if s.goals or s.own_goals]

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Match J{self.journey} {self.home_team_id} vs {self.away_team_id}>"


class MatchReport(TimestampMixin, db.Model):
    """Informe de un partido: foto, resultado y lectura del juego.

    Es 1:1 con Match. Lo edita el staff desde /admin/partidos/<id>/informe.
    """
    __tablename__ = "match_reports"

    id = db.Column(db.Integer, primary_key=True)
    match_id = db.Column(db.Integer, db.ForeignKey("matches.id", ondelete="CASCADE"),
                         nullable=False, unique=True, index=True)

    photo = db.Column(db.String(255))            # foto del partido
    photo_credit = db.Column(db.String(120))
    headline = db.Column(db.String(180))         # "Goleada en la jornada 5"
    summary = db.Column(db.String(400))
    body = db.Column(db.Text)                    # cronica / analisis
    video_url = db.Column(db.String(255))

    mvp_player_id = db.Column(db.Integer, db.ForeignKey("players.id", ondelete="SET NULL"),
                              nullable=True, index=True)
    author_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="SET NULL"), nullable=True)

    is_published = db.Column(db.Boolean, nullable=False, default=False, index=True)

    match = db.relationship("Match", back_populates="report")
    mvp = db.relationship("Player", lazy="joined")
    author = db.relationship("User", lazy="joined")

    @property
    def has_content(self) -> bool:
        return bool(self.photo or self.headline or self.summary or self.body)

    @property
    def photo_url(self) -> str | None:
        return self.photo

    @property
    def author_label(self) -> str:
        return self.author.label if self.author else "Redaccion de la liga"

    @property
    def stats(self) -> list["PlayerMatchStat"]:
        return list(self.match.player_stats or []) if self.match else []

    def __repr__(self) -> str:  # pragma: no cover
        return f"<MatchReport match={self.match_id}>"


class PlayerMatchStat(TimestampMixin, db.Model):
    """Estadistica individual de UN jugador en UN partido.

    Es la fuente de verdad de los goles, asistencias, clean sheets y
    autogoles; `Player.goals` etc. son el acumulado que se recalcula desde aqui.
    """
    __tablename__ = "player_match_stats"

    id = db.Column(db.Integer, primary_key=True)
    match_id = db.Column(db.Integer, db.ForeignKey("matches.id", ondelete="CASCADE"),
                         nullable=False, index=True)
    player_id = db.Column(db.Integer, db.ForeignKey("players.id", ondelete="CASCADE"),
                          nullable=False, index=True)
    team_id = db.Column(db.Integer, db.ForeignKey("teams.id", ondelete="CASCADE"),
                        nullable=False, index=True)

    goals = db.Column(db.Integer, nullable=False, default=0)
    assists = db.Column(db.Integer, nullable=False, default=0)
    clean_sheets = db.Column(db.Integer, nullable=False, default=0)   # CS / vallas invictas
    clean_sheet_seconds = db.Column(db.Integer, nullable=False, default=0)
    own_goals = db.Column(db.Integer, nullable=False, default=0)      # autogoles
    yellow_cards = db.Column(db.Integer, nullable=False, default=0)
    red_cards = db.Column(db.Integer, nullable=False, default=0)
    minutes = db.Column(db.Integer, nullable=False, default=0)
    is_mvp = db.Column(db.Boolean, nullable=False, default=False)
    note = db.Column(db.String(160))

    match = db.relationship("Match", back_populates="player_stats")
    player = db.relationship("Player", lazy="joined")
    team = db.relationship("Team", lazy="joined")

    __table_args__ = (
        UniqueConstraint("match_id", "player_id", name="uq_stat_match_player"),
        Index("ix_stat_player_match", "player_id", "match_id"),
    )

    @property
    def team_is_home(self) -> bool:
        return bool(self.match and self.team_id == self.match.home_team_id)

    @property
    def contribution(self) -> int:
        """Goles x2 + asistencias: metrica para ordenar las contribuciones."""
        return (self.goals or 0) * 2 + (self.assists or 0)

    def apply_to(self, player: Player) -> None:
        player.matches = (player.matches or 0) + 1
        player.goals = (player.goals or 0) + (self.goals or 0)
        player.assists = (player.assists or 0) + (self.assists or 0)
        player.clean_sheets = (player.clean_sheets or 0) + (self.clean_sheets or 0)
        player.clean_sheet_seconds = (player.clean_sheet_seconds or 0) + (self.clean_sheet_seconds or 0)
        player.own_goals = (player.own_goals or 0) + (self.own_goals or 0)
        player.yellow_cards = (player.yellow_cards or 0) + (self.yellow_cards or 0)
        player.red_cards = (player.red_cards or 0) + (self.red_cards or 0)

    def __repr__(self) -> str:  # pragma: no cover
        return f"<PlayerMatchStat p{self.player_id} m{self.match_id} g{self.goals}>"


class PasswordResetToken(TimestampMixin, db.Model):
    """Token de un solo uso para restablecer la contrasena por correo."""
    __tablename__ = "password_reset_tokens"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"),
                        nullable=False, index=True)
    token_hash = db.Column(db.String(128), nullable=False, unique=True, index=True)
    expires_at = db.Column(db.DateTime, nullable=False, index=True)
    used_at = db.Column(db.DateTime)
    requested_ip = db.Column(db.String(45))

    user = db.relationship("User", lazy="joined")

    @property
    def is_usable(self) -> bool:
        return self.used_at is None and self.expires_at > utcnow()

    def __repr__(self) -> str:  # pragma: no cover
        return f"<PasswordResetToken user={self.user_id} usable={self.is_usable}>"


class EmailLog(TimestampMixin, db.Model):
    """Historial de correos enviados (bienvenida, contrasena, avisos)."""
    __tablename__ = "email_logs"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="SET NULL"),
                        nullable=True, index=True)
    to_email = db.Column(db.String(160), nullable=False, index=True)
    subject = db.Column(db.String(180), nullable=False)
    template = db.Column(db.String(40), nullable=False, default="general", index=True)
    status = db.Column(db.String(16), nullable=False, default="sent", index=True)  # sent|failed|skipped
    error = db.Column(db.String(255))
    sent_at = db.Column(db.DateTime, default=utcnow, index=True)

    user = db.relationship("User", lazy="joined")

    @property
    def status_label(self) -> str:
        return {"sent": "Enviado", "failed": "Fallido", "skipped": "Omitido"}.get(self.status, self.status)

    @property
    def target(self) -> str:
        return self.user.label if self.user else (self.to_email or "—")

    def __repr__(self) -> str:  # pragma: no cover
        return f"<EmailLog {self.template}->{self.to_email} {self.status}>"


# --------------------------------------------------------------------------- #
# Contenido
# --------------------------------------------------------------------------- #
class Room(TimestampMixin, db.Model):
    """Salas publicas de HaxBall."""
    __tablename__ = "rooms"

    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(12), nullable=False)          # "ROOM 01"
    name = db.Column(db.String(80), nullable=False, default="DIAMONDS PUBLIC")
    haxball_url = db.Column(db.String(255), nullable=False)
    region = db.Column(db.String(40), default="Latam")
    max_players = db.Column(db.Integer, nullable=False, default=12)
    description = db.Column(db.String(255))
    is_open = db.Column(db.Boolean, nullable=False, default=True, index=True)
    sort_order = db.Column(db.Integer, nullable=False, default=100)
    players_online = db.Column(db.Integer, nullable=False, default=0)
    image = db.Column(db.String(255))
    map_name = db.Column(db.String(80), default="5v5 Diamonds League")
    mode = db.Column(db.String(40), default="5 VS 5")
    ping = db.Column(db.String(40), default="Latam")
    password = db.Column(db.String(60))
    is_pinned = db.Column(db.Boolean, nullable=False, default=False)
    is_featured = db.Column(db.Boolean, nullable=False, default=False)

    __table_args__ = (UniqueConstraint("code", name="uq_room_code"),)

    @property
    def display_code(self) -> str:
        return f"ROOM {self.code}"

    @property
    def haxball_id(self) -> str:
        return (self.haxball_url or "").rstrip("/").split("/")[-1].split("?")[-1]

    @property
    def room_url(self) -> str:
        return self.haxball_url

    @property
    def is_locked(self) -> bool:
        return not self.is_open

    @property
    def mode_label(self) -> str:
        return self.mode or "5 VS 5"

    @property
    def ping_label(self) -> str:
        return self.ping or self.region or "Latam"

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Room {self.code}>"


class Category:
    """Tipos de articulo editorial. Los valores deben coincidir con el
    CheckConstraint de la tabla ``articles``."""

    NEWS = "news"
    ANNOUNCEMENT = "announcement"
    REPORT = "report"

    ALL = (NEWS, ANNOUNCEMENT, REPORT)
    LABELS = {
        NEWS: "Noticia",
        ANNOUNCEMENT: "Anuncio",
        REPORT: "Informe",
    }


class Article(TimestampMixin, db.Model):
    """Noticias, anuncios e informes en un unico recurso editorial."""
    __tablename__ = "articles"

    id = db.Column(db.Integer, primary_key=True)
    kind = db.Column(db.String(20), nullable=False, default=Category.NEWS, index=True)  # news|announcement|report
    category = db.Column(db.String(30), nullable=False, default="general", index=True)
    title = db.Column(db.String(180), nullable=False)
    slug = db.Column(db.String(200), unique=True, nullable=False, index=True)
    summary = db.Column(db.String(400))
    body = db.Column(db.Text)
    cover = db.Column(db.String(255))
    is_featured = db.Column(db.Boolean, nullable=False, default=False, index=True)
    is_pinned = db.Column(db.Boolean, nullable=False, default=False, index=True)
    is_published = db.Column(db.Boolean, nullable=False, default=True, index=True)
    published_at = db.Column(db.DateTime, default=utcnow, index=True)
    expires_at = db.Column(db.DateTime)
    attachment = db.Column(db.String(255))
    views = db.Column(db.Integer, nullable=False, default=0)
    author_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    division_id = db.Column(db.Integer, db.ForeignKey("divisions.id", ondelete="SET NULL"), nullable=True)

    author = db.relationship("User", lazy="joined")
    division = db.relationship("Division", lazy="joined")

    __table_args__ = (
        CheckConstraint("kind in ('news','announcement','report')", name="kind_valid"),
        CheckConstraint("category in ('general','inscripcion','premios','sanciones','eventos','sorteos','entrevista')",
                        name="category_valid"),
        Index("ix_article_kind_published", "kind", "is_published", "published_at"),
    )

    def __init__(self, **kwargs):
        kwargs.setdefault("slug", slugify(kwargs.get("title", "articulo")))
        super().__init__(**kwargs)

    @property
    def kind_label(self) -> str:
        return {"news": "Noticia", "announcement": "Anuncio", "report": "Informe"}.get(self.kind, self.kind)

    @property
    def category_label(self) -> str:
        return {
            "general": "General", "inscripcion": "Inscripcion", "premios": "Premios",
            "sanciones": "Sanciones", "eventos": "Eventos", "sorteos": "Sorteos", "entrevista": "Entrevista",
        }.get(self.category, self.category.title())

    @property
    def cover_url(self) -> str | None:
        return self.cover

    @property
    def author_label(self) -> str:
        if self.author:
            return self.author.label
        return "Redaccion de la liga"

    @property
    def excerpt_text(self, length: int = 160) -> str:
        from utils import excerpt as _excerpt

        return _excerpt(self.summary or self.body, length)

    @property
    def is_live_now(self) -> bool:
        now = utcnow()
        if not self.is_published:
            return False
        if self.published_at and self.published_at > now:
            return False
        return not self.expires_at or self.expires_at >= now

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Article {self.kind}:{self.slug}>"


class MuseumItem(TimestampMixin, db.Model):
    """Museo de premios: balon, bota, guante, rankings, campeones, trofeos."""
    __tablename__ = "museum_items"

    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(140), nullable=False)
    slug = db.Column(db.String(160), unique=True, nullable=False, index=True)
    category = db.Column(db.String(30), nullable=False, default="premios", index=True)
    division_short = db.Column(db.String(8))
    season_number = db.Column(db.Integer)
    recipient = db.Column(db.String(80))
    team_id = db.Column(db.Integer, db.ForeignKey("teams.id", ondelete="SET NULL"), nullable=True)
    description = db.Column(db.String(400))
    image = db.Column(db.String(255))
    place = db.Column(db.Integer, nullable=False, default=0)
    awarded_on = db.Column(db.Date, index=True)
    is_highlight = db.Column(db.Boolean, nullable=False, default=False)
    sort_order = db.Column(db.Integer, nullable=False, default=100)

    team = db.relationship("Team", lazy="joined")

    CATEGORIES = ("premios", "rankings", "campeones", "trofeos")
    CATEGORY_LABELS = {
        "premios": "Premios", "rankings": "Rankings", "campeones": "Campeones", "trofeos": "Trofeos",
    }

    def __init__(self, **kwargs):
        kwargs.setdefault("slug", slugify(kwargs.get("title", "premio")))
        super().__init__(**kwargs)

    @property
    def category_label(self) -> str:
        return self.CATEGORY_LABELS.get(self.category, self.category.title())

    @property
    def division_label(self) -> str:
        return self.division_short or "LIGA"

    @property
    def image_url(self) -> str | None:
        return self.image

    @property
    def initials(self) -> str:
        words = [w for w in (self.title or "D").split() if w]
        return "".join(w[0] for w in words[:2]).upper() or "D"

    @property
    def holder(self) -> str | None:
        if self.recipient:
            return self.recipient
        return self.team.name if self.team else None

    def __repr__(self) -> str:  # pragma: no cover
        return f"<MuseumItem {self.title}>"


class Alliance(TimestampMixin, db.Model):
    __tablename__ = "alliances"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(90), nullable=False)
    slug = db.Column(db.String(110), unique=True, nullable=False, index=True)
    kind = db.Column(db.String(20), nullable=False, default="partner", index=True)  # partner|affiliate
    tagline = db.Column(db.String(160))
    description = db.Column(db.Text)
    url = db.Column(db.String(255))
    emblem = db.Column(db.String(8), default="P")
    code = db.Column(db.String(60))
    status = db.Column(db.String(16), nullable=False, default="activa", index=True)  # activa|proxima|pendiente|cerrada
    starts_on = db.Column(db.Date, index=True)
    ends_on = db.Column(db.Date)
    sort_order = db.Column(db.Integer, nullable=False, default=100)
    is_featured = db.Column(db.Boolean, nullable=False, default=False)

    STATUSES = ("activa", "proxima", "pendiente", "cerrada")
    STATUS_LABELS = {"activa": "Activa", "proxima": "Proxima afiliacion", "pendiente": "Pendiente", "cerrada": "Cerrada"}

    def __init__(self, **kwargs):
        kwargs.setdefault("slug", slugify(kwargs.get("name", "alianza")))
        super().__init__(**kwargs)

    @property
    def status_label(self) -> str:
        return self.STATUS_LABELS.get(self.status, self.status.title())

    @property
    def kind_label(self) -> str:
        return "Afiliacion" if self.kind == "affiliate" else "Servidor partner"

    @property
    def initials(self) -> str:
        words = [w for w in (self.name or "A").split() if w]
        return "".join(w[0] for w in words[:2]).upper() or "A"

    @property
    def website(self) -> str | None:
        return self.url


class SocialLink(TimestampMixin, db.Model):
    __tablename__ = "social_links"

    id = db.Column(db.Integer, primary_key=True)
    platform = db.Column(db.String(24), nullable=False, index=True)  # tiktok, discord, x, instagram...
    owner = db.Column(db.String(24), nullable=False, default="liga", index=True)  # liga | streamer
    label = db.Column(db.String(60), nullable=False)
    handle = db.Column(db.String(80))
    url = db.Column(db.String(255), nullable=False)
    icon = db.Column(db.String(8), default="#")
    is_primary = db.Column(db.Boolean, nullable=False, default=False, index=True)
    is_active = db.Column(db.Boolean, nullable=False, default=True)
    sort_order = db.Column(db.Integer, nullable=False, default=100)

    OWNER_LABELS = {"liga": "Liga", "streamer": "Streamers", "equipo": "Equipo"}
    PLATFORM_LABELS = {
        "tiktok": "TikTok", "discord": "Discord", "x": "X", "twitter": "Twitter",
        "instagram": "Instagram", "youtube": "YouTube", "twitch": "Twitch",
        "facebook": "Facebook", "kick": "Kick", "haxball": "HaxBall",
    }

    @property
    def platform_label(self) -> str:
        return self.PLATFORM_LABELS.get(self.platform, self.platform.title())

    @property
    def owner_label(self) -> str:
        return self.OWNER_LABELS.get(self.owner, self.owner.title())


class StaffMember(TimestampMixin, db.Model):
    __tablename__ = "staff_members"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(60), nullable=False)
    username = db.Column(db.String(60))
    role = db.Column(db.String(40), nullable=False, default="STAFF", index=True)
    title = db.Column(db.String(80))
    bio = db.Column(db.String(400))
    avatar = db.Column(db.String(255))
    banner = db.Column(db.String(255))
    tags = db.Column(db.String(160))
    discord = db.Column(db.String(80))
    email = db.Column(db.String(160))
    is_leader = db.Column(db.Boolean, nullable=False, default=False, index=True)
    is_active = db.Column(db.Boolean, nullable=False, default=True, index=True)
    sort_order = db.Column(db.Integer, nullable=False, default=100)

    @property
    def tag_list(self) -> list[str]:
        return [t.strip() for t in (self.tags or "").split(",") if t.strip()]

    @property
    def avatar_url(self) -> str | None:
        return self.avatar

    @property
    def banner_url(self) -> str | None:
        return self.banner

    @property
    def initials(self) -> str:
        words = [w for w in (self.name or "DL").split() if w]
        return "".join(w[0] for w in words[:2]).upper() or "DL"

    @property
    def nickname(self) -> str | None:
        return self.username


class RuleEntry(TimestampMixin, db.Model):
    """Reglamento general (discord / comunidad / sanciones)."""
    __tablename__ = "rule_entries"

    id = db.Column(db.Integer, primary_key=True)
    scope = db.Column(db.String(30), nullable=False, default="discord", index=True)
    position = db.Column(db.Integer, nullable=False, default=1)
    title = db.Column(db.String(90), nullable=False)
    body = db.Column(db.Text)

    SCOPES = ("discord", "comunidad", "sanciones")
    SCOPE_LABELS = {"discord": "Discord", "comunidad": "Comunidad", "sanciones": "Sanciones"}


class SanctionLevel(TimestampMixin, db.Model):
    __tablename__ = "sanction_levels"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(60), nullable=False)
    color = db.Column(db.String(20), nullable=False, default="general")
    items = db.Column(db.Text)
    note = db.Column(db.String(255))
    sort_order = db.Column(db.Integer, nullable=False, default=100)


class LiveStream(TimestampMixin, db.Model):
    """Live de futbol real, estilo Kick / Twitch."""
    __tablename__ = "live_streams"

    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(160), nullable=False)
    platform = db.Column(db.String(20), nullable=False, default="twitch", index=True)
    channel = db.Column(db.String(80))
    embed_url = db.Column(db.String(400))
    watch_url = db.Column(db.String(255), nullable=False)
    league = db.Column(db.String(80))
    competition = db.Column(db.String(80))
    thumbnail = db.Column(db.String(255))
    language = db.Column(db.String(20), default="es")
    is_live = db.Column(db.Boolean, nullable=False, default=False, index=True)
    is_featured = db.Column(db.Boolean, nullable=False, default=False)
    viewers = db.Column(db.Integer, nullable=False, default=0)
    scheduled_at = db.Column(db.DateTime)
    sort_order = db.Column(db.Integer, nullable=False, default=100)

    PLATFORMS = ("twitch", "kick", "youtube", "otro")
    PLATFORM_LABELS = {"twitch": "Twitch", "kick": "Kick", "youtube": "YouTube", "otro": "Otro"}

    @property
    def player_embed(self) -> str | None:
        if self.embed_url:
            return self.embed_url
        if self.platform == "twitch" and self.channel:
            from flask import current_app, request
            parent = current_app.config.get("TWITCH_PARENT") or request.host
            return f"https://player.twitch.tv/?channel={self.channel}&parent={parent}&muted=true"
        if self.platform == "youtube" and self.channel:
            return f"https://www.youtube.com/embed/{self.channel}?rel=0"
        return None

    @property
    def platform_label(self) -> str:
        return self.PLATFORM_LABELS.get(self.platform, self.platform.title())

    @property
    def is_upcoming(self) -> bool:
        if self.is_live:
            return False
        return bool(self.scheduled_at) and self.scheduled_at > utcnow()

    @property
    def chat_url(self) -> str | None:
        return self.embed_url

    @property
    def description(self) -> str:
        bits = [b for b in (self.league, self.competition, self.channel) if b]
        return " · ".join(bits)

    @property
    def category(self) -> str:
        return self.competition or self.league or "TRANSMISION"

    @property
    def url(self) -> str:
        return self.watch_url


class DonationChannel(TimestampMixin, db.Model):
    """Metodos de pago del bloque DONACION."""
    __tablename__ = "donation_channels"

    id = db.Column(db.Integer, primary_key=True)
    label = db.Column(db.String(60), nullable=False)
    method = db.Column(db.String(60), nullable=False)
    account = db.Column(db.String(120), nullable=False)
    note = db.Column(db.String(255))
    icon = db.Column(db.String(8), default="$")
    color = db.Column(db.String(16), default="#1bebf2")
    url = db.Column(db.String(255))
    is_active = db.Column(db.Boolean, nullable=False, default=True)
    sort_order = db.Column(db.Integer, nullable=False, default=100)


class Donation(TimestampMixin, db.Model):
    """Donaciones recibidas."""
    __tablename__ = "donations"

    id = db.Column(db.Integer, primary_key=True)
    donor_name = db.Column(db.String(80), nullable=False)
    message = db.Column(db.String(400))
    amount = db.Column(db.Numeric(12, 2), nullable=False, default=0)
    currency = db.Column(db.String(8), nullable=False, default="USD")
    channel = db.Column(db.String(60))
    is_public = db.Column(db.Boolean, nullable=False, default=True, index=True)
    donated_at = db.Column(db.DateTime, default=utcnow, index=True)

    @property
    def display_name(self) -> str:
        return self.donor_name

    @property
    def initials(self) -> str:
        words = [w for w in (self.donor_name or "?").split() if w]
        return "".join(w[0] for w in words[:2]).upper() or "?"

    @property
    def amount_text(self) -> str:
        return f"${float(self.amount or 0):,.2f}"


class DonationGoal(TimestampMixin, db.Model):
    __tablename__ = "donation_goals"

    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(120), nullable=False)
    description = db.Column(db.String(400))
    target = db.Column(db.Numeric(12, 2), nullable=False, default=0)
    is_active = db.Column(db.Boolean, nullable=False, default=True)

    @property
    def raised(self) -> float:
        total = db.session.query(db.func.coalesce(db.func.sum(Donation.amount), 0)).scalar() or 0
        return float(total)

    @property
    def label(self) -> str:
        return self.title

    @property
    def current_amount(self) -> str:
        return f"${self.raised:,.2f}"

    @property
    def target_amount(self) -> str:
        return f"${float(self.target or 0):,.2f}"

    @property
    def percent(self) -> int:
        target = float(self.target or 0)
        if target <= 0:
            return 0
        return min(100, int(round(self.raised / target * 100)))


class SiteSetting(TimestampMixin, db.Model):
    """Configuracion editable de la web (modo admin/premium, textos, etc.)."""
    __tablename__ = "site_settings"

    id = db.Column(db.Integer, primary_key=True)
    key = db.Column(db.String(60), unique=True, nullable=False, index=True)
    value = db.Column(db.Text)
    group = db.Column(db.String(40), nullable=False, default="general")
    label = db.Column(db.String(80))
    input_type = db.Column(db.String(16), default="text")

    def as_bool(self) -> bool:
        return str(self.value).strip().lower() in {"1", "true", "yes", "on", "si"}

    def __repr__(self) -> str:  # pragma: no cover
        return f"<SiteSetting {self.key}={self.value}>"


class ActivityLog(TimestampMixin, db.Model):
    """Auditoria ligera del panel: quien creo/editó/elimino que."""
    __tablename__ = "activity_logs"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    action = db.Column(db.String(40), nullable=False, index=True)
    entity = db.Column(db.String(40), nullable=False)
    entity_id = db.Column(db.Integer)
    detail = db.Column(db.String(255))

    user = db.relationship("User", lazy="joined")


def log_activity(user, action: str, entity: str, entity_id: int | None = None, detail: str = "") -> None:
    db.session.add(
        ActivityLog(user_id=getattr(user, "id", None), action=action, entity=entity, entity_id=entity_id, detail=detail[:255])
    )


# --------------------------------------------------------------------------- #
# Sugerencias de los jugadores
# --------------------------------------------------------------------------- #
class SuggestionStatus:
    """Estados por los que pasa un mensaje del canal de sugerencias."""

    NEW = "new"
    REVIEWING = "reviewing"
    DONE = "done"

    ALL = (NEW, REVIEWING, DONE)
    LABELS = {NEW: "Nueva", REVIEWING: "En estudio", DONE: "Aplicada"}


#: Categorias ofrecidas en el formulario de sugerencias.
SUGGESTION_CATEGORIES = {
    "idea": "Idea nueva",
    "mejora": "Mejora de la pagina",
    "liga": "Liga y reglamento",
    "error": "Algo no funciona",
    "otro": "Otro",
}


class Suggestion(TimestampMixin, db.Model):
    """Mensajes del foro de sugerencias: quien lo escribe y que dice."""
    __tablename__ = "suggestions"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"),
                        nullable=False, index=True)
    category = db.Column(db.String(30), nullable=False, default="idea", index=True)
    title = db.Column(db.String(120), nullable=False)
    body = db.Column(db.Text, nullable=False)
    status = db.Column(db.String(16), nullable=False, default=SuggestionStatus.NEW, index=True)
    staff_reply = db.Column(db.Text)
    replied_at = db.Column(db.DateTime)
    replied_by_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="SET NULL"),
                              nullable=True)
    likes = db.Column(db.Integer, nullable=False, default=0)

    author = db.relationship("User", foreign_keys=[user_id], lazy="joined")
    staff = db.relationship("User", foreign_keys=[replied_by_id], lazy="joined")

    __table_args__ = (
        CheckConstraint("status in ('new','reviewing','done')", name="suggestion_status_valid"),
        Index("ix_suggestions_created_status", "created_at", "status"),
    )

    @property
    def status_label(self) -> str:
        return SuggestionStatus.LABELS.get(self.status, self.status)

    @property
    def author_label(self) -> str:
        return self.author.label if self.author else "Jugador eliminado"

    @property
    def category_label(self) -> str:
        return SUGGESTION_CATEGORIES.get(self.category, self.category)

    @property
    def excerpt(self) -> str:
        clean = " ".join((self.body or "").split())
        return clean[:180] + ("..." if len(clean) > 180 else "")

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Suggestion #{self.id} {self.category} by user {self.user_id} {self.status}>"


class SuggestionVote(TimestampMixin, db.Model):
    """Un voto por usuario y sugerencia: el contador nunca se infla solo."""
    __tablename__ = "suggestion_votes"

    id = db.Column(db.Integer, primary_key=True)
    suggestion_id = db.Column(db.Integer, db.ForeignKey("suggestions.id", ondelete="CASCADE"),
                              nullable=False, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"),
                        nullable=False, index=True)

    suggestion = db.relationship("Suggestion", lazy="joined")
    user = db.relationship("User", lazy="joined")

    __table_args__ = (
        UniqueConstraint("suggestion_id", "user_id", name="uq_suggestion_vote"),
    )

    def __repr__(self) -> str:  # pragma: no cover
        return f"<SuggestionVote s={self.suggestion_id} u={self.user_id}>"


def setting(key: str, default: str = "") -> str:
    row = SiteSetting.query.filter_by(key=key).first()
    return row.value if row and row.value is not None else default


def set_setting(key: str, value: str, group: str = "general", label: str = "", input_type: str = "text") -> SiteSetting:
    row = SiteSetting.query.filter_by(key=key).first()
    if row is None:
        row = SiteSetting(key=key, value=value, group=group, label=label or key, input_type=input_type)
        db.session.add(row)
    else:
        row.value = value
    return row


def current_season() -> Season | None:
    return Season.query.filter_by(is_current=True).first() or Season.query.order_by(Season.number.desc()).first()


# --------------------------------------------------------------------------- #
# Estadisticas de jugadores
# --------------------------------------------------------------------------- #
def recompute_player_stats() -> int:
    """Recalcula los acumulados de Player desde player_match_stats.

    Devuelve cuantos jugadores quedaron actualizados.
    """
    rows = (
        db.session.query(
            PlayerMatchStat.player_id,
            func.count(func.distinct(PlayerMatchStat.match_id)),
            func.sum(PlayerMatchStat.goals),
            func.sum(PlayerMatchStat.assists),
            func.sum(PlayerMatchStat.clean_sheets),
            func.sum(PlayerMatchStat.clean_sheet_seconds),
            func.sum(PlayerMatchStat.own_goals),
            func.sum(PlayerMatchStat.yellow_cards),
            func.sum(PlayerMatchStat.red_cards),
        )
        .group_by(PlayerMatchStat.player_id)
        .all()
    )

    totals = {row[0]: row[1:] for row in rows}
    updated = 0
    for player in Player.query.all():
        data = totals.get(player.id)
        if data is None:
            player.matches = 0
            player.goals = 0
            player.assists = 0
            player.clean_sheets = 0
            player.clean_sheet_seconds = 0
            player.own_goals = 0
            player.yellow_cards = 0
            player.red_cards = 0
        else:
            (player.matches, player.goals, player.assists, player.clean_sheets,
             player.clean_sheet_seconds, player.own_goals,
             player.yellow_cards, player.red_cards) = [int(v or 0) for v in data]
        updated += 1
    db.session.commit()
    return updated


def player_stat_rows(
    division_id: int | None = None,
    limit: int | None = None,
    season_id: int | None = None,
) -> list[Player]:
    """Tabla de estadisticas: jugadores con alguna aportacion, mejor primero."""
    query = Player.query.filter(db.or_(Player.goals > 0, Player.assists > 0, Player.clean_sheets > 0,
                                        Player.matches > 0))
    if division_id or season_id:
        query = query.join(Team, Player.team_id == Team.id)
        if division_id:
            query = query.filter(Team.division_id == division_id)
        if season_id:
            query = query.join(Division, Team.division_id == Division.id) \
                         .filter(Division.season_id == season_id)
    query = query.order_by(
        (Player.goals * 2 + Player.assists).desc(),
        Player.clean_sheets.desc(),
        Player.goals.desc(),
        Player.username,
    )
    return query.limit(limit).all() if limit else query.all()


def division_standings(division_id: int) -> list[Standing]:
    rows = (
        Standing.query.filter_by(division_id=division_id)
        .join(Team, Standing.team_id == Team.id)
        .order_by(Standing.points.desc(), (Standing.goals_for - Standing.goals_against).desc(), Team.name)
        .all()
    )
    for index, row in enumerate(rows, start=1):
        row.position = index
    return rows


def seasons_with_divisions() -> list:
    return Season.query.order_by(Season.number.desc()).all()


def is_visible(item, now: datetime | None = None) -> bool:
    return bool(getattr(item, "is_live_now", True))


__all__ = [
    "User", "Role", "Season", "Division", "Phase", "DivisionRule", "PromotionSlot", "Team", "Player",
    "Standing", "Match", "MatchReport", "PlayerMatchStat", "PasswordResetToken", "EmailLog",
    "Room", "Category", "Article", "MuseumItem", "Alliance", "SocialLink",
    "StaffMember", "RuleEntry", "SanctionLevel", "LiveStream", "DonationChannel", "Donation",
    "DonationGoal", "SiteSetting", "ActivityLog", "log_activity", "setting", "set_setting",
    "Suggestion", "SuggestionStatus", "SUGGESTION_CATEGORIES", "SuggestionVote",
    "current_season", "seasons_with_divisions", "recompute_player_stats", "player_stat_rows",
    "division_standings", "date", "db", "utcnow",
]
