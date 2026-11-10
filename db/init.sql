CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE IF NOT EXISTS chunks (
    id          bigserial PRIMARY KEY,
    source_ref  text NOT NULL,
    url         text NOT NULL,
    title       text NOT NULL,
    content     text NOT NULL,
    token_count int NOT NULL,
    embedding   vector(1536) NOT NULL,
    created_at  timestamptz DEFAULT now()
);

CREATE INDEX IF NOT EXISTS chunks_embedding_hnsw
    ON chunks USING hnsw (embedding vector_cosine_ops);

CREATE INDEX IF NOT EXISTS chunks_source_ref_idx ON chunks (source_ref);

CREATE TABLE IF NOT EXISTS sections (
    id         bigserial PRIMARY KEY,
    source_ref text NOT NULL,
    url        text NOT NULL,
    title      text NOT NULL,
    content    text NOT NULL,
    UNIQUE (source_ref, url)
);

CREATE TABLE IF NOT EXISTS token_usage (
    day    date NOT NULL,
    kind   text NOT NULL,
    tokens bigint NOT NULL DEFAULT 0,
    PRIMARY KEY (day, kind)
);
