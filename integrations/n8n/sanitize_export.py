"""Limpia un workflow exportado con `n8n export:workflow` antes de commitearlo.

Quita los datos de la instancia (dueño, proyecto, versiones, fechas) y lo deja
inactivo. Las credenciales quedan solo como {id, name}: n8n nunca exporta sus valores.
Uso: python -I -X utf8 sanitize_export.py workflows/archivo.json
"""
import json
import sys

QUITAR = {"shared", "activeVersionId", "versionMetadata", "versionCounter", "versionId",
          "createdAt", "updatedAt", "triggerCount", "isArchived", "staticData", "sourceWorkflowId"}

ruta = sys.argv[1]
with open(ruta, encoding="utf-8") as f:
    datos = json.load(f)
wf = datos[0] if isinstance(datos, list) else datos
for clave in QUITAR:
    wf.pop(clave, None)
wf["active"] = False
texto = json.dumps(wf, ensure_ascii=False, indent=2) + "\n"
if "@" in texto.replace("@n8n", ""):
    sys.exit(f"{ruta}: todavía contiene '@' (¿un correo?); revisar a mano")
with open(ruta, "w", encoding="utf-8", newline="\n") as f:
    f.write(texto)
print(f"{ruta}: limpio ({len(wf['nodes'])} nodos)")
