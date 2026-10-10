/**
 * 后台「详情抢跑」的**队列纪律**（老实现 `ui/views/discover.js` 的
 * `PRE` / `prefetchDetail` / `pumpPrefetch` / `prefetchCards`，原本只在发现榜单里）。
 *
 * 为什么单独成文件：演员作品史要的是**同一条纪律**，但队列必须按"谁在看"隔离 ——
 * | 老实现 | 这里 |
 * | --- | --- |
 * | 全局 `PRE = {queue:[], busy:false}`，`pumpPrefetch()` 串行取队首 | `createDetailPrefetcher()` 每个视图各一份队列，同一个 pump |
 * | `apiGet('/detail')` 回来无条件 `put('detail:'+num, …)` | 回来前先过一次 `gen`（代数）闸门：期间被 `flush()` 过就**丢弃**，不写缓存 |
 * | 换演员时靠 `render()` 整块重建、旧响应落地也无所谓（缓存按番号存） | 换演员/卸载时 `flush()`：队里没跑的丢掉、在飞的那条标记作废（落地前被拦） |
 *
 * **为什么队列不能放模块级**：壳（`Console.vue`）用
 * `:key="section === 'actors' ? \`actors:${actorNonce}\` : section"` 挂视图，详情抽屉里点演员 →
 * `actorNonce++` → **旧实例卸载 + 新实例挂载**。模块级队列会让旧实例卸载时的 `flush()`
 * 把新实例刚排进去的作品史任务一起清掉。一份队列一个实例，"我的任务只被我自己取消"才成立。
 * （发现榜单那边仍是模块级单例 —— 老 `PRE` 也是全局的，见 `discoverCache.ts`。）
 *
 * 与老实现逐条对齐的纪律：
 * 1. **串行**：同一时刻只有一条在飞（`busy` 闸门；老实现的注释：不并发压多个 javdb 子进程）。
 *    被 `flush()` 取消的那条会先落定，下一轮才进 pump —— 所以"取消 + 新起"也不会重叠；
 * 2. **限量**：`enqueueMany` 只预热前 `PREFETCH_N` 张；
 * 3. **命中缓存跳过**：`detailCache` 里已有该番号就不再排队、也不发请求
 *    （切周期/切分类来回看、换年/展开时不重复抓）；
 * 4. **已在队列里不重复排**（+ 跨队列：同一个番号已在别的视图在飞也不重复发）；
 * 5. **失败不写任何条目**（老 `if (r.ok) put(...)` + `.catch(() => {})`），留给真正打开时报错重试。
 */
import { cachedDetail, putDetail } from './detailCache'
import { unwrap, type PluginApi } from './usePluginApi'

/** 每屏后台预热前几张：老 `PREFETCH_N = 6`（调大 = 点开更快、后台开销更多）。 */
export const PREFETCH_N = 6

/**
 * 图片预热（老 `ui/ui/image.js` 的 `preload` 单张版：
 * `if (u) { const im = new Image(); im.decoding = 'async'; im.src = u }`）。
 *
 * **这是"照抄"，不是"绕过图片链"**：老实现也把原地址直接塞给 `new Image()`，
 * 失败就悄悄算数（`Thumb` 的 `/img` 代理回落是**另一条**链，只有 `<img onerror>` 才会走）。
 * 换成代理地址预热会改变老行为语义（多打一次 `?url=`），所以不换 ——
 * 真要连代理一起预热，得等 `Thumb` 那条链也抽成可共用的小件（本轮不做）。
 */
export function warmImage(url: unknown): void {
  const src = String(url ?? '')
  if (!src) return
  const image = new Image()
  image.decoding = 'async'
  image.src = src
}

/**
 * 番号形状：`SSIS-901` / `FC2-PPV-4455667` / `259LUXU-123` 之类。
 *
 * 老实现只判"非空"；真实返回里番号永远是「字母数字 + 连字符」这种形状，这里收一道闸
 * 是为了不去预热空白/"无番号"的垃圾项（会白起一个 javdb 子进程），对真实番号零影响。
 */
const NUMBER_RE = /^[A-Za-z0-9][A-Za-z0-9._-]*$/

/** 一个待预热的番号（老实现 `PRE.queue` 里的 `{num, id}`）。 */
interface PrefetchJob {
  number: string
  /** javdb 内部 id：带上能省掉子进程里那次「番号 → id」搜索往返。 */
  id: string
}

/** 在飞的番号（跨队列去重：两个视图同时预热同一部片时，第二条不再发）。 */
const inFlight = new Set<string>()

/** 预热器接口（一个视图一份队列；发现榜单与演员作品史都用它）。 */
export interface DetailPrefetcher {
  /** 排一个番号进队（命中缓存 / 已在队里 / 已在飞都会静默跳过）。 */
  enqueue(number: unknown, id?: unknown): void
  /** 排一批（老 `prefetchCards`：只取前 n 个）。 */
  enqueueMany(movies: ReadonlyArray<{ number?: unknown; id?: unknown }> | null | undefined, n?: number): void
  /**
   * 取消：队里没跑的丢掉、在飞的那条作废（回来时被代数闸门拦下、不写缓存），
   * 在飞的那次顺手 abort，并等它落定才放行下一轮（串行因此不被破坏）。
   */
  flush(): void
  /** 队列 + 在飞是否为空（工装/自检用，产品代码不需要）。 */
  idle(): boolean
}

/** 在飞的那次请求（`flush()` 要能 abort 它、并等它落定后才放行下一轮）。 */
interface PrefetchRequest {
  controller: AbortController
  /** 这次请求的完整生命周期（含落地/丢弃与收尾）。 */
  promise: Promise<void> | null
}

/** 队列（每个预热器一份）。 */
interface PrefetchQueue {
  jobs: PrefetchJob[]
  busy: boolean
  gen: number
  req: PrefetchRequest | null
}

/** 创建一个"详情抢先跑"的预热器（api 用取值函数传，宿主请求器可能晚到）。 */
export function createDetailPrefetcher(api: () => PluginApi | null | undefined): DetailPrefetcher {
  const queue: PrefetchQueue = { jobs: [], busy: false, gen: 0, req: null }

  /** 宿主请求器可用吗（不可用时就默默不预热，等下一次 `enqueue`）。 */
  function getApi(): PluginApi | null {
    const value = api()
    return value && typeof value.get === 'function' ? value : null
  }

  /**
   * 串行取详情（老 `pumpPrefetch()`）：
   * 取队首 → 命中缓存（或已在别处飞）就再抽下一个 → 否则发一次
   * `GET plugin/detail?number=&id=` → 完成后继续。
   */
  async function pump(): Promise<void> {
    if (queue.busy) return
    /* 命中缓存 / 已在别的队列在飞的那些直接跳过（老 `pumpPrefetch` 的递归那两句）；
       用循环而不是递归：不必靠"同步递归"去和 `busy` 抢时序。 */
    let job = queue.jobs.shift()
    while (job && (cachedDetail(job.number) || inFlight.has(job.number))) job = queue.jobs.shift()
    if (!job) return
    const client = getApi()
    if (!client) {
      /* 请求器还不认识（首屏那一下）：整队丢掉，等下一次 `enqueue` 重新排。 */
      queue.jobs = []
      return
    }
    const gen = queue.gen
    const controller = new AbortController()
    const req: PrefetchRequest = { controller, promise: null }
    queue.busy = true
    queue.req = req
    inFlight.add(job.number)
    req.promise = (async () => {
      try {
        // 老 `apiUrl()` 会把空值参数丢掉，所以 id 为空时不带这一段。
        const params: Record<string, string> = { number: job.number }
        if (job.id) params.id = job.id
        const payload: any = unwrap(
          await client.get('plugin/detail', { params, signal: controller.signal }),
        )
        if (gen !== queue.gen) return // 期间被取消（换演员 / 卸载）：结果不落地
        if (payload && typeof payload === 'object' && payload.success === false) return
        putDetail(job.number, (payload as Record<string, any>) || {})
      } catch {
        /* 预热失败静默（老实现 `.catch(() => {})`）；被 abort 的那条也走这里 */
      } finally {
        inFlight.delete(job.number)
        if (queue.req === req) {
          queue.req = null
          queue.busy = false
        }
        /* 收尾之后再抽下一个（老 `pumpPrefetch()` 末尾那句递归；这里同样不 await）。 */
        void pump()
      }
    })()
  }

  function enqueue(number: unknown, id?: unknown): void {
    const num = String(number ?? '').trim()
    if (!num || !NUMBER_RE.test(num)) return
    if (cachedDetail(num)) return
    if (queue.jobs.some(job => job.number === num)) return
    if (inFlight.has(num)) return
    queue.jobs.push({ number: num, id: String(id ?? '') })
    void pump()
  }

  function flush(): void {
    queue.jobs = []
    queue.gen += 1
    const req = queue.req
    if (!req) {
      queue.busy = false
      return
    }
    /* 在飞的那条：abort + 标记作废（`gen` 已经变了，回来也不落地），
       并等它彻底落定（`finally` 会清 `busy`/`req`/`inFlight`）再让下一轮进 pump。 */
    queue.busy = true
    try {
      req.controller.abort()
    } catch {
      /* abort 不该抛；真抛了也不影响"结果不落地"（代数闸门还在） */
    }
    const resume = () => void pump()
    Promise.resolve(req.promise).then(resume, resume)
  }

  return {
    enqueue,
    enqueueMany(movies, n = PREFETCH_N) {
      ;(movies || []).slice(0, n).forEach(movie => enqueue(movie?.number, movie?.id))
    },
    flush,
    idle: () => !queue.busy,
  }
}
