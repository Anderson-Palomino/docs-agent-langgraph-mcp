"""Con docs-agent apagado, el webhook debe responder 502 con mensaje y dejar fila en el log.

Lo orquesta smoke.sh (paso 'caida'): apaga el contenedor api, corre esto y lo vuelve a levantar.
"""
import json
import sys
import urllib.error
import urllib.request

req = urllib.request.Request("http://127.0.0.1:5678/webhook/ask",
                             data=json.dumps({"question": "prueba con docs-agent caído"}).encode(),
                             headers={"Content-Type": "application/json"}, method="POST")
try:
    with urllib.request.urlopen(req, timeout=90) as r:
        status, body = r.status, r.read()
except urllib.error.HTTPError as e:
    status, body = e.code, e.read()
try:
    datos = json.loads(body)
except ValueError:
    datos = {"_raw": body[:200]}
ok = status == 502 and "error" in datos
print(("  OK   " if ok else "  FAIL ") + f"docs-agent caído → 502 con error  (obtuve {status}: {str(datos)[:150]})")
sys.exit(0 if ok else 1)
