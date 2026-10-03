"""Configuracion central de la aplicacion.

Todo es sobreescribible por variables de entorno (ver .env.example) para que
mas adelante se pueda conectar a MySQL / PostgreSQL sin tocar codigo.
"""
from __future__ import annotations

import os
from datetime import timedelta
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")


def _env_bool(key: str, default: bool) -> bool:
    raw = os.getenv(key)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on", "si", "sí"}


class BaseConfig:
    # Crea las tablas ausentes al arrancar. Ponlo en False cuando trabajes
    # con migraciones: flask --app app db upgrade
    AUTO_CREATE_TABLES = _env_bool("AUTO_CREATE_TABLES", True)
    # --- Core -------------------------------------------------------------
    SECRET_KEY = os.getenv("SECRET_KEY", "cambia-esta-clave-en-produccion")
    DEBUG = _env_bool("DEBUG", True)
    TESTING = False

    # --- Base de datos ---------------------------------------------------
    # SQLite por defecto. Para MySQL:
    #   mysql+pymysql://usuario:clave@127.0.0.1:3306/diamonds_league?charset=utf8mb4
    # Para PostgreSQL:
    #   postgresql+psycopg://usuario:clave@127.0.0.1:5432/diamonds_league
    SQLALCHEMY_DATABASE_URI = os.getenv("DATABASE_URL", f"sqlite:///{BASE_DIR / 'instance' / 'diamonds_league.db'}")
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = {
        "pool_pre_ping": True,
        "pool_recycle": 280,
    }

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

    # --- Uploads ---------------------------------------------------------
    UPLOAD_FOLDER = os.getenv("UPLOAD_FOLDER", str(BASE_DIR / "static" / "uploads"))
    MAX_CONTENT_LENGTH = int(os.getenv("MAX_UPLOAD_MB", "6")) * 1024 * 1024
    ALLOWED_IMAGE_EXTENSIONS = {"png", "jpg", "jpeg", "webp", "gif", "svg"}
    ALLOWED_DOC_EXTENSIONS = {"pdf", "png", "jpg", "jpeg", "webp"}

    # --- App -------------------------------------------------------------
    ITEMS_PER_PAGE = 12
    SITE_NAME = os.getenv("SITE_NAME", "The Diamonds League")
    TWITCH_PARENT = os.getenv("TWITCH_PARENT", "localhost")
    ITEMS_PER_PAGE_ADMIN = 20


class DevelopmentConfig(BaseConfig):
    DEBUG = True


class TestingConfig(BaseConfig):
    TESTING = True
    SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"
    WTF_CSRF_ENABLED = False
    STORE_PASSWORDS_PLAINTEXT = True


class ProductionConfig(BaseConfig):
    DEBUG = False
    SESSION_COOKIE_SECURE = True


CONFIG_MAP = {
    "development": DevelopmentConfig,
    "testing": TestingConfig,
    "production": ProductionConfig,
    "default": DevelopmentConfig,
}


def get_config(name: str | None = None) -> type[BaseConfig]:
    key = (name or os.getenv("FLASK_ENV", "development")).lower()
    return CONFIG_MAP.get(key, DevelopmentConfig)