# Deployment Guide

## Prerequisites
- Node.js 22+
- Python 3.12+
- Redis 7+
- Supabase account (with pgvector enabled)
- OpenAI API key

## 1. Supabase Setup

1. Create a new Supabase project
2. Enable the `pgvector` extension:
   ```sql
   CREATE EXTENSION IF NOT EXISTS vector;
   ```
3. Run migrations in order:
   ```bash
   # Using Supabase CLI
   supabase db push
   # Or manually in the SQL editor:
   # supabase/migrations/001_initial_schema.sql
   # supabase/migrations/002_rls_policies.sql
   ```

## 2. Environment Configuration

```bash
cp .env.example .env
# Edit .env with your actual values
```

Required variables:
- `SUPABASE_URL` — Your Supabase project URL
- `SUPABASE_SERVICE_KEY` — Service role key (from Supabase dashboard)
- `SUPABASE_ANON_KEY` — Anon key (safe for frontend)
- `OPENAI_API_KEY` — OpenAI API key

## 3. Local Development

### Backend
```bash
cd backend
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

### Frontend
```bash
cd frontend
npm install
cp ../.env.example .env.local
npm run dev
```

### Redis
```bash
redis-server
# Or with Docker:
docker run -d -p 6379:6379 redis:7-alpine
```

## 4. Docker Deployment

```bash
# Build and start all services
docker-compose up -d

# View logs
docker-compose logs -f backend
docker-compose logs -f frontend

# Stop
docker-compose down
```

## 5. Production Deployment

### Vercel (Frontend)
```bash
cd frontend
npm run build
vercel deploy
```
Set environment variables in Vercel dashboard.

### Railway / Render (Backend)
- Connect GitHub repo
- Set root directory to `backend/`
- Build command: `pip install -r requirements.txt`
- Start command: `uvicorn main:app --host 0.0.0.0 --port $PORT --workers 2`
- Add all environment variables

### Upstash Redis (Managed Redis)
- Create a Redis database at upstash.com
- Copy the `REDIS_URL` to your environment

## 6. Social Platform Integration

To connect real social media data sources, implement collectors that POST to:

```
POST /api/v1/posts/ingest
{
  "external_id": "unique_id",
  "platform": "twitter",
  "content": "post content",
  "author_id": "user_id",
  "author_username": "username",
  "author_followers": 10000,
  "likes_count": 42,
  "shares_count": 12,
  "posted_at": "2025-01-01T12:00:00Z"
}
```

Or batch ingest:
```
POST /api/v1/posts/ingest/batch
[...array of posts...]
```

## 7. Monitoring

- Health check: `GET /health`
- API docs (debug mode): `GET /api/docs`
- Logs: Structured JSON via structlog

## 8. Adding Custom Watch Terms

Via Supabase SQL editor or API:
```sql
INSERT INTO watch_terms (term, term_type, category, alert_severity)
VALUES ('your term', 'keyword', 'your_category', 'high');
```
