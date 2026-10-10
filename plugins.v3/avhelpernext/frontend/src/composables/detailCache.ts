/**
 * 影片详情 / 长缩略图的**模块级**缓存（模块作用域，跨组件卸载存活）。
 *
 * 为什么单独成文件（而不是放进 `views/DiscoverView.vue` 或 `detail/DetailDrawer.vue`）：
 * 老实现的这两份缓存在 `ui/core/state.js` 的全局 `CACHE` 里，被**两个方向**读写 ——
 * ① 发现榜单的 paint 之后 `prefetchCards()` 把前 6 张详情预热进 `CACHE['detail:'+num]`；
 * ② 详情抽屉 `paintDetail()` 先读同一份缓存，命中就**立刻画**、不转圈。
 * 两边写在同一个文件里，预热的结果才真的能省掉打开抽屉时那次 `GET /detail`。
 *
 * 与老实现的对应：
 * | 老实现 | 这里 |
 * | --- | --- |
 * | `CACHE['detail:'+number]` = `{data, t}` 或 `{error}` | `detailCache`（键就是番号，不带前缀） |
 * | `LONG_STATE[number]` = `{url}` / `{err}` / `{loading:true}` | `longState`（同样三态，写进 `reactive` 以便响应式） |
 * | `cached('detail:'+number)` | `cachedDetail(number)` |
 * | 长图解析结果**回填**详情条目（`e.data.longimage = url`） | `setLongUrl()` 同一件事 |
 */
import { reactive } from 'vue'
import type { PluginApi } from './usePluginApi'

/** 详情条目：`error` 非空 = 上次抓失败过（老 `{error}` 条目）；否则 `data` 是 `GET plugin/detail` 的载荷。 */
export interface DetailEntry {
  data: Record<string, any>
  t: number
  error: string
}

/** 长缩略图状态：`url` 已拿到 / `err` 失败 / `loading` 解析中（三态互斥，照抄老 `LONG_STATE`）。 */
export interface LongState {
  url?: string
  err?: string
  loading?: boolean
}

/** `CACHE['detail:'+number]`：键 = 番号。`reactive(Map)` 保证晚到的响应能触发重绘。 */
export const detailCache = reactive(new Map<string, DetailEntry>())

/** `LONG_STATE`：键 = 番号。 */
export const longState = reactive(new Map<string, LongState>())

/** 读详情缓存（老 `cached('detail:' + number)`）。 */
export function cachedDetail(number: unknown): DetailEntry | undefined {
  const key = String(number ?? '')
  return key ? detailCache.get(key) : undefined
}

/** 写详情缓存（老 `put('detail:'+number, {data, t})`）。 */
export function putDetail(number: unknown, data: Record<string, any>): void {
  const key = String(number ?? '')
  if (!key) return
  detailCache.set(key, { data: data || {}, t: Date.now(), error: '' })
}

/** 写失败条目（老 `put('detail:'+number, {error})`）。 */
export function putDetailError(number: unknown, error: string): void {
  const key = String(number ?? '')
  if (!key) return
  detailCache.set(key, { data: {}, t: Date.now(), error })
}

/** 删一条（老 `delete CACHE['detail:'+number]`，抽屉上的「重新抓取」与 `detail-retry` 都用它）。 */
export function dropDetail(number: unknown): void {
  const key = String(number ?? '')
  if (key) detailCache.delete(key)
}

/**
 * 删掉某个番号的长图状态。
 *
 * 老实现的「重新抓取」**不**动 `LONG_STATE`（`loadLong` 命中 `{url}` 就直接重画，
 * 这也是"重绘不该重新解析长图"的那条纪律）；这里保持同样的语义，
 * 只在确实要重新解析时才删（`loadLong(force)` 内部那段，以及验收工装换片子时）。
 */
export function dropLong(number: unknown): void {
  const key = String(number ?? '')
  if (key) longState.delete(key)
}

/**
 * 把解析到的长图地址回填进详情条目（老 `loadLong()` 里那句
 * `const e = cached('detail:'+number); if (e && e.data) e.data.longimage = url`）。
 *
 * 回填的意义：同一部片再打开时，`detailHtml` 已经能直接拿到 `longimage`，
 * 省掉一次 `/longimage` 往返。
 */
export function setLongUrl(number: unknown, url: string): void {
  const entry = cachedDetail(number)
  if (entry && entry.data) entry.data.longimage = url
}

/**
 * `GET plugin/longimage?number=`（长图 URL 只解析、不下载，图片由前端直连）。
 *
 * 用「抛错的 raw 请求」而不是 `usePluginApi.get()`：后者的 `unwrap` 会把 `success:false`
 * 折成一句话，而老 `apiGet` 的返回是 `{ok,data|message}` —— 这里要复刻的正是那个形状
 * （失败时把后端的 `message` 原文交给 `longFail`）。
 *
 * :param force: 老「重试」按钮走 `?force=1`，绕过后端那份 7 天缓存重新解析。
 */
export async function fetchLongUrl(
  api: PluginApi | null | undefined,
  number: string,
  force = false,
): Promise<{ ok: true; url: string } | { ok: false; message: string }> {
  if (!api || typeof api.get !== 'function') return { ok: false, message: '宿主请求器不可用' }
  const params: Record<string, string | number> = { number }
  if (force) params.force = 1
  try {
    const raw: any = await api.get('plugin/longimage', { params })
    const payload = raw && typeof raw === 'object' && 'data' in raw ? raw.data : raw
    if (payload && typeof payload === 'object' && payload.success === false) {
      return { ok: false, message: String(payload.message || payload.detail || '') }
    }
    const url = String((payload && (payload.url || payload.longimage)) || '')
    return { ok: true, url }
  } catch (err: any) {
    const payload = err?.payload || err?.response?.data
    const message = String(payload?.message || payload?.detail || err?.message || '请稍后重试')
    return { ok: false, message }
  }
}
