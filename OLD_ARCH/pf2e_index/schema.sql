PRAGMA journal_mode = WAL;
PRAGMA synchronous = NORMAL;
PRAGMA foreign_keys = ON;

-- Core document store
DROP TABLE IF EXISTS docs;
CREATE TABLE docs (
  aon_id           INTEGER PRIMARY KEY,
  category     TEXT NOT NULL,           -- e.g., spell, feat, equipment, …
  name         TEXT,                    -- canonical display name
  traits       TEXT,                    -- space/comma-separated traits (raw string from source)
  summary      TEXT,                    -- brief summary/entry
  text         TEXT,                    -- full body text (plain)
  url          TEXT,                    -- AoN relative or absolute URL
  level        INTEGER,                 -- where applicable (spells/feats/items)
  rarity       TEXT,                    -- common/uncommon/rare/unique
  traditions   TEXT,                    -- spells: arcane|divine|occult|primal (raw string)
  actions      TEXT,                    -- actions notation (e.g., "1", "2", "3", "R", "F")
  source       TEXT,                    -- source book/abbrev if provided
  extra        TEXT                     -- JSON string for any additional fields we don’t explicitly map
);

CREATE INDEX IF NOT EXISTS docs_cat_idx   ON docs(category);
CREATE INDEX IF NOT EXISTS docs_name_idx  ON docs(name);
CREATE INDEX IF NOT EXISTS docs_url_idx   ON docs(url);

-- Contentless FTS5 for fast ranked search (porter stemming)
DROP TABLE IF EXISTS docs_fts;
CREATE VIRTUAL TABLE docs_fts USING fts5(
  name,
  traits,
  summary,
  text,
  category,
  content='',
  tokenize='porter'
);

-- Helper to (re)build the FTS index from docs
DROP VIEW IF EXISTS docs_fts_source;
CREATE VIEW docs_fts_source AS
SELECT
  aon_id AS rowid,
  COALESCE(name,'')    AS name,
  COALESCE(traits,'')  AS traits,
  COALESCE(summary,'') AS summary,
  COALESCE(text,'')    AS text,
  COALESCE(category,'') AS category
FROM docs;

-- Refill FTS (call after you load/refresh docs)
--   DELETE FROM docs_fts;
--   INSERT INTO docs_fts(rowid, name, traits, summary, text, category)
--   SELECT rowid, name, traits, summary, text, category FROM docs_fts_source;
