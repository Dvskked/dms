"""Prueba HTTP real contra el servidor de desarrollo.

Levanta el servidor en un hilo, pide las rutas clave y comprueba:
- codigo 200
- doctype, <html lang="es"> y cierre de body
- que no queden etiquetas Jinja sin renderizar
- que los estilos esten enlazados
"""
from __future__ import annotations

import json
import re
import threading
import time
import urllib.error
import urllib.request
from wsgiref.simple_server import WSGIRequestHandler, make_server

from app import create_app

PORT = 5099
BASE = f"http://127.0.0.1:{PORT}"

app = create_app()


class Quiet(WSGIRequestHandler):
    def log_message(self, *args):  # silencia el log
        pass


server = make_server("127.0.0.1", PORT, app, handler_class=Quiet)
thread = threading.Thread(target=server.serve_forever, daemon=True)
thread.start()
time.sleep(0.6)

class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        return None


OPENER = urllib.request.build_opener(NoRedirect)

# Rutas publicas: se esperan sin sesion. La liga exige cuenta, asi que "/" y
# "/sugerencias" deben contestar 302 hacia el login.
PUBLIC_ROUTES = ["/auth/login", "/auth/register", "/auth/recuperar", "/health"]
GATED_ROUTES = ["/", "/estadisticas", "/sugerencias"]
ADMIN_ROUTES = [
    "/admin/", "/admin/noticias/", "/admin/reglas/", "/admin/sanciones/",
    "/admin/salas/nuevo", "/admin/usuarios/nuevo", "/admin/ajustes",
]

ROUTES: list[tuple[str, int]] = (
    [(route, 200) for route in PUBLIC_ROUTES]
    + [(route, 302) for route in GATED_ROUTES]
    + [(route, 302) for route in ADMIN_ROUTES]
)

JSON_ROUTES = {"/health"}

failures: list[str] = []
for route, expected in ROUTES:
    try:
        with OPENER.open(BASE + route) as response:
            status, body = response.status, response.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as error:
        status, body = error.code, error.read().decode("utf-8", "replace")
    except Exception as error:  # noqa: BLE001
        failures.append(f"{route} -> error de red: {error}")
        continue

    if status != expected:
        failures.append(f"{route} -> {status} (esperado {expected})")
        continue

    if status != 200:
        print(f"[OK ] {status} {route}")
        continue

    if route in JSON_ROUTES:
        try:
            json.loads(body)
        except ValueError:
            failures.append(f"{route} -> no devuelve JSON valido")
            print(f"[FAIL] 200 {route} -> JSON invalido")
        else:
            print(f"[OK ] 200 {route} (JSON)")
        continue

    checks = {
        "doctype": body.lstrip().lower().startswith("<!doctype html>"),
        "lang": '<html lang="es">' in body,
        "css": "/static/css/style.css" in body,
        "cierre body": "</body>" in body,
        "sin jinja": not re.search(r"\{\{|\{%", body),
        "sin undefined": "Undefined" not in body,
    }
    broken = [name for name, ok in checks.items() if not ok]
    if broken:
        failures.append(f"{route} -> falla: {', '.join(broken)}")
        print(f"[FAIL] 200 {route} -> {', '.join(broken)}")
    else:
        print(f"[OK ] 200 {route} ({len(body)} bytes)")

server.shutdown()

print("\n" + "=" * 50)
if failures:
    print("FALLOS:")
    for item in failures:
        print("  -", item)
else:
    print("TODO OK")
