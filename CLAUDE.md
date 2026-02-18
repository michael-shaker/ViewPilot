# ViewPilot — YouTube Creator Intelligence Platform

## What This Is
A portfolio project: YouTube analytics platform that uses YouTube Data API v3 + Analytics API to analyze channel performance, detect patterns in top vs bottom performing videos, and provide AI-powered title optimization and clustering.

## Tech Stack (Confirmed Decisions)
- **Backend:** Python FastAPI — REST (`/api/v1/`) + GraphQL (`/graphql` via Strawberry)
- **Frontend:** Vue 3 / Nuxt 3 (NOT React/Next — intentionally different for portfolio)
- **Database:** PostgreSQL with pgvector extension (Supabase free tier in prod, Docker locally)
- **Cache:** Redis (Upstash free tier in prod, Docker locally)
- **Embeddings:** Local sentence-transformers (`all-MiniLM-L6-v2`, 384-dim, ~80MB model, $0 cost)
- **Background Jobs:** APScheduler (in-process, no separate worker)
- **DevOps:** Docker + Docker Compose for local dev, GitHub Actions CI/CD
- **Hosting target:** <$10/mo (Railway $5 for API, Cloudflare Pages free for frontend, Supabase free for DB, Upstash free for Redis)

## YouTube APIs Used
- **Data API v3:** channels.list, playlistItems.list, videos.list (batch 50), videoCategories.list, playlists.list
- **Analytics API:** reports.query (per-video metrics: CTR, avg view duration, impressions, traffic sources)
- **OAuth scopes:** youtube.readonly, yt-analytics.readonly, userinfo.email, userinfo.profile
- **Quota:** 10,000 units/day (Data API), 200 requests/day (Analytics API)

## Development Environment
- **Python version:** 3.13 (installed via Microsoft Store on Windows)
- **Python command:** Use `py` not `python` on this Windows machine
- **Package manager:** uv
- **Local services:** Docker Compose runs: api (FastAPI), db (pgvector/pgvector:pg16), redis (redis:7-alpine)
- **Frontend dev server not set up yet** — Node.js will be needed later for Nuxt 3

## Current Progress

### Phase 1: Foundation (MVP Core) — IN PROGRESS
- [x] Plan created and approved
- [ ] Project scaffolding (repo structure, Docker Compose, pyproject.toml, linting)
- [ ] Database schema + SQLAlchemy models (10 tables: users, channels, videos, video_stats, video_analytics, video_embeddings, clusters, cluster_memberships, predictions, alerts)
- [ ] Google OAuth + YouTube channel connect
- [ ] Video data import pipeline (Data API v3)
- [ ] Basic REST + GraphQL API
- [ ] Nuxt frontend (auth flow, dashboard, video table)
- [ ] Scheduled refresh (APScheduler background job)

### Phase 2: Analytics & Insights — NOT STARTED
- [ ] YouTube Analytics API integration (CTR, avg view duration, traffic sources)
- [ ] View velocity calculations (views/day, first 24h/7d performance)
- [ ] Best vs Worst Autopsy (top 10% vs bottom 10% pattern detection)
- [ ] Dashboard enhancements (charts, sparklines, date range filters)
- [ ] Video detail view

### Phase 3: AI & Clustering — NOT STARTED
- [ ] Embedding pipeline (sentence-transformers → pgvector)
- [ ] Clustering (k-means / HDBSCAN, auto-labeling)
- [ ] Similarity scoring
- [ ] Title Lab (score draft titles against winning/losing clusters)
- [ ] Top 10 vs Bottom 10 AI analysis
- [ ] Simple prediction model (gradient boosting)

### Phase 4: Reports, Alerts & Polish — NOT STARTED
- [ ] Weekly recap report
- [ ] Alerts system
- [ ] PDF export (optional)
- [ ] Full CI/CD pipeline
- [ ] Production deployment
- [ ] Polish (error handling, loading states, responsive design)

## Key Architecture Decisions
- Single FastAPI service handles everything (REST, GraphQL, auth, background jobs, ML) to stay cheap
- pgvector for embedding storage + similarity search (cosine distance via `<=>` operator)
- Embeddings: 0.7*title + 0.3*description weighted average for combined embedding
- Clustering: k-means with silhouette score selection (k=2..10), HDBSCAN fallback
- Title Lab scoring: avg(similarity to top clusters) - avg(similarity to bottom clusters)
- Prediction: GradientBoosting on title embedding + metadata features, binary (top 50% vs bottom 50%)
- Rate limit strategy: batch video.list calls (50 per request), track quota in Redis, incremental sync

## Database Schema Overview
See `docs/architecture.md` for full column-level schema. Tables:
- `users` — Google OAuth users with encrypted tokens
- `channels` — YouTube channels linked to users
- `videos` — Video metadata (title, tags, duration, category, etc.)
- `video_stats` — Time-series snapshots (views, likes, comments)
- `video_analytics` — Analytics API data (CTR, avg view duration, impressions, traffic)
- `video_embeddings` — VECTOR(384) embeddings from sentence-transformers
- `clusters` — Auto-generated clusters with centroids
- `cluster_memberships` — Video-to-cluster assignments
- `predictions` — Title scoring results with reasoning
- `alerts` — Underperformance/trending alerts

## Repo Structure
```
backend/           → FastAPI app (app/main.py is entry point)
  app/
    api/v1/        → REST route handlers
    graphql/       → Strawberry GraphQL schema
    models/        → SQLAlchemy ORM models
    schemas/       → Pydantic request/response schemas
    services/      → Business logic layer
    jobs/          → APScheduler background tasks
    utils/         → Helpers (security, YouTube parsing)
  tests/           → pytest test suite
  alembic/         → DB migrations
frontend/          → Nuxt 3 app (not started yet)
docs/              → Architecture docs
docker-compose.yml → Local dev: api + db + redis
```

## Conventions
- Use `ruff` for Python linting and formatting
- Use `pytest` for testing with async support
- All API responses follow consistent Pydantic schema patterns
- Environment variables via pydantic-settings (`.env` file)
- Alembic for database migrations
- SQLAlchemy async (asyncpg driver)

## Session Log

### 2026-02-17 — Phase 1 Scaffolding (IN PROGRESS)
**Status:** Building foundational project files. Nothing committed yet — `backend/` is untracked.
**Last action:** Created `backend/Dockerfile`
- `backend/pyproject.toml`: uv project, Python 3.13, all deps + ruff/pytest config
- `docker-compose.yml`: api (uvicorn --reload), db (pgvector/pgvector:pg16, healthcheck), redis (7-alpine)
- `backend/Dockerfile`: python:3.13-slim, uv install, copies app/alembic/alembic.ini, CMD uvicorn
**Next:** .env.example → .gitignore → config.py → database.py → main.py → alembic setup
