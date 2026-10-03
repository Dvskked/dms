"""Prueba rapida de rutas: render, status y errores de plantilla."""
from __future__ import annotations

import re
import sys
import traceback

from app import app, db
from models import Article, Room, User

with app.app_context():
    db.create_all()

client = app.test_client()

with app.app_context():
    admin = User.query.filter_by(username="admin").first()
    admin_email = admin.email

PAGES = [
    ("/", None),
    ("/noticias/nueva-pagina-de-the-diamonds-league", None),
    ("/auth/login", None),
    ("/auth/register", None),
]

PUBLIC = ["/", "/auth/login", "/auth/register", "/auth/google", "/auth/perfil", "/auth/contrasena"]

with app.app_context():
    slugs = [a.slug for a in Article.query.limit(2).all()]
    stream_id = 1
PUBLIC += [f"/noticias/{s}" for s in slugs]
PUBLIC += [f"/live/{stream_id}"]
PUBLIC += [
    "/admin/", "/admin/avisos/", "/admin/noticias/", "/admin/informes/", "/admin/equipos/",
    "/admin/jugadores/", "/admin/calendario/", "/admin/salas/", "/admin/museo/", "/admin/alianzas/",
    "/admin/redes/", "/admin/equipo/", "/admin/live/", "/admin/donacion-canales/", "/admin/donaciones/",
    "/admin/divisiones/", "/admin/reglas/", "/admin/sanciones/", "/admin/usuarios/", "/admin/ajustes",
    "/admin/avisos/nuevo", "/admin/noticias/nuevo", "/admin/equipos/nuevo", "/admin/jugadores/nuevo",
    "/admin/calendario/nuevo", "/admin/salas/nuevo", "/admin/museo/nuevo", "/admin/alianzas/nuevo",
    "/admin/redes/nuevo", "/admin/equipo/nuevo", "/admin/live/nuevo", "/admin/divisiones/nuevo",
    "/admin/usuarios/nuevo",
]

import re as _re
token_re = _re.compile(r'name="csrf_token"[^>]*value="([^"]+)"')


def login():
    resp = client.get("/auth/login")
    token = token_re.search(resp.data.decode())
    return client.post("/auth/login", data={
        "username": "admin", "password": "adminmascapito", "csrf_token": token.group(1) if token else "",
    }, follow_redirects=False)


failures = []


def check(path, resp, expect=200):
    status = "OK " if resp.status_code == expect else "FAIL"
    if status == "FAIL":
        failures.append((path, resp.status_code))
    print(f"[{status}] {resp.status_code:>3} {path}")
    if resp.status_code >= 500:
        text = resp.data.decode("utf-8", "replace")
        print("        " + re.sub(r"<[^>]+>", " ", text)[-1200:].replace("\n", "\n        "))


print("=== SIN SESION ===")
# Con REQUIRE_LOGIN=1 la liga esta cerrada: estas rutas deben devolver 302 al login.
for path in ["/", "/auth/login", "/auth/register"] + [p for p in PUBLIC if p.startswith("/noticias") or p.startswith("/live")]:
    expect = 200 if path in ("/auth/login", "/auth/register") else 302
    check(path, client.get(path), expect=expect)

for path in ["/admin/", "/admin/avisos/", "/admin/ajustes", "/auth/perfil"]:
    check(path, client.get(path), expect=302)

print("\n=== LOGIN ===")
r = login()
print(f"[{'OK ' if r.status_code in (301, 302) else 'FAIL'}] login -> {r.status_code} {r.headers.get('Location', '')}")
if r.status_code not in (301, 302):
    failures.append(("login", r.status_code))
    print(r.data.decode()[:800])

print("\n=== CON SESION ===")
for path in PUBLIC:
    # Ya autenticado, /auth/login y /auth/register redirigen (comportamiento correcto)
    expect = 302 if path in ("/auth/login", "/auth/register") else 200
    check(path, client.get(path), expect=expect)

print("\n=== CRUD POST (crear noticia) ===")
resp = client.get("/admin/noticias/nuevo")
token = token_re.search(resp.data.decode())
payload = {
    "csrf_token": token.group(1) if token else "",
    "kind": "news", "category": "general", "title": "PRUEBA SMOKE",
    "slug": "", "summary": "Resumen de prueba.", "body": "Cuerpo de prueba.",
    "is_published": "y", "is_featured": "y",
}
r = client.post("/admin/noticias/nuevo", data=payload, follow_redirects=False)
print(f"[{'OK ' if r.status_code in (301, 302) else 'FAIL'}] crear noticia -> {r.status_code} {r.headers.get('Location', '')}")
if r.status_code not in (301, 302):
    failures.append(("crear noticia", r.status_code))
    print(r.data.decode()[:1500])
else:
    with app.app_context():
        art = Article.query.filter_by(title="PRUEBA SMOKE").first()
        print(f"    -> creado id={art.id if art else None} slug={art.slug if art else None}")
        if art:
            pk = art.id
            resp = client.get(f"/admin/noticias/{pk}/editar")
            token = token_re.search(resp.data.decode())
            r = client.post(f"/admin/noticias/{pk}/editar", data={
                "csrf_token": token.group(1) if token else "", "kind": "news", "category": "eventos",
                "title": "PRUEBA SMOKE EDITADA", "summary": "Editado.", "body": "Cuerpo editado.",
                "is_published": "y",
            }, follow_redirects=False)
            print(f"[{'OK ' if r.status_code in (301, 302) else 'FAIL'}] editar -> {r.status_code}")
            if r.status_code not in (301, 302):
                failures.append(("editar noticia", r.status_code))
                print(r.data.decode()[:1200])
            else:
                with app.app_context():
                    art = db.session.get(Article, pk)
                    print(f"    -> titulo ahora: {art.title} / categoria: {art.category}")
                r = client.post(f"/admin/articulos/{pk}/duplicar", data={"csrf_token": token.group(1) if token else ""})
                print(f"[{'OK ' if r.status_code in (301, 302) else 'FAIL'}] duplicar -> {r.status_code}")
                r = client.post(f"/admin/noticias/{pk}/eliminar", data={"csrf_token": token.group(1) if token else ""})
                print(f"[{'OK ' if r.status_code in (301, 302) else 'FAIL'}] eliminar -> {r.status_code}")
                # La copia que genera "duplicar" tambien se elimina para no dejar datos de prueba.
                with app.app_context():
                    clone = Article.query.filter(Article.title.like("PRUEBA SMOKE EDITADA (copia)%")).all()
                    for row in clone:
                        db.session.delete(row)
                    db.session.commit()
                    print(f"[OK ] limpieza copias -> {len(clone)} borrada(s)")

print("\n=== CRUD POST (regla, sancion y sala) ===")


def crud(resource, payload, model_name):
    """Crea un registro, lee sus campos guardados y lo elimina."""
    global token
    resp = client.get(f"/admin/{resource}/nuevo")
    match = token_re.search(resp.data.decode())
    if not match:
        failures.append((f"token {resource}", 0))
        print(f"[FAIL] {resource}: sin csrf")
        return
    token = match.group(1)
    data = {"csrf_token": token, **payload}
    r = client.post(f"/admin/{resource}/nuevo", data=data, follow_redirects=False)
    ok = r.status_code in (301, 302)
    print(f"[{'OK ' if ok else 'FAIL'}] crear {resource} -> {r.status_code}")
    if not ok:
        failures.append((f"crear {resource}", r.status_code))
        return
    with app.app_context():
        model = __import__("models")
        rows = getattr(model, model_name).query.all()
        row = rows[-1]
        pk = row.id
        print("    ->", {key: str(getattr(row, key))[:40] for key in payload if hasattr(row, key)})
    resp = client.get(f"/admin/{resource}/{pk}/editar")
    match = token_re.search(resp.data.decode())
    r = client.post(f"/admin/{resource}/{pk}/editar",
                    data={"csrf_token": match.group(1) if match else "", **payload},
                    follow_redirects=False)
    print(f"[{'OK ' if r.status_code in (301, 302) else 'FAIL'}] editar {resource} -> {r.status_code}")
    if r.status_code not in (301, 302):
        failures.append((f"editar {resource}", r.status_code))
        return
    r = client.post(f"/admin/{resource}/{pk}/eliminar", data={"csrf_token": token})
    print(f"[{'OK ' if r.status_code in (301, 302) else 'FAIL'}] eliminar {resource} -> {r.status_code}")
    if r.status_code not in (301, 302):
        failures.append((f"eliminar {resource}", r.status_code))


crud("reglas", {"scope": "discord", "position": 9, "title": "REGLA DE PRUEBA",
                "body": "Texto de la regla de prueba."}, "RuleEntry")
crud("sanciones", {"name": "NIVEL DE PRUEBA", "color": "yellow",
                   "items": "Primera\nSegunda", "note": "Nota de prueba"}, "SanctionLevel")
crud("salas", {"code": "99", "name": "SALA DE PRUEBA", "haxball_url": "https://haxball.com/headless/test",
               "map_name": "Diamond", "mode": "1v1", "ping": 90, "password": "DIAMONDS",
               "is_open": "y", "is_pinned": "y", "is_featured": "y", "max_players": 12,
               "region": "Latam", "description": "Sala creada por el smoke test."}, "Room")
crud("donacion-canales", {"label": "PAYPAL", "method": "PayPal", "account": "liga@paypal",
                          "url": "https://paypal.me/liga", "note": "Prueba"}, "DonationChannel")

print("\n=== AJUSTES ===")
resp = client.get("/admin/ajustes")
token = token_re.search(resp.data.decode())
r = client.post("/admin/ajustes", data={"csrf_token": token.group(1) if token else "", "values": '{"league_name":"THE DIAMONDS LEAGUE"}'})
print(f"[{'OK ' if r.status_code in (301, 302) else 'FAIL'}] guardar ajustes -> {r.status_code}")

print("\n=== LOGOUT ===")
resp = client.get("/auth/perfil")
token = token_re.search(resp.data.decode())
r = client.post("/auth/logout", data={"csrf_token": token.group(1) if token else ""})
print(f"[{'OK ' if r.status_code in (301, 302) else 'FAIL'}] logout -> {r.status_code}")
r = client.get("/admin/")
print(f"[{'OK ' if r.status_code == 302 else 'FAIL'}] admin tras logout -> {r.status_code}")

print("\n" + "=" * 50)
if failures:
    print(f"FALLOS: {len(failures)}")
    for path, code in failures:
        print(f"  - {path} -> {code}")
    sys.exit(1)
print("TODO OK")
