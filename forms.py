"""Formularios (WTForms + CSRF)."""
from __future__ import annotations

from flask_wtf import FlaskForm
from flask_wtf.file import FileAllowed, FileField
from wtforms import BooleanField, DecimalField, DateField, DateTimeField, IntegerField, PasswordField, SelectField, StringField, SubmitField, TextAreaField
from wtforms.validators import DataRequired, Email, EqualTo, Length, NumberRange, Optional, Regexp, URL

from models import Role
from utils import EMAIL_RE, USERNAME_RE


def optional_int(value):
    """Convierte a int sin fallar cuando el SelectField esta vacio."""
    if value is None or value == "":
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None



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
    avatar = FileField("Avatar", validators=[Optional(), FileAllowed(["png", "jpg", "jpeg", "webp"], "Solo imagenes.")])
    remove_avatar = BooleanField("Quitar avatar actual")
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
        "Confirmar nueva contrasena",
        validators=[DataRequired(), EqualTo("new_password", message="Las contrasenas no coinciden.")],
        render_kw={"autocomplete": "new-password", "placeholder": "········"},
    )
    submit = SubmitField("GUARDAR NUEVA CONTRASENA")


class GoogleLinkForm(FlaskForm):
    google_email = StringField(
        "Correo de Google", validators=[DataRequired(), Email("Correo no valido.")],
        render_kw={"placeholder": "tu.cuenta@gmail.com"},
    )
    submit = SubmitField("VINCULAR CUENTA")


# --------------------------------------------------------------------------- #
# Sugerencias
# --------------------------------------------------------------------------- #
class SuggestionForm(FlaskForm):
    """Mensaje del canal de sugerencias (solo para quien ya entro con su cuenta)."""

    category = SelectField(
        "Tipo de mensaje",
        choices=[("idea", "Idea nueva"), ("mejora", "Mejora de la pagina"),
                 ("liga", "Liga y reglamento"), ("error", "Algo no funciona"),
                 ("otro", "Otro")],
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
        choices=[("new", "Nueva"), ("reviewing", "En estudio"), ("done", "Aplicada")],
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


class ArticleForm(FlaskForm):
    kind = SelectField("Tipo", choices=[("news", "Noticia"), ("announcement", "Anuncio / Novedad"), ("report", "Informe")],
                       validators=[DataRequired()])
    category = SelectField(
        "Categoria",
        choices=[("general", "General"), ("inscripcion", "Inscripcion"), ("premios", "Premios"),
                 ("sanciones", "Sanciones"), ("eventos", "Eventos"), ("sorteos", "Sorteos"),
                 ("entrevista", "Entrevista")],
        validators=[DataRequired()],
    )
    title = StringField("Titulo", validators=[DataRequired("El titulo es obligatorio."), Length(max=180)])
    summary = StringField("Resumen", validators=[Optional(), Length(max=400)])
    body = TextAreaField("Contenido", validators=[Optional()])
    cover = FileField("Portada", validators=[Optional(), FileAllowed(["png", "jpg", "jpeg", "webp"], "Solo imagenes.")])
    remove_cover = BooleanField("Quitar portada actual")
    attachment = FileField("Documento adjunto", validators=[Optional(), FileAllowed(["pdf", "png", "jpg", "jpeg", "webp"], "PDF o imagen.")])
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
                           validators=[DataRequired()])
    division_short = StringField("Division", validators=[Optional(), Length(max=8)], render_kw={"placeholder": "D1"})
    season_number = IntegerField("Temporada", validators=[Optional(), NumberRange(0, 99)])
    recipient = StringField("Ganador", validators=[Optional(), Length(max=80)])
    team_id = SelectField("Equipo", coerce=optional_int, choices=[], validators=[Optional()])
    description = StringField("Descripcion", validators=[Optional(), Length(max=400)])
    image = FileField("Imagen", validators=[Optional(), FileAllowed(["png", "jpg", "jpeg", "webp"], "Solo imagenes.")])
    place = IntegerField("Puesto", validators=[Optional(), NumberRange(0, 99)], default=1)
    awarded_on = DateField("Fecha de entrega", validators=[Optional()])
    is_highlight = BooleanField("Destacar")
    sort_order = IntegerField("Orden", validators=[Optional(), NumberRange(0, 9999)], default=100)
    submit = SubmitField("GUARDAR")


class TeamForm(FlaskForm):
    name = StringField("Nombre del equipo", validators=[DataRequired(), Length(max=80)])
    short = StringField("Abreviatura", validators=[Optional(), Length(max=20)])
    division_id = SelectField("Division", coerce=optional_int, choices=[], validators=[Optional()])
    coach = StringField("DT / Entrenador", validators=[Optional(), Length(max=60)])
    captain = StringField("Capitan", validators=[Optional(), Length(max=60)])
    country = StringField("Pais", validators=[Optional(), Length(max=60)])
    founded_year = StringField("Fundado", validators=[Optional(), Length(max=12)])
    crest = FileField("Escudo", validators=[Optional(), FileAllowed(["png", "jpg", "jpeg", "webp", "svg"], "Solo imagenes.")])
    remove_crest = BooleanField("Quitar escudo actual")
    color = StringField("Color hex", validators=[Optional(), Length(max=16)], render_kw={"placeholder": "#1bebf2"})
    description = TextAreaField("Descripcion", validators=[Optional()])
    sort_order = IntegerField("Orden", validators=[Optional(), NumberRange(0, 9999)], default=100)
    is_active = BooleanField("Equipo activo", default=True)
    submit = SubmitField("GUARDAR")


class PlayerForm(FlaskForm):
    team_id = SelectField("Equipo", coerce=optional_int, choices=[], validators=[DataRequired("Selecciona un equipo.")])
    username = StringField("Usuario en HaxBall", validators=[DataRequired(), Length(max=60)])
    haxball_id = StringField("ID de HaxBall", validators=[Optional(), Length(max=40)])
    position = SelectField("Posicion", choices=[("GK", "Portero"), ("DF", "Defensa"), ("MF", "Medio"),
                                                 ("FW", "Delantero"), ("MC", "Mediocampo")],
                           validators=[DataRequired()], default="MF")
    number = IntegerField("Numero", validators=[Optional(), NumberRange(0, 99)], default=0)
    country = StringField("Pais", validators=[Optional(), Length(max=60)])
    is_captain = BooleanField("Capitan")
    is_active = BooleanField("Activo en plantilla", default=True)
    submit = SubmitField("GUARDAR")


class MatchForm(FlaskForm):
    division_id = SelectField("Division", coerce=optional_int, choices=[], validators=[DataRequired()])
    journey = IntegerField("Jornada", validators=[DataRequired(), NumberRange(1, 99)], default=1)
    stage = StringField("Fase", validators=[Optional(), Length(max=40)], default="Liga regular")
    played_on = DateField("Fecha", validators=[Optional()])
    kickoff = StringField("Hora", validators=[Optional(), Length(max=5)], render_kw={"placeholder": "19:00"})
    home_team_id = SelectField("Equipo local", coerce=optional_int, choices=[], validators=[DataRequired()])
    away_team_id = SelectField("Equipo visitante", coerce=optional_int, choices=[], validators=[DataRequired()])
    home_score = IntegerField("Marcador local", validators=[Optional(), NumberRange(0, 99)])
    away_score = IntegerField("Marcador visitante", validators=[Optional(), NumberRange(0, 99)])
    status = SelectField("Estado", choices=[("scheduled", "Programado"), ("live", "En vivo"),
                                             ("finished", "Finalizado"), ("wo", "Walkover"), ("postponed", "Aplazado")],
                         validators=[DataRequired()], default="scheduled")
    room_url = StringField("Link de la sala", validators=[Optional(), Length(max=255)])
    replay_url = StringField("Link del replay", validators=[Optional(), Length(max=255)])
    stream_url = StringField("Link del stream", validators=[Optional(), Length(max=255)])
    notes = TextAreaField("Notas", validators=[Optional()])
    submit = SubmitField("GUARDAR")


class MatchReportForm(FlaskForm):
    """Informe de un partido: foto del partido, resultado y lectura."""
    photo = FileField(
        "Foto del partido",
        validators=[Optional(), FileAllowed(["png", "jpg", "jpeg", "webp"], "Solo imagenes.")],
    )
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


class PlayerStatForm(FlaskForm):
    """Una fila de la tabla de estadisticas individuales del partido."""
    player_id = SelectField("Jugador", coerce=optional_int, choices=[],
                            validators=[DataRequired("Selecciona un jugador.")])
    goals = IntegerField("Goles", validators=[Optional(), NumberRange(0, 99)], default=0)
    assists = IntegerField("Asistencias", validators=[Optional(), NumberRange(0, 99)], default=0)
    clean_sheets = IntegerField("CS", validators=[Optional(), NumberRange(0, 9)], default=0,
                                render_kw={"title": "Clean sheet / valla invicta"})
    clean_sheet_seconds = IntegerField("Segundos sin gol", validators=[Optional(), NumberRange(0, 36000)], default=0)
    own_goals = IntegerField("Autogoles", validators=[Optional(), NumberRange(0, 99)], default=0)
    yellow_cards = IntegerField("Amarillas", validators=[Optional(), NumberRange(0, 9)], default=0)
    red_cards = IntegerField("Rojas", validators=[Optional(), NumberRange(0, 9)], default=0)
    minutes = IntegerField("Minutos", validators=[Optional(), NumberRange(0, 200)], default=0)
    is_mvp = BooleanField("MVP")
    note = StringField("Nota", validators=[Optional(), Length(max=160)],
                       render_kw={"placeholder": "Doblete en el minuto 3 y 40"})
    submit = SubmitField("ANADIR")


class RosterPlayerForm(FlaskForm):
    """Alta rapida de un jugador dentro de la pantalla de un equipo."""
    username = StringField("Usuario en HaxBall", validators=[DataRequired(), Length(max=60)],
                           render_kw={"placeholder": "jugador_x5"})
    haxball_id = StringField("ID de HaxBall", validators=[Optional(), Length(max=40)])
    position = SelectField("Posicion", choices=[("GK", "Portero"), ("DF", "Defensa"), ("MF", "Medio"),
                                                 ("FW", "Delantero"), ("MC", "Mediocampo")],
                           validators=[DataRequired()], default="MF")
    number = IntegerField("Numero", validators=[Optional(), NumberRange(0, 99)], default=0)
    country = StringField("Pais", validators=[Optional(), Length(max=60)])
    is_captain = BooleanField("Capitan")
    submit = SubmitField("ANADIR A LA PLANTILLA")


class TeamCrestForm(FlaskForm):
    """Subir o cambiar solo el escudo, sin entrar al formulario completo."""
    crest = FileField(
        "Escudo / logo del equipo",
        validators=[DataRequired("Elige una imagen."), FileAllowed(["png", "jpg", "jpeg", "webp", "svg"], "Solo imagenes.")],
    )
    remove_crest = BooleanField("Quitar el escudo actual")
    submit = SubmitField("GUARDAR ESCUDO")


class RoomForm(FlaskForm):
    code = StringField("Codigo", validators=[DataRequired(), Length(max=12)], render_kw={"placeholder": "01"})
    name = StringField("Nombre", validators=[Optional(), Length(max=80)], default="DIAMONDS PUBLIC")
    haxball_url = StringField("Link de HaxBall", validators=[DataRequired(), Length(max=255)])
    region = StringField("Region", validators=[Optional(), Length(max=40)], default="Latam")
    max_players = IntegerField("Jugadores maximos", validators=[Optional(), NumberRange(2, 30)], default=12)
    map_name = StringField("Mapa", validators=[Optional(), Length(max=80)])
    mode = StringField("Modo", validators=[Optional(), Length(max=80)])
    ping = IntegerField("Ping maximo", validators=[Optional(), NumberRange(0, 999)])
    password = StringField("Contrasena de la sala", validators=[Optional(), Length(max=60)])
    image = FileField("Miniatura", validators=[Optional(), FileAllowed(["png", "jpg", "jpeg", "webp"], "Solo imagenes.")])
    description = StringField("Descripcion", validators=[Optional(), Length(max=255)])
    is_open = BooleanField("Sala abierta", default=True)
    is_pinned = BooleanField("Fijar arriba")
    is_featured = BooleanField("Destacar")
    sort_order = IntegerField("Orden", validators=[Optional(), NumberRange(0, 999)], default=100)
    submit = SubmitField("GUARDAR")


class AllianceForm(FlaskForm):
    name = StringField("Nombre", validators=[DataRequired(), Length(max=90)])
    kind = SelectField("Tipo", choices=[("partner", "Servidor partner"), ("affiliate", "Afiliacion")],
                       validators=[DataRequired()], default="partner")
    tagline = StringField("Bajada", validators=[Optional(), Length(max=160)])
    description = TextAreaField("Descripcion", validators=[Optional()])
    url = StringField("Enlace", validators=[Optional(), Length(max=255)])
    emblem = StringField("Emblema (2-3 letras)", validators=[Optional(), Length(max=8)])
    code = StringField("Codigo de invitación", validators=[Optional(), Length(max=60)])
    status = SelectField("Estado", choices=[("activa", "Activa"), ("proxima", "Proxima afiliacion"),
                                           ("pendiente", "Pendiente"), ("cerrada", "Cerrada")],
                         validators=[DataRequired()], default="activa")
    starts_on = DateField("Inicio", validators=[Optional()])
    ends_on = DateField("Fin", validators=[Optional()])
    sort_order = IntegerField("Orden", validators=[Optional(), NumberRange(0, 9999)], default=100)
    is_featured = BooleanField("Destacar")
    submit = SubmitField("GUARDAR")


SocialPlatforms = {
    "tiktok": "TikTok", "discord": "Discord", "twitch": "Twitch", "kick": "Kick",
    "instagram": "Instagram", "x": "X (Twitter)", "youtube": "YouTube",
    "facebook": "Facebook", "haxball": "HaxBall",
}


class SocialForm(FlaskForm):
    platform = SelectField("Plataforma", choices=[(k, v) for k, v in SocialPlatforms.items()], validators=[DataRequired()])
    owner = SelectField("Pertenece a", choices=[("liga", "Liga"), ("streamer", "Streamers"), ("equipo", "Equipo")],
                        validators=[DataRequired()], default="liga")
    label = StringField("Nombre", validators=[DataRequired(), Length(max=60)])
    handle = StringField("Usuario", validators=[Optional(), Length(max=80)])
    url = StringField("Enlace", validators=[DataRequired(), Length(max=255)])
    icon = StringField("Icono (1-2 letras)", validators=[Optional(), Length(max=8)])
    is_primary = BooleanField("Principal")
    is_active = BooleanField("Activo", default=True)
    sort_order = IntegerField("Orden", validators=[Optional(), NumberRange(0, 9999)], default=100)
    submit = SubmitField("GUARDAR")



class StaffForm(FlaskForm):
    name = StringField("Nombre", validators=[DataRequired(), Length(max=60)])
    username = StringField("Usuario / Discord", validators=[Optional(), Length(max=60)])
    role = StringField("Rol", validators=[DataRequired(), Length(max=40)], default="STAFF")
    title = StringField("Cargo", validators=[Optional(), Length(max=80)])
    bio = StringField("Descripcion", validators=[Optional(), Length(max=400)])
    avatar = FileField("Avatar", validators=[Optional(), FileAllowed(["png", "jpg", "jpeg", "webp"], "Solo imagenes.")])
    banner = FileField("Banner", validators=[Optional(), FileAllowed(["png", "jpg", "jpeg", "webp"], "Solo imagenes.")])
    remove_avatar = BooleanField("Quitar avatar actual")
    remove_banner = BooleanField("Quitar banner actual")
    tags = StringField("Etiquetas (separadas por coma)", validators=[Optional(), Length(max=160)])
    discord = StringField("Discord", validators=[Optional(), Length(max=80)])
    email = StringField("Correo", validators=[Optional(), Email("Correo no valido.")])
    is_leader = BooleanField("Lider de la liga")
    is_active = BooleanField("Activo", default=True)
    sort_order = IntegerField("Orden", validators=[Optional(), NumberRange(0, 9999)], default=100)
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
    thumbnail = FileField("Miniatura", validators=[Optional(), FileAllowed(["png", "jpg", "jpeg", "webp"], "Solo imagenes.")])
    language = StringField("Idioma", validators=[Optional(), Length(max=20)], default="es")
    is_live = BooleanField("Esta en vivo")
    is_featured = BooleanField("Destacar")
    viewers = IntegerField("Espectadores", validators=[Optional(), NumberRange(0, 999999)], default=0)
    scheduled_at = DateTimeField("Programado para", validators=[Optional()], format="%Y-%m-%dT%H:%M")
    sort_order = IntegerField("Orden", validators=[Optional(), NumberRange(0, 9999)], default=100)
    submit = SubmitField("GUARDAR")


class DonationChannelForm(FlaskForm):
    label = StringField("Metodo", validators=[DataRequired(), Length(max=60)])
    method = StringField("Tipo", validators=[DataRequired(), Length(max=60)])
    account = StringField("Cuenta / alias", validators=[DataRequired(), Length(max=120)])
    url = StringField("Enlace de pago", validators=[Optional(), Length(max=255)])
    note = StringField("Nota", validators=[Optional(), Length(max=255)])
    icon = StringField("Icono", validators=[Optional(), Length(max=8)])
    color = StringField("Color", validators=[Optional(), Length(max=16)])
    is_active = BooleanField("Activo", default=True)
    sort_order = IntegerField("Orden", validators=[Optional(), NumberRange(0, 999)], default=100)
    submit = SubmitField("GUARDAR")


class DonationForm(FlaskForm):
    donor_name = StringField("Donante", validators=[DataRequired(), Length(max=80)])
    message = StringField("Mensaje", validators=[Optional(), Length(max=400)])
    amount = DecimalField("Monto", validators=[DataRequired(), NumberRange(0, 1000000)], places=2)
    currency = StringField("Moneda", validators=[Optional(), Length(max=8)], default="USD")
    channel = StringField("Metodo", validators=[Optional(), Length(max=60)])
    is_public = BooleanField("Mostrar públicamente", default=True)
    donated_at = DateTimeField("Fecha", validators=[Optional()], format="%Y-%m-%dT%H:%M")
    submit = SubmitField("GUARDAR")


class UserForm(FlaskForm):
    username = StringField("Usuario", validators=[DataRequired(), Length(min=3, max=24)])
    email = StringField("Correo", validators=[DataRequired(), Email("Correo no valido.")])
    password = PasswordField("Contrasena", validators=[Optional(), Length(min=6, message="Minimo 6 caracteres.")],
                             render_kw={"autocomplete": "new-password", "placeholder": "Dejar vacio para no cambiarla"})
    role = SelectField("Rol", choices=[(Role.ADMIN, "Administrador"), (Role.STAFF, "Staff"), (Role.USER, "Jugador")],
                       validators=[DataRequired()], default=Role.USER)
    display_name = StringField("Nombre visible", validators=[Optional(), Length(max=60)])
    bio = StringField("Biografia", validators=[Optional(), Length(max=400)])
    haxball_id = StringField("ID de HaxBall", validators=[Optional(), Length(max=40)])
    country = StringField("Pais", validators=[Optional(), Length(max=60)])
    is_premium = BooleanField("Premium")
    is_active_account = BooleanField("Cuenta activa", default=True)
    submit = SubmitField("GUARDAR")


class DivisionForm(FlaskForm):
    name = StringField("Nombre", validators=[DataRequired(), Length(max=80)])
    key = StringField("Clave", validators=[DataRequired(), Length(max=40)])
    short = StringField("Abreviatura", validators=[DataRequired(), Length(max=8)])
    level = IntegerField("Nivel", validators=[Optional(), NumberRange(1, 9)], default=1)
    teams_count = IntegerField("Equipos", validators=[Optional(), NumberRange(0, 64)])
    journeys_count = IntegerField("Jornadas", validators=[Optional(), NumberRange(0, 60)])
    playoffs_slots = IntegerField("Puestos a playoffs", validators=[Optional(), NumberRange(0, 32)])
    relegation_slots = IntegerField("Descensos", validators=[Optional(), NumberRange(0, 32)])
    promotion_slots = IntegerField("Ascensos", validators=[Optional(), NumberRange(0, 32)])
    modality = StringField("Modalidad", validators=[Optional(), Length(max=60)])
    duration = StringField("Duracion", validators=[Optional(), Length(max=80)])
    map_name = StringField("Mapa", validators=[Optional(), Length(max=80)])
    server = StringField("Servidor", validators=[Optional(), Length(max=60)])
    tolerance = StringField("Tolerancia", validators=[Optional(), Length(max=80)])
    description = TextAreaField("Descripcion", validators=[Optional()])
    schedule_note = StringField("Nota de calendario", validators=[Optional(), Length(max=200)])
    submit = SubmitField("GUARDAR")


class RuleForm(FlaskForm):
    """Reglamento: reglas de Discord, comunidad y conducta."""
    scope = SelectField("Ambito", choices=[("discord", "Discord"), ("comunidad", "Comunidad"),
                                          ("sanciones", "Sanciones")],
                        validators=[DataRequired()], default="discord")
    position = IntegerField("Posicion", validators=[Optional(), NumberRange(1, 999)], default=1)
    title = StringField("Titulo", validators=[DataRequired(), Length(max=90)])
    body = TextAreaField("Texto de la regla", validators=[Optional()])
    submit = SubmitField("GUARDAR")


class SanctionLevelForm(FlaskForm):
    """Nivel de la escala de sanciones."""
    name = StringField("Nombre", validators=[DataRequired(), Length(max=60)])
    color = SelectField("Color", choices=[("general", "General / informativo"), ("yellow", "Amarillo (aviso)"),
                                           ("orange", "Naranja"), ("red", "Rojo (grave)")],
                        validators=[DataRequired()], default="general")
    items = TextAreaField("Sanciones (una por linea)", validators=[Optional()])
    note = StringField("Nota", validators=[Optional(), Length(max=255)])
    sort_order = IntegerField("Orden", validators=[Optional(), NumberRange(0, 999)], default=100)
    submit = SubmitField("GUARDAR")


class SettingForm(FlaskForm):
    value = TextAreaField("Valor", validators=[Optional()])
    submit = SubmitField("GUARDAR")

