/**
 * 数据台（数据层 + 通用组件）共用的接口形状。
 *
 * 字段名与取值**照抄后端**（`GET plugin/bootstrap`、`plugin/tasks`、`store.py` 与
 * `scoring.py` 的实际返回），不许改名、不许"顺手补全"：老实现 `ui/views/*.js`
 * 直接按这些名字取字段，改一个名字就是一次静默的功能缺失。
 *
 * 单独成文件的原因：`usePluginStore.ts` 与 `components/common/*.vue` 都要这些类型，
 * 放在 store 里会让组件为一个类型去 import 整个 store。
 */

/** 宿主注入的插件请求器（`PluginDataDialog` 的 `api` prop）。 */
export interface PluginApi {
  /** GET：返回信封或裸数据，形状由插件自己决定（宿主原样透传）。 */
  get<T = any>(url: string, config?: unknown): Promise<T>
  post<T = any>(url: string, data?: unknown, config?: unknown): Promise<T>
  /** DELETE / PUT 是可选能力，拿不到时动作返回错误而不是崩掉。 */
  delete?<T = any>(url: string, config?: unknown): Promise<T>
  put?<T = any>(url: string, data?: unknown, config?: unknown): Promise<T>
}

/** `ready` = 这次动作走完了业务分支；`busy` = 同一动作重复触发被合并掉。 */
export type ActionResultKind = 'ok' | 'limited' | 'busy' | 'error'

/** 动作统一返回（界面据此决定 toast 文案与是否重绘）。 */
export interface ActionResult<T = unknown> {
  ok: boolean
  kind: ActionResultKind
  /** 可直接显示的中文文案（成功时也可能有，如后端返回的提示）。 */
  message: string
  data?: T
  /** `POST plugin/check` 专用的限流标记：`true` = 本次检查被限流跳过。 */
  limited?: boolean
}

/** 搜索范围站点（`GET /sites` → `SiteSearcher.describe()`）。 */
export interface SiteOption {
  id?: string | number | null
  name: string
  adapter?: string
  adapterLabel?: string
}

/** 收藏演员（`store.fav_list()`）。 */
export interface FavActor {
  name: string
  zh?: string
  avatar?: string
}

/** 订阅（`store.sub_list()`）：`rule` 是这条订阅自己的规则副本。 */
export interface Subscription {
  id?: number | string
  type?: string
  name?: string
  rule?: RuleValue
  hits?: number
  /** 上次检查时间（`YYYY-MM-DD HH:MM:SS`）。 */
  last?: string
  created?: string
}

/** 通知（`store.notice_list()`）。 */
export interface NoticeItem {
  kind?: string
  title?: string
  type?: string
  body?: string
  meta?: string
  image?: string
  time?: string
}

/** 后端规则的宽松形态：字段可能缺省，展示/摘要一律按缺省兜底。 */
export interface RuleValue {
  res?: string
  mustCnsub?: boolean
  preferUncensored?: boolean
  allow4k?: boolean
  minSeeders?: number
  sites?: string[]
  prefSites?: string[]
  btFallback?: boolean
  trigger?: string
  maxPerDay?: number
  minIntervalMin?: number
  savePath?: string
  category?: string
  downloader?: string
}

/** 候选种（`scoring.candidate_from_torrent` / `candidate_from_magnet`）。 */
export interface Candidate {
  /** `PT` = 站点候选，`BT` = javdb 磁力兜底。 */
  src?: string
  site?: string
  spec?: string
  cnsub?: boolean
  uncensored?: boolean
  size?: string
  seeders?: number | null
  free?: boolean
  pref?: boolean
  title?: string
  score?: number | string | null
  pass?: boolean
  breakdown?: string
  picked?: boolean
  res?: string
  group?: string
}

/** 搜种任务（`TaskEngine.build_task` / `store.task_list`）。 */
export interface SearchTask {
  id?: string
  number?: string
  actor?: string
  cands?: Candidate[]
  /** `await` = 待确认；提交下载后后端改成 `pushed`。 */
  state?: string
  reason?: string
  thumb?: string
  /** 订阅自动下载命中的任务。 */
  auto?: boolean
  rule?: RuleValue
  /** `manual` = 手动搜索，`sub` = 订阅检查。 */
  source?: string
}

/** 下载队列项（`store.kv_get(QUEUE_KEY)` + 下载器进度回填）。 */
export interface QueueItem {
  id?: string
  number?: string
  thumb?: string
  site?: string
  spec?: string
  size?: string
  hash?: string
  downloader?: string
  category?: string
  savePath?: string
  /** `down` = 下载中，`done` = 已完成（`progress >= 100` 或下载器说在 做种/upload）。 */
  state?: string
  /** 百分比整数（0–100）。 */
  progress?: number
  added?: string
}

/** `GET plugin/bootstrap` 的返回（已实测可用，S6 的单一数据源）。 */
export interface BootstrapPayload {
  enabled?: boolean
  sites?: SiteOption[]
  favs?: FavActor[]
  subs?: Subscription[]
  /** 已知番号（订阅快照/已下载）。 */
  known?: string[]
  notices?: NoticeItem[]
  tasks?: SearchTask[]
  queue?: QueueItem[]
  /** 后端字段名就是 `defaultRule`（不是 `rule`）。 */
  defaultRule?: RuleValue
  cacheSize?: number
  cacheSizeText?: string
  check?: unknown
}

/** 后端 `store.DEFAULT_RULE` 的镜像：`bootstrap.defaultRule` 拿不到字段时的兜底。 */
export const RULE_FALLBACK: RuleValue = {
  res: '1080p',
  mustCnsub: false,
  preferUncensored: true,
  allow4k: true,
  minSeeders: 3,
  sites: [],
  prefSites: ['馒头', 'Rousi'],
  btFallback: true,
  savePath: '/media/9kg/avi',
  category: 'avi',
  downloader: 'qb',
  trigger: 'notify',
  maxPerDay: 6,
  minIntervalMin: 240,
}

/**
 * 站点清单兜底：老实现 `core/state.js` 的 `S.sites` 初值（12 个站点，id 全空）。
 * `bootstrap` 与 `/sites` 都拿不到站点时用它，免得站点选择区一片空白。
 */
export const SITES_FALLBACK: SiteOption[] = [
  { id: '', name: '馒头' },
  { id: '', name: '观众' },
  { id: '', name: '我堡' },
  { id: '', name: '高清杜比' },
  { id: '', name: 'GGPT' },
  { id: '', name: '麒麟' },
  { id: '', name: '象站' },
  { id: '', name: '织梦' },
  { id: '', name: '皇后' },
  { id: '', name: 'PTS' },
  { id: '', name: 'UBits' },
  { id: '', name: 'Rousi' },
]

/** 规则归一：只补缺省键，不改已有值（`minIntervalMin` 也不许被界面放宽）。 */
export function toRule(raw: unknown): RuleValue {
  const src = (raw && typeof raw === 'object' ? raw : {}) as Record<string, unknown>
  const merged: RuleValue = { ...RULE_FALLBACK }
  ;(Object.keys(RULE_FALLBACK) as (keyof RuleValue)[]).forEach(key => {
    const value = src[key]
    if (value === undefined || value === null) return
    // 数组要复制一份，避免 resolve 出来的规则与 bootstrap 返回体共享同一个数组。
    ;(merged as Record<string, unknown>)[key] = Array.isArray(value) ? value.slice() : value
  })
  return merged
}

/** 老实现 `esc()` 的等价替换（Vue 插值自带转义，只在需要拼 HTML 时用）。 */
export function escapeHtml(value: unknown): string {
  return String(value === null || value === undefined ? '' : value).replace(
    /[&<>"]/g,
    char => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' })[char] as string,
  )
}

/** 老实现 `core/util.js` 的 `shortTime()`：ISO 时间戳显示成 `YYYY-MM-DD HH:MM`。 */
export function shortTime(value: unknown): string {
  const text = String(value === null || value === undefined ? '' : value)
  if (!text) return '—'
  if (/^\d{4}-\d{2}-\d{2}T/.test(text)) return text.replace('T', ' ').slice(0, 16)
  return text
}

/** 老实现 `core/util.js` 的 `nowStr()`：`HH:MM:SS`（本地时间，24 小时制）。 */
export function nowStr(): string {
  return new Date().toLocaleTimeString('zh-CN', { hour12: false })
}
