"""Modelos de datos de The Diamonds League.

Un solo conjunto de modelos sirve para SQLite (desarrollo local) y para
PostgreSQL serverless de Vercel (produccion): solo cambia DATABASE_URL.

El esquema tiene 19 tablas. Las que eran casi duplicadas se fusionaron:

- ``seasons`` + ``divisions``        -> ``divisions``
- ``phases`` + ``division_rules`` + ``promotion_slots`` -> ``division_notes``
- ``alliances`` + ``social_links`` + ``donation_channels`` -> ``links``
- ``rule_entries`` + ``sanction_levels`` -> ``regulation``
- ``staff_members``                   -> columnas de staff en ``users``
- ``email_logs`` + ``activity_logs``  -> ``logs``
- ``standings``                       -> se calcula en memoria (ver ``division_standings``)
- ``suggestion_votes``                -> columna ``voted_by`` en ``suggestions``
- ``donation_goals``                  -> claves en ``settings`` (ver ``donation_goal``)
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from typing import Optional

from flask_login import AnonymousUserMixin, UserMixin
from sqlalchemy import CheckConstraint, Index, UniqueConstraint, func

from extensions import db, login_manager
from utils import hash_password, slugify, utcnow, verify_password

#: Paleta de la liga. ``static/css/style.css`` la replica en variables CSS y el
#: seed la usa para los colores de escudos y enlaces.
PALETTE = {
    "bg": "#0046E3",         # azul fondo
    "secondary": "#00F3FF",  # cian
    "accent": "#D8FF00",     # lima
    "text": "#FFFFFF",       # blanco
}
#: Los tres colores que se repiten en escudos y enlaces.
TEAM_COLORS = (PALETTE["secondary"], PALETTE["accent"], PALETTE["bg"], PALETTE["text"])


# --------------------------------------------------------------------------- #
# Mezclas
# --------------------------------------------------------------------------- #
class TimestampMixin:
    created_at = db.Column(db.DateTime, default=utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=utcnow, onupdate=utcnow, nullable=False)


class ImageMixin:
    """Imagen opcional de un registro, por URL externa o por archivo local.

    En Vercel el disco es efimero, asi que ahi se usa siempre ``image_url``
    (Cloudinary, imgur, GitHub...). En local se puede subir el archivo y queda
    en ``image``. Las plantillas usan ``picture`` / ``has_image`` y el filtro
    ``media`` de Jinja, que ya resuelve las dos formas.
    """

    image = db.Column(db.String(255))
    image_url = db.Column(db.String(500))

    @property
    def picture(self) -> str | None:
        return self.image_url or self.image

    @property
    def has_image(self) -> bool:
        return bool(self.picture)

    def set_picture(self, path: str | None, url: str | None) -> None:
        """Guarda la imagen local y la externa de una vez."""
        self.image = path
        self.image_url = url


# --------------------------------------------------------------------------- #
# Usuarios (cuentas de acceso y equipo de administracion)
# --------------------------------------------------------------------------- #
class Role:
    ADMIN = "admin"
    STAFF = "staff"
    USER = "user"

    ALL = (ADMIN, STAFF, USER)
    LABELS = {ADMIN: "Administrador", STAFF: "Staff", USER: "Jugador"}
    #: Los que aparecen en la seccion EQUIPO de la pagina publica.
    TEAM = (ADMIN, STAFF)


class User(UserMixin, TimestampMixin, ImageMixin, db.Model):
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
    google_email = db.Column(db.String(160))
    country = db.Column(db.String(60))

    last_login = db.Column(db.DateTime)
    login_count = db.Column(db.Integer, nullable=False, default=0)

    # --- Ficha publica del staff (seccion EQUIPO) ---
    title = db.Column(db.String(80))
    tags = db.Column(db.String(160))
    discord = db.Column(db.String(80))
    banner = db.Column(db.String(255))
    banner_url = db.Column(db.String(500))
    is_leader = db.Column(db.Boolean, nullable=False, default=False, index=True)
    is_public = db.Column(db.Boolean, nullable=False, default=False, index=True)
    sort_order = db.Column(db.Integer, nullable=False, default=100)

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
        return self.picture or "img/logo-mark.png"

    @avatar_url.setter
    def avatar_url(self, value: str | None) -> None:
        """Los formularios asignan aqui la URL externa del avatar."""
        self.image_url = (value or "").strip() or None

    @property
    def banner_picture(self) -> str | None:
        return self.banner_url or self.banner

    @property
    def tag_list(self) -> list[str]:
        return [t.strip() for t in (self.tags or "").split(",") if t.strip()]

    @property
    def nickname(self) -> str | None:
        return self.username

    @property
    def is_in_public_team(self) -> bool:
        return self.is_active_account and self.is_public and self.role in Role.TEAM

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


class PasswordResetToken(TimestampMixin, db.Model):
    """Token de un solo uso para restablecer la contrasena por correo."""

    __tablename__ = "password_reset_tokens"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"),
                        nullable=False, index=True)
    token_hash = db.Column(db.String(128), nullable=False, unique=True, index=True)
    expires_at = db.Column(db.DateTime, nullable=False, index=True)
    used_at = db.Column(db.DateTime)

    user = db.relationship("User", lazy="joined")

    @property
    def is_usable(self) -> bool:
        return self.used_at is None and self.expires_at > utcnow()

    def __repr__(self) -> str:  # pragma: no cover
        return f"<PasswordResetToken user={self.user_id}>"


# --------------------------------------------------------------------------- #
# Ajustes del sitio (clave/valor) y registro unificado de actividad y correos
# --------------------------------------------------------------------------- #
class Setting(TimestampMixin, db.Model):
    """Configuracion editable de la web: textos, metas de donacion, banderas."""

    __tablename__ = "settings"

    id = db.Column(db.Integer, primary_key=True)
    key = db.Column(db.String(60), unique=True, nullable=False, index=True)
    value = db.Column(db.Text)
    group = db.Column(db.String(40), nullable=False, default="general")
    label = db.Column(db.String(80))
    input_type = db.Column(db.String(16), default="text")

    def as_bool(self) -> bool:
        return str(self.value).strip().lower() in {"1", "true", "yes", "on", "si"}

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Setting {self.key}={self.value}>"


class LogKind:
    """Lo que se guarda en la tabla unificada ``logs``."""

    ACTIVITY = "activity"
    EMAIL = "email"

    ALL = (ACTIVITY, EMAIL)


class Log(TimestampMixin, db.Model):
    """Auditoria del panel y historial de correos, en una sola tabla."""

    __tablename__ = "logs"

    id = db.Column(db.Integer, primary_key=True)
    kind = db.Column(db.String(12), nullable=False, default=LogKind.ACTIVITY, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="SET NULL"),
                        nullable=True, index=True)
    action = db.Column(db.String(40), index=True)
    entity = db.Column(db.String(40))
    entity_id = db.Column(db.Integer)
    detail = db.Column(db.String(255))

    # Solo para kind='email'
    to_email = db.Column(db.String(160), index=True)
    subject = db.Column(db.String(180))
    template = db.Column(db.String(40), index=True)
    status = db.Column(db.String(16), index=True)  # sent | failed | skipped
    error = db.Column(db.String(255))

    user = db.relationship("User", lazy="joined")

    __table_args__ = (
        CheckConstraint("kind in ('activity','email')", name="log_kind_valid"),
    )

    @property
    def status_label(self) -> str:
        return {"sent": "Enviado", "failed": "Fallido", "skipped": "Omitido"}.get(
            self.status, self.status or ""
        )

    @property
    def action_label(self) -> str:
        return {"crear": "Creo", "editar": "Edito", "eliminar": "Elimino",
                "login": "Entro", "logout": "Salio"}.get(self.action or "", (self.action or "").title())

    @property
    def target(self) -> str:
        if self.kind == LogKind.EMAIL:
            return self.user.label if self.user else (self.to_email or "-")
        return self.user.label if self.user else "Sistema"

    @property
    def summary(self) -> str:
        if self.kind == LogKind.EMAIL:
            return self.subject or ""
        entity = self.entity or ""
        if self.entity_id:
            entity += f" #{self.entity_id}"
        return (self.detail or entity or "").strip()

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Log {self.kind}:{self.action or self.template}>"


def log_activity(user, action: str, entity: str, entity_id: int | None = None, detail: str = "") -> None:
    db.session.add(Log(user_id=getattr(user, "id", None), kind=LogKind.ACTIVITY,
                       action=action, entity=entity, entity_id=entity_id, detail=detail[:255]))


# --------------------------------------------------------------------------- #
# Competicion: division (con su temporada), notas, equipos y jugadores
# --------------------------------------------------------------------------- #
class Division(TimestampMixin, db.Model):
    """Una division de la liga. La temporada viaja dentro de la propia fila."""

    __tablename__ = "divisions"

    id = db.Column(db.Integer, primary_key=True)
    season_number = db.Column(db.Integer, nullable=False, default=1, index=True)
    season_name = db.Column(db.String(60), nullable=False, default="Temporada")
    season_year = db.Column(db.String(12))
    is_current = db.Column(db.Boolean, nullable=False, default=True, index=True)
    starts_on = db.Column(db.Date)
    ends_on = db.Column(db.Date)
    is_registration_open = db.Column(db.Boolean, nullable=False, default=False)

    key = db.Column(db.String(40), unique=True, nullable=False)   # division-one
    name = db.Column(db.String(80), nullable=False)                # "Division 1"
    short = db.Column(db.String(8), nullable=False)                # "D1"
    level = db.Column(db.Integer, nullable=False, default=1)

    teams_count = db.Column(db.Integer, nullable=False, default=0)
    journeys_count = db.Column(db.Integer, nullable=False, default=0)

    modality = db.Column(db.String(60), default="5 VS 5 · X5")
    duration = db.Column(db.String(80), default="Dos tiempos de 10:00 + ultima jugada")
    map_name = db.Column(db.String(80), default="5v5 Diamonds League")
    server = db.Column(db.String(60), default="X Hosting")
    description = db.Column(db.Text)
    schedule_note = db.Column(db.String(200))

    notes = db.relationship("DivisionNote", back_populates="division", cascade="all, delete-orphan",
                            order_by="DivisionNote.position", lazy="selectin")
    teams = db.relationship("Team", back_populates="division", lazy="selectin")

    __table_args__ = (
        UniqueConstraint("season_number", "name", name="uq_division_season_name"),
    )

    @property
    def season_label(self) -> str:
        return f"Temporada {self.season_number}"

    @property
    def label(self) -> str:
        return f"{self.short} · {self.name}"

    @property
    def phases(self) -> list["DivisionNote"]:
        return [n for n in self.notes if n.scope == DivisionNote.PHASE]

    @property
    def base_rules(self) -> list["DivisionNote"]:
        return [n for n in self.notes if n.scope == DivisionNote.RULE]

    @property
    def moves(self) -> list["DivisionNote"]:
        return [n for n in self.notes if n.scope in (DivisionNote.PROMOTION, DivisionNote.RELEGATION)]

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Division {self.name} T{self.season_number}>"


class DivisionNote(TimestampMixin, db.Model):
    """Fases, reglas y ascensos/descensos de una division, en una sola tabla."""

    __tablename__ = "division_notes"

    PHASE = "fase"
    RULE = "regla"
    PROMOTION = "ascenso"
    RELEGATION = "descenso"

    SCOPES = (PHASE, RULE, PROMOTION, RELEGATION)
    SCOPE_LABELS = {PHASE: "Fases", RULE: "Reglas", PROMOTION: "Ascensos", RELEGATION: "Descensos"}

    id = db.Column(db.Integer, primary_key=True)
    division_id = db.Column(db.Integer, db.ForeignKey("divisions.id", ondelete="CASCADE"),
                            nullable=False, index=True)
    scope = db.Column(db.String(12), nullable=False, default=PHASE, index=True)
    position = db.Column(db.Integer, nullable=False, default=1)
    tag = db.Column(db.String(40))
    title = db.Column(db.String(90), nullable=False)
    body = db.Column(db.Text)
    highlight = db.Column(db.String(255))

    division = db.relationship("Division", back_populates="notes")

    __table_args__ = (
        CheckConstraint("scope in ('fase','regla','ascenso','descenso')", name="scope_valid"),
    )

    def __repr__(self) -> str:  # pragma: no cover
        return f"<DivisionNote {self.scope}:{self.title}>"


class Team(TimestampMixin, ImageMixin, db.Model):
    __tablename__ = "teams"

    id = db.Column(db.Integer, primary_key=True)
    division_id = db.Column(db.Integer, db.ForeignKey("divisions.id", ondelete="SET NULL"),
                            nullable=True, index=True)
    name = db.Column(db.String(80), nullable=False, unique=True)
    short = db.Column(db.String(20), nullable=False, default="")
    slug = db.Column(db.String(90), unique=True, nullable=False, index=True)
    coach = db.Column(db.String(60))
    captain = db.Column(db.String(60))
    country = db.Column(db.String(60))
    is_active = db.Column(db.Boolean, nullable=False, default=True, index=True)
    sort_order = db.Column(db.Integer, nullable=False, default=100)
    description = db.Column(db.Text)
    color = db.Column(db.String(16), default="#00F3FF")

    division = db.relationship("Division", back_populates="teams")
    players = db.relationship("Player", back_populates="team", cascade="all, delete-orphan",
                              order_by="Player.number", lazy="selectin")

    def __init__(self, **kwargs):
        kwargs.setdefault("slug", slugify(kwargs.get("name", "equipo")))
        super().__init__(**kwargs)

    @property
    def initials(self) -> str:
        """Siglas del escudo: 'Los Diamonds' -> LD, 'RFC' -> RF."""
        words = [w for w in (self.short or self.name).split() if w]
        if len(words) > 1:
            return "".join(w[:1] for w in words[:2]).upper()
        return (words[0][:2] if words else "EQ").upper()

    @property
    def player_count(self) -> int:
        return len([p for p in self.players if p.is_active])

    @property
    def squad_size(self) -> int:
        return len(self.players or [])

    @property
    def totals(self) -> dict:
        """Suma de la liga para el equipo (goles, asistencias, CS, tarjetas)."""
        rows = {"goals": 0, "assists": 0, "clean_sheets": 0, "own_goals": 0,
                "yellow_cards": 0, "red_cards": 0, "minutes": 0, "matches": 0}
        for stat in self.match_stats or []:
            rows["goals"] += stat.goals or 0
            rows["assists"] += stat.assists or 0
            rows["clean_sheets"] += stat.clean_sheets or 0
            rows["own_goals"] += stat.own_goals or 0
            rows["yellow_cards"] += stat.yellow_cards or 0
            rows["red_cards"] += stat.red_cards or 0
            rows["minutes"] += stat.minutes or 0
        rows["matches"] = len({s.match_id for s in (self.match_stats or [])})
        return rows

    match_stats = db.relationship("MatchStat", back_populates="team", cascade="all, delete-orphan",
                                  lazy="selectin")

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Team {self.name}>"


class Player(TimestampMixin, db.Model):
    __tablename__ = "players"

    id = db.Column(db.Integer, primary_key=True)
    team_id = db.Column(db.Integer, db.ForeignKey("teams.id", ondelete="CASCADE"),
                        nullable=False, index=True)
    username = db.Column(db.String(60), nullable=False)
    haxball_id = db.Column(db.String(40))
    position = db.Column(db.String(24), default="MF")
    number = db.Column(db.Integer, default=0)
    country = db.Column(db.String(60))
    is_captain = db.Column(db.Boolean, nullable=False, default=False)
    is_active = db.Column(db.Boolean, nullable=False, default=True, index=True)

    # Acumulados que se recalculan desde ``match_stats``.
    matches = db.Column(db.Integer, nullable=False, default=0)
    goals = db.Column(db.Integer, nullable=False, default=0)
    assists = db.Column(db.Integer, nullable=False, default=0)
    clean_sheets = db.Column(db.Integer, nullable=False, default=0)
    own_goals = db.Column(db.Integer, nullable=False, default=0)
    yellow_cards = db.Column(db.Integer, nullable=False, default=0)
    red_cards = db.Column(db.Integer, nullable=False, default=0)
    minutes = db.Column(db.Integer, nullable=False, default=0)

    team = db.relationship("Team", back_populates="players")
    match_stats = db.relationship("MatchStat", back_populates="player",
                                  cascade="all, delete-orphan", lazy="selectin")

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


# --------------------------------------------------------------------------- #
# Partidos, informes y estadisticas
# --------------------------------------------------------------------------- #
class Match(TimestampMixin, db.Model):
    __tablename__ = "matches"

    SCHEDULED = "scheduled"
    LIVE = "live"
    FINISHED = "finished"
    WALKOVER = "wo"
    POSTPONED = "postponed"

    STATUSES = (SCHEDULED, LIVE, FINISHED, WALKOVER, POSTPONED)
    STATUS_LABELS = {SCHEDULED: "Programado", LIVE: "En vivo", FINISHED: "Finalizado",
                     WALKOVER: "Walkover", POSTPONED: "Aplazado"}

    id = db.Column(db.Integer, primary_key=True)
    division_id = db.Column(db.Integer, db.ForeignKey("divisions.id", ondelete="CASCADE"),
                            nullable=False, index=True)
    journey = db.Column(db.Integer, nullable=False, default=1, index=True)
    stage = db.Column(db.String(40), nullable=False, default="Liga regular")
    played_on = db.Column(db.Date, index=True)
    kickoff = db.Column(db.String(5), default="19:00")

    home_team_id = db.Column(db.Integer, db.ForeignKey("teams.id", ondelete="CASCADE"),
                             nullable=False, index=True)
    away_team_id = db.Column(db.Integer, db.ForeignKey("teams.id", ondelete="CASCADE"),
                             nullable=False, index=True)

    home_score = db.Column(db.Integer)
    away_score = db.Column(db.Integer)
    status = db.Column(db.String(16), nullable=False, default=SCHEDULED, index=True)
    room_url = db.Column(db.String(255))
    replay_url = db.Column(db.String(255))
    notes = db.Column(db.Text)

    home_team = db.relationship("Team", foreign_keys=[home_team_id], lazy="joined")
    away_team = db.relationship("Team", foreign_keys=[away_team_id], lazy="joined")
    division = db.relationship("Division", lazy="joined")

    report = db.relationship("MatchReport", back_populates="match", uselist=False,
                             cascade="all, delete-orphan", lazy="selectin")
    player_stats = db.relationship("MatchStat", back_populates="match",
                                   cascade="all, delete-orphan", lazy="selectin",
                                   order_by="MatchStat.goals.desc(), MatchStat.player_id")

    __table_args__ = (
        Index("ix_match_division_journey", "division_id", "journey"),
        CheckConstraint("status in ('scheduled','live','finished','wo','postponed')", name="status_valid"),
    )

    # -- Resultado --------------------------------------------------------- #
    @property
    def is_finished(self) -> bool:
        return self.status == Match.FINISHED

    @property
    def status_label(self) -> str:
        return self.STATUS_LABELS.get(self.status, self.status)

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
        if not self.is_finished or self.home_score is None or self.away_score is None:
            return None
        mine, theirs = ((self.home_score, self.away_score) if self.home_team_id == team_id
                        else (self.away_score, self.home_score))
        if mine > theirs:
            return "W"
        return "D" if mine == theirs else "L"

    # -- Estadisticas e informe -------------------------------------------- #
    @property
    def roster(self) -> list[Player]:
        players = []
        if self.home_team:
            players += [p for p in self.home_team.players if p.is_active]
        if self.away_team:
            players += [p for p in self.away_team.players if p.is_active]
        return players

    def stats_for(self, team_id: int) -> list["MatchStat"]:
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
        return self._goals_for(self.home_team_id)

    @property
    def away_goals_from_stats(self) -> int:
        return self._goals_for(self.away_team_id)

    @property
    def scorers(self) -> list["MatchStat"]:
        return [s for s in (self.player_stats or []) if s.goals or s.own_goals]

    def sync_score_from_stats(self) -> bool:
        """Pasa el marcador a la suma de las fichas. Devuelve True si cambio."""
        if not self.player_stats:
            return False
        home, away = self.home_goals_from_stats, self.away_goals_from_stats
        if (self.home_score, self.away_score) == (home, away):
            return False
        self.home_score, self.away_score = home, away
        if self.status in (Match.SCHEDULED, Match.LIVE):
            self.status = Match.FINISHED
        return True

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Match J{self.journey} {self.home_team_id} vs {self.away_team_id}>"


class MatchReport(TimestampMixin, ImageMixin, db.Model):
    """Informe de un partido: foto, resultado y lectura del juego. Es 1:1 con Match."""

    __tablename__ = "match_reports"

    id = db.Column(db.Integer, primary_key=True)
    match_id = db.Column(db.Integer, db.ForeignKey("matches.id", ondelete="CASCADE"),
                         nullable=False, unique=True, index=True)

    photo_credit = db.Column(db.String(120))
    headline = db.Column(db.String(180))
    summary = db.Column(db.String(400))
    body = db.Column(db.Text)
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
        return bool(self.picture or self.headline or self.summary or self.body)

    @property
    def author_label(self) -> str:
        return self.author.label if self.author else "Redaccion de la liga"

    @property
    def stats(self) -> list["MatchStat"]:
        return list(self.match.player_stats or []) if self.match else []

    def __repr__(self) -> str:  # pragma: no cover
        return f"<MatchReport match={self.match_id}>"


class MatchStat(TimestampMixin, db.Model):
    """Estadistica individual de UN jugador en UN partido.

    Es la fuente de verdad de goles, asistencias, clean sheets y tarjetas;
    `Player.goals` etc. son el acumulado que se recalcula desde aqui.
    """

    __tablename__ = "match_stats"

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
    def contribution(self) -> int:
        """Goles x2 + asistencias: metrica para ordenar las contribuciones."""
        return (self.goals or 0) * 2 + (self.assists or 0)

    def __repr__(self) -> str:  # pragma: no cover
        return f"<MatchStat p{self.player_id} m{self.match_id} g{self.goals}>"


# --------------------------------------------------------------------------- #
# Contenido editorial y comunidad
# --------------------------------------------------------------------------- #
class Room(TimestampMixin, ImageMixin, db.Model):
    """Salas publicas de HaxBall."""

    __tablename__ = "rooms"

    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(12), nullable=False)          # "01"
    name = db.Column(db.String(80), nullable=False, default="DIAMONDS PUBLIC")
    url = db.Column(db.String(255), nullable=False)           # link de HaxBall
    region = db.Column(db.String(40), default="Latam")
    max_players = db.Column(db.Integer, nullable=False, default=12)
    mode = db.Column(db.String(40), default="5 VS 5")
    map_name = db.Column(db.String(80), default="5v5 Diamonds League")
    password = db.Column(db.String(60))
    description = db.Column(db.String(255))
    is_open = db.Column(db.Boolean, nullable=False, default=True, index=True)
    is_featured = db.Column(db.Boolean, nullable=False, default=False)
    sort_order = db.Column(db.Integer, nullable=False, default=100)

    __table_args__ = (UniqueConstraint("code", name="uq_room_code"),)

    @property
    def display_code(self) -> str:
        return f"ROOM {self.code}"

    @property
    def is_locked(self) -> bool:
        return not self.is_open

    @property
    def mode_label(self) -> str:
        return self.mode or "5 VS 5"

    @property
    def ping_label(self) -> str:
        return self.region or "Latam"

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Room {self.code}>"


class Category:
    """Tipos de articulo editorial. Los valores deben coincidir con el
    CheckConstraint de la tabla ``articles``."""

    NEWS = "news"
    ANNOUNCEMENT = "announcement"
    REPORT = "report"

    ALL = (NEWS, ANNOUNCEMENT, REPORT)
    LABELS = {NEWS: "Noticia", ANNOUNCEMENT: "Anuncio", REPORT: "Informe"}
    #: Etiqueta que usa el panel para el boton de alta rapida.
    RESOURCE = {NEWS: "noticias", ANNOUNCEMENT: "avisos", REPORT: "informes"}

    CATEGORIES = ("general", "inscripcion", "premios", "sanciones", "eventos", "sorteos", "entrevista")
    CATEGORY_LABELS = {
        "general": "General", "inscripcion": "Inscripcion", "premios": "Premios",
        "sanciones": "Sanciones", "eventos": "Eventos", "sorteos": "Sorteos",
        "entrevista": "Entrevista",
    }


class Article(TimestampMixin, ImageMixin, db.Model):
    """Noticias, anuncios e informes en un unico recurso editorial."""

    __tablename__ = "articles"

    id = db.Column(db.Integer, primary_key=True)
    kind = db.Column(db.String(20), nullable=False, default=Category.NEWS, index=True)
    category = db.Column(db.String(30), nullable=False, default="general", index=True)
    title = db.Column(db.String(180), nullable=False)
    slug = db.Column(db.String(200), unique=True, nullable=False, index=True)
    summary = db.Column(db.String(400))
    body = db.Column(db.Text)
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
        CheckConstraint("category in ('general','inscripcion','premios','sanciones',"
                        "'eventos','sorteos','entrevista')", name="category_valid"),
        Index("ix_article_kind_published", "kind", "is_published", "published_at"),
    )

    def __init__(self, **kwargs):
        kwargs.setdefault("slug", slugify(kwargs.get("title", "articulo")))
        super().__init__(**kwargs)

    @property
    def kind_label(self) -> str:
        return Category.LABELS.get(self.kind, self.kind)

    @property
    def category_label(self) -> str:
        return Category.CATEGORY_LABELS.get(self.category, (self.category or "").title())

    @property
    def author_label(self) -> str:
        return self.author.label if self.author else "Redaccion de la liga"

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


class MuseumItem(TimestampMixin, ImageMixin, db.Model):
    """Museo de premios: balon, bota, guante, rankings, campeones, trofeos."""

    __tablename__ = "museum_items"

    CATEGORIES = ("premios", "rankings", "campeones", "trofeos")
    CATEGORY_LABELS = {
        "premios": "Premios", "rankings": "Rankings", "campeones": "Campeones", "trofeos": "Trofeos",
    }

    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(140), nullable=False)
    slug = db.Column(db.String(160), unique=True, nullable=False, index=True)
    category = db.Column(db.String(30), nullable=False, default="premios", index=True)
    division_short = db.Column(db.String(8))
    season_number = db.Column(db.Integer)
    recipient = db.Column(db.String(80))
    team_id = db.Column(db.Integer, db.ForeignKey("teams.id", ondelete="SET NULL"), nullable=True)
    description = db.Column(db.String(400))
    place = db.Column(db.Integer, nullable=False, default=0)
    awarded_on = db.Column(db.Date, index=True)
    is_highlight = db.Column(db.Boolean, nullable=False, default=False)
    sort_order = db.Column(db.Integer, nullable=False, default=100)

    team = db.relationship("Team", lazy="joined")

    def __init__(self, **kwargs):
        kwargs.setdefault("slug", slugify(kwargs.get("title", "premio")))
        super().__init__(**kwargs)

    @property
    def category_label(self) -> str:
        return self.CATEGORY_LABELS.get(self.category, (self.category or "").title())

    @property
    def division_label(self) -> str:
        return self.division_short or "LIGA"

    @property
    def initials(self) -> str:
        words = [w for w in (self.title or "D").split() if w]
        return "".join(w[0] for w in words[:2]).upper() or "D"

    @property
    def holder(self) -> str | None:
        return self.recipient or (self.team.name if self.team else None)

    def __repr__(self) -> str:  # pragma: no cover
        return f"<MuseumItem {self.title}>"


class LinkKind:
    """Los tres tipos de enlace que comparten la tabla ``links``."""

    ALLIANCE = "alliance"
    SOCIAL = "social"
    DONATION = "donation"

    ALL = (ALLIANCE, SOCIAL, DONATION)
    LABELS = {ALLIANCE: "Alianza", SOCIAL: "Red social", DONATION: "Metodo de donacion"}


class Link(TimestampMixin, db.Model):
    """Alianzas, redes sociales y metodos de donacion en una sola tabla.

    Que columna significa que depende de ``kind``:

    ============ ========================== ============================
    columna      alliance                   social / donation
    ============ ========================== ============================
``label``    nombre del partner         nombre visible
    ``group``    estado (activa/proxima)    dueño (liga/streamer/equipo)
    ``subkind``  partner / affiliate        plataforma o metodo de pago
    ``tagline``  bajada                     —
    ``body``     descripcion                —
    ``handle``   —                          usuario de la cuenta
    ``account``  —                          alias / cuenta de cobro
    ``code``     codigo de invitacion       —

    ============ ========================== ============================
    """

    __tablename__ = "links"

    id = db.Column(db.Integer, primary_key=True)
    kind = db.Column(db.String(12), nullable=False, default=LinkKind.SOCIAL, index=True)
    label = db.Column(db.String(90), nullable=False)
    group = db.Column(db.String(24), default="liga", index=True)
    subkind = db.Column(db.String(24), index=True)
    tagline = db.Column(db.String(160))
    body = db.Column(db.Text)
    handle = db.Column(db.String(80))
    account = db.Column(db.String(120))
    code = db.Column(db.String(60))
    url = db.Column(db.String(255))
    icon = db.Column(db.String(8), default="#")
    color = db.Column(db.String(16))
    starts_on = db.Column(db.Date, index=True)
    is_active = db.Column(db.Boolean, nullable=False, default=True, index=True)
    is_featured = db.Column(db.Boolean, nullable=False, default=False)
    is_primary = db.Column(db.Boolean, nullable=False, default=False)
    sort_order = db.Column(db.Integer, nullable=False, default=100)

    __table_args__ = (
        CheckConstraint("kind in ('alliance','social','donation')", name="link_kind_valid"),
    )

    ALLIANCE_STATUS = ("activa", "proxima", "pendiente", "cerrada")
    ALLIANCE_STATUS_LABELS = {"activa": "Activa", "proxima": "Proxima afiliacion",
                              "pendiente": "Pendiente", "cerrada": "Cerrada"}
    ALLIANCE_KINDS = ("partner", "affiliate")

    OWNER_LABELS = {"liga": "Liga", "streamer": "Streamers", "equipo": "Equipo"}
    PLATFORM_LABELS = {
        "tiktok": "TikTok", "discord": "Discord", "x": "X", "twitter": "Twitter",
        "instagram": "Instagram", "youtube": "YouTube", "twitch": "Twitch",
        "facebook": "Facebook", "kick": "Kick", "haxball": "HaxBall",
    }
    #: Metodos de pago de los enlaces de tipo `donation` (columna ``subkind``).
    PAYMENT_METHODS = ("paypal", "yape", "binance", "mercadopago", "transferencia", "alias", "otro")
    PAYMENT_LABELS = {
        "paypal": "PayPal", "yape": "Yape", "binance": "Binance Pay",
        "mercadopago": "Mercado Pago", "transferencia": "Transferencia",
        "alias": "Alias bancario", "otro": "Otro",
    }

    @property
    def kind_label(self) -> str:
        return LinkKind.LABELS.get(self.kind, self.kind)

    @property
    def status_label(self) -> str:
        return self.ALLIANCE_STATUS_LABELS.get(self.group or "", (self.group or "").title())

    @property
    def kind_sub_label(self) -> str:
        if self.kind == LinkKind.ALLIANCE:
            return "Afiliacion" if self.subkind == "affiliate" else "Servidor partner"
        if self.kind == LinkKind.DONATION:
            return self.PAYMENT_LABELS.get(self.subkind or "", (self.subkind or "").title())
        return self.PLATFORM_LABELS.get(self.subkind or "", (self.subkind or "").title())

    @property
    def owner_label(self) -> str:
        if self.kind == LinkKind.ALLIANCE:
            return self.kind_sub_label
        return self.OWNER_LABELS.get(self.group or "", (self.group or "").title())

    @property
    def platform(self) -> str:
        return self.subkind or ""

    @property
    def initials(self) -> str:
        words = [w for w in (self.label or "A").split() if w]
        return "".join(w[0] for w in words[:2]).upper() or "A"

    @property
    def method(self) -> str:
        """Como se muestra el metodo: de pago para donaciones, dueno para redes."""
        if self.kind == LinkKind.DONATION:
            return self.kind_sub_label
        return self.group or ""

    @property
    def note(self) -> str | None:
        return self.tagline or None

    @property
    def description(self) -> str | None:
        return self.body or None

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Link {self.kind}:{self.label}>"


class Regulation(TimestampMixin, db.Model):
    """Reglamento general y escala de sanciones en una sola tabla.

    ``scope`` marca de que bloque sale la entrada; ``sanciones`` usa ademas
    ``color`` para el nivel y ``body`` para el listado de faltas.
    """

    __tablename__ = "regulation"

    SCOPES = ("discord", "comunidad", "sanciones")
    SCOPE_LABELS = {"discord": "Discord", "comunidad": "Comunidad", "sanciones": "Sanciones"}

    COLORS = ("general", "yellow", "orange", "red")
    COLOR_LABELS = {"general": "General / informativo", "yellow": "Amarillo (aviso)",
                    "orange": "Naranja", "red": "Rojo (grave)"}

    id = db.Column(db.Integer, primary_key=True)
    scope = db.Column(db.String(30), nullable=False, default="discord", index=True)
    position = db.Column(db.Integer, nullable=False, default=1)
    title = db.Column(db.String(90), nullable=False)
    body = db.Column(db.Text)
    color = db.Column(db.String(20), default="general")
    note = db.Column(db.String(255))

    __table_args__ = (
        CheckConstraint("scope in ('discord','comunidad','sanciones')", name="scope_valid"),
    )

    @property
    def items(self) -> str:
        return self.body or ""

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Regulation {self.scope}:{self.title}>"


class LiveStream(TimestampMixin, ImageMixin, db.Model):
    """Live de futbol real, estilo Kick / Twitch."""

    __tablename__ = "live_streams"

    PLATFORMS = ("twitch", "kick", "youtube", "otro")
    PLATFORM_LABELS = {"twitch": "Twitch", "kick": "Kick", "youtube": "YouTube", "otro": "Otro"}

    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(160), nullable=False)
    platform = db.Column(db.String(20), nullable=False, default="twitch", index=True)
    channel = db.Column(db.String(80))
    embed_url = db.Column(db.String(400))
    watch_url = db.Column(db.String(255), nullable=False)
    league = db.Column(db.String(80))
    competition = db.Column(db.String(80))
    language = db.Column(db.String(20), default="es")
    is_live = db.Column(db.Boolean, nullable=False, default=False, index=True)
    is_featured = db.Column(db.Boolean, nullable=False, default=False)
    viewers = db.Column(db.Integer, nullable=False, default=0)
    scheduled_at = db.Column(db.DateTime)
    sort_order = db.Column(db.Integer, nullable=False, default=100)

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
        return self.PLATFORM_LABELS.get(self.platform, (self.platform or "").title())

    @property
    def is_upcoming(self) -> bool:
        if self.is_live:
            return False
        return bool(self.scheduled_at) and self.scheduled_at > utcnow()

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

    @property
    def chat_url(self) -> str | None:
        return self.embed_url

    def __repr__(self) -> str:  # pragma: no cover
        return f"<LiveStream {self.title}>"


# --------------------------------------------------------------------------- #
# Economia y sugerencias
# --------------------------------------------------------------------------- #
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

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Donation {self.amount}>"


@dataclass
class DonationGoal:
    """Meta de donacion. Vive en ``settings``, no en una tabla propia."""

    title: str
    description: str
    target: float
    raised: float
    link: str = ""

    @property
    def label(self) -> str:
        return self.title

    @property
    def current_amount(self) -> str:
        return f"${self.raised:,.2f}"

    @property
    def target_amount(self) -> str:
        return f"${self.target:,.2f}"

    @property
    def remaining(self) -> float:
        """Cuanto falta para llegar a la meta (0 si ya esta cubierta)."""
        return max(0.0, round(self.target - self.raised, 2))

    @property
    def reached(self) -> bool:
        return self.target > 0 and self.raised >= self.target

    @property
    def percent(self) -> int:
        if self.target <= 0:
            return 0
        return min(100, int(round(self.raised / self.target * 100)))


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
    """Mensajes del foro de sugerencias.

    Los votos no necesitan tabla propia: ``voted_by`` guarda los ids de quien
    voto, separados por comas, asi una persona nunca puede votar dos veces.
    """

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
    replied_by_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    voted_by = db.Column(db.String(1000), default="")

    author = db.relationship("User", foreign_keys=[user_id], lazy="joined")
    staff = db.relationship("User", foreign_keys=[replied_by_id], lazy="joined")

    __table_args__ = (
        CheckConstraint("status in ('new','reviewing','done')", name="suggestion_status_valid"),
        Index("ix_suggestions_created_status", "created_at", "status"),
    )

    # -- Votos ------------------------------------------------------------- #
    @property
    def voters(self) -> list[int]:
        return [int(v) for v in (self.voted_by or "").split(",") if v.strip().isdigit()]

    @property
    def likes(self) -> int:
        return len(self.voters)

    def has_voted(self, user_id: int) -> bool:
        return str(user_id) in (self.voted_by or "").split(",")

    def toggle_vote(self, user_id: int) -> bool:
        """Alterna el voto de `user_id`. Devuelve True si se acaba de sumar."""
        current = [v for v in (self.voted_by or "").split(",") if v]
        token = str(user_id)
        if token in current:
            self.voted_by = ",".join(v for v in current if v != token)
            return False
        current.append(token)
        self.voted_by = ",".join(current)
        return True

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
        return f"<Suggestion #{self.id} {self.category} {self.status}>"


# --------------------------------------------------------------------------- #
# Ajustes: lectura y escritura
# --------------------------------------------------------------------------- #
def setting(key: str, default: str = "") -> str:
    row = Setting.query.filter_by(key=key).first()
    return row.value if row and row.value is not None else default


def set_setting(key: str, value: str, group: str = "general", label: str = "", input_type: str = "text") -> Setting:
    row = Setting.query.filter_by(key=key).first()
    if row is None:
        row = Setting(key=key, value=value, group=group, label=label or key, input_type=input_type)
        db.session.add(row)
    else:
        row.value = value
    return row


def settings_map() -> dict[str, str]:
    return {row.key: row.value for row in Setting.query.all()}


def donation_goal() -> DonationGoal | None:
    """Meta de donacion leida de los ajustes; None si no hay ninguna."""
    title = setting("donation_goal_title", "")
    raw_target = setting("donation_goal_target", "").strip()
    if not title and not raw_target:
        return None
    try:
        target = float(raw_target.replace(",", ".")) if raw_target else 0.0
    except ValueError:
        target = 0.0
    raised = float(db.session.query(func.coalesce(func.sum(Donation.amount), 0)).scalar() or 0)
    return DonationGoal(
        title=title or "Meta de la temporada",
        description=setting("donation_goal_note", ""),
        target=target,
        raised=raised,
        link=setting("donation_goal_link", ""),
    )


def current_division() -> Division | None:
    return (Division.query.filter_by(is_current=True).order_by(Division.level).first()
            or Division.query.order_by(Division.level).first())


# --------------------------------------------------------------------------- #
# Clasificacion: se calcula en memoria a partir de los partidos finalizados
# --------------------------------------------------------------------------- #
@dataclass
class StandingRow:
    """Una fila de la tabla de una division. No es una tabla: se calcula."""

    team: Team
    position: int = 0
    played: int = 0
    won: int = 0
    drawn: int = 0
    lost: int = 0
    goals_for: int = 0
    goals_against: int = 0
    points: int = 0

    @property
    def goal_difference(self) -> int:
        return self.goals_for - self.goals_against


def division_standings(division_id: int) -> list[StandingRow]:
    """Tabla de una division calculada desde los partidos finalizados.

    Evita la tabla ``standings``: no puede desincronizarse del calendario.
    """
    teams = Team.query.filter_by(division_id=division_id).order_by(Team.sort_order, Team.name).all()
    rows = {team.id: StandingRow(team=team) for team in teams}

    played = Match.query.filter_by(division_id=division_id, status=Match.FINISHED).all()
    for match in played:
        home = rows.get(match.home_team_id)
        away = rows.get(match.away_team_id)
        if home is None or away is None or match.home_score is None or match.away_score is None:
            continue
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
        row.played = row.won + row.drawn + row.lost
        row.points = row.won * 3 + row.drawn

    ordered = sorted(rows.values(),
                     key=lambda r: (-r.points, -r.goal_difference, r.team.name or ""))
    for index, row in enumerate(ordered, start=1):
        row.position = index
    return ordered


def team_standing(team_id: int) -> StandingRow | None:
    """Fila de la clasificacion de un equipo concreto."""
    team = db.session.get(Team, team_id)
    if team is None or team.division_id is None:
        return None
    return next((r for r in division_standings(team.division_id) if r.team.id == team_id), None)


def player_stat_rows(division_id: int | None = None, limit: int | None = None) -> list[Player]:
    """Tabla de estadisticas: jugadores con alguna aportacion, mejor primero."""
    query = Player.query.filter(db.or_(Player.goals > 0, Player.assists > 0,
                                        Player.clean_sheets > 0, Player.matches > 0))
    if division_id:
        query = query.join(Team, Player.team_id == Team.id).filter(Team.division_id == division_id)
    query = query.order_by(
        (Player.goals * 2 + Player.assists).desc(),
        Player.clean_sheets.desc(),
        Player.goals.desc(),
        Player.username,
    )
    return query.limit(limit).all() if limit else query.all()


def stat_leaders(division_id: int, column: str, order: str = "desc", limit: int = 10) -> list[Player]:
    """Ranking de una columna dentro de una division."""
    query = (
        Player.query
        .join(Team, Player.team_id == Team.id)
        .filter(Team.division_id == division_id, Player.is_active.is_(True))
    )
    column_attr = getattr(Player, column)
    query = query.order_by(column_attr.desc() if order == "desc" else column_attr.asc())
    return query.limit(limit).all()


def recalculate_player_stats() -> int:
    """Recalcula los acumulados de todos los jugadores desde ``match_stats``."""
    rows = (
        db.session.query(
            MatchStat.player_id,
            func.count(func.distinct(MatchStat.match_id)),
            func.sum(MatchStat.goals),
            func.sum(MatchStat.assists),
            func.sum(MatchStat.clean_sheets),
            func.sum(MatchStat.own_goals),
            func.sum(MatchStat.yellow_cards),
            func.sum(MatchStat.red_cards),
            func.sum(MatchStat.minutes),
        )
        .group_by(MatchStat.player_id)
        .all()
    )
    totals = {row[0]: [int(v or 0) for v in row[1:]] for row in rows}
    fields = ("matches", "goals", "assists", "clean_sheets",
              "own_goals", "yellow_cards", "red_cards", "minutes")

    players = Player.query.all()
    for player in players:
        data = totals.get(player.id, [0] * len(fields))
        for name, value in zip(fields, data):
            setattr(player, name, value)
    db.session.commit()
    return len(players)


__all__ = [
    # nucleo
    "User", "Role", "PasswordResetToken", "Setting", "Log", "LogKind",
    "log_activity", "setting", "set_setting", "settings_map",
    # competicion
    "Division", "DivisionNote", "Team", "Player", "Match", "MatchReport", "MatchStat",
    # contenido
    "Room", "Category", "Article", "MuseumItem", "Link", "LinkKind", "Regulation",
    "LiveStream", "Donation", "DonationGoal", "donation_goal",
    # comunidad
    "Suggestion", "SuggestionStatus", "SUGGESTION_CATEGORIES",
    # calculos
    "StandingRow", "division_standings", "team_standing", "player_stat_rows",
    "stat_leaders", "recalculate_player_stats", "current_division", "PALETTE", "TEAM_COLORS",
    # infra
    "date", "db", "utcnow",
]