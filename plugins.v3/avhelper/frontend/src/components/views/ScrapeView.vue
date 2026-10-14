<script setup lang="ts">
/**
 * 视图：刮削（数据台第八栏，v4 刮削线 S9 新增）。
 *
 * 两个页签（契约 §3.8 / v4.1 §10.2）：
 * 1. **全库刮削工作台** —— 首屏「搜索刮削」入口（`common/SearchScrapePanel.vue`）+
 *    顶部状态卡片（`full` / `missing_plot` / `missing_core` / `unscraped` / `total`，
 *    点一下筛选）、行列表（番号 / 标题 / 状态徽标 / 预览·刮削）、
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
 * | 单条 / 批量刮削 | `POST /scrape/run {keys?, all?, force?, confirm?}` |
 * | 流水 | `GET /scrape/log?limit=50` |
 * | 同步演员头像 | `POST /scrape/avatars {dry_run?, limit?, names?}` |
 *
 * `items[]` 的字段名由主统筹 2026-10-14 定死：
 * `{key, number, title, emby_id, completeness, scrape_state, has_backup, crop_anchor, version_tags[], updated_at}`
 * —— 缺字段一律容错（`—` / 不画），**不猜**。本视图只消费 `key` / `number` / `title` / `emby_id` /
 * `completeness` / `scrape_state` / `version_tags` / `updated_at`；`has_backup` / `crop_anchor` 仍由
 * 后端返回与使用（写前留底闸门、裁切自判），但**界面不展示、也不再提交**（见下条）。
 *
 * 五处刻意的口径（都有实测/裁决依据，改之前先读文档）：
 * - **「立即自检」只重读 `GET /scrape/status`**：契约 §3.7 **没有**触发式自检端点
 *   （`scraper.sources_selfcheck()` 是 Python 侧函数），所以这里把「刷新各源最近状态」如实
 *   说成「重新读取 `/scrape/status`」，不发明端点名。
 * - **批量刮削必须二次确认**（宿主 `moviepilot:confirm`，拿不到就 `window.confirm` 降级），
 *   文案写明「将写入 Emby」；载荷带 `confirm: true`（后端对 `all=true` 要求它）。
 * - **2026-10-15 界面减负**（用户要求「裁切锚点不需要出现、备份这些也都可以取消掉」）：
 *   锚点固定 `auto`、由后端裁切逻辑自判，界面不出现，`POST /scrape/run` 也不带 `anchor`；
 *   行内「回滚」按钮与「备份」列一并撤掉，文案不再提备份/回滚。**写前留底闸门
 *   （`has_backup`）与 `POST /scrape/rollback` 端点在后端原样保留**——只是界面不给入口。
 * - **2026-10-16 手动刮削改搜索式交互**（用户原话要义：「手动刮削预览信息过多；希望像搜索
 *   一样只显示几个搜到的结果；找到想要的点确认，数据直接导入；自动刮削无所谓」）：
 *   工作台首屏多一个**「搜索刮削」入口**（`common/SearchScrapePanel.vue`：输入番号或关键词 →
 *   回车即搜 `GET /search` → 只列几条候选卡片 → 点一条出**精简确认卡**（只画将写入的
 *   中文标题 / 原名 / 演员数 / 封面缩略 / 发行日）→ 「确认导入」走 `POST /scrape/run`）。
 *   **`GET /scrape/preview` 与字段级 diff 表原样保留，只是降级为默认收起的「高级」折叠**
 *   （展开后点一下才请求），行内那颗「预览」按钮也改由该面板承载 —— 全页只有一份 diff 表实现，
 *   所以本文件不再持有预览状态。**自动刮削（Tier 1/2 定时）相关交互一律未动**（用户："无所谓"）。
 * - **2026-10-16「同步演员头像」按钮（P8，方案 §2.6）**：工具栏那颗按钮接 `POST /scrape/avatars`，
 *   走**两段式**：点一下先弹一次宿主二次确认（写明会向 Emby 的 **Person 实体**上传头像、且下一步
 *   的 `dry_run` **零写请求**）→ `{dry_run:true}` 只读拿计划、把「上传 N / 跳过 M / 失败 K」摆到
 *   结果条上 → 再确认一次才 `{dry_run:false}` 真写。计划里 `up === 0` 时**不再问第二遍**
 *   （没有要写的东西，真跑只会把同一份只读计划重算一遍），计划本身照常留在结果条上。
 *   结果文案固定含「上传 N / 跳过 M / 失败 K」，另有一行说明 `gender_unknown`（旧数据缺 gender
 *   会保守跳过、重刮后自然补齐）与 `missing_person`（都不算失败），`errors` 只摆前几条。
 *
 * 降级纪律（本线的硬要求）：接口 404 / 网络失败 / 字段缺失 → 空态或错误态 + 一句原因，
 * **不白屏、不抛未捕获异常**、不因为一个端点坏了就把另一块也画成坏的（两块各自 try/catch）。
 */
import { computed, ref } from 'vue'
import EmptyState from '../common/EmptyState.vue'
import ErrorState from '../common/ErrorState.vue'
import SearchScrapePanel from '../common/SearchScrapePanel.vue'
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

/** `item_key` 缺省时按契约 §4 的格式从 `emby_id` 拼（`emby:<id>`）——勾选与选中集的去重身份。 */
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
  return {
    key,
    number: number || key,
    title: text(row.title),
    embyId: text(row.emby_id || row.embyId),
    itemKey: itemKeyOf(row),
    status: status.key,
    statusRaw: status.raw,
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

// ---------------------------------------------------------------- 筛选 / 选择

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

/**
 * 字段级 diff 已**降级为搜索面板里的「高级」折叠**（0.7.2）：预览状态、请求与那张
 * diff 表全部搬到了 `common/SearchScrapePanel.vue`，本视图的行内按钮只把番号交给它。
 *
 * 为什么不留两份：`GET /scrape/preview` 的回包同时喂着「确认卡的关键字段」与「diff 表」，
 * 分成两处持有就会出现"刚看过的那份值"和"确认卡上那份值"不一致。全页一份实现，
 * 行内「预览」与折叠里的「预览字段差异」也就天然同源。
 */
const pickRef = ref<InstanceType<typeof SearchScrapePanel> | null>(null)

function openPreview(row: WorkRow): void {
  void pickRef.value?.openPreview({ key: row.key, number: row.number })
}

// ---------------------------------------------------------------- 刮削

/** 在飞的动作（`''` = 空闲）：给对应按钮转圈，避免重复点。 */
const busy = ref('')

/**
 * 结果条的形状：一行结论 +（可省的）补充说明 + 失败明细。
 *
 * 结果条是**全页共用**的（批量/单条刮削、头像同步都往 `runResult` 里写），
 * 所以 `notes` 是可选字段：没给的调用方渲染出来与从前逐字节相同。
 */
interface ActionResult {
  ok: boolean
  text: string
  notes?: string[]
  errors: string[]
}

/** 最近一次批量/单条刮削（或头像同步）的结论（跑完留在页面上，别只靠 toast）。 */
const runResult = ref<ActionResult | null>(null)

/** `POST /scrape/run` 的结论 → 一句话 + 失败明细。 */
function summarizeRun(payload: any): ActionResult {
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
 * 批量「刮削选中」：**必须二次确认**（会写 Emby），文案写明「将写入 Emby」。
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
      `将写入 Emby：共 ${keys.length} 部影片。\n\n` +
      '插件会向这些影片写入标题 / 原名 / 简介 / 演员 / 封面 / 发行日等字段，' +
      '覆盖它们在 Emby 里的现有取值。确认现在开始？',
    confirmText: '开始刮削',
    cancelText: '取消',
  })
  if (!ok) return
  busy.value = 'run:batch'
  runResult.value = null
  t.info(`正在批量刮削 ${keys.length} 部…`)
  try {
    const body: Record<string, unknown> = { keys, all: false, force: false, confirm: true }
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

// ---------------------------------------------------------------- 同步演员头像（P8 / 方案 §2.6）

/**
 * 头像同步的条数（`POST /scrape/avatars` 回包归一）。
 *
 * 后端回 `{ok, dry_run, actors, planned[], applied[], errors[], missing_person, gender_unknown}`，
 * `planned[]` 每条是 `{name, person_id, action, reason, url?, source?}`，`action` 三态：
 * - `upload_avatar`：**要上传 / 已上传**（`dry_run` 时是"将上传"；真跑时成功的那些同时还进 `applied[]`）；
 * - `skip`：如实跳过（`has_image` 已有头像 / `person_missing` 还没建过 Person 实体 / `no_avatar` 两源都无图）；
 * - `failed`：取图或上传失败（真跑时是**由 `upload_avatar` 改写过来**的）。
 *
 * 所以「上传 N / 跳过 M / 失败 K」直接数 `planned[]` 的三种 `action` —— dry-run 与真跑**同一套计数**
 * （方案 §2.6 的验收要求就是"dry-run 报告与实际一致"）。性别过滤掉的演员**不在 `planned[]` 里**
 * （男演员不计数，缺 gender 的进 `gender_unknown`），所以那部分要单独说明，不能并进"跳过"。
 */
interface AvatarCounts {
  up: number
  skip: number
  fail: number
  missing: number
  genderUnknown: number
  errors: string[]
}

function countAvatarActions(payload: any): AvatarCounts {
  const num = (value: unknown) => (Number.isFinite(Number(value)) ? Number(value) : 0)
  const planned = Array.isArray(payload?.planned) ? payload.planned : []
  const applied = Array.isArray(payload?.applied) ? payload.applied : []
  let up = 0
  let skip = 0
  let fail = 0
  for (const entry of planned) {
    const action = text(entry?.action)
    if (action === 'upload_avatar') up += 1
    else if (action === 'failed') fail += 1
    else skip += 1
  }
  // 防御：回包形状变了（`planned` 不在）时，真跑的结果还能靠 `applied` 说清"传了几张"
  if (!up && !planned.length && applied.length) up = applied.length
  const errors = (Array.isArray(payload?.errors) ? payload.errors : []).map(item => text(item)).filter(Boolean)
  return {
    up,
    skip,
    fail,
    missing: num(payload?.missing_person),
    genderUnknown: num(payload?.gender_unknown),
    errors,
  }
}

/** 结论行：**必须含「上传 N / 跳过 M / 失败 K」**（方案 §2.6 指定的文案口径）。 */
function avatarText(counts: AvatarCounts, dryRun: boolean): string {
  const line = `上传 ${counts.up} / 跳过 ${counts.skip} / 失败 ${counts.fail}`
  return dryRun ? `同步计划（dry_run，零写请求）：${line}` : line
}

/**
 * 补充说明（既不是失败也不算"跳过"的那些）：`gender_unknown` 与 `missing_person`。
 *
 * `gender_unknown` **照实报数**（0 也画）——它是"旧数据缺 gender 保守跳过"的口径本身，
 * 用户看到 0 才知道这次不是被它挡住的；`missing_person` 只在非 0 时说一句，免得刷屏。
 */
function avatarNotes(counts: AvatarCounts): string[] {
  const notes = [
    `缺 gender 的旧数据保守跳过 ${counts.genderUnknown} 位（不算失败；那条影片重刮一遍后自然补齐）`,
  ]
  if (counts.missing > 0) {
    notes.push(`跳过里 ${counts.missing} 位还没在 Emby 建过 Person 实体（影片 People 写对后自会收敛）`)
  }
  return notes
}

/** 失败明细只摆前几条（`errors` 可能上百条，全铺出来会把页面顶烂）。 */
function headErrors(errors: string[]): string[] {
  const head = errors.slice(0, 5)
  if (errors.length > head.length) head.push(`…… 另有 ${errors.length - head.length} 条失败明细（后端日志里有全部）`)
  return head
}

/** 一次头像回包 → 结果条（同一份归一喂给 dry_run 计划与真跑结论；`extraNotes` 是本次额外要说的话）。 */
function avatarResult(counts: AvatarCounts, dryRun: boolean, extraNotes: string[] = []): ActionResult {
  return {
    ok: counts.fail === 0 && !counts.errors.length,
    text: avatarText(counts, dryRun),
    notes: [...avatarNotes(counts), ...extraNotes],
    errors: headErrors(counts.errors),
  }
}

/**
 * 「同步演员头像」：**两段式**（方案 §2.6）——先问一次（写明会写 Emby 的 Person 实体、
 * 下一步的 `dry_run` 零写请求）→ `{dry_run:true}` 只读拿计划并把条数摆到结果条上 →
 * 再问一次 → `{dry_run:false}` 真跑。
 *
 * 计划里 `up === 0`（全都有头像了 / 还没建过 Person 实体 / 两源都没图 / 没配 Emby）时
 * **不再问第二遍**：没有要写的东西，真跑只会把同一份只读计划重算一遍；计划与 `errors`
 * 照常留在结果条上，用户一眼能看出是被什么挡住的。
 */
async function syncAvatars(): Promise<void> {
  if (busy.value) return
  const proceed = await confirm({
    type: 'warn',
    title: '同步演员头像',
    content:
      '这一步只读：先跑一次 dry_run 计划，零写请求，不会向 Emby 写任何东西。\n\n' +
      '真正的上传在你看到计划条数、再确认一次之后才发生：届时会把头像写进 Emby 的 Person 实体' +
      '（Person 的 Primary 图，必要时合并写 ProviderIds.JavDB）。已经写过头像的 Person 会跳过。',
    confirmText: '先看计划',
    cancelText: '取消',
  })
  if (!proceed) return
  busy.value = 'avatars'
  runResult.value = null
  try {
    t.info('正在读取头像同步计划（dry_run，零写请求）…')
    let plan: AvatarCounts
    try {
      const planPayload: any = await postJson('plugin/scrape/avatars', { dry_run: true })
      plan = countAvatarActions(planPayload)
    } catch (err) {
      runResult.value = { ok: false, text: '头像同步计划读取失败', errors: [errorText(err)] }
      t.warning(`头像同步计划读取失败：${errorText(err)}`)
      return
    }
    runResult.value = avatarResult(plan, true, plan.up
      ? []
      : ['本次没有需要上传的头像（已经写过的、还没建过 Person 实体的都会跳过）'])
    if (!plan.up) {
      t.info(`没有需要上传的头像：上传 0 / 跳过 ${plan.skip} / 失败 ${plan.fail}`)
      return
    }
    const go = await confirm({
      type: 'warn',
      title: '同步演员头像（写入 Emby）',
      content:
        `dry_run 计划：上传 ${plan.up} / 跳过 ${plan.skip} / 失败 ${plan.fail}。\n\n` +
        `确认后真的开始上传：把这 ${plan.up} 张头像写进 Emby 的 Person 实体（Primary 图）；` +
        `计划里已跳过的 ${plan.skip} 位不会动，也没有别的写入。`,
      confirmText: `上传 ${plan.up} 张`,
      cancelText: '取消',
    })
    if (!go) {
      t.info('已取消，没有向 Emby 写入任何东西')
      return
    }
    t.info(`正在上传 ${plan.up} 张头像…`)
    const payload: any = await postJson('plugin/scrape/avatars', { dry_run: false })
    const done = countAvatarActions(payload)
    runResult.value = avatarResult(done, false)
    if (runResult.value.ok) t.success(`头像同步完成：${avatarText(done, false)}`)
    else t.warning(`头像同步未全部成功：${avatarText(done, false)}`)
  } catch (err) {
    runResult.value = { ok: false, text: '头像同步请求失败', errors: [errorText(err)] }
    t.warning(`头像同步失败：${errorText(err)}`)
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
        搜索刮削走 GET /search · 行内「刮削」与「确认导入」同一条写入链路 ·
        列表来源：{{
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
      <!--
        搜索刮削入口（0.7.2，首屏第一块）：输入番号或关键词 → 候选卡片 → 精简确认卡 → 确认导入。
        `GET /scrape/preview` 与字段级 diff 表在这个组件里降级为默认收起的「高级」折叠；
        行内「预览」按钮也走它的 `openPreview()`（`ref` 见 `<script>` 里的 `pickRef`）。
      -->
      <SearchScrapePanel
        ref="pickRef"
        :api="api"
        :plugin-id="pluginId"
        :toast="toast"
        @refresh-side="emit('refreshSide')"
        @done="load(false)"
      />

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
          <div v-for="(line, index) in runResult.notes || []" :key="`note#${index}`">{{ line }}</div>
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
        <!--
          同步演员头像（0.7.2，方案 §2.6）：**与上面的勾选无关**（整份 meta 索引），
          两段式 —— 先 dry_run 出计划（零写请求），确认后才写 Emby 的 Person 实体。
        -->
        <v-btn
          variant="outlined"
          size="small"
          prepend-icon="mdi-account-box-outline"
          :disabled="!!busy"
          :loading="busy === 'avatars'"
          @click="syncAvatars"
        >同步演员头像</v-btn>
        <span class="avh-scrape__hint">全库同步、与勾选无关 · 先 dry_run 出计划（零写请求），确认后才写 Person 实体</span>
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
            <col style="width:190px">
          </colgroup>
          <thead>
            <tr>
              <th />
              <th>番号</th>
              <th>标题</th>
              <th>状态</th>
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
                </div>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
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

    <!--
      字段级 diff 表（0.7.2）：**已搬进 `SearchScrapePanel.vue`** ——
      它默认收在「高级」折叠里，工作台行内「预览」与折叠里的按钮共用同一份实现与状态。
      这里不再放第二张表（原因见 `<script>` 里 `pickRef` 那段注释）。
    -->
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

/*
 * `.avh-table--diff` / `.avh-diff__changed` / `.avh-diff__cell` / `.avh-srcgrid*` 五条规则
 * 随 diff 表一起搬去了 `SearchScrapePanel.vue`（0.7.2）：scoped CSS 不会跨组件生效，
 * 留在这里就是五条永远选不中任何元素（本文件模板里已经没有 `--diff` / `srcgrid` 的类名了）。
 */

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
