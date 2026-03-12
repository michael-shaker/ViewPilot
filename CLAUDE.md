# ViewPilot — YouTube Creator Intelligence Platform

## Communication Style (ALWAYS FOLLOW)
- **Before writing any file or making any change**, give a short plain-English paragraph explaining what it does and why — like explaining to someone who isn't a developer. One paragraph max, no jargon.
- Keep all code comments lowercase and natural/conversational, not formal or technical-sounding.

## Git Commits (ALWAYS FOLLOW)
- **NEVER add a Co-Authored-By line** — commits are always authored by Michael Shaker only, no Claude attribution.
- **Keep commit messages simple, short, and layman-friendly** — no technical jargon, no bullet lists, no elaborate descriptions. Just a plain sentence saying what changed.
- Good example: `"Add error handling to dashboard and logout"`
- Good example: `"Fixed profile picture"`
- Bad example: `"fix(cors): resolve credentials flag inversion in CORSMiddleware debug mode"`

## What This Is
A portfolio project: YouTube analytics platform that uses YouTube Data API v3 + Analytics API to analyze channel performance, detect patterns in top vs bottom performing videos, and provide AI-powered title optimization and clustering.

## Tech Stack (Confirmed Decisions)
- **Backend:** Python FastAPI — REST (`/api/v1/`) + GraphQL (`/graphql` via Strawberry)
- **Frontend:** Vue 3 / Nuxt 3 (NOT React/Next — intentionally different for portfolio) + Tailwind CSS — dark mode aesthetic throughout (dark grays/slate, no white backgrounds)
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
- **Analytics API quota risk:** Each sync uses ~4-5 Analytics API calls. The autopsy page fires 1-2 extra calls on each Compare click (for 30-day recent views). Solo user would need to hit Compare ~90+ times in a single day to approach the 200 request limit — not a real concern in practice, but worth knowing.

## Development Environment
- **Python version:** 3.13 (installed via Microsoft Store on Windows)
- **Python command:** Use `py` not `python` on this Windows machine
- **Package manager:** uv
- **Local services:** Docker Compose runs: api (FastAPI), db (pgvector/pgvector:pg16), redis (redis:7-alpine)
- **Frontend dev server:** Node.js installed, Nuxt 3 running on port 3000 (`cd frontend && npm run dev`)

## Current Progress

### Phase 1: Foundation (MVP Core) — COMPLETE
- [x] Plan created and approved
- [x] Project scaffolding (pyproject.toml, docker-compose.yml, Dockerfile, .gitignore, .env.example)
- [x] Alembic setup (alembic.ini, env.py, migrations folder, initial migration run successfully)
- [x] Database schema + SQLAlchemy models (all 10 tables created and live in Postgres)
- [x] Google OAuth + YouTube channel connect (full flow working, user saved to DB)
- [x] Video data import pipeline — sync working, 223 videos imported from channel
- [x] Basic REST API — /auth, /channels, /channels/sync, /videos, /videos/{id}
- [x] GraphQL API (Strawberry)
- [x] Nuxt frontend (auth flow, dashboard, video table)
- [x] Scheduled refresh (APScheduler — syncs all users every 6 hours automatically)

### Phase 2: Analytics & Insights — IN PROGRESS
- [x] YouTube Analytics API integration (avg view duration, estimated minutes watched — live in DB)
- [x] YouTube Reporting API integration (impressions + CTR via daily CSV — job created, data pending 24-48h)
- [x] View velocity — views per day since publish, shown in dashboard sub-row
- [x] Video detail page — YouTube embed, stat pills, analytics section, description, tags, metadata, stats history table
- [x] Stats history — real daily data from Analytics API, full lifetime coverage (180-day chunks), cumulative totals, today pinned at top with live stats
- [x] Best vs Worst Autopsy — top vs bottom performer comparison page, fully built
- [x] Revenue + RPM — pulled from Analytics API, shown in autopsy and video table
- [x] Dashboard search + date range filter (client-side, covers full library, From/To dropdowns mutually constrained)
- [x] Revenue toggle — red slider on every page, defaults OFF, persists in localStorage via useRevenue composable
- [ ] Dashboard charts / sparklines for view trends
- [ ] Shorts toggle (data is there, `is_short` field exists, just no UI)
- [ ] ~~Shorts toggle~~ — intentionally skipped for now, not a priority while building out the core analytics features

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

### 2026-02-22 — GraphQL API Complete + Mac Dev Setup
**Status:** GraphQL done and tested. Dev environment set up on Mac for the first time.

**Completed:**
- `backend/app/graphql/types.py` — Strawberry type definitions (UserType, ChannelType, VideoStatsType, VideoType, VideosPage)
- `backend/app/graphql/schema.py` — full Query class with resolvers: me, channels, channel(id), videos(channelId, ...), video(id)
- `backend/app/main.py` — GraphQLRouter mounted at `/graphql` with context getter (injects request + db)
- Tested: introspection returns all 5 queries, auth guard returns "not logged in" correctly

**Mac dev environment notes:**
- uv installed at `~/.local/share/uv`
- Local PostgreSQL was running on port 5432 — docker-compose.yml updated to map DB to port **5433** instead
- DATABASE_URL in `.env` updated to port 5433
- Run migrations fresh on any new machine: `cd backend && uv run alembic upgrade head`
- Start server with: `uv run uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload --reload-dir app`
  (use `--reload-dir app` to avoid watchfiles going crazy on the .venv folder)

**How to resume:**
1. Docker Desktop running → `docker compose up -d db redis` (DB on port 5434 — changed from 5433 to avoid Windows local postgres conflict)
2. `cd backend && uv run uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload --reload-dir app`
3. GraphQL playground at `http://localhost:8000/graphql`

### 2026-02-23 — Nuxt 3 Frontend Built

**Completed:**
- Full Nuxt 3 frontend scaffolded and running on port 3000
- Login page with Google OAuth button (dark theme)
- Dashboard with channel stats bar (subscribers, views, video count, last synced)
- Video table with sorting by views/likes/comments/date, pagination (25 per page)
- Sync button, logout button
- Auth middleware protecting dashboard route
- Fixed Tailwind v4 conflict — dropped `@nuxtjs/tailwindcss` module, wired Tailwind v3 manually via PostCSS + `assets/css/main.css`
- Fixed Mac port conflict — Docker DB runs on 5433 instead of 5432

**Key files created:**
- `frontend/package.json` — nuxt 3, tailwindcss 3.4.17, autoprefixer, postcss
- `frontend/nuxt.config.ts` — PostCSS tailwind setup, apiBase runtimeConfig
- `frontend/app.vue` — dark root shell
- `frontend/assets/css/main.css` — tailwind directives
- `frontend/pages/index.vue` — login page
- `frontend/pages/dashboard.vue` — channel stats + video table + sync + logout
- `frontend/composables/useApi.ts` — fetch wrapper with credentials: include
- `frontend/composables/useAuth.ts` — user state, fetchMe, logout
- `frontend/middleware/auth.ts` — route guard

**Blocked on: Google OAuth test user not set up**
- App is in Testing mode on Google Cloud Console
- Need to go to APIs & Services → OAuth consent screen → Test users → add your Google email
- Once done, the full login → dashboard flow should work end to end

**How to resume:**
1. Terminal 1: `cd backend && uv run uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload --reload-dir app`
2. Terminal 2: `cd frontend && npm run dev`
3. Open `http://localhost:3000`, click Sign in with Google
4. After OAuth works, dashboard should show channel stats + video table (DB is empty on this Mac though — need to trigger a sync)

**Next after OAuth is working:**
- Trigger a sync from the dashboard UI and confirm videos load in the table
- Then move on to APScheduler background job (auto-refresh every X hours)

### 2026-02-27 — Frontend Fully Working + Bug Fixes

**Status:** End-to-end login → dashboard flow confirmed working on Windows PC.

**Bugs fixed:**
- `backend/app/main.py` — CORS middleware had `allow_credentials=not settings.debug` (backwards — blocked cookies in dev). Fixed to always allow credentials. Also changed `allow_origins` from `["*"]` to `["http://localhost:3000"]` in dev — wildcard can't be used with credentials.
- `docker-compose.yml` — Docker DB port changed from 5433 to **5434** to avoid conflict with a local PostgreSQL installation running on 5433 on the Windows machine.
- `.env.example` — updated DB port to 5434 with explanatory comment.
- `frontend/pages/dashboard.vue` — video table page size reduced from 25 to 10. Profile picture added to nav bar (data was already flowing from Google, just never rendered).

**Windows dev environment notes:**
- Local PostgreSQL is installed and runs on port 5433 — Docker must use a different port (5434)
- npm packages must be installed first: `cd frontend && npm install` then `npm run dev`
- PowerShell doesn't support `&&` — run commands separately or use `;`
- `.env` file must be created manually (gitignored) — copy from `.env.example` and fill in secrets

**How to resume (Windows):**
1. Docker Desktop running → `docker compose up -d db redis` (DB on port 5434)
2. Terminal 1: `cd backend` then `uv run uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload --reload-dir app`
3. Terminal 2: `cd frontend` then `npm run dev`
4. Open `http://localhost:3000`

**Next:** Phase 2 (YouTube Analytics API, view velocity, Best vs Worst Autopsy)

### 2026-02-27 (Part 2) — Phase 2 Analytics + Scheduler + UI Polish

**Completed:**
- `backend/app/services/youtube.py` — added YouTube Analytics API client (`get_channel_analytics`), YouTube Reporting API client (`ensure_reach_job`, `download_reach_reports`). Analytics returns per-video views/avg_duration/estimated_minutes. Reporting API downloads daily CSV files for impressions + CTR.
- `backend/app/services/sync.py` — added `_sync_analytics()` with two independent steps: step A = Analytics API (watch time metrics), step B = Reporting API (impressions/CTR from CSVs). Each step has its own try/except so one failure doesn't kill the other.
- `backend/app/api/v1/videos.py` — added `VideoAnalytics` to the list query via outer join, added `views_per_day` calculated field (view_count ÷ days since publish), now returns `click_through_rate`, `impressions`, `average_view_duration_seconds`, `average_view_percentage` per video.
- `backend/app/jobs/scheduler.py` — new file. APScheduler running inside FastAPI process, syncs all users every 6 hours automatically. Each user gets their own DB session.
- `backend/app/main.py` — wired scheduler start/stop into FastAPI lifespan hook.
- `frontend/pages/dashboard.vue` — added analytics sub-row under each video (views per day, avg watch time, CTR, impressions). Used `<template v-for>` to render two rows per video. Added `formatDuration` (seconds → m:ss) and `formatCtr` helpers. Card backgrounds changed to `bg-white/5 ring-1 ring-white/10` (glass effect).
- `frontend/assets/css/main.css` — set `viewpilot_background.png` as the body background (`background-size: 100% 100%`, fixed attachment).
- `frontend/public/viewpilot_background.png` — background image added to static assets.

**Analytics data status:**
- `average_view_duration_seconds` — ✅ live, showing real values (e.g. 4:34) on dashboard
- `views_per_day` — ✅ live, calculated on the fly from view_count + published_at
- `impressions` + `click_through_rate` — ⏳ pending, Reporting API job just created, Google takes 24-48h to generate first CSVs. Will populate on next sync after that.

**⚠️ Known issue — dashboard background not showing:**
- Background image shows correctly on the login page but appears dark/wrong on the dashboard
- The image (`viewpilot_background.png`) is a dark navy image with YouTube icons around the edges — the center is nearly black, so on a full-page layout the content covers the interesting parts
- Currently trying: `bg-white/5` glass cards, `background-size: 100% 100%` to stretch the image edge-to-edge
- **Next thing to fix:** get the background image fully visible on the dashboard like it is on the login page

**How to resume (Windows):**
1. Docker Desktop running → `docker compose up -d db redis`
2. Terminal 1: `cd backend` then `uv run uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload --reload-dir app`
3. Terminal 2: `cd frontend` then `npm run dev` (full restart needed after CSS changes)
4. Open `http://localhost:3000`

**Next:** Fix dashboard background → Best vs Worst Autopsy → Video detail page

### 2026-02-27 (Part 3) — Video Detail Page + Stats History

**Completed:**
- `frontend/pages/video/[id].vue` — full video detail page built: YouTube embed, stat pills (views, views/day, likes, comments), analytics section (CTR, avg watch time, impressions, avg view %), expandable description, metadata sidebar, tags, stats history table
- Stats history now fetches real daily data from YouTube Analytics API via `GET /videos/{id}/history`
- `backend/app/services/youtube.py` — fixed history fetch to use 180-day date range chunks instead of paginating with `startIndex` (which was capped at 200 rows and not reliably paginatable in Analytics API v2). Now covers the full video lifetime however long it is
- Stats history shows cumulative totals (total views/likes/comments at each date, not daily increments)
- Stats history always shows today's live stats pinned at the top row (uses video's real-time counts from main fetch, bypasses Analytics API's 2-3 day lag), then 8 evenly-spaced historical points below, with release day always at the bottom
- Fixed date timezone bug — was using `toISOString()` (UTC) for "today" which showed the wrong date for EST users after 7pm. Fixed to use local date components
- `backend/app/api/v1/videos.py` — added `/videos/{video_id}/history` endpoint
- Est. minutes watched now shows full number with commas (e.g. `102,347`) instead of K abbreviation

**How to resume (Windows):**
1. Docker Desktop running → `docker compose up -d db redis`
2. Terminal 1: `cd backend` then `uv run uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload --reload-dir app`
3. Terminal 2: `cd frontend` then `npm run dev`
4. Open `http://localhost:3000`

**Next:** Best vs Worst Autopsy → then Phase 3 ML pipeline

### 2026-02-27 (Part 4) — Autopsy Page Built

**Completed:**
- `backend/app/api/v1/autopsy.py` — new endpoint. Takes the N most recent videos (default 50), splits them into top 33% and bottom 33% by total views. Calculates per-group averages for CTR, avg watch time, views/day, revenue, RPM. Also detects title patterns (question marks, numbers, colons, all-caps words) and groups duration into buckets (under 5 min, 5–15, 15–30, 30+). Returns both groups as structured JSON.
- `frontend/pages/autopsy.vue` — full autopsy page. Two side-by-side performer cards (Top vs Bottom), each showing: total views, avg CTR, avg watch time, avg revenue, avg RPM, top title patterns, duration bucket breakdown. Compare button triggers a fresh API call. Window size selector (20/50/100 videos). Navigation link added to dashboard.

**Key files created/modified:**
- `backend/app/api/v1/autopsy.py` — new route, registered in main.py
- `frontend/pages/autopsy.vue` — new page

**How to resume (Windows):**
1. Docker Desktop running → `docker compose up -d db redis`
2. Terminal 1: `cd backend` then `uv run uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload --reload-dir app`
3. Terminal 2: `cd frontend` then `npm run dev`
4. Open `http://localhost:3000`

**Next:** Revenue + RPM → Dashboard overhaul

### 2026-02-28 — Revenue, RPM, Autopsy Improvements + Dashboard Overhaul

**Completed:**
- `backend/app/services/youtube.py` — added `estimated_revenue` and `rpm` fields to Analytics API pull. Both stored in `video_analytics` table on each sync.
- `backend/app/api/v1/videos.py` — revenue and RPM exposed in video list response and video detail response. Sort by revenue and RPM added to the video table.
- `backend/app/api/v1/autopsy.py` — added 30-day rolling views per video (separate Analytics API call for recent window). Smarter title pattern detection. Duration buckets refined. Performer totals footer added. Ranking changed from views/day to total views.
- `frontend/pages/autopsy.vue` — revenue + RPM shown in performer cards. Total views moved to rightmost column. Large revenue numbers rounded. Totals footer cleaned up. Title pattern chips improved.
- `frontend/pages/dashboard.vue` — full hero card overhaul: channel avatar + name + action buttons in top section, stats (subscribers/views/videos/last synced) in a dark footer strip below. Sticky nav with blur. Video table headers now highlight active sort column. Revenue and RPM columns added to table. Analytics sub-row chips unchanged. Rounded corners bumped to `rounded-2xl` throughout.

**What's still missing on dashboard (planned):**
- Charts / sparklines for view trends
- Date range filter on the video table
- Shorts filter toggle (data is there, `is_short` field exists, just no UI)
- Avg view % chip missing from analytics sub-row

**How to resume (Windows):**
1. Docker Desktop running → `docker compose up -d db redis`
2. Terminal 1: `cd backend` then `uv run uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload --reload-dir app`
3. Terminal 2: `cd frontend` then `npm run dev`
4. Open `http://localhost:3000`

**Next:** Dashboard remaining items (sparklines, filters) → Phase 3 ML pipeline (embeddings + clustering)

### 2026-02-28 (Part 2) — Performance Over Time Chart Polish + Title DNA Word Scaling

**Completed:**
- `frontend/pages/autopsy.vue` — extensive visual improvements to the Performance Over Time chart and Title DNA section:

**Performance Over Time chart:**
- Color gradient upgraded from 2-stop (green→red) to 5-stop smooth ramp: green → teal → blue → purple → red. No more flat zones or hard color jumps.
- Bar layout: removed `justify-between`, switched to `flex-1 min-w-0` columns with `gap-1` so bars fill the full width and shrink proportionally — no overflow.
- Block shape: fixed `h-[15px]` height (no more `aspect-video` which caused overflow), `rounded` corners for a brick-like look.
- Block depth: `inset 0 1px 0 rgba(255,255,255,0.22)` top highlight + `inset 0 0 0 2px rgba(0,0,0,0.55)` dark border on every block.
- X-axis labels: two-row layout — period label (Q1/Q2/month) in a fixed-height row on top, then a separate year-groups row below. Year groups use `flex: N` so each year label is truly centered over its full span of quarters, not pinned to a single column. Bracket lines (`border-t border-l border-r`) visually group quarters under their year.
- Legend: widened from `w-24` to `w-44`, updated gradient to match the 5-stop chart colors including a pink stop.

**Title DNA word clouds:**
- Words in top/bottom title chips now scale in font size based on frequency. Formula: `0.75rem + (count / maxCount) * 0.75rem` → range 0.75rem to 1.5rem. The most-used word is always the largest, all others scale proportionally down.
- Count badge uses `0.65em` (relative to chip font size) so it scales naturally with each chip.

**How to resume (Windows):**
1. Docker Desktop running → `docker compose up -d db redis`
2. Terminal 1: `cd backend` then `uv run uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload --reload-dir app`
3. Terminal 2: `cd frontend` then `npm run dev`
4. Open `http://localhost:3000`

**Next:** Dashboard remaining items (sparklines, filters, Shorts toggle) → Phase 3 ML pipeline
**Next:** Dashboard remaining items (sparklines, filters) → Phase 3 ML pipeline

### 2026-03-01 — Revenue Toggle, Search/Filter, Visual Polish

**Completed:**
- Opacity overhaul across all three pages (dashboard, video detail, autopsy) — cards changed from translucent `bg-white/10`/`bg-white/20` to solid dark `bg-slate-900/80`/`bg-slate-900/85` for readability and performance
- `frontend/composables/useRevenue.ts` — new shared composable. `showRevenue` state lives here (defaults false), `toggleRevenue` writes to localStorage on every toggle so state persists across refreshes
- `frontend/plugins/revenue.client.ts` — runs once on page boot, reads localStorage to restore the last revenue toggle state
- Revenue toggle integrated on all three pages (dashboard, video detail, autopsy) — red slider in the top nav. Hides direct revenue dollar amounts; RPM stays visible. `v-if="showRevenue"` gates all revenue cells/cards. Autopsy filters hero metrics + table rows + footer spans
- Nav polish — revenue label bumped to `text-sm text-gray-300`, username to `font-medium text-white`, logout changed from plain text link to a pill button with border/bg
- Dashboard search + filter — loads all videos at once (`per_page=500`) into `allVideos` ref, all filtering/sorting is client-side (instant, no API calls on keypress)
  - Title search: case-insensitive substring match
  - From/To date dropdowns: dynamically populated from real video publish dates, ascending order (oldest→newest), mutually constrained (`fromOptions` filters to ≤ dateTo, `toOptions` filters to ≥ dateFrom)
  - Search input and date dropdowns combined into a single row to save vertical space
  - Active filter count + "Clear" button
  - Empty state when no results match
- `backend/app/api/v1/videos.py` — raised `per_page` cap from `le=200` to `le=500` (required for loading full library)
- Avg watch time chip in dashboard sub-row now shows `4:34 / 12:30` format — watch time alongside full video duration for easy comparison without doing math

**Key files modified:**
- `frontend/composables/useRevenue.ts` — new
- `frontend/plugins/revenue.client.ts` — new
- `frontend/pages/dashboard.vue` — search/filter, revenue toggle, nav polish, avg watch format
- `frontend/pages/video/[id].vue` — revenue toggle in nav
- `frontend/pages/autopsy.vue` — revenue toggle in nav, visibleHeroMetrics computed
- `backend/app/api/v1/videos.py` — per_page cap raised to 500

**How to resume (Windows):**
1. Docker Desktop running → `docker compose up -d db redis`
2. Terminal 1: `cd backend` then `uv run uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload --reload-dir app`
3. Terminal 2: `cd frontend` then `npm run dev`
4. Open `http://localhost:3000`

<<<<<<< HEAD
### 2026-03-11 — Charts Page: Full Build + Bug Fixes + Polish

**Completed:**
- `backend/app/models/stats.py` — added `ChannelDailyStats` model (one row per channel per calendar day: views, watch time, avg view duration, likes, comments, subscribers gained/lost, impressions, CTR, revenue)
- `backend/alembic/versions/e7a1c3d4f2b8_add_channel_daily_stats.py` — migration for new table, ran successfully
- `backend/app/services/youtube.py` — added `get_channel_daily_stats()` (fetches real daily channel metrics via Analytics API `dimensions="day"`, in 180-day chunks, tries full reach metrics then falls back to core if rejected) and `get_channel_daily_revenue()` (separate revenue fetch, returns {} gracefully if scope not granted)
- `backend/app/services/sync.py` — added `_sync_channel_history()`: first run fetches full history from channel launch date (capped at 2015-01-01); subsequent runs refresh only the last 60 days (YouTube revises recent data). Upserts via `pg_insert(...).on_conflict_do_update(...)` on `uq_channel_daily_stats_channel_date` constraint. Normalizes CTR from percentage to 0–1 fraction on write if needed.
- `backend/app/api/v1/charts.py` — new endpoint `GET /charts/channel?channel_id=&granularity=`. Queries `channel_daily_stats` grouped by day/week/month. Returns dates array + metrics dict (views, watch_time_minutes, impressions, ctr, likes, comments, subscribers_gained, revenue, rpm, avg_view_duration). Cached 30 min in Redis.
- `backend/app/api/v1/__init__.py` — registered charts router
- `backend/app/api/v1/channels.py` — added charts cache busting on sync (all granularities)
- `frontend/plugins/apexcharts.client.ts` — registers vue3-apexcharts globally (client-only)
- `frontend/pages/charts.vue` — full Social Blade-style charts page. ApexCharts with brush scrubber, 10 metric pills (Views/Watch Time/Impressions/CTR/Likes/Comments/Subscribers/Revenue/RPM/Avg Watch Time), Daily/Weekly/Monthly granularity, Area/Line toggle, Normalize mode, 7D/30D/90D/6M/1Y/All quick range buttons, summary cards, revenue toggle gating.
- Charts nav links added to dashboard, autopsy, and video detail pages

**Critical bug fixed:**
- Root cause of blank chart: `brush.selection.xaxis` was `{}` on first render (because `visibleMin/Max` refs were undefined). ApexCharts interprets an empty brush selection as "show nothing" in the linked main chart. Fixed by computing a default selection from the actual data (last 90 days) inside `brushChartOptions` whenever `visibleMin/Max` are not yet set.

**Architecture of charts page:**
- `visibleMin/Max` refs track the currently visible date window
- `brushChartOptions.chart.events.selection` fires on brush drag → updates `visibleMin/Max` → `metricTotals` recomputes (filters to visible indices) → summary cards update
- `mainChartOptions.xaxis.min/max` bound to `visibleMin/Max` → main chart zooms reactively
- `applyQuickRange(days)` sets `visibleMin/Max` for button clicks; both paths flow through same refs

**Key files created/modified:**
- `backend/app/models/stats.py` — ChannelDailyStats added
- `backend/alembic/versions/e7a1c3d4f2b8_add_channel_daily_stats.py` — new
- `backend/app/services/youtube.py` — daily stats + revenue fetch added
- `backend/app/services/sync.py` — `_sync_channel_history()` added
- `backend/app/api/v1/charts.py` — new
- `frontend/plugins/apexcharts.client.ts` — new
- `frontend/pages/charts.vue` — new

**Charts page improvements (same session):**
- `contentRange` computed: finds first/last day with non-zero views, used to clip the scrubber X-axis so dead zones before/after content are hidden
- Y-axis: `fmtAxis(v, key)` helper formats all tick labels as "1.2M", "340K", "$4", "3.5%", "4:30" etc. — no trailing ".0", no raw integers. Added `tickAmount: 6, forceNiceScale: true` to prevent tick clutter
- Custom date range picker: "Custom range" button opens inline date-from/to inputs; applies to both the main chart zoom and the summary cards
- Video upload annotations: fetches video list (title + published_at) in parallel with chart data; renders subtle vertical lines at each upload date in the chart; tooltip shows video titles when hovering a day a video was published
- Custom tooltip: replaced ApexCharts' built-in shared tooltip with a fully custom one — shows formatted metric values for each selected series + "Uploaded" section with video titles for that date
- Scrubber visual differentiation: `bg-black/30`, `border-dashed border-slate-800`, left accent stripe `border-l-2 border-l-indigo-500/20` — clearly distinct from the main chart card above
- `visibleRangeLabel` shows the human-readable selected window ("Mar 1, 2024 → Mar 11, 2025") in the scrubber header
=======
### 2026-03-08 — Dashboard Loading Skeletons

**Completed:**
- `frontend/assets/css/main.css` — added `.skeleton` class + `@keyframes skeleton-shimmer`. Uses `transform: translateX()` on a `::after` pseudo-element (GPU composited, zero repaints) rather than `background-position` animation. Industry-standard approach.
- `frontend/pages/dashboard.vue` — replaced the plain "Loading channel…" text with two proper loading skeletons:
  - **Channel hero skeleton** — shows while the channel API call is in flight. Same gradient + purple/indigo glow blobs as the real card. Shimmer bars in exact positions of: avatar circle, channel name, "last synced" line, two action buttons (Autopsy + Sync), and all three stat mini-cards. Stat card shimmer delays stagger slightly so they cascade.
  - **Video table skeleton** — shows after channel loads, while the 500-video fetch completes. Includes: skeleton search bar + two filter dropdowns, the indigo/purple "Videos" accent bar, dimmed-real column header labels (Video / Date / Views / RPM / Likes / Comments), then 8 full skeleton rows each with: thumbnail block → varying-width title bars → stat cell placeholders → thin performance bar → 4 analytics chip blocks. Each row's shimmer is offset by 60ms so the sweep cascades down the table.
  - Loading states are **computed** (`isChannelLoading`, `isVideosLoading`) so clicking Sync never re-triggers skeletons — only the initial page load does.
  - Added `videosLoaded` ref that gets set in `loadVideos` finally block to gate the table skeleton correctly.
  - Added `skeletonTitleWidths` array with 8 varying pixel widths so title bars don't look like a uniform grid.

**Shorts toggle note:** intentionally removed from the roadmap — not a priority while building out core analytics features.

**How to resume (Windows):**
1. Docker Desktop running → `docker compose up -d db redis`
2. Terminal 1: `cd backend` then `uv run uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload --reload-dir app`
3. Terminal 2: `cd frontend` then `npm run dev`
4. Open `http://localhost:3000`
>>>>>>> 0ce2269460e086431132d2af1bb991755ab0cd79

---

## Future Ideas (not started)

### Views Chart on Video Detail Page
On the video detail page (`/video/[id]`), add an interactive chart of daily views over the video's lifetime. The key feature is a **time range scrubber at the bottom** — like a mini timeline you can drag the handles on to zoom into any window: first week, last 3 months, since the beginning, etc. The chart data already exists (the `/history` endpoint returns full daily data). Just need to pick a charting library (Chart.js or uPlot) and build the scrubber UI.

### Advanced Filter Panel on Dashboard
Add a secondary filter panel (separate from or extending the current search row) that lets you filter videos by any stat not already covered by sorting. Things like: dislike ratio, impressions, CTR, avg view duration, views per day — basically anything in the analytics sub-row. These would be range sliders (e.g. "CTR between 3% and 8%") rather than dropdowns. The data is already in `allVideos` client-side so no backend work needed — pure frontend filtering logic.

---

### Next Session — Nuxt 3 Frontend (archived plan)

**Goal:** Build the frontend so you can actually log in and see channel data in a browser.

**Scope for first version:**
- Login page with "Sign in with Google" button
- Dashboard with channel stats header (subscribers, views, video count, last synced)
- Sync button to trigger a fresh YouTube pull
- Logout button
- Functional Tailwind styling (no design polish yet)

**Auth flow:**
1. Login button → `window.location.href = 'http://localhost:8000/api/v1/auth/google'`
2. Backend handles OAuth, sets session cookie, redirects back to `http://localhost:3000`
3. Root page checks if logged in → redirects to `/dashboard`
4. Dashboard fetches `/api/v1/channels` for stats

**Files to create (all new, inside `frontend/`):**
```
frontend/
  package.json           → nuxt 3 + @nuxtjs/tailwindcss
  nuxt.config.ts         → tailwind module, runtimeConfig.public.apiBase = 'http://localhost:8000'
  tsconfig.json
  app.vue                → <NuxtPage />
  pages/
    index.vue            → login page, auto-redirects to /dashboard if already logged in
    dashboard.vue        → channel stats + sync button + logout
  composables/
    useApi.ts            → $fetch wrapper with credentials: 'include'
    useAuth.ts           → useState for user, fetchMe(), logout()
  middleware/
    auth.ts              → redirect to / if not logged in
  tailwind.config.ts
  .gitignore
```

**Node.js required** — install if not already: `brew install node` or download from nodejs.org
**Start frontend dev server:** `cd frontend && npm install && npm run dev` → runs on port 3000
