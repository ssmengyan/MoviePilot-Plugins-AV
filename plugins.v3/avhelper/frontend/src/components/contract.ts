import type { PluginApi, PluginConfig } from '../composables/usePluginApi'

/**
 * 宿主合同（实测 MP v3.1.2-1 前端产物 `PluginDataDialog.vue_…-*.js`，不是推测）：
 *
 * ```js
 * re = defineComponent({
 *   props: { plugin: Object, show_switch: { type: Boolean, default: true } },
 *   emits: ['close', 'save', 'switch'],
 *   ...
 *   h(Remote, {
 *     api: boundApi,                        // 已绑定当前实例 id 的 pluginApi
 *     'plugin-id': plugin.id,
 *     'source-plugin-id': plugin.source_plugin_id,
 *     'native-subscribe': nativeSubscribe,
 *     show_switch,                          // 宿主那个开关，原样透传
 *     onAction, onLayout: p => { maxWidth.value = p?.maxWidth?.trim?.() || '80rem' },
 *     onSwitch, onClose,
 *   })
 * })
 * ```
 *
 * 两点结论：
 * - 齿轮按钮是宿主 `render_mode === 'vuetify'` 分支才画的；`vue` 分支把弹窗正文
 *   整个交给我们（`VCard(pa-0)` + 我们的组件），所以我们自己画标题栏和关闭按钮。
 * - `layout` 的载荷是 `{maxWidth: '<CSS 长度>'}`，宿主默认 `80rem`。
 */
export interface HostContractProps {
  /** 宿主注入的已认证插件请求器（已绑定当前实例 id）。 */
  api?: PluginApi
  /** 当前插件实例 id。 */
  pluginId?: string
  /** 虚拟分身共享资源的源插件 id；普通插件为空。 */
  sourcePluginId?: string
  /** 打开宿主的原生订阅交互（可由 `moviepilot:nativeSubscribe` 注入同一份）。 */
  nativeSubscribe?: ((mediaInfo: Record<string, unknown>) => Promise<unknown>) | null
  /** 宿主是否显示 Page ⇄ Config 切换按钮（透传，我们只声明、不用它画东西）。 */
  show_switch?: boolean
}

/** Config 额外的初始配置（= 后端 `get_form()` 的 model）。 */
export interface ConfigProps extends HostContractProps {
  initialConfig?: PluginConfig
}

/** 设计文档 §3：挂载时声明弹窗宽度。 */
export const DEFAULT_MAX_WIDTH = '90rem'

/** 宿主默认弹窗宽度（实测 `V.value = t || '80rem'`），仅作注释参考。 */
export const HOST_DEFAULT_MAX_WIDTH = '80rem'
