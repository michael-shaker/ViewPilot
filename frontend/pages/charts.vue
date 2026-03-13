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

// month-based from/to selectors in the controls row
const selectedFrom = ref('')
const selectedTo = ref('')

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
  // clear the dropdown selectors so they don't show stale values
  selectedFrom.value = ''
  selectedTo.value = ''
}

// month options derived from the actual data — used by the from/to dropdowns
const monthOptions = computed(() => {
  if (!chartData.value?.dates?.length) return []
  const seen = new Set<string>()
  const opts: { value: string; label: string }[] = []
  for (const d of chartData.value.dates) {
    const m = d.slice(0, 7)
    if (!seen.has(m)) {
      seen.add(m)
      // use day 2 to avoid DST edge cases that could shift the month
      opts.push({ value: m, label: new Date(m + '-02').toLocaleDateString('en-US', { month: 'short', year: 'numeric' }) })
    }
  }
  return opts
})

const fromOptions = computed(() =>
  selectedTo.value ? monthOptions.value.filter(o => o.value <= selectedTo.value) : monthOptions.value
)

const toOptions = computed(() =>
  selectedFrom.value ? monthOptions.value.filter(o => o.value >= selectedFrom.value) : monthOptions.value
)

function onFromChange() {
  if (!selectedFrom.value || !chartData.value?.dates) return
  activeQuickRange.value = ''
  const fromMs = new Date(selectedFrom.value + '-01T00:00:00').getTime()
  const timestamps = chartData.value.dates.map(d => new Date(d + 'T00:00:00').getTime())
  const idx = timestamps.findIndex(t => t >= fromMs)
  if (idx >= 0) {
    visibleMin.value = timestamps[idx]
    if (visibleMax.value == null) visibleMax.value = contentRange.value?.max
  }
}

function onToChange() {
  if (!selectedTo.value || !chartData.value?.dates) return
  activeQuickRange.value = ''
  const parts = selectedTo.value.split('-')
  let yr = parseInt(parts[0]), mo = parseInt(parts[1]) + 1
  if (mo > 12) { mo = 1; yr++ }
  const endMs = new Date(`${yr}-${String(mo).padStart(2, '0')}-01T00:00:00`).getTime()
  const timestamps = chartData.value.dates.map(d => new Date(d + 'T00:00:00').getTime())
  let lastIdx = -1
  for (let i = timestamps.length - 1; i >= 0; i--) {
    if (timestamps[i] < endMs) { lastIdx = i; break }
  }
  if (lastIdx >= 0) {
    visibleMax.value = timestamps[lastIdx]
    if (visibleMin.value == null) visibleMin.value = contentRange.value?.min
  }
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

// ─── custom date range slider ───────────────────────────────────────────────
// replaces the old apexcharts brush: a thin draggable track with two handles

const sliderEl = ref<HTMLDivElement | null>(null)
type DragMode = 'left' | 'right' | 'pan' | null
const dragMode = ref<DragMode>(null)

// video dot tooltip state
const hoveredVideo = ref<{ title: string; date: string; pct: number } | null>(null)
const dragStartX = ref(0)
const dragStartMin = ref(0)
const dragStartMax = ref(0)

// percentage positions of the two handles (0–100)
const sliderLeft = computed(() => {
  const cr = contentRange.value
  if (!cr || visibleMin.value == null) return 0
  return Math.max(0, Math.min(100, ((visibleMin.value - cr.min) / (cr.max - cr.min)) * 100))
})

const sliderRight = computed(() => {
  const cr = contentRange.value
  if (!cr || visibleMax.value == null) return 100
  return Math.max(0, Math.min(100, ((visibleMax.value - cr.min) / (cr.max - cr.min)) * 100))
})

const sliderWidth = computed(() => Math.max(0.5, sliderRight.value - sliderLeft.value))

// year-boundary ticks to show below the track
const yearTicks = computed(() => {
  const cr = contentRange.value
  if (!cr) return []
  const startYear = new Date(cr.min).getFullYear() + 1
  const endYear = new Date(cr.max).getFullYear()
  const ticks: { pct: number; label: string }[] = []
  for (let y = startYear; y <= endYear; y++) {
    const ts = new Date(`${y}-01-01T00:00:00`).getTime()
    const pct = ((ts - cr.min) / (cr.max - cr.min)) * 100
    if (pct > 1 && pct < 99) ticks.push({ pct, label: String(y) })
  }
  return ticks
})

// video upload dots along the slider — one per video at the right % position
const videoDots = computed(() => {
  const cr = contentRange.value
  if (!cr || !videoList.value.length) return []
  return videoList.value.map(v => ({
    pct: Math.max(0, Math.min(100, ((v.ts - cr.min) / (cr.max - cr.min)) * 100)),
    title: v.title,
    date: new Date(v.ts).toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' }),
  }))
})

function onSliderMouseDown(e: MouseEvent) {
  const cr = contentRange.value
  if (!cr || visibleMin.value == null || visibleMax.value == null || !sliderEl.value) return
  const rect = sliderEl.value.getBoundingClientRect()
  const pct = Math.max(0, Math.min(100, ((e.clientX - rect.left) / rect.width) * 100))
  // 12px tolerance for grabbing a handle
  const tolPct = (12 / rect.width) * 100
  if (Math.abs(pct - sliderLeft.value) <= tolPct) {
    dragMode.value = 'left'
  } else if (Math.abs(pct - sliderRight.value) <= tolPct) {
    dragMode.value = 'right'
  } else if (pct > sliderLeft.value && pct < sliderRight.value) {
    dragMode.value = 'pan'
  } else {
    // click outside: center the current window at the clicked position
    const halfSpan = (visibleMax.value - visibleMin.value) / 2
    const clickTs = cr.min + (pct / 100) * (cr.max - cr.min)
    const newMin = Math.max(cr.min, clickTs - halfSpan)
    visibleMin.value = newMin
    visibleMax.value = Math.min(cr.max, newMin + halfSpan * 2)
    activeQuickRange.value = ''
    selectedFrom.value = ''
    selectedTo.value = ''
    return
  }
  dragStartX.value = e.clientX
  dragStartMin.value = visibleMin.value
  dragStartMax.value = visibleMax.value
  e.preventDefault()
  window.addEventListener('mousemove', onSliderMouseMove)
  window.addEventListener('mouseup', onSliderMouseUp)
}

function onSliderMouseMove(e: MouseEvent) {
  const cr = contentRange.value
  if (!cr || !dragMode.value || !sliderEl.value) return
  const trackWidth = sliderEl.value.getBoundingClientRect().width
  const deltaMs = ((e.clientX - dragStartX.value) / trackWidth) * (cr.max - cr.min)
  const span = dragStartMax.value - dragStartMin.value
  const minSpan = 86_400_000 // at least one day

  if (dragMode.value === 'left') {
    visibleMin.value = Math.max(cr.min, Math.min(dragStartMin.value + deltaMs, dragStartMax.value - minSpan))
  } else if (dragMode.value === 'right') {
    visibleMax.value = Math.min(cr.max, Math.max(dragStartMax.value + deltaMs, dragStartMin.value + minSpan))
  } else {
    let newMin = dragStartMin.value + deltaMs
    let newMax = dragStartMax.value + deltaMs
    if (newMin < cr.min) { newMin = cr.min; newMax = cr.min + span }
    if (newMax > cr.max) { newMax = cr.max; newMin = cr.max - span }
    visibleMin.value = newMin
    visibleMax.value = newMax
  }
  activeQuickRange.value = ''
  selectedFrom.value = ''
  selectedTo.value = ''
}

function onSliderMouseUp() {
  dragMode.value = null
  window.removeEventListener('mousemove', onSliderMouseMove)
  window.removeEventListener('mouseup', onSliderMouseUp)
}

onUnmounted(() => {
  window.removeEventListener('mousemove', onSliderMouseMove)
  window.removeEventListener('mouseup', onSliderMouseUp)
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

// count of data points falling inside the visible window (for the summary footer)
const visibleDayCount = computed(() => {
  if (!chartData.value?.dates) return 0
  const timestamps = chartData.value.dates.map(d => new Date(d + 'T00:00:00').getTime())
  const min = visibleMin.value
  const max = visibleMax.value
  return timestamps.filter(t => (min == null || t >= min - 1) && (max == null || t <= max + 1)).length
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
          <button @click="toggleRevenue" class="flex items-center gap-2 group" title="Toggle revenue visibility">
            <span class="text-sm text-gray-300 group-hover:text-white transition whitespace-nowrap">Revenue</span>
            <div class="relative w-9 h-5 rounded-full transition-colors duration-200" :class="showRevenue ? 'bg-red-500/70' : 'bg-white/15'">
              <span class="absolute top-0.5 left-0.5 w-4 h-4 rounded-full bg-white shadow transition-transform duration-200" :class="showRevenue ? 'translate-x-4' : 'translate-x-0'" />
            </div>
          </button>
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

        <!-- from / to month dropdowns — always visible, auto-apply on change -->
        <div v-if="monthOptions.length" class="flex items-center gap-1.5">
          <span class="text-xs text-slate-600 whitespace-nowrap hidden sm:block">From</span>
          <select
            v-model="selectedFrom"
            @change="onFromChange"
            class="bg-slate-900 border border-white/5 text-slate-400 text-xs rounded-lg px-2 h-7 outline-none focus:border-indigo-500/60 transition-colors cursor-pointer"
          >
            <option value="">Start</option>
            <option v-for="opt in fromOptions" :key="opt.value" :value="opt.value">{{ opt.label }}</option>
          </select>
          <span class="text-slate-700 text-xs">→</span>
          <select
            v-model="selectedTo"
            @change="onToChange"
            class="bg-slate-900 border border-white/5 text-slate-400 text-xs rounded-lg px-2 h-7 outline-none focus:border-indigo-500/60 transition-colors cursor-pointer"
          >
            <option value="">End</option>
            <option v-for="opt in toOptions" :key="opt.value" :value="opt.value">{{ opt.label }}</option>
          </select>
        </div>
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

        <!-- custom timeline slider ────────────────────────────────────────── -->
        <!-- a thin drag-and-drop range bar — much lighter than a second chart -->
        <div
          class="px-5 pt-4 pb-3 mb-4 rounded-xl border border-white/5 bg-slate-900/40 select-none"
          :class="dragMode === 'pan' ? 'cursor-grabbing' : ''"
        >
          <!-- track -->
          <div
            ref="sliderEl"
            class="relative flex items-center"
            style="height: 28px; overflow: visible"
            @mousedown="onSliderMouseDown"
          >
            <!-- base track line -->
            <div class="absolute inset-x-0 h-[3px] rounded-full bg-slate-800" />

            <!-- selected window fill -->
            <div
              class="absolute h-[3px] rounded-full bg-indigo-500/40"
              :class="dragMode === 'pan' ? 'cursor-grabbing' : 'cursor-grab'"
              :style="{ left: sliderLeft + '%', width: sliderWidth + '%' }"
            />

            <!-- year tick marks -->
            <div
              v-for="tick in yearTicks"
              :key="tick.pct"
              class="absolute w-px bg-slate-700/60 pointer-events-none"
              style="height: 6px; top: 50%; transform: translateY(-50%)"
              :style="{ left: tick.pct + '%' }"
            />

            <!-- video upload dots -->
            <div
              v-for="(dot, i) in videoDots"
              :key="i"
              class="absolute w-1.5 h-1.5 rounded-full bg-slate-600 hover:bg-indigo-400 top-1/2 -translate-y-1/2 -translate-x-1/2 transition-colors duration-100 z-10"
              style="pointer-events: auto; cursor: default"
              :style="{ left: dot.pct + '%' }"
              @mouseenter="hoveredVideo = { title: dot.title, date: dot.date, pct: dot.pct }"
              @mouseleave="hoveredVideo = null"
            />

            <!-- tooltip for hovered video dot -->
            <div
              v-if="hoveredVideo"
              class="absolute bottom-full mb-3 z-50 pointer-events-none"
              :style="{ left: hoveredVideo.pct + '%', transform: 'translateX(-50%)' }"
            >
              <div class="bg-slate-900 border border-white/10 rounded-lg px-3 py-2 text-xs shadow-xl whitespace-nowrap">
                <div class="text-slate-200 font-medium max-w-[220px] truncate">{{ hoveredVideo.title }}</div>
                <div class="text-slate-500 mt-0.5">{{ hoveredVideo.date }}</div>
              </div>
              <!-- small downward arrow -->
              <div class="absolute left-1/2 -translate-x-1/2 top-full w-0 h-0" style="border-left: 5px solid transparent; border-right: 5px solid transparent; border-top: 5px solid #1e293b" />
            </div>

            <!-- left handle -->
            <div
              class="absolute top-1/2 -translate-y-1/2 w-[3px] rounded-full cursor-ew-resize transition-colors duration-100"
              style="height: 20px"
              :class="dragMode === 'left' ? 'bg-indigo-300' : 'bg-indigo-500 hover:bg-indigo-400'"
              :style="{ left: 'calc(' + sliderLeft + '% - 1.5px)' }"
            />

            <!-- right handle -->
            <div
              class="absolute top-1/2 -translate-y-1/2 w-[3px] rounded-full cursor-ew-resize transition-colors duration-100"
              style="height: 20px"
              :class="dragMode === 'right' ? 'bg-indigo-300' : 'bg-indigo-500 hover:bg-indigo-400'"
              :style="{ left: 'calc(' + sliderRight + '% - 1.5px)' }"
            />
          </div>

          <!-- year labels row -->
          <div v-if="yearTicks.length" class="relative h-4 mt-0.5">
            <div
              v-for="tick in yearTicks"
              :key="tick.label"
              class="absolute text-[9px] text-slate-700 -translate-x-1/2 pointer-events-none font-mono"
              :style="{ left: tick.pct + '%' }"
            >{{ tick.label }}</div>
          </div>

          <!-- outer edge labels + visible range in center -->
          <div class="flex justify-between items-center mt-1 text-[10px] font-mono tabular-nums">
            <span class="text-slate-700">
              {{ contentRange ? new Date(contentRange.min).toLocaleDateString('en-US', { month: 'short', year: 'numeric' }) : '' }}
            </span>
            <span class="text-slate-500">{{ visibleRangeLabel }}</span>
            <span class="text-slate-700">
              {{ contentRange ? new Date(contentRange.max).toLocaleDateString('en-US', { month: 'short', year: 'numeric' }) : '' }}
            </span>
          </div>
        </div>

        <!-- summary section ──────────────────────────────────────────────── -->
        <!-- totals/averages for the currently visible window only -->
        <div class="bg-slate-900/60 rounded-2xl border border-white/5 p-4">
          <!-- period header -->
          <div class="flex items-center justify-between mb-3">
            <span class="text-[10px] font-semibold text-slate-600 uppercase tracking-widest">Summary</span>
            <span class="text-xs text-slate-500 tabular-nums font-mono">
              {{ visibleRangeLabel }}
              <span v-if="visibleDayCount" class="text-slate-600 ml-1">
                · {{ visibleDayCount }}&nbsp;{{ granularity === 'monthly' ? 'months' : granularity === 'weekly' ? 'weeks' : 'days' }}
              </span>
            </span>
          </div>

          <!-- metric cards -->
          <div
            class="grid gap-2.5"
            :style="`grid-template-columns: repeat(${Math.min(selectedMetrics.length, 5)}, minmax(0, 1fr))`"
          >
            <div
              v-for="key in selectedMetrics"
              :key="key"
              class="rounded-xl px-4 py-3 border"
              :style="{ borderColor: METRICS_CONFIG[key].color + '22', background: METRICS_CONFIG[key].color + '0a' }"
            >
              <div class="text-[10px] text-slate-500 uppercase tracking-widest mb-2 font-semibold truncate">
                {{ METRICS_CONFIG[key].label }}
              </div>
              <div class="text-xl font-bold tabular-nums leading-none" :style="{ color: METRICS_CONFIG[key].color }">
                {{ METRICS_CONFIG[key].fmt(metricTotals[key] ?? null) }}
              </div>
              <div class="text-[10px] text-slate-600 mt-1.5">
                {{ ['ctr', 'rpm', 'avg_view_duration'].includes(key) ? 'avg in range' : 'total in range' }}
              </div>
            </div>
          </div>
        </div>

      </template>
    </div>
  </div>
</template>
