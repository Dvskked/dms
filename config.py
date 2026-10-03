"""Configuracion central de la aplicacion.

Todo es sobreescribible por variables de entorno (ver .env.example). La base de
datos por defecto es MySQL (Clever Cloud); si el servidor no responde se puede
caer de forma automatica a SQLite con SQLITE_FALLBACK=1 para seguir desarrollando.
"""
from __future__ import annotations

import os
from datetime import timedelta
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

from dotenv import load_dotenv

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


def sqlite_fallback_uri() -> str:
    return f"sqlite:///{BASE_DIR / 'instance' / 'diamonds_league.db'}"


def normalize_database_url(url: str) -> str:
    """Normaliza la URL para que todos los drivers funcionen igual.

    - `postgres://` y `mysql://` pasan a sus drivers con driver real.
    - MySQL siempre con `utf8mb4` (acentos, emojis y escudos).
    """
    if not url:
        return ""
    url = url.strip()
    if url.startswith("postgres://"):
        url = "postgresql://" + url[len("postgres://"):]
    if url.startswith("mysql://"):
        url = "mysql+pymysql://" + url[len("mysql://"):]

    parts = urlsplit(url)
    if parts.scheme.startswith("mysql"):
        query = parts.query
        if "charset=" not in query:
            query = f"{query}&charset=utf8mb4" if query else "charset=utf8mb4"
        url = urlunsplit((parts.scheme, parts.netloc, parts.path, query, ""))
    return url


class BaseConfig:
    # Crea las tablas ausentes al arrancar. Ponlo en False cuando trabajes
    # con migraciones: flask --app app db upgrade
    AUTO_CREATE_TABLES = _env_bool("AUTO_CREATE_TABLES", True)

    # --- Core -------------------------------------------------------------
    SECRET_KEY = os.getenv("SECRET_KEY", "cambia-esta-clave-en-produccion")
    DEBUG = _env_bool("DEBUG", True)
    TESTING = False

    # --- Base de datos ---------------------------------------------------
    # MySQL (Clever Cloud) por defecto; SQLite local como red de seguridad.
    #   mysql+pymysql://usuario:clave@host:3306/base?charset=utf8mb4
    _DB_URL = normalize_database_url(os.getenv("DATABASE_URL", ""))
    SQLALCHEMY_DATABASE_URI = _DB_URL or sqlite_fallback_uri()
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = {
        "pool_pre_ping": True,
        "pool_recycle": _env_int("DB_POOL_RECYCLE", 280),
        "pool_size": _env_int("DB_POOL_SIZE", 5),
        "max_overflow": _env_int("DB_MAX_OVERFLOW", 10),
    }
    # 1 = si MySQL no responde, la app arranca igual sobre SQLite (solo dev).
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


CONFIG_MAP = {
    "development": DevelopmentConfig,
    "testing": TestingConfig,
    "production": ProductionConfig,
    "default": DevelopmentConfig,
}


def get_config(name: str | None = None) -> type[BaseConfig]:
    key = (name or os.getenv("FLASK_ENV", "development")).lower()
    return CONFIG_MAP.get(key, DevelopmentConfig)