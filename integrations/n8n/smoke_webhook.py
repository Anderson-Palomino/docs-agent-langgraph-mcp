"""Pruebas de humo del workflow 01-ask-log (URL de producción: el workflow debe estar publicado)."""
import json
import sys
import urllib.error
import urllib.request

URL = "http://127.0.0.1:5678/webhook/ask"
NO_ENCONTRE = "No encontré esto en la documentación"


def post(raw: bytes, content_type: str = "application/json"):
    req = urllib.request.Request(URL, data=raw, headers={"Content-Type": content_type}, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=90) as r:
            status, body = r.status, r.read()
    except urllib.error.HTTPError as e:
        status, body = e.code, e.read()
    except Exception as e:  # n8n caído o timeout
        return 0, {"_error": str(e)}
    try:
        return status, json.loads(body)
    except ValueError:
        return status, {"_raw": body.decode("utf-8", "replace")[:200]}


def ask(q):
    return post(json.dumps({"question": q}).encode())


casos = []

def caso(nombre):
    def deco(f):
        casos.append((nombre, f))
        return f
    return deco


@caso("pregunta de FastAPI → 200, grounded, con citas")
def _():
    s, b = ask("¿Cómo se declara un request body?")
    return s == 200 and b.get("grounded") is True and len(b.get("citations") or []) > 0, (s, b)


@caso("pregunta fuera de tema → mensaje 'No encontré…'")
def _():
    s, b = ask("¿Cuál es la capital de Francia?")
    return s == 200 and b.get("grounded") is False and b.get("answer") == NO_ENCONTRE, (s, b)


@caso("body sin question → 400 con error")
def _():
    s, b = post(b"{}")
    return s == 400 and "error" in b, (s, b)


@caso("body que no es JSON → 4xx con mensaje")
def _():
    s, b = post(b"no json", "text/plain")
    return 400 <= s < 500 and s != 404, (s, b)


@caso("pregunta de 1001 caracteres → 422 propagado desde /ask")
def _():
    s, b = ask("a" * 1001)
    return s == 422 and "error" in b, (s, b)


@caso('pregunta con "comillas", salto de línea y tildes → 200')
def _():
    s, b = ask('¿Qué hace "Depends"\ncon la inyección de dependencias?')
    return s == 200 and "answer" in b, (s, b)


fallos = 0
for nombre, f in casos:
    bien, detalle = f()
    print(("  OK   " if bien else "  FAIL ") + nombre + ("" if bien else f"  → {str(detalle)[:220]}"))
    fallos += not bien
sys.exit(fallos)
