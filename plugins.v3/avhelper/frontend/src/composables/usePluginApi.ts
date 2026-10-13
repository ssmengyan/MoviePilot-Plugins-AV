/**
 * 宿主注入的插件 API 客户端（`PluginDataDialog` / `PluginConfigDialog` 的 `api` prop）。
 *
 * 宿主侧实现（实测 MP v3.1.2-1 前端产物 `index-*.js`）：`pluginApi` 是 baseURL
 * `api/v1/` 的已认证 axios 实例；**只有分身场景**（`source_plugin_id` 非空且与实例 id
 * 不同）才套一层 `Proxy`，把 `plugin/<sourcePluginId>` 重写成 `plugin/<实例id>`。
 * 普通安装下 `source_plugin_id` 是 `null` → 垫片原样转发，**不会**替组件补插件 id。
 * 所以组件自己必须写全 `plugin/<pluginId>/<端点>`；本模块用 `bindPluginApi` 把这一步
 * 收在一处，组件里仍只写 `plugin/<端点>`。
 *
 * 返回值兼容两种形状（见 `unwrap`）：
 *   1. 完整信封 `{success, message, data}`；
 *   2. 宿主已拆包后的裸数据。
 */
export interface PluginApi {
  get<T = any>(url: string, config?: unknown): Promise<T>
  post<T = any>(url: string, data?: unknown, config?: unknown): Promise<T>
  put?<T = any>(url: string, data?: unknown, config?: unknown): Promise<T>
  delete?<T = any>(url: string, config?: unknown): Promise<T>
  request?<T = any>(config: unknown): Promise<T>
}

/** 宿主插件配置模型（`get_form()` 的 model）。 */
export interface PluginConfig {
  enabled?: boolean
  proxy?: string
  javdb_bin?: string
  data_root?: string
  emby_host?: string
  emby_apikey?: string
  [key: string]: unknown
}

/** `layout` 事件载荷：宿主据此改弹窗最大宽度。 */
export interface LayoutPayload {
  maxWidth: string
}

/** 宿主统一 toast（`moviepilot:toast`），四种方法都可能被调用。 */
export interface HostToast {
  success?(message: string): unknown
  info?(message: string): unknown
  warning?(message: string): unknown
  error?(message: string): unknown
}

/** 未拿到宿主 api 时的降级实现：请求直接失败，由调用方走错误分支。 */
export const NOOP_API: PluginApi = {
  get: () => Promise.reject(new Error('宿主 api 不可用')),
  post: () => Promise.reject(new Error('宿主 api 不可用')),
}

/** 空操作：宿主能力拿不到时的静默降级（设计要求：不自建 Toast / 弹窗）。 */
function noop(): void {
  /* 静默降级 */
}

/**
 * 取出响应信封里的业务数据。
 *
 * 宿主 axios 拦截器两种模式都可能出现（信封模式返回整份信封；旧的 data 模式
 * 直接返回 `data` 字段），所以这里两种都认，避免后端改动形态就把界面打死。
 */
export function unwrap<T = any>(res: any): T {
  if (res && typeof res === 'object' && !Array.isArray(res) && 'data' in res && 'success' in res) {
    return res.data as T
  }
  return res as T
}

/** 从信封或裸对象里读一句可读的错误/提示文案。 */
export function apiMessage(res: any): string {
  if (!res || typeof res !== 'object') return ''
  for (const key of ['message', 'detail', 'msg', 'error']) {
    const value = (res as Record<string, any>)[key]
    if (typeof value === 'string' && value.trim()) return value.trim()
  }
  return ''
}

/** 把任意异常转成一句可读文案。 */
export function errorText(err: any): string {
  const fromPayload = apiMessage(err?.payload) || apiMessage(err?.response?.data)
  if (fromPayload) return fromPayload
  const message = err?.message
  return typeof message === 'string' && message.trim() ? message.trim() : String(err ?? '未知错误')
}

/** 归一化宿主 toast：缺哪个方法就把哪个方法变成空操作。 */
export function hostToast(toast: HostToast | null | undefined): Required<HostToast> {
  return {
    success: typeof toast?.success === 'function' ? toast.success.bind(toast) : noop,
    info: typeof toast?.info === 'function' ? toast.info.bind(toast) : noop,
    warning: typeof toast?.warning === 'function' ? toast.warning.bind(toast) : noop,
    error: typeof toast?.error === 'function' ? toast.error.bind(toast) : noop,
  }
}

/**
 * 把后端给的 `toasts`（`[{level, text}]`）按顺序弹出来。
 *
 * **文案与顺序都由后端定**（`tasks.acquire_feedback()`）：前端不判"该说哪一句"，
 * 所以「PT 站未找到资源」「该资源在所有源中均未找到」这两句只有一处实现。
 * 认不出的级别按 `info` 处理，空文案跳过。
 */
export function playToasts(toast: Required<HostToast>, toasts: unknown): void {
  if (!Array.isArray(toasts)) return
  for (const item of toasts) {
    const record = (item || {}) as { level?: unknown; text?: unknown }
    const text = String(record.text ?? '').trim()
    if (!text) continue
    const level = String(record.level ?? 'info')
    if (level === 'success') toast.success(text)
    else if (level === 'warning') toast.warning(text)
    else if (level === 'error') toast.error(text)
    else toast.info(text)
  }
}

/**
 * 把宿主注入的 `api` 绑到**当前插件实例**上：`plugin/<端点>` → `plugin/<pluginId>/<端点>`。
 *
 * 为什么必须自己补 id（2026-10-10 真机实测根因）：宿主只在分身场景才重写路径
 * （`plugin.source_plugin_id` 非空且 ≠ 实例 id），普通安装下 `source_plugin_id` 是
 * `null`，垫片原样转发。于是 `api.get('plugin/rankings')` 实际打到
 * `/api/v1/plugin/rankings` —— MP 的兜底路由，返回 `{success:true,message:'',data:{}}`，
 * 界面于是"什么都没加载出来"而且**不报错**（榜单 0 部、右栏概况全是 `—`）。
 *
 * 官方指南（`create-moviepilot-plugin/SKILL.md` §Vue API calls）的标准写法是
 * ``props.api.get(`plugin/${props.pluginId}/history`)``；这里把补 id 收进一个函数，
 * 组件里继续只写 `plugin/<端点>`，不必在十几处调用里各写一遍插件 id。
 *
 * 幂等：已经带实例 id 的路径（或不是 `plugin/` 开头的宿主路由，如 `plugin/page/<id>`）
 * 原样返回；`pluginId` 为空时退回原始 `api`（宿主没传 id 时保持旧行为，不猜）。
 *
 * :param api: 宿主注入的原始请求器
 * :param pluginId: 宿主传入的实例 id（`props.pluginId || props.sourcePluginId`）
 */
export function bindPluginApi(api: PluginApi, pluginId: string): PluginApi {
  const id = String(pluginId || '').trim()
  if (!id) return api
  const head = 'plugin/'
  const prefix = `${head}${id}/`

  /** 单个路径的补前缀（非 `plugin/` 开头、或已带实例 id 的一律原样返回）。 */
  function one(path: unknown): any {
    if (typeof path !== 'string') return path
    if (!path.startsWith(head) || path.startsWith(prefix)) return path
    return prefix + path.slice(head.length)
  }

  /** `api.request({url, …})` 形态的补前缀（URL 没变就原样返回，少一次对象拷贝）。 */
  function oneConfig(config: unknown): any {
    if (!config || typeof config !== 'object') return config
    const url = (config as { url?: unknown }).url
    const next = one(url)
    return next === url ? config : { ...(config as Record<string, unknown>), url: next }
  }

  const bound: PluginApi = {
    get: <T = any>(url: string, config?: unknown): Promise<T> => api.get<T>(one(url), config),
    post: <T = any>(url: string, data?: unknown, config?: unknown): Promise<T> =>
      api.post<T>(one(url), data, config),
  }
  if (api.put) {
    bound.put = <T = any>(url: string, data?: unknown, config?: unknown): Promise<T> =>
      api.put!(one(url), data, config)
  }
  if (api.delete) {
    bound.delete = <T = any>(url: string, config?: unknown): Promise<T> => api.delete!(one(url), config)
  }
  if (api.request) {
    bound.request = <T = any>(config: unknown): Promise<T> => api.request!(oneConfig(config))
  }
  return bound
}

/**
 * 统一请求封装 + 宿主 toast 注入。
 *
 * 路径前缀 `plugin/` 由这里统一加，组件里只写端点名（`bootstrap` / `check` …）；
 * 插件 id 由 `bindPluginApi` 在壳（`Console.vue`）里补一次。
 */
export function usePluginApi(api: PluginApi, toast: HostToast | null | undefined) {
  const t = hostToast(toast)

  /** GET：返回业务数据（信封/裸数据都认）。 */
  async function get<T = any>(path: string, config?: unknown): Promise<T> {
    return unwrap<T>(await api.get(`plugin/${path}`, config))
  }

  /** GET 原始响应：少数场景要读信封里的 `message`。 */
  async function getRaw<T = any>(path: string, config?: unknown): Promise<T> {
    return (await api.get(`plugin/${path}`, config)) as T
  }

  /** POST：返回原始响应（调用方多数时候要读 `message`）。 */
  async function post<T = any>(path: string, data?: unknown): Promise<T> {
    return (await api.post(`plugin/${path}`, data)) as T
  }

  return { get, getRaw, post, toast: t }
}
