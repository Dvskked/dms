"""Compara los atributos data-* de las plantillas con los que usan los JS."""
from __future__ import annotations

import pathlib
import re

TEMPLATE_ATTR = re.compile(r"data-([a-z-]+)")
JS_SELECTOR = re.compile(r"""\[data-([a-z-]+)""")
JS_DATASET = re.compile(r"dataset\.([a-zA-Z]+)")

template_attrs: set[str] = set()
for path in pathlib.Path("templates").rglob("*.html"):
    template_attrs.update(TEMPLATE_ATTR.findall(path.read_text(encoding="utf-8")))

js_used: set[str] = set()
for path in pathlib.Path("static/js").glob("*.js"):
    text = path.read_text(encoding="utf-8")
    js_used.update(JS_SELECTOR.findall(text))
    for name in JS_DATASET.findall(text):
        js_used.add(re.sub(r"[A-Z]", lambda m: "-" + m.group(0).lower(), name))

print("data-* en plantillas:", len(template_attrs))
print("data-* usados por JS:", len(js_used))

sin_js = sorted(template_attrs - js_used)
print("\nAtributos sin uso en JS:", len(sin_js))
for item in sin_js:
    print("  -", item)

sin_html = sorted(js_used - template_attrs)
print("\nAtributos que JS busca pero ninguna plantilla define:", len(sin_html))
for item in sin_html:
    print("  -", item)
