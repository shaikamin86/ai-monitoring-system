# SENTINEL — Malaysia AI Social Monitor: Architecture

## System Overview

SENTINEL is a production-ready, AI-powered social media monitoring platform purpose-built for Malaysia. It ingests, analyzes, and surfaces intelligence from social media across multiple platforms and languages (Bahasa Malaysia, English, mixed slang).

```
┌─────────────────────────────────────────────────────────────────┐
│                      DATA SOURCES                               │
│  Twitter/X  │  Facebook  │  TikTok  │  Telegram  │  News Sites │
└──────────────────────────┬──────────────────────────────────────┘
                           │ Ingest API / Webhooks
                           ▼
┌─────────────────────────────────────────────────────────────────┐
│                    FASTAPI BACKEND                               │
│                                                                 │
│  ┌─────────────┐  ┌──────────────┐  ┌────────────────────────┐│
│  │  Ingestion  │  │  NLP Service │  │  Embedding Service     ││
│  │  Pipeline   │→ │  (OpenAI)    │→ │  (OpenAI text-embed-3) ││
│  └─────────────┘  └──────────────┘  └────────────────────────┘│
│         │                                       │               │
│         ▼                                       ▼               │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │              Narrative Clustering Service                │   │
│  │  DBSCAN on cosine-similarity of 1536-dim embeddings     │   │
│  │  Merges with existing narratives or creates new ones    │   │
│  └─────────────────────────────────────────────────────────┘   │
│         │                                                       │
│         ▼                                                       │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────────┐ │
│  │  Alert       │  │  Analytics   │  │  WebSocket           │ │
│  │  Service     │  │  Service     │  │  (Real-time push)    │ │
│  └──────────────┘  └──────────────┘  └──────────────────────┘ │
└──────────────────────────┬──────────────────────────────────────┘
                           │ Supabase Client (Service Key)
                           ▼
┌─────────────────────────────────────────────────────────────────┐
│                    SUPABASE / POSTGRESQL                        │
│                                                                 │
│  posts (pgvector)  │  narratives  │  alerts  │  influencers    │
│  entities          │  hashtags    │  watch_terms               │
│  analytics_snapshots  │  reports                               │
└──────────────────────────┬──────────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────────┐
│                   NEXT.JS FRONTEND                              │
│                                                                 │
│  Dashboard  │  Narratives  │  Alerts  │  Search  │  Reports    │
│  Trend Charts  │  Sentiment Gauge  │  Heatmap                  │
│  Real-time WebSocket updates                                    │
└─────────────────────────────────────────────────────────────────┘
```

## Core Capabilities

### 1. Exact Keyword Matching
- `watch_terms` table with configurable terms in BM/EN
- Real-time check during ingestion pipeline
- Seeded with 18 Malaysia-specific sensitive topics
- Auto-generates alerts on matches

### 2. Semantic Topic Detection
- OpenAI `text-embedding-3-small` (1536 dimensions)
- Stored in PostgreSQL with `pgvector` extension
- `ivfflat` index for ANN search at scale
- Semantic search via `match_posts` RPC

### 3. Entity Recognition
- GPT-4o-mini extracts: PERSON, ORG, LOCATION, EVENT, PRODUCT, TOPIC
- Multi-language aware (BM + EN + mixed)
- Entity deduplication via `normalized_name`
- Importance scoring based on frequency

### 4. Narrative Clustering
- Posts embedded → 1536-dim vectors
- DBSCAN clustering with cosine distance
- Threshold: 0.82 similarity → same narrative
- New clusters → OpenAI generates title/summary/themes
- Evolution tracking with hourly timeline buckets

### 5. Hashtag Tracking
- Extracted via regex from every post
- Hourly trend buckets in `hashtag_trends`
- Surge detection: 3x baseline triggers alert
- Word cloud visualization on dashboard

### 6. Influencer Tracking
- Auto-profiled from post authors
- Influence score = weighted followers + engagement + volume
- Flag/unflag mechanism for suspicious accounts
- Coordinated behavior detection (diversity ratio, content uniqueness)

### 7. Emerging Issue Detection
- Narrative spike alert: 3x volume increase in 1h
- Hashtag surge: 3x increase in 1h
- Sentiment shift: >70% negative in active narrative
- Anomaly window: rolling 1h vs previous 2h baseline

### 8. Multi-Language Support
- `detect_language()` uses `langdetect` + BM marker heuristics
- BM slang normalization map (xde→tidak ada, nk→nak, etc.)
- GPT-4o-mini analyzes content in its original language
- Language distribution tracked per narrative

## Database Schema Summary

| Table | Purpose |
|-------|---------|
| `posts` | Raw social media content + embeddings |
| `entities` | Named entities extracted from posts |
| `post_entities` | Junction: post ↔ entity |
| `hashtags` | All unique hashtags seen |
| `hashtag_trends` | Hourly hashtag volume buckets |
| `narratives` | Clustered narrative groups |
| `post_narratives` | Junction: post ↔ narrative |
| `narrative_timeline` | Hourly narrative activity buckets |
| `watch_terms` | Monitored keywords/phrases |
| `influencers` | Author profiles |
| `influencer_activity` | Hourly influencer activity |
| `alerts` | Generated alerts |
| `analytics_snapshots` | Hourly system-wide snapshots |
| `reports` | Generated report metadata |

## Background Tasks

| Task | Interval | Purpose |
|------|----------|---------|
| `run_alert_checks` | 60s | Check for spikes/surges/shifts |
| `run_narrative_clustering` | 5m | Cluster unassigned posts |
| `run_analytics_snapshot` | 1h | Compute analytics snapshot |
| `run_influencer_scoring` | 1h | Update influence scores |
| `run_narrative_status_update` | 30m | Mark narratives as declining/dormant |

## API Routes

### Posts
- `POST /api/v1/posts/ingest` — Single post ingestion
- `POST /api/v1/posts/ingest/batch` — Batch ingestion (max 500)
- `POST /api/v1/posts/search` — Keyword + semantic search
- `GET /api/v1/posts/{id}` — Post detail

### Narratives
- `GET /api/v1/narratives` — List narratives (with filters)
- `GET /api/v1/narratives/{id}` — Narrative detail + timeline
- `GET /api/v1/narratives/{id}/posts` — Posts in narrative

### Alerts
- `GET /api/v1/alerts` — List alerts
- `PATCH /api/v1/alerts/{id}` — Update status (ack/resolve/dismiss)
- `POST /api/v1/alerts/run-checks` — Manual trigger

### Analytics
- `GET /api/v1/analytics/dashboard` — Dashboard metrics
- `GET /api/v1/analytics/trends` — Time-series trend data
- `GET /api/v1/analytics/hashtags` — Top hashtags
- `GET /api/v1/analytics/sentiment-timeline` — Sentiment over time
- `GET /api/v1/analytics/platform-breakdown` — By platform

### Influencers
- `GET /api/v1/influencers` — List influencers
- `GET /api/v1/influencers/{id}` — Influencer detail
- `PATCH /api/v1/influencers/{id}/flag` — Flag influencer

### WebSocket
- `WS /ws` — Real-time event stream

## Security Considerations
- Row Level Security (RLS) enabled on all tables
- Service role key used only in backend (never exposed to client)
- Anon key used for frontend read-only access
- JWT-based auth for future user management
- Rate limiting: 120 req/min per IP
- Input validation via Pydantic v2
