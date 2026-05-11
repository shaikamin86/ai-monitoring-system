-- Enable required extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "vector";
CREATE EXTENSION IF NOT EXISTS "pg_trgm";

-- ============================================================
-- ENUMS
-- ============================================================
CREATE TYPE sentiment_type AS ENUM ('positive', 'negative', 'neutral', 'mixed');
CREATE TYPE language_type AS ENUM ('ms', 'en', 'mixed', 'other');
CREATE TYPE alert_severity AS ENUM ('low', 'medium', 'high', 'critical');
CREATE TYPE alert_status AS ENUM ('active', 'acknowledged', 'resolved', 'dismissed');
CREATE TYPE platform_type AS ENUM ('twitter', 'facebook', 'instagram', 'tiktok', 'reddit', 'telegram', 'news', 'youtube', 'other');
CREATE TYPE narrative_status AS ENUM ('emerging', 'active', 'declining', 'dormant');

-- ============================================================
-- POSTS TABLE
-- ============================================================
CREATE TABLE posts (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  external_id TEXT,
  platform platform_type NOT NULL,
  content TEXT NOT NULL,
  content_normalized TEXT,
  author_id TEXT,
  author_username TEXT,
  author_display_name TEXT,
  author_followers INTEGER DEFAULT 0,
  author_verified BOOLEAN DEFAULT FALSE,
  url TEXT,
  language language_type DEFAULT 'en',
  sentiment sentiment_type,
  sentiment_score FLOAT,
  embedding vector(1536),
  engagement_score FLOAT DEFAULT 0,
  likes_count INTEGER DEFAULT 0,
  shares_count INTEGER DEFAULT 0,
  comments_count INTEGER DEFAULT 0,
  views_count INTEGER DEFAULT 0,
  is_repost BOOLEAN DEFAULT FALSE,
  original_post_id UUID REFERENCES posts(id),
  posted_at TIMESTAMPTZ NOT NULL,
  collected_at TIMESTAMPTZ DEFAULT NOW(),
  processed_at TIMESTAMPTZ,
  metadata JSONB DEFAULT '{}',
  UNIQUE(platform, external_id)
);

CREATE INDEX idx_posts_posted_at ON posts(posted_at DESC);
CREATE INDEX idx_posts_platform ON posts(platform);
CREATE INDEX idx_posts_language ON posts(language);
CREATE INDEX idx_posts_sentiment ON posts(sentiment);
CREATE INDEX idx_posts_author_id ON posts(author_id);
CREATE INDEX idx_posts_embedding ON posts USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100);
CREATE INDEX idx_posts_content_trgm ON posts USING gin(content gin_trgm_ops);
CREATE INDEX idx_posts_engagement ON posts(engagement_score DESC);

-- ============================================================
-- ENTITIES TABLE
-- ============================================================
CREATE TABLE entities (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  name TEXT NOT NULL,
  type TEXT NOT NULL, -- PERSON, ORG, LOCATION, EVENT, PRODUCT, TOPIC
  normalized_name TEXT NOT NULL,
  aliases TEXT[] DEFAULT '{}',
  description TEXT,
  importance_score FLOAT DEFAULT 0,
  first_seen TIMESTAMPTZ DEFAULT NOW(),
  last_seen TIMESTAMPTZ DEFAULT NOW(),
  metadata JSONB DEFAULT '{}'
);

CREATE UNIQUE INDEX idx_entities_normalized ON entities(normalized_name, type);
CREATE INDEX idx_entities_type ON entities(type);
CREATE INDEX idx_entities_importance ON entities(importance_score DESC);

-- ============================================================
-- POST ENTITIES (junction)
-- ============================================================
CREATE TABLE post_entities (
  post_id UUID REFERENCES posts(id) ON DELETE CASCADE,
  entity_id UUID REFERENCES entities(id) ON DELETE CASCADE,
  context TEXT,
  confidence FLOAT DEFAULT 1.0,
  PRIMARY KEY (post_id, entity_id)
);

-- ============================================================
-- HASHTAGS TABLE
-- ============================================================
CREATE TABLE hashtags (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  tag TEXT NOT NULL UNIQUE,
  first_seen TIMESTAMPTZ DEFAULT NOW(),
  last_seen TIMESTAMPTZ DEFAULT NOW(),
  total_count INTEGER DEFAULT 0,
  metadata JSONB DEFAULT '{}'
);

CREATE INDEX idx_hashtags_tag ON hashtags(tag);
CREATE INDEX idx_hashtags_total_count ON hashtags(total_count DESC);

-- ============================================================
-- POST HASHTAGS (junction)
-- ============================================================
CREATE TABLE post_hashtags (
  post_id UUID REFERENCES posts(id) ON DELETE CASCADE,
  hashtag_id UUID REFERENCES hashtags(id) ON DELETE CASCADE,
  PRIMARY KEY (post_id, hashtag_id)
);

-- ============================================================
-- HASHTAG TRENDS (time series)
-- ============================================================
CREATE TABLE hashtag_trends (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  hashtag_id UUID REFERENCES hashtags(id) ON DELETE CASCADE,
  bucket TIMESTAMPTZ NOT NULL, -- hourly buckets
  count INTEGER DEFAULT 0,
  sentiment_positive INTEGER DEFAULT 0,
  sentiment_negative INTEGER DEFAULT 0,
  sentiment_neutral INTEGER DEFAULT 0,
  engagement_total FLOAT DEFAULT 0,
  UNIQUE(hashtag_id, bucket)
);

CREATE INDEX idx_hashtag_trends_bucket ON hashtag_trends(bucket DESC);

-- ============================================================
-- NARRATIVES TABLE
-- ============================================================
CREATE TABLE narratives (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  title TEXT NOT NULL,
  summary TEXT,
  description TEXT,
  status narrative_status DEFAULT 'emerging',
  centroid_embedding vector(1536),
  key_themes TEXT[] DEFAULT '{}',
  key_entities UUID[] DEFAULT '{}',
  key_hashtags TEXT[] DEFAULT '{}',
  sentiment_distribution JSONB DEFAULT '{"positive": 0, "negative": 0, "neutral": 0}',
  post_count INTEGER DEFAULT 0,
  unique_authors INTEGER DEFAULT 0,
  engagement_total FLOAT DEFAULT 0,
  virality_score FLOAT DEFAULT 0,
  threat_level INTEGER DEFAULT 0 CHECK (threat_level >= 0 AND threat_level <= 10),
  first_detected TIMESTAMPTZ DEFAULT NOW(),
  last_activity TIMESTAMPTZ DEFAULT NOW(),
  peak_time TIMESTAMPTZ,
  is_coordinated BOOLEAN DEFAULT FALSE,
  languages JSONB DEFAULT '{}',
  platforms JSONB DEFAULT '{}',
  metadata JSONB DEFAULT '{}'
);

CREATE INDEX idx_narratives_status ON narratives(status);
CREATE INDEX idx_narratives_threat ON narratives(threat_level DESC);
CREATE INDEX idx_narratives_last_activity ON narratives(last_activity DESC);
CREATE INDEX idx_narratives_centroid ON narratives USING ivfflat (centroid_embedding vector_cosine_ops) WITH (lists = 100);
CREATE INDEX idx_narratives_virality ON narratives(virality_score DESC);

-- ============================================================
-- POST NARRATIVES (junction)
-- ============================================================
CREATE TABLE post_narratives (
  post_id UUID REFERENCES posts(id) ON DELETE CASCADE,
  narrative_id UUID REFERENCES narratives(id) ON DELETE CASCADE,
  similarity_score FLOAT DEFAULT 0,
  assigned_at TIMESTAMPTZ DEFAULT NOW(),
  PRIMARY KEY (post_id, narrative_id)
);

-- ============================================================
-- NARRATIVE EVOLUTION (time series)
-- ============================================================
CREATE TABLE narrative_timeline (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  narrative_id UUID REFERENCES narratives(id) ON DELETE CASCADE,
  bucket TIMESTAMPTZ NOT NULL,
  post_count INTEGER DEFAULT 0,
  new_authors INTEGER DEFAULT 0,
  engagement FLOAT DEFAULT 0,
  sentiment_score FLOAT DEFAULT 0,
  UNIQUE(narrative_id, bucket)
);

CREATE INDEX idx_narrative_timeline_bucket ON narrative_timeline(bucket DESC);

-- ============================================================
-- KEYWORDS / WATCH TERMS
-- ============================================================
CREATE TABLE watch_terms (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  term TEXT NOT NULL,
  term_type TEXT DEFAULT 'keyword', -- keyword, regex, semantic
  category TEXT,
  description TEXT,
  is_active BOOLEAN DEFAULT TRUE,
  alert_on_match BOOLEAN DEFAULT TRUE,
  alert_severity alert_severity DEFAULT 'medium',
  match_count INTEGER DEFAULT 0,
  created_by TEXT,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_watch_terms_active ON watch_terms(is_active) WHERE is_active = TRUE;
CREATE INDEX idx_watch_terms_term ON watch_terms(term);

-- ============================================================
-- INFLUENCERS TABLE
-- ============================================================
CREATE TABLE influencers (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  platform platform_type NOT NULL,
  platform_user_id TEXT NOT NULL,
  username TEXT NOT NULL,
  display_name TEXT,
  bio TEXT,
  followers_count INTEGER DEFAULT 0,
  following_count INTEGER DEFAULT 0,
  posts_count INTEGER DEFAULT 0,
  verified BOOLEAN DEFAULT FALSE,
  influence_score FLOAT DEFAULT 0,
  avg_engagement_rate FLOAT DEFAULT 0,
  primary_language language_type DEFAULT 'en',
  primary_topics TEXT[] DEFAULT '{}',
  sentiment_lean sentiment_type DEFAULT 'neutral',
  is_monitored BOOLEAN DEFAULT TRUE,
  is_flagged BOOLEAN DEFAULT FALSE,
  flag_reason TEXT,
  first_seen TIMESTAMPTZ DEFAULT NOW(),
  last_active TIMESTAMPTZ DEFAULT NOW(),
  metadata JSONB DEFAULT '{}',
  UNIQUE(platform, platform_user_id)
);

CREATE INDEX idx_influencers_platform ON influencers(platform);
CREATE INDEX idx_influencers_influence ON influencers(influence_score DESC);
CREATE INDEX idx_influencers_flagged ON influencers(is_flagged) WHERE is_flagged = TRUE;
CREATE INDEX idx_influencers_monitored ON influencers(is_monitored) WHERE is_monitored = TRUE;

-- ============================================================
-- INFLUENCER ACTIVITY (time series)
-- ============================================================
CREATE TABLE influencer_activity (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  influencer_id UUID REFERENCES influencers(id) ON DELETE CASCADE,
  bucket TIMESTAMPTZ NOT NULL,
  post_count INTEGER DEFAULT 0,
  avg_sentiment FLOAT DEFAULT 0,
  total_engagement FLOAT DEFAULT 0,
  top_narrative_id UUID REFERENCES narratives(id),
  UNIQUE(influencer_id, bucket)
);

-- ============================================================
-- ALERTS TABLE
-- ============================================================
CREATE TABLE alerts (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  title TEXT NOT NULL,
  description TEXT,
  severity alert_severity NOT NULL,
  status alert_status DEFAULT 'active',
  alert_type TEXT NOT NULL, -- narrative_spike, keyword_match, influencer_activity, sentiment_shift, viral_content, coordinated_behavior
  source_id UUID, -- reference to narrative, post, influencer, etc.
  source_type TEXT,
  trigger_data JSONB DEFAULT '{}',
  affected_platforms TEXT[] DEFAULT '{}',
  affected_languages TEXT[] DEFAULT '{}',
  post_count INTEGER DEFAULT 0,
  reach_estimate INTEGER DEFAULT 0,
  acknowledged_by TEXT,
  acknowledged_at TIMESTAMPTZ,
  resolved_by TEXT,
  resolved_at TIMESTAMPTZ,
  notes TEXT,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  expires_at TIMESTAMPTZ
);

CREATE INDEX idx_alerts_status ON alerts(status);
CREATE INDEX idx_alerts_severity ON alerts(severity);
CREATE INDEX idx_alerts_created_at ON alerts(created_at DESC);
CREATE INDEX idx_alerts_type ON alerts(alert_type);

-- ============================================================
-- ANALYTICS SNAPSHOTS
-- ============================================================
CREATE TABLE analytics_snapshots (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  bucket TIMESTAMPTZ NOT NULL UNIQUE,
  total_posts INTEGER DEFAULT 0,
  posts_by_platform JSONB DEFAULT '{}',
  posts_by_language JSONB DEFAULT '{}',
  sentiment_distribution JSONB DEFAULT '{}',
  top_hashtags JSONB DEFAULT '[]',
  top_narratives JSONB DEFAULT '[]',
  top_entities JSONB DEFAULT '[]',
  active_alerts INTEGER DEFAULT 0,
  total_reach BIGINT DEFAULT 0,
  emerging_topics JSONB DEFAULT '[]',
  computed_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_analytics_snapshots_bucket ON analytics_snapshots(bucket DESC);

-- ============================================================
-- REPORTS TABLE
-- ============================================================
CREATE TABLE reports (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  title TEXT NOT NULL,
  report_type TEXT NOT NULL, -- daily, weekly, narrative, incident, custom
  parameters JSONB DEFAULT '{}',
  content JSONB DEFAULT '{}',
  file_url TEXT,
  created_by TEXT,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  period_start TIMESTAMPTZ,
  period_end TIMESTAMPTZ
);

-- ============================================================
-- SEARCH INDEX HELPER VIEW
-- ============================================================
CREATE VIEW post_search_view AS
SELECT
  p.id,
  p.content,
  p.platform,
  p.language,
  p.sentiment,
  p.sentiment_score,
  p.author_username,
  p.author_followers,
  p.author_verified,
  p.engagement_score,
  p.posted_at,
  p.url,
  array_agg(DISTINCT h.tag) FILTER (WHERE h.tag IS NOT NULL) AS hashtags,
  array_agg(DISTINCT e.name) FILTER (WHERE e.name IS NOT NULL) AS entities
FROM posts p
LEFT JOIN post_hashtags ph ON p.id = ph.post_id
LEFT JOIN hashtags h ON ph.hashtag_id = h.id
LEFT JOIN post_entities pe ON p.id = pe.post_id
LEFT JOIN entities e ON pe.entity_id = e.id
GROUP BY p.id;

-- ============================================================
-- FUNCTIONS
-- ============================================================

-- Update narrative stats after post assignment
CREATE OR REPLACE FUNCTION update_narrative_stats(p_narrative_id UUID)
RETURNS VOID AS $$
BEGIN
  UPDATE narratives n
  SET
    post_count = stats.post_count,
    unique_authors = stats.unique_authors,
    engagement_total = stats.engagement_total,
    last_activity = stats.last_activity,
    sentiment_distribution = stats.sentiment_dist
  FROM (
    SELECT
      COUNT(p.id) AS post_count,
      COUNT(DISTINCT p.author_id) AS unique_authors,
      SUM(p.engagement_score) AS engagement_total,
      MAX(p.posted_at) AS last_activity,
      jsonb_build_object(
        'positive', COUNT(*) FILTER (WHERE p.sentiment = 'positive'),
        'negative', COUNT(*) FILTER (WHERE p.sentiment = 'negative'),
        'neutral', COUNT(*) FILTER (WHERE p.sentiment = 'neutral'),
        'mixed', COUNT(*) FILTER (WHERE p.sentiment = 'mixed')
      ) AS sentiment_dist
    FROM post_narratives pn
    JOIN posts p ON pn.post_id = p.id
    WHERE pn.narrative_id = p_narrative_id
  ) stats
  WHERE n.id = p_narrative_id;
END;
$$ LANGUAGE plpgsql;

-- Compute engagement score for a post
CREATE OR REPLACE FUNCTION compute_engagement_score(
  p_likes INTEGER,
  p_shares INTEGER,
  p_comments INTEGER,
  p_views INTEGER,
  p_followers INTEGER
) RETURNS FLOAT AS $$
DECLARE
  raw_engagement FLOAT;
  engagement_rate FLOAT;
BEGIN
  raw_engagement := p_likes + (p_shares * 3) + (p_comments * 2);
  IF p_followers > 0 THEN
    engagement_rate := raw_engagement / p_followers * 100;
  ELSE
    engagement_rate := raw_engagement;
  END IF;
  -- Normalize to 0-100 scale using log
  RETURN LEAST(100, LN(GREATEST(1, raw_engagement) + 1) * 10 + engagement_rate);
END;
$$ LANGUAGE plpgsql;

-- Update hashtag trends on new post
CREATE OR REPLACE FUNCTION update_hashtag_trends()
RETURNS TRIGGER AS $$
DECLARE
  h_bucket TIMESTAMPTZ;
BEGIN
  h_bucket := date_trunc('hour', (SELECT posted_at FROM posts WHERE id = NEW.post_id));

  INSERT INTO hashtag_trends (hashtag_id, bucket, count, sentiment_positive, sentiment_negative, sentiment_neutral)
  VALUES (NEW.hashtag_id, h_bucket, 1, 0, 0, 0)
  ON CONFLICT (hashtag_id, bucket) DO UPDATE
  SET count = hashtag_trends.count + 1;

  UPDATE hashtags SET
    last_seen = (SELECT posted_at FROM posts WHERE id = NEW.post_id),
    total_count = total_count + 1
  WHERE id = NEW.hashtag_id;

  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trigger_update_hashtag_trends
AFTER INSERT ON post_hashtags
FOR EACH ROW EXECUTE FUNCTION update_hashtag_trends();

-- ============================================================
-- SEED DATA: Default Watch Terms for Malaysia
-- ============================================================
INSERT INTO watch_terms (term, term_type, category, description, alert_severity) VALUES
  ('keselamatan negara', 'keyword', 'national_security', 'National security', 'high'),
  ('ancaman', 'keyword', 'threat', 'Threat mentions', 'high'),
  ('darurat', 'keyword', 'emergency', 'Emergency declarations', 'critical'),
  ('rusuhan', 'keyword', 'civil_unrest', 'Riot/unrest mentions', 'critical'),
  ('demonstrasi', 'keyword', 'protest', 'Demonstration mentions', 'high'),
  ('propaganda', 'keyword', 'disinformation', 'Propaganda content', 'high'),
  ('berita palsu', 'keyword', 'disinformation', 'Fake news (BM)', 'high'),
  ('fake news', 'keyword', 'disinformation', 'Fake news (EN)', 'high'),
  ('hoax', 'keyword', 'disinformation', 'Hoax content', 'medium'),
  ('racial', 'keyword', 'racial_sensitivity', 'Racial content', 'critical'),
  ('kaum', 'keyword', 'racial_sensitivity', 'Race mentions (BM)', 'high'),
  ('agama', 'keyword', 'religious_sensitivity', 'Religion mentions (BM)', 'medium'),
  ('ekonomi', 'keyword', 'economic', 'Economic discussions', 'low'),
  ('inflasi', 'keyword', 'economic', 'Inflation mentions', 'medium'),
  ('rasuah', 'keyword', 'corruption', 'Corruption (BM)', 'high'),
  ('corruption', 'keyword', 'corruption', 'Corruption (EN)', 'high'),
  ('politik', 'keyword', 'political', 'Political content (BM)', 'medium'),
  ('skandal', 'keyword', 'political', 'Scandal mentions', 'high');
