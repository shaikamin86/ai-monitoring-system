# SENTINEL — Malaysia AI Social Monitor

> Production-ready AI-powered social media intelligence platform for Malaysia

---

## Overview

SENTINEL monitors social media across 7 platforms in real-time, detecting narratives, threats, and emerging issues in Bahasa Malaysia, English, and mixed social media slang — even when exact keywords are not mentioned.

## Architecture

```
Social Media → FastAPI Backend → Supabase/PostgreSQL
                    ↓                    ↑
               OpenAI APIs      pgvector embeddings
                    ↓
             Next.js Dashboard (WebSocket real-time)
```

## Key Capabilities

| Capability | Implementation |
|------------|---------------|
| Exact Keyword Matching | Watch terms table + real-time check |
| Semantic Topic Detection | OpenAI text-embedding-3-small + pgvector |
| Entity Recognition | GPT-4o-mini NER (BM + EN) |
| Narrative Clustering | DBSCAN on 1536-dim cosine similarity |
| Hashtag Tracking | Extracted + hourly trend buckets |
| Influencer Tracking | Auto-profiled + influence scoring |
| Emerging Issue Detection | 3x spike detection, sentiment shift alerts |
| Multi-Language | BM/EN/mixed with slang normalization |

## Tech Stack

- **Frontend**: Next.js 15, TypeScript, TailwindCSS, Recharts, Framer Motion
- **Backend**: FastAPI, Python 3.12, Pydantic v2, structlog
- **Database**: Supabase (PostgreSQL + pgvector)
- **AI**: OpenAI GPT-4o-mini (NLP) + text-embedding-3-small
- **Cache**: Redis
- **Real-time**: WebSocket

## Quick Start

```bash
# 1. Clone & configure
cp .env.example .env
# Fill in SUPABASE_URL, SUPABASE_SERVICE_KEY, OPENAI_API_KEY

# 2. Run database migrations in Supabase SQL editor
# supabase/migrations/001_initial_schema.sql
# supabase/migrations/002_rls_policies.sql
# supabase/migrations/003_semantic_search.sql

# 3. Start backend
cd backend && pip install -r requirements.txt
uvicorn main:app --reload

# 4. Start frontend
cd frontend && npm install && npm run dev

# OR: Docker Compose
docker-compose up -d
```

Open [http://localhost:3000](http://localhost:3000)

## Dashboard Features

- **Real-Time Dashboard** — Live metrics, trend charts, sentiment gauge
- **Narrative Intelligence Map** — Threat-level heatmap of active narratives
- **Alert Center** — Severity-based alerts with acknowledge/resolve workflow
- **Influencer Tracking** — Influence scoring, flag mechanism, activity timeline
- **Semantic Search** — AI-powered search by meaning, not just keywords
- **Trend Analysis** — Configurable time windows, platform breakdown
- **Report Generation** — Export executive, narrative, and alert reports as CSV

## Project Structure

```
├── frontend/           # Next.js app
│   └── src/
│       ├── app/        # Pages (dashboard, narratives, alerts, search, reports)
│       ├── components/ # UI components
│       ├── lib/        # API client, WebSocket, utilities
│       └── types/      # TypeScript types
├── backend/            # FastAPI app
│   └── app/
│       ├── api/        # Route handlers
│       ├── services/   # Business logic (NLP, embedding, narrative, alert)
│       ├── models/     # Pydantic models
│       └── workers/    # Background tasks
├── supabase/migrations/ # SQL schema + RLS + functions
└── docs/               # Architecture + deployment guides
```

## Documentation

- [Architecture](docs/ARCHITECTURE.md)
- [Deployment](docs/DEPLOYMENT.md)

---

*Classification: CONFIDENTIAL // Malaysia Intelligence System*
