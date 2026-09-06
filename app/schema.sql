-- Fase 1: metadatos técnicos. El modelo hidropónico corresponde a la fase 2.
CREATE TABLE IF NOT EXISTS schema_migrations (
    version INTEGER PRIMARY KEY,
    description TEXT NOT NULL,
    applied_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))
);

INSERT OR IGNORE INTO schema_migrations (version, description)
VALUES (1, 'Base Flask y SQLite');
