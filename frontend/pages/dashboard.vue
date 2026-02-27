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
const sortBy = ref('published_at')
const order = ref('desc')
const page = ref(1)
const perPage = 10

// load channel then videos on mount
onMounted(async () => {
  await loadChannel()
})

const loadChannel = async () => {
  const channels = await api<Channel[]>('/api/v1/channels')
  if (channels.length > 0) {
    channel.value = channels[0]
    await loadVideos()
  }
}

const loadVideos = async () => {
  if (!channel.value) return
  const data = await api<VideosResponse>(
    `/api/v1/videos?channel_id=${channel.value.id}&sort_by=${sortBy.value}&order=${order.value}&page=${page.value}&per_page=${perPage}`
  )
  videos.value = data.videos
  totalVideos.value = data.total
}

const sync = async () => {
  syncing.value = true
  try {
    await api('/api/v1/channels/sync', { method: 'POST' })
    await loadChannel()
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
</script>

<template>
  <div class="min-h-screen bg-gray-950 text-white">

    <!-- top nav -->
    <header class="border-b border-gray-800 px-6 py-4 flex items-center justify-between">
      <span class="text-lg font-bold tracking-tight">ViewPilot</span>
      <div class="flex items-center gap-4">
        <div class="flex items-center gap-2">
          <img v-if="user?.picture_url" :src="user.picture_url" class="h-7 w-7 rounded-full" />
          <span class="text-sm text-gray-400">{{ user?.name }}</span>
        </div>
        <button @click="logout" class="text-sm text-gray-400 hover:text-white transition">Logout</button>
      </div>
    </header>

    <main class="max-w-6xl mx-auto px-6 py-8">

      <!-- channel stats bar -->
      <div v-if="channel" class="bg-gray-900 rounded-xl p-6 mb-8 flex items-center gap-6">
        <img v-if="channel.thumbnail_url" :src="channel.thumbnail_url" class="h-14 w-14 rounded-full" />
        <div class="flex-1">
          <h2 class="text-xl font-semibold">{{ channel.title }}</h2>
          <p v-if="channel.last_synced_at" class="text-xs text-gray-500 mt-0.5">
            Last synced {{ formatDate(channel.last_synced_at) }}
          </p>
        </div>
        <div class="flex gap-8 text-center">
          <div>
            <p class="text-2xl font-bold">{{ formatNum(channel.subscriber_count) }}</p>
            <p class="text-xs text-gray-400 mt-0.5">Subscribers</p>
          </div>
          <div>
            <p class="text-2xl font-bold">{{ formatNum(channel.view_count) }}</p>
            <p class="text-xs text-gray-400 mt-0.5">Total views</p>
          </div>
          <div>
            <p class="text-2xl font-bold">{{ formatNum(channel.video_count) }}</p>
            <p class="text-xs text-gray-400 mt-0.5">Videos</p>
          </div>
        </div>
        <button
          @click="sync"
          :disabled="syncing"
          class="ml-4 rounded-lg bg-indigo-600 px-4 py-2 text-sm font-medium hover:bg-indigo-500 disabled:opacity-50 transition"
        >
          {{ syncing ? 'Syncing...' : 'Sync' }}
        </button>
      </div>

      <!-- loading state -->
      <div v-else class="text-center text-gray-500 py-20">Loading channel...</div>

      <!-- video table -->
      <div v-if="videos.length" class="bg-gray-900 rounded-xl overflow-hidden">
        <table class="w-full text-sm">
          <thead class="border-b border-gray-800 text-gray-400 text-xs uppercase tracking-wider">
            <tr>
              <th class="text-left px-4 py-3">Video</th>
              <th class="px-4 py-3 cursor-pointer hover:text-white" @click="setSort('published_at')">
                Date {{ sortIcon('published_at') }}
              </th>
              <th class="px-4 py-3 cursor-pointer hover:text-white" @click="setSort('views')">
                Views {{ sortIcon('views') }}
              </th>
              <th class="px-4 py-3 cursor-pointer hover:text-white" @click="setSort('likes')">
                Likes {{ sortIcon('likes') }}
              </th>
              <th class="px-4 py-3 cursor-pointer hover:text-white" @click="setSort('comments')">
                Comments {{ sortIcon('comments') }}
              </th>
            </tr>
          </thead>
          <tbody class="divide-y divide-gray-800">
            <tr v-for="v in videos" :key="v.id" class="hover:bg-gray-800/50 transition">
              <td class="px-4 py-3 flex items-center gap-3 max-w-sm">
                <img v-if="v.thumbnail_url" :src="v.thumbnail_url" class="h-10 w-16 rounded object-cover shrink-0" />
                <span class="truncate text-gray-100">{{ v.title }}</span>
              </td>
              <td class="px-4 py-3 text-center text-gray-400">{{ formatDate(v.published_at) }}</td>
              <td class="px-4 py-3 text-center">{{ formatNum(v.view_count) }}</td>
              <td class="px-4 py-3 text-center text-gray-400">{{ formatNum(v.like_count) }}</td>
              <td class="px-4 py-3 text-center text-gray-400">{{ formatNum(v.comment_count) }}</td>
            </tr>
          </tbody>
        </table>

        <!-- pagination -->
        <div class="border-t border-gray-800 px-4 py-3 flex items-center justify-between text-sm text-gray-400">
          <span>{{ totalVideos }} videos — page {{ page }} of {{ totalPages }}</span>
          <div class="flex gap-2">
            <button @click="prevPage" :disabled="page === 1" class="px-3 py-1 rounded bg-gray-800 hover:bg-gray-700 disabled:opacity-40 transition">←</button>
            <button @click="nextPage" :disabled="page === totalPages" class="px-3 py-1 rounded bg-gray-800 hover:bg-gray-700 disabled:opacity-40 transition">→</button>
          </div>
        </div>
      </div>

    </main>
  </div>
</template>
