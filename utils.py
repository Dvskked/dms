"""Utilidades transversales: passwords, seguridad de texto, uploads, formato."""
from __future__ import annotations

import os
import re
import secrets
import unicodedata
from datetime import datetime, timezone
from pathlib import Path

from flask import current_app
from markupsafe import Markup, escape
from werkzeug.security import check_password_hash, generate_password_hash
from werkzeug.utils import secure_filename

USERNAME_RE = re.compile(r"^[A-Za-z0-9_.-]{3,24}$")
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[A-Za-z]{2,}$")
SLUG_STRIP_RE = re.compile(r"[^a-z0-9]+")


# --------------------------------------------------------------------------- #
# Fechas
# --------------------------------------------------------------------------- #
def utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def slugify(value: str, max_length: int = 90) -> str:
    """Normaliza a un slug ascii en minusculas."""
    normalized = unicodedata.normalize("NFKD", value or "")
    ascii_text = normalized.encode("ascii", "ignore").decode("ascii").lower()
    slug = SLUG_STRIP_RE.sub("-", ascii_text).strip("-")
    return (slug[:max_length].rstrip("-")) or "sin-titulo"


def parse_date(value: str | None):
    """Acepta YYYY-MM-DD o DD/MM/YYYY. Devuelve date o None."""
    if not value:
        return None
    value = value.strip()
    for fmt in ("%Y-%m-%d", "%d/%m/%Y"):
        try:
            return datetime.strptime(value, fmt).date()
        except ValueError:
            continue
    return None


def parse_datetime(value: str | None):
    """Acepta 'YYYY-MM-DDTHH:MM' o 'DD/MM/YYYY HH:MM'."""
    if not value:
        return None
    value = value.strip().replace(" ", "T")
    for fmt in ("%Y-%m-%dT%H:%M", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d"):
        try:
            return datetime.strptime(value[: len(fmt) + 2], fmt)
        except ValueError:
            continue
    return None


def format_date(value, fmt: str = "%d/%m/%Y") -> str:
    if not value:
        return "—"
    if isinstance(value, datetime):
        return value.strftime(fmt)
    return value.strftime(fmt)


# --------------------------------------------------------------------------- #
# Passwords
# --------------------------------------------------------------------------- #
def hash_password(raw: str) -> str:
    """Guarda en texto plano (configuracion por defecto del proyecto) o hashea."""
    if current_app.config.get("STORE_PASSWORDS_PLAINTEXT", True):
        return raw
    return generate_password_hash(raw, method="pbkdf2:sha256:260000")


def verify_password(stored: str, raw: str) -> bool:
    if not stored:
        return False
    if stored.startswith(("pbkdf2:", "scrypt:", "argon2")):
        return check_password_hash(stored, raw)
    return secrets.compare_digest(stored, raw)


# --------------------------------------------------------------------------- #
# Texto seguro (los datos viene del admin -> hay que escapar siempre)
# --------------------------------------------------------------------------- #
_ALLOWED_TAGS = {
    "p", "br", "b", "strong", "i", "em", "u", "ul", "ol", "li",
    "h3", "h4", "blockquote", "a", "code", "pre", "span", "hr",
}
_TAG_RE = re.compile(r"</?([a-zA-Z0-9]+)((?:\s+[^<>]*?)?)/?>")
_ATTR_RE = re.compile(r"""\s+(on\w+|style|srcset|formaction)\s*=\s*("[^"]*"|'[^']*'|[^\s>]+)""", re.I)
_HREF_RE = re.compile(r"""href\s*=\s*(["'])\s*javascript:[^"']*\1""", re.I)


def rich_text(value: str) -> Markup:
    """Escapa HTML y permite solo un subconjunto seguro de etiquetas."""
    if not value:
        return Markup("")
    cleaned = _TAG_RE.sub(_safe_tag, escape(value))
    cleaned = _ATTR_RE.sub("", cleaned)
    cleaned = _HREF_RE.sub('href="#"', cleaned)
    return Markup(cleaned)


def _safe_tag(match: re.Match) -> str:
    name = match.group(1).lower()
    original = match.group(0)
    if name not in _ALLOWED_TAGS:
        return ""
    if name == "a":
        return re.sub(r"""href\s*=\s*"([^"]*)"|href\s*=\s*'([^']*)'""",
                      lambda m: ' href="%s" target="_blank" rel="noopener noreferrer"'
                      % (m.group(1) or m.group(2)), original)
    return original


def excerpt(value: str | None, length: int = 180) -> str:
    if not value:
        return ""
    text = re.sub(r"<[^>]+>", " ", value)
    text = re.sub(r"\s+", " ", text).strip()
    return text if len(text) <= length else text[: length - 1].rstrip() + "…"


# --------------------------------------------------------------------------- #
# Uploads
# --------------------------------------------------------------------------- #
def allowed_file(filename: str, doc: bool = False) -> bool:
    if "." not in filename:
        return False
    ext = filename.rsplit(".", 1)[1].lower()
    allowed = current_app.config["ALLOWED_DOC_EXTENSIONS"] if doc else current_app.config["ALLOWED_IMAGE_EXTENSIONS"]
    return ext in allowed


def save_upload(file_storage, subfolder: str = "", doc: bool = False) -> str | None:
    if not file_storage or not file_storage.filename:
        return None
    if not allowed_file(file_storage.filename, doc=doc):
        raise ValueError("Formato de archivo no permitido.")

    folder = Path(current_app.config["UPLOAD_FOLDER"]) / subfolder if subfolder else Path(current_app.config["UPLOAD_FOLDER"])
    folder.mkdir(parents=True, exist_ok=True)

    stem, ext = os.path.splitext(secure_filename(file_storage.filename))
    filename = f"{stem}-{secrets.token_hex(4)}{ext.lower()}"
    file_storage.save(folder / filename)

    rel = f"{subfolder}/{filename}" if subfolder else filename
    return f"uploads/{rel.replace(os.sep, '/')}"


def delete_upload(relative_path: str | None) -> None:
    """Borra un archivo subido si existe y vive dentro de UPLOAD_FOLDER."""
    if not relative_path or not relative_path.startswith("uploads/"):
        return
    root = Path(current_app.config["UPLOAD_FOLDER"]).resolve()
    target = (root / relative_path[len("uploads/"):]).resolve()
    if root in target.parents and target.is_file():
        target.unlink(missing_ok=True)