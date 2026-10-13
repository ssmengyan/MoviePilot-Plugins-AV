/**
 * 设置台的纯函数工具：后端字段归一、显示格式化、草稿等值比较。
 *
 * 单独成文件是为了不给 `useRuntimeInfo` 制造「运行时概况也要 import 设置台草稿」的耦合：
 * 右栏和设置台都要读同一批 `/bootstrap` 字段（`cacheSize*` / `check`），
 * 归一逻辑只能有一份，否则两边会各自解释字段。
 */
import { POLICY_MAX_PER_DAY, POLICY_MIN_INTERVAL_MIN } from './settingsPolicy'

/** 后端 `POST/GET /rule` 的规则对象（字段名照抄后端，不许改名）。 */
export interface RuleState {
  /** 分辨率策略：`1080p` | `2160p`（4K 优先）| `only4k`（仅 4K）。 */
  res: string
  mustCnsub: boolean
  preferUncensored: boolean
  allow4k: boolean
  minSeeders: number
  /** 搜索范围站点；空数组 = 全部已配置站点。 */
  sites: string[]
  /** 优先站点：先搜这些站，命中即停（顺序有意义）。 */
  prefSites: string[]
  btFallback: boolean
  trigger: 'notify' | 'auto'
  maxPerDay: number
  minIntervalMin: number
  savePath: string
  category: string
  downloader: string
}

/** 站点条目（`/bootstrap` 的 `sites`，来自后端 `SiteSearcher.describe()`）。 */
export interface SiteOption {
  id?: string | number | null
  name: string
  adapter?: string
  adapterLabel?: string
}

/** 通知条目（`GET /notices`）。 */
export interface NoticeItem {
  kind?: string
  title?: string
  type?: string
  body?: string
  meta?: string
  image?: string
  time?: string
}

/** 保存语义第 2 步要交给宿主的那份配置。 */
export interface HostConfigDraft {
  enabled: boolean
  proxy: string
  /** javdb 二进制路径；留空 = 自动下载 / 自动查找（见插件 `paths.py`）。 */
  javdb_bin: string
  /** 数据根（SQLite / JSON 缓存 / 图片缓存同根）；留空 = MoviePilot 插件数据目录
   *  `<PLUGIN_DATA_PATH>/AVHelper`（默认 `/config/plugins/AVHelper`）。 */
  data_root: string
  emby_host: string
  emby_apikey: string
  /**
   * 缓存上限（GB，0.6.3 加）。**草稿里存字符串**：它是输入框的直接形态
   * （用户会把整格删空、会打到「1.」这种中间态），转成数字再回填会让光标乱跳；
   * 归一与夹取由 `toCacheGbText()` 负责，后端 `paths.cache_limit_gb()` 还会再夹一道。
   */
  cache_max_gb: string
}

/** `/bootstrap` 里用得到的字段（`cacheSize*` 与 `check` 是后端正在补的，取不到就 `—`）。 */
export interface BootstrapLike {
  enabled?: boolean
  sites?: unknown
  defaultRule?: unknown
  notices?: unknown
  cacheSize?: unknown
  cacheSizeText?: unknown
  check?: unknown
}

/**
 * 限流只读展示用的 `check` 字段。
 *
 * **后端给的是 epoch 秒**（S5 补充裁决，与后端 S1b 对齐），
 * `toCheckInfo()` 负责把它换算成 **epoch 毫秒**再放进这里 —— 因为界面统一用
 * `Date` 格式化（毫秒），不换算就会把 2026 年显示成 1970 年。
 * `0` 是有语义的哨兵值：`nextAt: 0` = 现在就允许检查、`lastCheck: 0` = 从未检查。
 */
export interface CheckInfo {
  allowed?: boolean
  reason?: string
  /** 下次可检查的时间点（**epoch 毫秒**，由后端秒值 ×1000）；`0` = 现在可检查。 */
  nextAt?: number
  checkedToday?: number
  /** 上次检查时间（**epoch 毫秒**，由后端秒值 ×1000）；`0` = 从未检查。 */
  lastCheck?: number
  maxPerDay?: number
  minIntervalMin?: number
}

/** 后端 `DEFAULT_RULE` 的镜像：`/rule` 拿不到时的兜底，不编造额外字段。 */
export const RULE_FALLBACK: RuleState = {
  res: '1080p',
  mustCnsub: false,
  preferUncensored: true,
  allow4k: true,
  minSeeders: 3,
  sites: [],
  prefSites: ['馒头', 'Rousi'],
  btFallback: true,
  trigger: 'notify',
  maxPerDay: 6,
  minIntervalMin: POLICY_MIN_INTERVAL_MIN,
  savePath: '',
  category: 'avi',
  downloader: '',
}

export function str(value: unknown, fallback = ''): string {
  return typeof value === 'string' ? value : value === null || value === undefined ? fallback : String(value)
}

/**
 * 缓存上限（GB）的取值口径**必须与后端 `paths.cache_limit_gb()` 一模一样**，
 * 否则界面显示 1G、后端实际按别的数淘汰（0.6.3 加）：
 * 默认 1G；空/非数字/≤0 一律回落 1G（**不是「不限制」**：后端拿它当字节上限，
 * 归零会把缓存目录清空）；上下夹到 [0.1, 4096]。
 */
export const CACHE_MAX_GB_FALLBACK = 1
export const CACHE_MAX_GB_MIN = 0.1
export const CACHE_MAX_GB_MAX = 4096

/** 归一成输入框里的文本（`1` / `2.5`；非法值给出兜底 1）。 */
export function toCacheGbText(value: unknown): string {
  if (typeof value === 'string' && !value.trim()) return String(CACHE_MAX_GB_FALLBACK)
  const parsed = typeof value === 'number' ? value : Number.parseFloat(str(value))
  if (!Number.isFinite(parsed) || parsed <= 0) return String(CACHE_MAX_GB_FALLBACK)
  const clamped = Math.min(Math.max(parsed, CACHE_MAX_GB_MIN), CACHE_MAX_GB_MAX)
  // 去掉浮点尾巴（0.30000000000000004 这种），最多留三位小数
  return String(Number(clamped.toFixed(3)))
}

/** 归一后的数值形态（界面算「已用 / 上限」占比时用）。 */
export function toCacheGb(value: unknown): number {
  return Number.parseFloat(toCacheGbText(value))
}

function strList(value: unknown): string[] {
  return Array.isArray(value) ? value.map(item => str(item)).filter(Boolean) : []
}

function bool(value: unknown, fallback: boolean): boolean {
  return typeof value === 'boolean' ? value : fallback
}

/**
 * 数字归一：非数字回落兜底；`floor` 为真时取整（整数型字段）。
 * `min` 用来挡住负数（如「做种数下限」不该是负的）。
 */
function num(value: unknown, fallback: number, floor = false, min: number | null = null): number {
  let parsed = typeof value === 'number' ? value : Number.parseFloat(str(value))
  if (!Number.isFinite(parsed)) return fallback
  if (floor) parsed = Math.floor(parsed)
  if (min !== null && parsed < min) return min
  return parsed
}

/** 把任意形状的规则对象补全成 `RuleState`。 */
export function toRuleState(raw: unknown): RuleState {
  const src = (raw && typeof raw === 'object' ? raw : {}) as Record<string, unknown>
  const res = str(src.res, RULE_FALLBACK.res)
  return {
    res: res === '2160p' || res === 'only4k' || res === '1080p' ? res : RULE_FALLBACK.res,
    mustCnsub: bool(src.mustCnsub, RULE_FALLBACK.mustCnsub),
    preferUncensored: bool(src.preferUncensored, RULE_FALLBACK.preferUncensored),
    allow4k: bool(src.allow4k, RULE_FALLBACK.allow4k),
    minSeeders: num(src.minSeeders, RULE_FALLBACK.minSeeders, true, 0),
    sites: strList(src.sites),
    prefSites: strList(src.prefSites),
    btFallback: bool(src.btFallback, RULE_FALLBACK.btFallback),
    trigger: str(src.trigger) === 'auto' ? 'auto' : 'notify',
    // 限流参数不由界面放宽：每日上限封顶政策值 6（后端 `merge_rule()` 还会再夹一道），
    // 间隔拿不到就把政策固定值原样带回去。
    maxPerDay: Math.min(num(src.maxPerDay, RULE_FALLBACK.maxPerDay, true, 1), POLICY_MAX_PER_DAY),
    minIntervalMin: Math.max(num(src.minIntervalMin, RULE_FALLBACK.minIntervalMin, true, 1),
                             POLICY_MIN_INTERVAL_MIN),
    savePath: str(src.savePath, RULE_FALLBACK.savePath),
    category: str(src.category, RULE_FALLBACK.category),
    downloader: str(src.downloader, RULE_FALLBACK.downloader),
  }
}

/**
 * 归一 `check` 字段；后端还没上线该字段时返回 `null`（界面显示 `—`）。
 * 只要任何一项有值就当拿到了，缺的项由调用方单独显示 `—`。
 */
export function toCheckInfo(raw: unknown): CheckInfo | null {
  if (!raw || typeof raw !== 'object') return null
  const src = raw as Record<string, unknown>
  const info: CheckInfo = {
    allowed: typeof src.allowed === 'boolean' ? src.allowed : undefined,
    reason: str(src.reason) || undefined,
    nextAt: epochSecondsToMs(src.nextAt),
    checkedToday: Number.isFinite(Number(src.checkedToday)) ? Number(src.checkedToday) : undefined,
    lastCheck: epochSecondsToMs(src.lastCheck),
    maxPerDay: Number.isFinite(Number(src.maxPerDay)) ? Number(src.maxPerDay) : undefined,
    minIntervalMin: Number.isFinite(Number(src.minIntervalMin)) ? Number(src.minIntervalMin) : undefined,
  }
  const known = Object.values(info).some(value => value !== undefined)
  return known ? info : null
}

/**
 * 后端 epoch **秒** → 界面统一的 epoch **毫秒**。
 *
 * 非数字/负值一律当作「没给」（`undefined`），但 **`0` 是合法哨兵值**
 * （`nextAt: 0` = 现在可检查、`lastCheck: 0` = 从未检查），必须原样保留成 `0`。
 * 已经是毫秒量级的输入（>1e12，防止后端哪天改口径）不再乘 1000。
 */
export function epochSecondsToMs(value: unknown): number | undefined {
  if (value === null || value === undefined || value === '') return undefined
  const parsed = typeof value === 'number' ? value : Number.parseFloat(str(value))
  if (!Number.isFinite(parsed) || parsed < 0) return undefined
  return parsed > 1e12 ? Math.floor(parsed) : Math.floor(parsed * 1000)
}

/** 字节数 → 可读体积（后端 `cacheSizeText` 拿不到时的兜底换算）。 */
export function formatBytes(value: unknown): string {
  const parsed = typeof value === 'number' ? value : Number.parseFloat(str(value))
  if (!Number.isFinite(parsed) || parsed < 0) return ''
  if (parsed < 1024) return `${Math.round(parsed)} B`
  const units = ['KB', 'MB', 'GB', 'TB']
  let size = parsed / 1024
  let index = 0
  while (size >= 1024 && index < units.length - 1) {
    size /= 1024
    index += 1
  }
  return `${size >= 100 ? Math.round(size) : size.toFixed(1)} ${units[index]}`
}

/**
 * 时间 → `MM-DD HH:mm`。
 *
 * 兼容三种输入：数字时间戳（毫秒）、纯数字字符串（`check` 换算后的毫秒值走这条）、
 * 以及 `YYYY-MM-DD HH:mm[:ss]` 文本。拿不到或非法则返回空串，调用方显示 `—`。
 *
 * ⚠️ 纯数字字符串必须自己 `Number()` 再进 `Date`：`new Date("1791611460000")`
 * 在 V8 里是 **Invalid Date**（它按日期文本解析），实测会把 2026 年的一条时间
 * 原样显示成 `1791611460000`。
 */
export function formatMoment(value: unknown): string {
  let date: Date
  if (typeof value === 'number') {
    date = new Date(value)
  } else {
    const text = str(value).trim()
    if (!text) return ''
    date = /^\d+$/.test(text) ? new Date(Number(text)) : new Date(text.includes('T') ? text : text.replace(' ', 'T'))
    if (Number.isNaN(date.getTime())) return text
  }
  if (Number.isNaN(date.getTime())) return ''
  const pad = (n: number) => String(n).padStart(2, '0')
  return `${pad(date.getMonth() + 1)}-${pad(date.getDate())} ${pad(date.getHours())}:${pad(date.getMinutes())}`
}

/**
 * `check` 的时间字段（**epoch 毫秒**，已是 `toCheckInfo` 换算后的值）→ 可读文本，
 * 并把 `0` 的语义翻出来：
 * - `nextAt`：`0` = 现在就允许检查 →「现在可检查」；`undefined` = 字段没给 →「—」。
 * - `lastCheck`：`0` = 从未检查 →「从未检查」；`undefined` = 字段没给 →「—」。
 */
export function formatCheckTime(value: number | undefined, kind: 'next' | 'last'): string {
  if (value === undefined) return '—'
  if (value <= 0) return kind === 'next' ? '现在可检查' : '从未检查'
  return formatMoment(value) || '—'
}

/** 等值比较：草稿与原始快照的字段一一对上才算干净。 */
function sameValue(a: unknown, b: unknown): boolean {
  if (Array.isArray(a) || Array.isArray(b)) {
    const left = Array.isArray(a) ? a.map(item => str(item)) : []
    const right = Array.isArray(b) ? b.map(item => str(item)) : []
    return left.length === right.length && left.every((item, index) => item === right[index])
  }
  return a === b
}

/** 规则是否与快照一致（字段集合取自 `RULE_FALLBACK`，新增字段会自动被覆盖到）。 */
export function sameRule(a: RuleState | null, b: RuleState | null): boolean {
  if (!a || !b) return a === b
  return (Object.keys(RULE_FALLBACK) as (keyof RuleState)[]).every(key => sameValue(a[key], b[key]))
}

/** 宿主配置是否与快照一致。 */
export function sameHost(a: HostConfigDraft | null, b: HostConfigDraft | null): boolean {
  if (!a || !b) return a === b
  return (
    a.enabled === b.enabled &&
    a.proxy === b.proxy &&
    a.javdb_bin === b.javdb_bin &&
    a.data_root === b.data_root &&
    a.emby_host === b.emby_host &&
    a.emby_apikey === b.emby_apikey &&
    a.cache_max_gb === b.cache_max_gb
  )
}

/**
 * 两栏「Emby 地址 / API 密钥」只填一半不是错误配置，但会让人以为生效了，
 * 保存前给一句提示；空串表示没问题。
 */
export function embyHalfFilled(config: HostConfigDraft | null | undefined): string {
  const host = str(config?.emby_host).trim()
  const key = str(config?.emby_apikey).trim()
  if ((host && !key) || (!host && key)) {
    return 'Emby 地址与 API 密钥要一起填；两栏都留空 = 复用 MoviePilot「设置 → 媒体服务器」。'
  }
  return ''
}
