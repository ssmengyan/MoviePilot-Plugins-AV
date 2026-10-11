import type { PluginConfig } from '../composables/usePluginApi'
import type { LayoutPayload } from '../composables/usePluginApi'

/** 我们向宿主发出的五个事件（`action` 表示「宿主该刷新数据了」）。 */
export interface ConsoleEmit {
  /** 宿主负责 `PUT plugin/<id>` 保存插件配置（设计文档 §5 第 2 步）。 */
  (event: 'save', config: PluginConfig): void
  /** 改宿主弹窗最大宽度：`{maxWidth: '<CSS 长度>'}`。 */
  (event: 'layout', payload: LayoutPayload): void
  /** Page ⇄ Config 两个弹窗互换（宿主合同）。 */
  (event: 'switch'): void
  /** 关闭弹窗。 */
  (event: 'close'): void
  /** 通知宿主数据有变化，该刷新了（官方指南 §5.1）。 */
  (event: 'action'): void
}

/**
 * `defineEmits` 的函数式写法：类型明确、模板里 `emit('switch')` 等调用都带类型。
 * 三处入口（Page / Config / Console）共用同一份声明。
 */
export function consoleEmits(): ConsoleEmit {
  return (() => {}) as unknown as ConsoleEmit
}
