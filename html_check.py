"""Analiza el HTML renderizado del home: ids duplicados y balance de etiquetas."""
from __future__ import annotations

import re
from collections import Counter

from app import create_app

app = create_app()
client = app.test_client()

with app.app_context():
    login_page = client.get("/auth/login")
    token = re.search(r'name="csrf_token"[^>]*value="([^"]+)"', login_page.data.decode()).group(1)
    client.post("/auth/login", data={"username": "admin", "password": "adminmascapito",
                                    "csrf_token": token}, follow_redirects=False)

targets = ["/", "/admin/", "/admin/reglas/", "/admin/sanciones/", "/admin/salas/nuevo",
           "/auth/login", "/auth/register", "/admin/ajustes"]

VOID = {"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta",
        "param", "source", "track", "wbr"}

problems = 0
for route in targets:
    response = client.get(route, follow_redirects=False)
    if response.status_code != 200:
        print(f"[--  ] {route} -> {response.status_code} (se omite)")
        continue
    body = response.data.decode("utf-8")

    ids = re.findall(r'\sid="([^"]+)"', body)
    duplicates = [key for key, count in Counter(ids).items() if count > 1]

    stack: list[str] = []
    unbalanced: list[str] = []
    for match in re.finditer(r'<(/?)([a-zA-Z][a-zA-Z0-9]*)\b[^>]*?(/?)>', body):
        closing, tag, selfclose = match.group(1), match.group(2).lower(), match.group(3)
        if tag in VOID or selfclose:
            continue
        if closing:
            if stack and stack[-1] == tag:
                stack.pop()
            elif tag in stack:
                while stack and stack.pop() != tag:
                    pass
                unbalanced.append(tag)
            else:
                unbalanced.append(f"/{tag}")
        else:
            stack.append(tag)

    status = "OK " if not duplicates and not stack and not unbalanced else "FAIL"
    print(f"[{status}] {route} ids={len(ids)} duplicados={duplicates or '-'} "
          f"abiertas={stack or '-'} desbalanceadas={unbalanced or '-'}")
    if duplicates or stack or unbalanced:
        problems += 1

print("\n" + "=" * 50)
print("TODO OK" if not problems else f"paginas con problemas: {problems}")
