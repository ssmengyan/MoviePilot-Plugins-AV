<script setup lang="ts">
/**
 * 视图：刮削（数据台第八栏，v4 刮削线 S9 新增）。
 *
 * 两个页签（契约 §3.8 / v4.1 §10.2）：
 * 1. **全库刮削工作台** —— 顶部状态卡片（`full` / `missing_plot` / `missing_core` / `unscraped` / `total`，
 *    点一下筛选）、行列表（番号 / 标题 / 状态徽标 / 裁切锚点 / 预览·刮削·回滚）、字段级 diff 面板、
 *    全选 + 批量刮削（**二次确认，文案写明「将写入 Emby」**）；
 * 2. **数据源自检** —— `sources[]` 表格（源名 / 最近状态 / 耗时 / 错误摘要 / 检查时间）、
 *    「立即自检」按钮、`scrape_log` 最近 50 条流水。
 *
 * 接口（**全部来自契约 §3.7，一个都不自己发明**）：
 * | 用途 | 端点 |
 * | --- | --- |
 * | 状态 + 列表 | `GET /scrape/status`（`{stats, sources, queue, last_run, items}`） |
 * | 列表回落 | `GET /library`（`items[]` 缺失时用它，行里已带 `states` / `version_tags`） |
 * | 字段级 diff | `GET /scrape/preview?key=` |
 * | 单条 / 批量刮削 | `POST /scrape/run {keys?, all?, force?, anchor?, confirm?}` |
 * | 回滚 | `POST /scrape/rollback {item_key}` |
 * | 流水 | `GET /scrape/log?limit=50` |
 *
 * `items[]` 的字段名由主统筹 2026-10-14 定死：
 * `{key, number, title, emby_id, completeness, scrape_state, has_backup, crop_anchor, version_tags[], updated_at}`
 * —— 缺字段一律容错（`—` / 不画），**不猜**。
 *
 * 三处刻意的口径（都有实测/裁决依据，改之前先读文档）：
 * - **「立即自检」只重读 `GET /scrape/status`**：契约 §3.7 **没有**触发式自检端点
 *   （`scraper.sources_selfcheck()` 是 Python 侧函数），所以这里把「刷新各源最近状态」如实
 *   说成「重新读取 `/scrape/status`」，不发明端点名。
 * - **回滚禁用判据 = `has_backup === false`**（主统筹裁决）：禁用 + 提示「无 Emby 备份，无法回滚」；
 *   字段**缺失**时放行（否则 S8 没上线时整列按钮都是灰的）但每次都要二次确认。
 * - **批量刮削必须二次确认**（宿主 `moviepilot:confirm`，拿不到就 `window.confirm` 降级），
 *   文案写明「将写入 Emby（可回滚）」；载荷带 `confirm: true`（后端对 `all=true` 要求它）。
 *
 * 降级纪律（本线的硬要求）：接口 404 / 网络失败 / 字段缺失 → 空态或错误态 + 一句原因，
 * **不白屏、不抛未捕获异常**、不因为一个端点坏了就把另一块也画成坏的（两块各自 try/catch）。
 */
import { computed, ref } from 'vue'
import EmptyState from '../common/EmptyState.vue'
import ErrorState from '../common/ErrorState.vue'
import { errorText, hostToast, unwrap, type PluginApi } from '../../composables/usePluginApi'
import { useHostConfirm } from '../../composables/useHostDialogs'
import { shortTime } from '../../composables/storeTypes'

const props = withDefaults(
  defineProps<{
    /** 本插件实例 id（本视图不画图，保留是为了与其余原生视图同一组 props）。 */
    pluginId?: string
    /** 宿主请求器（壳已补插件 id）：本视图所有请求都走它。 */
    api?: PluginApi | null
    /** 宿主 toast（`moviepilot:toast` 注入），拿不到时静默降级。 */
    toast?: unknown
    /** 壳统一传的一组 props（本视图不用 store，声明只为不与壳的绑定冲突）。 */
    store?: unknown
  }>(),
  { pluginId: '', api: null, toast: null, store: null },
)

/** ⚠️ 必须是字符串数组（AGENTS.md §5 的坑：函数式写法编译出 `emits: <函数>`，事件静默失效）。 */
const emit = defineEmits(['refreshSide'])

const t = hostToast(props.toast as any)
const confirm = useHostConfirm()

// ---------------------------------------------------------------- 请求封装

function text(value: unknown): string {
  return value === null || value === undefined ? '' : String(value)
}

async function getJson(path: string, params?: Record<string, unknown>): Promise<any> {
  const api = props.api
  if (!api || typeof api.get !== 'function') throw new Error('宿主 api 不可用')
  const payload: any = unwrap<any>(await api.get(path, params ? { params } : undefined))
  if (payload && typeof payload === 'object' && payload.success === false) {
    throw new Error(text(payload.message) || '接口返回失败')
  }
  return payload
}

async function postJson(path: string, body: Record<string, unknown>): Promise<any> {
  const api = props.api
  if (!api || typeof api.post !== 'function') throw new Error('宿主 api 不可用')
  const payload: any = unwrap<any>(await api.post(path, body))
  if (payload && typeof payload === 'object' && payload.success === false) {
    throw new Error(text(payload.message) || '接口返回失败')
  }
  return payload
}

/** 从若干候选键里取第一个是数组的值（后端字段名变动时不至于整块空掉）。 */
function firstArray(source: any, keys: string[]): any[] | null {
  if (!source || typeof source !== 'object') return null
  for (const key of keys) {
    if (Array.isArray(source[key])) return source[key]
  }
  return null
}

// ---------------------------------------------------------------- 页签

type TabKey = 'workbench' | 'sources'
const TABS: { key: TabKey; name: string }[] = [
  { key: 'workbench', name: '全库刮削工作台' },
  { key: 'sources', name: '数据源自检' },
]
const tab = ref<TabKey>('workbench')

/** 流水（`GET /scrape/log`）是懒加载的：切到「数据源自检」时才读第一次（`sources` 跟主状态一起来）。 */
const sourcesLoaded = ref(false)

function pickTab(key: TabKey): void {
  tab.value = key
  if (key === 'sources' && !sourcesLoaded.value) void loadLog()
}

// ---------------------------------------------------------------- 状态与列表

/** 状态四档（`stats` 的键就是这四个 + `total`）。 */
type StatusKey = 'full' | 'missing_plot' | 'missing_core' | 'unscraped'

const STATUS_META: Record<StatusKey, { label: string; color: string; hint: string }> = {
  full: { label: '已完整', color: 'success', hint: '核心字段与简介都齐了' },
  missing_plot: { label: '缺简介', color: 'warning', hint: '标题/封面/演员有，简介还没拿到（Tier 1 退避重刮）' },
  missing_core: { label: '缺核心', color: 'error', hint: '核心字段（标题/封面/演员/发行日）还没补齐' },
  unscraped: { label: '未刮削', color: 'info', hint: '还没跑过自建刮削层' },
}
const STATUS_ORDER: StatusKey[] = ['full', 'missing_plot', 'missing_core', 'unscraped']

/** 一行（`/scrape/status.items[]` 或回落 `/library.items[]` 归一后的形状）。 */
interface WorkRow {
  key: string
  number: string
  title: string
  embyId: string
  itemKey: string
  status: StatusKey
  statusRaw: string
  hasBackup: boolean | null
  anchor: string
  versionTags: unknown
  updatedAt: string
  raw: Record<string, any>
}

/** 后端状态词 → 四档（认不出的归「未刮削」，并把原词留在 `statusRaw` 里照实显示）。 */
function statusKeyOf(raw: unknown): { key: StatusKey; raw: string } {
  const value = text(raw).trim()
  const lower = value.toLowerCase()
  if (lower === 'full' || lower === 'scraped_full' || lower === 'complete') return { key: 'full', raw: value }
  if (lower === 'missing_plot' || lower === 'scraped_partial' || lower === 'partial') return { key: 'missing_plot', raw: value }
  if (lower === 'missing_core') return { key: 'missing_core', raw: value }
  return { key: 'unscraped', raw: value }
}

/** `item_key` 缺省时按契约 §4 的格式从 `emby_id` 拼（`emby:<id>`）——回滚要用它。 */
function itemKeyOf(row: Record<string, any>): string {
  const direct = text(row.item_key || row.itemKey)
  if (direct) return direct
  const emby = text(row.emby_id || row.embyId)
  return emby ? `emby:${emby}` : ''
}

/** 一条原始行 → `WorkRow`（字段缺失一律容错）。 */
function normalizeRow(row: Record<string, any>): WorkRow {
  const number = text(row.number || row.display_number || row.key)
  const key = text(row.key || number)
  const status = statusKeyOf(row.completeness ?? row.scrape_state ?? row.status ?? row.states?.scrape)
  const backup = row.has_backup ?? row.hasBackup
  const anchor = text(row.crop_anchor || row.cropAnchor || 'auto') || 'auto'
  return {
    key,
    number: number || key,
    title: text(row.title),
    embyId: text(row.emby_id || row.embyId),
    itemKey: itemKeyOf(row),
    status: status.key,
    statusRaw: status.raw,
    hasBackup: typeof backup === 'boolean' ? backup : null,
    anchor,
    versionTags: row.version_tags ?? row.versionTags ?? null,
    updatedAt: text(row.updated_at || row.updatedAt),
    raw: row,
  }
}

const loading = ref(false)
/** 列表加载失败的原因（整块进 `ErrorState`）。 */
const error = ref('')
/** `/scrape/status` 单独失败的原因（列表可能已经从 `/library` 拿到了）。 */
const statusError = ref('')
const statusData = ref<any>(null)
const rows = ref<WorkRow[]>([])
/** 列表来自哪：`status` = `/scrape/status.items`；`library` = 回落 `/library`；`''` = 没有。 */
const listSource = ref<'' | 'status' | 'library'>('')

/** 顶部卡片：`stats` 五档（字段缺失按 0，`total` 缺失就用列表长度兜底）。 */
const stats = computed<Record<string, number>>(() => {
  const raw = (statusData.value && typeof statusData.value === 'object' ? statusData.value.stats : null) || {}
  const out: Record<string, number> = {}
  for (const key of STATUS_ORDER) out[key] = Number(raw?.[key]) || 0
  out.total = Number(raw?.total) || rows.value.length
  return out
})

/** 队列长度（`queue:{tier1,tier2}`）与上次运行时间。 */
const queueInfo = computed<{ tier1: number | null; tier2: number | null }>(() => {
  const queue = statusData.value?.queue
  if (!queue || typeof queue !== 'object') return { tier1: null, tier2: null }
  const numOf = (value: unknown) => (Number.isFinite(Number(value)) ? Number(value) : null)
  return { tier1: numOf(queue.tier1), tier2: numOf(queue.tier2) }
})
const lastRun = computed(() => text(statusData.value?.last_run))

// ---------------------------------------------------------------- 筛选 / 选择 / 锚点

/** 当前筛选（`''` = 全部）；点已选中的卡片再点一下取消。 */
const filter = ref<'' | StatusKey>('')
const filterLabel = computed(() => (filter.value ? STATUS_META[filter.value].label : ''))

function toggleFilter(key: StatusKey): void {
  filter.value = filter.value === key ? '' : key
}

const visibleRows = computed<WorkRow[]>(() =>
  filter.value ? rows.value.filter(row => row.status === filter.value) : rows.value,
)

/** 勾选的行（用行 key 做标识）。 */
const selected = ref<Set<string>>(new Set())

function rowId(row: WorkRow): string {
  return row.itemKey || row.key || row.number
}

function isSelected(row: WorkRow): boolean {
  return selected.value.has(rowId(row))
}

function toggleRow(row: WorkRow): void {
  const next = new Set(selected.value)
  const id = rowId(row)
  if (next.has(id)) next.delete(id)
  else next.add(id)
  selected.value = next
}

const allVisibleSelected = computed(
  () => visibleRows.value.length > 0 && visibleRows.value.every(row => isSelected(row)),
)

function toggleAll(): void {
  const next = new Set(selected.value)
  if (allVisibleSelected.value) {
    for (const row of visibleRows.value) next.delete(rowId(row))
  } else {
    for (const row of visibleRows.value) next.add(rowId(row))
  }
  selected.value = next
}

/** 每行可改的裁切锚点草稿（改完点「刮削」时随 `anchor` 发给后端；`/scrape/run` 接受该字段）。 */
const anchorEdits = ref<Record<string, string>>({})

function anchorOf(row: WorkRow): string {
  return text(anchorEdits.value[rowId(row)] || row.anchor || 'auto') || 'auto'
}

function setAnchor(row: WorkRow, value: string): void {
  anchorEdits.value = { ...anchorEdits.value, [rowId(row)]: value }
}

const ANCHOR_OPTIONS = [
  { value: 'auto', title: '自动（按图源判断）' },
  { value: 'right', title: '贴右（封套展开图取封面）' },
  { value: 'center', title: '居中' },
  { value: 'left', title: '贴左' },
  { value: 'raw', title: '不裁切（原图直传）' },
]

/** 批量刮削用哪一档锚点：选中行一致就用它，不一致就不传（由后端按 auto 处理）。 */
const batchAnchor = computed(() => {
  const chosen = visibleRows.value.filter(row => isSelected(row)).map(row => anchorOf(row))
  const unique = Array.from(new Set(chosen))
  return unique.length === 1 ? unique[0]! : ''
})

// ---------------------------------------------------------------- 读数据

/** 读 `GET /scrape/status`（两块共用：工作台的 stats/items、自检页的 sources/queue）。 */
async function loadStatus(): Promise<void> {
  statusError.value = ''
  try {
    statusData.value = await getJson('plugin/scrape/status')
  } catch (err) {
    statusData.value = null
    statusError.value = errorText(err)
  }
}

/** 回落：`GET /library`（契约 §3.7：每条带 `key/version_tags/states`）。 */
async function loadLibraryRows(): Promise<WorkRow[]> {
  const payload: any = await getJson('plugin/library')
  const list = firstArray(payload, ['items', 'list']) || []
  return list
    .filter((item: any) => item && typeof item === 'object')
    .map((item: any) => normalizeRow({
      key: item.key,
      number: item.number,
      title: item.title,
      emby_id: item.emby_id || item.id,
      // `/library` 没有 completeness：用 `states.scrape` 认档（`film_view` 的口径）
      completeness: item.states?.scrape,
      version_tags: item.version_tags,
      updated_at: item.updated_at,
    }))
}

/**
 * 整块读一次：状态 → 列表 → （列表缺了就回落 `/library`）。
 * 两块各自 try/catch：`/scrape/status` 挂了也还能靠 `/library` 把列表画出来。
 */
async function load(notify = false): Promise<void> {
  if (loading.value) return
  loading.value = true
  error.value = ''
  if (notify) t.info('正在读取刮削状态…')
  try {
    await loadStatus()
    const inline = firstArray(statusData.value, ['items', 'list', 'films'])
    if (inline) {
      rows.value = inline
        .filter((item: any) => item && typeof item === 'object')
        .map((item: any) => normalizeRow(item))
      listSource.value = 'status'
    } else {
      try {
        rows.value = await loadLibraryRows()
        listSource.value = rows.value.length ? 'library' : ''
      } catch (err) {
        rows.value = []
        listSource.value = ''
        // 两个来源都失败：把能说的原因合起来给用户（优先 /scrape/status 的那句）
        error.value = statusError.value || errorText(err)
      }
    }
    if (!rows.value.length && statusError.value && !error.value) error.value = statusError.value
    // 勾选里已经不存在的行清掉（避免"批量 n"里混着看不见的行）
    const alive = new Set(rows.value.map(row => rowId(row)))
    selected.value = new Set(Array.from(selected.value).filter(id => alive.has(id)))
    if (notify && !error.value) t.success(`共 ${rows.value.length} 条`)
    if (notify && error.value) t.warning(`刮削状态读取失败：${error.value}`)
  } finally {
    loading.value = false
  }
}

void load(false)

// ---------------------------------------------------------------- 预览（字段级 diff）

interface PreviewField {
  name: string
  current: string
  target: string
  changed: boolean
}

const preview = ref<{
  open: boolean
  loading: boolean
  error: string
  key: string
  number: string
  fields: PreviewField[]
  warnings: string[]
  sources: Record<string, any> | null
}>({
  open: false,
  loading: false,
  error: '',
  key: '',
  number: '',
  fields: [],
  warnings: [],
  sources: null,
})

/** 值 → 一行文本（对象/数组压成 JSON，null 显示 `—`）。 */
function valueText(value: unknown): string {
  if (value === null || value === undefined || value === '') return '—'
  if (typeof value === 'object') {
    try {
      return JSON.stringify(value)
    } catch {
      return String(value)
    }
  }
  return String(value)
}

async function openPreview(row: WorkRow): Promise<void> {
  preview.value = {
    open: true,
    loading: true,
    error: '',
    key: row.key,
    number: row.number,
    fields: [],
    warnings: [],
    sources: null,
  }
  try {
    const payload: any = await getJson('plugin/scrape/preview', { key: row.key })
    const list = firstArray(payload, ['fields']) || []
    preview.value.fields = list.map((item: any) => ({
      name: text(item?.name),
      current: valueText(item?.current),
      target: valueText(item?.target),
      changed: item?.changed === true,
    }))
    preview.value.warnings = Array.isArray(payload?.warnings)
      ? payload.warnings.map((item: any) => text(item))
      : []
    preview.value.sources =
      payload?.sources && typeof payload.sources === 'object' ? payload.sources : null
    if (payload?.number) preview.value.number = text(payload.number)
  } catch (err) {
    preview.value.error = errorText(err)
  } finally {
    preview.value.loading = false
  }
}

const previewChanged = computed(() => preview.value.fields.filter(item => item.changed).length)

// ---------------------------------------------------------------- 刮削 / 回滚

/** 在飞的动作（`''` = 空闲）：给对应按钮转圈，避免重复点。 */
const busy = ref('')
/** 最近一次批量/单条刮削的结论（跑完留在页面上，别只靠 toast）。 */
const runResult = ref<{ ok: boolean; text: string; errors: string[] } | null>(null)

/** `POST /scrape/run` 的结论 → 一句话 + 失败明细。 */
function summarizeRun(payload: any): { ok: boolean; text: string; errors: string[] } {
  const results = Array.isArray(payload?.results) ? payload.results : []
  const errors: string[] = []
  let okCount = 0
  for (const item of results) {
    const err = text(item?.error)
    const status = text(item?.status)
    if (err || status === 'error' || status === 'failed') {
      errors.push(`${text(item?.key) || '(未知)'}：${err || status || '失败'}`)
      continue
    }
    okCount += 1
  }
  const declared = payload?.ok
  const ok = declared === undefined ? errors.length === 0 : declared !== false && errors.length === 0
  return {
    ok,
    text: `成功 ${okCount} 条${errors.length ? ` · 失败 ${errors.length} 条` : ''}`,
    errors,
  }
}

/** 单条「刮削」：直接跑（用户明确点了这一行），跑完把结论留在页面上。 */
async function runOne(row: WorkRow): Promise<void> {
  if (busy.value) return
  const id = rowId(row)
  busy.value = `run:${id}`
  runResult.value = null
  t.info(`正在刮削 ${row.number || row.key} …`)
  try {
    const payload: any = await postJson('plugin/scrape/run', {
      keys: [row.key || row.number],
      force: false,
      anchor: anchorOf(row),
    })
    const summary = summarizeRun(payload)
    runResult.value = summary
    if (summary.ok) t.success(`刮削完成：${summary.text}`)
    else t.warning(`刮削未全部成功：${summary.text}`)
    emit('refreshSide')
    await load(false)
  } catch (err) {
    runResult.value = { ok: false, text: '刮削请求失败', errors: [errorText(err)] }
    t.warning(`刮削失败：${errorText(err)}`)
  } finally {
    busy.value = ''
  }
}

/**
 * 批量「刮削选中」：**必须二次确认**（会写 Emby），文案写明「将写入 Emby（可回滚）」。
 * 载荷带 `confirm: true`（后端对 `all=true` 要求该字段；这里也一并发，语义一致）。
 */
async function runSelected(): Promise<void> {
  if (busy.value) return
  const chosen = visibleRows.value.filter(row => isSelected(row))
  if (!chosen.length) return
  const keys = chosen.map(row => row.key || row.number).filter(Boolean)
  const ok = await confirm({
    type: 'warn',
    title: '批量刮削',
    content:
      `将写入 Emby（可回滚）：共 ${keys.length} 部影片。\n\n` +
      '插件会先给每一条落一份完整 Emby DTO 备份，再写标题 / 原名 / 简介 / 演员 / 封面 / 发行日等字段；' +
      '写坏了可以在本页用「回滚」还原。确认现在开始？',
    confirmText: '开始刮削',
    cancelText: '取消',
  })
  if (!ok) return
  busy.value = 'run:batch'
  runResult.value = null
  t.info(`正在批量刮削 ${keys.length} 部…`)
  try {
    const body: Record<string, unknown> = { keys, all: false, force: false, confirm: true }
    if (batchAnchor.value) body.anchor = batchAnchor.value
    const payload: any = await postJson('plugin/scrape/run', body)
    const summary = summarizeRun(payload)
    runResult.value = summary
    if (summary.ok) t.success(`批量刮削完成：${summary.text}`)
    else t.warning(`批量刮削未全部成功：${summary.text}`)
    selected.value = new Set()
    emit('refreshSide')
    await load(false)
  } catch (err) {
    runResult.value = { ok: false, text: '批量刮削请求失败', errors: [errorText(err)] }
    t.warning(`批量刮削失败：${errorText(err)}`)
  } finally {
    busy.value = ''
  }
}

/** 回滚禁用判据：`has_backup === false` 或压根没有 `item_key`。字段缺失时放行（见文件头）。 */
function rollbackDisabled(row: WorkRow): boolean {
  return row.hasBackup === false || !row.itemKey
}

function rollbackHint(row: WorkRow): string {
  if (!row.itemKey) return '这一行没有 item_key，无法定位要回滚的 Emby 条目'
  if (row.hasBackup === false) return '无 Emby 备份，无法回滚'
  if (row.hasBackup === null) return '不确定有没有备份：点了会先由后端校验'
  return '用写入前那份完整 DTO 还原这一条'
}

/** 回滚：破坏性操作（会覆盖 Emby 现字段），每次都要二次确认。 */
async function rollback(row: WorkRow): Promise<void> {
  if (busy.value || rollbackDisabled(row)) return
  const ok = await confirm({
    type: 'warn',
    title: '回滚这一条',
    content:
      `将用写入前保存的那份完整 Emby DTO 覆盖「${row.number || row.key}」，` +
      '期间在这部片上手改过的字段也会一起还原。此操作不可撤销，确认继续？',
    confirmText: '回滚',
    cancelText: '取消',
  })
  if (!ok) return
  const id = rowId(row)
  busy.value = `rollback:${id}`
  runResult.value = null
  try {
    const payload: any = await postJson('plugin/scrape/rollback', { item_key: row.itemKey })
    const restored = Array.isArray(payload?.restored) ? payload.restored.map((x: any) => text(x)) : []
    const failure = text(payload?.error)
    if (payload?.ok === false || failure) {
      runResult.value = { ok: false, text: '回滚失败', errors: [failure || '后端返回 ok=false'] }
      t.warning(`回滚失败：${failure || '原因未知'}`)
    } else {
      runResult.value = {
        ok: true,
        text: `已回滚${restored.length ? `：${restored.join('、')}` : ''}`,
        errors: [],
      }
      t.success('已回滚')
    }
    emit('refreshSide')
    await load(false)
  } catch (err) {
    runResult.value = { ok: false, text: '回滚请求失败', errors: [errorText(err)] }
    t.warning(`回滚失败：${errorText(err)}`)
  } finally {
    busy.value = ''
  }
}

// ---------------------------------------------------------------- 数据源自检页

/** 各源最近状态（`/scrape/status.sources`，字段名容错读）。 */
const sources = computed<any[]>(() => {
  const list = firstArray(statusData.value, ['sources'])
  return Array.isArray(list) ? list : []
})

const logItems = ref<Array<Record<string, any>>>([])
const logSummary = ref<Array<Record<string, any>>>([])
const logLoading = ref(false)
const logError = ref('')

/** 源名（`name` / `source` / `source_name` 三种写法都认）。 */
function sourceName(row: Record<string, any>): string {
  return text(row?.name ?? row?.source ?? row?.source_name) || '(未命名源)'
}

/** 源状态 + 成败着色（`ok` 布尔、`status` 字符串都认）。 */
function sourceState(row: Record<string, any>): { text: string; color: string } {
  const status = text(row?.status ?? row?.state).trim()
  const okFlag = row?.ok
  const bad = /fail|error|down|异常|失败/i.test(status) || okFlag === false
  const good = /ok|success|ready|正常|成功/i.test(status) || okFlag === true
  const label = status || (okFlag === true ? 'ok' : okFlag === false ? 'error' : '—')
  return { text: label, color: bad ? 'error' : good ? 'success' : 'info' }
}

function latencyText(value: unknown): string {
  const num = Number(value)
  return Number.isFinite(num) && num > 0 ? `${Math.round(num)} ms` : '—'
}

function sourceError(row: Record<string, any>): string {
  return text(row?.error ?? row?.error_summary) || '—'
}

function sourceCheckedAt(row: Record<string, any>): string {
  return shortTime(row?.checked_at ?? row?.updated_at ?? row?.at ?? row?.time ?? row?.created_at)
}

/** 读 `GET /scrape/log?limit=50`（流水 + summary）。 */
async function loadLog(): Promise<void> {
  if (logLoading.value) return
  logLoading.value = true
  logError.value = ''
  sourcesLoaded.value = true
  try {
    const payload: any = await getJson('plugin/scrape/log', { limit: 50 })
    logItems.value = Array.isArray(payload?.items) ? payload.items : []
    logSummary.value = Array.isArray(payload?.summary) ? payload.summary : []
  } catch (err) {
    logItems.value = []
    logSummary.value = []
    logError.value = errorText(err)
  } finally {
    logLoading.value = false
  }
}

/**
 * 「立即自检」：契约 §3.7 **没有**触发式自检端点，所以这里如实重读一次
 * `GET /scrape/status`（各源的最近状态就是它给的），顺带把流水也刷新一遍。
 */
async function refreshSelfcheck(): Promise<void> {
  if (busy.value) return
  busy.value = 'selfcheck'
  t.info('正在重新读取各数据源状态…')
  try {
    await loadStatus()
    await loadLog()
    if (statusError.value) t.warning(`状态读取失败：${statusError.value}`)
    else t.success('已刷新各数据源状态')
  } finally {
    busy.value = ''
  }
}

// ---------------------------------------------------------------- 展示小工具

/** 行的版本角标（与 `LibraryView` / `DownloadsView` 同一口径：数组或字典都认，缺字段不画）。 */
function badgeOf(row: WorkRow): string {
  const direct = text(row.raw?.badge).trim()
  if (direct) return direct
  const tags = row.versionTags
  if (Array.isArray(tags)) return tags.map(item => text(item)).filter(Boolean).join('/')
  if (tags && typeof tags === 'object') {
    const dict = tags as Record<string, any>
    const out: string[] = []
    if (dict.is_zh_sub) out.push('中字')
    if (dict.is_uncensored_leak) out.push('流出')
    const res = text(dict.resolution).trim()
    if (res) out.push(/2160|4k/i.test(res) ? '4K' : res.toUpperCase())
    if (dict.is_iso) out.push('ISO')
    if (dict.is_vr) out.push('VR')
    return out.join('/')
  }
  return ''
}

function logStatusColor(status: unknown): string {
  const value = text(status).toLowerCase()
  if (value === 'ok' || value === 'success') return 'success'
  if (value === 'error' || value === 'failed' || value === 'fail') return 'error'
  return 'info'
}
</script>

<template>
  <div class="avh-scrape">
    <div class="avh-scrape__toolbar">
      <div class="avh-tabs">
        <button
          v-for="item in TABS"
          :key="item.key"
          :class="{ 'avh-tabs__on': item.key === tab }"
          @click="pickTab(item.key)"
        >{{ item.name }}</button>
      </div>

      <span v-if="tab === 'workbench'" class="avh-scrape__hint">
        行内「刮削」写 Emby（先落备份，可回滚）· 列表来源：{{
          listSource === 'library' ? 'GET /library（/scrape/status 没有 items）'
            : listSource === 'status' ? 'GET /scrape/status'
              : '暂无（两个端点都没读到）'
        }}
      </span>
      <span v-else class="avh-scrape__hint">各源最近状态取自 GET /scrape/status · 流水取自 GET /scrape/log</span>

      <div class="avh-scrape__spacer" />

      <v-btn
        variant="outlined"
        size="small"
        :loading="loading"
        @click="load(true)"
      >↻ 刷新</v-btn>
    </div>

    <!-- ================= 页签 1：全库刮削工作台 ================= -->
    <template v-if="tab === 'workbench'">
      <!-- 状态卡片：点一下筛选，再点一下取消；「全部」清筛选 -->
      <div class="avh-stats">
        <div
          v-for="key in STATUS_ORDER"
          :key="key"
          class="avh-stat"
          :class="{ 'avh-stat--on': filter === key }"
          :title="STATUS_META[key].hint"
          @click="toggleFilter(key)"
        >
          <div class="avh-stat__num">{{ stats[key] }}</div>
          <div class="avh-stat__label">{{ STATUS_META[key].label }}</div>
        </div>
        <div
          class="avh-stat"
          :class="{ 'avh-stat--on': filter === '' }"
          title="全部（点一下清掉筛选）"
          @click="filter = ''"
        >
          <div class="avh-stat__num">{{ stats.total }}</div>
          <div class="avh-stat__label">全部</div>
        </div>
      </div>

      <div class="avh-scrape__meta">
        <span class="avh-scrape__hint">
          定时重刮队列：Tier 1 {{ queueInfo.tier1 === null ? '—' : queueInfo.tier1 }} ·
          Tier 2 {{ queueInfo.tier2 === null ? '—' : queueInfo.tier2 }} ·
          上次运行 {{ lastRun || '—' }}
        </span>
        <span v-if="filter" class="avh-scrape__hint">· 正在筛选「{{ filterLabel }}」（{{ visibleRows.length }} 条）</span>
      </div>

      <ErrorState
        v-if="error && !rows.length"
        :message="`刮削状态读取失败：${error}`"
        :retrying="loading"
        @retry="load(false)"
      />

      <v-alert
        v-else-if="error && rows.length"
        type="warning"
        variant="tonal"
        density="compact"
        class="text-caption mb-2"
      >{{ error }}（列表已回落到 GET /library）</v-alert>

      <div v-if="runResult" class="mb-2">
        <v-alert
          :type="runResult.ok ? 'success' : 'warning'"
          variant="tonal"
          density="compact"
          class="text-caption"
        >
          <div>{{ runResult.text }}</div>
          <div v-for="(line, index) in runResult.errors" :key="index">{{ line }}</div>
        </v-alert>
      </div>

      <div v-if="rows.length" class="avh-scrape__actions">
        <v-checkbox
          :model-value="allVisibleSelected"
          density="compact"
          hide-details
          label="全选当前列表"
          class="avh-scrape__checkall"
          @update:model-value="toggleAll"
        />
        <v-btn
          color="primary"
          variant="flat"
          size="small"
          prepend-icon="mdi-auto-fix"
          :disabled="!selected.size || !!busy"
          :loading="busy === 'run:batch'"
          @click="runSelected"
        >批量刮削（{{ selected.size }}）</v-btn>
        <span class="avh-scrape__hint">批量会先弹一次确认，文案里写明「将写入 Emby」</span>
      </div>

      <div v-if="loading && !rows.length" class="avh-scrape__loading">正在读取刮削状态…</div>

      <EmptyState
        v-else-if="!rows.length && !error"
        text="还没有可刮削的条目<br>后端把 meta 表建起来、或 Emby 库里已有影片后，这里会按状态列出全部番号"
        hint="本页数据来自 GET /scrape/status（items）与 GET /library；接口没上线时只会看到这句空态"
      />

      <EmptyState
        v-else-if="!visibleRows.length && filter"
        text="该状态下没有条目"
        hint="点顶部「全部」清掉筛选"
      />

      <div v-else-if="visibleRows.length" class="avh-tablewrap">
        <table class="avh-table">
          <colgroup>
            <col style="width:36px">
            <col style="width:152px">
            <col>
            <col style="width:96px">
            <col style="width:80px">
            <col style="width:178px">
            <col style="width:190px">
          </colgroup>
          <thead>
            <tr>
              <th />
              <th>番号</th>
              <th>标题</th>
              <th>状态</th>
              <th>备份</th>
              <th>裁切锚点</th>
              <th class="avh-table__right">操作</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="row in visibleRows" :key="rowId(row)">
              <td>
                <v-checkbox
                  :model-value="isSelected(row)"
                  density="compact"
                  hide-details
                  @update:model-value="toggleRow(row)"
                />
              </td>
              <td class="avh-table__num">
                {{ row.number }}
                <span v-if="badgeOf(row)" class="avh-vbadge avh-vbadge--inline">{{ badgeOf(row) }}</span>
              </td>
              <td :title="row.title">{{ row.title || '—' }}</td>
              <td>
                <v-chip size="x-small" :color="STATUS_META[row.status].color" variant="tonal">
                  {{ STATUS_META[row.status].label }}
                </v-chip>
                <span v-if="row.statusRaw && row.statusRaw !== row.status" class="avh-scrape__hint">
                  {{ row.statusRaw }}
                </span>
              </td>
              <td>
                <span v-if="row.hasBackup === true" class="avh-scrape__ok">有</span>
                <span v-else-if="row.hasBackup === false" class="avh-scrape__bad">无</span>
                <span v-else class="avh-scrape__hint">—</span>
              </td>
              <td>
                <v-select
                  :model-value="anchorOf(row)"
                  :items="ANCHOR_OPTIONS"
                  item-title="title"
                  item-value="value"
                  density="compact"
                  variant="outlined"
                  hide-details
                  @update:model-value="(value: any) => setAnchor(row, String(value))"
                />
              </td>
              <td class="avh-table__right">
                <div class="avh-rowbtns">
                  <v-btn size="x-small" variant="outlined" @click="openPreview(row)">预览</v-btn>
                  <v-btn
                    size="x-small"
                    variant="outlined"
                    color="primary"
                    :loading="busy === `run:${rowId(row)}`"
                    :disabled="!!busy"
                    @click="runOne(row)"
                  >刮削</v-btn>
                  <v-btn
                    size="x-small"
                    variant="outlined"
                    color="warning"
                    :disabled="rollbackDisabled(row) || !!busy"
                    :title="rollbackHint(row)"
                    @click="rollback(row)"
                  >回滚</v-btn>
                </div>
              </td>
            </tr>
          </tbody>
        </table>
      </div>

      <p class="avh-scrape__hint mt-2">
        裁切锚点是<strong>每行草稿</strong>：改了之后点这一行的「刮削」才会随 <code>anchor</code> 提交给后端（<code>POST /scrape/run</code>）。
        行内「回滚」在 <code>has_backup === false</code> 时禁用并提示「无 Emby 备份，无法回滚」。
      </p>
    </template>

    <!-- ================= 页签 2：数据源自检 ================= -->
    <template v-else>
      <div class="avh-scrape__actions">
        <v-btn
          color="primary"
          variant="flat"
          size="small"
          prepend-icon="mdi-stethoscope"
          :loading="busy === 'selfcheck'"
          :disabled="!!busy && busy !== 'selfcheck'"
          @click="refreshSelfcheck"
        >立即自检</v-btn>
        <span class="avh-scrape__hint">
          契约 §3.7 没有触发式自检端点，这里如实重新读取 <code>GET /scrape/status</code> 的
          <code>sources</code>（各源最近状态就是它给的）
        </span>
      </div>

      <v-alert
        v-if="statusError"
        type="warning"
        variant="tonal"
        density="compact"
        class="text-caption mb-2"
      >状态读取失败：{{ statusError }}</v-alert>

      <div class="avh-scrape__secttl">数据源（{{ sources.length }}）</div>
      <div v-if="sources.length" class="avh-tablewrap">
        <table class="avh-table">
          <colgroup>
            <col style="width:150px">
            <col style="width:96px">
            <col style="width:88px">
            <col>
            <col style="width:130px">
          </colgroup>
          <thead>
            <tr>
              <th>源</th>
              <th>最近状态</th>
              <th>耗时</th>
              <th>错误摘要</th>
              <th>检查时间</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="(row, index) in sources" :key="`${sourceName(row)}#${index}`">
              <td>{{ sourceName(row) }}</td>
              <td>
                <v-chip size="x-small" :color="sourceState(row).color" variant="tonal">
                  {{ sourceState(row).text }}
                </v-chip>
              </td>
              <td>{{ latencyText(row?.latency_ms ?? row?.latency ?? row?.ms) }}</td>
              <td class="avh-table__ellipsis" :title="sourceError(row)">{{ sourceError(row) }}</td>
              <td>{{ sourceCheckedAt(row) }}</td>
            </tr>
          </tbody>
        </table>
      </div>
      <EmptyState
        v-else
        text="还没有数据源状态"
        hint="GET /scrape/status 的 sources 为空（接口没上线，或后端还没跑过自检）"
      />

      <div class="avh-scrape__secttl">
        <span>最近流水（{{ logItems.length }}）</span>
        <span v-if="logSummary.length" class="avh-scrape__hint">summary {{ logSummary.length }} 组</span>
        <v-btn
          variant="text"
          size="x-small"
          class="ms-2"
          :loading="logLoading"
          @click="loadLog"
        >↻ 重新读取</v-btn>
      </div>

      <v-alert
        v-if="logError"
        type="warning"
        variant="tonal"
        density="compact"
        class="text-caption mb-2"
      >流水读取失败（GET /scrape/log）：{{ logError }}</v-alert>

      <div v-if="logItems.length" class="avh-tablewrap">
        <table class="avh-table">
          <colgroup>
            <col style="width:120px">
            <col style="width:88px">
            <col style="width:130px">
            <col style="width:88px">
            <col>
            <col style="width:130px">
          </colgroup>
          <thead>
            <tr>
              <th>源</th>
              <th>状态</th>
              <th>番号</th>
              <th>耗时</th>
              <th>错误</th>
              <th>时间</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="(row, index) in logItems" :key="`${row?.created_at || ''}#${index}`">
              <td>{{ sourceName(row) }}</td>
              <td>
                <v-chip size="x-small" :color="logStatusColor(row?.status)" variant="tonal">
                  {{ text(row?.status) || '—' }}
                </v-chip>
              </td>
              <td>{{ text(row?.key) || '—' }}</td>
              <td>{{ latencyText(row?.latency_ms) }}</td>
              <td class="avh-table__ellipsis" :title="text(row?.error)">{{ text(row?.error) || '—' }}</td>
              <td>{{ shortTime(row?.created_at) }}</td>
            </tr>
          </tbody>
        </table>
      </div>
      <div v-else-if="!logLoading && !logError" class="avh-scrape__hint">还没有流水记录。</div>

      <div v-if="logSummary.length" class="avh-scrape__secttl">summary</div>
      <div v-if="logSummary.length" class="avh-tablewrap">
        <table class="avh-table">
          <thead>
            <tr>
              <th>源</th>
              <th>条数</th>
              <th>失败</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="(row, index) in logSummary" :key="`sum#${index}`">
              <td>{{ sourceName(row) }}</td>
              <td>{{ text(row?.count ?? row?.total ?? '—') }}</td>
              <td>{{ text(row?.failed ?? row?.errors ?? '—') }}</td>
            </tr>
          </tbody>
        </table>
      </div>
    </template>

    <!-- ================= 字段级 diff 预览 ================= -->
    <v-dialog v-model="preview.open" max-width="880" scrollable>
      <v-card>
        <v-toolbar density="comfortable" color="surface">
          <v-icon icon="mdi-compare-horizontal" color="primary" class="ms-2" />
          <v-toolbar-title class="text-body-1">
            刮削预览 · {{ preview.number || preview.key }}
          </v-toolbar-title>
          <v-spacer />
          <v-chip v-if="!preview.loading && !preview.error" size="small" variant="tonal" class="me-2">
            变更 {{ previewChanged }} / {{ preview.fields.length }} 项
          </v-chip>
          <v-btn variant="text" icon="mdi-close" @click="preview.open = false" />
        </v-toolbar>

        <v-divider />

        <v-card-text>
          <div v-if="preview.loading" class="avh-scrape__loading">正在计算字段差异…</div>

          <v-alert
            v-else-if="preview.error"
            type="warning"
            variant="tonal"
            density="compact"
            class="text-caption"
          >预览失败（GET /scrape/preview）：{{ preview.error }}</v-alert>

          <template v-else>
            <v-alert
              v-for="(line, index) in preview.warnings"
              :key="`warn#${index}`"
              type="warning"
              variant="tonal"
              density="compact"
              class="text-caption mb-2"
            >{{ line }}</v-alert>

            <div v-if="preview.fields.length" class="avh-tablewrap">
              <table class="avh-table avh-table--diff">
                <colgroup>
                  <col style="width:150px">
                  <col>
                  <col>
                </colgroup>
                <thead>
                  <tr>
                    <th>字段</th>
                    <th>当前值</th>
                    <th>目标值</th>
                  </tr>
                </thead>
                <tbody>
                  <tr
                    v-for="field in preview.fields"
                    :key="field.name"
                    :class="{ 'avh-diff__changed': field.changed }"
                  >
                    <td>
                      <span>{{ field.name }}</span>
                      <v-chip v-if="field.changed" size="x-small" color="warning" variant="tonal" class="ms-1">
                        有变化
                      </v-chip>
                    </td>
                    <td class="avh-diff__cell">{{ field.current }}</td>
                    <td class="avh-diff__cell">{{ field.target }}</td>
                  </tr>
                </tbody>
              </table>
            </div>
            <EmptyState
              v-else
              text="没有可预览的字段"
              hint="GET /scrape/preview 返回的 fields 里没有条目（或后端还没算）"
            />

            <div v-if="preview.sources" class="avh-scrape__secttl">本次取值来源</div>
            <div v-if="preview.sources" class="avh-srcgrid">
              <div v-for="(value, key) in preview.sources" :key="String(key)" class="avh-srcgrid__item">
                <span class="avh-srcgrid__k">{{ key }}</span>
                <span>{{ valueText(value) }}</span>
              </div>
            </div>
          </template>
        </v-card-text>

        <v-divider />
        <v-card-actions>
          <span class="avh-scrape__hint">
            预览不写任何东西；点下面那颗才真正写 Emby（先落备份）。
          </span>
          <v-spacer />
          <v-btn variant="text" @click="preview.open = false">关闭</v-btn>
        </v-card-actions>
      </v-card>
    </v-dialog>
  </div>
</template>

<style scoped>
/* 与下载页/订阅页同一套工具条几何 */
.avh-scrape__toolbar {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
  margin-bottom: 12px;
}

.avh-scrape__hint {
  font-size: 12px;
  color: rgba(var(--v-theme-on-surface), 0.5);
}

.avh-scrape__spacer {
  flex: 1;
}

.avh-scrape__meta {
  display: flex;
  align-items: baseline;
  gap: 8px;
  flex-wrap: wrap;
  margin-bottom: 10px;
}

.avh-scrape__actions {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
  margin-bottom: 10px;
}

.avh-scrape__checkall {
  flex: none;
  max-width: 190px;
}

.avh-scrape__loading {
  padding: 44px 20px;
  text-align: center;
  font-size: 13px;
  color: rgba(var(--v-theme-on-surface), 0.5);
}

/* 状态卡片（照发现榜单那组 tabs 的胶囊观感，改成可点的方块） */
.avh-stats {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(108px, 1fr));
  gap: 10px;
  margin-bottom: 10px;
}

.avh-stat {
  padding: 10px 12px;
  cursor: pointer;
  border: 1px solid rgba(var(--v-theme-on-surface), 0.12);
  border-radius: 10px;
  background: rgba(var(--v-theme-on-surface), 0.04);
  transition: 0.15s;
}

.avh-stat:hover {
  border-color: rgb(var(--v-theme-primary));
}

.avh-stat--on {
  border-color: rgb(var(--v-theme-primary));
  background: rgba(var(--v-theme-primary), 0.16);
}

.avh-stat__num {
  font-size: 20px;
  font-weight: 700;
  line-height: 1.2;
}

.avh-stat__label {
  font-size: 12px;
  color: rgba(var(--v-theme-on-surface), 0.6);
}

/* 表格（`table-layout: fixed` + 显式列宽：宽屏不把「操作」列挤出去，照 S6 候选表的教训） */
.avh-tablewrap {
  overflow-x: auto;
}

.avh-table {
  width: 100%;
  table-layout: fixed;
  border-collapse: collapse;
  font-size: 12.5px;
}

.avh-table th,
.avh-table td {
  padding: 6px 8px;
  text-align: left;
  vertical-align: middle;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  border-bottom: 1px solid rgba(var(--v-theme-on-surface), 0.08);
}

.avh-table th {
  font-weight: 600;
  color: rgba(var(--v-theme-on-surface), 0.6);
  border-bottom: 1px solid rgba(var(--v-theme-on-surface), 0.16);
}

.avh-table__right {
  text-align: right;
}

.avh-table__num {
  font-weight: 600;
}

.avh-table__ellipsis {
  max-width: 0;
}

.avh-rowbtns {
  display: flex;
  gap: 4px;
  justify-content: flex-end;
}

.avh-scrape__secttl {
  display: flex;
  align-items: baseline;
  gap: 10px;
  margin: 18px 0 8px;
  font-size: 12px;
  letter-spacing: 0.4px;
  color: rgba(var(--v-theme-on-surface), 0.5);
}

.avh-scrape__ok {
  color: rgb(var(--v-theme-success));
}

.avh-scrape__bad {
  color: rgb(var(--v-theme-error));
}

/* 版本角标（与 `LibraryView` / `DownloadsView` 同一套观感） */
.avh-vbadge {
  display: inline-block;
  padding: 1px 6px;
  font-size: 10px;
  font-weight: 500;
  border-radius: 4px;
  color: #fff;
  background: rgba(var(--v-theme-secondary), 0.9);
  border: 1px solid rgba(255, 255, 255, 0.14);
}

.avh-vbadge--inline {
  margin-left: 4px;
}

/* diff 表：`changed` 的行整行高亮（当前值/目标值两列都看得见） */
.avh-table--diff td {
  white-space: normal;
  word-break: break-word;
  vertical-align: top;
}

.avh-diff__changed {
  background: rgba(var(--v-theme-warning), 0.16);
}

.avh-diff__cell {
  font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
  font-size: 12px;
  line-height: 1.6;
}

.avh-srcgrid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
  gap: 6px 16px;
}

.avh-srcgrid__item {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: 10px;
  font-size: 12px;
}

.avh-srcgrid__k {
  color: rgba(var(--v-theme-on-surface), 0.6);
}

/* 页签胶囊：与「下载」栏那组同一套（两份 scoped CSS 各有作用域，本项目既有做法） */
.avh-tabs {
  display: flex;
  gap: 4px;
  padding: 3px;
  border: 1px solid rgba(var(--v-theme-on-surface), 0.12);
  border-radius: 8px;
  background: rgba(var(--v-theme-on-surface), 0.04);
}

.avh-tabs button {
  padding: 4px 12px;
  font-size: 12px;
  color: rgba(var(--v-theme-on-surface), 0.5);
  background: none;
  border: 0;
  border-radius: 6px;
  cursor: pointer;
}

.avh-tabs__on {
  color: rgb(var(--v-theme-on-primary)) !important;
  background: rgb(var(--v-theme-primary)) !important;
}
</style>
