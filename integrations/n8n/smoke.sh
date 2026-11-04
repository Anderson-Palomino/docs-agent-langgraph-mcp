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

RAIZ="$(cd ../.. && pwd)"
psql_docs() { (cd "$RAIZ" && docker compose exec -T db psql -U docs -d docs -tAc "$1"); }

paso2_tabla() {
  echo "Tabla de log"
  local esperado="id,created_at,question,answer,grounded,citations,embedding_tokens,prompt_tokens,completion_tokens,total_tokens,http_status"
  local cols
  cols=$(psql_docs "select string_agg(column_name, ',' order by ordinal_position) from information_schema.columns where table_name = 'n8n_question_log'" 2>&1)
  if [ "$cols" = "$esperado" ]; then ok "n8n_question_log tiene las 11 columnas del plan"
  else fail "n8n_question_log tiene las 11 columnas del plan (obtuve: '${cols}')"; fi
}

paso2_webhook() {
  echo "Paso 2: webhook → docs-agent → log"
  local antes despues
  antes=$(psql_docs "select count(*) from n8n_question_log")
  python -I -X utf8 smoke_webhook.py || fallos=$((fallos+$?))
  despues=$(psql_docs "select count(*) from n8n_question_log")
  # 4 llamadas llegan a /ask (FastAPI, fuera de tema, 1001 caracteres, comillas): 4 filas nuevas
  if [ $((despues-antes)) -eq 4 ]; then ok "4 filas nuevas en n8n_question_log"
  else fail "4 filas nuevas en n8n_question_log (hubo $((despues-antes)))"; fi
}

case "${1:-todo}" in
  1) paso1 ;;
  2) paso2_tabla; paso2_webhook ;;
  todo) paso1; paso2_tabla; paso2_webhook ;;
esac
echo "Fallos: $fallos"
exit $fallos
