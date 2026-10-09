/**
 * 宿主注入的插件 API 客户端（`PluginDataDialog` 的 `api` prop）。
 *
 * 宿主侧实现（实测 MP v3.1.2-1 前端产物 `index-*.js`）：`pluginApi`（信封模式）
 * 经 `Proxy` 把 `plugin/<sourcePluginId>/…` 重写成当前实例 id，再交给
 * 已认证 axios 实例。返回值兼容两种形状（见 `unwrap`）：
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
 * 统一请求封装 + 宿主 toast 注入。
 *
 * 路径前缀 `plugin/` 由这里统一加，组件里只写端点名（`bootstrap` / `check` …）。
 * 不复用 `pluginId` 拼路径：宿主 `api` 已绑定当前实例（含分身重写），
 * 这正是官方指南 §5.5 推荐的做法。
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
