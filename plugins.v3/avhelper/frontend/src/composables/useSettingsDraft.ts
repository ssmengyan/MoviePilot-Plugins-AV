import { computed, reactive, ref, shallowRef, type ComputedRef, type Ref } from 'vue'
import {
  errorText,
  hostToast,
  unwrap,
  type HostToast,
  type PluginApi,
  type PluginConfig,
} from './usePluginApi'
import {
  RULE_FALLBACK,
  embyHalfFilled,
  formatBytes,
  sameHost,
  sameRule,
  str,
  toCheckInfo,
  toRuleState,
  type BootstrapLike,
  type CheckInfo,
  type HostConfigDraft,
  type NoticeItem,
  type RuleState,
  type SiteOption,
} from './settingsModel'
import { DIRTY_GROUPS } from '../components/settings/panels'

/**
 * 设置台草稿层（设计文档 §5 的唯一实现处）。
 *
 * 插件有两类可变状态，一个「保存修改」按钮要按顺序都提交：
 *   1. 插件自管数据（默认规则、站点范围）→ `await api.post('plugin/rule', {rule})`；
 *   2. 宿主插件配置（`enabled` / `proxy` / `emby_host` / `emby_apikey`）→ `emit('save', cfg)`，
 *      宿主负责 `PUT`。
 * 顺序固定「先 1 后 2」；第 1 步失败 → toast 报错 + **不**提交第 2 步 + 弹窗不关。
 *
 * 这里只管草稿与脏标记，不碰 DOM、不自己画 Toast：宿主能力（toast）由调用方注入。
 */

export type {
  BootstrapLike,
  CheckInfo,
  HostConfigDraft,
  NoticeItem,
  RuleState,
  SiteOption,
} from './settingsModel'

export { POLICY_MIN_INTERVAL_MIN, POLICY_MAX_PER_DAY } from './settingsPolicy'
export {
  RULE_FALLBACK,
  formatBytes,
  formatCheckTime,
  formatMoment,
  toCheckInfo,
  toRuleState,
} from './settingsModel'

export interface UseSettingsDraftOptions {
  /** 宿主注入的插件请求器（`api` prop）。 */
  api: PluginApi
  /** 宿主配置的初始值（`Config` 的 `initialConfig` prop）。 */
  initialConfig?: PluginConfig | null
  /** 宿主 toast 原始注入对象（拿不到就传 null，静默降级）。 */
  toast?: HostToast | null
  /**
   * 保存第 2 步（宿主配置）。
   *
   * 允许返回 Promise：宿主接了 `save` 时它就是同步的一发 `emit`；
   * 数据台弹窗里宿主没接 `save`，那边是自己 `PUT plugin/<id>`，**失败必须能报出来**，
   * 所以这一步是 await 的（抛异常 → 走下面 catch → toast「保存失败」并且不报成功）。
   */
  onSaveHost: (config: PluginConfig) => void | Promise<void>
}

export interface UseSettingsDraft {
  rule: Ref<RuleState | null>
  hostConfig: HostConfigDraft
  sites: Ref<SiteOption[]>
  sitesLoaded: Ref<boolean>
  notices: Ref<NoticeItem[]>
  cacheText: Ref<string>
  cacheBytes: Ref<number | null>
  checkInfo: Ref<CheckInfo | null>
  ruleDirty: ComputedRef<boolean>
  hostDirty: ComputedRef<boolean>
  dirty: ComputedRef<boolean>
  /** 是否真的拿到了插件开关状态（`initialConfig.enabled` / `/bootstrap.enabled` 至少一个）。 */
  enabledKnown: ComputedRef<boolean>
  /**
   * 宿主配置是否已经读到过**真实值**（`initialConfig` 非空，或调用方用 `GET plugin/<id>` 补过一次）。
   *
   * 这一位是**保存第 2 步的前置条件**：宿主配置走的是整份覆盖的 `PUT plugin/<id>`，
   * 拿一份全空的草稿去 PUT 会把 `enabled` / `proxy` 一起写没（2026-10-11 真机踩过：
   * 数据台弹窗里宿主**不传** `initialConfig`，一保存就把插件关了、代理也清了）。
   */
  hostLoaded: Ref<boolean>
  /** 顶条「保存修改」按钮文案（含 `● 未保存` 标记）。 */
  saveButtonLabel: ComputedRef<string>
  /** 「两栏只填一半」这类跨栏校验提示；空串表示没问题。 */
  validation: ComputedRef<string>
  loading: Ref<boolean>
  saving: Ref<boolean>
  noticeLoading: Ref<boolean>
  cacheCleaning: Ref<boolean>
  error: Ref<string>
  /** 该栏目是否脏（用于左栏小圆点）。 */
  sectionDirty: (key: string) => boolean
  load: () => Promise<void>
  applyBootstrap: (data: BootstrapLike | null) => void
  /** 用宿主配置（`GET plugin/<id>` 的存储值）补一次基准；用户已经改过就不覆盖。 */
  hydrateHost: (conf: PluginConfig | null | undefined) => void
  save: () => Promise<boolean>
  reset: () => void
  resetRule: () => void
  loadNotices: () => Promise<void>
  clearNotices: () => Promise<boolean>
  cleanCache: () => Promise<boolean>
}

/**
 * 设置台草稿。`useRuntimeInfo` 的轮询结果通过 `applyBootstrap` 灌进来：
 * 站点清单、缓存占用、限流信息只有 `/bootstrap` 有，而 `/rule` 才是权威规则来源；
 * 两者到位顺序不定，所以「填一次就不被轮询覆盖」（见 `ruleHydrated` / `hostHydrated`）。
 */
export function useSettingsDraft(options: UseSettingsDraftOptions): UseSettingsDraft {
  const t = hostToast(options.toast)

  const rulePlain: Ref<RuleState | null> = ref(null)
  /** 正常路径就是这一个 ref；`rule` 只是它的别名（避免额外一层对象破坏依赖追踪）。 */
  const rule = rulePlain
  const hostConfig = reactive<HostConfigDraft>({
    enabled: options.initialConfig?.enabled === true,
    proxy: str(options.initialConfig?.proxy),
    emby_host: str(options.initialConfig?.emby_host),
    emby_apikey: str(options.initialConfig?.emby_apikey),
  })

  const sites = ref<SiteOption[]>([])
  const sitesLoaded = ref(false)
  const notices = ref<NoticeItem[]>([])
  const cacheText = ref('')
  const cacheBytes = ref<number | null>(null)
  const checkInfo = ref<CheckInfo | null>(null)
  /** `/bootstrap` 给过的 enabled（`null` = 没给过）；用于判断开关状态是否真实可信。 */
  const bootstrapEnabled = ref<boolean | null>(null)
  /**
   * 宿主配置是否读到过真实值。
   *
   * `initialConfig` 非空（宿主 `./Config` 入口会传 `get_form()` 的 model）即为真；
   * 数据台入口（`./Page`）宿主**不传**这个 prop，必须由调用方 `GET plugin/<id>` 后
   * 用 `hydrateHost()` 补上 —— 在补上之前**不允许**提交宿主配置（见 `hostLoaded` 的说明）。
   */
  const hostLoaded = ref(
    Boolean(options.initialConfig && Object.keys(options.initialConfig as object).length > 0),
  )

  const loading = ref(false)
  const saving = ref(false)
  const noticeLoading = ref(false)
  const cacheCleaning = ref(false)
  const error = ref('')

  /**
   * 原始快照：脏标记的比较基准（`rule` 由 `/rule` 填，`host` 取 props）。
   *
   * ⚠️ 必须是 **shallowRef**，不能是普通 `let`：`ruleDirty` / `hostDirty` 是 `computed`，
   * 只有响应式依赖变化才会重算。用普通变量时「保存后把基准改成当前值」不会触发重算，
   * 顶条的「● 未保存」就永远擦不掉（实测踩过：保存成功、toast 也弹了，标记还在）。
   */
  const ruleBase = shallowRef<RuleState | null>(null)
  const hostBase = shallowRef<HostConfigDraft | null>(null)
  /** 宿主配置是否已从 props 取过一次（只取一次，之后用户的编辑不被覆盖）。 */
  let hostHydrated = false
  /** `/bootstrap` 的 `defaultRule` 是否已经当兜底填过一次（仅当 `/rule` 尚未返回时）。 */
  let ruleHydrated = false

  function hostFromProps(): HostConfigDraft {
    return {
      enabled: options.initialConfig?.enabled === true,
      proxy: str(options.initialConfig?.proxy),
      emby_host: str(options.initialConfig?.emby_host),
      emby_apikey: str(options.initialConfig?.emby_apikey),
    }
  }

  /** 首次取值：`initialConfig` 在挂载前就位；此刻还没有「用户编辑」可被覆盖。 */
  function hydrateHostFromProps(): void {
    if (hostHydrated) return
    hostHydrated = true
    hostBase.value = hostFromProps()
    Object.assign(hostConfig, hostBase.value)
  }

  hydrateHostFromProps()

  /**
   * 用宿主配置（`GET plugin/<id>` 的存储值）补一次基准。
   *
   * 只在「用户还没改过任何宿主字段」时采纳：否则会把用户正在编辑的内容盖掉，
   * 而且脏标记的基准也会被悄悄挪走。拿不到配置（请求失败）时保持原状，
   * `hostLoaded` 仍为 false → 保存第 2 步会被上层挡下（宁可不提交，也不写空）。
   */
  function hydrateHost(conf: PluginConfig | null | undefined): void {
    if (!conf || typeof conf !== 'object') return
    if (hostDirty.value) return
    const next: HostConfigDraft = {
      enabled: conf.enabled === true,
      proxy: str(conf.proxy),
      emby_host: str(conf.emby_host),
      emby_apikey: str(conf.emby_apikey),
    }
    hostHydrated = true
    Object.assign(hostConfig, next)
    hostBase.value = { ...next }
    hostLoaded.value = true
  }

  /** 把 `/bootstrap` 里的只读字段灌进草稿（不覆盖用户已经改过的规则）。 */
  function applyBootstrap(data: BootstrapLike | null): void {
    if (!data || typeof data !== 'object') return

    if (Array.isArray(data.sites)) {
      sites.value = (data.sites as Record<string, unknown>[])
        .map(item => {
          const site = (item || {}) as Record<string, unknown>
          return {
            id: (site.id as string | number | null | undefined) ?? null,
            name: str(site.name),
            adapter: str(site.adapter) || undefined,
            adapterLabel: str(site.adapterLabel) || undefined,
          }
        })
        .filter(item => item.name)
      sitesLoaded.value = true
    }

    if (Array.isArray(data.notices)) notices.value = data.notices as NoticeItem[]

    // 缓存占用：优先用后端的 `cacheSizeText`，没有就用 `cacheSize` 自己换算；都没有 = `—`。
    const text = str(data.cacheSizeText).trim()
    const bytes = Number.isFinite(Number(data.cacheSize)) ? Number(data.cacheSize) : null
    cacheBytes.value = bytes
    cacheText.value = text || formatBytes(bytes)

    checkInfo.value = toCheckInfo(data.check)
    if (typeof data.enabled === 'boolean') bootstrapEnabled.value = data.enabled

    // 只有 `/rule` 还没回来时才拿 bootstrap 的 defaultRule 兜底；它不算脏标记的基准。
    if (!ruleHydrated && !rule.value && data.defaultRule) {
      ruleHydrated = true
      rule.value = toRuleState(data.defaultRule)
    }

    if (!hostLoaded.value && typeof data.enabled === 'boolean') {
      // 宿主配置整份还没读到（数据台入口的常态，`GET plugin/<id>` 还在飞或失败了）：
      // 先把 `/bootstrap` 的 enabled 显示出来，免得把开关画成"假的关"。
      // 它只够显示 —— `hostLoaded` 仍是 false，第 2 步保存照样会被挡下，不会拿它去 PUT。
      hostBase.value = { ...hostConfig, enabled: data.enabled }
      hostConfig.enabled = data.enabled
    }
  }

  /** 拉权威规则（`GET /rule`）：这一份同时充当脏标记的比较基准。 */
  async function loadRule(): Promise<void> {
    const res = await options.api.get<any>('plugin/rule')
    const payload = unwrap<any>(res) ?? {}
    const raw = payload && typeof payload === 'object' && 'rule' in payload ? payload.rule : payload
    const loaded = toRuleState(raw)
    rule.value = loaded
    ruleBase.value = { ...loaded }
  }

  async function loadNotices(): Promise<void> {
    noticeLoading.value = true
    try {
      const res: any = await options.api.get('plugin/notices')
      const payload = unwrap<any>(res) ?? {}
      const list = Array.isArray(payload) ? payload : payload?.notices
      notices.value = Array.isArray(list) ? (list as NoticeItem[]) : []
    } catch (err) {
      error.value = errorText(err)
      t.warning(`通知读取失败：${error.value}`)
    } finally {
      noticeLoading.value = false
    }
  }

  /** 挂载时跑一次：规则与通知要真数据，站点/缓存/限流由 `/bootstrap` 轮询补。 */
  async function load(): Promise<void> {
    loading.value = true
    error.value = ''
    try {
      await loadRule()
    } catch (err) {
      error.value = errorText(err)
      // 规则拉不到不打死界面：草稿回落默认值，用户仍可编辑；此时没有基准 → 保持不脏。
      if (!rule.value) {
        rule.value = { ...RULE_FALLBACK }
        ruleBase.value = { ...RULE_FALLBACK }
      }
    } finally {
      loading.value = false
    }
    await loadNotices()
  }

  const ruleDirty = computed(() => !sameRule(rule.value, ruleBase.value))
  const hostDirty = computed(() => !sameHost(hostConfig, hostBase.value))
  const dirty = computed(() => ruleDirty.value || hostDirty.value)

  const saveButtonLabel = computed(() => (dirty.value ? '保存修改 ● 未保存' : '保存修改'))

  /** 开关状态是否来自真实数据（两边都没给就提示一句，别让人以为「关着」是真状态）。 */
  const enabledKnown = computed(
    () =>
      hostLoaded.value
      || typeof options.initialConfig?.enabled === 'boolean'
      || bootstrapEnabled.value !== null,
  )

  const validation = computed(() => embyHalfFilled(hostConfig))

  function sectionDirty(key: string): boolean {
    const group = DIRTY_GROUPS[key] || 'none'
    if (group === 'rule') return ruleDirty.value
    if (group === 'host') return hostDirty.value
    if (group === 'both') return dirty.value
    return false
  }

  /**
   * 「保存修改」：严格按设计文档 §5 的顺序。
   * 返回 false 表示第 1 步失败（不提交宿主配置、弹窗不关），调用方不需要再提示。
   */
  async function save(): Promise<boolean> {
    if (saving.value || !dirty.value) return !dirty.value
    saving.value = true
    try {
      // 第 1 步：插件自管数据（默认规则 + 站点范围）。
      if (ruleDirty.value && rule.value) {
        const res: any = await options.api.post('plugin/rule', { rule: { ...rule.value } })
        const payload = unwrap<any>(res) ?? {}
        if ((payload as any)?.success === false) {
          t.error(str((payload as any)?.message) || '默认规则保存失败')
          return false
        }
        ruleBase.value = { ...rule.value }
      }

      // 第 2 步：宿主配置（宿主接了 save 就交给宿主 PUT，没接就由调用方自己 PUT）。
      // 先提交、**成功之后**才挪基准：提交失败时「● 未保存」必须留着，否则用户以为存上了。
      const host: HostConfigDraft = {
        enabled: hostConfig.enabled,
        proxy: str(hostConfig.proxy).trim(),
        emby_host: str(hostConfig.emby_host).trim(),
        emby_apikey: str(hostConfig.emby_apikey).trim(),
      }
      await options.onSaveHost({ ...host })
      Object.assign(hostConfig, host)
      hostBase.value = { ...host }

      t.success('已保存')
      return true
    } catch (err) {
      // 第 1 步失败：只报错、不继续、弹窗不关（脏标记保留，改完再存）。
      t.error(`保存失败：${errorText(err)}`)
      return false
    } finally {
      saving.value = false
    }
  }

  function resetRule(): void {
    if (ruleBase.value) rule.value = { ...ruleBase.value }
  }

  /** 丢弃全部未保存改动（关闭弹窗/放弃编辑时用）。 */
  function reset(): void {
    resetRule()
    if (hostBase.value) Object.assign(hostConfig, hostBase.value)
  }

  async function clearNotices(): Promise<boolean> {
    try {
      const res: any = await options.api.delete?.('plugin/notices')
      const payload = unwrap<any>(res) ?? {}
      if ((payload as any)?.success === false) {
        t.warning(str((payload as any)?.message) || '清空通知失败')
        return false
      }
      notices.value = []
      t.success('通知已清空')
      return true
    } catch (err) {
      t.error(`清空通知失败：${errorText(err)}`)
      return false
    }
  }

  /** 清理缓存（返回体里带新的占用，但统一交给调用方再刷一次 `/bootstrap`）。 */
  async function cleanCache(): Promise<boolean> {
    if (cacheCleaning.value) return false
    cacheCleaning.value = true
    try {
      const res: any = await options.api.post('plugin/cache/clean', {})
      const payload = unwrap<any>(res) ?? {}
      if ((payload as any)?.success === false) {
        t.warning(str((payload as any)?.message) || '清理缓存失败')
        return false
      }
      const freed = str((payload as any)?.freedText).trim()
      const message = str((payload as any)?.message).trim()
      t.success(message || (freed ? `缓存已清理，释放 ${freed}` : '缓存已清理'))
      return true
    } catch (err) {
      t.error(`清理缓存失败：${errorText(err)}`)
      return false
    } finally {
      cacheCleaning.value = false
    }
  }

  return {
    rule,
    hostConfig,
    sites,
    sitesLoaded,
    notices,
    cacheText,
    cacheBytes,
    checkInfo,
    ruleDirty,
    hostDirty,
    dirty,
    enabledKnown,
    hostLoaded,
    saveButtonLabel,
    validation,
    loading,
    saving,
    noticeLoading,
    cacheCleaning,
    error,
    sectionDirty,
    load,
    applyBootstrap,
    hydrateHost,
    save,
    reset,
    resetRule,
    loadNotices,
    clearNotices,
    cleanCache,
  }
}
