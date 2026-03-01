<script setup lang="ts">
definePageMeta({ middleware: 'auth' })

const api = useApi()
const { user, logout } = useAuth()

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
const videos = ref<Video[]>([])
const totalVideos = ref(0)
const syncing = ref(false)
const loadError = ref<string | null>(null)
const syncError = ref<string | null>(null)
const sortBy = ref('published_at')
const order = ref('desc')
const page = ref(1)
const perPage = 10

// dislike counts fetched from the Return YouTube Dislike API (returnyoutubedislikeapi.com)
// keyed by youtube_video_id
const dislikes = ref<Record<string, number>>({})

// load channel then videos on mount
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
    const data = await api<VideosResponse>(
      `/api/v1/videos?channel_id=${channel.value.id}&sort_by=${sortBy.value}&order=${order.value}&page=${page.value}&per_page=${perPage}`
    )
    videos.value = data.videos
    totalVideos.value = data.total
    fetchDislikes(data.videos)
  } catch (e) {
    loadError.value = 'failed to load videos'
  }
}

// one backend call gets all dislike counts for the page — backend caches them in redis for 24h
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

const setSort = async (col: string) => {
  if (sortBy.value === col) {
    order.value = order.value === 'desc' ? 'asc' : 'desc'
  } else {
    sortBy.value = col
    order.value = 'desc'
  }
  page.value = 1
  await loadVideos()
}

const totalPages = computed(() => Math.ceil(totalVideos.value / perPage))

// relative performance bar — each video's views/day vs the page's best
const pageMaxViewsPerDay = computed(() => Math.max(...videos.value.map(v => v.views_per_day), 1))

const prevPage = async () => {
  if (page.value > 1) { page.value--; await loadVideos() }
}
const nextPage = async () => {
  if (page.value < totalPages.value) { page.value++; await loadVideos() }
}

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

// format seconds into m:ss (e.g. 274 → "4:34")
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

// pre-computed map so the template never calls a function twice per row per render
const likeRatioMap = computed<Record<string, string | null>>(() => {
  const map: Record<string, string | null> = {}
  for (const v of videos.value) {
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

    <!-- nav — matches autopsy styling -->
    <header class="border-b border-white/10 bg-black/30 backdrop-blur-[2px] px-6 py-4 flex items-center justify-between sticky top-0 z-10">
      <span class="text-lg font-bold tracking-tight">ViewPilot</span>
      <div class="flex items-center gap-4">
        <div class="flex items-center gap-2.5">
          <img v-if="user?.picture_url" :src="user.picture_url" class="h-8 w-8 rounded-full ring-1 ring-white/20" />
          <span class="text-sm text-gray-300">{{ user?.name }}</span>
        </div>
        <div class="w-px h-4 bg-white/10"></div>
        <button @click="logout" class="text-sm text-gray-500 hover:text-white transition">Logout</button>
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

      <!-- video table -->
      <div v-if="videos.length" class="bg-slate-900/80 ring-1 ring-white/15 rounded-2xl overflow-hidden">

        <!-- table card header -->
        <div class="px-6 py-4 border-b border-white/10 flex items-center justify-between">
          <div class="flex items-center gap-3">
            <div class="w-1 h-4 rounded-full bg-gradient-to-b from-indigo-400 to-purple-500"></div>
            <h2 class="text-xs uppercase tracking-widest text-gray-300">Videos</h2>
          </div>
          <span class="text-xs text-gray-600">{{ totalVideos }} total</span>
        </div>

        <table class="w-full text-sm">
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
            <template v-for="(v, i) in videos" :key="v.id">

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
                <td class="px-4 pt-3 pb-2 text-center">
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
                <td colspan="7" class="px-5 pb-4 pt-0">
                  <!-- views/day performance bar -->
                  <div class="pl-[84px] pr-4 mb-2.5">
                    <div class="h-0.5 rounded-full bg-white/5 overflow-hidden">
                      <div
                        class="h-full rounded-full bg-gradient-to-r from-indigo-500 to-blue-400"
                        :style="{ width: Math.round(Math.min(v.views_per_day / pageMaxViewsPerDay, 1) * 100) + '%' }"
                      ></div>
                    </div>
                  </div>
                  <!-- colored chips -->
                  <div class="flex items-center gap-2 pl-[84px] flex-wrap">
                    <span class="bg-blue-500/10 ring-1 ring-blue-500/20 rounded-lg px-2.5 py-1 text-xs text-blue-400/80">
                      Views/day <span class="text-blue-300 font-medium ml-1">{{ formatNum(v.views_per_day) }}</span>
                    </span>
                    <span class="bg-purple-500/10 ring-1 ring-purple-500/20 rounded-lg px-2.5 py-1 text-xs text-purple-400/80">
                      Avg watch <span class="text-purple-300 font-medium ml-1">{{ formatDuration(v.average_view_duration_seconds) }}</span>
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
        <div class="border-t border-white/10 bg-black/20 px-6 py-3 flex items-center justify-between">
          <span class="text-xs text-gray-500">
            Showing {{ (page - 1) * perPage + 1 }}–{{ Math.min(page * perPage, totalVideos) }} of {{ totalVideos }} videos
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
