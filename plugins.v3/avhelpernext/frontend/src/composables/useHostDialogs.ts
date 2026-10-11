import { inject } from 'vue'

/**
 * 宿主确认弹窗（`moviepilot:confirm`）的注入封装。
 *
 * 官方《模块联邦接入指南》§5.10 的签名：
 * ```ts
 * type HostConfirm = (options?: ConfirmOptions) => Promise<boolean>
 * ```
 * - 返回 `true` = 用户点了确认；`false` = 取消或关闭；`undefined` = 注入能力不存在。
 *
 * **降级**：注入拿不到时（旧宿主 / 迷你工装 / 独立调试页）`window.confirm` 接管，
 * 保证「清理缓存」「清空通知」这类破坏性操作仍然有拦一道。
 * 注意本文件**不**自建 Toast、也**不**渲染 `VDialog` 容器：宿主合同要求复用它的实例。
 */
export interface HostConfirmOptions {
  type?: 'info' | 'warn' | 'error'
  title?: string
  content?: string
  confirmText?: string
  cancelText?: string
  width?: string | number
}

export type HostConfirm = (options?: HostConfirmOptions) => Promise<boolean>

/** 一次注入、全设置台共用（`inject` 只能在 `setup()` 顶层调用）。 */
export function useHostConfirm(): (options?: HostConfirmOptions) => Promise<boolean> {
  const injected = inject<HostConfirm | null>('moviepilot:confirm', null)

  return async function confirm(options?: HostConfirmOptions): Promise<boolean> {
    if (typeof injected === 'function') {
      const result = await injected(options)
      return result === true
    }
    // 降级：宿主没给注入能力时用浏览器原生确认框（阻塞式，但只在破坏性操作上出现）。
    const text = [options?.title, options?.content].filter(Boolean).join('\n\n')
    return typeof window !== 'undefined' && typeof window.confirm === 'function'
      ? window.confirm(text || '确认继续？')
      : false
  }
}
