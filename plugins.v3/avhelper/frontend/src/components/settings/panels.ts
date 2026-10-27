/**
 * 设置台栏目清单（设计文档 §4）。
 *
 * 单独一个 `.ts` 而不写在 `Console.vue` 里：`useSettingsDraft` 也要用它判断
 * 「该栏目是否持有草稿字段」（`dirtyMarker`），两处必须同一份来源。
 */
export interface SectionItem {
  key: string
  title: string
  icon: string
}

/**
 * 设置台十栏。
 *
 * - 「常规」是本轮（0.3.x）新增：切 `vue` 模式后宿主不再画 JSON 配置表单；
 * - 「刮削」「刮削规则」是 v4 刮削线（0.7.0）新增，排在「下载规则」之后
 *   —— 界面顺序 = 「下载」→「刮削」→「刮削规则」，与数据台「下载」栏在前的口径一致；
 * - 「演员」是 0.9.0 演员线（S5）新增，紧跟「刮削规则」。
 */
export const SETTINGS_SECTIONS: SectionItem[] = [
  { key: 'general', title: '常规', icon: 'mdi-cog-outline' },
  { key: 'sites', title: '搜索站点', icon: 'mdi-web' },
  { key: 'rule', title: '下载规则', icon: 'mdi-filter-cog' },
  { key: 'scrape', title: '刮削', icon: 'mdi-auto-fix' },
  { key: 'scrapeRule', title: '刮削规则', icon: 'mdi-file-document-edit-outline' },
  // 「演员」（0.9.0 演员线 S5 加）：头像源开关 / gFriends 索引 / 自动同步 / 一键补齐。
  // 紧跟「刮削规则」——演员线是刮削线的一部分，排序上跟着走。
  { key: 'actor', title: '演员', icon: 'mdi-account-star' },
  { key: 'notify', title: '通知', icon: 'mdi-bell' },
  { key: 'library', title: '媒体库', icon: 'mdi-server' },
  { key: 'runtime', title: '运行与缓存', icon: 'mdi-database-cog' },
  { key: 'about', title: '关于', icon: 'mdi-information-outline' },
]

/**
 * 设置台各栏目「算不算脏」看的是自己那部分草稿，避免在某栏改了东西、
 * 切到别的栏看不到未保存标记。通知/关于两栏没有草稿字段。
 * （「运行与缓存」0.6.3 起有宿主配置字段 `cache_max_gb`，所以归 host 组。）
 *
 * ⚠️ 「刮削」「刮削规则」两栏的字段**不在 `RuleState` / `HostConfigDraft` 里**
 * （见 `SCRAPE_DEFAULTS` 的说明），草稿层的 `ruleDirty` / `hostDirty` 认不出它们，
 * 所以这里写 `none`，由壳（`Console.vue` 的 `sectionDirtyEx()`）把
 * `scrapeDirty` 或进来 —— 两处合起来才是这一栏真正的脏标记。
 * 「演员」「通知」两栏同一条待遇（`actorDirty` / `notifyDirty`，见 `ACTOR_SECTIONS` /
 * `NOTIFY_SECTIONS`）。
 */
export const DIRTY_GROUPS: Record<string, 'none' | 'rule' | 'host' | 'both'> = {
  general: 'host',
  sites: 'rule',
  rule: 'rule',
  scrape: 'none',
  scrapeRule: 'none',
  actor: 'none',
  notify: 'none',
  library: 'host',
  runtime: 'host',
  about: 'none',
}

/** 「刮削」「刮削规则」两栏的 key（壳用它决定脏标记与懒加载）。 */
export const SCRAPE_SECTIONS: string[] = ['scrape', 'scrapeRule']

/** 「演员」栏的 key（与 `SCRAPE_SECTIONS` 同一套机制：壳用它决定脏标记与懒加载）。 */
export const ACTOR_SECTIONS: string[] = ['actor']

/** 「通知」栏的 key（0.9.1：推送渠道/分类/时间表都在这一栏，同一套脏标记与懒加载）。 */
export const NOTIFY_SECTIONS: string[] = ['notify']

/** 刮削模式四档（v4.1 §5 / 契约 §3.7 的 `/scrape/run`）。 */
export type ScrapeMode = 'off' | 'fill' | 'hybrid' | 'own'
/** 预告片三档（契约 D9：**默认 off**，写媒体目录会触发 Emby 实时扫描）。 */
export type TrailerMode = 'off' | 'remote' | 'local'

/**
 * 刮削两栏的设置形状（v4 刮削线 S9）。
 *
 * **存哪**：与「下载规则」同一份 kv —— `POST /rule` 的 JSON 里多出来的键
 * （后端 `tasks.merge_rule()` 是 `merged.update(rule)`，未知键原样保留；
 * `api_rule` 把整份 dict 存进 `GLOBAL_RULE_KEY`，GET 时原样回）。
 * 为什么不挂宿主配置：`useSettingsDraft.save()` 提交宿主配置时只装配 7 个老字段、
 * 脏标记也只比那 7 项，新字段既不进 payload 也不触发「● 未保存」（该文件不在本线可改清单内）。
 * 后端（S8）读法：`self.global_rule().get("scrapeMode")` 等，缺键按下面的默认值兜底。
 */
export interface ScrapeSettings {
  /** 刮削模式：`off` 关闭 / `fill` 只补空缺 / `hybrid` 自建层 + 站点兜底 / `own` 只用自建层。 */
  scrapeMode: ScrapeMode
  /** 简介源：Javtxt（中文直出，契约 §4.2）。 */
  plotJavtxt: boolean
  /** 翻译模型（契约 D6：默认 `hy3`，失败降级 `translateModelFallback`）。 */
  translateModel: string
  /** 备用翻译模型（同一网关）。 */
  translateModelFallback: string
  /** 预告片模式：`off` / `remote`（写 RemoteTrailers，**实测写不进去**）/ `local`（旁挂 mp4）。 */
  trailerMode: TrailerMode
  /** 定时重刮 Tier 1（新片 / 缺简介指数退避，v4.1 §5.3）。 */
  autoScrapeTier1: boolean
  /** 定时重刮 Tier 2（全库冷数据滚动，v4.1 §5.3）。 */
  autoScrapeTier2: boolean
  /**
   * 下载完成后立即刮削（S6）：台账入账那一刻把这一部片刮一遍，不等定时重刮。
   * 后端读法 `self.scrape_conf().get("scrapeOnDownload")`，缺键默认 **true**；刮在后台
   * worker 线程里逐条做，与 `scrapeMode == 'off'` 联动（关了刮削模式就不排）。
   */
  scrapeOnDownload: boolean
  /** 后缀清洗词表（番号解析前逐个剥离，`ScrapeRulePanel` 可增删）。 */
  cleanSuffixes: string[]
  /** 命名模板（Emby `Name`，变量 `{number}` / `{badge}` / `{title}`）。 */
  nameTemplate: string
  /**
   * 启用哪些数据源（0.8.0 / P1-5，**取数图的新真值**）。可选值由后端 `/scrape/graph` 下发；
   * `javdb` 是骨架、永远在。`plotJavtxt` 由它派生（老前端仍按布尔读）；0.8.1 起只剩 javdb / javtxt。
   */
  sources: string[]
  /** 字段优先级（稀疏）：`{字段: [站点…]}` —— 把某些源在**这个字段**上提前（P0-1）。 */
  fieldPriority: Record<string, string[]>
  /** 字段黑名单（稀疏）：`{字段: [站点…]}` —— 这个字段**不采用**这些源。 */
  fieldBlacklist: Record<string, string[]>
  /** 每 host 请求间隔（秒；调用方没显式给间隔时用。P1-2）。 */
  defaultRateLimit: string
  /** 逐 host / 站点的间隔覆盖：`{域名: "秒"}`（P1-2）。 */
  rateLimits: Record<string, string>
}

/** 默认值（后端拿不到键时按这一份兜底；面板里的文案与它一一对应）。 */
export const SCRAPE_DEFAULTS: ScrapeSettings = {
  scrapeMode: 'off',
  plotJavtxt: true,
  translateModel: 'hy3',
  translateModelFallback: 'deepseek-v4.1-flash',
  trailerMode: 'off',
  autoScrapeTier1: false,
  autoScrapeTier2: false,
  scrapeOnDownload: true,
  cleanSuffixes: ['-UC', '_4K', '-4K', '-C', '-L', '-VR', '-ISO', 'CD1', 'CD2', '中字', '流出'],
  nameTemplate: '{number}{badge} {title}',
  sources: ['javdb', 'javtxt'],
  fieldPriority: {},
  fieldBlacklist: {},
  defaultRateLimit: '2',
  rateLimits: {},
}

const MODES: ScrapeMode[] = ['off', 'fill', 'hybrid', 'own']
const TRAILERS: TrailerMode[] = ['off', 'remote', 'local']

function pick<T extends string>(value: unknown, allowed: T[], fallback: T): T {
  const text = typeof value === 'string' ? value.trim() : ''
  return (allowed as string[]).includes(text) ? (text as T) : fallback
}

function boolOf(value: unknown, fallback: boolean): boolean {
  if (typeof value === 'boolean') return value
  if (value === 'true' || value === 1 || value === '1') return true
  if (value === 'false' || value === 0 || value === '0') return false
  return fallback
}

/** 整数：认数字与数字字符串，越界夹回区间，认不出就用默认值（演员栏的条数/间隔用它）。 */
function intOf(value: unknown, fallback: number, min: number, max: number): number {
  const num = typeof value === 'number' ? value : Number(String(value ?? '').trim())
  if (!Number.isFinite(num)) return fallback
  return Math.min(max, Math.max(min, Math.round(num)))
}

function textOf(value: unknown, fallback: string): string {
  const text = typeof value === 'string' ? value.trim() : ''
  return text || fallback
}

function listOf(value: unknown, fallback: string[]): string[] {
  if (!Array.isArray(value)) return [...fallback]
  const out = value.map(item => String(item ?? '').trim()).filter(Boolean)
  return out.length ? out : [...fallback]
}

/** 启用源列表：空/非法就回默认；`javdb` 是骨架，永远补上（与后端 `_source_list` 同一口径）。 */
function sourcesOf(value: unknown, fallback: string[]): string[] {
  const out = Array.isArray(value)
    ? value.map(item => String(item ?? '').trim()).filter(Boolean)
    : []
  const merged = new Set([...(out.length ? out : fallback), 'javdb'])
  return [...merged]
}

/** `{字段: [站点…]}`：只留数组值且非空（字段/站点名是否合法由后端写入校验兜底）。 */
function fieldMapOf(value: unknown): Record<string, string[]> {
  if (!value || typeof value !== 'object') return {}
  const out: Record<string, string[]> = {}
  for (const [key, raw] of Object.entries(value as Record<string, unknown>)) {
    if (!Array.isArray(raw)) continue
    const list = raw.map(item => String(item ?? '').trim()).filter(Boolean)
    if (key.trim() && list.length) out[key.trim()] = list
  }
  return out
}

/** `{域名: "秒"}`：值统一成字符串数字（后端 `_rate_value` 会再夹一次范围）。 */
function rateMapOf(value: unknown): Record<string, string> {
  if (!value || typeof value !== 'object') return {}
  const out: Record<string, string> = {}
  for (const [key, raw] of Object.entries(value as Record<string, unknown>)) {
    const name = key.trim()
    const text = String(raw ?? '').trim()
    if (name && text) out[name] = text
  }
  return out
}

/**
 * 任意形状（`GET /rule` 的原始 dict、老后端、缺键）→ `ScrapeSettings`。
 * 认不出的枚举值回落默认档，**不抛错**（老后端没有这些键时界面照样画得出来）。
 */
export function toScrapeSettings(raw: unknown): ScrapeSettings {
  const src = (raw && typeof raw === 'object' ? raw : {}) as Record<string, unknown>
  return {
    scrapeMode: pick(src.scrapeMode, MODES, SCRAPE_DEFAULTS.scrapeMode),
    plotJavtxt: boolOf(src.plotJavtxt, SCRAPE_DEFAULTS.plotJavtxt),
    translateModel: textOf(src.translateModel, SCRAPE_DEFAULTS.translateModel),
    translateModelFallback: textOf(src.translateModelFallback, SCRAPE_DEFAULTS.translateModelFallback),
    trailerMode: pick(src.trailerMode, TRAILERS, SCRAPE_DEFAULTS.trailerMode),
    autoScrapeTier1: boolOf(src.autoScrapeTier1, SCRAPE_DEFAULTS.autoScrapeTier1),
    autoScrapeTier2: boolOf(src.autoScrapeTier2, SCRAPE_DEFAULTS.autoScrapeTier2),
    scrapeOnDownload: boolOf(src.scrapeOnDownload, SCRAPE_DEFAULTS.scrapeOnDownload),
    cleanSuffixes: listOf(src.cleanSuffixes, SCRAPE_DEFAULTS.cleanSuffixes),
    nameTemplate: textOf(src.nameTemplate, SCRAPE_DEFAULTS.nameTemplate),
    // P1-5 / P1-2：启用源、字段级择优、限流参数
    sources: sourcesOf(src.sources, SCRAPE_DEFAULTS.sources),
    fieldPriority: fieldMapOf(src.fieldPriority),
    fieldBlacklist: fieldMapOf(src.fieldBlacklist),
    defaultRateLimit: textOf(src.defaultRateLimit, SCRAPE_DEFAULTS.defaultRateLimit),
    rateLimits: rateMapOf(src.rateLimits),
  }
}

/** 只有这几个键属于刮削两栏（决定「这一栏脏了没有」与提交哪些字段）。 */
export const SCRAPE_KEYS: (keyof ScrapeSettings)[] = [
  'scrapeMode',
  'plotJavtxt',
  'translateModel',
  'translateModelFallback',
  'trailerMode',
  'autoScrapeTier1',
  'autoScrapeTier2',
  'scrapeOnDownload',
  'cleanSuffixes',
  'nameTemplate',
  'sources',
  'fieldPriority',
  'fieldBlacklist',
  'defaultRateLimit',
  'rateLimits',
]

// ---------------------------------------------------------------------------
// 演员（0.9.0 演员线 S5，见 docs/AVHelper-演员刮削子系统方案.md §6）
// ---------------------------------------------------------------------------

/**
 * 「演员」栏的设置形状。
 *
 * **存哪**：与「刮削」两栏**完全同一套** —— `POST /rule` 那份 kv（后端 `merge_rule()` 保留未知键），
 * 键名就是下面这六个（后端 `self.global_rule().get("actorEnabled")` 这样读）。
 * **不要**塞进宿主配置：`useSettingsDraft.save()` 只装配 7 个老字段，新字段既不进 payload
 * 也不触发「● 未保存」（见 `SCRAPE_DEFAULTS` 的同一段说明）。
 *
 * 两组语义（别混）：
 * - 前三个是**取数开关**（子系统本身开不开、gFriends 与 javdb 两个头像源开不开）；
 * - 后三个是**同步节奏**（自动同步开不开、每轮条数、轮间隔秒）。
 *
 * 默认全开（方案 §6：Gfriends 开关与 javdb 兜底开关都默认开）；条数 20 / 间隔 2s 与
 * 方案 §4「定时 tick 每轮最多 20 位，间隔≥2s」同一口径。
 */
export interface ActorSettings {
  /** 演员子系统总开关。关掉 = 不抓、不写头像（已有数据不动）。 */
  actorEnabled: boolean
  /** gFriends 头像源（`raw.githubusercontent.com` 的索引图，整图最高清）。 */
  actorGfriends: boolean
  /** javdb 兜底头像源（javdb 演员页缩略图，比 gFriends 小）。 */
  actorJavdbFallback: boolean
  /** 自动同步：影片刮完后把该片女演员登记进队列，由定时 tick 消费。 */
  actorAutoSync: boolean
  /** 每轮最多同步多少位（默认 20）。 */
  actorBatchSize: number
  /** 每两位之间的间隔秒数（默认 2；后端另有 host 桶限流）。 */
  actorInterval: number
}

/** 默认值（后端拿不到键时按这一份兜底；面板文案与它一一对应）。 */
export const ACTOR_DEFAULTS: ActorSettings = {
  actorEnabled: true,
  actorGfriends: true,
  actorJavdbFallback: true,
  actorAutoSync: true,
  actorBatchSize: 20,
  actorInterval: 2,
}

/**
 * 任意形状（`GET /rule` 的原始 dict、老后端、缺键）→ `ActorSettings`。
 * 认不出的值回落默认，**不抛错**（老后端没有这些键时界面照样画得出来）。
 */
export function toActorSettings(raw: unknown): ActorSettings {
  const src = (raw && typeof raw === 'object' ? raw : {}) as Record<string, unknown>
  return {
    actorEnabled: boolOf(src.actorEnabled, ACTOR_DEFAULTS.actorEnabled),
    actorGfriends: boolOf(src.actorGfriends, ACTOR_DEFAULTS.actorGfriends),
    actorJavdbFallback: boolOf(src.actorJavdbFallback, ACTOR_DEFAULTS.actorJavdbFallback),
    actorAutoSync: boolOf(src.actorAutoSync, ACTOR_DEFAULTS.actorAutoSync),
    actorBatchSize: intOf(src.actorBatchSize, ACTOR_DEFAULTS.actorBatchSize, 1, 200),
    actorInterval: intOf(src.actorInterval, ACTOR_DEFAULTS.actorInterval, 1, 60),
  }
}

/** 只有这几个键属于演员栏（决定「这一栏脏了没有」与提交哪些字段）。 */
export const ACTOR_KEYS: (keyof ActorSettings)[] = [
  'actorEnabled',
  'actorGfriends',
  'actorJavdbFallback',
  'actorAutoSync',
  'actorBatchSize',
  'actorInterval',
]

// ---------------------------------------------------------------------------
// 通知（0.9.1，2026-10-27 用户反馈：通知栏要能选渠道 + 选推什么 + 配时间表）
// ---------------------------------------------------------------------------

/**
 * 「通知」栏的设置形状（4 个键，其余两项是只读展示，不进草稿）。
 *
 * **存哪**：与「下载规则」「刮削」「演员」**完全同一套** —— `POST /rule` 那份 kv
 * （后端 `merge_rule()` 原样保留未知键），键名就是下面这四个（后端 `notify_conf()` 这样读）。
 *
 * 语义（别混）：
 * - `notifyPush`：推送总开关。关掉 = 通知只进插件收件箱，一个渠道都不发；
 * - `notifyChannels`：发到**哪几个渠道**（存渠道中文标签，见后端 `notify.CHANNELS`）。
 *   **空数组 = 不过滤 = 推给 MoviePilot 自己配置过的全部渠道**（老口径，升级不改行为）；
 * - `notifyKinds`：推**哪些通知**（`sub` / `download` / `scrape` / `candidate`）。
 *   空数组 = 老口径（业务通知都推，限流/界面提示永远只进收件箱）；含 `*` = 全推；
 * - `notifyCron`：订阅检查的时间表（标准 5 段 cron）。默认值**固定写死**在这里与后端
 *   `notify.DEFAULT_SUBCHECK_CRON`，两处都是 `30 9,14,21 * * *`（= 老的三档 09:30/14:30/21:30）。
 */
export interface NotifySettings {
  notifyPush: boolean
  notifyChannels: string[]
  notifyKinds: string[]
  notifyCron: string
}

/** 默认值（后端 `notify_conf()` 拿不到键时按同一份兜底；面板文案与它一一对应）。 */
export const NOTIFY_DEFAULTS: NotifySettings = {
  notifyPush: true,
  notifyChannels: [],
  notifyKinds: [],
  notifyCron: '30 9,14,21 * * *',
}

/** 内置渠道表（后端 `notify.CHANNELS` 的镜像；`GET /notify` 拿不到时面板用它先画）。 */
export const NOTIFY_CHANNEL_FALLBACK: Array<{ name: string; label: string }> = [
  { name: 'Telegram', label: 'Telegram' },
  { name: '微信', label: '微信' },
  { name: '飞书', label: '飞书' },
  { name: 'Discord', label: 'Discord' },
  { name: 'Slack', label: 'Slack' },
  { name: '钉钉', label: '钉钉' },
  { name: 'QQ', label: 'QQ' },
  { name: 'SynologyChat', label: 'SynologyChat' },
  { name: 'VoceChat', label: 'VoceChat' },
  { name: 'WebPush', label: 'WebPush' },
  { name: 'Web', label: 'Web' },
  { name: 'WebAgent', label: 'WebAgent' },
  { name: '微信ClawBot', label: '微信ClawBot' },
]

/** 推送分类（后端 `notify.PUSH_KINDS` 的镜像）。 */
export const NOTIFY_KIND_FALLBACK: Array<{ name: string; label: string }> = [
  { name: 'sub', label: '订阅命中（新片 / 番号命中开始搜索）' },
  { name: 'download', label: '开始下载' },
  { name: 'scrape', label: '刮削与入库（正在刮削 / 已入库）' },
  { name: 'candidate', label: '发现候选、等待确认' },
]

function listOfText(value: unknown): string[] {
  if (!Array.isArray(value)) return []
  const out: string[] = []
  for (const item of value) {
    const text = String(item ?? '').trim()
    if (text && !out.includes(text)) out.push(text)
  }
  return out
}

/**
 * 任意形状（`GET /notify` 的 `conf`、`GET /rule` 的原始 dict、老后端、缺键）→ `NotifySettings`。
 * 认不出的值回落默认，**不抛错**。cron 这里只做「5 段」这一层粗判，
 * 真正的合法性由后端 `pick_cron()` 兜底（写坏了会被夹回默认值）。
 */
export function toNotifySettings(raw: unknown): NotifySettings {
  const src = (raw && typeof raw === 'object' ? raw : {}) as Record<string, unknown>
  const cron = typeof src.notifyCron === 'string' ? src.notifyCron.trim().split(/\s+/).join(' ') : ''
  return {
    notifyPush: boolOf(src.notifyPush, NOTIFY_DEFAULTS.notifyPush),
    notifyChannels: listOfText(src.notifyChannels),
    notifyKinds: listOfText(src.notifyKinds),
    notifyCron: cron && cron.split(' ').length === 5 ? cron : NOTIFY_DEFAULTS.notifyCron,
  }
}

/** 只有这几个键属于通知栏（决定「这一栏脏了没有」与提交哪些字段）。 */
export const NOTIFY_KEYS: (keyof NotifySettings)[] = [
  'notifyPush',
  'notifyChannels',
  'notifyKinds',
  'notifyCron',
]
