-- Log de las preguntas que pasan por el workflow 01-ask-log de n8n.
-- Vive en el Postgres de docs-agent. Idempotente: se puede correr varias veces.
-- Aplicar desde la raíz del repo:
--   docker compose exec -T db psql -U docs -d docs < integrations/n8n/sql/001_n8n_question_log.sql
CREATE TABLE IF NOT EXISTS n8n_question_log (
    id                bigserial PRIMARY KEY,
    created_at        timestamptz NOT NULL DEFAULT now(),
    question          text        NOT NULL,
    answer            text,                 -- null si /ask falló
    grounded          boolean,              -- null si /ask falló
    citations         jsonb,                -- [{url, title}]
    embedding_tokens  int,
    prompt_tokens     int,
    completion_tokens int,
    total_tokens      int,                  -- suma de los tres: base para controlar consumo
    http_status       int         NOT NULL  -- status que devolvió /ask
);

CREATE INDEX IF NOT EXISTS n8n_question_log_created_at_idx ON n8n_question_log (created_at);
