<script setup lang="ts">
/**
 * 设置台 · 常规。
 *
 * 切到 `vue` 渲染模式后宿主不再画 `get_form()` 那套 JSON 配置表单，
 * `enabled` / `proxy` / `javdb_bin` / `data_root` 只能在设置台里改 —— 这一栏是它们唯一的入口。
 * 数据归属：宿主配置，点「保存修改」时走 `emit('save', config)`。
 */
import type { HostConfigDraft } from '../../composables/settingsModel'

const props = defineProps<{
  config: HostConfigDraft
  enabledKnown: boolean
}>()

const emit = defineEmits<{
  /** 打补丁到宿主配置草稿（只传改动的字段）。 */
  (event: 'patch', patch: Partial<HostConfigDraft>): void
}>()

function patch<K extends keyof HostConfigDraft>(key: K, value: HostConfigDraft[K]): void {
  emit('patch', { [key]: value } as Partial<HostConfigDraft>)
}
</script>

<template>
  <v-card variant="tonal" class="avh-panel">
    <v-card-item>
      <template #prepend>
        <v-icon icon="mdi-cog-outline" color="primary" />
      </template>
      <v-card-title>常规</v-card-title>
      <v-card-subtitle>插件开关、代理与路径 · 属于宿主插件配置</v-card-subtitle>
    </v-card-item>

    <v-card-text>
      <v-switch
        :model-value="props.config.enabled"
        color="primary"
        hide-details
        inset
        label="启用插件"
        class="mb-2"
        @update:model-value="(value: any) => patch('enabled', value === true)"
      />
      <p v-if="!props.enabledKnown" class="text-caption text-medium-emphasis mb-4">
        拿不到当前开关状态（<code>/bootstrap</code> 未返回 <code>enabled</code>），保存前请确认。
      </p>
      <p class="text-caption text-medium-emphasis mb-4">
        关闭后定时订阅检查与「运行一次」都不执行，界面仍可浏览。
      </p>

      <v-text-field
        :model-value="props.config.proxy"
        label="javdb 代理地址"
        placeholder="http://host:port"
        hint="javdb 子进程与站点请求走这个代理；站点自己开了代理时按站点配置走。留空 = 直连。"
        persistent-hint
        variant="outlined"
        density="comfortable"
        clearable
        class="mb-4"
        @update:model-value="(value: any) => patch('proxy', value ?? '')"
      />

      <v-text-field
        :model-value="props.config.javdb_bin"
        label="javdb 路径"
        placeholder="留空 = 自动下载 / 自动查找"
        hint="发现层依赖 javdb-cli 单文件二进制。留空时插件启动后自动下一份到数据目录；网络不通就手工放一份再填这里。"
        persistent-hint
        variant="outlined"
        density="comfortable"
        clearable
        class="mb-4"
        @update:model-value="(value: any) => patch('javdb_bin', value ?? '')"
      />

      <v-text-field
        :model-value="props.config.data_root"
        label="数据目录"
        placeholder="留空 = MP 插件数据目录（/config/plugins/AVHelper）"
        hint="SQLite 台账、JSON 缓存与图片缓存同根。改这里等于换一套数据，旧数据不会自动搬过去。"
        persistent-hint
        variant="outlined"
        density="comfortable"
        clearable
        @update:model-value="(value: any) => patch('data_root', value ?? '')"
      />
    </v-card-text>
  </v-card>
</template>

<style scoped>
.avh-panel {
  margin-bottom: 12px;
}
</style>
