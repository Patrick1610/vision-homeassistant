-- Frozen Vision 0.1.1 schema from 0926145e2fb375d997d5917715266fa05cd1999e

PRAGMA journal_mode=WAL;
CREATE TABLE IF NOT EXISTS meta (key TEXT PRIMARY KEY, value TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS availability (
 id INTEGER PRIMARY KEY, entity_id TEXT NOT NULL, state TEXT NOT NULL,
 started REAL NOT NULL, ended REAL, uncertain INTEGER NOT NULL DEFAULT 0);
CREATE INDEX IF NOT EXISTS availability_entity ON availability(entity_id, started);
CREATE UNIQUE INDEX IF NOT EXISTS availability_open ON availability(entity_id) WHERE ended IS NULL;
CREATE TABLE IF NOT EXISTS issues (
 key TEXT PRIMARY KEY, source TEXT NOT NULL, severity TEXT NOT NULL,
 title TEXT NOT NULL, detail TEXT NOT NULL, first_seen REAL NOT NULL,
 last_seen REAL NOT NULL, occurrences INTEGER NOT NULL, active INTEGER NOT NULL);
CREATE TABLE IF NOT EXISTS runs (
 entity_id TEXT NOT NULL, run_id TEXT NOT NULL, context_id TEXT,
 started REAL NOT NULL, outcome TEXT NOT NULL, triggered INTEGER NOT NULL DEFAULT 0,
 detail TEXT NOT NULL, PRIMARY KEY(entity_id, run_id));
CREATE INDEX IF NOT EXISTS runs_context ON runs(entity_id, context_id);
CREATE TABLE IF NOT EXISTS exceptions (
 entity_id TEXT PRIMARY KEY, reason TEXT NOT NULL, expires REAL);
CREATE TABLE IF NOT EXISTS analyses (
 id INTEGER PRIMARY KEY, created REAL NOT NULL, kind TEXT NOT NULL,
 target TEXT, provider TEXT NOT NULL, model TEXT NOT NULL, result TEXT NOT NULL,
 evidence TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS usage (
 id INTEGER PRIMARY KEY, created REAL NOT NULL, provider TEXT NOT NULL,
 model TEXT NOT NULL, input_tokens INTEGER, output_tokens INTEGER,
 cost_usd REAL NOT NULL, status TEXT NOT NULL);

