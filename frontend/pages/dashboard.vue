<script setup lang="ts">
definePageMeta({ middleware: 'auth' })

const api = useApi()
const { user, logout } = useAuth()
const { showRevenue, toggleRevenue } = useRevenue()

interface Channel {
  id: string
  title: string
  thumbnail_url: string | null
  subscriber_count: number | null
  video_count: number | null
  view_count: number | null
  last_synced_at: string | null
}

interface Video {
  id: string
  youtube_video_id: string
  title: string
  published_at: string
  duration_seconds: number | null
  is_short: boolean
  thumbnail_url: string | null
  view_count: number
  like_count: number
  comment_count: number
  views_per_day: number
  click_through_rate: number | null
  impressions: number | null
  average_view_duration_seconds: number | null
  average_view_percentage: number | null
  estimated_revenue: number | null
  rpm: number | null
}

interface VideosResponse {
  total: number
  page: number
  per_page: number
  videos: Video[]
}

const channel = ref<Channel | null>(null)
const allVideos = ref<Video[]>([])
const syncing = ref(false)
const loadError = ref<string | null>(null)
const syncError = ref<string | null>(null)
const sortBy = ref('published_at')
const order = ref('desc')
const page = ref(1)
const perPage = 20

// filter state
const searchQuery = ref('')
const dateFrom = ref<string | null>(null)  // "YYYY-MM" or null
const dateTo   = ref<string | null>(null)  // "YYYY-MM" or null

// unique year-months from the actual video library, oldest first
const availableMonths = computed(() => {
  const months = new Set<string>()
  for (const v of allVideos.value) months.add(v.published_at.slice(0, 7))
  return [...months].sort()
})

// from options: exclude anything after the current "to" selection
const fromOptions = computed(() =>
  dateTo.value ? availableMonths.value.filter(m => m <= dateTo.value!) : availableMonths.value
)

// to options: exclude anything before the current "from" selection
const toOptions = computed(() =>
  dateFrom.value ? availableMonths.value.filter(m => m >= dateFrom.value!) : availableMonths.value
)

// "2023-01" → "Jan 2023"
const fmtMonth = (ym: string) => {
  const [y, m] = ym.split('-')
  return new Date(+y, +m - 1).toLocaleString('en-US', { month: 'short', year: 'numeric' })
}

// dislike counts keyed by youtube_video_id — fetched from the backend (cached in redis for 24h)
const dislikes = ref<Record<string, number>>({})

onMounted(async () => {
  await loadChannel()
})

const loadChannel = async () => {
  try {
    const channels = await api<Channel[]>('/api/v1/channels')
    if (channels.length > 0) {
      channel.value = channels[0]
      await loadVideos()
    }
  } catch (e) {
    loadError.value = 'failed to load channel — is the backend running?'
  }
}

const loadVideos = async () => {
  if (!channel.value) return
  try {
    // load the full library at once so search/filter works across all videos, not just one page
    const data = await api<VideosResponse>(
      `/api/v1/videos?channel_id=${channel.value.id}&sort_by=published_at&order=desc&page=1&per_page=500`
    )
    allVideos.value = data.videos
  } catch (e) {
    loadError.value = 'failed to load videos'
  }
}

const fetchDislikes = async (videoList: Video[]) => {
  if (!videoList.length) return
  const ids = videoList.map(v => v.youtube_video_id).join(',')
  try {
    const res = await api<Record<string, number | null>>(`/api/v1/videos/dislikes?ids=${ids}`)
    for (const [ytId, count] of Object.entries(res)) {
      if (count != null) dislikes.value[ytId] = count
    }
  } catch {
    // silently skip — dislike badge is a nice-to-have
  }
}

const sync = async () => {
  syncing.value = true
  syncError.value = null
  try {
    await api('/api/v1/channels/sync', { method: 'POST' })
    await loadChannel()
  } catch {
    syncError.value = 'sync failed — try again in a moment'
  } finally {
    syncing.value = false
  }
}

// returns the sort value for a video given a column key — handles all sortable fields
const getSortValue = (v: Video, col: string): number | string | null => {
  switch (col) {
    case 'views':        return v.view_count
    case 'likes':        return v.like_count
    case 'comments':     return v.comment_count
    case 'published_at': return v.published_at
    case 'duration':     return v.duration_seconds
    case 'title':        return v.title
    case 'revenue':      return v.estimated_revenue
    case 'rpm':          return v.rpm
    default:             return null
  }
}

// all filtering and sorting is client-side — instant, no api round-trips
const filteredSorted = computed(() => {
  let list = allVideos.value

  // title search — case-insensitive substring match
  if (searchQuery.value.trim()) {
    const q = searchQuery.value.toLowerCase().trim()
    list = list.filter(v => v.title.toLowerCase().includes(q))
  }

  // date range — compare "YYYY-MM" strings (lexicographic works correctly for ISO dates)
  if (dateFrom.value) list = list.filter(v => v.published_at.slice(0, 7) >= dateFrom.value!)
  if (dateTo.value)   list = list.filter(v => v.published_at.slice(0, 7) <= dateTo.value!)

  // sort — nulls always sink to the bottom regardless of sort direction
  const dir = order.value === 'desc' ? -1 : 1
  return [...list].sort((a, b) => {
    const av = getSortValue(a, sortBy.value)
    const bv = getSortValue(b, sortBy.value)
    if (av == null && bv == null) return 0
    if (av == null) return 1
    if (bv == null) return -1
    if (typeof av === 'string' && typeof bv === 'string') return dir * av.localeCompare(bv)
    return dir * ((av as number) - (bv as number))
  })
})

const totalFiltered  = computed(() => filteredSorted.value.length)
const totalPages     = computed(() => Math.ceil(totalFiltered.value / perPage))
const paginatedVideos = computed(() =>
  filteredSorted.value.slice((page.value - 1) * perPage, page.value * perPage)
)

const hasActiveFilters = computed(() =>
  searchQuery.value.trim() !== '' || dateFrom.value !== null || dateTo.value !== null
)

const clearFilters = () => {
  searchQuery.value = ''
  dateFrom.value = null
  dateTo.value = null
}

// reset to page 1 whenever filters or sort change so you don't end up on an empty page
watch([searchQuery, dateFrom, dateTo, sortBy, order], () => {
  page.value = 1
})

// fetch dislike counts whenever the visible set changes (pagination, filters)
watch(paginatedVideos, (newVideos) => {
  fetchDislikes(newVideos)
}, { immediate: true })

const setSort = (col: string) => {
  if (sortBy.value === col) {
    order.value = order.value === 'desc' ? 'asc' : 'desc'
  } else {
    sortBy.value = col
    order.value = 'desc'
  }
}

// relative performance bar — each video vs the best on the current visible page
const pageMaxViewsPerDay = computed(() =>
  Math.max(...paginatedVideos.value.map(v => v.views_per_day), 1)
)

const prevPage = () => { if (page.value > 1) page.value-- }
const nextPage = () => { if (page.value < totalPages.value) page.value++ }

const formatNum = (n: number | null) => {
  if (n == null) return '—'
  if (n >= 1_000_000) return (n / 1_000_000).toFixed(1) + 'M'
  if (n >= 1_000) return (n / 1_000).toFixed(1) + 'K'
  return n.toLocaleString()
}

const formatDate = (iso: string) =>
  new Date(iso).toLocaleDateString('en-GB', { day: 'numeric', month: 'short', year: 'numeric' })

const sortIcon = (col: string) => {
  if (sortBy.value !== col) return '↕'
  return order.value === 'desc' ? '↓' : '↑'
}

const formatDuration = (secs: number | null) => {
  if (secs == null) return '—'
  const m = Math.floor(secs / 60)
  const s = Math.floor(secs % 60)
  return `${m}:${String(s).padStart(2, '0')}`
}

const formatCtr = (ctr: number | null) => {
  if (ctr == null) return '—'
  return (ctr * 100).toFixed(1) + '%'
}

const formatMoney = (n: number | null) => {
  if (n == null) return '—'
  return '$' + n.toFixed(2)
}

const formatRpm = (n: number | null) => {
  if (n == null) return '—'
  return '$' + n.toFixed(2)
}

// pre-computed so the template never calls a function twice per row per render
const likeRatioMap = computed<Record<string, string | null>>(() => {
  const map: Record<string, string | null> = {}
  for (const v of paginatedVideos.value) {
    const dis = dislikes.value[v.youtube_video_id]
    if (dis === undefined) { map[v.youtube_video_id] = null; continue }
    const total = v.like_count + dis
    map[v.youtube_video_id] = total > 0 ? (v.like_count / total * 100).toFixed(1) + '%' : null
  }
  return map
})
</script>

<template>
  <div class="min-h-screen text-white">

    <!-- nav -->
    <header class="border-b border-white/10 bg-black/30 backdrop-blur-[2px] px-6 py-4 flex items-center justify-between sticky top-0 z-10">
      <span class="text-lg font-bold tracking-tight">ViewPilot</span>
      <div class="flex items-center gap-4">
        <!-- revenue toggle -->
        <button @click="toggleRevenue" class="flex items-center gap-2 group" title="Toggle revenue visibility">
          <span class="text-sm text-gray-300 group-hover:text-white transition">Revenue</span>
          <div class="relative w-9 h-5 rounded-full transition-colors duration-200" :class="showRevenue ? 'bg-red-500/70' : 'bg-white/15'">
            <span class="absolute top-0.5 left-0.5 w-4 h-4 rounded-full bg-white shadow transition-transform duration-200" :class="showRevenue ? 'translate-x-4' : 'translate-x-0'"></span>
          </div>
        </button>
        <div class="w-px h-4 bg-white/10"></div>
        <div class="flex items-center gap-2.5">
          <img v-if="user?.picture_url" :src="user.picture_url" class="h-8 w-8 rounded-full ring-1 ring-white/20" />
          <span class="text-sm font-medium text-white">{{ user?.name }}</span>
        </div>
        <div class="w-px h-4 bg-white/10"></div>
        <button @click="logout" class="text-sm text-gray-300 hover:text-white border border-white/15 bg-white/5 hover:bg-white/10 rounded-lg px-3 py-1.5 transition">Logout</button>
      </div>
    </header>

    <main class="max-w-6xl mx-auto px-6 py-8 space-y-6">

      <!-- channel hero card -->
      <div v-if="channel" class="relative overflow-hidden rounded-2xl ring-1 ring-white/15">
        <!-- dark gradient base -->
        <div class="absolute inset-0 bg-gradient-to-br from-indigo-950 via-slate-900 to-purple-950"></div>
        <!-- ambient glow blobs -->
        <div class="absolute -top-24 -left-12 w-80 h-80 rounded-full bg-purple-600/20 blur-3xl pointer-events-none"></div>
        <div class="absolute -top-8 right-24 w-60 h-60 rounded-full bg-indigo-500/15 blur-3xl pointer-events-none"></div>
        <div class="absolute bottom-0 left-1/2 w-96 h-32 rounded-full bg-indigo-800/20 blur-2xl pointer-events-none"></div>

        <!-- avatar + name + buttons -->
        <div class="relative px-8 pt-8 pb-6 flex items-center gap-6">
          <div class="relative shrink-0">
            <div class="absolute inset-0 rounded-full bg-purple-500/50 blur-xl scale-125 pointer-events-none"></div>
            <img v-if="channel.thumbnail_url" :src="channel.thumbnail_url"
              class="relative h-20 w-20 rounded-full ring-2 ring-purple-400/40 shrink-0" />
            <div v-else class="relative h-20 w-20 rounded-full bg-white/10 flex items-center justify-center text-gray-400 text-2xl ring-2 ring-purple-400/20">▶</div>
          </div>

          <div class="flex-1 min-w-0">
            <h1 class="text-3xl font-bold tracking-tight truncate">{{ channel.title }}</h1>
            <p v-if="channel.last_synced_at" class="text-xs text-purple-400/50 mt-2 uppercase tracking-widest">
              Synced {{ formatDate(channel.last_synced_at) }}
            </p>
          </div>

          <div class="flex items-center gap-3 shrink-0">
            <NuxtLink
              to="/charts"
              class="border border-indigo-500/40 bg-indigo-500/15 hover:bg-indigo-500/30 hover:border-indigo-400/60 active:scale-95 px-8 py-3.5 rounded-xl text-base font-semibold text-indigo-300 hover:text-indigo-200 transition"
            >Charts</NuxtLink>
            <NuxtLink
              to="/autopsy"
              class="border border-purple-500/40 bg-purple-500/15 hover:bg-purple-500/30 hover:border-purple-400/60 active:scale-95 px-8 py-3.5 rounded-xl text-base font-semibold text-purple-300 hover:text-purple-200 transition"
            >Autopsy</NuxtLink>
            <button
              @click="sync"
              :disabled="syncing"
              class="border border-indigo-500/40 bg-indigo-500/15 hover:bg-indigo-500/30 hover:border-indigo-400/60 disabled:opacity-40 active:scale-95 px-8 py-3.5 rounded-xl text-base font-semibold text-indigo-300 hover:text-indigo-200 transition"
            >{{ syncing ? 'Syncing…' : 'Sync' }}</button>
          </div>
        </div>

        <!-- stat mini-cards -->
        <div class="relative px-8 pb-8 grid grid-cols-3 gap-3">
          <div class="bg-white/5 rounded-xl p-5 ring-1 ring-white/10 flex flex-col gap-1.5">
            <span class="text-3xl font-bold tracking-tight">{{ formatNum(channel.subscriber_count) }}</span>
            <span class="text-xs text-gray-500 uppercase tracking-widest font-medium">Subscribers</span>
          </div>
          <div class="bg-white/5 rounded-xl p-5 ring-1 ring-white/10 flex flex-col gap-1.5">
            <span class="text-3xl font-bold tracking-tight">{{ formatNum(channel.view_count) }}</span>
            <span class="text-xs text-gray-500 uppercase tracking-widest font-medium">Total Views</span>
          </div>
          <div class="bg-white/5 rounded-xl p-5 ring-1 ring-white/10 flex flex-col gap-1.5">
            <span class="text-3xl font-bold tracking-tight">{{ formatNum(channel.video_count) }}</span>
            <span class="text-xs text-gray-500 uppercase tracking-widest font-medium">Videos</span>
          </div>
        </div>

        <span v-if="syncError" class="absolute bottom-4 right-8 text-xs text-red-400">{{ syncError }}</span>
      </div>

      <!-- error state -->
      <div v-else-if="loadError" class="bg-slate-900/80 ring-1 ring-white/10 rounded-2xl px-8 py-16 text-center text-red-400 text-sm">
        {{ loadError }}
      </div>

      <!-- loading state -->
      <div v-else class="bg-slate-900/80 ring-1 ring-white/10 rounded-2xl px-8 py-16 text-center text-gray-500 text-sm">
        Loading channel…
      </div>

      <!-- video table — only shows once all videos are loaded -->
      <div v-if="allVideos.length" class="bg-slate-900/80 ring-1 ring-white/15 rounded-2xl overflow-hidden">

        <!-- search + date filters in one row -->
        <div class="px-5 pt-5 pb-4 flex items-center gap-3">
          <!-- search -->
          <div class="relative flex-1">
            <svg class="absolute left-3.5 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-500 pointer-events-none" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="2" stroke="currentColor">
              <path stroke-linecap="round" stroke-linejoin="round" d="m21 21-4.35-4.35m0 0A7 7 0 1 0 6.65 6.65a7 7 0 0 0 9.99 9.99z" />
            </svg>
            <input
              v-model="searchQuery"
              type="text"
              placeholder="Search videos by title…"
              class="w-full bg-white/5 border border-white/10 rounded-xl pl-10 pr-10 py-2 text-sm text-gray-200 placeholder-gray-600 focus:outline-none focus:ring-2 focus:ring-indigo-500/40 focus:border-indigo-500/30 transition"
            />
            <button
              v-if="searchQuery"
              @click="searchQuery = ''"
              class="absolute right-3.5 top-1/2 -translate-y-1/2 text-gray-500 hover:text-gray-300 transition text-sm leading-none"
            >✕</button>
          </div>

          <!-- from -->
          <div class="flex items-center gap-1.5 shrink-0">
            <span class="text-[10px] text-gray-600 uppercase tracking-widest">From</span>
            <select
              v-model="dateFrom"
              class="bg-slate-800 border border-white/15 rounded-lg px-2.5 py-2 text-xs text-gray-200 focus:outline-none focus:ring-1 focus:ring-indigo-500/40 transition cursor-pointer"
            >
              <option :value="null" class="bg-slate-800 text-gray-200">Any</option>
              <option v-for="m in fromOptions" :key="m" :value="m" class="bg-slate-800 text-gray-200">{{ fmtMonth(m) }}</option>
            </select>
          </div>

          <!-- to -->
          <div class="flex items-center gap-1.5 shrink-0">
            <span class="text-[10px] text-gray-600 uppercase tracking-widest">To</span>
            <select
              v-model="dateTo"
              class="bg-slate-800 border border-white/15 rounded-lg px-2.5 py-2 text-xs text-gray-200 focus:outline-none focus:ring-1 focus:ring-indigo-500/40 transition cursor-pointer"
            >
              <option :value="null" class="bg-slate-800 text-gray-200">Any</option>
              <option v-for="m in toOptions" :key="m" :value="m" class="bg-slate-800 text-gray-200">{{ fmtMonth(m) }}</option>
            </select>
          </div>

          <!-- clear all -->
          <button
            v-if="hasActiveFilters"
            @click="clearFilters"
            class="text-[11px] text-gray-500 hover:text-gray-300 underline underline-offset-2 transition shrink-0"
          >Clear</button>
        </div>

        <!-- result count divider -->
        <div class="border-t border-white/5 px-6 py-3 flex items-center justify-between">
          <div class="flex items-center gap-3">
            <div class="w-1 h-4 rounded-full bg-gradient-to-b from-indigo-400 to-purple-500"></div>
            <h2 class="text-xs uppercase tracking-widest text-gray-300">Videos</h2>
          </div>
          <span class="text-xs text-gray-600">
            <template v-if="hasActiveFilters">
              <span class="text-gray-400 font-medium">{{ totalFiltered }}</span> match · {{ allVideos.length }} total
            </template>
            <template v-else>{{ allVideos.length }} total</template>
          </span>
        </div>

        <!-- empty filter result -->
        <div v-if="totalFiltered === 0" class="px-6 py-16 text-center border-t border-white/5">
          <p class="text-gray-500 text-sm">No videos match your filters.</p>
          <button @click="clearFilters" class="mt-3 text-xs text-indigo-400 hover:text-indigo-300 transition">Clear filters</button>
        </div>

        <!-- table -->
        <table v-else class="w-full text-sm border-t border-white/5">
          <thead class="border-b border-white/5 text-xs uppercase tracking-wider">
            <tr>
              <th class="text-left px-5 py-3 text-gray-500">Video</th>
              <th
                class="px-4 py-3 cursor-pointer select-none transition"
                :class="sortBy === 'published_at' ? 'text-white' : 'text-gray-500 hover:text-gray-300'"
                @click="setSort('published_at')"
              >Date {{ sortIcon('published_at') }}</th>
              <th
                class="px-4 py-3 cursor-pointer select-none transition"
                :class="sortBy === 'views' ? 'text-white' : 'text-gray-500 hover:text-gray-300'"
                @click="setSort('views')"
              >Views {{ sortIcon('views') }}</th>
              <th
                v-if="showRevenue"
                class="px-4 py-3 cursor-pointer select-none transition"
                :class="sortBy === 'revenue' ? 'text-white' : 'text-gray-500 hover:text-gray-300'"
                @click="setSort('revenue')"
              >Revenue {{ sortIcon('revenue') }}</th>
              <th
                class="px-4 py-3 cursor-pointer select-none transition"
                :class="sortBy === 'rpm' ? 'text-white' : 'text-gray-500 hover:text-gray-300'"
                @click="setSort('rpm')"
              >RPM {{ sortIcon('rpm') }}</th>
              <th
                class="px-4 py-3 cursor-pointer select-none transition"
                :class="sortBy === 'likes' ? 'text-white' : 'text-gray-500 hover:text-gray-300'"
                @click="setSort('likes')"
              >Likes {{ sortIcon('likes') }}</th>
              <th
                class="px-4 py-3 cursor-pointer select-none transition"
                :class="sortBy === 'comments' ? 'text-white' : 'text-gray-500 hover:text-gray-300'"
                @click="setSort('comments')"
              >Comments {{ sortIcon('comments') }}</th>
            </tr>
          </thead>
          <tbody class="divide-y divide-white/5">
            <template v-for="(v, i) in paginatedVideos" :key="v.id">

              <!-- main row -->
              <tr class="hover:bg-white/5 transition">
                <td class="px-5 pt-3 pb-2">
                  <div class="flex items-center gap-3 max-w-xs">
                    <img
                      v-if="v.thumbnail_url"
                      :src="v.thumbnail_url"
                      class="h-11 w-[72px] rounded-lg object-cover shrink-0 ring-1 ring-white/10"
                    />
                    <div class="flex flex-col gap-1 min-w-0">
                      <NuxtLink
                        :to="`/video/${v.id}`"
                        class="text-[15px] text-gray-200 hover:text-white transition line-clamp-2 leading-snug"
                      >{{ v.title }}</NuxtLink>
                      <span v-if="i === 0 && sortBy === 'views'" class="text-[10px] font-semibold text-amber-400/80 uppercase tracking-widest">Top video</span>
                    </div>
                  </div>
                </td>
                <td class="px-4 pt-3 pb-2 text-center text-gray-400 whitespace-nowrap text-xs">{{ formatDate(v.published_at) }}</td>
                <td class="px-4 pt-3 pb-2 text-center font-medium">{{ formatNum(v.view_count) }}</td>
                <td v-if="showRevenue" class="px-4 pt-3 pb-2 text-center">
                  <span v-if="v.estimated_revenue != null" class="text-emerald-400 font-medium">{{ formatMoney(v.estimated_revenue) }}</span>
                  <span v-else class="text-gray-600">—</span>
                </td>
                <td class="px-4 pt-3 pb-2 text-center text-gray-400">{{ formatRpm(v.rpm) }}</td>
                <td class="px-4 pt-3 pb-2 text-center text-gray-400">
                  <div class="inline-flex items-center gap-1.5">
                    <span>{{ formatNum(v.like_count) }}</span>
                    <span
                      v-if="likeRatioMap[v.youtube_video_id]"
                      class="text-[10px] font-medium bg-emerald-500/10 ring-1 ring-emerald-500/25 text-emerald-400 rounded px-1.5 py-0.5 whitespace-nowrap"
                    >{{ likeRatioMap[v.youtube_video_id] }}</span>
                  </div>
                </td>
                <td class="px-4 pt-3 pb-2 text-center text-gray-400">{{ formatNum(v.comment_count) }}</td>
              </tr>

              <!-- analytics sub-row — performance bar + colored chips -->
              <tr>
                <td :colspan="showRevenue ? 7 : 6" class="px-5 pb-4 pt-0">
                  <div class="pl-[84px] pr-4 mb-2.5">
                    <div class="h-0.5 rounded-full bg-white/5 overflow-hidden">
                      <div
                        class="h-full rounded-full bg-gradient-to-r from-indigo-500 to-blue-400"
                        :style="{ width: Math.round(Math.min(v.views_per_day / pageMaxViewsPerDay, 1) * 100) + '%' }"
                      ></div>
                    </div>
                  </div>
                  <div class="flex items-center gap-2 pl-[84px] flex-wrap">
                    <span class="bg-blue-500/10 ring-1 ring-blue-500/20 rounded-lg px-2.5 py-1 text-xs text-blue-400/80">
                      Views/day <span class="text-blue-300 font-medium ml-1">{{ formatNum(v.views_per_day) }}</span>
                    </span>
                    <span class="bg-purple-500/10 ring-1 ring-purple-500/20 rounded-lg px-2.5 py-1 text-xs text-purple-400/80">
                      Avg watch <span class="text-purple-300 font-medium ml-1">{{ formatDuration(v.average_view_duration_seconds) }}</span><span class="text-purple-600 mx-1">/</span><span class="text-purple-400/60">{{ formatDuration(v.duration_seconds) }}</span>
                    </span>
                    <span class="bg-yellow-500/10 ring-1 ring-yellow-500/20 rounded-lg px-2.5 py-1 text-xs text-yellow-400/80">
                      CTR <span class="text-yellow-300 font-medium ml-1">{{ formatCtr(v.click_through_rate) }}</span>
                    </span>
                    <span class="bg-indigo-500/10 ring-1 ring-indigo-500/20 rounded-lg px-2.5 py-1 text-xs text-indigo-400/80">
                      Impressions <span class="text-indigo-300 font-medium ml-1">{{ formatNum(v.impressions) }}</span>
                    </span>
                  </div>
                </td>
              </tr>

            </template>
          </tbody>
        </table>

        <!-- pagination -->
        <div v-if="totalPages > 1" class="border-t border-white/10 bg-black/20 px-6 py-3 flex items-center justify-between">
          <span class="text-xs text-gray-500">
            Showing {{ (page - 1) * perPage + 1 }}–{{ Math.min(page * perPage, totalFiltered) }} of {{ totalFiltered }} videos
          </span>
          <div class="flex items-center gap-1.5">
            <button
              @click="prevPage"
              :disabled="page === 1"
              class="px-3 py-1.5 rounded-lg bg-white/5 hover:bg-white/10 disabled:opacity-30 disabled:cursor-not-allowed transition text-xs text-gray-400"
            >← Prev</button>
            <span class="px-3 py-1.5 text-xs text-gray-500">{{ page }} / {{ totalPages }}</span>
            <button
              @click="nextPage"
              :disabled="page === totalPages"
              class="px-3 py-1.5 rounded-lg bg-white/5 hover:bg-white/10 disabled:opacity-30 disabled:cursor-not-allowed transition text-xs text-gray-400"
            >Next →</button>
          </div>
        </div>

      </div>

    </main>
  </div>
</template>
