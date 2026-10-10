/**
 * 发现榜单的**模块级**状态：榜单缓存 / 后台详情预热（老实现 `ui/views/discover.js` 的
 * `PRE` / `prefetchDetail` / `pumpPrefetch` / `prefetchCards`，以及
 * `ui/core/state.js` 里全局 `CACHE` 的 `rank:<period>:<kind>` 那一半）。
 *
 * 为什么这些必须放模块作用域（`<script setup>` 里的顶层变量会随组件卸载丢掉，
 * 而 `Console.vue` 的 `<component :is>` 没有 keep-alive，切栏目就是卸载）：
 * - 榜单缓存在，切走再回「发现榜单」不重抓榜单（javdb 有站点限流，这条是纪律不是优化）；
 * - 详情缓存在（见 `detailCache.ts`），后台预热的结果才留得住 —— 详情抽屉（S6-7）直接读它；
 * - `period` / `kind` 在，切走再回来还停在你上次看的那一档（老 `S.period` / `S.kind` 是全局的）。
 *
 * **S6-7 拆出来的原因**：详情抽屉的骨架 `skeletonHtml(number)` 要照老 `findMovie(number)`
 * 遍历「所有列表缓存」找那张卡片，它得读这份 `rankCache`；让抽屉反向 import 视图模块
 * 会在 `views/DiscoverView.vue ↔ detail/DetailDrawer.vue` 之间绕一圈，所以榜单缓存
 * 与详情缓存一样，各自落在一个 composable 里，两边都从那儿取。
 */
import { reactive, ref } from 'vue'
import { unwrap, type PluginApi } from './usePluginApi'
import { detailCache, putDetail } from './detailCache'

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

/** 榜单缓存：键 `rank:<period>:<kind>`，跨栏目切换存活（老 `CACHE`）。 */
export const rankCache = reactive(new Map<string, RankEntry>())

/**
 * 当前榜单周期：老 `S.period`（默认 `week`，全局存活，切栏目回来不变）。
 * `<script setup>` 的模板绑定只能在 setup 里声明，所以视图里再取一个计算属性。
 */
export const periodState = ref('week')

/** 当前榜单分类：老 `S.kind`（默认 `censored`）。 */
export const kindState = ref('censored')

/**
 * 详情缓存与它的写入口（真身在 `composables/detailCache.ts`）。
 * 转出一手是为了让「发现榜单」这一个模块就能拿到它需要的全部缓存，
 * 不必在两个 composable 之间来回 import（抽屉那边直接 import `detailCache.ts`）。
 */
export { cachedDetail, detailCache, putDetail } from './detailCache'

/** `unwrap`（信封/裸数据两形状兼容）转出一手：视图那边从同一个模块取，少一处 import。 */
export { unwrap } from './usePluginApi'

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
    putDetail(job.number, (payload as Record<string, any>) || {})
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
