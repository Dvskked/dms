"""Verifica que las clases usadas en plantillas existan en el CSS."""
from __future__ import annotations

import pathlib
import re

css = pathlib.Path("static/css/style.css").read_text(encoding="utf-8")
print("llaves CSS -> abiertas:", css.count("{"), "cerradas:", css.count("}"))

pattern = re.compile(r'class="([^"{]+)"')
classes: set[str] = set()
for path in pathlib.Path("templates").rglob("*.html"):
    text = path.read_text(encoding="utf-8")
    for match in pattern.finditer(text):
        classes.update(match.group(1).split())

missing = sorted(item for item in classes if f".{item}" not in css)
print("clases HTML sin regla CSS:", len(missing))
for item in missing:
    print("  -", item)
