-- Semantic similarity search function for posts
CREATE OR REPLACE FUNCTION match_posts(
  query_embedding vector(1536),
  match_threshold float DEFAULT 0.75,
  match_count int DEFAULT 50
)
RETURNS TABLE (
  id uuid,
  content text,
  platform text,
  author_username text,
  author_followers int,
  author_verified bool,
  sentiment text,
  sentiment_score float,
  engagement_score float,
  likes_count int,
  shares_count int,
  comments_count int,
  posted_at timestamptz,
  language text,
  url text,
  similarity float
)
LANGUAGE plpgsql
AS $$
BEGIN
  RETURN QUERY
  SELECT
    p.id,
    p.content,
    p.platform::text,
    p.author_username,
    p.author_followers,
    p.author_verified,
    p.sentiment::text,
    p.sentiment_score,
    p.engagement_score,
    p.likes_count,
    p.shares_count,
    p.comments_count,
    p.posted_at,
    p.language::text,
    p.url,
    1 - (p.embedding <=> query_embedding) AS similarity
  FROM posts p
  WHERE p.embedding IS NOT NULL
    AND 1 - (p.embedding <=> query_embedding) > match_threshold
  ORDER BY p.embedding <=> query_embedding
  LIMIT match_count;
END;
$$;

-- Semantic search for narratives
CREATE OR REPLACE FUNCTION match_narratives(
  query_embedding vector(1536),
  match_threshold float DEFAULT 0.75,
  match_count int DEFAULT 20
)
RETURNS TABLE (
  id uuid,
  title text,
  summary text,
  status text,
  threat_level int,
  post_count int,
  virality_score float,
  similarity float
)
LANGUAGE plpgsql
AS $$
BEGIN
  RETURN QUERY
  SELECT
    n.id,
    n.title,
    n.summary,
    n.status::text,
    n.threat_level,
    n.post_count,
    n.virality_score,
    1 - (n.centroid_embedding <=> query_embedding) AS similarity
  FROM narratives n
  WHERE n.centroid_embedding IS NOT NULL
    AND 1 - (n.centroid_embedding <=> query_embedding) > match_threshold
  ORDER BY n.centroid_embedding <=> query_embedding
  LIMIT match_count;
END;
$$;
