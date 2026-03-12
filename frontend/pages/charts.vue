<script setup lang="ts">
definePageMeta({ middleware: 'auth' })

const api = useApi()
const { showRevenue, toggleRevenue } = useRevenue()

// ─── metric definitions ────────────────────────────────────────────────────
const METRICS_CONFIG: Record<string, {
  label: string
  color: string
  revenueGated: boolean
  fmt: (v: number | null) => string
  fmtShort: (v: number | null) => string
}> = {
  views: {
    label: 'Views',
    color: '#6366f1',
    revenueGated: false,
    fmt: v => v == null ? '—' : fmtBig(v),
    fmtShort: v => v == null ? '—' : fmtBig(v),
  },
  watch_time_minutes: {
    label: 'Watch Time',
    color: '#a855f7',
    revenueGated: false,
    fmt: v => v == null ? '—' : fmtBig(v) + ' min',
    fmtShort: v => v == null ? '—' : fmtBig(v),
  },
  impressions: {
    label: 'Impressions',
    color: '#0ea5e9',
    revenueGated: false,
    fmt: v => v == null ? '—' : fmtBig(v),
    fmtShort: v => v == null ? '—' : fmtBig(v),
  },
  ctr: {
    label: 'CTR',
    color: '#10b981',
    revenueGated: false,
    fmt: v => v == null ? '—' : v.toFixed(2) + '%',
    fmtShort: v => v == null ? '—' : v.toFixed(2) + '%',
  },
  likes: {
    label: 'Likes',
    color: '#f472b6',
    revenueGated: false,
    fmt: v => v == null ? '—' : fmtBig(v),
    fmtShort: v => v == null ? '—' : fmtBig(v),
  },
  comments: {
    label: 'Comments',
    color: '#fb923c',
    revenueGated: false,
    fmt: v => v == null ? '—' : fmtBig(v),
    fmtShort: v => v == null ? '—' : fmtBig(v),
  },
  subscribers_gained: {
    label: 'Subscribers',
    color: '#facc15',
    revenueGated: false,
    fmt: v => v == null ? '—' : fmtBig(v),
    fmtShort: v => v == null ? '—' : fmtBig(v),
  },
  revenue: {
    label: 'Revenue',
    color: '#f87171',
    revenueGated: true,
    fmt: v => v == null ? '—' : '$' + fmtBig(v),
    fmtShort: v => v == null ? '—' : '$' + fmtBig(v),
  },
  rpm: {
    label: 'RPM',
    color: '#fb7185',
    revenueGated: true,
    fmt: v => v == null ? '—' : '$' + (v as number).toFixed(2),
    fmtShort: v => v == null ? '—' : '$' + (v as number).toFixed(2),
  },
  avg_view_duration: {
    label: 'Avg Watch Time',
    color: '#38bdf8',
    revenueGated: false,
    fmt: v => v == null ? '—' : fmtSeconds(v as number),
    fmtShort: v => v == null ? '—' : fmtSeconds(v as number),
  },
}

function fmtBig(v: number): string {
  if (v >= 1_000_000_000) return (v / 1_000_000_000).toFixed(1).replace(/\.0$/, '') + 'B'
  if (v >= 1_000_000)     return (v / 1_000_000).toFixed(1).replace(/\.0$/, '') + 'M'
  if (v >= 1_000)         return (v / 1_000).toFixed(1).replace(/\.0$/, '') + 'K'
  return Math.round(v).toLocaleString()
}

function fmtSeconds(s: number): string {
  const h = Math.floor(s / 3600)
  const m = Math.floor((s % 3600) / 60)
  const sec = Math.floor(s % 60)
  if (h > 0) return `${h}:${String(m).padStart(2, '0')}:${String(sec).padStart(2, '0')}`
  return `${m}:${String(sec).padStart(2, '0')}`
}

function fmtDate(ts: number): string {
  return new Date(ts).toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' })
}

// smart y-axis label formatter — no trailing .0, no excess zeros
function fmtAxis(v: number | null, key: string): string {
  if (v == null || isNaN(v as number)) return ''
  const n = v as number
  if (key === 'ctr') return n.toFixed(1) + '%'
  if (key === 'rpm') return '$' + n.toFixed(0)
  if (key === 'revenue') {
    if (n >= 1_000_000) return '$' + (n / 1_000_000).toFixed(1).replace(/\.0$/, '') + 'M'
    if (n >= 1_000)     return '$' + (n / 1_000).toFixed(0) + 'K'
    return '$' + n.toFixed(0)
  }
  if (key === 'avg_view_duration') return fmtSeconds(n)
  if (n >= 1_000_000_000) return (n / 1_000_000_000).toFixed(1).replace(/\.0$/, '') + 'B'
  if (n >= 1_000_000)     return (n / 1_000_000).toFixed(1).replace(/\.0$/, '') + 'M'
  if (n >= 1_000)         return (n / 1_000).toFixed(1).replace(/\.0$/, '') + 'K'
  if (n === 0)            return '0'
  return Math.round(n).toString()
}

// ─── state ────────────────────────────────────────────────────────────────

interface ChartData {
  dates: string[]
  metrics: Record<string, (number | null)[]>
  date_range: { min: string; max: string } | null
  granularity: string
}

interface VideoItem {
  ts: number
  title: string
  youtube_video_id: string
}

const loading = ref(false)
const chartData = ref<ChartData | null>(null)
const channel = ref<{ id: string; title: string } | null>(null)
const videoList = ref<VideoItem[]>([])

const selectedMetrics = ref<string[]>(['views'])
const granularity = ref<'daily' | 'weekly' | 'monthly'>('daily')
const chartType = ref<'area' | 'line'>('area')
const normalize = ref(false)
const activeQuickRange = ref('90D')

// tracks the currently visible date range
const visibleMin = ref<number | undefined>(undefined)
const visibleMax = ref<number | undefined>(undefined)

// custom date range picker
const showCustomRange = ref(false)
const customDateFrom = ref('')
const customDateTo = ref('')

// pre-fill the date inputs whenever the picker opens
watch(showCustomRange, (open) => {
  if (open && visibleMin.value && visibleMax.value) {
    customDateFrom.value = new Date(visibleMin.value).toISOString().split('T')[0]
    customDateTo.value   = new Date(visibleMax.value).toISOString().split('T')[0]
  }
})

// ─── content range ────────────────────────────────────────────────────────
// clips the scrubber to the stretch where there's actually non-zero views data,
// so the timeline doesn't show a big dead zone at the start/end
const contentRange = computed(() => {
  if (!chartData.value?.dates?.length) return null
  const { dates, metrics } = chartData.value
  const timestamps = dates.map(d => new Date(d + 'T00:00:00').getTime())
  const views = metrics.views ?? []

  let firstIdx = timestamps.findIndex((_, i) => (views[i] ?? 0) > 0)
  if (firstIdx === -1) firstIdx = 0

  let lastIdx = -1
  for (let i = timestamps.length - 1; i >= 0; i--) {
    if ((views[i] ?? 0) > 0) { lastIdx = i; break }
  }
  if (lastIdx === -1) lastIdx = timestamps.length - 1

  return { min: timestamps[firstIdx], max: timestamps[lastIdx] }
})

// ─── visible metrics ──────────────────────────────────────────────────────
const visibleMetricEntries = computed(() =>
  Object.entries(METRICS_CONFIG).filter(([, cfg]) => !cfg.revenueGated || showRevenue.value)
)

watch(showRevenue, (on) => {
  if (!on) {
    selectedMetrics.value = selectedMetrics.value.filter(k => !METRICS_CONFIG[k].revenueGated)
    if (!selectedMetrics.value.length) selectedMetrics.value = ['views']
  }
})

// ─── quick range config ───────────────────────────────────────────────────
const quickRanges = [
  { label: '7D',  days: 7 },
  { label: '30D', days: 30 },
  { label: '90D', days: 90 },
  { label: '6M',  days: 180 },
  { label: '1Y',  days: 365 },
  { label: 'All', days: null as number | null },
]

const granularities = [
  { value: 'daily',   label: 'Daily' },
  { value: 'weekly',  label: 'Weekly' },
  { value: 'monthly', label: 'Monthly' },
]

// ─── data loading ─────────────────────────────────────────────────────────

onMounted(async () => {
  try {
    const channels = await api<{ id: string; title: string }[]>('/api/v1/channels')
    if (channels.length) {
      channel.value = channels[0]
      // load chart data and video list in parallel
      await Promise.all([
        fetchChartData(),
        fetchVideoList(channels[0].id),
      ])
    }
  } catch { /* handled by empty state */ }
})

async function fetchChartData() {
  if (!channel.value) return
  loading.value = true
  try {
    chartData.value = await api<ChartData>(
      `/api/v1/charts/channel?channel_id=${channel.value.id}&granularity=${granularity.value}`
    )
    await nextTick()
    const current = quickRanges.find(r => r.label === activeQuickRange.value)
    applyQuickRange(current?.days ?? 90)
  } catch { chartData.value = null }
  finally { loading.value = false }
}

async function fetchVideoList(channelId: string) {
  try {
    const res = await api<{ items: { title: string; published_at: string; youtube_video_id: string }[] }>(
      `/api/v1/videos?channel_id=${channelId}&per_page=500&sort_by=published_at&order=asc`
    )
    videoList.value = (res.items ?? []).map(v => ({
      ts: new Date(v.published_at + 'T00:00:00').getTime(),
      title: v.title,
      youtube_video_id: v.youtube_video_id,
    }))
  } catch {}
}

async function setGranularity(g: 'daily' | 'weekly' | 'monthly') {
  if (g === granularity.value) return
  granularity.value = g
  await fetchChartData()
}

function toggleMetric(key: string) {
  const idx = selectedMetrics.value.indexOf(key)
  if (idx >= 0) {
    if (selectedMetrics.value.length === 1) return
    selectedMetrics.value = selectedMetrics.value.filter(k => k !== key)
  } else {
    selectedMetrics.value = [...selectedMetrics.value, key]
  }
}

// ─── quick range + custom range ────────────────────────────────────────────

function applyQuickRange(days: number | null) {
  if (!chartData.value?.dates?.length) return

  // use content range bounds (non-zero views) so we don't zoom to dead zones
  const cr = contentRange.value
  if (!cr) return

  const dataMax = cr.max
  const dataMin = cr.min

  if (days == null) {
    visibleMin.value = dataMin
    visibleMax.value = dataMax
    activeQuickRange.value = 'All'
  } else {
    visibleMin.value = Math.max(dataMin, dataMax - days * 86_400_000)
    visibleMax.value = dataMax
    activeQuickRange.value = quickRanges.find(r => r.days === days)?.label ?? activeQuickRange.value
  }
  showCustomRange.value = false
}

function applyCustomRange() {
  if (!customDateFrom.value || !customDateTo.value) return
  const from = new Date(customDateFrom.value + 'T00:00:00').getTime()
  const to   = new Date(customDateTo.value   + 'T23:59:59').getTime()
  if (isNaN(from) || isNaN(to) || from >= to) return
  visibleMin.value = from
  visibleMax.value = to
  activeQuickRange.value = 'Custom'
  showCustomRange.value = false
}

// ─── series computation ────────────────────────────────────────────────────

const rawSeries = computed(() => {
  if (!chartData.value?.dates?.length) return []
  const { dates, metrics } = chartData.value
  const timestamps = dates.map(d => new Date(d + 'T00:00:00').getTime())

  return selectedMetrics.value.map(key => ({
    name: METRICS_CONFIG[key].label,
    data: timestamps.map((t, i) => [t, metrics[key]?.[i] ?? null] as [number, number | null]),
  }))
})

const displaySeries = computed(() => {
  if (!normalize.value) return rawSeries.value
  return rawSeries.value.map(series => {
    const firstVal = series.data.find(([, v]) => v != null && (v as number) > 0)?.[1] ?? 1
    return {
      ...series,
      data: series.data.map(([t, v]) => [
        t,
        v != null ? Math.round((v as number) / (firstVal as number) * 10000) / 100 : null,
      ] as [number, number | null]),
    }
  })
})

const brushSeries = computed(() => {
  if (!rawSeries.value.length) return []
  return [{ ...rawSeries.value[0], name: rawSeries.value[0].name }]
})

const chartColors = computed(() => selectedMetrics.value.map(k => METRICS_CONFIG[k].color))

// ─── y-axis config ─────────────────────────────────────────────────────────
const yAxisConfig = computed(() => {
  if (normalize.value) {
    return [{
      tickAmount: 6,
      forceNiceScale: true,
      labels: {
        style: { colors: '#94a3b8', fontSize: '11px' },
        formatter: (v: number) => v != null ? Math.round(v) + '%' : '',
      },
      title: { text: '% from start', style: { color: '#64748b', fontSize: '11px' } },
      min: 0,
    }]
  }

  return selectedMetrics.value.map((key, i) => {
    const cfg = METRICS_CONFIG[key]
    return {
      seriesName: cfg.label,
      opposite: i === 1,
      show: i < 2,
      tickAmount: 6,
      forceNiceScale: true,
      decimalsInFloat: 0,
      labels: {
        style: { colors: cfg.color, fontSize: '11px' },
        // use fmtAxis so we get "1.2M" not "1200000", "3.5%" not "3.5000001%", etc.
        formatter: (v: number) => fmtAxis(v, key),
      },
      ...(i < 2 ? {
        title: { text: cfg.label, style: { color: cfg.color, fontSize: '11px' } },
      } : {}),
    }
  })
})

// ─── video annotations ─────────────────────────────────────────────────────
// subtle vertical lines at every video upload date so you can see at a glance
// when content was published — full info shows in the tooltip on hover
const videoAnnotationsConfig = computed(() =>
  videoList.value.map(v => ({
    x: v.ts,
    borderColor: '#1e293b',
    borderWidth: 1,
    strokeDashArray: 0,
    opacity: 0.8,
  }))
)

// ─── main chart options ────────────────────────────────────────────────────
const mainChartOptions = computed(() => ({
  chart: {
    id: 'main-chart',
    type: chartType.value,
    background: 'transparent',
    foreColor: '#94a3b8',
    toolbar: {
      show: true,
      autoSelected: 'zoom',
      tools: { download: false, selection: true, zoom: true, zoomin: true, zoomout: true, pan: true, reset: true },
    },
    zoom: { enabled: true, type: 'x' },
    animations: {
      enabled: true,
      speed: 300,
      animateGradually: { enabled: false },
      dynamicAnimation: { enabled: true, speed: 200 },
    },
    fontFamily: 'inherit',
  },
  theme: { mode: 'dark' },
  colors: chartColors.value,
  stroke: {
    curve: 'smooth' as const,
    width: selectedMetrics.value.length > 1 ? 2 : 2.5,
  },
  fill: chartType.value === 'area' ? {
    type: 'gradient',
    gradient: { type: 'vertical', shadeIntensity: 0.4, opacityFrom: 0.25, opacityTo: 0.02, stops: [0, 95, 100] },
  } : { opacity: 1 },
  dataLabels: { enabled: false },
  markers: { size: 0, hover: { size: 5 }, strokeWidth: 2, strokeOpacity: 1 },
  xaxis: {
    type: 'datetime' as const,
    labels: {
      style: { colors: '#64748b', fontSize: '11px' },
      datetimeUTC: false,
      datetimeFormatter: { year: 'yyyy', month: "MMM 'yy", day: 'dd MMM', hour: 'HH:mm' },
    },
    axisBorder: { show: false },
    axisTicks: { show: false },
    crosshairs: { show: true, stroke: { color: '#475569', width: 1, dashArray: 4 } },
    tooltip: { enabled: false },
    ...(visibleMin.value != null && visibleMax.value != null
      ? { min: visibleMin.value, max: visibleMax.value }
      : {}),
  },
  yaxis: yAxisConfig.value,
  grid: {
    borderColor: '#1e293b',
    strokeDashArray: 4,
    xaxis: { lines: { show: false } },
    yaxis: { lines: { show: true } },
    padding: { top: 10, right: selectedMetrics.value.length > 1 ? 20 : 10 },
  },
  // video upload annotations — thin vertical marks on the chart
  annotations: { xaxis: videoAnnotationsConfig.value },
  // custom tooltip so we can show: formatted metric values + any videos uploaded that day
  tooltip: {
    custom: ({ series, dataPointIndex, w }: any) => {
      const ts: number = w.globals.seriesX[0]?.[dataPointIndex]
      if (ts == null) return ''

      const dateLabel = new Date(ts).toLocaleDateString('en-US', {
        weekday: 'short', month: 'short', day: 'numeric', year: 'numeric',
      })

      const metricRows = selectedMetrics.value.map((key, i) => {
        const raw = series[i]?.[dataPointIndex]
        if (raw == null) return ''
        const display = normalize.value
          ? raw.toFixed(1) + '% from start'
          : METRICS_CONFIG[key].fmt(raw)
        const c = METRICS_CONFIG[key].color
        const lbl = METRICS_CONFIG[key].label
        return `<div style="display:flex;align-items:center;gap:6px;padding:2px 0">
          <span style="width:8px;height:8px;border-radius:50%;background:${c};flex-shrink:0"></span>
          <span style="color:#94a3b8;font-size:11px">${lbl}</span>
          <span style="color:${c};font-weight:600;font-size:11px;margin-left:auto;padding-left:12px">${display}</span>
        </div>`
      }).filter(Boolean).join('')

      // show any videos uploaded within ~1.5 days of the hovered date
      const nearby = videoList.value.filter(v => Math.abs(v.ts - ts) < 86_400_000 * 1.5)
      const videoSection = nearby.length
        ? `<div style="margin-top:8px;padding-top:8px;border-top:1px solid #1e293b">
            <div style="color:#475569;font-size:10px;font-weight:600;text-transform:uppercase;letter-spacing:0.04em;margin-bottom:4px">Uploaded</div>
            ${nearby.slice(0, 5).map(v =>
              `<div style="color:#94a3b8;font-size:11px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;max-width:240px;padding:1px 0">▶ ${v.title}</div>`
            ).join('')}
          </div>`
        : ''

      return `<div style="background:#0f172a;border:1px solid #1e293b;border-radius:10px;padding:10px 14px;min-width:160px;max-width:260px;font-family:inherit;box-shadow:0 4px 20px rgba(0,0,0,0.6)">
        <div style="color:#64748b;font-size:10px;font-weight:600;text-transform:uppercase;letter-spacing:0.04em;margin-bottom:8px">${dateLabel}</div>
        ${metricRows}
        ${videoSection}
      </div>`
    },
  },
  legend: {
    show: selectedMetrics.value.length > 1,
    position: 'top' as const,
    horizontalAlign: 'left' as const,
    offsetY: 4,
    labels: { colors: '#94a3b8' },
    markers: { width: 10, height: 10, radius: 10, strokeWidth: 0 },
    itemMargin: { horizontal: 14 },
    fontSize: '12px',
  },
  noData: { text: 'No analytics data yet', style: { color: '#64748b', fontSize: '13px' } },
}))

// ─── brush chart options ───────────────────────────────────────────────────
const brushChartOptions = computed(() => {
  // clip to actual content (non-zero views) so the scrubber doesn't show dead zones
  const cr = contentRange.value
  const dataMin = cr?.min ?? Date.now() - 90 * 86_400_000
  const dataMax = cr?.max ?? Date.now()

  const selMin = visibleMin.value ?? Math.max(dataMin, dataMax - 90 * 86_400_000)
  const selMax = visibleMax.value ?? dataMax

  return {
    chart: {
      id: 'brush-chart',
      type: 'area',
      background: 'transparent',
      foreColor: '#475569',
      brush: { target: 'main-chart', enabled: true },
      selection: {
        enabled: true,
        fill: { color: '#6366f1', opacity: 0.12 },
        stroke: { width: 1, color: '#6366f1', opacity: 0.6, dashArray: 0 },
        xaxis: { min: selMin, max: selMax },
      },
      events: {
        selection: (_ctx: unknown, { xaxis }: { xaxis: { min: number; max: number } }) => {
          visibleMin.value = xaxis.min
          visibleMax.value = xaxis.max
          activeQuickRange.value = ''
        },
      },
      animations: { enabled: false },
      toolbar: { show: false },
      zoom: { enabled: false },
      fontFamily: 'inherit',
    },
    theme: { mode: 'dark' },
    colors: [chartColors.value[0] ?? '#6366f1'],
    stroke: { width: 1.5, curve: 'smooth' as const },
    fill: { type: 'solid', opacity: 0.06 },
    dataLabels: { enabled: false },
    markers: { size: 0 },
    xaxis: {
      type: 'datetime' as const,
      // clip the scrubber's visible range to where content actually exists
      min: dataMin,
      max: dataMax,
      labels: {
        style: { colors: '#334155', fontSize: '10px' },
        datetimeUTC: false,
        datetimeFormatter: { year: 'yyyy', month: "MMM 'yy", day: 'dd MMM' },
      },
      axisBorder: { show: false },
      axisTicks: { show: false },
      tooltip: { enabled: false },
    },
    yaxis: { show: false, min: 0 },
    grid: {
      borderColor: 'transparent',
      padding: { top: 0, right: 0, bottom: 0, left: 0 },
      xaxis: { lines: { show: false } },
      yaxis: { lines: { show: false } },
    },
    tooltip: { enabled: false },
  }
})

// ─── summary totals — filtered to visible window ────────────────────────────
const metricTotals = computed(() => {
  if (!chartData.value?.metrics || !chartData.value?.dates?.length) {
    return {} as Record<string, number | null>
  }

  const { dates, metrics } = chartData.value
  const timestamps = dates.map(d => new Date(d + 'T00:00:00').getTime())
  const min = visibleMin.value
  const max = visibleMax.value

  const visibleIdx = timestamps.reduce<number[]>((acc, t, i) => {
    if ((min == null || t >= min - 1) && (max == null || t <= max + 1)) acc.push(i)
    return acc
  }, [])

  const out: Record<string, number | null> = {}
  for (const key of selectedMetrics.value) {
    const vals = visibleIdx.map(i => metrics[key]?.[i]).filter((v): v is number => v != null)
    if (!vals.length) { out[key] = null; continue }
    if (key === 'ctr' || key === 'rpm' || key === 'avg_view_duration') {
      out[key] = vals.reduce((a, b) => a + b, 0) / vals.length
    } else {
      out[key] = vals.reduce((a, b) => a + b, 0)
    }
  }
  return out
})

// ─── visible date range label ──────────────────────────────────────────────
const visibleRangeLabel = computed(() => {
  if (visibleMin.value != null && visibleMax.value != null) {
    return `${fmtDate(visibleMin.value)} → ${fmtDate(visibleMax.value)}`
  }
  const dr = chartData.value?.date_range
  return dr ? `${dr.min} → ${dr.max}` : ''
})
</script>

<template>
  <div class="min-h-screen bg-slate-950 text-white">

    <!-- nav ──────────────────────────────────────────────────────────────── -->
    <nav class="sticky top-0 z-50 bg-slate-950/80 backdrop-blur border-b border-white/5 px-4 py-3">
      <div class="max-w-7xl mx-auto flex items-center justify-between gap-4 min-w-0">
        <div class="flex items-center gap-4 min-w-0 overflow-hidden">
          <NuxtLink to="/dashboard" class="text-slate-400 hover:text-white text-sm transition-colors whitespace-nowrap">
            ← Dashboard
          </NuxtLink>
          <span class="text-slate-700 hidden sm:block">|</span>
          <h1 class="text-white font-semibold hidden sm:block">Charts</h1>
          <NuxtLink to="/autopsy" class="text-slate-400 hover:text-white text-sm transition-colors whitespace-nowrap hidden sm:block">Autopsy</NuxtLink>
        </div>

        <div class="flex items-center gap-3 flex-shrink-0">
          <label class="flex items-center gap-2 cursor-pointer select-none">
            <span class="text-sm text-gray-400 whitespace-nowrap">Revenue</span>
            <button
              @click="toggleRevenue"
              :class="['relative flex-shrink-0 w-10 h-5 rounded-full transition-colors duration-200', showRevenue ? 'bg-red-500' : 'bg-slate-700']"
            >
              <span :class="['absolute top-0.5 w-4 h-4 bg-white rounded-full shadow transition-transform duration-200', showRevenue ? 'translate-x-5' : 'translate-x-0.5']" />
            </button>
          </label>
        </div>
      </div>
    </nav>

    <div class="max-w-7xl mx-auto px-4 sm:px-6 py-5">

      <!-- controls row ──────────────────────────────────────────────────── -->
      <div class="flex flex-wrap items-center gap-2 mb-2">

        <!-- granularity -->
        <div class="flex items-center gap-0.5 bg-slate-900 border border-white/5 rounded-lg p-0.5">
          <button
            v-for="g in granularities"
            :key="g.value"
            @click="setGranularity(g.value as 'daily' | 'weekly' | 'monthly')"
            :class="['px-3 h-7 text-xs font-medium rounded-md transition-all whitespace-nowrap',
              granularity === g.value ? 'bg-slate-700 text-white shadow' : 'text-slate-500 hover:text-white']"
          >{{ g.label }}</button>
        </div>

        <!-- chart type -->
        <div class="flex items-center gap-0.5 bg-slate-900 border border-white/5 rounded-lg p-0.5">
          <button
            @click="chartType = 'area'"
            :class="['px-3 h-7 text-xs font-medium rounded-md transition-all',
              chartType === 'area' ? 'bg-slate-700 text-white shadow' : 'text-slate-500 hover:text-white']"
          >Area</button>
          <button
            @click="chartType = 'line'"
            :class="['px-3 h-7 text-xs font-medium rounded-md transition-all',
              chartType === 'line' ? 'bg-slate-700 text-white shadow' : 'text-slate-500 hover:text-white']"
          >Line</button>
        </div>

        <!-- normalize -->
        <button
          @click="normalize = !normalize"
          :class="['px-3 h-7 text-xs font-medium rounded-lg border transition-all',
            normalize
              ? 'bg-indigo-600/20 border-indigo-500/60 text-indigo-300'
              : 'bg-slate-900 border-white/5 text-slate-500 hover:text-white hover:border-slate-600']"
        >Normalize</button>

        <span class="text-slate-800 hidden sm:block">|</span>

        <!-- quick range buttons -->
        <div class="flex items-center gap-0.5 bg-slate-900 border border-white/5 rounded-lg p-0.5">
          <button
            v-for="r in quickRanges"
            :key="r.label"
            @click="applyQuickRange(r.days)"
            :class="['px-2.5 h-7 text-xs font-medium rounded-md transition-all',
              activeQuickRange === r.label ? 'bg-slate-700 text-white shadow' : 'text-slate-500 hover:text-white']"
          >{{ r.label }}</button>
        </div>

        <!-- custom date range toggle -->
        <button
          @click="showCustomRange = !showCustomRange; if (!showCustomRange && activeQuickRange === 'Custom') activeQuickRange = ''"
          :class="['px-3 h-7 text-xs font-medium rounded-lg border transition-all',
            activeQuickRange === 'Custom' || showCustomRange
              ? 'bg-indigo-600/20 border-indigo-500/60 text-indigo-300'
              : 'bg-slate-900 border-white/5 text-slate-500 hover:text-white hover:border-slate-600']"
        >Custom range</button>
      </div>

      <!-- custom date range inputs ─────────────────────────────────────── -->
      <div
        v-if="showCustomRange"
        class="flex items-center gap-2 mb-3 pl-1 animate-fade-in"
      >
        <span class="text-xs text-slate-500">From</span>
        <input
          type="date"
          v-model="customDateFrom"
          class="bg-slate-900 border border-slate-700 text-slate-300 text-xs rounded-lg px-3 py-1.5 outline-none focus:border-indigo-500 transition-colors"
        />
        <span class="text-slate-700 text-sm">→</span>
        <input
          type="date"
          v-model="customDateTo"
          class="bg-slate-900 border border-slate-700 text-slate-300 text-xs rounded-lg px-3 py-1.5 outline-none focus:border-indigo-500 transition-colors"
        />
        <button
          @click="applyCustomRange"
          class="px-3 py-1.5 text-xs bg-indigo-600 hover:bg-indigo-500 text-white rounded-lg transition-colors"
        >Apply</button>
        <button
          @click="showCustomRange = false"
          class="px-2 py-1.5 text-xs text-slate-600 hover:text-slate-400 transition-colors"
        >✕</button>
      </div>

      <!-- metric pills ───────────────────────────────────────────────────── -->
      <div class="flex flex-wrap gap-2 mb-5">
        <button
          v-for="[key, cfg] in visibleMetricEntries"
          :key="key"
          @click="toggleMetric(key)"
          class="flex items-center gap-2 px-3.5 py-1.5 rounded-full text-sm font-medium border transition-all duration-150"
          :style="selectedMetrics.includes(key)
            ? { backgroundColor: cfg.color + '22', borderColor: cfg.color + 'aa', color: cfg.color }
            : { backgroundColor: 'transparent', borderColor: '#334155', color: '#64748b' }"
        >
          <span
            class="w-2 h-2 rounded-full flex-shrink-0"
            :style="{ backgroundColor: selectedMetrics.includes(key) ? cfg.color : '#334155' }"
          />
          {{ cfg.label }}
        </button>
      </div>

      <!-- loading ────────────────────────────────────────────────────────── -->
      <template v-if="loading">
        <div class="flex items-center justify-center h-[540px] text-slate-500">
          <div class="flex flex-col items-center gap-3">
            <div class="w-6 h-6 border-2 border-slate-700 border-t-indigo-500 rounded-full animate-spin" />
            <span class="text-sm">Loading chart data…</span>
          </div>
        </div>
      </template>

      <!-- empty state ────────────────────────────────────────────────────── -->
      <template v-else-if="!chartData || !chartData.dates.length">
        <div class="flex items-center justify-center h-[540px] text-slate-500">
          <div class="text-center">
            <div class="text-4xl mb-3 opacity-30">📊</div>
            <div class="text-sm">No analytics data yet — sync your channel to get started.</div>
          </div>
        </div>
      </template>

      <!-- charts ─────────────────────────────────────────────────────────── -->
      <template v-else>

        <!-- main chart ───────────────────────────────────────────────────── -->
        <div class="bg-slate-900/80 rounded-2xl border border-white/5 px-4 pt-4 pb-2 mb-3">
          <div v-if="normalize" class="flex items-center gap-1.5 mb-2 text-xs text-indigo-400">
            <svg class="w-3.5 h-3.5 flex-shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
            </svg>
            Normalized — all series rebased to 100% at the start, showing relative % change
          </div>

          <ClientOnly>
            <apexchart
              :type="chartType"
              height="420"
              :options="mainChartOptions"
              :series="displaySeries"
            />
            <template #fallback>
              <div class="h-[420px] flex items-center justify-center text-slate-600 text-sm">Loading chart…</div>
            </template>
          </ClientOnly>
        </div>

        <!-- timeline scrubber ─────────────────────────────────────────────── -->
        <!-- visually distinct from the chart above: darker bg, dashed border, left accent -->
        <div class="rounded-xl border border-dashed border-slate-800 overflow-hidden bg-black/30 mb-4" style="border-left: 2px solid rgba(99,102,241,0.2)">
          <div class="flex items-center justify-between px-4 pt-2.5 pb-0">
            <div class="flex items-center gap-2">
              <span class="text-[10px] font-semibold text-slate-600 uppercase tracking-widest select-none">
                Timeline
              </span>
              <span class="text-[10px] text-slate-700 select-none">— drag handles to zoom</span>
            </div>
            <span class="text-[10px] text-slate-600 select-none tabular-nums font-mono">
              {{ visibleRangeLabel }}
            </span>
          </div>
          <ClientOnly>
            <apexchart
              type="area"
              height="100"
              :options="brushChartOptions"
              :series="brushSeries"
            />
            <template #fallback>
              <div class="h-[100px]" />
            </template>
          </ClientOnly>
        </div>

        <!-- summary cards ────────────────────────────────────────────────── -->
        <!-- values always reflect the currently visible date range above -->
        <div
          class="grid gap-3"
          :style="`grid-template-columns: repeat(${Math.min(selectedMetrics.length, 5)}, minmax(0, 1fr))`"
        >
          <div
            v-for="key in selectedMetrics"
            :key="key"
            class="bg-slate-900/80 rounded-xl border border-white/5 p-4"
            :style="{ borderColor: METRICS_CONFIG[key].color + '33' }"
          >
            <div class="text-xs text-slate-500 mb-1.5 font-medium uppercase tracking-wide">
              {{ METRICS_CONFIG[key].label }}
            </div>
            <div class="text-xl font-bold tabular-nums" :style="{ color: METRICS_CONFIG[key].color }">
              {{ METRICS_CONFIG[key].fmt(metricTotals[key] ?? null) }}
            </div>
            <div class="text-xs text-slate-600 mt-0.5">
              {{ key === 'ctr' || key === 'rpm' || key === 'avg_view_duration' ? 'average' : 'total' }}
              · {{ granularity }}
            </div>
          </div>
        </div>

      </template>
    </div>
  </div>
</template>
