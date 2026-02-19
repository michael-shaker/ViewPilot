# ViewPilot — YouTube Creator Intelligence Platform

## Communication Style (ALWAYS FOLLOW)
- **Before writing any file or making any change**, give a short plain-English paragraph explaining what it does and why — like explaining to someone who isn't a developer. One paragraph max, no jargon.
- Keep all code comments lowercase and natural/conversational, not formal or technical-sounding.

## What This Is
A portfolio project: YouTube analytics platform that uses YouTube Data API v3 + Analytics API to analyze channel performance, detect patterns in top vs bottom performing videos, and provide AI-powered title optimization and clustering.

## Tech Stack (Confirmed Decisions)
- **Backend:** Python FastAPI — REST (`/api/v1/`) + GraphQL (`/graphql` via Strawberry)
- **Frontend:** Vue 3 / Nuxt 3 (NOT React/Next — intentionally different for portfolio) + Tailwind CSS
- **Database:** PostgreSQL with pgvector extension (Supabase free tier in prod, Docker locally)
- **Cache:** Redis (Upstash free tier in prod, Docker locally) — used for caching expensive ML results (clusters, embeddings, autopsy reports), NOT for rate limiting
- **Embeddings:** Local sentence-transformers (`all-MiniLM-L6-v2`, 384-dim, ~80MB model, $0 cost, CPU-only)
- **AI Explanations:** Google Gemini API (free tier) — generates plain-English insights from ML results
- **Background Jobs:** APScheduler (in-process, no separate worker)
- **Real-time:** WebSockets — live progress updates during YouTube sync
- **DevOps:** Docker + Docker Compose for local dev, GitHub Actions CI/CD
- **Hosting target:** <$10/mo (Railway $5 for API, Cloudflare Pages free for frontend, Supabase free for DB, Upstash free for Redis)

## Constraints
- **Compute:** CPU only (no GPU) — all ML must be lightweight
- **API budget:** $0 — only free tiers (Gemini API free tier for LLM calls)
- **Scale:** Solo user / tiny user base — no heavy rate limiting needed
- **Subscriptions:** Claude.ai + ChatGPT Plus ($20/mo each) are chat interfaces only, NOT usable as APIs in code

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
- [x] Project scaffolding (pyproject.toml, docker-compose.yml, Dockerfile, .gitignore, .env.example)
- [x] Alembic setup (alembic.ini, env.py, migrations folder, initial migration run successfully)
- [x] Database schema + SQLAlchemy models (all 10 tables created and live in Postgres)
- [x] Google OAuth + YouTube channel connect (full flow working, user saved to DB)
- [x] Video data import pipeline — sync working, 223 videos imported from channel
- [x] Basic REST API — /auth, /channels, /channels/sync, /videos, /videos/{id}
- [ ] GraphQL API (Strawberry)
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

## Core Analysis Philosophy — Recency Window Comparisons
**IMPORTANT:** Never compare all videos against each other globally. The channel has years of content where early videos are objectively worse due to lower skill/production quality. Comparing old vs new would produce useless conclusions.

Instead, ALL comparisons (autopsy, clustering, Title Lab, predictions) must operate within a **recency window** — the N most recent videos by publish date:
- **Window size is configurable:** 20, 50, 100 etc. Default: 50
- **Two comparison modes within the window:**
  - Broad: top 50% vs bottom 50% (general pattern detection)
  - Extreme: top 10-20% vs bottom 10-20% (strongest signal, clearest contrast)
- **Ranking metric:** primarily views, secondarily watch time
- **The goal:** compare videos made in the same era of the channel — similar skill level, similar audience size, similar production quality. Finds what's working *right now*, not historically.

## Key Architecture Decisions
- Single FastAPI service handles everything (REST, GraphQL, auth, background jobs, ML) to stay cheap
- pgvector for embedding storage + similarity search (cosine distance via `<=>` operator)
- Embeddings: 0.9*title + 0.1*description weighted average for combined embedding
- Clustering: k-means with silhouette score selection (k=2..10), HDBSCAN fallback
- Title Lab scoring: avg(similarity to top clusters) - avg(similarity to bottom clusters)
- Prediction: GradientBoosting on title embedding + metadata features, binary (top 50% vs bottom 50%)
- No heavy rate limiting needed (solo/tiny user base) — Redis is for ML result caching only
- Redis cache targets: cluster results (1hr TTL), Title Lab scores (24hr TTL), autopsy reports (1hr TTL), channel stats (30min TTL)
- Gemini API (free tier) handles plain-English explanation generation from ML pattern data
- WebSockets for real-time sync progress feedback
- sentence-transformers runs on CPU — lightweight enough for solo use, no GPU needed

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
- `.env.example`: all env vars documented
- `.gitignore`: Python, uv, env, ML models, Nuxt, Docker volumes

### 2026-02-18 — Architecture Decisions Finalized
**Decisions made:**
- Redis kept but repurposed: caching ML results only (not rate limiting)
- Gemini API (free tier) added for plain-English AI explanations
- WebSockets added for real-time sync progress
- Tailwind CSS added for frontend styling
- sentence-transformers confirmed as CPU-only lightweight local ML
- No rate limiting needed (solo user base)
- $0 API budget — free tiers only
**Completed:**
- `backend/app/config.py`: pydantic-settings, reads .env, includes gemini + youtube api keys
- `backend/app/database.py`: async sqlalchemy engine, session factory, Base class, get_db dependency
- `backend/app/main.py`: FastAPI app, CORS middleware, lifespan hook, /health endpoint
**Next:** alembic setup → database models → routes

### 2026-02-19 — Phase 1 Core Complete
**Completed:**
- Alembic fully set up (alembic.ini, env.py, script.py.mako, versions/)
- All 10 SQLAlchemy models written and live in Postgres via initial migration
- Google Cloud Console project created, YouTube Data API v3 + Analytics API enabled
- OAuth credentials created and saved to .env
- Full Google OAuth flow working — login, token storage (encrypted), session cookie
- Video import pipeline working — syncs channel info + all videos in batches of 50
- 223 videos successfully imported from the Shakes channel
- REST API routes: /auth/google, /auth/me, /auth/logout, /channels, /channels/sync, /videos, /videos/{id}
- Recency window comparison philosophy locked into architecture (never compare all-time, always compare within N most recent)
- Embedding ratio updated to 0.9 title / 0.1 description

**Key files created:**
- `backend/alembic/` — full alembic setup
- `backend/app/models/` — users, channels, videos, stats, ml, alerts
- `backend/app/utils/security.py` — fernet token encryption
- `backend/app/utils/dependencies.py` — get_current_user dependency
- `backend/app/utils/youtube_parser.py` — ISO 8601 duration parser
- `backend/app/services/auth.py` — get_or_create_user
- `backend/app/services/youtube.py` — youtube api client (async wrapper)
- `backend/app/services/sync.py` — full channel sync orchestration
- `backend/app/api/v1/auth.py` — auth routes
- `backend/app/api/v1/channels.py` — channel routes
- `backend/app/api/v1/videos.py` — video list + detail routes

**How to resume:**
1. Make sure Docker Desktop is running
2. `docker compose up -d db redis` from project root
3. `cd backend && uv run uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload`
4. Login at `http://localhost:8000/api/v1/auth/google`

**Next session:** GraphQL API → Nuxt frontend setup → APScheduler background job
