<script setup lang="ts">
import Console from './Console.vue'
import { consoleEmits } from './emitContract'
import { type ConfigProps } from './contract'

/**
 * 暴露给宿主的 `./Page`：插件详情弹窗正文。
 *
 * 薄封装——和 `./Config` 渲染的是同一个 `Console.vue`，只差初始栏目
 * （设计文档 §1：用户无论从哪个入口进来，看到的都是同一套界面）。
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
    mode="data"
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
