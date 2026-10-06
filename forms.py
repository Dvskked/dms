"""Formularios (WTForms + CSRF).

Cada formulario corresponde a un recurso del esquema de 19 tablas. Los campos
de imagen van siempre en pareja: ``*_file`` para subir el archivo en local y
``*_url`` para pegar una URL (necesario en Vercel, donde el disco es efimero).
"""
from __future__ import annotations

from flask_wtf import FlaskForm
from flask_wtf.file import FileAllowed, FileField
from wtforms import (
    BooleanField,
    DateField,
    DateTimeField,
    DecimalField,
    IntegerField,
    PasswordField,
    SelectField,
    StringField,
    SubmitField,
    TextAreaField,
)
from wtforms.validators import DataRequired, Email, EqualTo, Length, NumberRange, Optional, Regexp

from models import (
    Category,
    DivisionNote,
    LinkKind,
    PALETTE,
    Role,
    SUGGESTION_CATEGORIES,
    SuggestionStatus,
)
from utils import USERNAME_RE

IMG_EXT = ["png", "jpg", "jpeg", "webp"]
IMG_EXT_SVG = ["png", "jpg", "jpeg", "webp", "svg"]
POSITIONS = [("GK", "Portero"), ("DF", "Defensa"), ("MF", "Medio"),
             ("MC", "Mediocampo"), ("FW", "Delantero")]


def optional_int(value):
    """Convierte a int sin fallar cuando el SelectField esta vacio."""
    if value in (None, ""):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def hex_color(label: str = "Color") -> StringField:
    """Campo de color con la paleta de la liga como sugerencia."""
    return StringField(label, validators=[Optional(), Length(max=16)],
                       render_kw={"placeholder": PALETTE["secondary"], "list": "paleta-liga"})


# --------------------------------------------------------------------------- #
# Auth
# --------------------------------------------------------------------------- #
class LoginForm(FlaskForm):
    username = StringField(
        "Usuario", validators=[DataRequired("Escribe tu nombre de usuario."), Length(max=24)],
        render_kw={"autocomplete": "username", "autofocus": True, "placeholder": "admin"},
    )
    password = PasswordField(
        "Contrasena", validators=[DataRequired("Escribe tu contrasena.")],
        render_kw={"autocomplete": "current-password", "placeholder": "········"},
    )
    remember = BooleanField("Mantener la sesion abierta")
    submit = SubmitField("INGRESAR")


class RegisterForm(FlaskForm):
    username = StringField(
        "Nombre de usuario",
        validators=[
            DataRequired("El nombre de usuario es obligatorio."),
            Length(min=3, max=24, message="Usa entre 3 y 24 caracteres."),
            Regexp(USERNAME_RE.pattern, message="Solo letras, numeros, punto, guion y guion bajo."),
        ],
        render_kw={"autocomplete": "username", "autofocus": True, "placeholder": "jugador_x5"},
    )
    email = StringField(
        "Correo electronico",
        validators=[DataRequired("El correo es obligatorio."), Email("Correo no valido.")],
        render_kw={"autocomplete": "email", "placeholder": "correo@ejemplo.com"},
    )
    password = PasswordField(
        "Contrasena",
        validators=[DataRequired("La contrasena es obligatoria."), Length(min=6, message="Minimo 6 caracteres.")],
        render_kw={"autocomplete": "new-password", "placeholder": "········"},
    )
    confirm_password = PasswordField(
        "Confirmar contrasena",
        validators=[DataRequired("Repite la contrasena."), EqualTo("password", message="Las contrasenas no coinciden.")],
        render_kw={"autocomplete": "new-password", "placeholder": "········"},
    )
    submit = SubmitField("CREAR CUENTA")


class ProfileForm(FlaskForm):
    display_name = StringField("Nombre para mostrar", validators=[Optional(), Length(max=60)])
    email = StringField("Correo electronico", validators=[Optional(), Email("Correo no valido.")])
    haxball_id = StringField("ID de HaxBall", validators=[Optional(), Length(max=40)])
    country = StringField("Pais", validators=[Optional(), Length(max=60)])
    bio = TextAreaField("Biografia", validators=[Optional(), Length(max=400)])
    avatar = FileField("Subir avatar", validators=[Optional(), FileAllowed(IMG_EXT, "Solo imagenes.")])
    avatar_url = StringField("Avatar por URL", validators=[Optional(), Length(max=500)],
                             render_kw={"placeholder": "https://.../avatar.png"})
    remove_avatar = BooleanField("Quitar el avatar actual")
    submit = SubmitField("GUARDAR CAMBIOS")


class ChangePasswordForm(FlaskForm):
    current_password = PasswordField("Contrasena actual", validators=[DataRequired("Escribe tu contrasena actual.")])
    new_password = PasswordField("Nueva contrasena", validators=[DataRequired(), Length(min=6, message="Minimo 6 caracteres.")])
    confirm_password = PasswordField(
        "Confirmar nueva contrasena",
        validators=[DataRequired(), EqualTo("new_password", message="Las contrasenas no coinciden.")],
    )
    submit = SubmitField("ACTUALIZAR CONTRASENA")


class ForgotPasswordForm(FlaskForm):
    """Solicita el enlace de restablecimiento; el campo acepta usuario o correo."""
    identifier = StringField(
        "Usuario o correo electronico",
        validators=[DataRequired("Escribe tu usuario o tu correo."), Length(max=160)],
        render_kw={"autocomplete": "username", "autofocus": True, "placeholder": "jugador_x5"},
    )
    submit = SubmitField("ENVIAR ENLACE")


class ResetPasswordForm(FlaskForm):
    new_password = PasswordField(
        "Nueva contrasena", validators=[DataRequired(), Length(min=6, message="Minimo 6 caracteres.")],
        render_kw={"autocomplete": "new-password", "placeholder": "········"},
    )
    confirm_password = PasswordField(
        "Confirmar contrasena",
        validators=[DataRequired(), EqualTo("new_password", message="Las contrasenas no coinciden.")],
        render_kw={"autocomplete": "new-password", "placeholder": "········"},
    )
    submit = SubmitField("GUARDAR NUEVA CONTRASENA")


class GoogleLinkForm(FlaskForm):
    """Vinculacion manual de la cuenta de Google (el hook de OAuth va aparte)."""
    google_email = StringField(
        "Correo de Google", validators=[DataRequired(), Email("Correo no valido.")],
        render_kw={"placeholder": "tu.cuenta@gmail.com"},
    )
    submit = SubmitField("VINCULAR CUENTA")


# --------------------------------------------------------------------------- #
# Sugerencias (canal de la comunidad)
# --------------------------------------------------------------------------- #
class SuggestionForm(FlaskForm):
    """Mensaje del canal de sugerencias (solo para quien ya entro con su cuenta)."""

    category = SelectField(
        "Tipo de mensaje",
        choices=[(key, label) for key, label in SUGGESTION_CATEGORIES.items()],
        validators=[DataRequired("Elige de que tipo es tu mensaje.")],
    )
    title = StringField(
        "Titulo",
        validators=[DataRequired("Escribe un titulo corto."), Length(max=120, message="Maximo 120 caracteres.")],
        render_kw={"placeholder": "Que quieres cambiar de la pagina", "maxlength": "120"},
    )
    body = TextAreaField(
        "Comentario",
        validators=[DataRequired("Escribe tu comentario."), Length(min=10, message="Cuenta un poco mas.")],
        render_kw={"placeholder": "Explica tu idea, el error o lo que mejoraria.", "rows": "5"},
    )
    submit = SubmitField("ENVIAR SUGERENCIA")


class SuggestionReplyForm(FlaskForm):
    """Respuesta del staff en el hilo de sugerencias."""

    status = SelectField(
        "Estado",
        choices=[(key, SuggestionStatus.LABELS[key]) for key in SuggestionStatus.ALL],
        validators=[DataRequired()],
    )
    staff_reply = TextAreaField(
        "Respuesta del staff", validators=[Optional()],
        render_kw={"placeholder": "Contesta al jugador...", "rows": "4"},
    )
    submit = SubmitField("GUARDAR RESPUESTA")


# --------------------------------------------------------------------------- #
# Genericos
# --------------------------------------------------------------------------- #
class BooleanOnlyForm(FlaskForm):
    """Formulario CSRF minimo para acciones POST sin campos."""
    submit = SubmitField("Confirmar")


class SettingForm(FlaskForm):
    value = TextAreaField("Valor", validators=[Optional()])
    submit = SubmitField("GUARDAR")


# --------------------------------------------------------------------------- #
# Competicion: divisiones, notas, equipos, jugadores
# --------------------------------------------------------------------------- #
class DivisionForm(FlaskForm):
    """Division de la liga. La temporada vive en la propia fila."""

    name = StringField("Nombre", validators=[DataRequired(), Length(max=80)])
    key = StringField("Clave", validators=[DataRequired(), Length(max=40)],
                      render_kw={"placeholder": "division-one"})
    short = StringField("Abreviatura", validators=[DataRequired(), Length(max=8)],
                        render_kw={"placeholder": "D1"})
    level = IntegerField("Nivel", validators=[Optional(), NumberRange(1, 9)], default=1)

    season_number = IntegerField("Temporada", validators=[Optional(), NumberRange(1, 99)], default=1)
    season_name = StringField("Nombre de la temporada", validators=[Optional(), Length(max=60)],
                              default="Temporada")
    season_year = StringField("Anio", validators=[Optional(), Length(max=12)],
                              render_kw={"placeholder": "2026"})
    is_current = BooleanField("Es la temporada actual", default=True)
    starts_on = DateField("Empieza", validators=[Optional()])
    ends_on = DateField("Termina", validators=[Optional()])
    is_registration_open = BooleanField("Inscripcion abierta", default=False)

    teams_count = IntegerField("Equipos", validators=[Optional(), NumberRange(0, 64)])
    journeys_count = IntegerField("Jornadas", validators=[Optional(), NumberRange(0, 60)])
    modality = StringField("Modalidad", validators=[Optional(), Length(max=60)])
    duration = StringField("Duracion", validators=[Optional(), Length(max=80)])
    map_name = StringField("Mapa", validators=[Optional(), Length(max=80)])
    server = StringField("Servidor", validators=[Optional(), Length(max=60)])
    description = TextAreaField("Descripcion", validators=[Optional()])
    schedule_note = StringField("Nota de calendario", validators=[Optional(), Length(max=200)])
    submit = SubmitField("GUARDAR")


class DivisionNoteForm(FlaskForm):
    """Fase, regla, ascenso o descenso de una division (tabla ``division_notes``)."""

    division_id = SelectField("Division", coerce=optional_int, choices=[], validators=[DataRequired()])
    scope = SelectField(
        "Tipo", choices=[(key, DivisionNote.SCOPE_LABELS[key]) for key in DivisionNote.SCOPES],
        validators=[DataRequired()], default=DivisionNote.PHASE,
    )
    position = IntegerField("Posicion", validators=[Optional(), NumberRange(1, 999)], default=1)
    tag = StringField("Etiqueta", validators=[Optional(), Length(max=40)],
                      render_kw={"placeholder": "Jornada 1"})
    title = StringField("Titulo", validators=[DataRequired(), Length(max=90)])
    body = TextAreaField("Detalle", validators=[Optional()])
    highlight = StringField("Destacado", validators=[Optional(), Length(max=255)],
                            render_kw={"placeholder": "Debuta la Division 1"})
    submit = SubmitField("GUARDAR")


class TeamForm(FlaskForm):
    name = StringField("Nombre del equipo", validators=[DataRequired(), Length(max=80)])
    short = StringField("Abreviatura", validators=[Optional(), Length(max=20)],
                        render_kw={"placeholder": "LD"})
    division_id = SelectField("Division", coerce=optional_int, choices=[], validators=[Optional()])
    coach = StringField("DT / Entrenador", validators=[Optional(), Length(max=60)])
    captain = StringField("Capitan", validators=[Optional(), Length(max=60)])
    country = StringField("Pais", validators=[Optional(), Length(max=60)])
    crest = FileField("Escudo", validators=[Optional(), FileAllowed(IMG_EXT_SVG, "Solo imagenes.")])
    crest_url = StringField("Escudo por URL", validators=[Optional(), Length(max=500)],
                            render_kw={"placeholder": "https://.../escudo.png"})
    remove_crest = BooleanField("Quitar el escudo actual")
    color = hex_color()
    description = TextAreaField("Descripcion", validators=[Optional()])
    sort_order = IntegerField("Orden", validators=[Optional(), NumberRange(0, 9999)], default=100)
    is_active = BooleanField("Equipo activo", default=True)
    submit = SubmitField("GUARDAR")


class TeamCrestForm(FlaskForm):
    """Subir o cambiar solo el escudo, sin entrar al formulario completo."""
    crest = FileField(
        "Escudo / logo del equipo",
        validators=[Optional(), FileAllowed(IMG_EXT_SVG, "Solo imagenes.")],
    )
    crest_url = StringField("Escudo por URL", validators=[Optional(), Length(max=500)])
    remove_crest = BooleanField("Quitar el escudo actual")
    submit = SubmitField("GUARDAR ESCUDO")


class PlayerForm(FlaskForm):
    team_id = SelectField("Equipo", coerce=optional_int, choices=[],
                          validators=[DataRequired("Selecciona un equipo.")])
    username = StringField("Usuario en HaxBall", validators=[DataRequired(), Length(max=60)])
    haxball_id = StringField("ID de HaxBall", validators=[Optional(), Length(max=40)])
    position = SelectField("Posicion", choices=POSITIONS, validators=[DataRequired()], default="MF")
    number = IntegerField("Numero", validators=[Optional(), NumberRange(0, 99)], default=0)
    country = StringField("Pais", validators=[Optional(), Length(max=60)])
    is_captain = BooleanField("Capitan")
    is_active = BooleanField("Activo en plantilla", default=True)
    submit = SubmitField("GUARDAR")


class RosterPlayerForm(FlaskForm):
    """Alta rapida de varios jugadores dentro de la pantalla de un equipo.

    ``usernames`` admite uno por linea, que es como se rellena la plantilla en
    la practica: pegar la lista y dar a guardar.
    """
    usernames = TextAreaField(
        "Usuarios en HaxBall (uno por linea)",
        validators=[DataRequired("Escribe al menos un usuario."), Length(min=2)],
        render_kw={"rows": "6", "placeholder": "jugador_1\njugador_2\njugador_3"},
    )
    position = SelectField("Posicion (para todos)", choices=POSITIONS,
                           validators=[Optional()], default="MF")
    activate = BooleanField("Marcar como activos", default=True)
    submit = SubmitField("ANADIR A LA PLANTILLA")


# --------------------------------------------------------------------------- #
# Partidos: calendario, informe en un solo formulario y estadisticas
# --------------------------------------------------------------------------- #
class MatchForm(FlaskForm):
    division_id = SelectField("Division", coerce=optional_int, choices=[], validators=[DataRequired()])
    journey = IntegerField("Jornada", validators=[DataRequired(), NumberRange(1, 99)], default=1)
    stage = StringField("Fase", validators=[Optional(), Length(max=40)], default="Liga regular")
    played_on = DateField("Fecha", validators=[Optional()])
    kickoff = StringField("Hora", validators=[Optional(), Length(max=5)], render_kw={"placeholder": "19:00"})
    home_team_id = SelectField("Equipo local", coerce=optional_int, choices=[], validators=[DataRequired()])
    away_team_id = SelectField("Equipo visitante", coerce=optional_int, choices=[], validators=[DataRequired()])
    status = SelectField("Estado", choices=[("scheduled", "Programado"), ("live", "En vivo"),
                                            ("finished", "Finalizado"), ("wo", "Walkover"),
                                            ("postponed", "Aplazado")],
                         validators=[DataRequired()], default="scheduled")
    home_score = IntegerField("Marcador local", validators=[Optional(), NumberRange(0, 99)])
    away_score = IntegerField("Marcador visitante", validators=[Optional(), NumberRange(0, 99)])
    room_url = StringField("Link de la sala", validators=[Optional(), Length(max=255)])
    replay_url = StringField("Link del replay", validators=[Optional(), Length(max=255)])
    notes = TextAreaField("Notas", validators=[Optional()])
    submit = SubmitField("GUARDAR")


class MatchReportForm(FlaskForm):
    """Informe de partido. El marcador se calcula desde las fichas de stats."""

    photo = FileField("Foto del partido", validators=[Optional(), FileAllowed(IMG_EXT, "Solo imagenes.")])
    photo_url = StringField("Foto por URL", validators=[Optional(), Length(max=500)],
                            render_kw={"placeholder": "https://.../foto.jpg"})
    remove_photo = BooleanField("Quitar la foto actual")
    photo_credit = StringField("Credito de la foto", validators=[Optional(), Length(max=120)],
                               render_kw={"placeholder": "Foto: staff de la liga"})
    headline = StringField("Titular", validators=[Optional(), Length(max=180)],
                           render_kw={"placeholder": "Goleada en la jornada 5"})
    summary = StringField("Resumen", validators=[Optional(), Length(max=400)])
    body = TextAreaField("Cronica", validators=[Optional()])
    video_url = StringField("Video del partido", validators=[Optional(), Length(max=255)])
    mvp_player_id = SelectField("Jugador del partido", coerce=optional_int, choices=[], validators=[Optional()])
    is_published = BooleanField("Publicar el informe", default=True)
    submit = SubmitField("GUARDAR INFORME")


# --------------------------------------------------------------------------- #
# Contenido: salas, articulos, museo, enlaces, reglamento, streams
# --------------------------------------------------------------------------- #
class RoomForm(FlaskForm):
    code = StringField("Codigo", validators=[DataRequired(), Length(max=12)], render_kw={"placeholder": "01"})
    name = StringField("Nombre", validators=[Optional(), Length(max=80)], default="DIAMONDS PUBLIC")
    url = StringField("Link de HaxBall", validators=[DataRequired(), Length(max=255)])
    region = StringField("Region", validators=[Optional(), Length(max=40)], default="Latam")
    max_players = IntegerField("Jugadores maximos", validators=[Optional(), NumberRange(2, 30)], default=12)
    map_name = StringField("Mapa", validators=[Optional(), Length(max=80)])
    mode = StringField("Modo", validators=[Optional(), Length(max=40)])
    password = StringField("Contrasena de la sala", validators=[Optional(), Length(max=60)])
    image = FileField("Miniatura", validators=[Optional(), FileAllowed(IMG_EXT, "Solo imagenes.")])
    image_url = StringField("Miniatura por URL", validators=[Optional(), Length(max=500)])
    description = StringField("Descripcion", validators=[Optional(), Length(max=255)])
    is_open = BooleanField("Sala abierta", default=True)
    is_featured = BooleanField("Destacar")
    sort_order = IntegerField("Orden", validators=[Optional(), NumberRange(0, 999)], default=100)
    submit = SubmitField("GUARDAR")


class ArticleForm(FlaskForm):
    kind = SelectField("Tipo", choices=[(key, Category.LABELS[key]) for key in Category.ALL],
                       validators=[DataRequired()], default=Category.NEWS)
    category = SelectField(
        "Categoria",
        choices=[(key, Category.CATEGORY_LABELS[key]) for key in Category.CATEGORIES],
        validators=[DataRequired()],
    )
    title = StringField("Titulo", validators=[DataRequired("El titulo es obligatorio."), Length(max=180)])
    summary = StringField("Resumen", validators=[Optional(), Length(max=400)])
    body = TextAreaField("Contenido", validators=[Optional()])
    cover = FileField("Portada", validators=[Optional(), FileAllowed(IMG_EXT, "Solo imagenes.")])
    cover_url = StringField("Portada por URL", validators=[Optional(), Length(max=500)])
    remove_cover = BooleanField("Quitar portada actual")
    attachment = StringField("Documento adjunto (URL)", validators=[Optional(), Length(max=255)])
    division_id = SelectField("Division", coerce=optional_int, choices=[], validators=[Optional()])
    published_at = DateTimeField("Publicado el", validators=[Optional()], format="%Y-%m-%dT%H:%M")
    expires_at = DateTimeField("Vigente hasta", validators=[Optional()], format="%Y-%m-%dT%H:%M")
    is_featured = BooleanField("Destacar en portada")
    is_pinned = BooleanField("Fijar arriba")
    is_published = BooleanField("Publicado", default=True)
    submit = SubmitField("GUARDAR")


class MuseumForm(FlaskForm):
    title = StringField("Titulo del premio", validators=[DataRequired(), Length(max=140)])
    category = SelectField("Categoria", choices=[("premios", "Premios"), ("rankings", "Rankings"),
                                                 ("campeones", "Campeones"), ("trofeos", "Trofeos")],
                           validators=[DataRequired()], default="premios")
    division_short = StringField("Division", validators=[Optional(), Length(max=8)], render_kw={"placeholder": "D1"})
    season_number = IntegerField("Temporada", validators=[Optional(), NumberRange(0, 99)])
    recipient = StringField("Ganador", validators=[Optional(), Length(max=80)])
    team_id = SelectField("Equipo", coerce=optional_int, choices=[], validators=[Optional()])
    description = StringField("Descripcion", validators=[Optional(), Length(max=400)])
    image = FileField("Imagen", validators=[Optional(), FileAllowed(IMG_EXT, "Solo imagenes.")])
    image_url = StringField("Imagen por URL", validators=[Optional(), Length(max=500)])
    place = IntegerField("Puesto", validators=[Optional(), NumberRange(0, 99)], default=1)
    awarded_on = DateField("Fecha de entrega", validators=[Optional()])
    is_highlight = BooleanField("Destacar")
    sort_order = IntegerField("Orden", validators=[Optional(), NumberRange(0, 9999)], default=100)
    submit = SubmitField("GUARDAR")


class LinkForm(FlaskForm):
    """Alianzas, redes sociales y metodos de donacion: un solo formulario.

    Que campos importan depende de ``kind`` (ver ``LinkKind``).
    """
    kind = SelectField("Tipo", choices=[(key, LinkKind.LABELS[key]) for key in LinkKind.ALL],
                       validators=[DataRequired()], default=LinkKind.SOCIAL)
    label = StringField("Nombre", validators=[DataRequired(), Length(max=90)])
    group = SelectField("Grupo / estado", choices=[], validators=[Optional()])
    subkind = SelectField("Subtipo", choices=[], validators=[Optional()])
    tagline = StringField("Bajada", validators=[Optional(), Length(max=160)])
    body = TextAreaField("Descripcion", validators=[Optional()])
    handle = StringField("Usuario", validators=[Optional(), Length(max=80)],
                         render_kw={"placeholder": "@diamondsleague"})
    account = StringField("Alias / cuenta de cobro", validators=[Optional(), Length(max=120)])
    code = StringField("Codigo de invitacion", validators=[Optional(), Length(max=60)])
    url = StringField("Enlace", validators=[Optional(), Length(max=255)],
                      render_kw={"placeholder": "https://"})
    icon = StringField("Icono (1-2 letras)", validators=[Optional(), Length(max=8)])
    color = hex_color()
    starts_on = DateField("Inicio", validators=[Optional()])
    is_active = BooleanField("Activo", default=True)
    is_featured = BooleanField("Destacar")
    is_primary = BooleanField("Principal")
    sort_order = IntegerField("Orden", validators=[Optional(), NumberRange(0, 9999)], default=100)
    submit = SubmitField("GUARDAR")


class RegulationForm(FlaskForm):
    """Reglamento de la liga: reglas de Discord, comunidad y escala de sanciones."""
    scope = SelectField("Ambito", choices=[("discord", "Discord"), ("comunidad", "Comunidad"),
                                           ("sanciones", "Sanciones")],
                        validators=[DataRequired()], default="discord")
    position = IntegerField("Posicion", validators=[Optional(), NumberRange(1, 999)], default=1)
    title = StringField("Titulo", validators=[DataRequired(), Length(max=90)])
    body = TextAreaField("Texto de la regla", validators=[Optional()])
    color = SelectField("Nivel", choices=[("general", "General / informativo"), ("yellow", "Amarillo (aviso)"),
                                           ("orange", "Naranja"), ("red", "Rojo (grave)")],
                        validators=[Optional()], default="general")
    note = StringField("Nota", validators=[Optional(), Length(max=255)])
    submit = SubmitField("GUARDAR")


class LiveStreamForm(FlaskForm):
    title = StringField("Titulo del partido", validators=[DataRequired(), Length(max=160)])
    platform = SelectField("Plataforma", choices=[("twitch", "Twitch"), ("kick", "Kick"),
                                                   ("youtube", "YouTube"), ("otro", "Otro")],
                           validators=[DataRequired()], default="twitch")
    channel = StringField("Canal / ID de video", validators=[Optional(), Length(max=80)])
    embed_url = StringField("URL de embed personalizada", validators=[Optional(), Length(max=400)])
    watch_url = StringField("URL para ver", validators=[DataRequired(), Length(max=255)])
    league = StringField("Liga", validators=[Optional(), Length(max=80)], default="LIVE FUTBOL")
    competition = StringField("Competencia", validators=[Optional(), Length(max=80)])
    thumbnail = FileField("Miniatura", validators=[Optional(), FileAllowed(IMG_EXT, "Solo imagenes.")])
    thumbnail_url = StringField("Miniatura por URL", validators=[Optional(), Length(max=500)])
    language = StringField("Idioma", validators=[Optional(), Length(max=20)], default="es")
    is_live = BooleanField("Esta en vivo")
    is_featured = BooleanField("Destacar")
    viewers = IntegerField("Espectadores", validators=[Optional(), NumberRange(0, 999999)], default=0)
    scheduled_at = DateTimeField("Programado para", validators=[Optional()], format="%Y-%m-%dT%H:%M")
    sort_order = IntegerField("Orden", validators=[Optional(), NumberRange(0, 9999)], default=100)
    submit = SubmitField("GUARDAR")


class DonationForm(FlaskForm):
    donor_name = StringField("Donante", validators=[DataRequired(), Length(max=80)])
    message = TextAreaField("Mensaje", validators=[Optional(), Length(max=400)])
    amount = DecimalField("Monto", validators=[DataRequired(), NumberRange(0, 1000000)], places=2)
    currency = StringField("Moneda", validators=[Optional(), Length(max=8)], default="USD")
    channel = StringField("Metodo", validators=[Optional(), Length(max=60)])
    is_public = BooleanField("Mostrar publicamente", default=True)
    donated_at = DateTimeField("Fecha", validators=[Optional()], format="%Y-%m-%dT%H:%M")
    submit = SubmitField("GUARDAR")


class DonationGoalForm(FlaskForm):
    """La meta de donacion vive en ``settings``: aqui se editan sus cuatro claves."""
    title = StringField("Titulo", validators=[DataRequired(), Length(max=90)])
    target = DecimalField("Meta", validators=[DataRequired(), NumberRange(0, 1000000)], places=2)
    note = TextAreaField("Nota", validators=[Optional(), Length(max=400)])
    link = StringField("Enlace de pago", validators=[Optional(), Length(max=255)])
    submit = SubmitField("GUARDAR META")


# --------------------------------------------------------------------------- #
# Usuarios y equipo de administracion (una sola tabla: ``users``)
# --------------------------------------------------------------------------- #
class UserForm(FlaskForm):
    """Cuenta de acceso y, si es del equipo, su ficha publica en un solo formulario."""
    username = StringField("Usuario", validators=[DataRequired(), Length(min=3, max=24)])
    email = StringField("Correo", validators=[DataRequired(), Email("Correo no valido.")])
    password = PasswordField("Contrasena", validators=[Optional(), Length(min=6, message="Minimo 6 caracteres.")],
                             render_kw={"autocomplete": "new-password",
                                        "placeholder": "Dejar vacio para no cambiarla"})
    role = SelectField("Rol", choices=[(Role.ADMIN, "Administrador"), (Role.STAFF, "Staff"),
                                       (Role.USER, "Jugador")],
                       validators=[DataRequired()], default=Role.USER)
    display_name = StringField("Nombre visible", validators=[Optional(), Length(max=60)])
    bio = TextAreaField("Biografia", validators=[Optional(), Length(max=400)])
    haxball_id = StringField("ID de HaxBall", validators=[Optional(), Length(max=40)])
    country = StringField("Pais", validators=[Optional(), Length(max=60)])
    is_premium = BooleanField("Premium")
    is_active_account = BooleanField("Cuenta activa", default=True)

    # Ficha publica del equipo (solovisible si aparece en la seccion EQUIPO)
    title = StringField("Cargo", validators=[Optional(), Length(max=80)],
                        render_kw={"placeholder": "Director de competicion"})
    tags = StringField("Etiquetas (separadas por coma)", validators=[Optional(), Length(max=160)])
    discord = StringField("Discord", validators=[Optional(), Length(max=80)])
    avatar = FileField("Avatar", validators=[Optional(), FileAllowed(IMG_EXT, "Solo imagenes.")])
    avatar_url = StringField("Avatar por URL", validators=[Optional(), Length(max=500)])
    banner = FileField("Banner", validators=[Optional(), FileAllowed(IMG_EXT, "Solo imagenes.")])
    banner_url = StringField("Banner por URL", validators=[Optional(), Length(max=500)])
    remove_avatar = BooleanField("Quitar el avatar actual")
    remove_banner = BooleanField("Quitar el banner actual")
    is_leader = BooleanField("Lider de la liga")
    is_public = BooleanField("Aparece en la pagina de equipo")
    sort_order = IntegerField("Orden", validators=[Optional(), NumberRange(0, 9999)], default=100)
    submit = SubmitField("GUARDAR")


class SuggestionFilterForm(FlaskForm):
    """Filtros del listado de sugerencias del panel."""
    status = SelectField("Estado", choices=[("", "Todos")] +
                         [(key, SuggestionStatus.LABELS[key]) for key in SuggestionStatus.ALL],
                         validators=[Optional()], default="")
    category = SelectField("Categoria", choices=[("", "Todas")] +
                           [(key, label) for key, label in SUGGESTION_CATEGORIES.items()],
                           validators=[Optional()], default="")
    q = StringField("Buscar", validators=[Optional(), Length(max=120)],
                    render_kw={"placeholder": "titulo o texto"})
    submit = SubmitField("FILTRAR")


class SearchForm(FlaskForm):
    """Buscador global del panel: un campo, resultados en todas las secciones."""
    q = StringField("Buscar en todo el panel", validators=[Optional(), Length(max=120)],
                    render_kw={"placeholder": "equipo, jugador, noticia, usuario..."})
    submit = SubmitField("BUSCAR")
