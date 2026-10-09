<script setup lang="ts">
import Console from './Console.vue'
import { consoleEmits } from './emitContract'
import { type ConfigProps } from './contract'

/**
 * 暴露给宿主的 `./Config`：插件配置弹窗正文（`initialConfig` = `get_form()` 的 model）。
 *
 * 和 `./Page` 共用 `Console.vue`，只差初始栏目与顶条的「保存修改」按钮
 * （设计文档 §5：宿主负责把 `save` 的载荷 `PUT` 回插件配置）。
 */
withDefaults(defineProps<ConfigProps>(), {
  api: () => ({ get: () => Promise.reject(new Error('宿主 api 不可用')), post: () => Promise.reject(new Error('宿主 api 不可用')) }),
  pluginId: '',
  sourcePluginId: '',
  nativeSubscribe: null,
  show_switch: true,
  initialConfig: () => ({}),
})

const emit = defineEmits(consoleEmits())
</script>

<template>
  <Console
    mode="settings"
    :api="api"
    :plugin-id="pluginId"
    :source-plugin-id="sourcePluginId"
    :native-subscribe="nativeSubscribe"
    :show_switch="show_switch"
    :initial-config="initialConfig"
    @save="(config: any) => emit('save', config)"
    @layout="(payload: any) => emit('layout', payload)"
    @switch="emit('switch')"
    @close="emit('close')"
    @action="emit('action')"
  />
</template>
