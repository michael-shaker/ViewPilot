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

const video = ref<Video | null>(null)
const loadError = ref<string | null>(null)
const descExpanded = ref(false)
const dailyHistory = ref<DailyRow[]>([])
const historyLoading = ref(true)

onMounted(async () => {
  try {
    video.value = await api<Video>(`/api/v1/videos/${route.params.id}`)
  } catch {
    loadError.value = 'could not load video'
    return
  }

  // fetch real daily data from analytics api separately so the page loads fast
  // and the history table fills in after
  try {
    const res = await api<{ daily: { day: string, views: number, likes: number, comments: number }[] }>(
      `/api/v1/videos/${route.params.id}/history`
    )
    dailyHistory.value = res.daily
  } catch {
    // silently fall back to empty — table will just show nothing
  } finally {
    historyLoading.value = false
  }
})

const formatNum = (n: number | null) => {
  if (n == null) return '—'
  if (n >= 1_000_000) return (n / 1_000_000).toFixed(1) + 'M'
  if (n >= 1_000) return (n / 1_000).toFixed(1) + 'K'
  return n.toLocaleString()
}

const formatDate = (iso: string) =>
  new Date(iso).toLocaleDateString('en-GB', { day: 'numeric', month: 'short', year: 'numeric' })

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
</script>

<template>
  <div class="min-h-screen text-white">

    <!-- nav -->
    <header class="border-b border-white/10 px-6 py-4 flex items-center gap-4">
      <NuxtLink to="/dashboard" class="text-gray-400 hover:text-white transition text-sm flex items-center gap-1">
        ← Dashboard
      </NuxtLink>
      <span class="text-gray-600">|</span>
      <span class="text-sm font-bold tracking-tight">ViewPilot</span>
    </header>

    <main v-if="video" class="max-w-6xl mx-auto px-6 py-8 space-y-6">

      <!-- hero card -->
      <div class="bg-white/10 ring-1 ring-white/20 rounded-2xl overflow-hidden">
        <div class="flex flex-col md:flex-row gap-0">

          <!-- youtube embed -->
          <div class="md:w-[480px] shrink-0 aspect-video bg-black">
            <iframe
              :src="`https://www.youtube.com/embed/${video.youtube_video_id}`"
              class="w-full h-full"
              frameborder="0"
              allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture"
              allowfullscreen
            />
          </div>

          <!-- title + meta -->
          <div class="flex-1 p-6 flex flex-col justify-between">
            <div>
              <div class="flex items-start gap-2 mb-3">
                <span v-if="video.is_short" class="shrink-0 text-xs font-semibold px-2 py-0.5 rounded-full bg-red-500/20 text-red-400 ring-1 ring-red-500/30">#Short</span>
                <h1 class="text-xl font-bold leading-snug">{{ video.title }}</h1>
              </div>
              <div class="flex flex-wrap gap-3 text-sm text-gray-400 mb-6">
                <span>Published {{ formatDate(video.published_at) }}</span>
                <span class="text-gray-600">•</span>
                <span>{{ formatDuration(video.duration_seconds) }}</span>
                <span v-if="video.default_language" class="text-gray-600">•</span>
                <span v-if="video.default_language" class="uppercase text-xs tracking-wider">{{ video.default_language }}</span>
              </div>
            </div>

            <!-- main stat pills -->
            <div class="grid grid-cols-2 gap-3 mb-6">
              <div class="bg-white/5 rounded-xl p-4 text-center">
                <p class="text-2xl font-bold">{{ formatNum(video.view_count) }}</p>
                <p class="text-xs text-gray-400 mt-0.5">Total Views</p>
              </div>
              <div class="bg-white/5 rounded-xl p-4 text-center">
                <p class="text-2xl font-bold">{{ formatNum(video.views_per_day) }}</p>
                <p class="text-xs text-gray-400 mt-0.5">Views per Day</p>
              </div>
              <div class="bg-white/5 rounded-xl p-4 text-center">
                <p class="text-2xl font-bold">{{ formatNum(video.like_count) }}</p>
                <p class="text-xs text-gray-400 mt-0.5">Likes</p>
              </div>
              <div class="bg-white/5 rounded-xl p-4 text-center">
                <p class="text-2xl font-bold">{{ formatNum(video.comment_count) }}</p>
                <p class="text-xs text-gray-400 mt-0.5">Comments</p>
              </div>
            </div>

            <a
              :href="`https://www.youtube.com/watch?v=${video.youtube_video_id}`"
              target="_blank"
              class="inline-flex items-center gap-2 rounded-lg bg-red-600 hover:bg-red-500 transition px-4 py-2 text-sm font-medium w-fit"
            >
              ▶ Open on YouTube
            </a>
          </div>
        </div>
      </div>

      <!-- analytics row (only shown when data exists) -->
      <div v-if="hasAnalytics" class="bg-white/10 ring-1 ring-white/20 rounded-2xl p-6">
        <h2 class="text-xs uppercase tracking-widest text-gray-400 mb-4">Analytics</h2>
        <div class="grid grid-cols-2 md:grid-cols-3 gap-4 mb-4">
          <div class="bg-white/5 rounded-xl p-4 text-center">
            <p class="text-2xl font-bold">{{ formatCtr(video.click_through_rate) }}</p>
            <p class="text-xs text-gray-400 mt-0.5">Click-Through Rate</p>
          </div>
          <div class="bg-white/5 rounded-xl p-4 text-center">
            <p class="text-2xl font-bold">{{ formatDuration(video.average_view_duration_seconds) }}</p>
            <p class="text-xs text-gray-400 mt-0.5">Avg Watch Time</p>
          </div>
          <div class="bg-white/5 rounded-xl p-4 text-center">
            <p class="text-2xl font-bold">{{ formatNum(video.impressions) }}</p>
            <p class="text-xs text-gray-400 mt-0.5">Impressions</p>
          </div>
          <div class="bg-white/5 rounded-xl p-4 text-center">
            <p class="text-2xl font-bold">{{ formatPct(video.average_view_percentage) }}</p>
            <p class="text-xs text-gray-400 mt-0.5">Avg View %</p>
          </div>
          <div class="bg-white/5 rounded-xl p-4 text-center">
            <p class="text-2xl font-bold">{{ formatMoney(video.rpm) }}</p>
            <p class="text-xs text-gray-400 mt-0.5">RPM</p>
          </div>
          <div class="bg-white/5 rounded-xl p-4 text-center">
            <p class="text-2xl font-bold">{{ formatMoney(video.estimated_revenue) }}</p>
            <p class="text-xs text-gray-400 mt-0.5">Revenue</p>
          </div>
        </div>
      </div>

      <!-- engagement + metadata row -->
      <div class="grid grid-cols-1 md:grid-cols-3 gap-6">

        <!-- description -->
        <div class="md:col-span-2 bg-white/10 ring-1 ring-white/20 rounded-2xl p-6">
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
        <div class="bg-white/10 ring-1 ring-white/20 rounded-2xl p-6 space-y-4">
          <h2 class="text-xs uppercase tracking-widest text-gray-400">Details</h2>
          <div class="space-y-3 text-sm">
            <div class="flex justify-between">
              <span class="text-gray-400">Category</span>
              <span class="text-right">{{ categoryName }}</span>
            </div>
            <div class="flex justify-between">
              <span class="text-gray-400">Duration</span>
              <span>{{ formatDuration(video.duration_seconds) }}</span>
            </div>
            <div class="flex justify-between">
              <span class="text-gray-400">Type</span>
              <span>{{ video.is_short ? 'Short' : 'Regular video' }}</span>
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
      <div v-if="video.tags.length" class="bg-white/10 ring-1 ring-white/20 rounded-2xl p-6">
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
      <div class="bg-white/10 ring-1 ring-white/20 rounded-2xl overflow-hidden">
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
              <td class="px-6 py-3 text-right">{{ formatNum(s.view_count) }}</td>
              <td class="px-6 py-3 text-right text-gray-400">{{ formatNum(s.like_count) }}</td>
              <td class="px-6 py-3 text-right text-gray-400">{{ formatNum(s.comment_count) }}</td>
            </tr>
          </tbody>
        </table>
      </div>

    </main>

    <!-- loading / error states -->
    <div v-else-if="loadError" class="text-center text-red-400 py-40">{{ loadError }}</div>
    <div v-else class="text-center text-gray-500 py-40">Loading...</div>

  </div>
</template>
