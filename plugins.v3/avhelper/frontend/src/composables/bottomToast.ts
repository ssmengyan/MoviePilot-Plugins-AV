/**
 * 插件自带的「底部居中」提示条（0.6.0 加）。
 *
 * 为什么不用宿主 toast（`moviepilot:toast`）：真机产物里查到 MP 用的库是
 * **vue-toastification**，并在 main.ts 里显式装成了 `position:"bottom-right"`
 * （构建产物原文：`.use(t_,{position:"bottom-right",hideProgressBar:!0,…})`），
 * 落在**右下角**。而「PT 站未找到资源」这类提示按用户要求要出现在**界面中间下方**；
 * 宿主那个位置是宿主自己的配置，插件改不了，所以这一条链路自己弹。
 *
 * 状态放模块级（与 `detailCache` / `filledThumbs` 同一套做法）：`Console.vue` 挂一个
 * `<BottomToast/>`，任意子组件（详情抽屉）都能直接推，不必层层传 props。
 *
 * 级别与后端 `toasts` 的 `level` 一一对应（success / info / warning / error）。
 */
import { ref } from 'vue'

export type BottomToastLevel = 'success' | 'info' | 'warning' | 'error'

export interface BottomToastItem {
  id: number
  level: BottomToastLevel
  text: string
}

/** 一条提示的默认存活时间（毫秒）。 */
export const BOTTOM_TOAST_MS = 4000
/** 最多同时留几条：后端一次最多给三条（PT 未找到 / 所有源都没找到 / 已放进任务页）。 */
export const BOTTOM_TOAST_MAX = 4
/** 同一批提示之间的错开间隔：三条一起冒出来会分不清先后。 */
export const BOTTOM_TOAST_STAGGER_MS = 320

/** 当前在屏幕上的提示（数组顺序 = 自上而下）。 */
export const bottomToasts = ref<BottomToastItem[]>([])

let seq = 0
const timers = new Map<number, number>()

/** 收起一条（点 × 或到点自动收）。 */
export function dismissBottomToast(id: number): void {
  const timer = timers.get(id)
  if (timer !== undefined) {
    window.clearTimeout(timer)
    timers.delete(id)
  }
  bottomToasts.value = bottomToasts.value.filter(item => item.id !== id)
}

/** 弹一条；空文案直接忽略（后端偶尔会带空项）。返回 id（0 = 没弹）。 */
export function pushBottomToast(
  level: BottomToastLevel,
  text: string,
  timeout: number = BOTTOM_TOAST_MS,
): number {
  const clean = String(text ?? '').trim()
  if (!clean) return 0
  seq += 1
  const id = seq
  bottomToasts.value = [...bottomToasts.value, { id, level, text: clean }].slice(-BOTTOM_TOAST_MAX)
  if (timeout > 0) {
    timers.set(id, window.setTimeout(() => dismissBottomToast(id), timeout))
  }
  return id
}

/** 后端给的级别 → 我们认的四种，认不出的按 info。 */
function normalizeLevel(raw: unknown): BottomToastLevel {
  const level = String(raw ?? 'info')
  if (level === 'success' || level === 'warning' || level === 'error') return level
  return 'info'
}

/**
 * 把后端 `toasts`（`[{level,text}]`）按顺序弹出来 —— **文案与顺序都由后端定**
 * （`tasks.acquire_feedback()`），前端只负责显示，所以「PT 站未找到资源」
 * 与「该资源在所有源中均未找到」这两句只有一处实现。
 */
export function playBottomToasts(raw: unknown, timeout: number = BOTTOM_TOAST_MS): void {
  if (!Array.isArray(raw)) return
  raw.forEach((item, index) => {
    const record = (item || {}) as { level?: unknown; text?: unknown }
    const level = normalizeLevel(record.level)
    const text = String(record.text ?? '')
    if (index === 0) {
      pushBottomToast(level, text, timeout)
      return
    }
    window.setTimeout(
      () => pushBottomToast(level, text, timeout),
      index * BOTTOM_TOAST_STAGGER_MS,
    )
  })
}
