-- Runs on every startup, so every statement must be idempotent.
-- No migration tool on purpose: to change a table, add an ALTER here or
-- reset the volume with `docker compose down -v`.

CREATE TABLE IF NOT EXISTS payments (
    id              BIGSERIAL PRIMARY KEY,
    bank            TEXT        NOT NULL,
    method          TEXT        NOT NULL,
    amount_paise    BIGINT      NOT NULL CHECK (amount_paise > 0),
    status          TEXT        NOT NULL CHECK (status IN ('SUCCESS', 'FAILED')),
    error_code      TEXT,
    latency_ms      INTEGER     NOT NULL CHECK (latency_ms >= 0),
    -- NULLs never collide in a UNIQUE column, so the key stays optional.
    idempotency_key TEXT        UNIQUE,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- /stats only ever reads a recent time window.
CREATE INDEX IF NOT EXISTS payments_created_at_idx ON payments (created_at);

-- At most one rule per bank: POST /chaos replaces it.
CREATE TABLE IF NOT EXISTS chaos_rules (
    bank       TEXT             PRIMARY KEY,
    type       TEXT             NOT NULL CHECK (type IN ('timeout', 'decline')),
    rate       DOUBLE PRECISION NOT NULL CHECK (rate >= 0 AND rate <= 1),
    updated_at TIMESTAMPTZ      NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS deploys (
    id              BIGSERIAL PRIMARY KEY,
    service         TEXT        NOT NULL,
    version         TEXT        NOT NULL,
    description     TEXT,
    idempotency_key TEXT        UNIQUE,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS deploys_created_at_idx ON deploys (created_at);
