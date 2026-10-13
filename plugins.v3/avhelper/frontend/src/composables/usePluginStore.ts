/**
 * 数据台的单一数据源 + 动作层（S6 地基）。
 *
 * 边界：
 * - 数据形状与端点**对齐老实现**（`ui/views/*.js` + `ui/core/api.js`），端点清单见文件末尾注释；
 * - 只依赖调用方传入的宿主 `api`（与 `Console.vue` 的 `currentApi()` 用法一致，路径写 `plugin/xxx`），
 *   不引 `vue-router` / `pinia` 之类新依赖，也不自己去拼实例 id；
 * - 只管"数据与动作"，不管当前栏目/榜单周期这类界面状态（那是各视图自己的事）。
 *
 * 与老实现的已知差异（刻意，见交付报告）：
 * 1. 老实现 `apiGet` 每次请求都从同源 `localStorage` 扫 JWT 自己发 fetch；这里走宿主 `api`，
 *    鉴权由宿主 axios 负责（联邦组件拿不到、也不该拿 token）。
 * 2. 老实现 `applyBootstrap` 会在规则站点为空时**就地改写** `S.rule.sites/prefSites`；
 *    这里保持后端返回的规则原样（空数组 = 全部站点，语义本来就对），不改写。
 * 3. 老实现每个动作各自 `toast`；这里只返回 `ActionResult`，由视图决定文案与提示方式。
 * 4. `refresh()` 有一条公开的兄弟 `hydrate(payload)`：壳/设置台已经在轮询 `/bootstrap`，
 *    数据台视图读的是同一份数据，没必要第二次打同一个端点（`refresh()` 内部就是
 *    「取一次 + hydrate」，解析规则只有一份）。
 */
import { computed, ref, shallowRef, type Ref } from 'vue'
import { errorText } from './usePluginApi'
import {
  SITES_FALLBACK,
  toRule,
  type ActionResult,
  type ActionResultKind,
  type BootstrapPayload,
  type Candidate,
  type FavActor,
  type NoticeItem,
  type PluginApi,
  type QueueItem,
  type RuleValue,
  type SearchTask,
  type SiteOption,
  type Subscription,
} from './storeTypes'

/** 请求器的兜底：宿主没传 `api` 时动作立刻失败，界面照样画得出来。 */
export const NOOP_API: PluginApi = {
  get: () => Promise.reject(new Error('宿主 api 不可用')),
  post: () => Promise.reject(new Error('宿主 api 不可用')),
}

/** `POST plugin/check` 的返回（后端 `api_check`）。 */
export interface CheckResult {
  limited?: boolean
  notices?: NoticeItem[]
  message?: string
  subs?: Subscription[]
  tasks?: SearchTask[]
  queue?: QueueItem[]
}

/** `POST plugin/tasks/download` 的返回（后端 `api_task_download`）。 */
export interface TaskDownloadResult {
  notice?: NoticeItem | null
  hash?: string
  downloader?: string
  queue?: QueueItem[]
  message?: string
}

/** `POST plugin/magnet-download` 的返回（后端 `api_magnet_download`）。 */
export interface MagnetDownloadResult {
  hash?: string
  downloader?: string
  queue?: QueueItem[]
  message?: string
}

/** 后端给的提示语（`acquire` 的 `toasts`）：前端只管按序弹，不判逻辑。 */
export interface PluginToast {
  level?: string
  text?: string
}

/** `POST plugin/tasks/acquire` 的返回（后端 `api_task_acquire`，0.6.0）。 */
export interface AcquireResult {
  /** `downloaded` = 已按规则当场下单；`pending` = 落进「任务」页待确认。 */
  outcome?: string
  /** PT 段：`hit` 有合格候选 / `miss` 没有。 */
  pt?: string
  /** BT 兜底：`hit` / `miss` / `off`（开关关着）/ `skipped`（PT 已命中，不必兜底）。 */
  bt?: string
  /** 任务卡上的标记：`''` | `pt-only` | `none`。 */
  pending?: string
  task?: SearchTask
  candCount?: number
  passCount?: number
  hash?: string
  downloader?: string
  site?: string
  spec?: string
  toasts?: PluginToast[]
  queue?: QueueItem[]
  message?: string
}

/** 每次请求的形状判定结果。 */
type Outcome = { ok: true; res: Record<string, any> } | { ok: false; message: string }

/** 从任意响应/异常里挖一句可显示的中文文案（后端用 `message`，个别地方用 `detail`）。 */
function textOf(value: unknown): string {
  if (!value || typeof value !== 'object') return ''
  const record = value as Record<string, unknown>
  for (const key of ['message', 'detail', 'msg']) {
    const text = record[key]
    if (typeof text === 'string' && text.trim()) return text.trim()
  }
  return ''
}

/** 数组字段原样取，非数组一律不认（老实现 `Array.isArray` 的同一套判定）。 */
function listOf<T>(value: unknown): T[] | null {
  return Array.isArray(value) ? (value as T[]) : null
}

/**
 * 映射类字段（`aliases`）原样取：只认纯对象，值统一成字符串。
 *
 * 与 `listOf` 分开是因为 `Array.isArray({})` 是 false、`typeof [] === 'object'` 也为真，
 * 两者混用会把数组当成映射去遍历。空对象 `{}` 是**合法值**（表示一条备注都没有），
 * 所以这里只对"非对象"返回 `null`，不像 `listOf` 那样顺带把空当作缺失。
 */
function mapOf(value: unknown): Record<string, string> | null {
  if (!value || typeof value !== 'object' || Array.isArray(value)) return null
  const out: Record<string, string> = {}
  Object.keys(value as Record<string, unknown>).forEach(key => {
    out[key] = String((value as Record<string, unknown>)[key] ?? '')
  })
  return out
}

export function usePluginStore(api: PluginApi) {
  const client: PluginApi = api && typeof api.get === 'function' ? api : NOOP_API

  // ---------- 状态（形状 = GET plugin/bootstrap 的返回） ----------
  const enabled = ref(true)
  const sites: Ref<SiteOption[]> = ref([])
  const favs: Ref<FavActor[]> = ref([])
  /**
   * 演员自定义备注（`{演员原名: 备注}`）。
   *
   * 与 `favs` **分开存**：备注挂在演员原名上，没收藏的演员也能有备注，所以不能只从
   * `favs` 派生。只含非空项（后端 `alias_map()` 已把清除掉的行滤掉），查不到就是没备注。
   */
  const aliases: Ref<Record<string, string>> = ref({})
  const subs: Ref<Subscription[]> = ref([])
  /** 已知番号：`Set` 便于判断，老实现同款（`new Set(d.known)`）。 */
  const known = shallowRef<Set<string>>(new Set())
  const notices: Ref<NoticeItem[]> = ref([])
  const tasks: Ref<SearchTask[]> = ref([])
  const queue: Ref<QueueItem[]> = ref([])
  const rule: Ref<RuleValue> = ref(toRule(null))
  /** 未归一化的原始规则（保存前对比、只读展示用）。 */
  const ruleRaw: Ref<RuleValue> = ref(toRule(null))

  const loading = ref(false)
  const error = ref('')
  /** 上次成功刷新的本地时间（`HH:MM:SS`）。 */
  const updatedAt = ref('')
  const booted = ref(false)

  /** 每个动作一份 in-flight 标记：重复点击合并，不并发打同一端点。 */
  const busy = ref<Record<string, boolean>>({})

  // ---------- 派生值（角标与空态） ----------
  /** 待确认任务数（老 `renderPills` 的 `pillTasks`）。 */
  const awaitTasks = computed(() => tasks.value.filter(item => item.state === 'await').length)
  /** 未完成的下载数（老 `renderPills` 的 `pillQueue`）。 */
  const downloading = computed(() => queue.value.filter(item => item.state !== 'done').length)

  async function guarded<T>(
    key: string,
    run: () => Promise<ActionResult<T>>,
  ): Promise<ActionResult<T>> {
    if (busy.value[key]) {
      return { ok: false, kind: 'busy', message: '上一次操作还在进行中，请稍候' }
    }
    busy.value = { ...busy.value, [key]: true }
    try {
      return await run()
    } finally {
      const next = { ...busy.value }
      delete next[key]
      busy.value = next
    }
  }

  /** 发一次请求并把「HTTP/网络/业务失败」折成同一形状。 */
  async function send(
    method: 'get' | 'post' | 'delete',
    path: string,
    body?: unknown,
    query?: Record<string, string | number>,
  ): Promise<Outcome> {
    try {
      let raw: any
      if (method === 'get') {
        raw = await client.get(`plugin/${path}`)
      } else if (method === 'post') {
        raw = await client.post(`plugin/${path}`, body === undefined ? {} : body)
      } else {
        if (typeof client.delete !== 'function') {
          return { ok: false, message: '宿主请求器不支持 DELETE，无法执行该操作' }
        }
        const config = query && Object.keys(query).length ? { params: query } : undefined
        raw = await client.delete(`plugin/${path}`, config)
      }
      if (raw && typeof raw === 'object' && !Array.isArray(raw)) {
        const record = raw as Record<string, any>
        if (record.success === false) {
          return { ok: false, message: textOf(record) || '接口返回失败' }
        }
        return { ok: true, res: record }
      }
      // 数组或其他标量：包一层，调用方按字段取数组时自然落空。
      return { ok: true, res: { data: raw } }
    } catch (err) {
      return { ok: false, message: textOf((err as any)?.payload) || errorText(err) }
    }
  }

  /** 列表类端点（`/check`、`/subs`、`/tasks`）可能顺带回传最新快照，有就同步。 */
  function syncLists(res: Record<string, any>): void {
    const nextSubs = listOf<Subscription>(res.subs)
    if (nextSubs) subs.value = nextSubs
    const nextTasks = listOf<SearchTask>(res.tasks)
    if (nextTasks) tasks.value = nextTasks
    const nextQueue = listOf<QueueItem>(res.queue)
    if (nextQueue) queue.value = nextQueue
  }

  /** 新通知插到最前（老实现 `S.notices.unshift(...)` 的语义）。 */
  function prependNotices(incoming: unknown): void {
    const items = listOf<NoticeItem>(incoming)
    if (!items?.length) return
    notices.value = [...items, ...notices.value]
  }

  /** 站点清单兜底：`bootstrap` 没给就单查 `/sites`（老 `ensureSites()`）。 */
  async function ensureSites(): Promise<boolean> {
    if (sites.value.length) return true
    const outcome = await send('get', 'sites')
    if (!outcome.ok) return false
    const payload = (outcome.res.data ?? outcome.res) as Record<string, any>
    const list = listOf<SiteOption>(payload.sites) || listOf<SiteOption>(payload) || []
    if (list.length) sites.value = list
    return sites.value.length > 0
  }

  /**
   * 用一份已有的 `/bootstrap` 载荷灌状态（**不发请求**）。
   *
   * 用途：壳（`Console.vue`）与设置台各自已经在拉 `/bootstrap`（`useRuntimeInfo` 15s 轮询），
   * 数据台视图读的同一份数据没必要再打一次；解析规则与 `refresh()` 完全一致
   * （`refresh()` 现在就是「取一次 + hydrate」）。
   *
   * :param payload: 裸载荷或 `{success, data}` 信封都认。
   * :return: 是否成功灌入（信封 `success === false` 时返回 `false` 并把文案写进 `error`）。
   */
  async function hydrate(payload: unknown): Promise<boolean> {
    const envelope =
      payload && typeof payload === 'object' && 'data' in (payload as Record<string, unknown>)
        ? (payload as Record<string, any>)
        : null
    if (envelope && envelope.success === false) {
      error.value = textOf(envelope) || 'bootstrap 失败'
      return false
    }
    const data = ((envelope ? envelope.data : payload) || {}) as BootstrapPayload

    if (typeof data.enabled === 'boolean') enabled.value = data.enabled

    const nextSites = listOf<SiteOption>(data.sites)
    if (nextSites?.length) sites.value = nextSites
    const nextFavs = listOf<FavActor>(data.favs)
    if (nextFavs) favs.value = nextFavs
    const nextSubs = listOf<Subscription>(data.subs)
    if (nextSubs) subs.value = nextSubs
    const nextTasks = listOf<SearchTask>(data.tasks)
    if (nextTasks) tasks.value = nextTasks
    const nextQueue = listOf<QueueItem>(data.queue)
    if (nextQueue) queue.value = nextQueue
    const nextNotices = listOf<NoticeItem>(data.notices)
    if (nextNotices) notices.value = nextNotices
    const nextKnown = listOf<string>(data.known)
    if (nextKnown) known.value = new Set(nextKnown.map(item => String(item)))
    const nextAliases = mapOf(data.aliases)
    if (nextAliases) aliases.value = nextAliases
    if (data.defaultRule && typeof data.defaultRule === 'object') {
      ruleRaw.value = data.defaultRule
      rule.value = toRule(data.defaultRule)
    }

    await ensureSites()
    error.value = ''
    booted.value = true
    const now = new Date()
    updatedAt.value = [now.getHours(), now.getMinutes(), now.getSeconds()]
      .map(part => String(part).padStart(2, '0'))
      .join(':')
    return true
  }

  // ---------- 刷新 ----------
  /**
   * 拉 `plugin/bootstrap` 灌满全部状态。
   *
   * 失败时**保留**已有数据（老实现同样只是记 `S.bootError` 并不清空），
   * 供界面继续显示上一份快照并提示错误。
   */
  async function refresh(): Promise<boolean> {
    if (loading.value) return false
    loading.value = true
    try {
      const outcome = await send('get', 'bootstrap')
      if (!outcome.ok) {
        error.value = outcome.message || 'bootstrap 失败'
        return false
      }
      return await hydrate(outcome.res)
    } finally {
      loading.value = false
    }
  }

  // ---------- 动作 ----------
  /**
   * `POST plugin/check`：手动检查订阅（**受限流**）。
   *
   * 被限流时后端返回 `success: true + limited: true`，那是**业务结果不是错误**：
   * `ok` 仍为 `true`，`kind` 为 `'limited'`，界面照老实现提示「检查被限流」。
   *
   * :param name: 只检查这一条订阅（演员名/番号）；空串 = 检查全部。
   */
  function runCheck(name = ''): Promise<ActionResult<CheckResult>> {
    return guarded('check', async () => {
      const outcome = await send('post', 'check', name ? { name } : {})
      if (!outcome.ok) return { ok: false, kind: 'error' as ActionResultKind, message: outcome.message }
      const payload = (outcome.res.data ?? outcome.res) as CheckResult
      syncLists(outcome.res as Record<string, any>)
      prependNotices(payload.notices)
      const limited = payload.limited === true
      return {
        ok: true,
        kind: limited ? ('limited' as ActionResultKind) : ('ok' as ActionResultKind),
        limited,
        message: payload.message || (limited ? '距上次检查不足间隔，已跳过' : '检查完成'),
        data: payload,
      }
    })
  }

  /**
   * `DELETE plugin/subs?id=`：取消订阅。
   *
   * 老实现传的就是订阅读取到的数字 id；这里额外容忍被传成订阅名（先在本地列表里找）。
   * 注意老实现"缺 id 就直接 toast 报错、不发请求"的分支被保留。
   */
  function unsubscribe(kindOrId: string | number): Promise<ActionResult> {
    return guarded('unsubscribe', async () => {
      const raw = String(kindOrId ?? '').trim()
      if (!raw) return { ok: false, kind: 'error' as ActionResultKind, message: '这条订阅缺少 id，无法删除' }
      let id = raw
      if (!/^\d+$/.test(raw)) {
        const hit = subs.value.find(item => String(item.name ?? '') === raw)
        if (!hit || hit.id === undefined || hit.id === null || !/^\d+$/.test(String(hit.id))) {
          return { ok: false, kind: 'error' as ActionResultKind, message: `找不到订阅「${raw}」的 id，无法删除` }
        }
        id = String(hit.id)
      }
      const outcome = await send('delete', 'subs', undefined, { id })
      if (!outcome.ok) return { ok: false, kind: 'error' as ActionResultKind, message: outcome.message }
      if (outcome.res.success !== true) {
        return { ok: false, kind: 'error' as ActionResultKind, message: textOf(outcome.res) || '请稍后重试' }
      }
      // 就地移除（不等下一次 bootstrap）：老实现 `S.subs = S.subs.filter(...)`。
      subs.value = subs.value.filter(item => String(item.id ?? '') !== id)
      return { ok: true, kind: 'ok' as ActionResultKind, message: textOf(outcome.res) || '已取消订阅' }
    })
  }

  /**
   * `POST plugin/favs`：收藏一个演员（老 `views/actors.js` 的 `addFav`）。
   *
   * 与老实现逐条对齐：
   * - **已收藏就不发请求**（老实现 `if (findFav(name)){ toast('已收藏', name); return true; }`）；
   * - 成功后**就地 push**，不拿响应里的 `favs` 覆盖整表（老实现 `S.favs.push(f)`：后端那份快照
   *   要等下一次 `/bootstrap` 才生效，`hydrate` 会接手）；
   * - 演员名缺失 → `缺少演员名`（与后端 `api_favs` 同一句）。
   */
  function addFav(name: string, zh = '', avatar = ''): Promise<ActionResult<FavActor>> {
    return guarded('fav', async () => {
      const target = String(name ?? '').trim()
      if (!target) return { ok: false, kind: 'error' as ActionResultKind, message: '缺少演员名' }
      const hit = favs.value.find(item => item.name === target)
      if (hit) return { ok: true, kind: 'ok' as ActionResultKind, message: '已收藏', data: hit }
      const outcome = await send('post', 'favs', { name: target, zh: zh || '', avatar: avatar || '' })
      if (!outcome.ok) return { ok: false, kind: 'error' as ActionResultKind, message: outcome.message }
      if (outcome.res.success !== true) {
        return { ok: false, kind: 'error' as ActionResultKind, message: textOf(outcome.res) || '请稍后重试' }
      }
      const entry: FavActor = { name: target, zh: zh || '', avatar: avatar || '' }
      if (!favs.value.some(item => item.name === target)) favs.value = [...favs.value, entry]
      return {
        ok: true,
        kind: 'ok' as ActionResultKind,
        message: textOf(outcome.res) || `已收藏 ${target}`,
        data: entry,
      }
    })
  }

  /**
   * `DELETE plugin/favs?name=`：取消收藏（老 `views/actors.js` 的 `delFav`）。
   * 成功后**就地**从 `favs` 里摘掉（老实现 `S.favs = S.favs.filter(...)`）。
   */
  function delFav(name: string): Promise<ActionResult> {
    return guarded('fav', async () => {
      const target = String(name ?? '').trim()
      if (!target) return { ok: false, kind: 'error' as ActionResultKind, message: '缺少演员名' }
      const outcome = await send('delete', 'favs', undefined, { name: target })
      if (!outcome.ok) return { ok: false, kind: 'error' as ActionResultKind, message: outcome.message }
      if (outcome.res.success !== true) {
        return { ok: false, kind: 'error' as ActionResultKind, message: textOf(outcome.res) || '请稍后重试' }
      }
      favs.value = favs.value.filter(item => item.name !== target)
      return {
        ok: true,
        kind: 'ok' as ActionResultKind,
        message: textOf(outcome.res) || `已取消收藏 ${target}`,
      }
    })
  }

  /**
   * `POST plugin/aliases`：写一位演员的自定义备注（`alias` 空串 = 清除）。
   *
   * 本动作与 `favs` **无关**：键是演员原名，没收藏的演员也能写（后端两张表）。
   * 成功后**就地**更新本地表（空串删键），不整表覆盖 —— 照 `addFav`/`delFav` 的纪律；
   * 若响应里带了 `aliases` 快照也顺手合并进来（后端每次都回，等于顺带对齐一次）。
   * 名字为空在本地就拦掉，不发请求（与后端同一句文案）。
   */
  function setAlias(name: string, alias: string): Promise<ActionResult<Record<string, string>>> {
    return guarded('alias', async () => {
      const target = String(name ?? '').trim()
      if (!target) return { ok: false, kind: 'error' as ActionResultKind, message: '缺少演员名' }
      const text = String(alias ?? '').trim()
      const outcome = await send('post', 'aliases', { name: target, alias: text })
      if (!outcome.ok) return { ok: false, kind: 'error' as ActionResultKind, message: outcome.message }
      if (outcome.res.success !== true) {
        return { ok: false, kind: 'error' as ActionResultKind, message: textOf(outcome.res) || '请稍后重试' }
      }
      const next = { ...aliases.value }
      if (text) next[target] = text
      else delete next[target]
      aliases.value = next
      const synced = mapOf(outcome.res.aliases)
      if (synced) aliases.value = synced
      return {
        ok: true,
        kind: 'ok' as ActionResultKind,
        message: textOf(outcome.res) || (text ? `已保存备注 ${text}` : `已清除备注 ${target}`),
        data: aliases.value,
      }
    })
  }

  /**
   * `POST plugin/subs`：新建订阅。
   *
   * 老实现两处调用点：
   * - 番号订阅 `subscribeNumber(num)` → `{type:'number', name:num}`；
   * - 演员订阅 `subActorDialog(name, zh, avatar)` → `{type:'actor', name, rule}`。
   * 两者合成本方法：`kind` 缺省 `'number'`，`rule` 传了才带（后端会用全局规则合并）。
   *
   * :param kind: `'number'`（番号）或 `'actor'`（演员）。
   * :param name: 番号或演员名。
   * :param actor: 番号订阅时顺带传的演员名（详情页有就用；后端忽略未知字段，仅作请求可读性）。
   * :param rule: 演员订阅的规则副本；不传表示用全局规则。
   */
  function subscribeNumber(
    name: string,
    kind: 'number' | 'actor' = 'number',
    actor = '',
    rule?: RuleValue | null,
  ): Promise<ActionResult> {
    return guarded('subscribe', async () => {
      const target = String(name ?? '').trim()
      if (!target) return { ok: false, kind: 'error' as ActionResultKind, message: '订阅参数不完整' }
      const body: Record<string, unknown> = { type: kind, name: target }
      if (kind === 'number' && actor) body.actor = actor
      if (rule && typeof rule === 'object') body.rule = rule
      const outcome = await send('post', 'subs', body)
      if (!outcome.ok) return { ok: false, kind: 'error' as ActionResultKind, message: outcome.message }
      if (outcome.res.success !== true) {
        return { ok: false, kind: 'error' as ActionResultKind, message: textOf(outcome.res) || '请稍后重试' }
      }
      const nextSubs = listOf<Subscription>(outcome.res.subs)
      if (nextSubs) subs.value = nextSubs
      return {
        ok: true,
        kind: 'ok' as ActionResultKind,
        message: textOf(outcome.res) || `已订阅 ${target}`,
      }
    })
  }

  /**
   * `POST plugin/tasks/search`：站点搜索（真站点，受限流）。
   *
   * 两种用法与后端一致：
   * - 番号搜索（任务页 / 详情页「搜索 PT 站」）→ `{number}`（可带 `actor` / `thumb`）；
   * - 关键词搜索（站点搜索页）→ `{keyword}`（可带 `sites` 限定站点）。
   *
   * 返回的 task 由调用方决定放哪（老实现：站点搜索放 `S.siteTask`、番号搜索 unshift 进 `S.tasks`）。
   */
  function searchKeyword(
    keyword: string,
    sites?: string[] | null,
    extra: { actor?: string; thumb?: string } = {},
  ): Promise<ActionResult<SearchTask>> {
    return guarded('search', async () => {
      const target = String(keyword ?? '').trim()
      if (!target) return { ok: false, kind: 'error' as ActionResultKind, message: '先输入番号或关键词' }
      const body: Record<string, unknown> = { keyword: target }
      if (sites && sites.length) body.sites = sites.slice()
      if (extra.actor) body.actor = extra.actor
      if (extra.thumb) body.thumb = extra.thumb
      const outcome = await send('post', 'tasks/search', body)
      if (!outcome.ok) return { ok: false, kind: 'error' as ActionResultKind, message: outcome.message }
      const task = (outcome.res.task ?? (outcome.res as SearchTask)) as SearchTask
      const cands = listOf<Candidate>(task.cands) || []
      return {
        ok: true,
        kind: 'ok' as ActionResultKind,
        message: textOf(outcome.res) || `搜到 ${cands.length} 个候选`,
        data: task,
      }
    })
  }

  /**
   * `POST plugin/tasks/acquire`：详情页「下载该影片」——**按规则当场决定**。
   *
   * 与 `searchKeyword` 的分工（别合并）：那个是「检索」（站点搜索页用，只搜不下种），
   * 这个走全局规则的 `trigger` —— 自动下载就当场下单，仅通知（或没找到）就落一条待确认。
   * 提示文案由后端 `toasts` 给，调用方用 `playToasts()` 依次弹。
   */
  function acquireMovie(
    number: string,
    extra: { actor?: string; thumb?: string } = {},
  ): Promise<ActionResult<AcquireResult>> {
    return guarded('acquire', async () => {
      const target = String(number ?? '').trim()
      if (!target) return { ok: false, kind: 'error' as ActionResultKind, message: '缺少番号' }
      const body: Record<string, unknown> = { number: target }
      if (extra.actor) body.actor = extra.actor
      if (extra.thumb) body.thumb = extra.thumb
      const outcome = await send('post', 'tasks/acquire', body)
      if (!outcome.ok) return { ok: false, kind: 'error' as ActionResultKind, message: outcome.message }
      if (outcome.res.success !== true) {
        return { ok: false, kind: 'error' as ActionResultKind, message: textOf(outcome.res) || '请稍后重试' }
      }
      const payload = (outcome.res.data ?? outcome.res) as AcquireResult
      const nextQueue = listOf<QueueItem>(outcome.res.queue)
      if (nextQueue) queue.value = nextQueue
      const task = payload.task
      if (task && typeof task === 'object' && task.id) {
        // 后端回的就是这条任务的最新状态（自动下单后是 pushed）：就地替换/插到最前，
        // 待确认列表与左栏角标立刻对齐，不必再打一次 `/tasks`。
        tasks.value = [
          task,
          ...tasks.value.filter(item => String(item.id ?? '') !== String(task.id)),
        ]
      }
      return {
        ok: true,
        kind: 'ok' as ActionResultKind,
        message: textOf(outcome.res) || '',
        data: payload,
      }
    })
  }

  /**
   * `POST plugin/tasks/download`：提交下载（按任务 id + 站点）。
   *
   * :param force: `true` = 「仍要下载」（允许下载被规则淘汰的候选）。
   */
  function startDownload(
    taskId: string | number,
    site: string,
    force = false,
  ): Promise<ActionResult<TaskDownloadResult>> {
    return guarded('download', async () => {
      const id = String(taskId ?? '').trim()
      if (!id) return { ok: false, kind: 'error' as ActionResultKind, message: '缺少任务 id' }
      const body: Record<string, unknown> = { id, site: site || '' }
      if (force) body.force = true
      const outcome = await send('post', 'tasks/download', body)
      if (!outcome.ok) return { ok: false, kind: 'error' as ActionResultKind, message: outcome.message }
      if (outcome.res.success !== true) {
        return { ok: false, kind: 'error' as ActionResultKind, message: textOf(outcome.res) || '请稍后重试' }
      }
      const payload = (outcome.res.data ?? outcome.res) as TaskDownloadResult
      const nextQueue = listOf<QueueItem>(outcome.res.queue)
      if (nextQueue) queue.value = nextQueue
      // 后端在顶层给 `notice`；老实现还有 `{...id}` 兜底（宿主回传任务体）→ 认出来就插通知。
      const notice = (outcome.res.notice ?? (outcome.res.id ? outcome.res : null)) as NoticeItem | null
      if (notice && (notice.body || notice.title)) prependNotices([notice])
      // 该任务已进入下载：状态变了，顺带把待确认角标对齐。
      tasks.value = tasks.value.map(item =>
        String(item.id ?? '') === id ? { ...item, state: 'pushed' } : item,
      )
      return {
        ok: true,
        kind: 'ok' as ActionResultKind,
        message: textOf(outcome.res) || '已提交下载',
        data: payload,
      }
    })
  }

  /** `POST plugin/magnet-download`：详情页磁力直接推给下载器。 */
  function downloadMagnet(
    hash: string,
    name = '',
    number = '',
  ): Promise<ActionResult<MagnetDownloadResult>> {
    return guarded('magnet', async () => {
      const digest = String(hash ?? '').trim()
      if (!digest) return { ok: false, kind: 'error' as ActionResultKind, message: '缺少磁力 Hash' }
      const body: Record<string, unknown> = { hash: digest, name: name || '' }
      if (number) body.number = number
      const outcome = await send('post', 'magnet-download', body)
      if (!outcome.ok) return { ok: false, kind: 'error' as ActionResultKind, message: outcome.message }
      if (outcome.res.success !== true) {
        return { ok: false, kind: 'error' as ActionResultKind, message: textOf(outcome.res) || '请检查下载器配置' }
      }
      const nextQueue = listOf<QueueItem>(outcome.res.queue)
      if (nextQueue) queue.value = nextQueue
      if (number) known.value = new Set([...known.value, String(number)])
      return {
        ok: true,
        kind: 'ok' as ActionResultKind,
        message: textOf(outcome.res) || '已提交下载',
        data: (outcome.res.data ?? outcome.res) as MagnetDownloadResult,
      }
    })
  }

  /** `POST plugin/tasks/cancel`：取消一条待确认任务（任务卡上的「取消任务」）。
   *
   *  后端只允许取消 `state=await` 的：置成 `canceled` 后任务页与角标都不再算它；
   *  已推进下载器的种子要在下载器里停，后端会直接回失败文案。
   */
  function cancelTask(taskId: string | number): Promise<ActionResult<{ tasks?: SearchTask[] }>> {
    return guarded('cancel', async () => {
      const id = String(taskId ?? '').trim()
      if (!id) return { ok: false, kind: 'error' as ActionResultKind, message: '这条任务缺少 id，无法取消' }
      const outcome = await send('post', 'tasks/cancel', { id })
      if (!outcome.ok) return { ok: false, kind: 'error' as ActionResultKind, message: outcome.message }
      if (outcome.res.success !== true) {
        return { ok: false, kind: 'error' as ActionResultKind, message: textOf(outcome.res) || '请稍后重试' }
      }
      const nextTasks = listOf<SearchTask>(outcome.res.tasks)
      if (nextTasks) tasks.value = nextTasks
      const nextQueue = listOf<QueueItem>(outcome.res.queue)
      if (nextQueue) queue.value = nextQueue
      return {
        ok: true,
        kind: 'ok' as ActionResultKind,
        message: textOf(outcome.res) || '已取消任务',
        data: outcome.res as { tasks?: SearchTask[] },
      }
    })
  }

  /** `DELETE plugin/notices`：清空通知（不可恢复，界面自己先确认）。 */
  function clearNotices(): Promise<ActionResult> {
    return guarded('clearNotices', async () => {
      const outcome = await send('delete', 'notices')
      if (!outcome.ok) return { ok: false, kind: 'error' as ActionResultKind, message: outcome.message }
      if (outcome.res.success !== true) {
        return { ok: false, kind: 'error' as ActionResultKind, message: textOf(outcome.res) || '请稍后重试' }
      }
      // 后端删完回传 `notices: []`：以它为准，回不去就本地清空（老实现是本地清空）。
      const nextNotices = listOf<NoticeItem>(outcome.res.notices)
      notices.value = nextNotices ?? []
      return { ok: true, kind: 'ok' as ActionResultKind, message: textOf(outcome.res) || '通知已清空' }
    })
  }

  /** `POST plugin/rule`：保存全局默认规则（后端以已存规则为基准合并）。 */
  function saveRule(next: RuleValue): Promise<ActionResult<RuleValue>> {
    return guarded('saveRule', async () => {
      if (!next || typeof next !== 'object') {
        return { ok: false, kind: 'error' as ActionResultKind, message: '规则内容为空' }
      }
      const outcome = await send('post', 'rule', { rule: next })
      if (!outcome.ok) return { ok: false, kind: 'error' as ActionResultKind, message: outcome.message }
      if (outcome.res.success !== true) {
        return { ok: false, kind: 'error' as ActionResultKind, message: textOf(outcome.res) || '请稍后重试' }
      }
      const saved = (outcome.res.rule ?? next) as RuleValue
      ruleRaw.value = saved
      rule.value = toRule(saved)
      return {
        ok: true,
        kind: 'ok' as ActionResultKind,
        message: textOf(outcome.res) || '默认规则已保存',
        data: rule.value,
      }
    })
  }

  /**
   * `GET plugin/tasks`：只刷新任务与下载队列（老实现 5 秒轮询用的端点，
   * 比整份 bootstrap 轻，不动 favs/subs/notices）。
   *
   * :param silent: `true` 时失败不写 `error`（后台轮询不该把界面打成错误态）。
   */
  async function refreshTasks(silent = true): Promise<boolean> {
    const outcome = await send('get', 'tasks')
    if (!outcome.ok) {
      if (!silent) error.value = outcome.message
      return false
    }
    syncLists(outcome.res as Record<string, any>)
    return true
  }

  return {
    // 状态
    enabled,
    sites,
    favs,
    aliases,
    subs,
    known,
    notices,
    tasks,
    queue,
    rule,
    ruleRaw,
    loading,
    error,
    updatedAt,
    booted,
    busy,
    // 派生
    awaitTasks,
    downloading,
    // 动作
    refresh,
    /** 用壳已经拉到的 `/bootstrap` 载荷灌状态（不发请求，S6 站点搜索视图靠它拿 `rule.sites`）。 */
    hydrate,
    refreshTasks,
    ensureSites,
    runCheck,
    unsubscribe,
    addFav,
    delFav,
    setAlias,
    subscribeNumber,
    searchKeyword,
    acquireMovie,
    startDownload,
    cancelTask,
    downloadMagnet,
    clearNotices,
    saveRule,
  }
}

/** 数据台 store 的类型别名：视图组件用它标注 `store` prop。 */
export type PluginStore = ReturnType<typeof usePluginStore>
