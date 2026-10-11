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
 * `defineEmits` 的**运行时**事件名清单（`Page` / `Config` / `Console` 三个入口共用同一份）。
 *
 * ⚠️ 这里必须是**字符串数组**，不能写成 `defineEmits(consoleEmits())` 那种"返回一个空函数"的
 * 类型式写法 —— 编译器会把那个调用原样搬进组件选项（`emits: consoleEmits()`），而 Vue 的
 * `normalizeEmitsOptions` 只认**数组或对象**，拿到函数什么都不声明。后果是这五个事件全部
 * 退化成 fallthrough attrs 层层下传，在 `Console` 上被 `mergeProps` 合并成
 * `ARRAY[2]`（宿主处理函数 + 上一层 `emit('switch')` 的转发），**一次点击触发两次同名事件**。
 *
 * 真机实测（MP v3.1.4，2026-10-11）：
 * - `switch` 双发 → 宿主 `openSharedDialog` 连推两个设置弹窗，界面叠成两层；
 *   第一次「关闭」只关掉最上面那层，看起来"关不掉"；再点「打开数据台」把最后一层也关掉，
 *   就变成"整个界面消失"；
 * - 递归回环还会抛 `RangeError: Maximum call stack size exceeded`。
 *
 * 所以：运行时清单用下面的常量（`as const` 只为保留字面量类型），类型仍由 `ConsoleEmit` 提供。
 */
export const CONSOLE_EMIT_NAMES = ['save', 'layout', 'switch', 'close', 'action'] as const

/**
 * 历史形态的 `defineEmits` 类型式写法（**已废弃**，保留仅为说明根因）。
 *
 * 现在三处入口写成 `defineEmits(consoleEmits())` 是错的（见上）；
 * 正确写法是 `defineEmits(CONSOLE_EMIT_NAMES)`。
 */
export function consoleEmits(): ConsoleEmit {
  return (() => {}) as unknown as ConsoleEmit
}
