/**
 * 通用组件的共用辅助（由 S6 地基提供）。
 *
 * 这里只放"多个组件都要用、且必须与老实现逐字一致"的判定与惰性补图队列；
 * 颜色一律由各组件 `<style scoped>` 里的 `var(--v-theme-*)` 直接表达，不在这里转手。
 */
import { ref } from 'vue'
import type { ActionResult, PluginApi } from '../../composables/storeTypes'

/** 匹配分档位（老 `candTable`：≥80 hi、≥55 mid、其余 lo）。 */
export type ScoreLevel = 'hi' | 'mid' | 'lo'

/** 老实现 `views/tasks.js` 的分数档位判定，逐字对齐。 */
export function scoreLevel(score: unknown, pass: boolean): ScoreLevel {
  if (!pass) return 'lo'
  const value = Number(score)
  if (value >= 80) return 'hi'
  if (value >= 55) return 'mid'
  return 'lo'
}

/**
 * 缺封面的番号：串行、限量地补一次详情（老 `views/downloads.js` 的
 * `queueThumb` / `pumpThumbFill` / `applyThumb` / `queueMissingThumbs`）。
 *
 * - **串行**：同一时间只起一个 `plugin/detail` 请求（与详情预热同一条纪律，别并发压 javdb 子进程）；
 * - **限量**：每轮最多补 3 个（`LIMIT`），补过的番号不再排队（`tried`）；
 * - **只回填不重绘**：调用方拿到结果自己更新列表项，别整块重建（用户可能正点着「下载」）。
 */
const FILL_LIMIT = 3
const fillQueue: string[] = []
const fillTried = new Set<string>()
let fillBusy = false

/** 补图结果（`number` → 封面地址，地址可能是相对本插件的 `/img` 代理地址）。 */
export const filledThumbs = ref<Record<string, string>>({})

export function queueThumb(api: PluginApi, number: unknown): void {
  const num = String(number ?? '')
  if (!num || fillTried.has(num)) return
  fillTried.add(num)
  fillQueue.push(num)
  void pumpThumbFill(api)
}

/** 列表里凡是没图的番号，每轮最多补 3 个（老 `queueMissingThumbs(items)`）。 */
export function queueMissingThumbs(
  api: PluginApi,
  items: Array<{ number?: string; thumb?: string }> | null | undefined,
): void {
  ;(items || [])
    .filter(item => item && item.number && !item.thumb)
    .map(item => item.number as string)
    .slice(0, FILL_LIMIT)
    .forEach(num => queueThumb(api, num))
}

async function pumpThumbFill(api: PluginApi): Promise<void> {
  if (fillBusy) return
  const num = fillQueue.shift()
  if (!num) return
  fillBusy = true
  try {
    const raw: any = await api.get('plugin/detail', { params: { number: num } })
    const payload = raw && typeof raw === 'object' && 'success' in raw ? (raw.data ?? raw) : raw
    const thumb = payload?.movie?.thumb
    if (typeof thumb === 'string' && thumb) {
      filledThumbs.value = { ...filledThumbs.value, [num]: thumb }
    }
  } catch {
    // 补图失败不打扰用户：老实现同样是 `.catch(() => {})`，下一轮列表刷新时可以再试。
  } finally {
    fillBusy = false
    void pumpThumbFill(api)
  }
}

/** 仅供测试/调试：清掉"补过图"的记忆。 */
export function resetThumbFill(): void {
  fillQueue.length = 0
  fillTried.clear()
  filledThumbs.value = {}
}

/** 动作结果 → 老实现那套 toast 语义（`kind` 决定提示级别，文案逐字沿用后端/老实现的）。 */
export function toastKindOf(result: ActionResult): 'success' | 'info' | 'warning' | 'error' {
  if (result.kind === 'ok') return 'success'
  if (result.kind === 'limited') return 'warning'
  if (result.kind === 'busy') return 'info'
  return 'error'
}
