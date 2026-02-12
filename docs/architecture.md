# ViewPilot — YouTube Creator Intelligence Platform

## Context
Build a portfolio-differentiating YouTube analytics platform that uses the YouTube Data API v3 + Analytics API to analyze channel performance, detect patterns in top vs bottom performers, and provide AI-powered title optimization. Must be cheap to run (<$10/mo), use non-React/Next stacks, and demonstrate breadth across many technologies.

---

## Phase 1: Foundation (MVP Core)
> Goal: Auth, data ingestion, basic dashboard. A working app end-to-end.

1. **Project scaffolding** — repo structure, Docker Compose, linting, CI skeleton
2. **Google OAuth + YouTube channel connect** — login flow, token storage, channel selection
3. **Video data import pipeline** — fetch channel info, video list, metadata, public stats via Data API v3
4. **Database schema + models** — all core tables
5. **Basic REST + GraphQL API** — videos list, channel stats, filters
6. **Nuxt frontend** — auth flow, basic dashboard with video table, sorting, filtering
7. **Scheduled refresh** — background job to re-fetch stats periodically

## Phase 2: Analytics & Insights
> Goal: Deep analytics, the "autopsy" features, Analytics API integration.

1. **YouTube Analytics API integration** — CTR, avg view duration, traffic sources, audience retention
2. **View velocity calculations** — views/day since publish, first 24h/7d performance
3. **Best vs Worst Autopsy** — top 10% vs bottom 10% pattern detection (title words, length, publish time, tags)
4. **Dashboard enhancements** — date range filters, performance charts, sparklines
5. **Video detail view** — full stats breakdown per video

## Phase 3: AI & Clustering
> Goal: Embeddings, clustering, Title Lab, Top 10 vs Bottom 10 analysis.

1. **Embedding pipeline** — compute title/description embeddings with sentence-transformers, store in DB
2. **Clustering** — k-means / HDBSCAN on embeddings, auto-label clusters
3. **Similarity scoring** — cosine similarity between videos, cluster performance ranking
4. **Title Lab** — input draft title → score against winning/losing clusters, suggest improvements
5. **Top 10 vs Bottom 10 Analysis** — full AI feature (clusters per list, pattern extraction, scoring)
6. **Simple prediction model** — logistic regression on features (title tokens, duration, publish time, tags)

## Phase 4: Reports, Alerts & Polish
> Goal: Automated insights, alerting, deployment, CI/CD.

1. **Weekly recap report** — web view summarizing channel performance
2. **Alerts system** — "new upload underperforming baseline after X hours"
3. **PDF export** (optional) — generate report PDFs
4. **Full CI/CD pipeline** — lint, test, build, deploy to production
5. **Production deployment** — deploy to hosting infrastructure
6. **Polish** — error handling, loading states, responsive design, onboarding flow

---

## System Architecture

```
┌─────────────────┐     ┌──────────────────────────────┐
│   Nuxt 3 SPA    │────▶│   FastAPI Backend             │
│ (Cloudflare     │     │   ├─ REST  (/api/v1/...)      │
│  Pages)         │     │   ├─ GraphQL (/graphql)       │
│                 │     │   ├─ Auth (Google OAuth)       │
│                 │     │   ├─ Background Jobs (APScheduler) │
│                 │     │   └─ ML Pipeline (sentence-transformers) │
└─────────────────┘     └──────────┬───────────────────┘
                                   │
                        ┌──────────▼───────────┐
                        │  PostgreSQL (Supabase)│
                        └──────────────────────┘
                        ┌──────────────────────┐
                        │  Redis (Upstash)     │
                        │  - API rate limiting  │
                        │  - Job queue/locks    │
                        │  - Session cache      │
                        └──────────────────────┘
```

**Services:**
- **FastAPI** — single service handling REST, GraphQL, auth, background jobs, ML inference
- **Nuxt 3** — SSR/SPA frontend, deployed as static to Cloudflare Pages
- **PostgreSQL** — Supabase free tier (500MB, unlimited API requests)
- **Redis** — Upstash free tier (10K commands/day) for rate limiting + job locking
- **APScheduler** — in-process scheduler for periodic data refreshes (no separate worker needed to stay cheap)

---

## Database Schema

### `users`
| Column | Type | Notes |
|--------|------|-------|
| id | UUID (PK) | |
| google_id | VARCHAR(255) UNIQUE | Google account ID |
| email | VARCHAR(255) | |
| name | VARCHAR(255) | |
| picture_url | TEXT | Profile picture |
| access_token | TEXT | Encrypted Google OAuth access token |
| refresh_token | TEXT | Encrypted Google OAuth refresh token |
| token_expires_at | TIMESTAMPTZ | |
| created_at | TIMESTAMPTZ | |
| updated_at | TIMESTAMPTZ | |

### `channels`
| Column | Type | Notes |
|--------|------|-------|
| id | UUID (PK) | |
| user_id | UUID (FK → users) | |
| youtube_channel_id | VARCHAR(255) UNIQUE | |
| title | VARCHAR(255) | |
| description | TEXT | |
| custom_url | VARCHAR(255) | |
| thumbnail_url | TEXT | |
| subscriber_count | BIGINT | |
| video_count | INTEGER | |
| view_count | BIGINT | |
| published_at | TIMESTAMPTZ | Channel creation date |
| last_synced_at | TIMESTAMPTZ | |
| created_at | TIMESTAMPTZ | |

### `videos`
| Column | Type | Notes |
|--------|------|-------|
| id | UUID (PK) | |
| channel_id | UUID (FK → channels) | |
| youtube_video_id | VARCHAR(255) UNIQUE | |
| title | TEXT | |
| description | TEXT | |
| tags | TEXT[] | Postgres array |
| category_id | VARCHAR(10) | YouTube category ID |
| duration_seconds | INTEGER | Parsed from ISO 8601 |
| published_at | TIMESTAMPTZ | |
| thumbnail_url | TEXT | |
| default_language | VARCHAR(10) | |
| is_short | BOOLEAN | Duration < 60s heuristic |
| playlist_ids | TEXT[] | Playlists this video belongs to |
| created_at | TIMESTAMPTZ | |
| updated_at | TIMESTAMPTZ | |

### `video_stats` (time-series snapshots)
| Column | Type | Notes |
|--------|------|-------|
| id | UUID (PK) | |
| video_id | UUID (FK → videos) | |
| view_count | BIGINT | |
| like_count | BIGINT | |
| comment_count | BIGINT | |
| fetched_at | TIMESTAMPTZ | When this snapshot was taken |

**Index:** `(video_id, fetched_at)` for time-series queries.

### `video_analytics` (from Analytics API)
| Column | Type | Notes |
|--------|------|-------|
| id | UUID (PK) | |
| video_id | UUID (FK → videos) | |
| date | DATE | Analytics date |
| views | INTEGER | |
| estimated_minutes_watched | FLOAT | |
| average_view_duration_seconds | FLOAT | |
| average_view_percentage | FLOAT | |
| click_through_rate | FLOAT | Impressions CTR |
| impressions | INTEGER | |
| likes | INTEGER | |
| comments | INTEGER | |
| shares | INTEGER | |
| subscribers_gained | INTEGER | |
| subscribers_lost | INTEGER | |
| traffic_source | JSONB | Breakdown by source |
| fetched_at | TIMESTAMPTZ | |

**Index:** `(video_id, date)` unique.

### `video_embeddings`
| Column | Type | Notes |
|--------|------|-------|
| id | UUID (PK) | |
| video_id | UUID (FK → videos) UNIQUE | |
| model_name | VARCHAR(100) | e.g. "all-MiniLM-L6-v2" |
| title_embedding | VECTOR(384) | pgvector extension |
| description_embedding | VECTOR(384) | |
| combined_embedding | VECTOR(384) | Weighted avg of title + desc |
| created_at | TIMESTAMPTZ | |

**Requires:** `pgvector` extension on Supabase (available on free tier).

### `clusters`
| Column | Type | Notes |
|--------|------|-------|
| id | UUID (PK) | |
| channel_id | UUID (FK → channels) | |
| name | VARCHAR(255) | Auto-generated label |
| description | TEXT | AI-generated summary |
| algorithm | VARCHAR(50) | "kmeans" / "hdbscan" |
| n_videos | INTEGER | |
| avg_views | FLOAT | |
| avg_ctr | FLOAT | |
| centroid | VECTOR(384) | Cluster center |
| created_at | TIMESTAMPTZ | |

### `cluster_memberships`
| Column | Type | Notes |
|--------|------|-------|
| cluster_id | UUID (FK → clusters) | |
| video_id | UUID (FK → videos) | |
| distance_to_centroid | FLOAT | |
| **PK** | (cluster_id, video_id) | |

### `predictions`
| Column | Type | Notes |
|--------|------|-------|
| id | UUID (PK) | |
| channel_id | UUID (FK → channels) | |
| input_title | TEXT | |
| input_metadata | JSONB | Optional: duration, tags, etc. |
| predicted_performance | VARCHAR(20) | "top", "above_avg", "below_avg", "bottom" |
| confidence | FLOAT | |
| top_likeness_score | FLOAT | |
| similar_top_clusters | JSONB | Cluster IDs + similarity scores |
| similar_bottom_clusters | JSONB | |
| reasoning | TEXT[] | Array of explanation strings |
| created_at | TIMESTAMPTZ | |

### `alerts`
| Column | Type | Notes |
|--------|------|-------|
| id | UUID (PK) | |
| channel_id | UUID (FK → channels) | |
| video_id | UUID (FK → videos) NULL | |
| alert_type | VARCHAR(50) | "underperforming", "trending", "weekly_recap" |
| message | TEXT | |
| is_read | BOOLEAN DEFAULT false | |
| created_at | TIMESTAMPTZ | |

---

## YouTube API Integration

### APIs & Endpoints Used

**YouTube Data API v3:**
| Endpoint | Purpose | Quota Cost |
|----------|---------|------------|
| `channels.list` (part=snippet,statistics,contentDetails) | Get channel info + stats | 1 unit/call |
| `playlistItems.list` (part=snippet) on uploads playlist | List all videos | 1 unit/page |
| `videos.list` (part=snippet,statistics,contentDetails) | Video metadata + stats (batch 50) | 1 unit/call |
| `videoCategories.list` | Category name mapping | 1 unit |
| `playlists.list` | User's playlists | 1 unit/page |

**YouTube Analytics API:**
| Endpoint | Purpose |
|----------|---------|
| `reports.query` dimensions=video, metrics=views,estimatedMinutesWatched,averageViewDuration,averageViewPercentage,annotationClickThroughRate,impressions,impressionClickThroughRate,likes,comments,shares,subscribersGained,subscribersLost | Per-video analytics |
| `reports.query` dimensions=day, filters=video==VIDEO_ID | Daily time-series for a video |
| `reports.query` dimensions=insightTrafficSourceType, filters=video==VIDEO_ID | Traffic sources per video |

### OAuth Scopes
```
https://www.googleapis.com/auth/youtube.readonly
https://www.googleapis.com/auth/yt-analytics.readonly
https://www.googleapis.com/auth/userinfo.email
https://www.googleapis.com/auth/userinfo.profile
```

### Rate Limit Strategy
- YouTube Data API: 10,000 units/day quota
- Batch video.list calls (50 IDs per request = 1 unit for 50 videos)
- Store last_synced_at per channel; only re-fetch if >1 hour old for stats, >24h for metadata
- Use Redis to track daily quota usage; block requests if approaching limit
- Analytics API: 200 requests/day per project — batch date ranges, cache aggressively
- Incremental sync: on refresh, only fetch stats for last 30 days from Analytics API unless full resync requested

---

## Key API Endpoints

### REST (`/api/v1/`)

**Auth:**
- `GET /api/v1/auth/google` → redirect to Google OAuth
- `GET /api/v1/auth/google/callback` → handle OAuth callback, set session
- `GET /api/v1/auth/me` → current user info
- `POST /api/v1/auth/logout` → clear session

**Channels:**
- `GET /api/v1/channels` → list user's connected channels
- `POST /api/v1/channels/sync` → trigger full channel data sync
- `GET /api/v1/channels/{id}/stats` → channel-level statistics

**Videos:**
- `GET /api/v1/videos?channel_id=&sort_by=&order=&date_from=&date_to=&min_views=&category=&page=&per_page=` → paginated video list with filters
- `GET /api/v1/videos/{id}` → single video detail with stats history
- `GET /api/v1/videos/{id}/analytics` → Analytics API data for a video
- `GET /api/v1/videos/{id}/velocity` → view velocity metrics (views/day, first 24h, first 7d)

**Insights:**
- `GET /api/v1/insights/autopsy?channel_id=` → top 10% vs bottom 10% analysis
- `POST /api/v1/insights/compare` → body: `{ top_titles: [...], bottom_titles: [...] }` → full Top 10 vs Bottom 10 analysis
- `GET /api/v1/insights/clusters?channel_id=` → cluster listing with performance stats
- `POST /api/v1/insights/title-lab` → body: `{ title: "...", channel_id: "..." }` → score + suggestions

**Predictions:**
- `POST /api/v1/predictions/score` → body: `{ title, duration, tags, category, publish_time }` → predicted performance
- `GET /api/v1/predictions/history?channel_id=` → past predictions

**Alerts & Reports:**
- `GET /api/v1/alerts?channel_id=&unread_only=` → list alerts
- `PATCH /api/v1/alerts/{id}/read` → mark alert as read
- `GET /api/v1/reports/weekly?channel_id=&week=` → weekly recap data

### GraphQL (`/graphql`)

Strawberry GraphQL schema mirroring the REST endpoints:

```graphql
type Query {
  me: User!
  channels: [Channel!]!
  channel(id: ID!): Channel!
  videos(channelId: ID!, filters: VideoFilters): VideoConnection!
  video(id: ID!): Video!
  videoAnalytics(videoId: ID!): VideoAnalytics
  videoVelocity(videoId: ID!): ViewVelocity!
  autopsy(channelId: ID!): AutopsyReport!
  clusters(channelId: ID!): [Cluster!]!
  alerts(channelId: ID!, unreadOnly: Boolean): [Alert!]!
  weeklyReport(channelId: ID!, week: String): WeeklyReport!
  predictionHistory(channelId: ID!): [Prediction!]!
}

type Mutation {
  syncChannel(channelId: ID!): SyncResult!
  scoreTitleLab(input: TitleLabInput!): TitleLabResult!
  compareTopBottom(input: CompareInput!): CompareReport!
  scoreTitle(input: PredictionInput!): Prediction!
  markAlertRead(alertId: ID!): Alert!
}
```

---

## AI / ML Pipeline

### Embedding Pipeline
1. **Model:** `all-MiniLM-L6-v2` via `sentence-transformers` (384-dim vectors, ~80MB model)
2. **When:** After video import/sync, compute embeddings for any video without one
3. **What:** Embed `title`, `description` (truncated to 256 tokens), and a `combined` = 0.7*title + 0.3*description weighted average
4. **Storage:** `video_embeddings` table using pgvector's `VECTOR(384)` type
5. **Similarity:** Cosine similarity via pgvector `<=>` operator for nearest-neighbor queries

### Clustering Pipeline
1. **Trigger:** On-demand when user views clusters or after a sync adds >5 new videos
2. **Algorithm:** K-means (sklearn) with k chosen by silhouette score (k=2..min(10, n_videos/5))
3. **Fallback:** HDBSCAN if k-means silhouette < 0.3
4. **Labels:** Extract top TF-IDF terms from titles in each cluster → auto-generate label
5. **Storage:** `clusters` + `cluster_memberships` tables; centroid stored as VECTOR(384)

### Title Lab Scoring
1. User inputs draft title → compute embedding
2. Compute cosine similarity to each cluster centroid
3. **Top-likeness score** = avg(similarity to top-performing clusters) - avg(similarity to bottom-performing clusters)
4. Return score, closest clusters, and reasoning bullets
5. Suggest improvements: find nearest top-cluster centroid → retrieve 3 nearest titles in that cluster → use as "inspiration" examples

### Top 10 vs Bottom 10 Analysis
1. Embed all 20 titles
2. Cluster each list separately (k=2..5, pick best silhouette)
3. NLP stats: word freq (unigrams/bigrams), title length, punctuation, numbers, question marks, brackets, caps ratio, emoji presence
4. Compute frequency differences between top and bottom lists
5. Generate structured output: clusters, pattern bullets, contrasts, per-title top-likeness score

### Prediction Model
1. **Features:** title embedding (384-dim), duration_seconds, publish_hour, publish_dow, n_tags, category_id (one-hot), title_length, has_number, has_question, has_brackets
2. **Target:** Binary (top 50% vs bottom 50% by view count, normalized by channel age)
3. **Model:** Gradient boosting (LightGBM or sklearn GradientBoostingClassifier)
4. **Training:** On each channel's data after sufficient videos (>50). Retrain on sync.
5. **Storage:** Pickle model stored on disk (per channel). Prediction results in `predictions` table.

---

## Repo Structure

```
ViewPilot/
├── .github/
│   └── workflows/
│       ├── ci.yml                # Lint + test on PR
│       └── deploy.yml            # Deploy on push to main
├── backend/
│   ├── Dockerfile
│   ├── pyproject.toml            # uv project config
│   ├── alembic.ini
│   ├── alembic/
│   │   └── versions/             # DB migrations
│   ├── app/
│   │   ├── __init__.py
│   │   ├── main.py               # FastAPI app factory
│   │   ├── config.py             # Settings via pydantic-settings
│   │   ├── database.py           # SQLAlchemy async engine + session
│   │   ├── models/               # SQLAlchemy ORM models
│   │   ├── schemas/              # Pydantic request/response schemas
│   │   ├── api/v1/               # REST route handlers
│   │   ├── graphql/              # Strawberry GraphQL schema
│   │   ├── services/             # Business logic layer
│   │   ├── jobs/                 # APScheduler background tasks
│   │   └── utils/                # Helpers (security, YouTube parsing)
│   └── tests/
├── frontend/                     # Nuxt 3 (not started yet)
├── docs/                         # Architecture docs (this file)
├── docker-compose.yml
├── .gitignore
├── .env.example
└── CLAUDE.md
```

---

## Docker Compose (Local Dev)

```yaml
services:
  api:
    build: ./backend
    ports:
      - "8000:8000"
    volumes:
      - ./backend/app:/app/app
    env_file: .env
    depends_on:
      - db
      - redis
    command: uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

  frontend:
    build: ./frontend
    ports:
      - "3000:3000"
    volumes:
      - ./frontend:/app
      - /app/node_modules
    env_file: .env
    command: npm run dev -- --host 0.0.0.0

  db:
    image: pgvector/pgvector:pg16
    ports:
      - "5432:5432"
    environment:
      POSTGRES_DB: viewpilot
      POSTGRES_USER: viewpilot
      POSTGRES_PASSWORD: viewpilot_dev
    volumes:
      - pgdata:/var/lib/postgresql/data

  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"

volumes:
  pgdata:
```

---

## CI/CD Pipeline

### `.github/workflows/ci.yml` (on PR)
```
Jobs:
1. backend-lint:  ruff check + ruff format --check
2. backend-test:  pytest with postgres service container
3. frontend-lint: eslint + prettier --check
4. frontend-build: nuxt build (type-check + build verification)
```

### `.github/workflows/deploy.yml` (on push to main)
```
Jobs:
1. backend-deploy:
   - Build Docker image
   - Push to container registry
   - Deploy to hosting platform (Railway / Fly.io)
2. frontend-deploy:
   - nuxt generate (static output)
   - Deploy to Cloudflare Pages
```

---

## Hosting Plan (<$10/mo)

| Service | Provider | Tier | Est. Cost |
|---------|----------|------|-----------|
| **Backend API** | Railway | Hobby plan (512MB, shared CPU) | $5/mo |
| **Frontend** | Cloudflare Pages | Free | $0 |
| **PostgreSQL** | Supabase | Free (500MB, unlimited requests) | $0 |
| **Redis** | Upstash | Free (10K commands/day) | $0 |
| **Domain** (optional) | Cloudflare | Already owned or ~$10/yr | ~$1/mo |
| **YouTube APIs** | Google Cloud | Free tier (10K units/day) | $0 |
| **Total** | | | **~$5-6/mo** |
