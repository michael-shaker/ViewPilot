<script setup lang="ts">
definePageMeta({ middleware: 'auth' })

const route = useRoute()
const api = useApi()

interface StatsSnapshot {
  view_count: number
  like_count: number
  comment_count: number
  fetched_at: string
}

interface Video {
  id: string
  youtube_video_id: string
  title: string
  description: string | null
  published_at: string
  duration_seconds: number | null
  is_short: boolean
  thumbnail_url: string | null
  tags: string[]
  category_id: string | null
  default_language: string | null
  view_count: number
  like_count: number
  comment_count: number
  views_per_day: number | null
  engagement_rate: number | null
  click_through_rate: number | null
  impressions: number | null
  average_view_duration_seconds: number | null
  average_view_percentage: number | null
  estimated_minutes_watched: number | null
  estimated_revenue: number | null
  estimated_ad_revenue: number | null
  rpm: number | null
  cpm: number | null
  stats_history: StatsSnapshot[]
}

const CATEGORIES: Record<string, string> = {
  '1': 'Film & Animation', '2': 'Autos & Vehicles', '10': 'Music',
  '15': 'Pets & Animals', '17': 'Sports', '19': 'Travel & Events',
  '20': 'Gaming', '22': 'People & Blogs', '23': 'Comedy',
  '24': 'Entertainment', '25': 'News & Politics', '26': 'Howto & Style',
  '27': 'Education', '28': 'Science & Technology', '29': 'Nonprofits & Activism',
}

interface DailyRow {
  day: string       // "YYYY-MM-DD"
  views: number
  likes: number
  comments: number
}

interface Comment {
  id: string
  youtube_comment_id: string
  parent_youtube_id: string | null
  author_name: string
  author_image_url: string | null
  author_channel_url: string | null
  text: string
  like_count: number
  reply_count: number
  is_reply: boolean
  published_at: string | null
  replies: Comment[]
}

const { showRevenue, toggleRevenue } = useRevenue()

const video = ref<Video | null>(null)
const loadError = ref<string | null>(null)
const descExpanded = ref(false)
const dailyHistory = ref<DailyRow[]>([])
const historyLoading = ref(true)
const dislikeCount = ref<number | null>(null)  // null = still loading
const comments = ref<Comment[]>([])
const commentsLoading = ref(true)

// tracks which avatar images failed to load so we can show the letter fallback instead
// reactive(Set) lets us call .add() without replacing the whole object every time
const failedAvatars = reactive(new Set<string>())
const onAvatarError = (id: string) => { failedAvatars.add(id) }

onMounted(async () => {
  try {
    video.value = await api<Video>(`/api/v1/videos/${route.params.id}`)
  } catch {
    loadError.value = 'could not load video'
    return
  }

  // all three secondary fetches run in parallel after the video loads
  Promise.all([
    // dislike count via backend — cached in redis for 24h so it's fast after first load
    api<Record<string, number | null>>(`/api/v1/videos/dislikes?ids=${video.value.youtube_video_id}`)
      .then(res => { dislikeCount.value = res[video.value!.youtube_video_id] ?? -1 })
      .catch(() => { dislikeCount.value = -1 }),

    // daily analytics history
    api<{ daily: { day: string, views: number, likes: number, comments: number }[] }>(
      `/api/v1/videos/${route.params.id}/history`
    ).then(res => { dailyHistory.value = res.daily })
      .catch(() => {})
      .finally(() => { historyLoading.value = false }),

    // top comments with replies
    api<{ comments: Comment[] }>(`/api/v1/videos/${route.params.id}/comments`)
      .then(res => { comments.value = res.comments })
      .catch(() => {})
      .finally(() => { commentsLoading.value = false }),
  ])
})

// e.g. "3 days ago", "2 months ago"
const timeAgo = (iso: string | null): string => {
  if (!iso) return ''
  const diff = Date.now() - new Date(iso).getTime()
  const mins  = Math.floor(diff / 60000)
  const hours = Math.floor(diff / 3600000)
  const days  = Math.floor(diff / 86400000)
  const months = Math.floor(days / 30)
  const years  = Math.floor(days / 365)
  if (years  > 0) return `${years} year${years  > 1 ? 's' : ''} ago`
  if (months > 0) return `${months} month${months > 1 ? 's' : ''} ago`
  if (days   > 0) return `${days} day${days   > 1 ? 's' : ''} ago`
  if (hours  > 0) return `${hours} hour${hours  > 1 ? 's' : ''} ago`
  return `${mins} minute${mins > 1 ? 's' : ''} ago`
}

const formatNum = (n: number | null) => {
  if (n == null) return '—'
  if (n >= 1_000_000) return (n / 1_000_000).toFixed(1) + 'M'
  if (n >= 1_000) return (n / 1_000).toFixed(1) + 'K'
  return n.toLocaleString()
}

const formatDate = (iso: string) => {
  const d = new Date(iso)
  const date = d.toLocaleDateString('en-US', { month: 'long', day: 'numeric', year: 'numeric' })
  const time = d.toLocaleTimeString('en-US', { hour: 'numeric', minute: '2-digit', hour12: true })
  return `${date} at ${time}`
}

const formatDateTime = (iso: string) =>
  new Date(iso).toLocaleString('en-GB', { day: 'numeric', month: 'short', year: 'numeric', hour: '2-digit', minute: '2-digit' })

const formatDuration = (secs: number | null) => {
  if (secs == null) return '—'
  const h = Math.floor(secs / 3600)
  const m = Math.floor((secs % 3600) / 60)
  const s = Math.floor(secs % 60)
  if (h > 0) return `${h}:${String(m).padStart(2, '0')}:${String(s).padStart(2, '0')}`
  return `${m}:${String(s).padStart(2, '0')}`
}

const formatCtr = (ctr: number | null) =>
  ctr == null ? '—' : (ctr * 100).toFixed(2) + '%'

const formatPct = (pct: number | null) =>
  pct == null ? '—' : pct.toFixed(1) + '%'

const formatMoney = (n: number | null) =>
  n == null ? '—' : '$' + n.toFixed(2)

// like % = likes / (likes + dislikes) from the RYD API
const likePercent = computed(() => {
  if (!video.value || dislikeCount.value === null) return null  // loading
  if (dislikeCount.value < 0) return null  // fetch failed
  const total = video.value.like_count + dislikeCount.value
  if (total === 0) return null
  return (video.value.like_count / total * 100).toFixed(1) + '%'
})

const categoryName = computed(() =>
  video.value?.category_id ? (CATEGORIES[video.value.category_id] ?? `Category ${video.value.category_id}`) : '—'
)

const shortDescription = computed(() => {
  const d = video.value?.description ?? ''
  return d.length > 300 ? d.slice(0, 300) + '…' : d
})

const hasAnalytics = computed(() =>
  video.value && (
    video.value.click_through_rate != null ||
    video.value.average_view_duration_seconds != null ||
    video.value.impressions != null ||
    video.value.average_view_percentage != null ||
    video.value.rpm != null ||
    video.value.estimated_revenue != null
  )
)

interface HistoryRow {
  label: string
  view_count: number
  like_count: number
  comment_count: number
}

const fmtDay = (day: string) => {
  // "Nov. 12, 2023" format — add period after 3-letter month abbreviation
  const s = new Date(day + 'T12:00:00').toLocaleDateString('en-US', {
    month: 'short', day: 'numeric', year: 'numeric'
  })
  return s.replace(/^([A-Za-z]{3})\b/, '$1.')
}

// stats history: today's row pinned at top (live stats, no api lag), then up to 9 points
// from the analytics daily data spread from release day to most recent available
const filteredHistory = computed((): HistoryRow[] => {
  if (!video.value) return []

  // today row always uses the live view/like/comment counts from the main video fetch
  const now = new Date()
  const todayStr = `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, '0')}-${String(now.getDate()).padStart(2, '0')}`
  const todayLabel = fmtDay(todayStr)
  const todayRow: HistoryRow = {
    label: todayLabel,
    view_count: video.value.view_count,
    like_count: video.value.like_count,
    comment_count: video.value.comment_count,
  }

  const data = dailyHistory.value
  if (!data.length) return [todayRow]

  // build running cumulative totals from analytics data
  let cumViews = 0, cumLikes = 0, cumComments = 0
  const cumulative = data.map(d => {
    cumViews += d.views
    cumLikes += d.likes
    cumComments += d.comments
    return { day: d.day, views: cumViews, likes: cumLikes, comments: cumComments }
  })

  // always pin day 1 (release), then pick up to 8 evenly spaced points from the rest
  const first = cumulative[0]
  let rest: typeof cumulative = []
  if (cumulative.length > 1) {
    const restData = cumulative.slice(1)
    const count = Math.min(8, restData.length)
    const step = (restData.length - 1) / Math.max(count - 1, 1)
    rest = Array.from({ length: count }, (_, i) => restData[Math.round(i * step)])
  }

  const historicalRows = [first, ...rest].map(d => ({
    label: fmtDay(d.day),
    view_count: d.views,
    like_count: d.likes,
    comment_count: d.comments,
  })).reverse() // newest historical first

  // today row at the very top, then historical rows below
  return [todayRow, ...historicalRows]
})

const historyIntervalLabel = computed(() => {
  const total = dailyHistory.value.length
  if (!total) return ''
  if (total <= 10) return `All ${total} days of data`
  const showing = filteredHistory.value.length
  return `${showing} days across ${total} total days of data`
})

const historyMaxViews = computed(() =>
  Math.max(...filteredHistory.value.map(r => r.view_count), 1)
)
</script>

<template>
  <div class="min-h-screen text-white">

    <!-- nav -->
    <header class="sticky top-0 z-10 border-b border-white/10 bg-black/30 backdrop-blur-sm px-6 py-4 flex items-center justify-between">
      <div class="flex items-center gap-3">
        <NuxtLink to="/dashboard" class="text-gray-400 hover:text-white transition text-sm">← Dashboard</NuxtLink>
        <span class="text-gray-700 text-xs">|</span>
        <span class="text-sm font-bold tracking-tight">ViewPilot</span>
        <span class="text-gray-700 text-xs">|</span>
        <NuxtLink to="/charts" class="text-gray-600 hover:text-gray-300 transition text-xs">Charts</NuxtLink>
        <span class="text-gray-700 text-xs">|</span>
        <NuxtLink to="/autopsy" class="text-gray-600 hover:text-gray-300 transition text-xs">Autopsy</NuxtLink>
      </div>
      <!-- revenue toggle -->
      <button @click="toggleRevenue" class="flex items-center gap-2 group" title="Toggle revenue visibility">
        <span class="text-xs text-gray-500 group-hover:text-gray-300 transition">Revenue</span>
        <div class="relative w-9 h-5 rounded-full transition-colors duration-200" :class="showRevenue ? 'bg-red-500/70' : 'bg-white/15'">
          <span class="absolute top-0.5 left-0.5 w-4 h-4 rounded-full bg-white shadow transition-transform duration-200" :class="showRevenue ? 'translate-x-4' : 'translate-x-0'"></span>
        </div>
      </button>
    </header>

    <main v-if="video" class="max-w-6xl mx-auto px-6 py-8 space-y-6">

      <!-- hero card -->
      <div class="relative overflow-hidden rounded-2xl ring-1 ring-white/15">
        <!-- gradient bg -->
        <div class="absolute inset-0 bg-gradient-to-br from-slate-950 via-slate-900 to-indigo-950"></div>
        <!-- glow blobs -->
        <div class="absolute -top-16 -right-8 w-72 h-72 rounded-full bg-indigo-600/15 blur-3xl pointer-events-none"></div>
        <div class="absolute -bottom-8 left-1/3 w-80 h-32 rounded-full bg-purple-800/15 blur-2xl pointer-events-none"></div>

        <div class="relative flex flex-col md:flex-row md:h-[270px]">
          <!-- youtube embed — fixed row height means this fills top to bottom with no bars -->
          <div class="relative md:w-[480px] shrink-0 bg-black">
            <iframe
              :src="`https://www.youtube.com/embed/${video.youtube_video_id}`"
              class="absolute inset-0 w-full h-full"
              frameborder="0"
              allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture"
              allowfullscreen
            />
          </div>

          <!-- title + stats -->
          <div class="flex-1 p-4 flex flex-col justify-between min-w-0">
            <div>
              <span v-if="video.is_short" class="inline-block mb-2 text-xs font-semibold px-2 py-0.5 rounded-full bg-red-500/20 text-red-400 ring-1 ring-red-500/30">#Short</span>
              <h1 class="text-lg font-bold leading-snug">{{ video.title }}</h1>
              <p class="text-xs text-gray-500 mt-2 uppercase tracking-widest">
                {{ formatDate(video.published_at) }}
              </p>
            </div>

            <!-- colored stat cards -->
            <div class="grid grid-cols-2 gap-2">
              <div class="bg-blue-500/10 ring-1 ring-blue-500/20 rounded-xl p-2">
                <p class="text-xl font-bold text-blue-300">{{ formatNum(video.view_count) }}</p>
                <p class="text-[10px] text-blue-400/60 mt-0.5 uppercase tracking-wider">Total Views</p>
              </div>
              <div class="bg-indigo-500/10 ring-1 ring-indigo-500/20 rounded-xl p-2">
                <p class="text-xl font-bold text-indigo-300">{{ formatNum(video.views_per_day) }}</p>
                <p class="text-[10px] text-indigo-400/60 mt-0.5 uppercase tracking-wider">Views / Day</p>
              </div>
              <div class="bg-emerald-500/10 ring-1 ring-emerald-500/20 rounded-xl p-2">
                <div class="flex items-baseline gap-1.5 flex-wrap">
                  <p class="text-xl font-bold text-emerald-300">{{ formatNum(video.like_count) }}</p>
                  <span v-if="likePercent" class="text-[10px] font-medium text-emerald-400 bg-emerald-500/15 ring-1 ring-emerald-500/25 rounded px-1 py-0.5">{{ likePercent }}</span>
                  <span v-else-if="dislikeCount === null" class="text-[10px] text-gray-600">…</span>
                </div>
                <p class="text-[10px] text-emerald-400/60 mt-0.5 uppercase tracking-wider">Likes</p>
              </div>
              <div class="bg-purple-500/10 ring-1 ring-purple-500/20 rounded-xl p-2">
                <p class="text-xl font-bold text-purple-300">{{ formatNum(video.comment_count) }}</p>
                <p class="text-[10px] text-purple-400/60 mt-0.5 uppercase tracking-wider">Comments</p>
              </div>
            </div>

            <a
              :href="`https://www.youtube.com/watch?v=${video.youtube_video_id}`"
              target="_blank"
              class="block w-1/4 text-center border border-red-500/40 bg-red-500/15 hover:bg-red-500/25 hover:border-red-500/60 active:scale-95 transition px-4 py-2 rounded-xl text-xs font-semibold text-red-300 hover:text-red-200"
            >Open on YouTube</a>
          </div>
        </div>
      </div>

      <!-- analytics row (only shown when data exists) -->
      <div v-if="hasAnalytics" class="bg-slate-900/80 ring-1 ring-white/10 rounded-2xl p-6">
        <h2 class="text-xs uppercase tracking-widest text-gray-400 mb-4">Analytics</h2>
        <div class="grid grid-cols-2 md:grid-cols-3 gap-3">
          <div class="bg-amber-500/10 ring-1 ring-amber-500/20 rounded-xl p-4 text-center">
            <p class="text-2xl font-bold text-amber-300">{{ formatCtr(video.click_through_rate) }}</p>
            <p class="text-[11px] text-amber-400/60 mt-1 uppercase tracking-wider">Click-Through Rate</p>
          </div>
          <div class="bg-purple-500/10 ring-1 ring-purple-500/20 rounded-xl p-4 text-center">
            <p class="text-2xl font-bold text-purple-300">{{ formatDuration(video.average_view_duration_seconds) }}</p>
            <p class="text-[11px] text-purple-400/60 mt-1 uppercase tracking-wider">Avg Watch Time</p>
          </div>
          <div class="bg-indigo-500/10 ring-1 ring-indigo-500/20 rounded-xl p-4 text-center">
            <p class="text-2xl font-bold text-indigo-300">{{ formatNum(video.impressions) }}</p>
            <p class="text-[11px] text-indigo-400/60 mt-1 uppercase tracking-wider">Impressions</p>
          </div>
          <div class="bg-cyan-500/10 ring-1 ring-cyan-500/20 rounded-xl p-4 text-center">
            <p class="text-2xl font-bold text-cyan-300">{{ formatPct(video.average_view_percentage) }}</p>
            <p class="text-[11px] text-cyan-400/60 mt-1 uppercase tracking-wider">Avg View %</p>
          </div>
          <div class="bg-emerald-500/10 ring-1 ring-emerald-500/20 rounded-xl p-4 text-center">
            <p class="text-2xl font-bold text-emerald-300">{{ formatMoney(video.rpm) }}</p>
            <p class="text-[11px] text-emerald-400/60 mt-1 uppercase tracking-wider">RPM</p>
          </div>
          <div v-if="showRevenue" class="bg-emerald-500/10 ring-1 ring-emerald-500/20 rounded-xl p-4 text-center">
            <p class="text-2xl font-bold text-emerald-300">{{ formatMoney(video.estimated_revenue) }}</p>
            <p class="text-[11px] text-emerald-400/60 mt-1 uppercase tracking-wider">Revenue</p>
          </div>
        </div>
      </div>

      <!-- engagement + metadata row -->
      <div class="grid grid-cols-1 md:grid-cols-3 gap-6">

        <!-- description -->
        <div class="md:col-span-2 bg-slate-900/80 ring-1 ring-white/10 rounded-2xl p-6">
          <h2 class="text-xs uppercase tracking-widest text-gray-400 mb-3">Description</h2>
          <p v-if="video.description" class="text-sm text-gray-300 leading-relaxed whitespace-pre-line">
            {{ descExpanded ? video.description : shortDescription }}
          </p>
          <p v-else class="text-sm text-gray-500 italic">No description.</p>
          <button
            v-if="video.description && video.description.length > 300"
            @click="descExpanded = !descExpanded"
            class="mt-3 text-xs text-indigo-400 hover:text-indigo-300 transition"
          >
            {{ descExpanded ? 'Show less' : 'Show more' }}
          </button>
        </div>

        <!-- metadata -->
        <div class="bg-slate-900/80 ring-1 ring-white/10 rounded-2xl p-6 space-y-4">
          <h2 class="text-xs uppercase tracking-widest text-gray-400">Details</h2>
          <div class="space-y-3 text-sm">
            <div class="flex justify-between">
              <span class="text-gray-400">Duration</span>
              <span>{{ formatDuration(video.duration_seconds) }}</span>
            </div>
            <div class="flex justify-between">
              <span class="text-gray-400">Engagement</span>
              <span>{{ video.engagement_rate != null ? video.engagement_rate + '%' : '—' }}</span>
            </div>
            <div class="flex justify-between">
              <span class="text-gray-400">Mins Watched</span>
              <span>{{ video.estimated_minutes_watched != null ? video.estimated_minutes_watched.toLocaleString() : '—' }}</span>
            </div>
            <div class="flex justify-between items-center">
              <span class="text-gray-400">Video ID</span>
              <span class="text-xs font-mono text-gray-300">{{ video.youtube_video_id }}</span>
            </div>
          </div>
        </div>
      </div>

      <!-- tags -->
      <div v-if="video.tags.length" class="bg-slate-900/80 ring-1 ring-white/10 rounded-2xl p-6">
        <h2 class="text-xs uppercase tracking-widest text-gray-400 mb-4">Tags</h2>
        <div class="flex flex-wrap gap-2">
          <span
            v-for="tag in video.tags"
            :key="tag"
            class="px-3 py-1 rounded-full text-xs bg-white/5 ring-1 ring-white/10 text-gray-300"
          >
            {{ tag }}
          </span>
        </div>
      </div>

      <!-- stats history -->
      <div class="bg-slate-900/80 ring-1 ring-white/10 rounded-2xl overflow-hidden">
        <div class="px-6 py-4 border-b border-white/10 flex items-baseline justify-between">
          <h2 class="text-xs uppercase tracking-widest text-gray-400">Stats History</h2>
          <span class="text-xs text-gray-500">{{ historyIntervalLabel }}</span>
        </div>

        <!-- loading -->
        <div v-if="historyLoading" class="px-6 py-8 text-center text-sm text-gray-500">
          Fetching historical data from YouTube...
        </div>

        <!-- no data -->
        <div v-else-if="!filteredHistory.length" class="px-6 py-8 text-center text-sm text-gray-500">
          No historical data available yet.
        </div>

        <!-- table -->
        <table v-else class="w-full text-sm">
          <thead class="border-b border-white/10 text-gray-400 text-xs uppercase tracking-wider">
            <tr>
              <th class="text-left px-6 py-3">Date</th>
              <th class="px-6 py-3 text-right">Views</th>
              <th class="px-6 py-3 text-right">Likes</th>
              <th class="px-6 py-3 text-right">Comments</th>
            </tr>
          </thead>
          <tbody class="divide-y divide-white/5">
            <tr v-for="(s, i) in filteredHistory" :key="i" class="hover:bg-white/5 transition">
              <td class="px-6 py-3 text-gray-400 text-xs">{{ s.label }}</td>
              <td class="px-6 py-3 text-right">
                <div class="flex flex-col items-end gap-1">
                  <span>{{ formatNum(s.view_count) }}</span>
                  <div class="w-20 h-0.5 rounded-full bg-white/5 overflow-hidden">
                    <div class="h-full rounded-full bg-gradient-to-r from-indigo-500 to-blue-400"
                      :style="{ width: (s.view_count / historyMaxViews * 100) + '%' }"></div>
                  </div>
                </div>
              </td>
              <td class="px-6 py-3 text-right text-gray-400">{{ formatNum(s.like_count) }}</td>
              <td class="px-6 py-3 text-right text-gray-400">{{ formatNum(s.comment_count) }}</td>
            </tr>
          </tbody>
        </table>
      </div>

      <!-- comments section -->
      <div class="bg-slate-900/80 ring-1 ring-white/10 rounded-2xl overflow-hidden">
        <div class="px-6 py-4 border-b border-white/10 flex items-center justify-between">
          <h2 class="text-xs uppercase tracking-widest text-gray-400">Top Comments</h2>
          <span class="text-xs text-gray-600">{{ commentsLoading ? '…' : comments.length + ' threads' }}</span>
        </div>

        <!-- loading -->
        <div v-if="commentsLoading" class="px-6 py-10 text-center text-sm text-gray-500">
          Fetching comments…
        </div>

        <!-- no comments -->
        <div v-else-if="!comments.length" class="px-6 py-10 text-center text-sm text-gray-500">
          No comments found — they may be disabled on this video.
        </div>

        <!-- comment list -->
        <div v-else class="divide-y divide-white/5">
          <div v-for="comment in comments" :key="comment.youtube_comment_id" class="px-6 py-5">

            <!-- top-level comment -->
            <div class="flex gap-3">
              <!-- avatar — falls back to a colored letter if the image is missing or fails -->
              <a :href="comment.author_channel_url || '#'" target="_blank" class="shrink-0">
                <img v-if="comment.author_image_url && !failedAvatars.has(comment.youtube_comment_id)"
                  :src="comment.author_image_url"
                  @error="onAvatarError(comment.youtube_comment_id)"
                  class="h-9 w-9 rounded-full ring-1 ring-white/10 object-cover"
                />
                <div v-else class="h-9 w-9 rounded-full bg-indigo-600/80 flex items-center justify-center text-white text-sm font-semibold select-none">
                  {{ (comment.author_name?.[0] || '?').toUpperCase() }}
                </div>
              </a>

              <div class="flex-1 min-w-0">
                <!-- author + time -->
                <div class="flex items-baseline gap-2 mb-1">
                  <a :href="comment.author_channel_url || '#'" target="_blank"
                    class="text-sm font-semibold text-gray-200 hover:text-white transition truncate">
                    {{ comment.author_name }}
                  </a>
                  <span class="text-[11px] text-gray-600 shrink-0">{{ timeAgo(comment.published_at) }}</span>
                </div>

                <!-- text -->
                <p class="text-sm text-gray-300 leading-relaxed whitespace-pre-line">{{ comment.text }}</p>

                <!-- likes + reply count -->
                <div class="flex items-center gap-4 mt-2">
                  <span class="text-xs text-gray-500 flex items-center gap-1">
                    <span class="text-gray-400">👍</span> {{ formatNum(comment.like_count) }}
                  </span>
                  <span v-if="comment.reply_count > 0" class="text-xs text-gray-600">
                    {{ comment.reply_count }} {{ comment.reply_count === 1 ? 'reply' : 'replies' }}
                  </span>
                </div>
              </div>
            </div>

            <!-- replies -->
            <div v-if="comment.replies?.length" class="mt-4 ml-12 space-y-4">
              <div v-for="reply in comment.replies" :key="reply.youtube_comment_id" class="flex gap-3">
                <a :href="reply.author_channel_url || '#'" target="_blank" class="shrink-0">
                  <img v-if="reply.author_image_url && !failedAvatars.has(reply.youtube_comment_id)"
                    :src="reply.author_image_url"
                    @error="onAvatarError(reply.youtube_comment_id)"
                    class="h-7 w-7 rounded-full ring-1 ring-white/10 object-cover"
                  />
                  <div v-else class="h-7 w-7 rounded-full bg-indigo-600/80 flex items-center justify-center text-white text-xs font-semibold select-none">
                    {{ (reply.author_name?.[0] || '?').toUpperCase() }}
                  </div>
                </a>
                <div class="flex-1 min-w-0">
                  <div class="flex items-baseline gap-2 mb-1">
                    <a :href="reply.author_channel_url || '#'" target="_blank"
                      class="text-xs font-semibold text-gray-300 hover:text-white transition truncate">
                      {{ reply.author_name }}
                    </a>
                    <span class="text-[10px] text-gray-600 shrink-0">{{ timeAgo(reply.published_at) }}</span>
                  </div>
                  <p class="text-xs text-gray-400 leading-relaxed whitespace-pre-line">{{ reply.text }}</p>
                  <span class="text-[11px] text-gray-600 mt-1 flex items-center gap-1">
                    <span>👍</span> {{ formatNum(reply.like_count) }}
                  </span>
                </div>
              </div>
            </div>

          </div>
        </div>
      </div>

    </main>

    <!-- loading / error states -->
    <div v-else-if="loadError" class="text-center text-red-400 py-40">{{ loadError }}</div>
    <div v-else class="text-center text-gray-500 py-40">Loading...</div>

  </div>
</template>
