-- Runs automatically on first start (empty volume).
-- Subsequent starts skip this file because the data directory already exists.

CREATE TABLE IF NOT EXISTS tasks (
    id          TEXT        PRIMARY KEY,
    title       TEXT        NOT NULL,
    completed   BOOLEAN     NOT NULL DEFAULT FALSE,
    description TEXT        NOT NULL DEFAULT '',
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
