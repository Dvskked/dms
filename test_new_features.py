"""Prueba de las funciones nuevas: base de datos, equipos, informes y correo.

    python test_new_features.py

Importante: las peticiones HTTP nunca se lanzan con un app context abierto a mano.
Flask reutiliza el app context existente y `flask_login` cachea el usuario en `g`,
por lo que `current_user` se quedaria pegado al de la peticion anterior. Por eso
cada comprobacion de base de datos usa `q()`, que abre su propio contexto.
"""
from __future__ import annotations

import datetime
import io
import os
import sys
import tempfile

os.environ.setdefault("FLASK_ENV", "testing")
os.environ["MAIL_ENABLED"] = "0"

# SQLite en fichero temporal: con `:memory:` todas las sesiones comparten
# conexion (StaticPool) y las transacciones se pisan entre si.
_TMP = tempfile.TemporaryDirectory(prefix="diamonds-test-", ignore_cleanup_errors=True)
os.environ["TEST_DATABASE_URL"] = (
    "sqlite:///" + os.path.join(_TMP.name, "test.db").replace("\\", "/")
)
os.environ["TESTING_UPLOAD_FOLDER"] = _TMP.name

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import create_app  # noqa: E402
from config import normalize_database_url  # noqa: E402
from extensions import db  # noqa: E402
from models import (  # noqa: E402
    Division, EmailLog, Match, MatchReport, PasswordResetToken, Player, PlayerMatchStat,
    Role, Season, Standing, Suggestion, SuggestionVote, Team, User, recompute_player_stats,
)
from utils import utcnow  # noqa: E402

PASS, FAIL = "\033[92m[OK ]\033[0m", "\033[91m[FAIL]\033[0m"
results: list[tuple[bool, str]] = []


def check(label: str, condition: bool, extra: str = "") -> None:
    results.append((bool(condition), label))
    print(f"{PASS if condition else FAIL} {label}{(' -> ' + extra) if extra and not condition else ''}")


def q(app, fn, *args, **kwargs):
    """Ejecuta `fn` dentro de su propio app context y devuelve el resultado."""
    with app.app_context():
        return fn(*args, **kwargs)


def png_file(color=(27, 235, 242), name: str = "logo.png") -> tuple[io.BytesIO, str]:
    """Archivo PNG minimo valido (2x2) para probar las subidas de imagen.

    Devuelve un flujo, no `bytes`: el cliente de pruebas de Werkzeug descarta
    silenciosamente los ficheros enviados como bytes planos.
    """
    from PIL import Image

    buf = io.BytesIO()
    Image.new("RGB", (2, 2), color).save(buf, format="PNG")
    buf.seek(0)
    return buf, name


def file_exists(app, relative: str | None) -> bool:
    if not relative:
        return False
    return os.path.exists(os.path.join(app.config["UPLOAD_FOLDER"], relative.replace("uploads/", "")))


# --------------------------------------------------------------------------- #
# 0. Datos de partida
# --------------------------------------------------------------------------- #
def seed(app) -> dict:
    with app.app_context():
        db.drop_all()
        db.create_all()

        admin = User(username="admin", email="admin@test.app", role=Role.ADMIN,
                     is_admin=True, is_premium=True)
        admin.set_password("adminmascapito")
        db.session.add(admin)
        db.session.add(Season(number=1, name="Temporada 1", is_current=True))
        db.session.commit()

        season = Season.query.first()
        db.session.add_all([
            Division(key="division-one", name="Division 1", short="D1", level=1, season_id=season.id),
            Division(key="division-two", name="Division 2", short="D2", level=2, season_id=season.id),
        ])
        db.session.commit()

        staff = User(username="staff1", email="staff@test.app", role=Role.STAFF)
        staff.set_password("staffpass")
        db.session.add(staff)
        db.session.commit()

        return {
            "admin_id": admin.id,
            "div1": Division.query.filter_by(key="division-one").first().id,
            "div2": Division.query.filter_by(key="division-two").first().id,
        }


# --------------------------------------------------------------------------- #
# 1. Esquema
# --------------------------------------------------------------------------- #
def test_schema(app) -> None:
    print("\n=== 1. BASE DE DATOS Y ESQUEMA ===")
    env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")
    with open(env_path, encoding="utf-8") as fh:
        env_text = fh.read()
    check("MySQL es el backend configurado en .env", "mysql" in env_text)

    # La URL de produccion no debe fijar la zona horaria a UTC en la conexion:
    # el horario de la liga se decide en la capa de aplicacion, no en el servidor.
    production_uri = normalize_database_url(os.getenv("DATABASE_URL", ""))
    check("la zona horaria no se fija en UTC (MySQL la pone a UTC)",
          "time_zone" not in production_uri and "init_command" not in production_uri,
          production_uri)
    check("la conexion MySQL usa utf8mb4", "charset=utf8mb4" in production_uri)


    tables = set(q(app, lambda: set(db.inspect(db.engine).get_table_names())))
    for name in ("match_reports", "player_match_stats", "password_reset_tokens", "email_logs"):
        check(f"tabla {name} creada", name in tables)

    from sqlalchemy import create_mock_engine
    from sqlalchemy.dialects import mysql

    import models  # noqa: F401

    ddl: list[str] = []
    mock = create_mock_engine(
        "mysql+pymysql://",
        lambda s, *a, **k: ddl.append(str(s.compile(dialect=mysql.dialect()))),
    )
    with app.app_context():
        db.metadata.create_all(mock, checkfirst=False)
    check("el esquema completo compila para MySQL", len(ddl) >= 28, f"{len(ddl)} sentencias")
    check("ninguna sentencia lleva sintaxis de SQLite", not any("AUTOINCREMENT" in s for s in ddl))
    check("el esquema conserva los 24 tablas originales", len(tables) >= 28, f"{len(tables)} tablas")


# --------------------------------------------------------------------------- #
# 2. Registro con correo
# --------------------------------------------------------------------------- #
def test_register(app) -> None:
    print("\n=== 2. REGISTRO CON CORREO DE BIENVENIDA ===")
    client = app.test_client()
    response = client.post("/auth/register", data={
        "username": "nuevo_jugador", "email": "nuevo@test.app",
        "password": "secreto123", "confirm_password": "secreto123",
    }, follow_redirects=True)
    check("registro acepta el formulario nuevo", response.status_code == 200)
    check("usuario creado", q(app, lambda: User.query.filter_by(username="nuevo_jugador").first()) is not None)
    check("el nuevo usuario no es admin",
          q(app, lambda: User.query.filter_by(username="nuevo_jugador").first().is_admin) is False)
    check("se registro el correo de bienvenida",
          q(app, lambda: EmailLog.query.filter_by(template="welcome").count()) == 1)
    check("el correo va al usuario correcto",
          q(app, lambda: EmailLog.query.filter_by(template="welcome").first().to_email) == "nuevo@test.app")
    check("el correo se marco como omitido (SMTP off en test)",
          q(app, lambda: EmailLog.query.filter_by(template="welcome").first().status) == "skipped")
    check("los admins recibieron el aviso de cuenta nueva",
          q(app, lambda: EmailLog.query.filter_by(template="new_account").count()) == 1)
    return client


# --------------------------------------------------------------------------- #
# 3-5. Equipos, informes y estadisticas
# --------------------------------------------------------------------------- #
def login_admin(app) -> object:
    client = app.test_client()
    response = client.post("/auth/login", data={"username": "admin", "password": "adminmascapito"},
                           follow_redirects=True)
    check("login del admin", response.status_code == 200)
    check("el panel responde al admin", client.get("/admin/").status_code == 200)
    return client


def test_teams_and_reports(app, ids, client) -> None:
    print("\n=== 3. EQUIPOS: ESCUDO Y PLANTILLA ===")
    response = client.post("/admin/equipos/nuevo", data={
        "name": "Los Diamonds", "short": "DIA", "division_id": str(ids["div1"]),
        "color": "#1bebf2", "sort_order": "1", "crest": png_file(),
    }, content_type="multipart/form-data", follow_redirects=True)
    check("alta de equipo con escudo", response.status_code == 200)
    team = q(app, lambda: Team.query.filter_by(name="Los Diamonds").first())
    check("equipo creado", team is not None)
    if team is None:
        return None
    check("el escudo quedo guardado", bool(team.crest), str(team.crest))
    check("el escudo es un archivo real", file_exists(app, team.crest))

    response = client.post(f"/admin/equipos/{team.id}/jugadores", data={
        "username": "diamante_01", "position": "MF", "number": "1",
        "country": "Argentina", "is_active": "y",
    }, follow_redirects=True)
    check("agregar jugador a la plantilla", response.status_code == 200)
    player = q(app, lambda: Player.query.filter_by(username="diamante_01").first())
    check("jugador creado y asignado al equipo", player is not None and player.team_id == team.id)

    response = client.post(f"/admin/equipos/{team.id}/jugadores", data={
        "username": "diamante_01", "position": "GK",
    }, follow_redirects=True)
    check("no permite duplicar un jugador en la misma plantilla",
          q(app, lambda: Player.query.filter_by(username="diamante_01").count()) == 1)
    return team.id, player.id


def test_match_report(app, ids, team_id, player_id, client) -> tuple[int, int]:
    print("\n=== 4. INFORME DE PARTIDO Y ESTADISTICAS ===")
    def make_rival():
        rival = Team(name="River FC", short="RIV", division_id=ids["div1"])
        db.session.add(rival)
        db.session.commit()
        match = Match(division_id=ids["div1"], journey=1, stage="Liga regular",
                      home_team_id=team_id, away_team_id=rival.id,
                      home_score=0, away_score=0, status="finished")
        db.session.add(match)
        db.session.commit()
        return match.id

    match_id = q(app, make_rival)

    response = client.get(f"/admin/partidos/{match_id}/informe")
    check("el editor de informe carga", response.status_code == 200)
    check("el editor ofrece a los dos equipos", b"Los Diamonds" in response.data)

    response = client.post(f"/admin/partidos/{match_id}/informe", data={
        "headline": "Goleada en la jornada 1", "summary": "Doblete del volante.",
        "body": "Cronica del partido.", "photo": png_file((255, 46, 136), "partido.png"),
        "photo_credit": "Foto: staff", "is_published": "y",
    }, content_type="multipart/form-data", follow_redirects=True)
    check("guardar informe con foto del partido", response.status_code == 200)
    report = q(app, lambda: MatchReport.query.filter_by(match_id=match_id).first())
    check("informe creado", report is not None)
    if report is None:
        return match_id, team_id
    check("foto del partido guardada", bool(report.photo), str(report.photo))
    check("la foto del partido existe en disco", file_exists(app, report.photo))
    check("titular del informe guardado", report.headline == "Goleada en la jornada 1")
    check("no se guardan campos internos del formulario",
          not hasattr(report, "csrf_token") and not hasattr(report, "submit"))

    response = client.post(f"/admin/partidos/{match_id}/informe/estadistica", data={
        "player_id": str(player_id), "goals": "2", "assists": "1",
        "clean_sheets": "1", "own_goals": "0", "yellow_cards": "0",
        "red_cards": "0", "minutes": "20", "is_mvp": "y", "note": "Doblete",
    }, follow_redirects=True)
    check("anadir fila de estadisticas", response.status_code == 200)
    check("fila de estadisticas creada",
          q(app, lambda: PlayerMatchStat.query.filter_by(match_id=match_id, player_id=player_id).first()) is not None)
    check("el MVP del informe se actualiza solo",
          q(app, lambda: db.session.get(MatchReport, match_id).mvp_player_id) == player_id)

    response = client.post(f"/admin/partidos/{match_id}/informe/estadistica", data={
        "player_id": str(player_id), "goals": "5",
    }, follow_redirects=True)
    check("no permite dos filas del mismo jugador",
          q(app, lambda: PlayerMatchStat.query.filter_by(match_id=match_id, player_id=player_id).count()) == 1)

    response = client.post(f"/admin/partidos/{match_id}/informe/resultado", data={}, follow_redirects=True)
    check("calcular el resultado desde las estadisticas", response.status_code == 200)
    m = q(app, lambda: db.session.get(Match, match_id))
    check("marcador local = goles del jugador", m.home_score == 2, str(m.home_score))
    check("marcador visitante = 0", m.away_score == 0, str(m.away_score))

    response = client.post("/admin/estadisticas/recalcular", data={}, follow_redirects=True)
    check("recalcular estadisticas acumuladas", response.status_code == 200)
    p = q(app, lambda: db.session.get(Player, player_id))
    check("goles acumulados del jugador", p.goals == 2, str(p.goals))
    check("asistencias acumuladas", p.assists == 1, str(p.assists))
    check("clean sheets acumulados", p.clean_sheets == 1, str(p.clean_sheets))
    check("partidos acumulados", p.matches == 1, str(p.matches))
    def stats_snapshot():
        """Firma de lo acumulado: tiene que quedar igual al recomputar otra vez."""
        return (
            sorted((pl.id, pl.goals, pl.assists, pl.clean_sheets, pl.own_goals, pl.matches)
                   for pl in Player.query.all()),
            sorted((s.division_id, s.team_id, s.position, s.points, s.goal_difference)
                   for s in Standing.query.all()),
        )

    def recompute_again():
        recompute_player_stats()
        return stats_snapshot()

    before = q(app, stats_snapshot)
    q(app, recompute_again)
    after = q(app, stats_snapshot)
    check("la recomputacion global es idempotente", bool(before[0]) and before == after,
          f"antes={before} despues={after}")

    def seed_standing():
        """Una fila de tabla de posiciones: la seccion solo se pinta si hay datos."""
        division_id = q(app, lambda: db.session.get(Team, team_id).division_id)
        if not Standing.query.filter_by(division_id=division_id, team_id=team_id).first():
            db.session.add(Standing(division_id=division_id, team_id=team_id, played=1,
                                    won=1, drawn=0, lost=0, goals_for=2, goals_against=0,
                                    points=3, position=1))
            db.session.commit()

    q(app, seed_standing)

    print("\n=== 5. PAGINAS PUBLICAS ===")

    response = client.get(f"/partidos/{match_id}")
    check("el informe publico responde 200", response.status_code == 200)
    check("muestra el marcador", b'scoreboard' in response.data)
    check("muestra al goleador", b"diamante_01" in response.data)
    check("muestra la tabla de estadisticas", b"ESTADISTICAS DEL PARTIDO" in response.data)

    response = client.get("/estadisticas")
    check("la pagina de estadisticas responde 200", response.status_code == 200)
    check("incluye las dos divisiones",
          b"Division 1" in response.data and b"Division 2" in response.data)
    check("incluye la tabla de posiciones", b"standings-table" in response.data)
    check("incluye la tabla de estadisticas", b"ESTADISTICAS INDIVIDUALES" in response.data)
    return match_id, team_id


def test_password_flow(app, ids, client) -> None:
    print("\n=== 6. CORREO DE CONTRASENA ===")
    response = client.post("/auth/contrasena", data={
        "current_password": "adminmascapito", "new_password": "nuevaclave123",
        "confirm_password": "nuevaclave123",
    }, follow_redirects=True)
    check("cambio de contrasena", response.status_code == 200)
    check("se registro el aviso de cambio de contrasena",
          q(app, lambda: EmailLog.query.filter_by(template="password_changed").count()) == 1)

    client.post("/auth/logout")
    response = client.post("/auth/recuperar", data={"identifier": "admin@test.app"},
                           follow_redirects=True)
    check("pedir enlace de recuperacion", response.status_code == 200)
    check("se creo un token de recuperacion", q(app, lambda: PasswordResetToken.query.count()) == 1)

    import hashlib

    def prepare_token():
        record = PasswordResetToken.query.first()
        record.token_hash = hashlib.sha256(b"token-de-prueba").hexdigest()
        record.expires_at = utcnow().replace(year=utcnow().year + 10)
        db.session.commit()

    q(app, prepare_token)

    response = client.post("/auth/recuperar/token-de-prueba", data={
        "new_password": "restablecida123", "confirm_password": "restablecida123",
    }, follow_redirects=True)
    check("restablecer contrasena con el token", response.status_code == 200)

    def token_used():
        record = PasswordResetToken.query.first()
        return record.used_at is not None

    check("el token quedo consumido", q(app, token_used))
    check("la contrasena quedo actualizada",
          q(app, lambda: db.session.get(User, ids["admin_id"]).check_password("restablecida123"))
          or q(app, lambda: User.query.filter_by(username="admin").first().check_password("restablecida123")))

    response = client.get("/auth/recuperar/token-de-prueba", follow_redirects=True)
    check("el token no se puede reutilizar",
          b"no es valido o ya caduco" in response.data)


def test_cascade_delete(app, ids, team_id, match_id, client) -> None:
    print("\n=== 7. BORRADO DE EQUIPOS EN CASCADA ===")
    # El flujo de contrasena cerro la sesion del admin: hay que volver a entrar.
    client.post("/auth/login", data={"username": "admin", "password": "restablecida123"},
                follow_redirects=True)
    check("el admin sigue con sesion activa", client.get("/admin/").status_code == 200)
    response = client.post(f"/admin/equipos/{team_id}/eliminar", data={}, follow_redirects=True)
    check("borrar equipo", response.status_code == 200)

    check("el equipo ya no existe", q(app, lambda: db.session.get(Team, team_id)) is None)
    check("se borraron sus jugadores",
          q(app, lambda: Player.query.filter_by(team_id=team_id).count()) == 0)
    check("se borraron sus partidos", q(app, lambda: db.session.get(Match, match_id)) is None)
    check("no quedaron estadisticas huerfanas", q(app, lambda: PlayerMatchStat.query.count()) == 0)
    check("no quedaron informes huerfanos", q(app, lambda: MatchReport.query.count()) == 0)
    check("no quedaron filas de standings",
          q(app, lambda: Standing.query.filter_by(team_id=team_id).count()) == 0)


def test_permissions(app, ids, client) -> None:
    print("\n=== 8. PERMISOS ===")
    client.post("/auth/logout")
    response = client.get("/admin/equipos/1")
    check("sin sesion no se entra al panel", response.status_code in (302, 401, 403))

    staff_client = app.test_client()
    staff_client.post("/auth/login", data={"username": "staff1", "password": "staffpass"},
                      follow_redirects=True)
    check("el staff entra al panel", staff_client.get("/admin/").status_code == 200)
    check("el staff no ve el historial de correos", staff_client.get("/admin/correos").status_code == 403)

    def fixtures() -> dict[str, int]:
        """Dos partidos con informe: uno publicado y otro todavia en borrador."""
        made = {}
        for key, published in (("pub", True), ("draft", False)):
            home = Team(name=f"Local {key}", short=f"L{key}", division_id=ids["div1"])
            away = Team(name=f"Visitante {key}", short=f"V{key}", division_id=ids["div1"])
            db.session.add_all([home, away])
            db.session.flush()
            match = Match(division_id=ids["div1"], journey=1, home_team_id=home.id,
                          away_team_id=away.id, home_score=1, away_score=0,
                          status="finished", played_on=utcnow().date())
            db.session.add(match)
            db.session.flush()
            db.session.add(MatchReport(match_id=match.id, headline=f"Informe {key}",
                                       is_published=published))
            db.session.commit()
            made[key] = match.id
        return made

    made = q(app, fixtures)

    guest_client = app.test_client()
    check("un informe publicado es publico",
          guest_client.get(f"/partidos/{made['pub']}").status_code == 200)
    check("un borrador no es publico para cualquiera",
          guest_client.get(f"/partidos/{made['draft']}").status_code == 404)

    player_client = app.test_client()
    player_client.post("/auth/login", data={"username": "nuevo_jugador", "password": "secreto123"},
                       follow_redirects=True)
    check("un jugador registrado tampoco ve el borrador",
          player_client.get(f"/partidos/{made['draft']}").status_code == 404)
    check("el staff si ve su propio borrador",
          staff_client.get(f"/partidos/{made['draft']}").status_code == 200)



def test_auth_gate(app) -> None:
    """Con REQUIRE_LOGIN=1 la liga entera pide cuenta, menos login y assets."""
    print("\n=== 9. VALLA DE ACCESO ===")
    app.config["REQUIRE_LOGIN"] = True
    try:
        guest = app.test_client()

        for ruta in ("/", "/estadisticas", "/sugerencias", "/noticias/inexistente"):
            response = guest.get(ruta)
            check(f"sin sesion {ruta} va al login",
                  response.status_code == 302 and "/auth/login" in response.headers.get("Location", ""))

        check("el login es publico", guest.get("/auth/login").status_code == 200)
        check("el registro es publico", guest.get("/auth/register").status_code == 200)
        check("recuperar clave es publico", guest.get("/auth/recuperar").status_code == 200)
        check("los estilos se sirven sin sesion", guest.get("/static/css/style.css").status_code == 200)
        check("la sonda de salud responde", guest.get("/health").status_code in (200, 503))

        response = guest.get("/estadisticas")
        location = response.headers.get("Location", "")
        check("se recuerda la pagina pedida", "next=/estadisticas" in location, location)

        check("el panel redirige tambien", guest.get("/admin/").status_code == 302)
        check("la API responde 401 y no un HTML de login",
              guest.get("/api/matches").status_code == 401)

        player = app.test_client()
        player.post("/auth/login", data={"username": "nuevo_jugador", "password": "secreto123"},
                    follow_redirects=True)
        check("con sesion se entra a la pagina", player.get("/").status_code == 200)
        check("con sesion se ven las sugerencias", player.get("/sugerencias").status_code == 200)
    finally:
        app.config["REQUIRE_LOGIN"] = False


def test_suggestions(app, ids) -> None:
    """El canal guarda mensaje, autor, votos y la respuesta del staff."""
    print("\n=== 10. CANAL DE SUGERENCIAS ===")

    def crear() -> int:
        user = User.query.filter_by(username="nuevo_jugador").first()
        fila = Suggestion(user_id=user.id, category="mejora", title="Poner fotos a los escudos",
                          body="Los escudos se ven pequenos en el movil, AGRANDARLOS un poco mas.")
        db.session.add(fila)
        db.session.commit()
        return fila.id

    suggestion_id = q(app, crear)

    player = app.test_client()
    player.post("/auth/login", data={"username": "nuevo_jugador", "password": "secreto123"},
                follow_redirects=True)
    response = player.get("/sugerencias")
    check("el foro se abre para el jugador", response.status_code == 200)
    html = response.get_data(as_text=True)
    check("el mensaje aparece en el foro", "AGRANDARLOS" in html)
    check("el foro muestra el autor", "nuevo_jugador" in html)

    posted = player.post("/sugerencias", data={
        "category": "liga", "title": "Mas jornadas por temporada",
        "body": "Con 8 jornadas se acaba muy rapido la liga, propongo 12.",
    }, follow_redirects=True)
    check("se guarda una sugerencia nueva", posted.status_code == 200)
    check("se confirma el envio", "Gracias por opinar" in posted.get_data(as_text=True))

    def total() -> int:
        return Suggestion.query.count()

    check("la sugerencia quedo en la base", q(app, total) == 2)

    voted = player.post(f"/sugerencias/{suggestion_id}/voto", follow_redirects=True)
    check("el voto se registra", voted.status_code == 200)

    def votos() -> int:
        fila = db.session.get(Suggestion, suggestion_id)
        return (SuggestionVote.query.filter_by(suggestion_id=fila.id).count(), fila.likes)

    count, likes = q(app, votos)
    check("un voto cuenta una vez", count == 1 and likes == 1)

    player.post(f"/sugerencias/{suggestion_id}/voto", follow_redirects=True)
    count, likes = q(app, votos)
    check("se puede quitar el voto", count == 0 and likes == 0)

    # El admin cambio su clave en la prueba 6, asi que responde el usuario staff.
    staff = app.test_client()
    staff.post("/auth/login", data={"username": "staff1", "password": "staffpass"},
               follow_redirects=True)
    check("el panel lista las sugerencias", staff.get("/admin/sugerencias").status_code == 200)

    replied = staff.post(f"/admin/sugerencias/{suggestion_id}/responder", data={
        "status": "done", "staff_reply": "Hecho, los escudos ya se agrandan en movil.",
    }, follow_redirects=True)
    check("el staff responde la sugerencia", replied.status_code == 200)

    def estado() -> tuple:
        fila = db.session.get(Suggestion, suggestion_id)
        return fila.status, bool(fila.staff_reply), fila.replied_by_id is not None

    status, reply, con_autor = q(app, estado)
    check("la respuesta queda guardada", status == "done" and reply and con_autor)

    check("el jugador ve la respuesta del staff",
          "los escudos ya se agrandan" in player.get("/sugerencias").get_data(as_text=True))
    check("el correo al staff queda registrado",
          q(app, lambda: EmailLog.query.filter_by(template="suggestion").count()) >= 1)


def test_nulls_last(app, ids) -> None:
    """Los nulos van al final y el SQL no usa NULLS LAST (MySQL da error 1064)."""
    print("\n=== 11. ORDEN DE FECHAS NULLS LAST ===")
    from sqlalchemy.dialects import mysql

    from models import MuseumItem
    from utils import nulls_last

    def sembrar():
        MuseumItem.query.delete()
        fechas = ["2026-01-10", "2026-05-20", "2026-03-15", None]
        for index, fecha in enumerate(fechas):
            db.session.add(MuseumItem(
                title=f"Museo {index}", slug=f"museo-{index}", sort_order=index,
                awarded_on=None if fecha is None else datetime.date.fromisoformat(fecha),
            ))
        db.session.commit()

    q(app, sembrar)

    def titulos(descending: bool) -> list[str]:
        return [row.title for row in MuseumItem.query.order_by(
            *nulls_last(MuseumItem.awarded_on, descending=descending))]

    check("descendente: la fecha vacia queda al final", q(app, titulos, True)[-1] == "Museo 3")
    check("ascendente: la fecha vacia queda al final", q(app, titulos, False)[-1] == "Museo 3")

    def sql_mysql(descending: bool) -> str:
        columns = nulls_last(MuseumItem.awarded_on, descending=descending)
        return str(db.select(*columns).compile(dialect=mysql.dialect())).upper()

    check("el SQL no lleva NULLS LAST",
          "NULLS LAST" not in q(app, sql_mysql, True) and "NULLS LAST" not in q(app, sql_mysql, False))

    def borrar():
        MuseumItem.query.delete()
        db.session.commit()

    q(app, borrar)


def main() -> int:
    app = create_app("testing")
    try:
        return run(app)
    finally:
        # Sin esto Windows mantiene el .db bloqueado y el TemporaryDirectory no borra.
        with app.app_context():
            db.session.remove()
            db.engine.dispose()


def run(app) -> int:
    ids = seed(app)

    test_schema(app)
    test_register(app)
    client = login_admin(app)
    created = test_teams_and_reports(app, ids, client)
    if created:
        team_id, player_id = created
        match_id, team_id = test_match_report(app, ids, team_id, player_id, client)
        test_password_flow(app, ids, client)
        test_cascade_delete(app, ids, team_id, match_id, client)
    test_permissions(app, ids, client)
    test_auth_gate(app)
    test_suggestions(app, ids)
    test_nulls_last(app, ids)

    failed = [label for ok, label in results if not ok]
    print("\n" + "=" * 52)
    print(f"{len(results) - len(failed)}/{len(results)} pruebas OK")
    if failed:
        print("\nFALLARON:")
        for label in failed:
            print(f"  - {label}")
    print("=" * 52)
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())

