<script setup lang="ts">
/**
 * 视图：演员库（数据台第九栏，0.9.0 演员线 S5 新增）。
 *
 * 方案依据：docs/AVHelper-演员刮削子系统方案.md §6「数据台演员详情（P2）：多图轮播 + 每图来源/尺寸
 * + 裁剪框 + 锁 + 重刮 + 资料字段」，以及 §「演员卡片墙（P2）」。
 *
 * 照抄了哪几处（**不要自创交互**）：
 * 1. 卡片墙 + 分段渲染 = `views/LibraryView.vue`（「已入库的番号」栏）：
 *    数据一次取回、只渲染前 60 张、滚到底自动追加（`usePagedList`）、末尾哨兵兼进度提示；
 *    空态 / 错误态 / 工具条 / 网格样式全部同一套。
 * 2. 卡片本体 = `common/ActorRow.vue`（老 `app.css` 的 `.actor` 卡：圆形头像 76×76、
 *    中文名主位、原名辅位），图片一律走 `common/Thumb.vue`（外网图必走 `/img?url=` 代理口径，
 *    **不直连图床**）。
 * 3. 「演员详情不是抽屉，而是同一个视图里换内容」= `views/ActorsView.vue` 的
 *    `renderActorDetail` 行为：顶部「← 返回」，返回后回到列表（筛选项与搜索词都保留）。
 * 4. 两段式写操作（先 `dry_run` 看计划、再确认应用）= `views/ScrapeView.vue` 的「同步演员头像」。
 *
 * 端点（后端契约原文，一个都不自己发明）：
 * | 用途 | 端点 |
 * | --- | --- |
 * | 卡片墙 | `GET /actor/list?q=&filter=&page=&limit=` → `{success, items[], total}` |
 * | 详情 | `GET /actor/detail?id=` → `{success, actor, numbers[], history[]}` |
 * | 重刮 | `POST /actor/scrape {id, dry_run, force}` → `{success, ok, dry_run, counts, items, errors}` |
 * | 裁剪 | `POST /actor/crop-avatar {id, rect}` → `{success, actor}` |
 * | 锁 | `POST /actor/lock {id, field:"images", on}` → `{success, actor}` |
 *
 * 三处刻意的口径：
 * - **筛选走服务端、搜索走本地**：`filter` ∈ `""` / `missing_avatar` / `locked` / `failed` 是后端真值
 *   （缺头像要跨表算），所以换筛选就重发一次请求；搜索框只过滤**本页已取回的那一批**（与
 *   「已入库的番号」栏同一口径：不为一次按键去打服务器）。
 * - **一次取 200 位、前端分批渲染**：契约本来就给了 `page`/`limit`，这一版先按「一次取一页、
 *   前端分段渲染」实现（与「已入库的番号」栏同一条纪律）；后端返回的 `total` 大于本页条数时，
 *   工具条如实写「共 N 位 · 本屏 200 位」，不假装全量都在。
 * - **裁剪不做前端图像编辑器**：只用「3:4 居中框 + 上下微调」算一个 `rect` 交给后端裁
 *   （方案 §5.6：默认 3:4，基于当前主图生成派生图并**前插**为主图，原图保留）。
 *   源图尺寸取自 `images[].w/h`；缺尺寸时**不发 rect**（由后端按默认 3:4 自判），界面上写明。
 */
import { computed, onMounted, ref } from 'vue'
import ActorRow from '../common/ActorRow.vue'
import EmptyState from '../common/EmptyState.vue'
import ErrorState from '../common/ErrorState.vue'
import Thumb from '../common/Thumb.vue'
import { usePagedList } from '../../composables/usePagedList'
import { errorText, hostToast, unwrap, type PluginApi } from '../../composables/usePluginApi'
import { useHostConfirm } from '../../composables/useHostDialogs'
import { shortTime } from '../../composables/storeTypes'

const props = withDefaults(
  defineProps<{
    /** 本插件实例 id：给 ActorRow / Thumb 拼图片代理地址用。 */
    pluginId?: string
    /** 宿主请求器（壳已补插件 id）：本视图所有请求都走它。 */
    api?: PluginApi | null
    /** 宿主 toast（moviepilot:toast 注入），拿不到时静默降级。 */
    toast?: unknown
    /** 壳统一传的一组 props（本视图不用 store，声明只为不与壳的绑定冲突）。 */
    store?: unknown
  }>(),
  { pluginId: '', api: null },
)

/** ⚠️ 必须是字符串数组（AGENTS.md §5：函数式写法编译出 emits: <函数>，事件静默失效）。 */
const emit = defineEmits(['refreshSide'])

const t = hostToast(props.toast as any)
const confirm = useHostConfirm()

/** 每批渲染多少张（与「已入库的番号」栏同数：60，见 usePagedList 的默认值）。 */
const ACTOR_PAGE_SIZE = 60
/** 一次向服务器要多少位（契约的 limit；前端再把这一页分批画出来）。 */
const FETCH_LIMIT = 200

// ---------------------------------------------------------------- 类型（字段名照契约，缺字段一律容错）

/** 演员的一张图（契约：每图带来源、尺寸与是否主图）。 */
interface ActorImage {
  url?: string
  source?: string
  w?: number
  h?: number
  bytes?: number
  primary?: boolean
}

/** 演员（`GET /actor/list` 的 items[] 与 `/actor/detail` 的 actor 同一形状）。 */
interface ActorItem {
  id?: string | number
  person?: string
  name?: string
  zh?: string
  jp?: string
  gender?: string
  aliases?: string[]
  javdb_actor_id?: string
  images?: ActorImage[]
  field_sources?: Record<string, string>
  locked_fields?: string[]
  last_scraped_at?: string
  retry_count?: number
  next_retry?: string
  status?: string
}

/**
 * 作品番号一行：后端口径是 `{number, title}`（`title` 可能是空串）。
 * 纯字符串也认 —— 契约早期写法是 `numbers: ["ABC-123"]`；两种都不至于把界面画成 `[object Object]`。
 */
type ActorNumber = { number?: string; title?: string } | string

/** 详情回包：演员本体 + 作品番号 + 最近动作流水。 */
interface ActorDetail {
  actor: ActorItem
  numbers: ActorNumber[]
  history: Array<{ at?: string; action?: string; reason?: string }>
}

function textOf(value: unknown): string {
  return value === null || value === undefined ? '' : String(value)
}

async function getJson(path: string, params?: Record<string, unknown>): Promise<any> {
  const api = props.api
  if (!api || typeof api.get !== 'function') throw new Error('宿主 api 不可用')
  const payload: any = unwrap<any>(await api.get(path, params ? { params } : undefined))
  if (payload && typeof payload === 'object' && payload.success === false) {
    throw new Error(textOf(payload.message) || '接口返回失败')
  }
  return payload
}

async function postJson(path: string, body: Record<string, unknown>): Promise<any> {
  const api = props.api
  if (!api || typeof api.post !== 'function') throw new Error('宿主 api 不可用')
  const payload: any = unwrap<any>(await api.post(path, body))
  if (payload && typeof payload === 'object' && payload.success === false) {
    throw new Error(textOf(payload.message) || '接口返回失败')
  }
  return payload
}

// ---------------------------------------------------------------- 列表

/** 筛选档（服务端真值；`""` = 全部）。 */
const FILTERS: Array<{ value: string; label: string }> = [
  { value: '', label: '全部' },
  { value: 'missing_avatar', label: '缺头像' },
  { value: 'locked', label: '已锁定' },
  { value: 'failed', label: '失败' },
]

const items = ref<ActorItem[]>([])
/** 后端给的演员总数（本页只取 FETCH_LIMIT 位，小于总数时工具条会如实写出来）。 */
const total = ref(0)
const loading = ref(false)
const error = ref('')
const loaded = ref(false)
const query = ref('')
const filter = ref('')

/** 本页数组 + 本地搜索词过滤（筛选是服务端的，见文件头）。 */
const rows = computed<ActorItem[]>(() => {
  const keyword = String(query.value || '').trim().toLowerCase()
  if (!keyword) return items.value
  return items.value.filter((item) => {
    const haystack = [
      item.name,
      item.zh,
      item.jp,
      item.person,
      ...(Array.isArray(item.aliases) ? item.aliases : []),
    ].map(value => textOf(value).toLowerCase()).join(' ')
    return haystack.includes(keyword)
  })
})

const filtered = computed(() => !!String(query.value || '').trim())

const {
  rows: pagedRows,
  shown: shownRows,
  total: pagedTotal,
  hasMore,
  sentinel,
} = usePagedList(rows, { pageSize: ACTOR_PAGE_SIZE })

/** 末尾哨兵那行文案（与「已入库的番号」栏同一句口径，单位换成「位」）。 */
const pagedHint = computed(() => (
  hasMore.value
    ? '已显示 ' + shownRows.value + ' / ' + pagedTotal.value + ' 位 · 继续下滑自动加载'
    : '已全部加载（' + pagedTotal.value + ' 位）'
))

/** 工具条计数：后端总数 + 本页条数（两者不等时如实说明，不假装全量）。 */
const summary = computed(() => {
  const all = total.value || items.value.length
  const parts = ['共 ' + all + ' 位']
  if (items.value.length && all > items.value.length) parts.push('本屏 ' + items.value.length + ' 位')
  if (filtered.value) parts.push('筛出 ' + rows.value.length + ' 位')
  return parts.join(' · ')
})

/** 读一页演员（换筛选时调用；`notify` = 手动刷新时给一句 toast）。 */
async function load(notify = false): Promise<void> {
  if (loading.value) return
  loading.value = true
  error.value = ''
  if (notify) t.info('正在读取演员库…')
  try {
    const payload: any = await getJson('plugin/actor/list', {
      filter: filter.value,
      page: 1,
      limit: FETCH_LIMIT,
    })
    const list = Array.isArray(payload?.items) ? payload.items : []
    items.value = list as ActorItem[]
    total.value = Number(payload?.total || list.length) || list.length
    loaded.value = true
    if (notify) t.success('共 ' + total.value + ' 位')
  } catch (err) {
    error.value = errorText(err)
    if (notify) t.warning('演员库读取失败：' + error.value)
  } finally {
    loading.value = false
  }
}

/** 换筛选：重发请求（服务端真值），并回到第一批（源数组换身份后 usePagedList 自动重置）。 */
function pickFilter(value: string): void {
  if (filter.value === value) return
  filter.value = value
  void load(false)
}

// ---------------------------------------------------------------- 卡片上的小角标

/** 这张卡的图（主图优先；没有图就是空串 → Thumb 画占位）。 */
function avatarOf(item: ActorItem): string {
  const images = Array.isArray(item.images) ? item.images : []
  const primary = images.find(image => image?.primary) || images[0]
  return textOf(primary?.url)
}

/** 缺头像（契约 list 的 filter 同名词：没有可用图）。 */
function missingAvatar(item: ActorItem): boolean {
  return !avatarOf(item)
}

/** images 字段被锁（详情里可解锁；锁住的不会被「重刮」换图）。 */
function imagesLocked(item: ActorItem): boolean {
  return (Array.isArray(item.locked_fields) ? item.locked_fields : []).includes('images')
}

/** 卡片 key：id 优先，缺 id 用名字兜底（后端异常数据也不撞 key）。 */
function rowKey(item: ActorItem, index: number): string {
  return textOf(item.id) || textOf(item.name) || 'row#' + index
}

// ---------------------------------------------------------------- 详情

const detailId = ref('')
const detail = ref<ActorDetail | null>(null)
const detailLoading = ref(false)
const detailError = ref('')
/** 在飞的写操作（`''` = 空闲）：给按钮转圈并防重复点。 */
const busy = ref('')

/** 详情里的演员本体（模板里少写几层 `detail?.actor?.xxx`）。 */
const actor = computed<ActorItem | null>(() => detail.value?.actor || null)
const images = computed<ActorImage[]>(() => (Array.isArray(actor.value?.images) ? actor.value!.images! : []))
const numbers = computed<ActorNumber[]>(() => (Array.isArray(detail.value?.numbers) ? detail.value!.numbers! : []))
const history = computed(() => (Array.isArray(detail.value?.history) ? detail.value!.history! : []))

/** 番号主文（`{number}` 优先；纯字符串直接用）。 */
function numberText(entry: ActorNumber): string {
  return typeof entry === 'string' ? entry : textOf(entry?.number) || textOf(entry?.title)
}

/** 番号对应的片名（悬停提示用；没有就是空串，不画 tooltip）。 */
function numberTitle(entry: ActorNumber): string {
  return typeof entry === 'string' ? '' : textOf(entry?.title)
}

/** 打开某位演员的详情（同一视图内换内容，见文件头第 3 条）。 */
function openActor(item: ActorItem): void {
  const id = textOf(item.id)
  if (!id) {
    t.warning('这位演员还没有 id（后端没入库），暂时打不开详情')
    return
  }
  detailId.value = id
  detail.value = null
  imageIndex.value = 0
  scrapeResult.value = null
  cropOffset.value = 50
  void loadDetail()
}

async function loadDetail(): Promise<void> {
  if (!detailId.value) return
  detailLoading.value = true
  detailError.value = ''
  try {
    const payload: any = await getJson('plugin/actor/detail', { id: detailId.value })
    const raw = payload?.actor && typeof payload.actor === 'object' ? payload.actor : payload
    detail.value = {
      actor: (raw || {}) as ActorItem,
      numbers: Array.isArray(payload?.numbers) ? payload.numbers : [],
      history: Array.isArray(payload?.history) ? payload.history : [],
    }
    if (imageIndex.value >= images.value.length) imageIndex.value = 0
  } catch (err) {
    detailError.value = errorText(err)
  } finally {
    detailLoading.value = false
  }
}

/** 「← 返回」：回到列表（筛选项与搜索词都保留，与 ActorsView 的 backToList 同一行为）。 */
function backToList(): void {
  detailId.value = ''
  detail.value = null
  detailError.value = ''
  scrapeResult.value = null
}

// ---------------------------------------------------------------- 多图轮播

const imageIndex = ref(0)

const currentImage = computed<ActorImage | null>(() => images.value[imageIndex.value] || null)

/** 当前图的角标：来源 · 尺寸 · 体积（缺哪项就不写哪项）。 */
const currentMeta = computed(() => {
  const image = currentImage.value
  if (!image) return ''
  const parts: string[] = []
  const source = textOf(image.source) || '未知来源'
  parts.push(source === 'gfriends' ? 'gfriends' : source === 'javdb' ? 'javdb' : source === 'manual' ? '手动上传' : source)
  const w = Number(image.w) || 0
  const h = Number(image.h) || 0
  if (w && h) parts.push(w + '×' + h)
  const bytes = Number(image.bytes) || 0
  if (bytes) parts.push(Math.round(bytes / 1024) + ' KB')
  return parts.join(' · ')
})

function stepImage(delta: number): void {
  const count = images.value.length
  if (!count) return
  imageIndex.value = (imageIndex.value + delta + count) % count
  cropOffset.value = 50
}

function pickImage(index: number): void {
  imageIndex.value = index
  cropOffset.value = 50
}

// ---------------------------------------------------------------- 重刮（dry_run 预览 → 应用）

/** 重刮结论条（dry_run 与真跑各写一次，跑完留在页面上）。 */
const scrapeResult = ref<{ ok: boolean; text: string; errors: string[] } | null>(null)

/** 归一 `/actor/scrape` 的 counts（键名开放，缺就按 items[] 数）。 */
function scrapeSummary(payload: any, dryRun: boolean): { ok: boolean; text: string; errors: string[] } {
  const counts = (payload?.counts && typeof payload.counts === 'object' ? payload.counts : {}) as Record<string, unknown>
  const items = Array.isArray(payload?.items) ? payload.items : []
  const errors = (Array.isArray(payload?.errors) ? payload.errors : [])
    .map((item: unknown) => textOf(item))
    .filter(Boolean)
  const first = (keys: string[]): number | null => {
    for (const key of keys) {
      const value = counts[key]
      if (value === undefined || value === null) continue
      const num = Number(value)
      if (Number.isFinite(num)) return num
    }
    return null
  }
  let up = first(['uploaded', 'applied', 'ok', 'done'])
  let skip = first(['skipped', 'skip'])
  let fail = first(['failed', 'error'])
  if (up === null || skip === null || fail === null) {
    let okCount = 0
    let skipCount = 0
    let failCount = 0
    for (const item of items) {
      const action = textOf(item?.action ?? item?.status).toLowerCase()
      if (/fail|error/.test(action)) failCount += 1
      else if (/skip|no_avatar|person_missing|has_image|locked/.test(action)) skipCount += 1
      else okCount += 1
    }
    if (up === null) up = okCount
    if (skip === null) skip = skipCount
    if (fail === null) fail = failCount
  }
  const line = '更新 ' + (up || 0) + ' / 跳过 ' + (skip || 0) + ' / 失败 ' + (fail || 0)
  return {
    ok: (fail || 0) === 0 && !errors.length,
    text: (dryRun ? '重刮计划（dry_run，零写请求）：' : '') + line,
    errors: errors.slice(0, 5),
  }
}

/**
 * 「重刮」：先 `{dry_run:true}` 只读拿计划 → 确认 → `{dry_run:false, force:true}`。
 *
 * 带 `force` 是因为这是**用户点名要重刮这一位**（不带 force 的批量会跳过「已经有图」的）；
 * 设了 `images` 锁的仍然只补资料、不换图（锁的语义在后端，界面只如实显示「已锁定」）。
 */
async function rescrape(): Promise<void> {
  if (busy.value) return
  const id = detailId.value
  if (!id) return
  const name = textOf(actor.value?.zh || actor.value?.name) || '这位演员'
  busy.value = 'scrape'
  scrapeResult.value = null
  try {
    t.info('正在读取重刮计划（dry_run，零写请求）…')
    let plan: { ok: boolean; text: string; errors: string[] }
    try {
      const payload: any = await postJson('plugin/actor/scrape', { id, dry_run: true, force: true })
      plan = scrapeSummary(payload, true)
    } catch (err) {
      scrapeResult.value = { ok: false, text: '重刮计划读取失败', errors: [errorText(err)] }
      t.warning('重刮计划读取失败：' + errorText(err))
      return
    }
    scrapeResult.value = plan
    const go = await confirm({
      type: 'warn',
      title: '重刮演员资料与头像',
      content:
        'dry_run 计划：' + plan.text.replace('重刮计划（dry_run，零写请求）：', '') + '。\n\n' +
        '确认后真的开始抓取：会重新问一遍 gFriends / javdb，并把新头像写进 Emby 的 Person 实体（Primary 图）。' +
        (imagesLocked(actor.value || {}) ? '\n\n★ 这位演员的 images 字段当前是锁住的：只补资料，不会换图。' : ''),
      confirmText: '开始重刮',
      cancelText: '取消',
    })
    if (!go) {
      t.info('已取消，没有向 Emby 写入任何东西')
      return
    }
    const payload: any = await postJson('plugin/actor/scrape', { id, dry_run: false, force: true })
    const done = scrapeSummary(payload, false)
    scrapeResult.value = done
    if (done.ok) t.success(name + ' 重刮完成：' + done.text)
    else t.warning(name + ' 重刮未全部成功：' + done.text)
    await loadDetail()
    emit('refreshSide')
  } catch (err) {
    scrapeResult.value = { ok: false, text: '重刮请求失败', errors: [errorText(err)] }
    t.warning('重刮失败：' + errorText(err))
  } finally {
    busy.value = ''
  }
}

// ---------------------------------------------------------------- 锁（images 字段）

/** 「🔒 锁定 / 解锁 images」：`POST /actor/lock {id, field:"images", on}` → 回新的 actor。 */
async function toggleLock(): Promise<void> {
  if (busy.value) return
  const id = detailId.value
  if (!id) return
  const on = !imagesLocked(actor.value || {})
  busy.value = 'lock'
  try {
    const payload: any = await postJson('plugin/actor/lock', { id, field: 'images', on })
    applyActor(payload)
    t.success(on ? '已锁定 images：重刮只补资料、不换图' : '已解锁 images：下次重刮会换图')
    emit('refreshSide')
  } catch (err) {
    t.warning('锁定状态切换失败：' + errorText(err))
  } finally {
    busy.value = ''
  }
}

/**
 * 写操作回包 → 详情。
 *
 * **主路径 = `{success, actor}`**（`/actor/lock` 与 `/actor/crop-avatar` 统一后的形状）。
 * 宽容分支留着是有原因的：这两个端点的早期实现把 `store.actor_*` 的整行摊平在顶层
 * （`{success, id, images…}`），而别的 `/actor/*` 端点又只回裸行 —— 一份回包形状的变动
 * 不该让界面在真机上打成空白。取不到 `actor` 就退回顶层行，两样都没有才重读详情。
 */
function applyActor(raw: any): void {
  const nested = raw && typeof raw === 'object' ? raw.actor : null
  const flat = raw && typeof raw === 'object' && raw.id !== undefined ? raw : null
  const row = nested && typeof nested === 'object' ? nested : flat
  if (row && detail.value) {
    detail.value = { ...detail.value, actor: row as ActorItem }
  } else {
    void loadDetail()
  }
}

// ---------------------------------------------------------------- 3:4 裁剪（只算 rect，裁切在后端）

/** 裁剪框的竖向位置（百分比，50 = 居中）：只做上下微调，不做自研图像编辑器。 */
const cropOffset = ref(50)

/**
 * 每张图是不是主图：后端的 `images[]` 每条会带 `primary` 布尔，**有就认它**；
 * 没有（老数据 / 旧回包）就退回「第 0 张」—— `store.actor_set_images()` 的口径本来就是
 * 「`images[0]` 就是主图，顺序有意义、这里不重排」。
 */
function isPrimary(index: number): boolean {
  const image = images.value[index]
  return !!image?.primary || index === 0
}

/** 当前主图（裁剪以它为准：带 `primary` 标记的那张，否则第 0 张）。 */
const primaryImage = computed<ActorImage | null>(() => (
  images.value.find(image => image?.primary) || images.value[0] || null
))

/**
 * 3:4 裁剪框 → `rect`（源图像素坐标）。
 *
 * 规则（最简单的一种，方案 §5.6 的默认口径）：
 * - 比例已经比 3:4 更宽/更高时，先按短边切出最大的 3:4 窗口：横向居中、纵向按 `cropOffset` 挪；
 * - 源图尺寸未知（`w`/`h` 缺）→ 返回 `null`，`crop-avatar` 不带 rect（由后端按默认 3:4 自判）。
 */
const cropRect = computed<{ x: number; y: number; w: number; h: number } | null>(() => {
  const image = primaryImage.value
  if (!image) return null
  const w = Math.round(Number(image.w) || 0)
  const h = Math.round(Number(image.h) || 0)
  if (!w || !h) return null
  const target = 3 / 4
  let boxW = w
  let boxH = Math.round(w / target)
  if (boxH > h) {
    boxH = h
    boxW = Math.round(h * target)
  }
  const x = Math.round((w - boxW) / 2)
  const maxY = Math.max(0, h - boxH)
  const y = Math.round(maxY * (cropOffset.value / 100))
  return { x, y, w: boxW, h: boxH }
})

/** 裁剪预览：3:4 盒子里用 `object-position` 表现纵向位置（CSS 变量由外层盒子传下去）。 */
const cropStyle = computed(() => ({ '--avh-crop-y': cropOffset.value + '%' }))

/** 主图地址（走 Thumb 的代理口径，不直连图床）。 */
const primaryUrl = computed(() => textOf(primaryImage.value?.url))

/** 「裁剪」：`POST /actor/crop-avatar {id, rect}`，成功后**前插为主图**（后端行为，这里同步到界面）。 */
async function applyCrop(): Promise<void> {
  if (busy.value) return
  const id = detailId.value
  if (!id) return
  const rect = cropRect.value
  const ok = await confirm({
    type: 'warn',
    title: '裁剪为主图（3:4）',
    content:
      '确认后按 3:4 裁掉边缘，生成一张派生图并**设为主图**写进 Emby 的 Person 实体；原图保留。' +
      (rect
        ? '\n\n本次裁剪框：x ' + rect.x + ' · y ' + rect.y + ' · ' + rect.w + '×' + rect.h + '（基于当前主图）。'
        : '\n\n这张图没有尺寸信息，将由后端按默认 3:4 居中裁切。') +
      '\n\n裁剪成功后 images 会被自动锁住，避免下次重刮又换掉这张。',
    confirmText: '裁剪并设为主图',
    cancelText: '取消',
  })
  if (!ok) return
  busy.value = 'crop'
  try {
    const body: Record<string, unknown> = { id }
    if (rect) body.rect = rect
    const payload: any = await postJson('plugin/actor/crop-avatar', body)
    applyActor(payload)
    imageIndex.value = 0
    t.success('已裁剪并设为主图')
    emit('refreshSide')
  } catch (err) {
    t.warning('裁剪失败：' + errorText(err))
  } finally {
    busy.value = ''
  }
}

// 进本栏即读一次（壳按栏目 key 重挂本组件，所以「进来就是最新的」）。
onMounted(() => {
  void load(false)
})
</script>

<template>
  <div class="avh-actlib">
    <!-- ================= 演员详情（同一视图内换内容，顶部 ← 返回） ================= -->
    <template v-if="detailId">
      <div class="avh-actlib__toolbar">
        <v-btn variant="outlined" size="small" @click="backToList">← 返回</v-btn>
        <span class="avh-actlib__hint">
          演员详情 · {{ actor?.zh || actor?.name || '—' }}
        </span>
        <div class="avh-actlib__spacer" />
        <v-btn variant="outlined" size="small" :loading="detailLoading" @click="loadDetail">↻ 重新读取</v-btn>
      </div>

      <ErrorState
        v-if="detailError"
        :message="'演员详情读取失败：' + detailError"
        :retrying="detailLoading"
        @retry="loadDetail"
      />

      <div v-else-if="detailLoading && !actor" class="avh-actlib__loading">正在读取演员详情…</div>

      <template v-else-if="actor">
        <!-- 资料头：名字 + 状态角标 -->
        <div class="avh-actlib__head">
          <div class="avh-actlib__names">
            <div class="avh-actlib__nm">{{ actor.zh || actor.name || '—' }}</div>
            <div v-if="actor.zh && actor.name" class="avh-actlib__sub">{{ actor.name }}</div>
            <div v-else-if="actor.jp" class="avh-actlib__sub">{{ actor.jp }}</div>
          </div>
          <v-chip v-if="imagesLocked(actor)" size="x-small" color="warning" variant="flat" label>🔒 images 已锁定</v-chip>
          <v-chip v-else size="x-small" variant="tonal" label>images 未锁</v-chip>
          <v-chip v-if="actor.status" size="x-small" variant="tonal" label>状态 {{ actor.status }}</v-chip>
        </div>

        <div class="avh-actlib__detail">
          <!-- 左：多图轮播 -->
          <div class="avh-actlib__gallery">
            <div v-if="images.length" class="avh-actlib__stage">
              <Thumb
                class="avh-actlib__shot"
                variant="film"
                :src="textOf(currentImage?.url)"
                :alt="actor.zh || actor.name || '无图'"
                :plugin-id="pluginId"
              />
              <span class="avh-actlib__badge">{{ currentMeta }}</span>
              <span v-if="isPrimary(imageIndex)" class="avh-actlib__badge avh-actlib__badge--primary">主图</span>
              <template v-if="images.length > 1">
                <button class="avh-actlib__nav avh-actlib__nav--prev" type="button" aria-label="上一张" @click="stepImage(-1)">‹</button>
                <button class="avh-actlib__nav avh-actlib__nav--next" type="button" aria-label="下一张" @click="stepImage(1)">›</button>
              </template>
            </div>
            <EmptyState v-else text="这位演员还没有图" hint="去「设置 → 演员」确认头像源开关，或点下面的「重刮」抓一次" />

            <div v-if="images.length > 1" class="avh-actlib__strip">
              <button
                v-for="(image, index) in images"
                :key="'img#' + index"
                type="button"
                class="avh-actlib__thumb"
                :class="{ 'avh-actlib__thumb--on': index === imageIndex }"
                :title="textOf(image.source) + ' ' + (image.w || '?') + '×' + (image.h || '?')"
                @click="pickImage(index)"
              >
                <Thumb :src="textOf(image.url)" :alt="'图 ' + (index + 1)" :plugin-id="pluginId" />
              </button>
            </div>
          </div>

          <!-- 右：写操作（重刮 / 锁 / 裁剪） -->
          <div class="avh-actlib__ops">
            <div class="text-caption text-medium-emphasis mb-1">维护</div>
            <div class="avh-actlib__row mb-2">
              <v-btn
                size="small"
                variant="outlined"
                prepend-icon="mdi-auto-fix"
                :loading="busy === 'scrape'"
                @click="rescrape"
              >重刮</v-btn>
              <span class="avh-actlib__hint">先 dry_run 预览，再确认应用</span>
            </div>
            <div class="avh-actlib__row mb-2">
              <v-btn
                size="small"
                variant="outlined"
                :prepend-icon="imagesLocked(actor) ? 'mdi-lock-open-variant' : 'mdi-lock'"
                :loading="busy === 'lock'"
                @click="toggleLock"
              >{{ imagesLocked(actor) ? '解锁 images' : '锁定 images' }}</v-btn>
              <span class="avh-actlib__hint">锁住后重刮只补资料、不换图</span>
            </div>

            <v-alert
              v-if="scrapeResult"
              :type="scrapeResult.ok ? 'success' : 'warning'"
              variant="tonal"
              density="compact"
              class="text-caption mb-3"
            >
              <div>{{ scrapeResult.text }}</div>
              <div v-for="(line, index) in scrapeResult.errors" :key="index">{{ line }}</div>
            </v-alert>

            <v-divider class="mb-3" />

            <div class="text-caption text-medium-emphasis mb-1">裁剪为主图（3:4）</div>
            <template v-if="primaryUrl">
              <div class="avh-actlib__cropbox">
                <Thumb
                  class="avh-actlib__crop"
                  :style="cropStyle"
                  variant="film"
                  :src="primaryUrl"
                  alt="裁剪预览"
                  :plugin-id="pluginId"
                />
              </div>
              <div class="avh-actlib__row mb-1">
                <span class="avh-actlib__hint">上下微调</span>
                <v-slider
                  :model-value="cropOffset"
                  :min="0"
                  :max="100"
                  :step="1"
                  density="compact"
                  hide-details
                  class="avh-actlib__slider"
                  @update:model-value="(value: any) => (cropOffset = Number(value) || 0)"
                />
                <span class="avh-actlib__hint">{{ cropOffset }}%</span>
              </div>
              <p class="text-caption text-medium-emphasis mb-2">
                <template v-if="cropRect">
                  裁剪框：x {{ cropRect.x }} · y {{ cropRect.y }} · {{ cropRect.w }}×{{ cropRect.h }}（基于当前主图 {{ primaryImage?.w || '?' }}×{{ primaryImage?.h || '?' }}）
                </template>
                <template v-else>
                  这张图没有尺寸信息，裁切换后端默认的 3:4 居中框。
                </template>
              </p>
              <v-btn
                size="small"
                variant="outlined"
                prepend-icon="mdi-crop"
                :loading="busy === 'crop'"
                @click="applyCrop"
              >裁剪并设为主图</v-btn>
            </template>
            <p v-else class="text-caption text-medium-emphasis mb-0">
              还没有主图可裁：先「重刮」拿到一张图。
            </p>
          </div>
        </div>

        <!-- 资料字段 -->
        <div class="avh-actlib__fields">
          <div class="avh-actlib__field"><span>原名</span><b>{{ actor.name || '—' }}</b></div>
          <div class="avh-actlib__field"><span>中文名</span><b>{{ actor.zh || '—' }}</b></div>
          <div class="avh-actlib__field"><span>日文名</span><b>{{ actor.jp || '—' }}</b></div>
          <div class="avh-actlib__field"><span>性别</span><b>{{ actor.gender || '—' }}</b></div>
          <div class="avh-actlib__field"><span>javdb 演员 id</span><b>{{ actor.javdb_actor_id || '—' }}</b></div>
          <div class="avh-actlib__field"><span>别名</span><b>{{ (actor.aliases || []).join(' / ') || '—' }}</b></div>
          <div class="avh-actlib__field"><span>最后刮削</span><b>{{ actor.last_scraped_at ? shortTime(actor.last_scraped_at) : '—' }}</b></div>
          <div class="avh-actlib__field"><span>重试</span><b>{{ actor.retry_count || 0 }}{{ actor.next_retry ? ' · 下次 ' + shortTime(actor.next_retry) : '' }}</b></div>
        </div>

        <!-- 作品番号 -->
        <div class="avh-actlib__section">
          <div class="text-caption text-medium-emphasis mb-1">作品番号（{{ numbers.length }}）</div>
          <div v-if="numbers.length" class="avh-actlib__chips">
            <v-chip
              v-for="(entry, index) in numbers"
              :key="numberText(entry) + '#' + index"
              size="x-small"
              variant="tonal"
              label
              :title="numberTitle(entry)"
            >{{ numberText(entry) }}</v-chip>
          </div>
          <p v-else class="text-caption text-medium-emphasis mb-0">还没有关联到作品番号。</p>
        </div>

        <!-- 动作流水 -->
        <div class="avh-actlib__section">
          <div class="text-caption text-medium-emphasis mb-1">最近动作（{{ history.length }}）</div>
          <div v-if="history.length" class="avh-actlib__history">
            <div v-for="(row, index) in history" :key="'h#' + index" class="avh-actlib__hrow">
              <span class="avh-actlib__hint">{{ row.at ? shortTime(row.at) : '—' }}</span>
              <span>{{ row.action || '—' }}</span>
              <span class="avh-actlib__hint">{{ row.reason || '' }}</span>
            </div>
          </div>
          <p v-else class="text-caption text-medium-emphasis mb-0">还没有执行过动作。</p>
        </div>
      </template>
    </template>

    <!-- ================= 演员卡片墙 ================= -->
    <template v-else>
      <div class="avh-actlib__toolbar">
        <v-btn-toggle
          :model-value="filter"
          mandatory
          density="compact"
          variant="outlined"
          color="primary"
          class="avh-actlib__filters"
          @update:model-value="(value: any) => value !== undefined && pickFilter(String(value))"
        >
          <v-btn v-for="item in FILTERS" :key="item.value" :value="item.value" size="small">{{ item.label }}</v-btn>
        </v-btn-toggle>

        <div class="avh-actlib__spacer" />

        <v-text-field
          v-model="query"
          class="avh-actlib__q"
          density="compact"
          variant="outlined"
          hide-details
          clearable
          single-line
          prepend-inner-icon="mdi-magnify"
          placeholder="艺名 / 中文名 / 别名"
          aria-label="按艺名、中文名或别名过滤已取回的演员"
        />

        <v-btn variant="outlined" size="small" :loading="loading" @click="load(true)">↻ 刷新</v-btn>
      </div>

      <div v-if="!error && (loaded || items.length)" class="avh-actlib__stats">
        <v-chip size="x-small" variant="flat" color="success" label>演员库</v-chip>
        <span class="avh-actlib__hint">{{ summary }}</span>
      </div>

      <ErrorState
        v-if="error"
        :message="'演员库读取失败：' + error"
        :retrying="loading"
        @retry="load(false)"
      />

      <div v-else-if="loading && !items.length" class="avh-actlib__loading">正在读取演员库…</div>

      <EmptyState
        v-else-if="!items.length && filter"
        text="这个筛选下没有演员"
        hint="换个筛选档看看，或者点「全部」"
      />

      <EmptyState
        v-else-if="!items.length"
        text="演员库里还没有演员<br>影片刮削过一次之后，演员会自动登记进来"
        hint="也可以去「设置 → 演员」点「一键补齐缺失头像」立刻跑一批"
      />

      <EmptyState
        v-else-if="filtered && !rows.length"
        text="没有匹配的演员"
        hint="试试清空搜索词，或者换个艺名 / 中文名"
      />

      <template v-else>
        <div class="avh-actlib__grid">
          <div
            v-for="(item, index) in pagedRows"
            :key="rowKey(item, index)"
            class="avh-actlib__cell"
          >
            <ActorRow
              :name="textOf(item.name) || textOf(item.zh) || '—'"
              :zh="textOf(item.zh)"
              :avatar="avatarOf(item)"
              :plugin-id="pluginId"
              @select="openActor(item)"
            />
            <span v-if="missingAvatar(item)" class="avh-actlib__abadge">缺头像</span>
            <span v-if="imagesLocked(item)" class="avh-actlib__abadge avh-actlib__abadge--lock">🔒</span>
          </div>
        </div>

        <!-- 末尾哨兵：滚到底自动追加下一批（必须待在滚动层内部） -->
        <div ref="sentinel" class="avh-actlib__more">
          <span class="avh-actlib__hint">{{ pagedHint }}</span>
        </div>
      </template>
    </template>
  </div>
</template>

<style scoped>
/* 工具条 / 统计行 / 网格 / 哨兵：与「已入库的番号」栏（LibraryView）同一套尺寸与间距 */
.avh-actlib__toolbar {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
  margin-bottom: 8px;
}

.avh-actlib__hint {
  font-size: 12px;
  color: rgba(var(--v-theme-on-surface), 0.5);
}

.avh-actlib__spacer {
  flex: 1;
}

.avh-actlib__q {
  width: 220px;
  flex: none;
}

.avh-actlib__stats {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
  margin-bottom: 10px;
}

.avh-actlib__loading {
  padding: 44px 20px;
  text-align: center;
  font-size: 13px;
  color: rgba(var(--v-theme-on-surface), 0.5);
}

/* 演员卡片墙：老演示页 .actors 的网格（136px 起） */
.avh-actlib__grid {
  display: grid;
  gap: 12px;
  grid-template-columns: repeat(auto-fill, minmax(136px, 1fr));
}

.avh-actlib__cell {
  position: relative;
  display: flex;
  flex-direction: column;
}

.avh-actlib__more {
  padding: 14px 4px 2px;
  text-align: center;
}

/* 卡片右上角的两个小角标（缺头像 / 已锁定）：与 LibraryView 的版本角标同尺寸 */
.avh-actlib__abadge {
  position: absolute;
  top: 6px;
  left: 6px;
  z-index: 1;
  padding: 1px 6px;
  font-size: 10px;
  line-height: 1.6;
  border-radius: 4px;
  color: #fff;
  background: rgba(var(--v-theme-warning), 0.9);
  pointer-events: none;
}

.avh-actlib__abadge--lock {
  left: auto;
  right: 6px;
  background: rgba(var(--v-theme-secondary), 0.9);
}

/* ---------- 详情 ---------- */

.avh-actlib__head {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
  margin-bottom: 10px;
}

.avh-actlib__nm {
  font-size: 17px;
  font-weight: 600;
}

.avh-actlib__sub {
  font-size: 12px;
  color: rgba(var(--v-theme-on-surface), 0.5);
}

.avh-actlib__detail {
  display: grid;
  gap: 16px;
  grid-template-columns: minmax(240px, 1.3fr) minmax(240px, 1fr);
  margin-bottom: 14px;
}

/* 窄屏自然折成一列（与设置台面板同一策略） */
@media (max-width: 720px) {
  .avh-actlib__detail {
    grid-template-columns: 1fr;
  }
}

.avh-actlib__stage {
  position: relative;
  border-radius: 10px;
  overflow: hidden;
  background: rgba(var(--v-theme-on-surface), 0.06);
}

/* 详情大图：固定 3:4 舞台，图按 contain 铺满（竖图/横图都不裁） */
.avh-actlib__shot {
  width: 100%;
  aspect-ratio: 3 / 4;
}

.avh-actlib__badge {
  position: absolute;
  left: 8px;
  bottom: 8px;
  padding: 2px 7px;
  font-size: 11px;
  border-radius: 4px;
  color: #fff;
  background: rgba(0, 0, 0, 0.62);
}

.avh-actlib__badge--primary {
  left: auto;
  right: 8px;
  background: rgba(var(--v-theme-success), 0.9);
}

.avh-actlib__nav {
  position: absolute;
  top: 50%;
  transform: translateY(-50%);
  width: 32px;
  height: 32px;
  border: 0;
  border-radius: 50%;
  font-size: 20px;
  line-height: 1;
  cursor: pointer;
  color: #fff;
  background: rgba(0, 0, 0, 0.42);
}

.avh-actlib__nav:hover {
  background: rgba(0, 0, 0, 0.66);
}

.avh-actlib__nav--prev {
  left: 8px;
}

.avh-actlib__nav--next {
  right: 8px;
}

.avh-actlib__strip {
  display: flex;
  gap: 6px;
  flex-wrap: wrap;
  margin-top: 8px;
}

.avh-actlib__thumb {
  width: 52px;
  height: 69px;
  padding: 0;
  border: 2px solid transparent;
  border-radius: 6px;
  overflow: hidden;
  cursor: pointer;
  background: rgba(var(--v-theme-on-surface), 0.06);
}

.avh-actlib__thumb--on {
  border-color: rgb(var(--v-theme-primary));
}

.avh-actlib__thumb :deep(.avh-thumb) {
  width: 100%;
  height: 100%;
}

.avh-actlib__ops {
  border: 1px solid rgba(var(--v-theme-on-surface), 0.12);
  border-radius: 10px;
  padding: 12px;
}

.avh-actlib__row {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
}

.avh-actlib__cropbox {
  width: 132px;
  margin-bottom: 8px;
}

/* 裁剪预览：3:4 盒子 + 纵向位置微调（object-position 由 CSS 变量传下去） */
.avh-actlib__crop {
  width: 132px;
  aspect-ratio: 3 / 4;
  border-radius: 8px;
}

.avh-actlib__crop :deep(img) {
  object-position: 50% var(--avh-crop-y, 50%);
}

.avh-actlib__slider {
  flex: 1;
  min-width: 120px;
}

.avh-actlib__fields {
  display: grid;
  gap: 6px 16px;
  grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
  margin-bottom: 14px;
}

.avh-actlib__field {
  display: flex;
  gap: 8px;
  font-size: 12.5px;
  min-width: 0;
}

.avh-actlib__field span {
  flex: none;
  width: 84px;
  color: rgba(var(--v-theme-on-surface), 0.5);
}

.avh-actlib__field b {
  font-weight: 500;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.avh-actlib__section {
  margin-bottom: 12px;
}

.avh-actlib__chips {
  display: flex;
  gap: 6px;
  flex-wrap: wrap;
}

.avh-actlib__history {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.avh-actlib__hrow {
  display: flex;
  gap: 10px;
  font-size: 12.5px;
  flex-wrap: wrap;
}
</style>
