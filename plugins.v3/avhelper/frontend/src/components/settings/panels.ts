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
 * 设置台九栏。
 *
 * - 「常规」是本轮（0.3.x）新增：切 `vue` 模式后宿主不再画 JSON 配置表单；
 * - 「刮削」「刮削规则」是 v4 刮削线（0.7.0）新增，排在「下载规则」之后
 *   —— 界面顺序 = 「下载」→「刮削」→「刮削规则」，与数据台「下载」栏在前的口径一致。
 */
export const SETTINGS_SECTIONS: SectionItem[] = [
  { key: 'general', title: '常规', icon: 'mdi-cog-outline' },
  { key: 'sites', title: '搜索站点', icon: 'mdi-web' },
  { key: 'rule', title: '下载规则', icon: 'mdi-filter-cog' },
  { key: 'scrape', title: '刮削', icon: 'mdi-auto-fix' },
  { key: 'scrapeRule', title: '刮削规则', icon: 'mdi-file-document-edit-outline' },
  { key: 'notify', title: '通知', icon: 'mdi-bell' },
  { key: 'library', title: '媒体库', icon: 'mdi-server' },
  { key: 'runtime', title: '运行与缓存', icon: 'mdi-database-cog' },
  { key: 'about', title: '关于', icon: 'mdi-information-outline' },
]

/**
 * 各栏目「算不算脏」看的是自己那部分草稿，避免在某栏改了东西、
 * 切到别的栏看不到未保存标记。通知/关于两栏没有草稿字段。
 * （「运行与缓存」0.6.3 起有宿主配置字段 `cache_max_gb`，所以归 host 组。）
 *
 * ⚠️ 「刮削」「刮削规则」两栏的字段**不在 `RuleState` / `HostConfigDraft` 里**
 * （见 `SCRAPE_DEFAULTS` 的说明），草稿层的 `ruleDirty` / `hostDirty` 认不出它们，
 * 所以这里写 `none`，由壳（`Console.vue` 的 `sectionDirtyEx()`）把
 * `scrapeDirty` 或进来 —— 两处合起来才是这一栏真正的脏标记。
 */
export const DIRTY_GROUPS: Record<string, 'none' | 'rule' | 'host' | 'both'> = {
  general: 'host',
  sites: 'rule',
  rule: 'rule',
  scrape: 'none',
  scrapeRule: 'none',
  notify: 'none',
  library: 'host',
  runtime: 'host',
  about: 'none',
}

/** 「刮削」「刮削规则」两栏的 key（壳用它决定脏标记与懒加载）。 */
export const SCRAPE_SECTIONS: string[] = ['scrape', 'scrapeRule']

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
  /** 刮削模式：`off` 关闭 / `fill` 只补空缺 / `hybrid` 自建层 + MetaTube 兜底 / `own` 只用自建层。 */
  scrapeMode: ScrapeMode
  /** 简介源：Javtxt（中文直出，契约 §4.2）。 */
  plotJavtxt: boolean
  /** 简介源：MetaTube（日文 + LLM 翻译）。 */
  plotMetatube: boolean
  /** MetaTube 服务地址（0.7.0 加：只在开了上面的开关时才有意义；**代码里不写死**，留空 = 不做兜底）。 */
  metatubeBase: string
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
  /** 后缀清洗词表（番号解析前逐个剥离，`ScrapeRulePanel` 可增删）。 */
  cleanSuffixes: string[]
  /** 命名模板（Emby `Name`，变量 `{number}` / `{badge}` / `{title}`）。 */
  nameTemplate: string
}

/** 默认值（后端拿不到键时按这一份兜底；面板里的文案与它一一对应）。 */
export const SCRAPE_DEFAULTS: ScrapeSettings = {
  scrapeMode: 'off',
  plotJavtxt: true,
  plotMetatube: true,
  metatubeBase: '',
  translateModel: 'hy3',
  translateModelFallback: 'deepseek-v4.1-flash',
  trailerMode: 'off',
  autoScrapeTier1: false,
  autoScrapeTier2: false,
  cleanSuffixes: ['-UC', '_4K', '-4K', '-C', '-L', '-VR', '-ISO', 'CD1', 'CD2', '中字', '流出'],
  nameTemplate: '{number}{badge} {title}',
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

function textOf(value: unknown, fallback: string): string {
  const text = typeof value === 'string' ? value.trim() : ''
  return text || fallback
}

function listOf(value: unknown, fallback: string[]): string[] {
  if (!Array.isArray(value)) return [...fallback]
  const out = value.map(item => String(item ?? '').trim()).filter(Boolean)
  return out.length ? out : [...fallback]
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
    plotMetatube: boolOf(src.plotMetatube, SCRAPE_DEFAULTS.plotMetatube),
    // 地址没有默认值：留空就是留空（后端据此报「未配置 MetaTube 地址」），不回落
    metatubeBase: typeof src.metatubeBase === 'string' ? src.metatubeBase.trim() : '',
    translateModel: textOf(src.translateModel, SCRAPE_DEFAULTS.translateModel),
    translateModelFallback: textOf(src.translateModelFallback, SCRAPE_DEFAULTS.translateModelFallback),
    trailerMode: pick(src.trailerMode, TRAILERS, SCRAPE_DEFAULTS.trailerMode),
    autoScrapeTier1: boolOf(src.autoScrapeTier1, SCRAPE_DEFAULTS.autoScrapeTier1),
    autoScrapeTier2: boolOf(src.autoScrapeTier2, SCRAPE_DEFAULTS.autoScrapeTier2),
    cleanSuffixes: listOf(src.cleanSuffixes, SCRAPE_DEFAULTS.cleanSuffixes),
    nameTemplate: textOf(src.nameTemplate, SCRAPE_DEFAULTS.nameTemplate),
  }
}

/** 只有这几个键属于刮削两栏（决定「这一栏脏了没有」与提交哪些字段）。 */
export const SCRAPE_KEYS: (keyof ScrapeSettings)[] = [
  'scrapeMode',
  'plotJavtxt',
  'plotMetatube',
  'metatubeBase',
  'translateModel',
  'translateModelFallback',
  'trailerMode',
  'autoScrapeTier1',
  'autoScrapeTier2',
  'cleanSuffixes',
  'nameTemplate',
]
