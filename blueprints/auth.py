"""Blueprint de autenticacion: registro, login, logout, perfil y contrasena."""
from __future__ import annotations

import hashlib
import secrets
from datetime import timedelta
from urllib.parse import urljoin, urlparse

from flask import Blueprint, abort, flash, redirect, render_template, request, session, url_for
from flask_login import current_user, login_required, login_user, logout_user
from sqlalchemy import func

from extensions import db
from forms import (
    ChangePasswordForm, ForgotPasswordForm, GoogleLinkForm, LoginForm, ProfileForm,
    RegisterForm, ResetPasswordForm,
)
from mailer import (
    notify_admins_new_user, send_password_changed_email, send_password_reset_email,
    send_welcome_email,
)
from models import PasswordResetToken, Role, User, log_activity
from utils import EMAIL_RE, USERNAME_RE, delete_upload, save_upload, utcnow

bp = Blueprint("auth", __name__, url_prefix="/auth")

SAFE_NEXT = {"auth.login", "site.index", "admin.dashboard"}
RESET_TOKEN_TTL = timedelta(hours=2)


def lower(column):
    """Comparacion case-insensitive portable entre SQLite/MySQL/PostgreSQL."""
    return func.lower(column)


def _is_safe_url(target: str) -> bool:
    """Evita redirecciones abiertas (open redirect)."""
    if not target:
        return False
    ref = urlparse(request.host_url)
    test = urlparse(urljoin(request.host_url, target))
    return test.scheme in ("http", "https") and ref.netloc == test.netloc


def _safe_next(default: str = "site.index") -> str:
    target = request.args.get("next") or request.form.get("next") or ""
    return target if _is_safe_url(target) else url_for(default)


def _hash_token(raw: str) -> str:
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


@bp.route("/register", methods=["GET", "POST"])
def register():
    if current_user.is_authenticated:
        return redirect(url_for("site.index"))

    form = RegisterForm()
    if form.validate_on_submit():
        username = form.username.data.strip()
        email = form.email.data.strip().lower()

        if User.query.filter(lower(User.username) == username.lower()).first():
            flash("Ese nombre de usuario ya esta registrado.", "error")
            return render_template("auth/register.html", form=form)
        if not EMAIL_RE.match(email):
            flash("El correo no tiene un formato valido.", "error")
            return render_template("auth/register.html", form=form)
        if User.query.filter(lower(User.email) == email).first():
            flash("Ese correo ya esta registrado.", "error")
            return render_template("auth/register.html", form=form)

        # Primer usuario = administrador de la liga (cuenta por defecto).
        is_first_user = User.query.count() == 0

        user = User(
            username=username,
            email=email,
            display_name=username,
            role=Role.ADMIN if is_first_user else Role.USER,
            is_admin=is_first_user,
            is_premium=is_first_user,
        )
        user.set_password(form.password.data)
        db.session.add(user)
        db.session.flush()
        log_activity(user, "crear", "usuario", user.id, f"registro de {username}")

        session.permanent = bool(form.data.get("remember"))
        login_user(user, remember=bool(form.data.get("remember")))
        user.last_login = utcnow()
        user.login_count = (user.login_count or 0) + 1
        db.session.commit()

        # Bienvenida al correo: usuario, que es la liga y donde entrar.
        send_welcome_email(user)
        if not is_first_user:
            notify_admins_new_user(user)

        if is_first_user:
            flash("Bienvenido. Eres el administrador principal de la liga.", "success")
            return redirect(url_for("admin.dashboard"))
        flash("Cuenta creada. Te enviamos la bienvenida por correo. Ya puedes entrar al panel.", "success")
        return redirect(url_for("site.index"))
    return render_template("auth/register.html", form=form)


@bp.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("site.index"))

    form = LoginForm()
    if form.validate_on_submit():
        identifier = form.username.data.strip()
        user = (
            User.query.filter(lower(User.username) == identifier.lower()).first()
            or User.query.filter(lower(User.email) == identifier.lower()).first()
        )
        if user is None or not user.check_password(form.password.data):
            flash("Usuario o contrasena incorrectos.", "error")
            return render_template("auth/login.html", form=form)
        if not user.is_active:
            flash("Tu cuenta esta desactivada. Contacta a la administracion.", "error")
            return render_template("auth/login.html", form=form)

        session.permanent = bool(form.remember.data)
        login_user(user, remember=bool(form.remember.data))
        user.last_login = utcnow()
        user.login_count = (user.login_count or 0) + 1
        log_activity(user, "login", "usuario", user.id)
        db.session.commit()

        flash(f"Hola de nuevo, {user.label}.", "success")
        if user.is_admin:
            return redirect(_safe_next("admin.dashboard"))
        return redirect(_safe_next("site.index"))
    return render_template("auth/login.html", form=form)


@bp.route("/logout", methods=["POST"])
@login_required
def logout():
    log_activity(current_user, "logout", "usuario", current_user.id)
    db.session.commit()
    logout_user()
    session.clear()
    flash("Sesion cerrada correctamente.", "info")
    return redirect(url_for("auth.login"))


@bp.route("/perfil", methods=["GET", "POST"])
@login_required
def profile():
    form = ProfileForm(obj=current_user)
    if form.validate_on_submit():
        user = current_user
        email = (form.email.data or "").strip().lower()
        if email and email != user.email and User.query.filter(
            db.func.lower(User.email) == email, User.id != user.id
        ).first():
            flash("Ese correo ya pertenece a otra cuenta.", "error")
            return render_template("auth/profile.html", form=form)

        if form.avatar.data:
            new_path = save_upload(form.avatar.data, subfolder="avatars")
            if new_path:
                delete_upload(user.avatar)
                user.avatar = new_path
        if form.remove_avatar.data:
            delete_upload(user.avatar)
            user.avatar = None

        user.display_name = (form.display_name.data or "").strip() or user.username
        user.email = email or user.email
        user.haxball_id = (form.haxball_id.data or "").strip()
        user.country = (form.country.data or "").strip()
        user.bio = (form.bio.data or "").strip()
        db.session.commit()
        flash("Perfil actualizado.", "success")
        return redirect(url_for("auth.profile"))
    return render_template("auth/profile.html", form=form)


@bp.route("/contrasena", methods=["GET", "POST"])
@login_required
def change_password():
    form = ChangePasswordForm()
    if form.validate_on_submit():
        if not current_user.check_password(form.current_password.data):
            flash("La contrasena actual no es correcta.", "error")
            return render_template("auth/change_password.html", form=form)
        changed_at = utcnow()
        current_user.set_password(form.new_password.data)
        log_activity(current_user, "cambio_password", "usuario", current_user.id)
        db.session.commit()
        # Aviso al correo: la contrasena cambio, con fecha y usuario.
        send_password_changed_email(current_user, changed_at)
        # Tras cambiar la contrasena se invalidan las otras sesiones abiertas.
        session.permanent = True
        flash("Contrasena actualizada. Te enviamos la confirmacion por correo.", "success")
        return redirect(url_for("auth.profile"))
    return render_template("auth/change_password.html", form=form)


@bp.route("/recuperar", methods=["GET", "POST"])
def forgot_password():
    """Pide el enlace de restablecimiento; siempre responde igual."""
    if current_user.is_authenticated:
        return redirect(url_for("auth.profile"))

    form = ForgotPasswordForm()
    if form.validate_on_submit():
        identifier = form.identifier.data.strip()
        user = (
            User.query.filter(lower(User.username) == identifier.lower()).first()
            or User.query.filter(lower(User.email) == identifier.lower()).first()
        )
        if user is not None and user.is_active:
            # Un token por solicitud; los anteriores quedan invalidados.
            PasswordResetToken.query.filter_by(user_id=user.id, used_at=None).delete()
            raw = secrets.token_urlsafe(32)
            db.session.add(
                PasswordResetToken(
                    user_id=user.id,
                    token_hash=_hash_token(raw),
                    expires_at=utcnow() + RESET_TOKEN_TTL,
                    requested_ip=request.headers.get("X-Forwarded-For", request.remote_addr or "")[:45],
                )
            )
            log_activity(user, "pide_reset", "usuario", user.id)
            db.session.commit()
            send_password_reset_email(user, raw)

        flash(
            "Si esa cuenta existe, te enviamos el enlace por correo. Revisa tambien la carpeta de spam.",
            "success",
        )
        return redirect(url_for("auth.login"))
    return render_template("auth/forgot_password.html", form=form)


@bp.route("/recuperar/<token>", methods=["GET", "POST"])
def reset_password(token: str):
    """Consume el token del correo y deja una contrasena nueva."""
    record = PasswordResetToken.query.filter_by(token_hash=_hash_token(token)).first()
    if record is None or not record.is_usable:
        flash("Ese enlace no es valido o ya caduco. Pide uno nuevo.", "error")
        return redirect(url_for("auth.forgot_password"))

    form = ResetPasswordForm()
    if form.validate_on_submit():
        user = record.user
        if user is None or not user.is_active:
            flash("Esa cuenta no esta disponible.", "error")
            return redirect(url_for("auth.forgot_password"))

        changed_at = utcnow()
        user.set_password(form.new_password.data)
        record.used_at = changed_at
        # Invalida el resto de tokens vivos de esa cuenta.
        PasswordResetToken.query.filter(
            PasswordResetToken.user_id == user.id, PasswordResetToken.used_at.is_(None)
        ).update({"used_at": changed_at}, synchronize_session=False)
        log_activity(user, "reset_password", "usuario", user.id)
        db.session.commit()

        send_password_changed_email(user, changed_at)
        flash("Contrasena restablecida. Ya puedes entrar con la nueva.", "success")
        return redirect(url_for("auth.login"))
    return render_template("auth/reset_password.html", form=form, token=token)


@bp.route("/google", methods=["GET", "POST"])
@login_required
def google():
    """Vinculacion manual de la cuenta de Google (hook para OAuth later)."""
    form = GoogleLinkForm(obj=current_user)
    if form.validate_on_submit():
        email = (form.google_email.data or "").strip().lower()
        if User.query.filter(db.func.lower(User.email) == email, User.id != current_user.id).first():
            flash("Ese correo ya esta en uso dentro de la pagina.", "error")
            return render_template("auth/google.html", form=form)
        current_user.google_email = email
        db.session.commit()
        flash("Cuenta de Google vinculada.", "success")
        return redirect(url_for("auth.profile"))
    return render_template("auth/google.html", form=form)


@bp.route("/refresh")
@login_required
def refresh():
    """Re-confirma la identidad: util si la sesion es muy antigua."""
    if request.method == "GET":
        return redirect(url_for("auth.profile"))
    return redirect(url_for("site.index"))


@bp.route("/modo/<mode>", methods=["POST"])
@login_required
def toggle_mode(mode: str):
    """Activa/desactiva el modo administrador o premium de la interfaz."""
    from forms import BooleanOnlyForm
    from models import setting

    form = BooleanOnlyForm()
    if not form.validate_on_submit():
        abort(400)

    if mode == "admin":
        if not current_user.is_admin:
            abort(403)
        session["admin_mode"] = not session.get("admin_mode", True)
        state = "activado" if session["admin_mode"] else "desactivado"
        flash(f"Modo administrador {state}.", "info")
    elif mode == "premium":
        if not current_user.is_premium and not current_user.is_admin:
            abort(403)
        session["premium_mode"] = not session.get("premium_mode", False)
        state = "activado" if session["premium_mode"] else "desactivado"
        flash(f"Modo premium {state}.", "info")
    else:
        abort(404)
    return redirect(request.referrer or url_for("site.index"))


def current_admin_mode() -> bool:
    """El modo admin de la interfaz (boton de la tuerca)."""
    if not current_user.is_authenticated or not current_user.is_admin:
        return False
    return session.get("admin_mode", True)


def current_premium_mode() -> bool:
    if not current_user.is_authenticated:
        return False
    if current_user.is_admin:
        return session.get("premium_mode", False)
    return current_user.is_premium and session.get("premium_mode", True)


def waffle_defaults() -> dict:
    """Datos que consume la tuerca de configuracion del header."""
    if not current_user.is_authenticated:
        return {}
    return {
        "admin_mode": current_admin_mode(),
        "premium_mode": current_premium_mode(),
        "can_admin": current_user.is_admin,
        "can_premium": current_user.is_premium or current_user.is_admin,
        "google_linked": bool(current_user.google_email),
    }