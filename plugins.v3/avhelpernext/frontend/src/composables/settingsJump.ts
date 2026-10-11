/**
 * 「跳到设置台某一栏」的一次性便签。
 *
 * 背景：宿主合同里的 `switch` 事件只是把 **Page 弹窗**与 **Config 弹窗**互换，
 * **不带任何载荷**；而两个弹窗各自挂一个独立的 `Console` 实例（`mode` 是 prop），
 * 实例之间不共享 `section`。所以数据台里点「改范围 / 改规则」时，切过去只会落在
 * 设置台的第一栏。
 *
 * 解法：用同源 `localStorage` 传一张**一次性**便签 —— 写的一侧紧接着 `emit('switch')`，
 * 读的一侧（设置台实例）在挂载时取走并定位到该栏。不依赖宿主新增能力，
 * 也不改 `switch` 的既有语义（拿不到/读不到就照旧落在第一栏）。
 */

const KEY = 'avhnext.pendingSettingsSection'

/** 记下"切过去之后要落在哪一栏"。取不到存储（隐私模式/被禁）时静默忽略。 */
export function requestSettingsSection(key: string): void {
  try {
    window.localStorage.setItem(KEY, String(key || ''))
  } catch {
    /* 忽略：落回设置台第一栏，不是错误 */
  }
}

/** 取走便签（读后即删，避免下次误跳）。没有则返回空串。 */
export function takePendingSettingsSection(): string {
  try {
    const value = window.localStorage.getItem(KEY) || ''
    if (value) window.localStorage.removeItem(KEY)
    return value
  } catch {
    return ''
  }
}
