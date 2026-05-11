-- Migration 004: Ingestion sources table
-- Stores operator-managed data sources (RSS feeds, Facebook pages, etc.)
-- that the ingestion pipeline reads at runtime.

-- ── ingestion_sources ────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS ingestion_sources (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    platform    TEXT NOT NULL,          -- 'news' | 'facebook' | 'twitter' | 'tiktok'
    source_name TEXT NOT NULL,          -- human-readable label
    config      JSONB NOT NULL DEFAULT '{}',
    -- platform-specific config shapes:
    --   news:      { "feed_url": "https://...", "source_name": "Outlet Name" }
    --   facebook:  { "page_id": "pageslug",    "page_name": "Page Name"     }
    --   twitter:   { "query": "search string"                                }
    --   tiktok:    { "hashtag": "hashtag"                                    }
    is_active   BOOLEAN NOT NULL DEFAULT TRUE,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS ingestion_sources_platform_active
    ON ingestion_sources (platform, is_active);

-- ── ingestion_job_runs ───────────────────────────────────────────────────────
-- Append-only log of every scheduler run for observability / debugging.
CREATE TABLE IF NOT EXISTS ingestion_job_runs (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    job_id          TEXT NOT NULL,      -- matches scheduler JOB_CONFIGS[].id
    platform        TEXT NOT NULL,
    started_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    finished_at     TIMESTAMPTZ,
    status          TEXT NOT NULL DEFAULT 'running',
    -- 'running' | 'ok' | 'rate_limited' | 'circuit_open' | 'error'
    posts_collected INT NOT NULL DEFAULT 0,
    posts_ingested  INT NOT NULL DEFAULT 0,
    posts_skipped   INT NOT NULL DEFAULT 0,
    error_message   TEXT,
    metadata        JSONB DEFAULT '{}'
);

CREATE INDEX IF NOT EXISTS ingestion_job_runs_job_started
    ON ingestion_job_runs (job_id, started_at DESC);

CREATE INDEX IF NOT EXISTS ingestion_job_runs_platform_started
    ON ingestion_job_runs (platform, started_at DESC);

-- Auto-prune runs older than 90 days (keep the table lean)
CREATE OR REPLACE FUNCTION prune_old_job_runs() RETURNS TRIGGER LANGUAGE plpgsql AS $$
BEGIN
    DELETE FROM ingestion_job_runs
    WHERE started_at < NOW() - INTERVAL '90 days';
    RETURN NULL;
END;
$$;

DROP TRIGGER IF EXISTS trg_prune_job_runs ON ingestion_job_runs;
CREATE TRIGGER trg_prune_job_runs
    AFTER INSERT ON ingestion_job_runs
    FOR EACH STATEMENT EXECUTE FUNCTION prune_old_job_runs();

-- ── updated_at trigger ───────────────────────────────────────────────────────
CREATE OR REPLACE FUNCTION set_updated_at()
RETURNS TRIGGER LANGUAGE plpgsql AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS trg_ingestion_sources_updated_at ON ingestion_sources;
CREATE TRIGGER trg_ingestion_sources_updated_at
    BEFORE UPDATE ON ingestion_sources
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();

-- ── Row Level Security ───────────────────────────────────────────────────────
ALTER TABLE ingestion_sources   ENABLE ROW LEVEL SECURITY;
ALTER TABLE ingestion_job_runs  ENABLE ROW LEVEL SECURITY;

-- Service role (backend) has full access
CREATE POLICY "service_full_ingestion_sources"
    ON ingestion_sources FOR ALL
    TO service_role USING (true) WITH CHECK (true);

CREATE POLICY "service_full_ingestion_job_runs"
    ON ingestion_job_runs FOR ALL
    TO service_role USING (true) WITH CHECK (true);

-- Authenticated users can read
CREATE POLICY "auth_read_ingestion_sources"
    ON ingestion_sources FOR SELECT
    TO authenticated USING (true);

CREATE POLICY "auth_read_ingestion_job_runs"
    ON ingestion_job_runs FOR SELECT
    TO authenticated USING (true);

-- ── Seed: default Malaysian RSS sources ──────────────────────────────────────
-- These mirror DEFAULT_FEEDS in rss.py. Seeding here lets operators
-- manage them via the UI without code changes.
INSERT INTO ingestion_sources (platform, source_name, config) VALUES
    ('news', 'Malay Mail',          '{"feed_url": "https://www.malaymail.com/feed",                        "source_name": "Malay Mail"}'),
    ('news', 'Free Malaysia Today', '{"feed_url": "https://www.freemalaysiatoday.com/feed/",               "source_name": "Free Malaysia Today"}'),
    ('news', 'The Star',            '{"feed_url": "https://www.thestar.com.my/rss/news/nation/",           "source_name": "The Star"}'),
    ('news', 'New Straits Times',   '{"feed_url": "https://www.nst.com.my/rss/news",                      "source_name": "New Straits Times"}'),
    ('news', 'Malaysiakini',        '{"feed_url": "https://www.malaysiakini.com/rss",                     "source_name": "Malaysiakini"}'),
    ('news', 'Bernama',             '{"feed_url": "https://www.bernama.com/feed/index.php",                "source_name": "Bernama"}'),
    ('news', 'Astro Awani',         '{"feed_url": "https://www.astroawani.com/rss",                       "source_name": "Astro Awani"}'),
    ('news', 'Sinar Harian',        '{"feed_url": "https://www.sinarharian.com.my/feed",                  "source_name": "Sinar Harian"}'),
    ('news', 'Berita Harian',       '{"feed_url": "https://www.bharian.com.my/rss.xml",                   "source_name": "Berita Harian"}'),
    ('news', 'Utusan Malaysia',     '{"feed_url": "https://www.utusan.com.my/feed/",                      "source_name": "Utusan Malaysia"}')
ON CONFLICT DO NOTHING;
