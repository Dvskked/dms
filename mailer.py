"""Envio de correos por SMTP (Gmail con contrasena de aplicacion).

Sin dependencias externas: usa smtplib de la libreria estandar.
Todos los correos se registran en la tabla `email_logs` para que el staff
pueda revisar que salio y que fallo.
"""
from __future__ import annotations

import smtplib
from email.message import EmailMessage
from email.utils import formataddr, formatdate, make_msgid

from flask import current_app, url_for

from extensions import db
from models import EmailLog

__all__ = [
    "send_email", "send_welcome_email", "send_password_changed_email",
    "send_password_reset_email", "send_test_email", "notify_admins_new_user",
    "notify_staff_new_suggestion", "send_suggestion_notice", "send_suggestion_reply_email",
    "mail_enabled",
]


# --------------------------------------------------------------------------- #
# Plantilla base
# --------------------------------------------------------------------------- #
def _layout(title: str, preheader: str, blocks: list[str]) -> str:
    """HTML del correo: la misma paleta neon del sitio, en modo email."""
    return f"""<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{title}</title>
</head>
<body style="margin:0;padding:0;background:#08090c;">
<div style="display:none;max-height:0;overflow:hidden;opacity:0;">{preheader}</div>
<table role="presentation" width="100%" cellpadding="0" cellspacing="0"
       style="background:#08090c;padding:32px 12px;">
  <tr>
    <td align="center">
      <table role="presentation" width="100%" cellpadding="0" cellspacing="0"
             style="max-width:600px;background:#101218;border:1px solid #1e222c;border-radius:14px;overflow:hidden;">

        <tr>
          <td style="padding:26px 30px;border-bottom:1px solid #1e222c;">
            <span style="font:700 13px/1 'IBM Plex Mono',monospace;letter-spacing:.22em;
                         text-transform:uppercase;color:#1bebf2;">The Diamonds League</span>
            <h1 style="margin:12px 0 0;font:800 26px/1.15 'Bebas Neue',Impact,sans-serif;
                       letter-spacing:.02em;color:#ffffff;">{title}</h1>
          </td>
        </tr>

        <tr>
          <td style="padding:30px;font:400 15px/1.65 Inter,-apple-system,Segoe UI,Roboto,sans-serif;color:#c3c9d6;">
            {blocks[0]}
          </td>
        </tr>

        <tr>
          <td style="padding:22px 30px;background:#0b0d12;border-top:1px solid #1e222c;">
            <p style="margin:0 0 6px;font:700 11px/1.5 'IBM Plex Mono',monospace;
                      letter-spacing:.18em;text-transform:uppercase;color:#6b7386;">
              Liga competitiva de HaxBall X5</p>
            <p style="margin:0;font:400 12px/1.6 Inter,sans-serif;color:#5c6376;">
              No respondas a este correo. Si no esperabas este mensaje,
              ignoralo o escribe al staff de la liga.</p>
          </td>
        </tr>

      </table>
    </td>
  </tr>
</table>
</body>
</html>"""


def _button(label: str, url: str) -> str:
    return f"""<p style="margin:26px 0;">
      <a href="{url}" style="display:inline-block;background:#1bebf2;color:#04121a;
         font:700 12px/1 'IBM Plex Mono',monospace;letter-spacing:.16em;text-transform:uppercase;
         text-decoration:none;padding:14px 24px;border-radius:8px;">
        {label}</a>
</p>
<p style="margin:0;font:400 12px/1.6 'IBM Plex Mono',monospace;color:#6b7386;word-break:break-all;">
  {url}</p>"""


def _facts(rows: list[tuple[str, str]]) -> str:
    cells = "".join(
        f"""<tr>
          <td style="padding:9px 0;border-bottom:1px solid #1a1e26;color:#6b7386;
                     font:400 12px/1.4 'IBM Plex Mono',monospace;letter-spacing:.12em;
                     text-transform:uppercase;width:38%;">{label}</td>
          <td style="padding:9px 0;border-bottom:1px solid #1a1e26;color:#ffffff;
                     font:700 14px/1.4 Inter,sans-serif;">{value}</td>
        </tr>"""
        for label, value in rows
    )
    return f'<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="margin:22px 0;">{cells}</table>'


# --------------------------------------------------------------------------- #
# Envio
# --------------------------------------------------------------------------- #
def mail_enabled() -> bool:
    try:
        cfg = current_app.config
    except RuntimeError:
        return False
    return bool(cfg.get("MAIL_ENABLED")) and bool(cfg.get("MAIL_USERNAME")) and bool(cfg.get("MAIL_PASSWORD"))


def _public_url() -> str:
    return (current_app.config.get("MAIL_PUBLIC_URL") or "").rstrip("/")


def _absolute(url: str) -> str:
    return f"{_public_url()}{url}" if url.startswith("/") else url


def _link(endpoint: str, **values) -> str:
    """URL absoluta de un endpoint, valida tambien desde la consola.

    Los avisos salen a veces desde un comando (`flask send-test`), donde no hay
    contexto de peticion; por eso se construye la ruta sin `_external` y se
    antepone MAIL_PUBLIC_URL.
    """
    try:
        path = url_for(endpoint, **values)
    except RuntimeError:
        with current_app.test_request_context():
            path = url_for(endpoint, **values)
    return _absolute(path)


def _log_email(user, to_email: str, subject: str, template: str, status: str, error: str = "") -> None:
    try:
        db.session.add(
            EmailLog(
                user_id=getattr(user, "id", None),
                to_email=(to_email or "")[:160],
                subject=subject[:180],
                template=template,
                status=status,
                error=error[:255] or None,
            )
        )
        db.session.commit()
    except Exception:  # noqa: BLE001 - el log nunca debe romper la web
        db.session.rollback()


def send_email(to_email: str, subject: str, html: str, user=None, template: str = "general") -> bool:
    """Envia un correo y lo registra. Nunca lanza: devuelve True/False."""
    if not to_email:
        _log_email(user, "", subject, template, "skipped", "Sin destinatario")
        return False

    cfg = current_app.config
    if not mail_enabled():
        current_app.logger.info("[mail] SMTP desactivado; se omite «%s» para %s", subject, to_email)
        _log_email(user, to_email, subject, template, "skipped", "SMTP desactivado")
        return False

    sender = cfg.get("MAIL_SENDER") or cfg["MAIL_USERNAME"]
    message = EmailMessage()
    message["Subject"] = subject
    message["From"] = formataddr((cfg.get("MAIL_SENDER_NAME", "The Diamonds League"), sender))
    message["To"] = to_email
    message["Date"] = formatdate(localtime=True)
    message["Message-ID"] = make_msgid(domain=sender.split("@")[-1] if "@" in sender else None)
    message.set_content(
        "Este mensaje necesita un visor compatible con HTML.\n\n"
        f"{subject}\n\n-- The Diamonds League"
    )
    message.add_alternative(html, subtype="html")

    try:
        timeout = cfg.get("MAIL_TIMEOUT", 15)
        if cfg.get("MAIL_USE_TLS"):
            server = smtplib.SMTP(cfg["MAIL_SERVER"], cfg["MAIL_PORT"], timeout=timeout)
            server.starttls()
        elif cfg.get("MAIL_USE_SSL"):
            server = smtplib.SMTP_SSL(cfg["MAIL_SERVER"], cfg["MAIL_PORT"], timeout=timeout)
        else:
            server = smtplib.SMTP(cfg["MAIL_SERVER"], cfg["MAIL_PORT"], timeout=timeout)
        try:
            with server:
                server.login(cfg["MAIL_USERNAME"], cfg["MAIL_PASSWORD"])
                server.send_message(message)
        except Exception:  # noqa: BLE001
            raise
    except Exception as exc:  # noqa: BLE001
        current_app.logger.warning("[mail] fallo enviando «%s» a %s: %s", subject, to_email, exc)
        _log_email(user, to_email, subject, template, "failed", str(exc))
        return False

    current_app.logger.info("[mail] enviado «%s» a %s", subject, to_email)
    _log_email(user, to_email, subject, template, "sent")
    return True


# --------------------------------------------------------------------------- #
# Correos de la aplicacion
# --------------------------------------------------------------------------- #
def send_welcome_email(user) -> bool:
    """Bienvenida al registrarse: usuario, acceso al panel y a que se espera."""
    league = current_app.config.get("SITE_NAME", "The Diamonds League")
    login_url = _link("auth.login")
    body = f"""
      <p style="margin:0 0 18px;font-size:17px;color:#ffffff;">¡Bienvenido a <strong style="color:#1bebf2;">{league}</strong>, {user.display_name or user.username}!</p>
      <p style="margin:0 0 16px;">Tu cuenta ya esta activa. Somos una liga competitiva de
      <strong style="color:#ffffff;">HaxBall 5 vs 5</strong> con dos divisiones, donde compiten
      los mejores clubes de la comunidad. Cada jornada se juega, se informa y se actualiza la tabla.</p>
      <p style="margin:0 0 16px;">Desde tu cuenta puedes seguir las tablas de posiciones, los informes
      de los partidos con las fotos y las estadisticas de cada jugador, y entrar al panel de la liga.</p>
      {_facts([
          ("Tu usuario", user.username),
          ("Correo", user.email),
          ("Acceso", "Administrador" if user.is_admin else ("Staff" if user.is_staff else "Jugador")),
          ("Tu perfil", _link("auth.profile")),
      ])}
      {_button("Entrar a mi cuenta", login_url)}
    """
    return send_email(
        user.email,
        f"Bienvenido a {league} · tu cuenta ya esta lista",
        _layout(f"Bienvenido a {league}", "Tu cuenta en la liga ya esta activa.", [body]),
        user=user,
        template="welcome",
    )


def send_password_changed_email(user, changed_at=None) -> bool:
    """Aviso de seguridad: la contrasena se acaba de cambiar."""
    league = current_app.config.get("SITE_NAME", "The Diamonds League")
    stamp = changed_at.strftime("%d/%m/%Y %H:%M UTC") if changed_at else "ahora mismo"
    body = f"""
      <p style="margin:0 0 18px;font-size:17px;color:#ffffff;">Contrasena actualizada</p>
      <p style="margin:0 0 16px;">Hola <strong>{user.display_name or user.username}</strong>: la contrasena
      de tu cuenta en {league} se cambio <strong style="color:#ffffff;">{stamp}</strong>.</p>
      {_facts([
          ("Usuario", user.username),
          ("Correo", user.email),
          ("Cambio", stamp),
          ("Sesiones abiertas", "Las demas sesiones tendran que entrar de nuevo"),
      ])}
      <p style="margin:18px 0 0;padding:14px 16px;border-left:3px solid #ff3b6b;background:#14161d;
                font-size:14px;color:#c3c9d6;">
        <strong style="color:#ff3b6b;">¿No fuiste tu?</strong> Restablece la contrasena de inmediato
        y avisale al staff de la liga.</p>
      {_button("Restablecer contrasena", _link("auth.forgot_password"))}
    """
    return send_email(
        user.email,
        f"Tu contrasena de {league} fue cambiada",
        _layout("Cambio de contrasena", f"Tu contrasena de {league} fue cambiada.", [body]),
        user=user,
        template="password_changed",
    )


def send_password_reset_email(user, token: str) -> bool:
    """Enlace de un solo uso para dejar una contrasena nueva."""
    from datetime import timedelta

    from utils import utcnow

    league = current_app.config.get("SITE_NAME", "The Diamonds League")
    reset_url = _link("auth.reset_password", token=token)
    expires = (utcnow() + timedelta(hours=2)).strftime("%d/%m/%Y %H:%M UTC")
    body = f"""
      <p style="margin:0 0 18px;font-size:17px;color:#ffffff;">Restablecer contrasena</p>
      <p style="margin:0 0 16px;">Hola <strong>{user.display_name or user.username}</strong>: pediste
      dejar una contrasena nueva para tu cuenta de {league}. Usa el boton para crear una.</p>
      {_button("Elegir nueva contrasena", reset_url)}
      {_facts([
          ("Usuario", user.username),
          ("Correo", user.email),
          ("El enlace vence", expires),
      ])}
      <p style="margin:18px 0 0;font-size:14px;color:#8a91a3;">
        Si no solicitaste esto, no hagas nada: tu contrasena actual sigue siendo valida.</p>
    """
    return send_email(
        user.email,
        f"Restablece tu contrasena de {league}",
        _layout("Restablecer contrasena", f"Enlace para dejar una contrasena nueva en {league}.", [body]),
        user=user,
        template="password_reset",
    )


def send_test_email(to_email: str) -> tuple[bool, str]:
    """Correo de comprobacion desde el comando `flask send-test-email`."""
    league = current_app.config.get("SITE_NAME", "The Diamonds League")
    body = f"""
      <p style="margin:0 0 16px;font-size:17px;color:#ffffff;">Conexion verificada</p>
      <p style="margin:0 0 16px;">Este es un correo de prueba de <strong style="color:#1bebf2;">{league}</strong>.
      Si lo estas leyendo, el servidor SMTP y la cuenta estan bien configurados.</p>
      {_facts([
          ("Servidor", current_app.config.get("MAIL_SERVER", "")),
          ("Puerto", current_app.config.get("MAIL_PORT", "")),
          ("Remitente", current_app.config.get("MAIL_SENDER") or current_app.config.get("MAIL_USERNAME", "")),
      ])}
    """
    ok = send_email(to_email, f"Prueba de correo · {league}",
                    _layout("Prueba de correo", "Prueba de configuracion SMTP.", [body]),
                    template="test")
    return ok, "" if ok else "revisa MAIL_USERNAME / MAIL_PASSWORD en .env"


def send_new_account_notice(user, admin) -> bool:
    """Avisa al adminstaff cada vez que se registra alguien nuevo."""
    league = current_app.config.get("SITE_NAME", "The Diamonds League")
    body = f"""
      <p style="margin:0 0 16px;font-size:17px;color:#ffffff;">Nuevo jugador en la liga</p>
      <p style="margin:0 0 16px;"><strong>{user.username}</strong> acaba de crear su cuenta en {league}.</p>
      {_facts([
          ("Usuario", user.username),
          ("Correo", user.email),
          ("Registro", user.created_at.strftime("%d/%m/%Y %H:%M UTC") if user.created_at else "-"),
      ])}
      {_button("Gestionar usuarios", _link("admin.list_resource", resource="usuarios"))}
    """
    return send_email(
        admin.email,
        f"Nueva cuenta en {league}: {user.username}",
        _layout("Nueva cuenta registrada", f"{user.username} se registro en {league}.", [body]),
        user=admin,
        template="new_account",
    )


def notify_admins_new_user(user) -> None:
    """Envia el aviso a todos los administradores activos (sin fallar si no hay)."""
    from models import User

    admins = User.query.filter(User.is_admin.is_(True), User.is_active_account.is_(True)).all()
    for admin in admins:
        if admin.id == getattr(user, "id", None):
            continue
        send_new_account_notice(user, admin)


def _escape(text: str) -> str:
    """Escapa el texto que viene de la base antes de meterlo en el HTML."""
    return (
        (text or "")
        .replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        .replace('"', "&quot;").replace("'", "&#39;")
    )


def send_suggestion_notice(suggestion, author, staff) -> bool:
    """Correo al staff: hay una opinion nueva en el canal de sugerencias."""
    league = current_app.config.get("SITE_NAME", "The Diamonds League")
    body = f"""
      <p style="margin:0 0 16px;font-size:17px;color:#ffffff;">Nueva sugerencia de la comunidad</p>
      <p style="margin:0 0 16px;"><strong>{_escape(author.label)}</strong>
      (<code>{_escape(author.username)}</code> · {_escape(author.email)}) opinio en el canal de
      sugerencias de {league}.</p>
      <div style="margin:22px 0;padding:16px 18px;border-left:3px solid #1bebf2;background:#14161d;">
        <p style="margin:0 0 8px;font:700 11px/1.4 'IBM Plex Mono',monospace;letter-spacing:.16em;
                  text-transform:uppercase;color:#8a91a3;">{_escape(suggestion.category_label)}</p>
        <p style="margin:0 0 10px;font-size:16px;color:#ffffff;">{_escape(suggestion.title)}</p>
        <p style="margin:0;font-size:14px;color:#c3c9d6;white-space:pre-wrap;">{_escape(suggestion.body)}</p>
      </div>
      {_facts([
          ("Usuario", f"{author.label} (@{author.username})"),
          ("Correo", author.email),
          ("Recibido", suggestion.created_at.strftime("%d/%m/%Y %H:%M UTC") if suggestion.created_at else "-"),
          ("Mensaje", f"#{suggestion.id}"),
      ])}
      {_button("Responder en el canal", _link("site.suggestions"))}
    """
    return send_email(
        staff.email,
        f"Sugerencia nueva en {league}: {suggestion.title}",
        _layout("Sugerencia de un jugador", f"{author.label} dejo una sugerencia.", [body]),
        user=staff,
        template="suggestion",
    )


def notify_staff_new_suggestion(suggestion, author) -> bool:
    """Reparte el aviso entre administradores y staff. Nunca rompe la web."""
    from models import User

    staff = User.query.filter(
        db.or_(
            User.is_admin.is_(True),
            User.role == "staff",
        ),
        User.is_active_account.is_(True),
    ).all()
    sent = False
    for member in staff:
        if member.id == getattr(author, "id", None):
            continue
        sent = send_suggestion_notice(suggestion, author, member) or sent
    return sent


def send_suggestion_reply_email(suggestion) -> bool:
    """Avisa al jugador de que el staff respondio a su sugerencia."""
    author = suggestion.author
    if author is None or not getattr(author, "email", ""):
        return False
    league = current_app.config.get("SITE_NAME", "The Diamonds League")
    body = f"""
      <p style="margin:0 0 16px;font-size:17px;color:#ffffff;">El staff respondio a tu sugerencia</p>
      <p style="margin:0 0 16px;">Hola <strong>{_escape(author.label)}</strong>: tu mensaje
      «{_escape(suggestion.title)}» en {league} cambio de estado a
      <strong style="color:#1bebf2;">{_escape(suggestion.status_label)}</strong>.</p>
      <div style="margin:22px 0;padding:16px 18px;border-left:3px solid #1bebf2;background:#14161d;">
        <p style="margin:0;font-size:14px;color:#c3c9d6;white-space:pre-wrap;">{_escape(suggestion.staff_reply)}</p>
      </div>
      {_button("Ver el canal de sugerencias", _link("site.suggestions"))}
    """
    return send_email(
        author.email,
        f"Respuesta a tu sugerencia en {league}",
        _layout("Respuesta del staff", f"Tu sugerencia «{suggestion.title}» fue respondida.", [body]),
        user=author,
        template="suggestion_reply",
    )
