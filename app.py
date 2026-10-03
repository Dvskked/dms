"""The Diamonds League — aplicacion web (Flask).

Arranque:      python app.py
Consola admin: flask --app app shell
Migraciones:   flask --app app db init / migrate / upgrade
"""
from __future__ import annotations

import os
from datetime import date
from pathlib import Path

from flask import Flask, jsonify, render_template, request, session
from flask_login import current_user
from flask_wtf.csrf import generate_csrf

from blueprints import BLUEPRINTS
from blueprints.auth import current_admin_mode, current_premium_mode
from config import BASE_DIR, get_config
from extensions import csrf, db, login_manager, migrate
from models import Role, SiteSetting, User, set_setting

__version__ = "1.0.0"


def create_app(config_name: str | None = None) -> Flask:
    app = Flask(__name__, instance_relative_config=False)
    app.config.from_object(get_config(config_name))

    Path(app.instance_path).mkdir(parents=True, exist_ok=True)
    Path(app.config["UPLOAD_FOLDER"]).mkdir(parents=True, exist_ok=True)

    db.init_app(app)
    migrate.init_app(app, db)
    login_manager.init_app(app)
    csrf.init_app(app)

    for bp in BLUEPRINTS:
        app.register_blueprint(bp)

    register_error_handlers(app)
    register_context(app)
    register_cli(app)
    register_filters(app)

    with app.app_context():
        # En desarrollo se crean las tablas si faltan; con migraciones aplicadas
        # se respeta el esquema versionado (AUTO_CREATE_TABLES=0).
        if app.config.get("AUTO_CREATE_TABLES", True):
            db.create_all()
        if _schema_ready():
            if User.query.count() == 0:
                _bootstrap_admin()
            if SiteSetting.query.count() == 0:
                for key, value, group in _DEFAULT_SETTINGS:
                    set_setting(key, value, group=group)
            db.session.commit()

    return app


def _schema_ready() -> bool:
    """True si las tablas base ya existen en la base de datos."""
    from sqlalchemy import inspect

    return {"users", "site_settings"}.issubset(set(inspect(db.engine).get_table_names()))


def _bootstrap_admin() -> None:
    """Cuenta administradora por defecto, creada solo si la tabla esta vacia."""
    admin = User(
        username=os.getenv("ADMIN_USERNAME", "admin"),
        email=os.getenv("ADMIN_EMAIL", "admin@diamondsleague.app"),
        display_name=os.getenv("ADMIN_DISPLAY_NAME", "Administracion"),
        role=Role.ADMIN,
        is_admin=True,
        is_premium=True,
        bio="Cuenta principal de administracion de The Diamonds League.",
    )
    admin.set_password(os.getenv("ADMIN_PASSWORD", "adminmascapito"))
    db.session.add(admin)


_DEFAULT_SETTINGS = [
    ("league_name", "The Diamonds League", "liga"),
    ("league_tagline", "Liga competitiva de HaxBall X5", "liga"),
    ("league_modality", "5 VS 5 · X5", "liga"),
    ("league_status", "ACTIVA", "liga"),
    ("league_description", "La liga competitiva de HaxBall donde compiten los mejores clubes de la comunidad.", "liga"),
    ("live_headline", "LIVE FUTBOL", "streams"),
    ("live_description", "Transmisiones de futbol en vivo. Abre el canal y mira desde aqui.", "streams"),
    ("donation_headline", "DONACION", "donacion"),
    ("donation_description", "Tu apoyo sostiene los servidores, los premios y la Temporada 3.", "donacion"),
    ("donation_note", "Cada aporte se usa para premiar a los mejores jugadores de la liga.", "donacion"),
    ("show_premium_panel", "1", "avances"),
    ("show_admin_shortcut", "1", "avances"),
    ("maintenance_mode", "0", "avances"),
]


# --------------------------------------------------------------------------- #
# Contexto global para las plantillas
# --------------------------------------------------------------------------- #
def register_context(app: Flask) -> None:
    @app.context_processor
    def inject_globals():
        prefs = {
            "admin_mode": False,
            "premium_mode": False,
            "can_admin_mode": False,
            "can_premium_mode": False,
            "google_linked": False,
        }
        if current_user.is_authenticated:
            prefs.update(
                admin_mode=current_admin_mode(),
                premium_mode=current_premium_mode(),
                can_admin_mode=current_user.is_admin,
                can_premium_mode=current_user.is_premium or current_user.is_admin,
                google_linked=bool(current_user.google_email),
            )

        return {
            "app_name": app.config.get("SITE_NAME", "The Diamonds League"),
            "app_version": __version__,
            "csrf_token": generate_csrf(),
            "site_settings": _settings_map(),
            "prefs": prefs,
            "current_year": date.today().year,
        }


def _settings_map() -> dict:
    from models import SiteSetting

    try:
        return {row.key: row.value for row in SiteSetting.query.all()}
    except Exception:  # pragma: no cover - antes de crear tablas
        return {}


# --------------------------------------------------------------------------- #
# Filtros de plantilla
# --------------------------------------------------------------------------- #
def register_filters(app: Flask) -> None:
    from utils import excerpt, format_date, rich_text

    app.jinja_env.filters["rich"] = rich_text
    app.jinja_env.filters["fdate"] = format_date
    app.jinja_env.filters["excerpt"] = excerpt
    app.jinja_env.globals["has_request_context"] = lambda: True


# --------------------------------------------------------------------------- #
# Errores
# --------------------------------------------------------------------------- #
def register_error_handlers(app: Flask) -> None:
    def render_error(code: int, message: str, hint: str = ""):
        if request.path.startswith("/admin") or request.path.startswith("/auth"):
            template = "errors/admin.html" if code in (403, 404) else "errors/generic.html"
        else:
            template = "errors/generic.html"
        return render_template(template, code=code, message=message, hint=hint), code

    @app.errorhandler(400)
    def bad_request(_e):
        return render_error(400, "Solicitud invalida.", "Revisa los datos enviados e intentalo de nuevo.")

    @app.errorhandler(401)
    def unauthorized(_e):
        return render_error(401, "No autorizado.", "Necesitas iniciar sesion.")

    @app.errorhandler(403)
    def forbidden(_e):
        return render_error(403, "Acceso restringido.", "Tu cuenta no tiene permisos para esta zona.")

    @app.errorhandler(404)
    def not_found(_e):
        return render_error(404, "Pagina no encontrada.", "El enlace que buscas no existe o cambio de lugar.")

    @app.errorhandler(413)
    def too_large(_e):
        return render_error(413, "Archivo demasiado pesado.", f"El limite es {app.config['MAX_CONTENT_LENGTH'] // 1048576} MB.")

    @app.errorhandler(500)
    def server_error(e):  # pragma: no cover
        app.logger.exception("Error interno: %s", e)
        return render_error(500, "Error interno del servidor.", "Ya fue registrado. Intenta en un momento.")

    @app.errorhandler(429)
    def too_many(_e):
        return render_error(429, "Demasiadas solicitudes.", "Espera unos segundos antes de reintentar.")


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #
def register_cli(app: Flask) -> None:
    import click

    @app.cli.command("init-db")
    def init_db():
        """Crea las tablas y el usuario administrador por defecto."""
        db.create_all()
        if User.query.count() == 0:
            _bootstrap_admin()
            db.session.commit()
            click.secho("Usuario administrador creado: admin / adminmascapito", fg="cyan")
        click.secho("Base de datos lista.", fg="green")

    @app.cli.command("seed")
    @click.option("--force", is_flag=True, help="Vuelve a insertar datos aunque ya existan.")
    def seed_cmd(force):
        """Carga la informacion inicial de la liga."""
        from seed import seed_all

        seed_all(force=force)

    @app.cli.command("create-admin")
    @click.argument("username")
    @click.argument("password")
    @click.option("--email", default=None)
    def create_admin(username, password, email):
        from models import Role as R

        if User.query.filter_by(username=username).first():
            click.secho("Ese usuario ya existe.", fg="yellow")
            return
        user = User(
            username=username,
            email=email or f"{username}@diamondsleague.app",
            display_name=username,
            role=R.ADMIN,
            is_admin=True,
            is_premium=True,
        )
        user.set_password(password)
        db.session.add(user)
        db.session.commit()
        click.secho(f"Administrador {username} creado.", fg="green")

    @app.shell_context_processor
    def shell_context():
        import models

        return {"db": db, **{
            name: getattr(models, name) for name in models.__all__ if name not in {"db", "utcnow", "date"}
        }}


app = create_app()


@app.after_request
def security_headers(response):
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("X-Frame-Options", "SAMEORIGIN")
    response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
    response.headers.setdefault("X-DNS-Prefetch-Control", "off")
    response.headers["Cache-Control"] = response.headers.get("Cache-Control", "no-cache, must-revalidate")
    return response


@app.context_processor
def _inject_path():
    return {"request_path": request.path}


if __name__ == "__main__":
    app.run(
        host=os.getenv("HOST", "127.0.0.1"),
        port=int(os.getenv("PORT", "5000")),
        debug=app.config["DEBUG"],
    )