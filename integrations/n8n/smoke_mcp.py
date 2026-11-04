"""Pruebas de humo del servidor MCP de n8n (workflow 02-mcp-docs-agent, publicado).

Habla MCP por HTTP (streamable) a mano, sin SDK: initialize → tools/list → tools/call.
Lee el token de N8N_MCP_TOKEN en .env (nunca lo imprime).
"""
import json
import pathlib
import sys
import urllib.error
import urllib.request

URL = "http://127.0.0.1:5678/mcp/docs-agent"
TOOL = "ask_docs_agent"
token = next((l.split("=", 1)[1].strip() for l in pathlib.Path(".env").read_text(encoding="utf-8").splitlines()
              if l.startswith("N8N_MCP_TOKEN=")), "")


def rpc(method, params=None, id_=1, auth=True, session=None):
    headers = {"Content-Type": "application/json", "Accept": "application/json, text/event-stream"}
    if auth:
        headers["Authorization"] = f"Bearer {token}"
    if session:
        headers["Mcp-Session-Id"] = session
    body = {"jsonrpc": "2.0", "method": method, "params": params or {}}
    if id_ is not None:
        body["id"] = id_
    req = urllib.request.Request(URL, data=json.dumps(body).encode(), headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=120) as r:
            raw, status, sid = r.read().decode("utf-8", "replace"), r.status, r.headers.get("Mcp-Session-Id")
    except urllib.error.HTTPError as e:
        return e.code, None, None
    except Exception as e:
        return 0, {"_error": str(e)}, None
    # La respuesta puede venir como JSON o como SSE ("data: {...}")
    datos = [l[5:].strip() for l in raw.splitlines() if l.startswith("data:")] or [raw]
    msg = None
    for d in datos:
        try:
            m = json.loads(d)
        except ValueError:
            continue
        if m.get("id") == id_:
            msg = m
    return status, msg, sid


fallos = 0
def check(nombre, ok, detalle=""):
    global fallos
    print(("  OK   " if ok else "  FAIL ") + nombre + ("" if ok else f"  → {str(detalle)[:220]}"))
    fallos += not ok


s, _, _ = rpc("initialize", {"protocolVersion": "2025-03-26", "capabilities": {},
                             "clientInfo": {"name": "smoke", "version": "0"}}, auth=False)
check("sin token → 401/403", s in (401, 403), s)

s, m, sid = rpc("initialize", {"protocolVersion": "2025-03-26", "capabilities": {},
                               "clientInfo": {"name": "smoke", "version": "0"}})
check("initialize con token → 200", s == 200 and m and "result" in m, (s, m))
if s == 200:
    rpc("notifications/initialized", id_=None, session=sid)
    s, m, _ = rpc("tools/list", id_=2, session=sid)
    nombres = [t["name"] for t in (m or {}).get("result", {}).get("tools", [])]
    check(f"tools/list incluye {TOOL}", TOOL in nombres, nombres)
    s, m, _ = rpc("tools/call", {"name": TOOL, "arguments": {"question": "¿Cómo se declara un request body?"}},
                  id_=3, session=sid)
    texto = json.dumps((m or {}).get("result", {}), ensure_ascii=False)
    check("tools/call devuelve respuesta con citas (fastapi.tiangolo.com)",
          s == 200 and "fastapi.tiangolo.com" in texto and not (m or {}).get("result", {}).get("isError"), (s, texto))
sys.exit(fallos)
