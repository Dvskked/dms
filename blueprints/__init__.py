"""Registro de blueprints."""
from __future__ import annotations

from blueprints.admin import bp as admin_bp
from blueprints.auth import bp as auth_bp
from blueprints.site import bp as site_bp

BLUEPRINTS = (site_bp, auth_bp, admin_bp)

__all__ = ["BLUEPRINTS", "site_bp", "auth_bp", "admin_bp"]