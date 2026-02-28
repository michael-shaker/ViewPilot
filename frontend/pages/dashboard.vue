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
  } catch (e) {
    loadError.value = 'failed to load videos'
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
</script>

<template>
  <div class="min-h-screen text-white">

    <!-- nav — matches autopsy styling -->
    <header class="border-b border-white/10 bg-black/30 backdrop-blur-sm px-6 py-4 flex items-center justify-between sticky top-0 z-10">
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
      <div v-if="channel" class="bg-white/15 ring-1 ring-white/25 rounded-2xl overflow-hidden">

        <!-- top section: avatar + name + action buttons -->
        <div class="px-8 py-7 flex items-center gap-6">
          <img
            v-if="channel.thumbnail_url"
            :src="channel.thumbnail_url"
            class="h-16 w-16 rounded-full ring-2 ring-white/20 shrink-0"
          />
          <div v-else class="h-16 w-16 rounded-full bg-white/10 shrink-0 flex items-center justify-center text-gray-500 text-xl">▶</div>

          <div class="flex-1 min-w-0">
            <h1 class="text-2xl font-bold tracking-tight truncate">{{ channel.title }}</h1>
            <p class="text-xs text-gray-500 mt-1 uppercase tracking-wider">YouTube Channel</p>
          </div>

          <!-- action buttons — larger per spec -->
          <div class="flex items-center gap-3 shrink-0">
            <NuxtLink
              to="/autopsy"
              class="bg-purple-600 hover:bg-purple-500 active:scale-95 px-6 py-3 rounded-xl text-sm font-semibold transition"
            >Autopsy</NuxtLink>
            <button
              @click="sync"
              :disabled="syncing"
              class="bg-indigo-600 hover:bg-indigo-500 disabled:opacity-50 active:scale-95 px-6 py-3 rounded-xl text-sm font-semibold transition"
            >{{ syncing ? 'Syncing…' : 'Sync' }}</button>
          </div>
        </div>

        <!-- stats + last synced footer strip -->
        <div class="border-t border-white/10 bg-black/20 px-8 py-4 flex items-center gap-8 flex-wrap">
          <div class="flex items-baseline gap-2">
            <span class="text-xl font-bold">{{ formatNum(channel.subscriber_count) }}</span>
            <span class="text-xs text-gray-500 uppercase tracking-wider">Subscribers</span>
          </div>
          <div class="w-px h-4 bg-white/10 shrink-0"></div>
          <div class="flex items-baseline gap-2">
            <span class="text-xl font-bold">{{ formatNum(channel.view_count) }}</span>
            <span class="text-xs text-gray-500 uppercase tracking-wider">Total Views</span>
          </div>
          <div class="w-px h-4 bg-white/10 shrink-0"></div>
          <div class="flex items-baseline gap-2">
            <span class="text-xl font-bold">{{ formatNum(channel.video_count) }}</span>
            <span class="text-xs text-gray-500 uppercase tracking-wider">Videos</span>
          </div>
          <div class="flex-1"></div>
          <div v-if="channel.last_synced_at" class="text-sm text-gray-400">
            Last synced <span class="text-gray-200 font-medium ml-1">{{ formatDate(channel.last_synced_at) }}</span>
          </div>
          <span v-if="syncError" class="text-xs text-red-400">{{ syncError }}</span>
        </div>
      </div>

      <!-- error state -->
      <div v-else-if="loadError" class="bg-white/5 ring-1 ring-white/10 rounded-2xl px-8 py-16 text-center text-red-400 text-sm">
        {{ loadError }}
      </div>

      <!-- loading state -->
      <div v-else class="bg-white/5 ring-1 ring-white/10 rounded-2xl px-8 py-16 text-center text-gray-500 text-sm">
        Loading channel…
      </div>

      <!-- video table -->
      <div v-if="videos.length" class="bg-white/15 ring-1 ring-white/25 rounded-2xl overflow-hidden">

        <!-- table card header -->
        <div class="px-6 py-4 border-b border-white/10 flex items-center justify-between">
          <h2 class="text-xs uppercase tracking-widest text-gray-400">Videos</h2>
          <span class="text-xs text-gray-500">{{ totalVideos }} total</span>
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
            <template v-for="v in videos" :key="v.id">

              <!-- main row -->
              <tr class="hover:bg-white/5 transition">
                <td class="px-5 pt-3 pb-2">
                  <div class="flex items-center gap-3 max-w-xs">
                    <img
                      v-if="v.thumbnail_url"
                      :src="v.thumbnail_url"
                      class="h-11 w-[72px] rounded-lg object-cover shrink-0 ring-1 ring-white/10"
                    />
                    <NuxtLink
                      :to="`/video/${v.id}`"
                      class="text-sm text-gray-200 hover:text-white transition line-clamp-2 leading-snug"
                    >{{ v.title }}</NuxtLink>
                  </div>
                </td>
                <td class="px-4 pt-3 pb-2 text-center text-gray-400 whitespace-nowrap text-xs">{{ formatDate(v.published_at) }}</td>
                <td class="px-4 pt-3 pb-2 text-center font-medium">{{ formatNum(v.view_count) }}</td>
                <td class="px-4 pt-3 pb-2 text-center">
                  <span v-if="v.estimated_revenue != null" class="text-emerald-400 font-medium">{{ formatMoney(v.estimated_revenue) }}</span>
                  <span v-else class="text-gray-600">—</span>
                </td>
                <td class="px-4 pt-3 pb-2 text-center text-gray-400">{{ formatRpm(v.rpm) }}</td>
                <td class="px-4 pt-3 pb-2 text-center text-gray-400">{{ formatNum(v.like_count) }}</td>
                <td class="px-4 pt-3 pb-2 text-center text-gray-400">{{ formatNum(v.comment_count) }}</td>
              </tr>

              <!-- analytics sub-row — stat chips -->
              <tr>
                <td colspan="7" class="px-5 pb-3 pt-0">
                  <div class="flex items-center gap-2 pl-[84px] flex-wrap">
                    <span class="bg-white/5 rounded-lg px-2.5 py-1 text-xs text-gray-500">
                      Views/day <span class="text-gray-300 font-medium ml-1">{{ formatNum(v.views_per_day) }}</span>
                    </span>
                    <span class="bg-white/5 rounded-lg px-2.5 py-1 text-xs text-gray-500">
                      Avg watch <span class="text-gray-300 font-medium ml-1">{{ formatDuration(v.average_view_duration_seconds) }}</span>
                    </span>
                    <span class="bg-white/5 rounded-lg px-2.5 py-1 text-xs text-gray-500">
                      CTR <span class="text-gray-300 font-medium ml-1">{{ formatCtr(v.click_through_rate) }}</span>
                    </span>
                    <span class="bg-white/5 rounded-lg px-2.5 py-1 text-xs text-gray-500">
                      Impressions <span class="text-gray-300 font-medium ml-1">{{ formatNum(v.impressions) }}</span>
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
