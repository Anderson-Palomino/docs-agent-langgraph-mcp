#!/usr/bin/env bash
# Pruebas de humo de la integración n8n. Uso: ./smoke.sh [1|3|todo]
# Requiere docs-agent y n8n levantados. No usa secretos.
set -u
cd "$(dirname "$0")"
N8N=http://127.0.0.1:5678
fallos=0
ok()   { echo "  OK   $1"; }
fail() { echo "  FAIL $1"; fallos=$((fallos+1)); }
check() { local nombre="$1"; shift; if "$@" >/dev/null 2>&1; then ok "$nombre"; else fail "$nombre"; fi; }

paso1() {
  echo "Paso 1: n8n on-premise"
  check "n8n responde en 127.0.0.1:5678/healthz" curl -sf "$N8N/healthz"
  check "puerto 5678 publicado solo en 127.0.0.1" \
    bash -c 'docker compose port n8n 5678 | grep -q "^127.0.0.1:"'
  check "n8n llega a api:8000/health por la red de Docker" \
    docker compose exec -T n8n node -e \
      'fetch("http://api:8000/health").then(r=>r.json()).then(j=>process.exit(j.status==="ok"?0:1)).catch(()=>process.exit(1))'
}

case "${1:-todo}" in
  1) paso1 ;;
  todo) paso1 ;;
esac
echo "Fallos: $fallos"
exit $fallos
