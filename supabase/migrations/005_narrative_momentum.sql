-- ============================================================
-- NARRATIVE MOMENTUM & COORDINATION TRACKING
-- Adds velocity-based momentum scoring, coordinated-behavior
-- detection fields, and soft "related narrative" links.
-- ============================================================

-- New columns on narratives
ALTER TABLE narratives
  ADD COLUMN IF NOT EXISTS momentum_score      FLOAT   DEFAULT 0,
  ADD COLUMN IF NOT EXISTS coordination_score  FLOAT   DEFAULT 0,
  ADD COLUMN IF NOT EXISTS coordination_signals JSONB  DEFAULT '[]',
  ADD COLUMN IF NOT EXISTS related_narrative_ids UUID[] DEFAULT '{}';

-- Fast sorts / filters for new fields
CREATE INDEX IF NOT EXISTS idx_narratives_momentum
  ON narratives(momentum_score DESC);

CREATE INDEX IF NOT EXISTS idx_narratives_coordination
  ON narratives(coordination_score DESC)
  WHERE coordination_score > 0.3;

-- ============================================================
-- SQL helper: compute momentum score for a single narrative.
-- Called from Python via db.rpc() when a batch update is too
-- expensive to run in pure Python for large narrative sets.
-- Returns a value in [-100, 100].
-- ============================================================
CREATE OR REPLACE FUNCTION compute_narrative_momentum(p_narrative_id UUID)
RETURNS FLOAT AS $$
DECLARE
  now_hour       TIMESTAMPTZ;
  current_count  INTEGER;
  baseline_avg   FLOAT;
BEGIN
  now_hour := date_trunc('hour', NOW() AT TIME ZONE 'UTC');

  SELECT COALESCE(SUM(post_count), 0)
    INTO current_count
    FROM narrative_timeline
   WHERE narrative_id = p_narrative_id
     AND bucket >= now_hour
     AND bucket <  now_hour + INTERVAL '1 hour';

  SELECT COALESCE(AVG(post_count), 0)
    INTO baseline_avg
    FROM narrative_timeline
   WHERE narrative_id = p_narrative_id
     AND bucket >= now_hour - INTERVAL '7 hours'
     AND bucket <  now_hour;

  IF baseline_avg = 0 THEN
    RETURN LEAST(100.0, current_count::FLOAT * 10.0);
  END IF;

  RETURN GREATEST(-100.0, LEAST(100.0,
    (current_count - baseline_avg) / baseline_avg * 100.0
  ));
END;
$$ LANGUAGE plpgsql;

-- ============================================================
-- SQL helper: upsert a narrative timeline bucket with additive
-- semantics (post_count and engagement are incremented).
-- Called from Python via db.rpc().
-- ============================================================
CREATE OR REPLACE FUNCTION upsert_narrative_timeline(
  p_narrative_id  UUID,
  p_bucket        TIMESTAMPTZ,
  p_post_count    INTEGER,
  p_new_authors   INTEGER,
  p_engagement    FLOAT,
  p_sentiment     FLOAT
) RETURNS VOID AS $$
BEGIN
  INSERT INTO narrative_timeline
    (narrative_id, bucket, post_count, new_authors, engagement, sentiment_score)
  VALUES
    (p_narrative_id, p_bucket, p_post_count, p_new_authors, p_engagement, p_sentiment)
  ON CONFLICT (narrative_id, bucket) DO UPDATE SET
    post_count    = narrative_timeline.post_count    + EXCLUDED.post_count,
    new_authors   = narrative_timeline.new_authors   + EXCLUDED.new_authors,
    engagement    = narrative_timeline.engagement    + EXCLUDED.engagement,
    sentiment_score = (narrative_timeline.sentiment_score + EXCLUDED.sentiment_score) / 2.0;
END;
$$ LANGUAGE plpgsql;
