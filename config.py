"""Configuracion central de la aplicacion.

Todo es sobreescribible por variables de entorno (ver .env.example).

Bases de datos soportadas:

- **SQLite** en local (sin configurar nada): ``instance/diamonds_league.db``.
- **PostgreSQL** en produccion/Vercel mediante ``DATABASE_URL`` (Neon, Supabase,
  Railway...). En Vercel es obligatorio: no hay disco persistente.
- **MySQL** sigue funcionando por si el despliegue actual lo necesita.
"""
from __future__ import annotations

import os
from datetime import timedelta
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

from dotenv import load_dotenv
from sqlalchemy.pool import NullPool

BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")


def _env_bool(key: str, default: bool) -> bool:
    raw = os.getenv(key)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on", "si", "sí"}


def _env_int(key: str, default: int) -> int:
    try:
        return int(os.getenv(key, "") or default)
    except ValueError:
        return default


def _env_str(key: str, default: str = "") -> str:
    """Lee una variable de entorno tratando "" como "no definida".

    En `.env` es habitual dejar claves vacias como documentacion
    (por ejemplo `UPLOAD_FOLDER=`); sin esto la app se quedaria con rutas
    vacias y las subidas acabarian en el directorio de trabajo.
    """
    value = os.getenv(key)
    return value.strip() if value and value.strip() else default


def is_serverless() -> bool:
    """True en Vercel u otros entornos que levantan el WSGI por invocacion."""
    return _env_bool("SERVERLESS", bool(os.getenv("VERCEL")))


def sqlite_fallback_uri() -> str:
    return f"sqlite:///{BASE_DIR / 'instance' / 'diamonds_league.db'}"


def normalize_database_url(url: str) -> str:
    """Normaliza la URL para que todos los drivers funcionen igual.

    - `postgres://` pasa a `postgresql+psycopg://` (driver v3, el que hay en
      requirements.txt y el que usa Neon/Supabase).
    - `mysql://` pasa a `mysql+pymysql://` con `utf8mb4` siempre.
    """
    if not url:
        return ""
    url = url.strip()
    if url.startswith("postgres://"):
        url = "postgresql://" + url[len("postgres://"):]
    if url.startswith("postgresql://"):
        url = "postgresql+psycopg://" + url[len("postgresql://"):]
    if url.startswith("mysql://"):
        url = "mysql+pymysql://" + url[len("mysql://"):]

    parts = urlsplit(url)
    if parts.scheme.startswith("mysql"):
        query = parts.query
        if "charset=" not in query:
            query = f"{query}&charset=utf8mb4" if query else "charset=utf8mb4"
        url = urlunsplit((parts.scheme, parts.netloc, parts.path, query, ""))
    return url


def engine_options(serverless: bool) -> dict:
    """Opciones de pool segun el entorno.

    En Vercel cada peticion puede caer en una instancia distinta y el numero de
    conexiones simultaneas esta limitado por el plan del proveedor: se usa
    ``NullPool`` (una conexion por peticion, se cierra al terminar) en lugar de
    un pool persistente que podria agotar el limite.
    """
    if serverless:
        return {"poolclass": NullPool, "pool_pre_ping": True}
    return {
        "pool_pre_ping": True,
        "pool_recycle": _env_int("DB_POOL_RECYCLE", 280),
        "pool_size": _env_int("DB_POOL_SIZE", 5),
        "max_overflow": _env_int("DB_MAX_OVERFLOW", 10),
    }


class BaseConfig:
    # Crea las tablas ausentes al arrancar. En Vercel es la via normal (no hay
    # migraciones en el despliegue); en local ponlo en False cuando trabajes con
    # migraciones: flask --app app db upgrade
    AUTO_CREATE_TABLES = _env_bool("AUTO_CREATE_TABLES", True)

    # --- Core -------------------------------------------------------------
    SECRET_KEY = os.getenv("SECRET_KEY", "cambia-esta-clave-en-produccion")
    DEBUG = _env_bool("DEBUG", True)
    TESTING = False

    # --- Base de datos ---------------------------------------------------
    # SQLite local si no hay DATABASE_URL; PostgreSQL en Vercel.
    SERVERLESS = is_serverless()
    _DB_URL = normalize_database_url(os.getenv("DATABASE_URL", ""))
    SQLALCHEMY_DATABASE_URI = _DB_URL or sqlite_fallback_uri()
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = engine_options(SERVERLESS)
    # 1 = si el servidor no responde, la app arranca igual sobre SQLite (solo dev).
    SQLITE_FALLBACK = _env_bool("SQLITE_FALLBACK", not (os.getenv("FLASK_ENV", "development").lower() == "production"))
    DB_BOOTSTRAP = _env_bool("DB_BOOTSTRAP", True)  # seed de ajustes + admin al arrancar

    # --- Sesiones --------------------------------------------------------
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    SESSION_COOKIE_SECURE = _env_bool("SESSION_COOKIE_SECURE", False)
    PERMANENT_SESSION_LIFETIME = timedelta(days=int(os.getenv("SESSION_LIFETIME_DAYS", "14")))
    REMEMBER_COOKIE_HTTPONLY = True
    REMEMBER_COOKIE_SAMESITE = "Lax"

    # --- Seguridad / passwords -------------------------------------------
    # El proyecto guarda las contrasenas en texto plano por requerimiento
    # explicito del cliente. Poner en True para hashear con pbkdf2:sha256
    # sin cambiar ni el modelo ni las vistas.
    STORE_PASSWORDS_PLAINTEXT = _env_bool("STORE_PASSWORDS_PLAINTEXT", True)

    # --- Valla de acceso -------------------------------------------------
    # REQUIRE_LOGIN=0 deja la pagina abierta para revisarla sin cuenta.
    REQUIRE_LOGIN = _env_bool("REQUIRE_LOGIN", True)

    # --- Uploads ---------------------------------------------------------
    UPLOAD_FOLDER = _env_str("UPLOAD_FOLDER", str(BASE_DIR / "static" / "uploads"))
    # En Vercel el disco es efimero: lo que se sube se pierde en el siguiente
    # despliegue, asi que ahi las imagenes van por URL (campo `image_url`).
    UPLOADS_PERSISTENT = _env_bool("UPLOADS_PERSISTENT", not SERVERLESS)
    MAX_CONTENT_LENGTH = int(os.getenv("MAX_UPLOAD_MB", "6")) * 1024 * 1024
    ALLOWED_IMAGE_EXTENSIONS = {"png", "jpg", "jpeg", "webp", "gif", "svg"}
    ALLOWED_DOC_EXTENSIONS = {"pdf", "png", "jpg", "jpeg", "webp"}

    # --- App -------------------------------------------------------------
    ITEMS_PER_PAGE = 12
    SITE_NAME = os.getenv("SITE_NAME", "The Diamonds League")
    TWITCH_PARENT = os.getenv("TWITCH_PARENT", "localhost")
    ITEMS_PER_PAGE_ADMIN = 20

    # --- Correo (SMTP) ---------------------------------------------------
    # Gmail con contrasena de aplicacion:
    #   MAIL_SERVER=smtp.gmail.com  MAIL_PORT=465  MAIL_USE_SSL=1
    MAIL_ENABLED = _env_bool("MAIL_ENABLED", bool(os.getenv("MAIL_PASSWORD")))
    MAIL_SERVER = os.getenv("MAIL_SERVER", "smtp.gmail.com")
    MAIL_PORT = _env_int("MAIL_PORT", 465)
    MAIL_USE_SSL = _env_bool("MAIL_USE_SSL", True)
    MAIL_USE_TLS = _env_bool("MAIL_USE_TLS", False)
    MAIL_USERNAME = os.getenv("MAIL_USERNAME", "")
    MAIL_PASSWORD = os.getenv("MAIL_PASSWORD", "").replace(" ", "")
    MAIL_SENDER = os.getenv("MAIL_SENDER", "") or os.getenv("MAIL_USERNAME", "")
    MAIL_SENDER_NAME = os.getenv("MAIL_SENDER_NAME", os.getenv("SITE_NAME", "The Diamonds League"))
    MAIL_TIMEOUT = _env_int("MAIL_TIMEOUT", 15)
    MAIL_PUBLIC_URL = os.getenv("MAIL_PUBLIC_URL", "").rstrip("/")


class DevelopmentConfig(BaseConfig):
    DEBUG = True


class TestingConfig(BaseConfig):
    TESTING = True
    # En pruebas se puede apuntar a un fichero temporal (TEST_DATABASE_URL) para
    # evitar que varias sesiones compartan la misma transaccion en memoria.
    SQLALCHEMY_DATABASE_URI = os.getenv("TEST_DATABASE_URL") or "sqlite:///:memory:"
    SQLALCHEMY_ENGINE_OPTIONS = {}
    WTF_CSRF_ENABLED = False
    STORE_PASSWORDS_PLAINTEXT = True
    # La valla de acceso se prueba aparte; por defecto las pruebas entran directas.
    REQUIRE_LOGIN = False
    MAIL_ENABLED = False
    SQLITE_FALLBACK = False
    DB_BOOTSTRAP = False
    # En pruebas las subidas van a una carpeta aparte (TESTING_UPLOAD_FOLDER).
    UPLOAD_FOLDER = _env_str("TESTING_UPLOAD_FOLDER") or _env_str(
        "UPLOAD_FOLDER", str(BASE_DIR / "static" / "uploads")
    )


class ProductionConfig(BaseConfig):
    DEBUG = False
    SESSION_COOKIE_SECURE = True
    SQLITE_FALLBACK = False
    STORE_PASSWORDS_PLAINTEXT = _env_bool("STORE_PASSWORDS_PLAINTEXT", False)

    @classmethod
    def validate(cls) -> None:
        """Falla rapido y con un mensaje claro si falta algo de produccion."""
        problems = []
        if cls.SQLALCHEMY_DATABASE_URI.startswith("sqlite"):
            problems.append(
                "DATABASE_URL debe apuntar a PostgreSQL en produccion "
                "(Neon, Supabase, Railway...). En Vercel no hay disco para SQLite."
            )
        if cls.SQLALCHEMY_DATABASE_URI.startswith("mysql"):
            problems.append(
                "MySQL ya no es el motor de produccion soportado: usa PostgreSQL."
            )
        if cls.SECRET_KEY == "cambia-esta-clave-en-produccion":
            problems.append("SECRET_KEY sigue con el valor de ejemplo: define uno propio.")
        if problems:
            raise RuntimeError("Configuracion de produccion incompleta:\n- " + "\n- ".join(problems))


CONFIG_MAP = {
    "development": DevelopmentConfig,
    "testing": TestingConfig,
    "production": ProductionConfig,
    "default": DevelopmentConfig,
}


def get_config(name: str | None = None) -> type[BaseConfig]:
    key = (name or os.getenv("FLASK_ENV", "development")).lower()
    return CONFIG_MAP.get(key, DevelopmentConfig)