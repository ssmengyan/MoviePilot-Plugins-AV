<script lang="ts">
/**
 * 发现榜单的**模块级**状态：榜单缓存 / 详情缓存 / 后台预热队列
 * （老实现 `ui/views/discover.js` 的 `PRE` / `prefetchDetail` / `pumpPrefetch` /
 * `prefetchCards`，以及 `ui/core/state.js` 里的全局 `CACHE` 与 `S.period` / `S.kind`）。
 *
 * **为什么本文件比前五个视图多一个普通 `<script>` 块**：
 * `<script setup>` 里的顶层变量会落进 `setup()`，随组件卸载一起丢掉（`Console.vue` 的
 * `<component :is>` 没有 keep-alive，切到别的栏目就是卸载）。而老实现的 `CACHE` 是
 * **模块级全局对象**：
 * - 榜单缓存在，切走再回「发现榜单」不重抓榜单（javdb 有站点限流，这条是纪律不是优化）；
 * - 详情缓存在，后台预热的结果才留得住（下一轮详情抽屉直接读 `cachedDetail()`）；
 * - `S.period` / `S.kind` 在，切走再回来还停在你上次看的那一档（老 S 是全局的）。
 * 所以这三样都放这里（真·模块作用域），并按老实现的名字导出。
 */
import { reactive, ref } from 'vue'
import { unwrap, type PluginApi } from '../../composables/usePluginApi'

/** 每屏后台预热前几张：老 `PREFETCH_N = 6`（调大 = 点开更快、后台开销更多）。 */
export const PREFETCH_N = 6

/** 榜单里的一部片（后端 `_movie()`；与 `common/NumCard.vue` 的 `CardMovie` 同 shape）。 */
export interface RankMovie {
  number?: string
  title?: string
  thumb?: string
  date?: string
  /** 分钟数（后端是 int，0/空表示没解析到）。 */
  duration?: number | string
  cnsub?: boolean
  uncensored?: boolean
  /** 磁力条数。 */
  magnets?: number
  actor?: string
  /** javdb 内部 id（打开详情时回传，能省一次「番号 → id」往返）。 */
  id?: string
  /** 已入库（Emby 命中）时是对象。 */
  lib?: { id?: string; name?: string; path?: string; url?: string } | null
}

/**
 * 榜单缓存条目：老 `put('rank:'+period+':'+kind, {data}|{error})` 的同形状。
 * **错误条目没有 `data`**（老实现同样只塞 `{error}`）：工具条的「n 部」就是靠这个不显示。
 */
export interface RankEntry {
  error: string
  data?: RankMovie[]
}

/** 详情缓存条目：老 `put('detail:'+number, {data, t})`，键不含前缀（取用时用番号）。 */
export interface DetailEntry {
  data: Record<string, any>
  t: number
}

/** 榜单缓存：键 `rank:<period>:<kind>`，跨栏目切换存活（老 `CACHE`）。 */
export const rankCache = reactive(new Map<string, RankEntry>())

/** 详情缓存：键 = 番号（老 `CACHE['detail:'+number]`）；下一轮详情抽屉直接读它。 */
export const detailCache = reactive(new Map<string, DetailEntry>())

/**
 * 当前榜单周期：老 `S.period`（默认 `week`，全局存活，切栏目回来不变）。
 * `<script setup>` 的模板绑定只能在 setup 里声明，所以那里再取一个 `period` 计算属性。
 */
export const periodState = ref('week')
/** 当前榜单分类：老 `S.kind`（默认 `censored`）。 */
export const kindState = ref('censored')

/** 读预热/详情缓存（老 `cached('detail:' + number)`）。 */
export function cachedDetail(number: unknown): DetailEntry | undefined {
  const key = String(number ?? '')
  return key ? detailCache.get(key) : undefined
}

/**
 * 后台预热队列：老 `PRE = {queue:[], busy:false}`。
 * **串行 1 条**——同一时间只起一个 `/detail` 请求，不并发压多个 javdb 子进程。
 */
const PRE: { queue: Array<{ number: string; id: string }>; busy: boolean } = { queue: [], busy: false }

/**
 * 排一张卡片的详情进预热队列（老 `prefetchDetail(num, id)`）。
 *
 * 三条纪律与老实现逐条一致：
 * 1. 命中 `detailCache` 直接跳过（切周期/切分类来回看不重复抓）；
 * 2. 已在队列里不重复排队；
 * 3. 只是**排队**，真正抓取由 `pumpPrefetch` 串行执行。
 */
export function prefetchDetail(api: PluginApi | null, number: unknown, id?: unknown): void {
  const num = String(number ?? '')
  if (!api || typeof api.get !== 'function' || !num) return
  if (detailCache.has(num)) return
  if (PRE.queue.some(item => item.number === num)) return
  PRE.queue.push({ number: num, id: String(id ?? '') })
  void pumpPrefetch(api)
}

/**
 * 串行取详情（老 `pumpPrefetch()`）：
 * 取队首 → 命中缓存就再抽下一个 → 否则发一次 `GET plugin/detail?number=&id=` → 完成后继续。
 * **失败不写任何条目**（老实现 `if (r.ok) put(...)` + `.catch(() => {})`），
 * 留给真正打开详情时报错重试。
 */
async function pumpPrefetch(api: PluginApi): Promise<void> {
  if (PRE.busy) return
  const job = PRE.queue.shift()
  if (!job) return
  if (detailCache.has(job.number)) {
    void pumpPrefetch(api)
    return
  }
  PRE.busy = true
  try {
    // 老 `apiUrl()` 会把空值参数丢掉，所以 id 为空时不带这一段。
    const params: Record<string, string> = { number: job.number }
    if (job.id) params.id = job.id
    const payload: any = unwrap(await api.get('plugin/detail', { params }))
    if (payload && typeof payload === 'object' && payload.success === false) return
    detailCache.set(job.number, { data: (payload as Record<string, any>) || {}, t: Date.now() })
  } catch {
    /* 预热失败静默（老实现 `.catch(() => {})`） */
  } finally {
    PRE.busy = false
    void pumpPrefetch(api)
  }
}

/**
 * 渲染后预热前 n 张（老 `prefetchCards(root, n)`：连点带滑也只取靠前的 n 张）。
 * 老实现是从 DOM 里取 `.card`，这里直接取同一个数组——列表顺序就是卡片顺序。
 */
export function prefetchCards(
  api: PluginApi | null,
  movies: RankMovie[] | null | undefined,
  n: number = PREFETCH_N,
): void {
  ;(movies || []).slice(0, n).forEach(movie => prefetchDetail(api, movie?.number, movie?.id))
}
</script>

<script setup lang="ts">
/**
 * 视图：发现榜单（S6 第六个、也是最后一个原生化视图）。
 *
 * 对照老实现 `ui/views/discover.js`（`renderDiscover` / `periodTabsHtml` / `zoneTabsHtml` /
 * `bindTabs` / `rankBodyHtml` / `loadDiscover` / `loadDiscoverForce` / `card` /
 * `prefetchDetail` / `pumpPrefetch` / `prefetchCards` / `bindCards`）与它的调用方
 * `ui/app.js`（`render()` 的首屏门与 `bindUi()` 的 `rank-retry` 委托），逐条对齐的是
 * **行为与文案**，DOM 换成 Vuetify 组件：
 *
 * | 老实现 | 这里 |
 * | --- | --- |
 * | `render()`：`!S.booted && S.view === 'discover'` → 整屏 `loadingHtml('正在读取插件状态…')`（连工具条都不画） | `!booted && !bootError` → 同一个 `.avh-discover__loading`、同一句文案 |
 * | `S.bootError` → 工具条（两组 tabs，**没有**「↻ 重新抓取」、**没有**「n 部」）＋ `errHtml('插件状态读取失败：'+bootError+'（仍可尝试直接抓取榜单）','data-act="rank-retry"')` | 同一结构、同一句文案（`ErrorState` 画「重试」，文案不变）；失败文案取自 `store.error` |
 * | `periodTabsHtml()`：`日榜/周榜/月榜`，`S.period` 命中的那颗 `.on` | 同一组按钮（`.avh-tabs` 对齐 `app.css` 的 `.tabs`/`.tabs button.on`），`period` 是模块级 ref（= 老 S 的全局性） |
 * | `zoneTabsHtml()`：`有码/无码/FC2`，`S.kind` 命中 | 同（`kind`） |
 * | `bindTabs(m)`：切一下就把 `S.period`/`S.kind` 写回去并 `render()`（重画工具条 + 榜单） | 同义：改 ref → 缓存命中就立刻画，没命中就落 `正在抓取榜单…` 再画 |
 * | 工具条：`<span class="hint">{n} 部</span>`（**只在 `entry.data` 存在时画**，空榜单也画 `0 部`）＋ `<div style="flex:1">` ＋ `<button class="ghost" id="btnReload">↻ 重新抓取</button>` | 同一句「n 部」、同一个出现条件、同一个右侧位置（按钮用 `variant="outlined"`，写法照任务页的「↻ 刷新任务」） |
 * | `#btnReload` → `loadDiscoverForce(true)` | `reloadRank()` |
 * | `rankBodyHtml`：`entry.error` → `errHtml(entry.error,'data-act="rank-retry"')`；空数组 → `emptyHtml('该榜单暂无数据，换个周期 / 分类试试')`；否则 `.grid` + `card(mv)` | 同一个判定顺序、同一句空态文案；卡片本体是 `common/NumCard.vue` |
 * | `card(mv)`：`.thumb`（`imgWithPlaceholder` + `.badges`：中字／破解／⭐已收藏演员／✔已入库）＋ `.meta`（番号 ／ 演员或 `—` ＋ `🧲 n` ／ 日期 ＋ `时长′`） | `NumCard` 同字段同顺序；`merged = mv.actor && S.favs.some(...)` → `actorFavorited` prop（口径仍是 `store.favs`） |
 * | `loadDiscover(force)`：`apiGet('/rankings', {period,kind})` → `r.data.movies` 写 `rank:<period>:<kind>`；失败 `toast('榜单抓取失败', r.message \|\| '抓取失败，请稍后重试','warn')` | `loadRank()` → `api.get('plugin/rankings', { params: { period, kind } })`（一致：**只认 `movies`**，空就是空）；失败拆成 `t.warning('榜单抓取失败')` + `t.info(原因)` |
 * | 传输层失败：老 `apiGet()` 自己 catch，折成 `请求失败（HTTP n）` / `网络请求失败：…` **返回值**（所以照样走上面那条 toast 分支） | `fetchRank()` 把 axios 的 reject 折回同一对文案与同一个 toast 分支（语义不变：传输失败也提示） |
 * | 意外异常（`renderDiscover` 里挂在 `.then(paint).catch(...)` 上的那条）→ `{error:'抓取失败，请稍后重试（' + e.message + '）'}`，不 toast | `loadRank()` 的 catch 原样照搬这句（老实现里 `apiGet` 从不 reject，所以那一支基本是死代码；这里留给"归一过程本身出意外"的情况） |
 * | `loadDiscoverForce(true)`：删缓存 → `toast('javdb-cli','正在重新抓取榜单…')` → 重抓 → `toast('榜单已更新','{n} 条','ok')` / `toast('重新抓取失败', e.error,'warn')` → `if (S.view==='discover') render()` | `reloadRank()`：两对 toast 逐字照搬；最后那次 `render()` 由响应式缓存更新替代（无需手动重绘） |
 * | `bindUi()` 的 `rank-retry`：`S.bootError && !cached(key)` → `bootAndRender()`，否则 `loadDiscoverForce(true)` | `retryRank()` 同条件：先 `store.refresh()`（重拉 `/bootstrap`），仍失败就停在错误框；否则走 `reloadRank()` |
 * | `bindCards(root)`：点卡片 `openMovie(num, id)`、`onmouseenter` 抢跑 `prefetchDetail` | `NumCard` 的 `@select` / `@hover`；本轮点开只 `emit('openMovie',…)`（见下方差异 1） |
 * | `prefetchCards(body, PREFETCH_N)`：paint 完之后预热前 6 张详情（串行、命中缓存跳过、失败不写条目） | `watch(movies)` 每次列表变化补一轮（`prefetchCards` 在模块级实现里，逐条对齐） |
 *
 * 刻意**不做**（本轮不做、或老实现也没有）：
 * - **详情抽屉不在这里**：老 `openMovie(number,id)` / `paintDetail` / 预览图 / 磁力 / 长图补图 / 灯箱
 *   （`ui/views/detail.js` + `ui/ui/lightbox.js`）是**下一轮**的独立视图；本轮只把番号与 id 交出去；
 * - 不做图片 `preload()`：老 `renderDiscover` 也没预热图片（`preload` 只服务于演员页与详情页）；
 * - 不把 `period`/`kind` 落到 `localStorage`：老实现只在内存里（`S`），刷新页面照样回到 周榜/有码；
 * - 不加「点击卡片时的 loading 遮罩」：老实现点下去就开抽屉，没有中间态；
 * - 不改 `.grid` 的列宽策略：照抄 `repeat(auto-fill, minmax(172px, 1fr))`。
 *
 * 与老实现的差异（都在下面各自位置有注释）：
 * 1. **点卡片只发事件**：老实现 `openMovie()` 直接开抽屉，抽屉下一轮才做 → 这里
 *    `emit('openMovie', {number, id})`，由壳（`Console.vue`）先给一句临时提示；
 * 2. **`booted` / `bootError` 的来源**：老实现是 `S.booted` / `S.bootError`（`bootAndRender()`
 *    失败时也会把 `booted` 置 true，并带 `接口无响应` 兜底文案进错误框）。这里用 store 的
 *    `booted`（成功 hydrate 过）与 `error`（读状态失败的那句话）。取不到文案时停在
 *    「正在读取插件状态…」等右栏那次 15 秒 `/bootstrap` 轮询自愈，而不是进一个只能反复重试的错误框；
 * 3. **同一 key 加了在途守卫**：老实现靠"有缓存就不发 + 每次 `render()` 重建 DOM"隐式避免重复请求；
 * 4. toast 拆成两行是宿主 toast 的单行正文所致（写法照 S6-4 订阅页 / S6-5 演员页）；
 * 5. `NumCard` 自带 `:title`（悬停显示片名）是 S6 地基里就有的通用件行为，老 `card()` 没有这个属性 —— 多一个 tooltip，不改文案与布局。
 */
import { computed, ref, watch } from 'vue'
import EmptyState from '../common/EmptyState.vue'
import ErrorState from '../common/ErrorState.vue'
import NumCard from '../common/NumCard.vue'
import { errorText, hostToast, type PluginApi } from '../../composables/usePluginApi'
import type { PluginStore } from '../../composables/usePluginStore'

const props = withDefaults(
  defineProps<{
    /** 数据台单一数据源（`Console.vue` 建好后传进来）：`favs` 决定「⭐已收藏演员」角标。 */
    store: PluginStore
    /** 本插件实例 id：给 `NumCard` → `Thumb` 拼图片代理地址用。 */
    pluginId?: string
    /**
     * 宿主请求器：榜单（`plugin/rankings`）与后台预热（`plugin/detail`）走它。
     * store 只暴露动作、不暴露底层请求器，而这两条是"模块级缓存 + 直接读形状"的读接口，
     * 与 S6-2/S6-3 用 `api` 补封面同一个理由。
     */
    api?: PluginApi | null
    /** 宿主 toast（`moviepilot:toast` 注入），拿不到时静默降级。 */
    toast?: unknown
  }>(),
  { pluginId: '', api: null, toast: null },
)

const emit = defineEmits<{
  /**
   * 点卡片：老 `openMovie(number, id)` 打开「影片详情」抽屉。
   * 抽屉是 §6.1 的最后一批（下一轮），本轮由壳先接一句临时提示。
   */
  (event: 'openMovie', payload: { number: string; id: string }): void
}>()

const t = hostToast(props.toast as any)

/** 周期切换项：老 `periodTabsHtml()` 的三项（文案与顺序逐字一致）。 */
const PERIOD_TABS = [
  { key: 'day', name: '日榜' },
  { key: 'week', name: '周榜' },
  { key: 'month', name: '月榜' },
]
/** 分类切换项：老 `zoneTabsHtml()` 的三项。 */
const ZONE_TABS = [
  { key: 'censored', name: '有码' },
  { key: 'uncensored', name: '无码' },
  { key: 'fc2', name: 'FC2' },
]

/** 模板侧的当前周期 / 分类（真身是模块级 ref，切栏目回来不变）。 */
const period = computed(() => periodState.value)
const kind = computed(() => kindState.value)

/** 切周期 / 切分类：老 `bindTabs(m)` 里的 `S.period = b.dataset.p` / `S.kind = b.dataset.z`。 */
function pickPeriod(key: string): void {
  periodState.value = key
}

function pickKind(key: string): void {
  kindState.value = key
}

// ---------- 首屏门与状态读取（老 `S.booted` / `S.bootError`） ----------

/** 插件状态（`/bootstrap`）读到过没有：老 `S.booted`。 */
const booted = computed(() => props.store.booted.value === true)
/** 状态读取失败的那句话：老 `S.bootError`（成功读到时是空串）。 */
const bootError = computed(() => String(props.store.error.value || ''))

// ---------- 缓存与取数 ----------

/** 当前榜单 key：老 `'rank:' + S.period + ':' + S.kind`。 */
const rankKey = computed(() => `rank:${period.value}:${kind.value}`)

/** 当前 key 的缓存条目（`undefined` = 还没抓过，画加载态）。 */
const entry = computed<RankEntry | null>(() => rankCache.get(rankKey.value) || null)

/** 当前榜单的片单：老 `entry.data || []`。 */
const movies = computed<RankMovie[]>(() => (entry.value && entry.value.data) || [])

/** 榜单错误文案：老 `entry.error`（有错时优先于列表与空态）。 */
const rankError = computed(() => String((entry.value && entry.value.error) || ''))

/** 在途的榜单请求 key：同一个 key 不重复发（差异 3）。 */
const inflight = new Set<string>()

/** 「重试」按钮的转圈态（老实现没有，是 `ErrorState` 的既有能力）。 */
const retrying = ref(false)

/**
 * 抓一次榜单（老 `loadDiscover(force)`）：`GET plugin/rankings?period=&kind=`。
 *
 * - 成功了只认 `movies`（老 `(r.data && r.data.movies) || []`，空数组就是空态）；
 * - 业务失败（`success:false`）/ HTTP 失败 / 网络异常都会写一条**只有 error 的**缓存条目，
 *   老实现同样如此（那正是工具条「n 部」在错误态下不显示的原因）。
 */
async function loadRank(p: string, k: string, force: boolean): Promise<void> {
  const key = `rank:${p}:${k}`
  if (!force && rankCache.has(key)) return
  if (inflight.has(key)) return
  inflight.add(key)
  try {
    const res = await fetchRank(p, k)
    if (!res.ok) {
      rankCache.set(key, { error: res.message || '抓取失败，请稍后重试' })
      t.warning('榜单抓取失败')
      t.info(res.message || '抓取失败，请稍后重试')
      return
    }
    rankCache.set(key, { error: '', data: res.movies })
  } catch (err) {
    // 老 `renderDiscover` 的 `.catch`：拼成一条错误条目，**不 toast**。
    rankCache.set(key, { error: `抓取失败，请稍后重试（${errorText(err)}）` })
  } finally {
    inflight.delete(key)
  }
}

/**
 * 传输层失败折成一句话：老 `apiGet()` 的两条文案（`请求失败（HTTP n）` / `网络请求失败：…`）。
 * 它们与业务失败走**同一个** toast 分支（老 `r.ok === false` 那一支），所以这里也返回消息而不是抛。
 */
function transportMessage(err: unknown): string {
  const status = Number((err as any)?.response?.status || (err as any)?.status || 0)
  if (status) return `请求失败（HTTP ${status}）`
  return `网络请求失败：${errorText(err)}`
}

/** 一次榜单请求的归一结果（老 `apiGet('/rankings')` 的 `{ok, data|message}`）。 */
async function fetchRank(
  p: string,
  k: string,
): Promise<{ ok: true; movies: RankMovie[] } | { ok: false; message: string }> {
  const api = props.api
  if (!api || typeof api.get !== 'function') return { ok: false, message: '宿主请求器不可用' }
  let raw: any
  try {
    raw = await api.get('plugin/rankings', { params: { period: p, kind: k } })
  } catch (err) {
    return { ok: false, message: transportMessage(err) }
  }
  const payload: any = unwrap(raw)
  if (payload && typeof payload === 'object' && payload.success === false) {
    return { ok: false, message: String(payload.message || payload.detail || '') }
  }
  const list = Array.isArray(payload?.movies)
    ? payload.movies
    : Array.isArray(payload?.data?.movies)
      ? payload.data.movies
      : []
  return { ok: true, movies: list as RankMovie[] }
}

/** 需要时才抓当前榜单（老 `if (entry) paint(entry); else loadDiscover(false)`）。 */
async function ensureRank(): Promise<void> {
  if (bootError.value || !booted.value) return
  await loadRank(period.value, kind.value, false)
}

/** 「↻ 重新抓取」与错误态的非 boot 分支：老 `loadDiscoverForce(true)`。 */
async function reloadRank(): Promise<void> {
  const p = period.value
  const k = kind.value
  const key = `rank:${p}:${k}`
  rankCache.delete(key)
  t.info('javdb-cli')
  t.info('正在重新抓取榜单…')
  await loadRank(p, k, true)
  const done = rankCache.get(key)
  if (done && !done.error) {
    t.success('榜单已更新')
    t.info(`${(done.data || []).length} 条`)
  } else {
    t.warning('重新抓取失败')
    t.info((done && done.error) || '')
  }
}

/**
 * 错误框里的「重试」：老 `bindUi()` 的 `rank-retry` 委托 ——
 * 状态没读到、且当前榜单还没有缓存时，先补一次状态（老 `bootAndRender()`）；
 * 其余情况都等于「重新抓取这一档榜单」。
 */
async function retryRank(): Promise<void> {
  retrying.value = true
  try {
    if (bootError.value && !rankCache.has(rankKey.value)) {
      await props.store.refresh()
      return
    }
    await reloadRank()
  } finally {
    retrying.value = false
  }
}

// ---------- 列表与卡片 ----------

/** 演员是否已在「我的演员」里：老 `mv.actor && S.favs.some(f => f.name === mv.actor)`。 */
function isActorFaved(movie: RankMovie): boolean {
  const actor = String(movie.actor || '')
  if (!actor) return false
  return (props.store.favs.value || []).some(item => item.name === actor)
}

/** 卡片 key：老实现按数组顺序画；这里用番号 + 下标，避免刷新时卡片被重建。 */
function cardKey(movie: RankMovie, index: number): string {
  return `${movie.number || ''}#${index}`
}

/** 点卡片：老 `bindCards` 的 `openMovie(num, id)`（本轮只发事件，见差异 1）。 */
function openCard(movie: RankMovie): void {
  emit('openMovie', { number: String(movie.number || ''), id: String(movie.id || '') })
}

/** 鼠标进入卡片：老 `onmouseenter = () => prefetchDetail(num, id)`，点下去时多半已在路上。 */
function hoverCard(movie: RankMovie): void {
  prefetchDetail(props.api, movie.number, movie.id)
}

// ---------- 生效点 ----------

/** 状态到位或切档之后：有缓存立刻画，没有就抓（老 `renderDiscover` 的分支）。 */
watch([booted, bootError, rankKey], () => void ensureRank(), { immediate: true })

/** paint 之后预热前 `PREFETCH_N` 张（老 `paint()` 末尾的 `prefetchCards(body, PREFETCH_N)`）。 */
watch(movies, list => prefetchCards(props.api, list), { immediate: true })
</script>

<template>
  <div class="avh-discover">
    <!-- 首屏：老 `render()` 的 `!S.booted && S.view==='discover'` 分支（连工具条都不画） -->
    <div v-if="!booted && !bootError" class="avh-discover__loading">正在读取插件状态…</div>

    <template v-else>
      <div class="avh-discover__toolbar">
        <div class="avh-tabs">
          <button
            v-for="item in PERIOD_TABS"
            :key="item.key"
            :class="{ 'avh-tabs__on': item.key === period }"
            @click="pickPeriod(item.key)"
          >{{ item.name }}</button>
        </div>
        <div class="avh-tabs">
          <button
            v-for="item in ZONE_TABS"
            :key="item.key"
            :class="{ 'avh-tabs__on': item.key === kind }"
            @click="pickKind(item.key)"
          >{{ item.name }}</button>
        </div>

        <!-- 老实现：`entry && entry.data` 才画「n 部」（错误态与首屏都没有它） -->
        <span v-if="!bootError && entry && entry.data" class="avh-discover__hint">
          {{ entry.data.length }} 部
        </span>

        <div class="avh-discover__spacer" />

        <!-- 老实现：状态读取失败时不画「↻ 重新抓取」（那种情况下重试按钮在错误框里） -->
        <v-btn v-if="!bootError" variant="outlined" size="small" @click="reloadRank">
          ↻ 重新抓取
        </v-btn>
      </div>

      <ErrorState
        v-if="bootError"
        :message="`插件状态读取失败：${bootError}（仍可尝试直接抓取榜单）`"
        :retrying="retrying"
        @retry="retryRank"
      />

      <template v-else>
        <ErrorState
          v-if="rankError"
          :message="rankError"
          :retrying="retrying"
          @retry="retryRank"
        />

        <div v-else-if="!entry" class="avh-discover__loading">正在抓取榜单…</div>

        <EmptyState v-else-if="!movies.length" text="该榜单暂无数据，换个周期 / 分类试试" />

        <div v-else class="avh-discover__grid">
          <NumCard
            v-for="(movie, index) in movies"
            :key="cardKey(movie, index)"
            :movie="movie"
            :plugin-id="pluginId"
            :actor-favorited="isActorFaved(movie)"
            @select="openCard(movie)"
            @hover="hoverCard(movie)"
          />
        </div>
      </template>
    </template>
  </div>
</template>

<style scoped>
/* 对齐 `.toolbar`：一行放两组 tabs + 计数 + 右侧按钮 */
.avh-discover__toolbar {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
  margin-bottom: 14px;
}

.avh-discover__spacer {
  flex: 1;
}

/* 对齐 `.hint` */
.avh-discover__hint {
  font-size: 12px;
  color: rgba(var(--v-theme-on-surface), 0.5);
}

/* 对齐 `.loading`（首屏那句与榜单那句共用） */
.avh-discover__loading {
  padding: 44px 20px;
  text-align: center;
  font-size: 13px;
  color: rgba(var(--v-theme-on-surface), 0.5);
}

/* 对齐 `.tabs`：胶囊容器 + 选中那颗走主色（写法照演员页的 `.avh-filmyears`） */
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

/* 对齐 `.grid`：`repeat(auto-fill,minmax(172px,1fr))`，卡片本体是 `NumCard` */
.avh-discover__grid {
  display: grid;
  gap: 14px;
  grid-template-columns: repeat(auto-fill, minmax(172px, 1fr));
}
</style>
