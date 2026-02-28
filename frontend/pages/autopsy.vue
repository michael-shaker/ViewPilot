<script setup lang="ts">
definePageMeta({ middleware: 'auth' })

const api = useApi()

// ── types ─────────────────────────────────────────────────────────────────────

interface MetricCompare {
  top: number | null
  bottom: number | null
  delta_pct: number | null
  top_available: number
  bottom_available: number
}

interface TitleStats {
  avg_length: number | null
  avg_word_count: number | null
  has_number_pct: number
  has_question_pct: number
  has_exclamation_pct: number
  has_all_caps_pct: number
  has_colon_pct: number
  has_brackets_pct: number
  top_words: { word: string; count: number }[]
}

interface ScheduleAnalysis {
  top: Record<string, number>
  bottom: Record<string, number>
  avg_vpd_by_day: Record<string, number>
  best_day: string | null
  worst_day: string | null
}

interface DurationAnalysis {
  top: Record<string, number>
  bottom: Record<string, number>
  avg_vpd_by_bucket: Record<string, number>
  best_bucket: string | null
  shorts_pct_top: number
  shorts_pct_bottom: number
}

interface TagStats {
  avg_count: number
  top_tags: { tag: string; count: number }[]
}

interface TagAnalysis {
  top: TagStats
  bottom: TagStats
  shared_count: number
}

interface CategoryEntry {
  name: string
  count: number
  avg_vpd: number
}

interface VideoSummary {
  id: string
  youtube_video_id: string
  title: string
  thumbnail_url: string | null
  published_at: string
  view_count: number
  views_per_day: number
  ctr: number | null
  avg_view_duration: number | null
  engagement_rate: number
  duration_seconds: number | null
  is_short: boolean
  rpm: number | null
  estimated_revenue: number | null
}

interface AutopsyData {
  meta: { window_size: number; tier_pct: number; tier_count: number }
  key_metrics: Record<string, MetricCompare>
  title_analysis: { top: TitleStats; bottom: TitleStats }
  schedule_analysis: ScheduleAnalysis
  duration_analysis: DurationAnalysis
  tag_analysis: TagAnalysis
  category_analysis: { top: CategoryEntry[]; bottom: CategoryEntry[] }
  top_videos: VideoSummary[]
  bottom_videos: VideoSummary[]
}

interface Channel {
  id: string
  title: string
}

// ── state ─────────────────────────────────────────────────────────────────────

const channel = ref<Channel | null>(null)
const windowSize = ref(100)
const tierPct = ref(10)
const data = ref<AutopsyData | null>(null)
const loading = ref(false)
const error = ref<string | null>(null)

onMounted(async () => {
  try {
    const channels = await api<Channel[]>('/api/v1/channels')
    if (!channels.length) { error.value = 'no channel found'; return }
    channel.value = channels[0]
    await fetchAutopsy()
  } catch {
    error.value = 'failed to load channel'
  }
})

const fetchAutopsy = async () => {
  if (!channel.value) return
  loading.value = true
  error.value = null
  try {
    data.value = await api<AutopsyData>(
      `/api/v1/autopsy?channel_id=${channel.value.id}&window_size=${windowSize.value}&tier_pct=${tierPct.value}`
    )
  } catch {
    error.value = 'failed to load autopsy data'
  } finally {
    loading.value = false
  }
}

// ── formatting helpers ────────────────────────────────────────────────────────

const fmtNum = (n: number | null) => {
  if (n == null) return '—'
  if (n >= 1_000_000) return (n / 1_000_000).toFixed(1) + 'M'
  if (n >= 1_000) return (n / 1_000).toFixed(1) + 'K'
  return n.toLocaleString()
}

// only abbreviate at millions — everything else gets full number with commas
const fmtNumFull = (n: number | null) => {
  if (n == null) return '—'
  if (n >= 1_000_000) return (n / 1_000_000).toFixed(1) + 'M'
  return Math.round(n).toLocaleString()
}

const fmtDuration = (secs: number | null) => {
  if (secs == null) return '—'
  const h = Math.floor(secs / 3600)
  const m = Math.floor((secs % 3600) / 60)
  const s = Math.floor(secs % 60)
  if (h > 0) return `${h}:${String(m).padStart(2, '0')}:${String(s).padStart(2, '0')}`
  return `${m}:${String(s).padStart(2, '0')}`
}

const fmtDelta = (pct: number | null) => {
  if (pct == null) return null
  const sign = pct >= 0 ? '+' : ''
  return `${sign}${Math.round(pct)}%`
}

const fmtDate = (iso: string) =>
  new Date(iso).toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' })

const fmtMoney = (n: number | null) =>
  n == null ? '—' : '$' + n.toFixed(2)

const deltaColor = (pct: number | null) => {
  if (pct == null) return 'text-gray-500'
  if (pct >= 50) return 'text-emerald-400'
  if (pct >= 10) return 'text-yellow-400'
  if (pct >= -10) return 'text-gray-400'
  return 'text-red-400'
}

const deltaBg = (pct: number | null) => {
  if (pct == null) return 'bg-gray-500/20 text-gray-400'
  if (pct >= 50) return 'bg-emerald-500/20 text-emerald-400'
  if (pct >= 10) return 'bg-yellow-500/20 text-yellow-400'
  if (pct >= -10) return 'bg-gray-500/20 text-gray-400'
  return 'bg-red-500/20 text-red-400'
}

// ── metric table rows ─────────────────────────────────────────────────────────

// maps each metric key to a display label and a formatter function
const METRIC_DEFS = [
  { key: 'views_per_day',           label: 'Views per Day',        fmt: (v: number) => fmtNum(Math.round(v)) },
  { key: 'ctr',                     label: 'Click-Through Rate',   fmt: (v: number) => v.toFixed(1) + '%' },
  { key: 'avg_view_duration',       label: 'Avg Watch Time',       fmt: (v: number) => fmtDuration(v) },
  { key: 'avg_view_pct',            label: 'Avg View %',           fmt: (v: number) => v.toFixed(1) + '%' },
  { key: 'engagement_rate',         label: 'Engagement Rate',      fmt: (v: number) => v.toFixed(2) + '%' },
  { key: 'comment_rate',            label: 'Comments per 1K Views', fmt: (v: number) => (v * 10).toFixed(2) },
  { key: 'view_count',              label: 'Total Views',          fmt: (v: number) => fmtNumFull(v) },
  { key: 'impressions',             label: 'Impressions',          fmt: (v: number) => fmtNumFull(v) },
  { key: 'estimated_minutes_watched', label: 'Mins Watched',      fmt: (v: number) => fmtNumFull(v) },
  { key: 'rpm',                     label: 'RPM',                  fmt: (v: number) => fmtMoney(v) },
  { key: 'estimated_revenue',       label: 'Revenue',         fmt: (v: number) => fmtMoney(v) },
  { key: 'duration_seconds',        label: 'Avg Duration',         fmt: (v: number) => fmtDuration(v) },
  { key: 'tag_count',               label: 'Avg Tag Count',        fmt: (v: number) => v.toFixed(1) },
]

// ── metrics table sorting (difference column only, 3-state: default → desc → asc → default) ───

const metricDeltaSort = ref<'desc' | 'asc' | null>(null)

const cycleMetricSort = () => {
  if (metricDeltaSort.value === null) metricDeltaSort.value = 'desc'
  else if (metricDeltaSort.value === 'desc') metricDeltaSort.value = 'asc'
  else metricDeltaSort.value = null
}

const metricDeltaIcon = computed(() => {
  if (metricDeltaSort.value === 'desc') return '↓'
  if (metricDeltaSort.value === 'asc') return '↑'
  return '↕'
})

const metricRows = computed(() => {
  if (!data.value) return []
  const rows = METRIC_DEFS.map(def => {
    const m = data.value!.key_metrics[def.key]
    return {
      ...def,
      topFmt:    m?.top    != null ? def.fmt(m.top)    : '—',
      bottomFmt: m?.bottom != null ? def.fmt(m.bottom) : '—',
      delta:     m?.delta_pct ?? null,
      hasData:   (m?.top_available ?? 0) > 0,
    }
  })

  // no-data rows always stay at the bottom no matter what sort is active
  const withData = rows.filter(r => r.hasData)
  const noData   = rows.filter(r => !r.hasData)

  if (metricDeltaSort.value) {
    const dir = metricDeltaSort.value === 'desc' ? -1 : 1
    withData.sort((a, b) => {
      if (a.delta == null && b.delta == null) return 0
      if (a.delta == null) return 1
      if (b.delta == null) return -1
      return dir * (a.delta - b.delta)
    })
  }

  return [...withData, ...noData]
})

// ── hero cards (4 most actionable metrics) ────────────────────────────────────

const heroMetrics = computed(() => {
  if (!data.value) return []
  const km = data.value.key_metrics
  const tier = data.value.meta.tier_pct
  return [
    {
      label: 'Avg View %',
      topFmt: km.avg_view_pct?.top != null ? km.avg_view_pct.top.toFixed(1) + '%' : '—',
      bottomFmt: km.avg_view_pct?.bottom != null ? km.avg_view_pct.bottom.toFixed(1) + '%' : '—',
      delta: km.avg_view_pct?.delta_pct ?? null,
    },
    {
      label: 'Click-Through Rate',
      topFmt: km.ctr?.top != null ? km.ctr.top.toFixed(1) + '%' : '—',
      bottomFmt: km.ctr?.bottom != null ? km.ctr.bottom.toFixed(1) + '%' : '—',
      delta: km.ctr?.delta_pct ?? null,
    },
    {
      label: 'Avg Watch Time',
      topFmt: fmtDuration(km.avg_view_duration?.top ?? null),
      bottomFmt: fmtDuration(km.avg_view_duration?.bottom ?? null),
      delta: km.avg_view_duration?.delta_pct ?? null,
    },
    {
      label: 'Engagement Rate',
      topFmt: km.engagement_rate?.top != null ? km.engagement_rate.top.toFixed(2) + '%' : '—',
      bottomFmt: km.engagement_rate?.bottom != null ? km.engagement_rate.bottom.toFixed(2) + '%' : '—',
      delta: km.engagement_rate?.delta_pct ?? null,
    },
  ]
})

// ── title feature rows ────────────────────────────────────────────────────────

// converts a percentage back to "X out of N" for clearer reading
const pctToCount = (pct: number, total: number) => Math.round(pct / 100 * total)

const titleFeatures = computed(() => {
  if (!data.value) return []
  const t = data.value.title_analysis.top
  const b = data.value.title_analysis.bottom
  const n = data.value.meta.tier_count

  // all possible patterns in priority order — filter out any where both top and bottom are 0
  // so we never waste a slot on a pattern that doesn't exist in this channel's videos
  const ALL_PATTERNS = [
    { label: 'Has a number',        topPct: t.has_number_pct,      bottomPct: b.has_number_pct      },
    { label: 'Has ALL CAPS word',   topPct: t.has_all_caps_pct,    bottomPct: b.has_all_caps_pct    },
    { label: 'Has "?" question',    topPct: t.has_question_pct,    bottomPct: b.has_question_pct    },
    { label: 'Has ":" colon',       topPct: t.has_colon_pct,       bottomPct: b.has_colon_pct       },
    { label: 'Has brackets/parens', topPct: t.has_brackets_pct,    bottomPct: b.has_brackets_pct    },
    { label: 'Has "!" exclamation', topPct: t.has_exclamation_pct, bottomPct: b.has_exclamation_pct },
  ]

  return ALL_PATTERNS
    .filter(p => p.topPct > 0 || p.bottomPct > 0)
    .slice(0, 4)
    .map(p => ({
      ...p,
      topCount:    pctToCount(p.topPct, n),
      bottomCount: pctToCount(p.bottomPct, n),
    }))
})

// ── performer group totals ────────────────────────────────────────────────────

const groupTotals = (videos: VideoSummary[]) => {
  const vpd = videos.reduce((sum, v) => sum + v.views_per_day, 0)
  const views = videos.reduce((sum, v) => sum + v.view_count, 0)
  const revenueVideos = videos.filter(v => v.estimated_revenue != null)
  const revenue = revenueVideos.length ? revenueVideos.reduce((sum, v) => sum + (v.estimated_revenue ?? 0), 0) : null
  return { vpd, views, revenue }
}

// ── schedule bar chart helpers ────────────────────────────────────────────────

const DAYS = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']

// height of schedule bar normalized to 0–48px
const scheduleBarHeight = (day: string, group: 'top' | 'bottom') => {
  if (!data.value) return 0
  const counts = group === 'top' ? data.value.schedule_analysis.top : data.value.schedule_analysis.bottom
  const maxCount = Math.max(...Object.values(counts), 1)
  return Math.round((counts[day] ?? 0) / maxCount * 48)
}

// ── duration helpers ──────────────────────────────────────────────────────────

const DURATION_BUCKETS = ['< 3 min', '3–7 min', '8–9 min', '10–11 min', '12–15 min', '15+ min']

const durationBarWidth = (bucket: string, group: 'top' | 'bottom') => {
  if (!data.value) return 0
  const counts = group === 'top' ? data.value.duration_analysis.top : data.value.duration_analysis.bottom
  const total = Object.values(counts).reduce((a, b) => a + b, 0) || 1
  return Math.round((counts[bucket] ?? 0) / total * 100)
}
</script>

<template>
  <div class="min-h-screen text-white">

    <!-- nav -->
    <header class="border-b border-white/10 bg-black/30 backdrop-blur-sm px-6 py-4 flex items-center gap-4">
      <NuxtLink to="/dashboard" class="text-gray-400 hover:text-white transition text-sm flex items-center gap-1">
        ← Dashboard
      </NuxtLink>
      <span class="text-gray-600">|</span>
      <span class="text-sm font-bold tracking-tight">ViewPilot</span>
    </header>

    <main class="max-w-6xl mx-auto px-6 py-8 space-y-6">

      <!-- page title + controls -->
      <div class="flex flex-col md:flex-row md:items-end justify-between gap-4 bg-black/55 backdrop-blur-sm ring-1 ring-white/10 rounded-2xl px-6 py-5">
        <div>
          <h1 class="text-2xl font-bold tracking-tight">Autopsy</h1>
          <p class="text-sm text-gray-400 mt-1">Compare what your top videos do differently from your worst.</p>
        </div>

        <!-- controls -->
        <div class="flex flex-wrap items-center gap-4 text-sm">
          <!-- window size -->
          <div class="flex items-center gap-2">
            <span class="text-gray-400 text-xs uppercase tracking-wider">Window</span>
            <div class="flex gap-1">
              <button
                v-for="w in [20, 50, 100, 200]" :key="w"
                @click="windowSize = w"
                :class="windowSize === w
                  ? 'bg-indigo-600 text-white'
                  : 'bg-white/5 text-gray-400 hover:bg-white/10'"
                class="px-3 py-1 rounded-lg transition text-xs font-medium"
              >{{ w }}</button>
            </div>
          </div>

          <!-- tier -->
          <div class="flex items-center gap-2">
            <span class="text-gray-400 text-xs uppercase tracking-wider">Tier</span>
            <div class="flex gap-1">
              <button
                v-for="t in [5, 10, 20, 25]" :key="t"
                @click="tierPct = t"
                :class="tierPct === t
                  ? 'bg-indigo-600 text-white'
                  : 'bg-white/5 text-gray-400 hover:bg-white/10'"
                class="px-3 py-1 rounded-lg transition text-xs font-medium"
              >{{ t }}%</button>
            </div>
          </div>

          <button
            @click="fetchAutopsy"
            :disabled="loading"
            class="px-4 py-1.5 rounded-lg bg-indigo-600 hover:bg-indigo-500 disabled:opacity-50 transition text-xs font-medium"
          >
            {{ loading ? 'Loading...' : 'Compare' }}
          </button>
        </div>
      </div>

      <!-- error -->
      <div v-if="error" class="text-center text-red-400 py-20">{{ error }}</div>

      <!-- loading -->
      <div v-else-if="loading" class="text-center text-gray-500 py-20">Running the analysis...</div>

      <!-- results -->
      <template v-else-if="data">

        <!-- context banner -->
        <div class="bg-black/55 backdrop-blur-sm ring-1 ring-white/10 rounded-xl px-5 py-3 text-sm text-gray-400">
          Comparing your
          <span class="text-white font-medium">top {{ data.meta.tier_pct }}%</span>
          ({{ data.meta.tier_count }} videos) vs
          <span class="text-white font-medium">bottom {{ data.meta.tier_pct }}%</span>
          ({{ data.meta.tier_count }} videos) out of your last
          <span class="text-white font-medium">{{ data.meta.window_size }} videos</span>.
          Ranked by views per day.
        </div>

        <!-- ── hero summary ──────────────────────────────────────────────── -->
        <div class="grid grid-cols-2 md:grid-cols-4 gap-4">
          <div
            v-for="m in heroMetrics" :key="m.label"
            class="bg-white/15 ring-1 ring-white/25 rounded-2xl p-5"
          >
            <div class="text-xs uppercase tracking-widest text-gray-400 mb-4 text-center">{{ m.label }}</div>
            <div class="flex justify-around items-end mb-4">
              <div class="text-center">
                <div class="text-xl font-bold text-emerald-400">{{ m.topFmt }}</div>
                <div class="text-xs text-gray-500 mt-1">top {{ data.meta.tier_pct }}%</div>
              </div>
              <div class="text-gray-600 text-sm pb-3">vs</div>
              <div class="text-center">
                <div class="text-xl font-bold text-red-400">{{ m.bottomFmt }}</div>
                <div class="text-xs text-gray-500 mt-1">bottom {{ data.meta.tier_pct }}%</div>
              </div>
            </div>
            <div v-if="m.delta != null" class="text-center">
              <span :class="deltaBg(m.delta)" class="px-2.5 py-1 rounded-full text-xs font-bold">
                {{ fmtDelta(m.delta) }} difference
              </span>
            </div>
            <div v-else class="text-center text-xs text-gray-600">no data yet</div>
          </div>
        </div>

        <!-- ── all metrics table ─────────────────────────────────────────── -->
        <div class="bg-white/15 ring-1 ring-white/25 rounded-2xl overflow-hidden">
          <div class="px-6 py-4 border-b border-white/10">
            <h2 class="text-xs uppercase tracking-widest text-gray-400">All Metrics</h2>
          </div>
          <table class="w-full text-sm">
            <thead class="border-b border-white/5 text-xs uppercase tracking-wider text-gray-500">
              <tr>
                <th class="text-left px-6 py-3">Metric</th>
                <th class="px-6 py-3 text-right text-emerald-400/70">Top {{ data.meta.tier_pct }}%</th>
                <th class="px-6 py-3 text-right text-red-400/70">Bottom {{ data.meta.tier_pct }}%</th>
                <th class="px-6 py-3 text-right cursor-pointer hover:text-gray-300 select-none" @click="cycleMetricSort">
                  Difference {{ metricDeltaIcon }}
                </th>
              </tr>
            </thead>
            <tbody class="divide-y divide-white/5">
              <tr
                v-for="m in metricRows" :key="m.key"
                class="hover:bg-white/5 transition"
                :class="!m.hasData ? 'opacity-40' : ''"
              >
                <td class="px-6 py-3 text-gray-300">{{ m.label }}</td>
                <td class="px-6 py-3 text-right font-medium text-emerald-400">{{ m.topFmt }}</td>
                <td class="px-6 py-3 text-right text-red-400">{{ m.bottomFmt }}</td>
                <td class="px-6 py-3 text-right">
                  <span v-if="m.delta != null" :class="deltaBg(m.delta)" class="px-2 py-0.5 rounded-full text-xs font-semibold">
                    {{ fmtDelta(m.delta) }}
                  </span>
                  <span v-else class="text-gray-600 text-xs">no data</span>
                </td>
              </tr>
            </tbody>
          </table>
        </div>

        <!-- ── title DNA ─────────────────────────────────────────────────── -->
        <div class="bg-white/15 ring-1 ring-white/25 rounded-2xl p-6">
          <h2 class="text-xs uppercase tracking-widest text-gray-400 mb-6">Title DNA</h2>

          <!-- length + word count -->
          <div class="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
            <div class="bg-white/5 rounded-xl p-4 text-center">
              <div class="text-xs text-gray-500 mb-1">Avg title length</div>
              <div class="text-lg font-bold text-emerald-400">{{ data.title_analysis.top.avg_length }} <span class="text-xs font-normal text-gray-500">chars</span></div>
              <div class="text-sm text-red-400">{{ data.title_analysis.bottom.avg_length }} <span class="text-xs text-gray-500">chars</span></div>
            </div>
            <div class="bg-white/5 rounded-xl p-4 text-center">
              <div class="text-xs text-gray-500 mb-1">Avg word count</div>
              <div class="text-lg font-bold text-emerald-400">{{ data.title_analysis.top.avg_word_count }} <span class="text-xs font-normal text-gray-500">words</span></div>
              <div class="text-sm text-red-400">{{ data.title_analysis.bottom.avg_word_count }} <span class="text-xs text-gray-500">words</span></div>
            </div>
          </div>

          <!-- formatting patterns with percentage bars -->
          <div class="space-y-3 mb-6">
            <div class="grid grid-cols-3 gap-2 text-xs text-gray-500 uppercase tracking-wider mb-1">
              <span>Pattern</span>
              <span class="text-emerald-400/70 text-center">Top {{ data.meta.tier_pct }}%</span>
              <span class="text-red-400/70 text-center">Bottom {{ data.meta.tier_pct }}%</span>
            </div>
            <div
              v-for="f in titleFeatures" :key="f.label"
              class="grid grid-cols-3 gap-2 items-center py-1.5 border-t border-white/5"
            >
              <span class="text-sm text-gray-300">{{ f.label }}</span>
              <!-- top bar + count -->
              <div class="flex items-center gap-2">
                <div class="flex-1 bg-white/5 rounded-full h-2">
                  <div class="bg-emerald-500 rounded-full h-2 transition-all" :style="{ width: f.topPct + '%' }"></div>
                </div>
                <span class="text-emerald-400 text-xs font-medium whitespace-nowrap">{{ f.topCount }} of {{ data!.meta.tier_count }}</span>
              </div>
              <!-- bottom bar + count -->
              <div class="flex items-center gap-2">
                <div class="flex-1 bg-white/5 rounded-full h-2">
                  <div class="bg-red-500 rounded-full h-2 transition-all" :style="{ width: f.bottomPct + '%' }"></div>
                </div>
                <span class="text-red-400 text-xs font-medium whitespace-nowrap">{{ f.bottomCount }} of {{ data!.meta.tier_count }}</span>
              </div>
            </div>
          </div>

          <!-- common title words side by side -->
          <div class="grid grid-cols-2 gap-6">
            <div>
              <div class="text-xs text-emerald-400/70 uppercase tracking-wider mb-2">Words in top titles</div>
              <div class="flex flex-wrap gap-1.5">
                <span
                  v-for="w in data.title_analysis.top.top_words" :key="w.word"
                  class="px-2.5 py-1 rounded-full text-xs bg-emerald-500/15 text-emerald-300 ring-1 ring-emerald-500/25"
                >{{ w.word }}</span>
                <span v-if="!data.title_analysis.top.top_words?.length" class="text-gray-600 text-xs">—</span>
              </div>
            </div>
            <div>
              <div class="text-xs text-red-400/70 uppercase tracking-wider mb-2">Words in bottom titles</div>
              <div class="flex flex-wrap gap-1.5">
                <span
                  v-for="w in data.title_analysis.bottom.top_words" :key="w.word"
                  class="px-2.5 py-1 rounded-full text-xs bg-red-500/15 text-red-300 ring-1 ring-red-500/25"
                >{{ w.word }}</span>
                <span v-if="!data.title_analysis.bottom.top_words?.length" class="text-gray-600 text-xs">—</span>
              </div>
            </div>
          </div>
        </div>

        <!-- ── publishing schedule ────────────────────────────────────────── -->
        <div class="bg-white/15 ring-1 ring-white/25 rounded-2xl p-6">
          <div class="flex items-start justify-between mb-6">
            <h2 class="text-xs uppercase tracking-widest text-gray-400">Publishing Schedule</h2>
            <div class="flex gap-4 text-xs">
              <span v-if="data.schedule_analysis.best_day" class="text-emerald-400">
                Best day: <span class="font-semibold">{{ data.schedule_analysis.best_day }}</span>
              </span>
              <span v-if="data.schedule_analysis.worst_day" class="text-red-400">
                Weakest: <span class="font-semibold">{{ data.schedule_analysis.worst_day }}</span>
              </span>
            </div>
          </div>

          <!-- bar chart: top (emerald) vs bottom (red) per day -->
          <div class="flex gap-2 items-end">
            <div
              v-for="day in DAYS" :key="day"
              class="flex-1 flex flex-col items-center gap-2"
            >
              <!-- bars -->
              <div class="w-full flex gap-0.5 items-end" style="height: 52px">
                <div
                  class="flex-1 bg-emerald-500/60 rounded-t-sm transition-all"
                  :style="{ height: scheduleBarHeight(day, 'top') + 'px' }"
                ></div>
                <div
                  class="flex-1 bg-red-500/60 rounded-t-sm transition-all"
                  :style="{ height: scheduleBarHeight(day, 'bottom') + 'px' }"
                ></div>
              </div>
              <!-- counts -->
              <div class="text-center leading-tight">
                <div class="text-xs text-emerald-400">{{ data.schedule_analysis.top[day] ?? 0 }}</div>
                <div class="text-xs text-red-400">{{ data.schedule_analysis.bottom[day] ?? 0 }}</div>
              </div>
              <span class="text-xs text-gray-500">{{ day.slice(0, 3) }}</span>
            </div>
          </div>

          <!-- legend -->
          <div class="flex gap-4 mt-4 text-xs text-gray-500">
            <span class="flex items-center gap-1.5"><span class="w-3 h-3 rounded-sm bg-emerald-500/60 inline-block"></span>Top {{ data.meta.tier_pct }}% videos</span>
            <span class="flex items-center gap-1.5"><span class="w-3 h-3 rounded-sm bg-red-500/60 inline-block"></span>Bottom {{ data.meta.tier_pct }}% videos</span>
          </div>

          <!-- avg vpd by day -->
          <div class="mt-5 pt-4 border-t border-white/10">
            <div class="text-xs text-gray-500 mb-3">Avg views/day across all {{ data.meta.window_size }} videos by publish day</div>
            <div class="flex gap-2 flex-wrap">
              <div
                v-for="day in DAYS" :key="day"
                v-if="data.schedule_analysis.avg_vpd_by_day[day] != null"
                class="bg-white/5 rounded-lg px-3 py-2 text-center min-w-[72px]"
                :class="day === data.schedule_analysis.best_day ? 'ring-1 ring-emerald-500/50' : ''"
              >
                <div class="text-sm font-semibold">{{ fmtNum(data.schedule_analysis.avg_vpd_by_day[day]) }}</div>
                <div class="text-xs text-gray-500">{{ day.slice(0, 3) }}</div>
              </div>
            </div>
          </div>
        </div>

        <!-- ── duration sweet spot ────────────────────────────────────────── -->
        <div class="bg-white/15 ring-1 ring-white/25 rounded-2xl p-6">
          <div class="flex items-start justify-between mb-6">
            <h2 class="text-xs uppercase tracking-widest text-gray-400">Duration Sweet Spot</h2>
            <span v-if="data.duration_analysis.best_bucket" class="text-xs text-emerald-400">
              Best length: <span class="font-semibold">{{ data.duration_analysis.best_bucket }}</span>
            </span>
          </div>

          <!-- duration breakdown table -->
          <div class="space-y-2">
            <div class="grid grid-cols-4 gap-2 text-xs text-gray-500 uppercase tracking-wider mb-2">
              <span>Length</span>
              <span class="text-emerald-400/70">Top {{ data.meta.tier_pct }}%</span>
              <span class="text-red-400/70">Bottom {{ data.meta.tier_pct }}%</span>
              <span>Avg views/day</span>
            </div>
            <div
              v-for="bucket in DURATION_BUCKETS" :key="bucket"
              class="grid grid-cols-4 gap-2 items-center py-2 border-t border-white/5"
              :class="bucket === data.duration_analysis.best_bucket ? 'bg-emerald-500/5 rounded-lg px-2' : ''"
            >
              <span class="text-sm text-gray-300 flex items-center gap-1.5">
                <span v-if="bucket === data.duration_analysis.best_bucket" class="text-emerald-400 text-xs">★</span>
                {{ bucket }}
              </span>

              <!-- top bar -->
              <div class="flex items-center gap-1.5">
                <div class="w-20 bg-white/5 rounded-full h-1.5">
                  <div class="bg-emerald-500 rounded-full h-1.5" :style="{ width: durationBarWidth(bucket, 'top') + '%' }"></div>
                </div>
                <span class="text-xs text-emerald-400">{{ data.duration_analysis.top[bucket] ?? 0 }}</span>
              </div>

              <!-- bottom bar -->
              <div class="flex items-center gap-1.5">
                <div class="w-20 bg-white/5 rounded-full h-1.5">
                  <div class="bg-red-500 rounded-full h-1.5" :style="{ width: durationBarWidth(bucket, 'bottom') + '%' }"></div>
                </div>
                <span class="text-xs text-red-400">{{ data.duration_analysis.bottom[bucket] ?? 0 }}</span>
              </div>

              <span class="text-xs text-gray-400">
                {{ data.duration_analysis.avg_vpd_by_bucket[bucket] != null ? fmtNum(data.duration_analysis.avg_vpd_by_bucket[bucket]) : '—' }}
              </span>
            </div>
          </div>
        </div>

        <!-- ── tags ──────────────────────────────────────────────────────── -->
        <div class="bg-white/15 ring-1 ring-white/25 rounded-2xl p-6">
          <div class="flex items-center justify-between mb-6">
            <h2 class="text-xs uppercase tracking-widest text-gray-400">Tags</h2>
            <span v-if="data.tag_analysis.shared_count" class="text-xs text-gray-500">
              {{ data.tag_analysis.shared_count }} tag{{ data.tag_analysis.shared_count !== 1 ? 's' : '' }} shared by both groups — hidden
            </span>
          </div>
          <div class="grid grid-cols-2 gap-8">
            <div>
              <div class="flex items-center justify-between mb-3">
                <span class="text-xs text-emerald-400/70 uppercase tracking-wider">Top {{ data.meta.tier_pct }}%</span>
                <span class="text-xs text-gray-500">avg {{ data.tag_analysis.top.avg_count }} tags/video</span>
              </div>
              <div class="flex flex-wrap gap-1.5">
                <span
                  v-for="t in data.tag_analysis.top.top_tags" :key="t.tag"
                  class="px-2.5 py-1 rounded-full text-xs bg-emerald-500/15 text-emerald-300 ring-1 ring-emerald-500/25"
                >{{ t.tag }}</span>
                <span v-if="!data.tag_analysis.top.top_tags.length" class="text-gray-400 text-xs italic">no unique tags</span>
              </div>
            </div>
            <div>
              <div class="flex items-center justify-between mb-3">
                <span class="text-xs text-red-400/70 uppercase tracking-wider">Bottom {{ data.meta.tier_pct }}%</span>
                <span class="text-xs text-gray-500">avg {{ data.tag_analysis.bottom.avg_count }} tags/video</span>
              </div>
              <div class="flex flex-wrap gap-1.5">
                <span
                  v-for="t in data.tag_analysis.bottom.top_tags" :key="t.tag"
                  class="px-2.5 py-1 rounded-full text-xs bg-red-500/15 text-red-300 ring-1 ring-red-500/25"
                >{{ t.tag }}</span>
                <span v-if="!data.tag_analysis.bottom.top_tags.length" class="text-gray-400 text-xs italic">no unique tags</span>
              </div>
            </div>
          </div>
        </div>

        <!-- ── top performers ─────────────────────────────────────────────── -->
        <div class="bg-white/15 ring-1 ring-white/25 rounded-2xl overflow-hidden">
          <div class="px-6 py-4 border-b border-white/10 flex items-center justify-between">
            <h2 class="text-xs uppercase tracking-widest text-gray-400">Top Performers</h2>
            <span class="text-xs text-gray-500">{{ data.meta.tier_count }} videos — top {{ data.meta.tier_pct }}%</span>
          </div>
          <div class="divide-y divide-white/5">
            <div
              v-for="(v, i) in data.top_videos" :key="v.id"
              class="flex items-center gap-4 px-4 py-3 hover:bg-white/5 transition"
            >
              <span class="text-xs text-emerald-400 font-bold w-4 shrink-0">{{ i + 1 }}</span>
              <img v-if="v.thumbnail_url" :src="v.thumbnail_url" class="h-9 w-14 rounded object-cover shrink-0" />
              <NuxtLink :to="`/video/${v.id}`" class="flex-1 min-w-0 text-sm text-gray-100 hover:text-white hover:underline truncate">
                {{ v.title }}
              </NuxtLink>
              <div class="flex text-xs text-right shrink-0">
                <div class="w-20"><div class="text-emerald-400 font-medium">{{ fmtNum(v.views_per_day) }}/day</div><div class="text-gray-500">views/day</div></div>
                <div class="w-20"><div class="text-emerald-400 font-medium">{{ fmtNumFull(v.view_count) }}</div><div class="text-gray-500">total views</div></div>
                <div class="w-16"><div class="text-emerald-400 font-medium">{{ v.ctr != null ? v.ctr.toFixed(1) + '%' : '—' }}</div><div class="text-gray-500">CTR</div></div>
                <div class="w-16"><div class="text-emerald-400 font-medium">{{ v.avg_view_duration != null ? fmtDuration(v.avg_view_duration) : '—' }}</div><div class="text-gray-500">watch</div></div>
                <div class="w-16"><div class="text-emerald-400 font-medium">{{ v.rpm != null ? fmtMoney(v.rpm) : '—' }}</div><div class="text-gray-500">RPM</div></div>
                <div class="w-20"><div class="text-emerald-400 font-medium">{{ v.estimated_revenue != null ? fmtMoney(v.estimated_revenue) : '—' }}</div><div class="text-gray-500">revenue</div></div>
                <div class="w-24 text-gray-500"><div>{{ fmtDate(v.published_at) }}</div></div>
              </div>
            </div>
          </div>
          <!-- totals footer -->
          <div class="border-t border-white/10 px-4 py-3 flex items-center justify-between text-xs text-gray-400 bg-white/5">
            <span class="font-medium text-gray-300">Group totals</span>
            <div class="flex items-center gap-6">
              <span>Views/day: <span class="text-emerald-400 font-medium">{{ fmtNum(Math.round(groupTotals(data.top_videos).vpd)) }}</span></span>
              <span>Total Views: <span class="text-emerald-400 font-medium">{{ fmtNumFull(groupTotals(data.top_videos).views) }}</span></span>
              <span v-if="groupTotals(data.top_videos).revenue != null">Total Revenue: <span class="text-emerald-400 font-medium">{{ fmtMoney(groupTotals(data.top_videos).revenue) }}</span></span>
            </div>
          </div>
        </div>

        <!-- ── bottom performers ──────────────────────────────────────────── -->
        <div class="bg-white/15 ring-1 ring-white/25 rounded-2xl overflow-hidden">
          <div class="px-6 py-4 border-b border-white/10 flex items-center justify-between">
            <h2 class="text-xs uppercase tracking-widest text-gray-400">Bottom Performers</h2>
            <span class="text-xs text-gray-500">{{ data.meta.tier_count }} videos — bottom {{ data.meta.tier_pct }}%</span>
          </div>
          <div class="divide-y divide-white/5">
            <div
              v-for="(v, i) in [...data.bottom_videos].reverse()" :key="v.id"
              class="flex items-center gap-4 px-4 py-3 hover:bg-white/5 transition"
            >
              <span class="text-xs text-red-400 font-bold w-4 shrink-0">{{ data.meta.window_size - i }}</span>
              <img v-if="v.thumbnail_url" :src="v.thumbnail_url" class="h-9 w-14 rounded object-cover shrink-0" />
              <NuxtLink :to="`/video/${v.id}`" class="flex-1 min-w-0 text-sm text-gray-100 hover:text-white hover:underline truncate">
                {{ v.title }}
              </NuxtLink>
              <div class="flex text-xs text-right shrink-0">
                <div class="w-20"><div class="text-red-400 font-medium">{{ fmtNum(v.views_per_day) }}/day</div><div class="text-gray-500">views/day</div></div>
                <div class="w-20"><div class="text-red-400 font-medium">{{ fmtNumFull(v.view_count) }}</div><div class="text-gray-500">total views</div></div>
                <div class="w-16"><div class="text-red-400 font-medium">{{ v.ctr != null ? v.ctr.toFixed(1) + '%' : '—' }}</div><div class="text-gray-500">CTR</div></div>
                <div class="w-16"><div class="text-red-400 font-medium">{{ v.avg_view_duration != null ? fmtDuration(v.avg_view_duration) : '—' }}</div><div class="text-gray-500">watch</div></div>
                <div class="w-16"><div class="text-red-400 font-medium">{{ v.rpm != null ? fmtMoney(v.rpm) : '—' }}</div><div class="text-gray-500">RPM</div></div>
                <div class="w-20"><div class="text-red-400 font-medium">{{ v.estimated_revenue != null ? fmtMoney(v.estimated_revenue) : '—' }}</div><div class="text-gray-500">revenue</div></div>
                <div class="w-24 text-gray-500"><div>{{ fmtDate(v.published_at) }}</div></div>
              </div>
            </div>
          </div>
          <!-- totals footer -->
          <div class="border-t border-white/10 px-4 py-3 flex items-center justify-between text-xs text-gray-400 bg-white/5">
            <span class="font-medium text-gray-300">Group totals</span>
            <div class="flex items-center gap-6">
              <span>Views/day: <span class="text-red-400 font-medium">{{ fmtNum(Math.round(groupTotals(data.bottom_videos).vpd)) }}</span></span>
              <span>Total Views: <span class="text-red-400 font-medium">{{ fmtNumFull(groupTotals(data.bottom_videos).views) }}</span></span>
              <span v-if="groupTotals(data.bottom_videos).revenue != null">Total Revenue: <span class="text-red-400 font-medium">{{ fmtMoney(groupTotals(data.bottom_videos).revenue) }}</span></span>
            </div>
          </div>
        </div>

      </template>

      <!-- empty state before first load -->
      <div v-else class="text-center text-gray-500 py-20">Select a window and tier above, then click Compare.</div>

    </main>
  </div>
</template>
