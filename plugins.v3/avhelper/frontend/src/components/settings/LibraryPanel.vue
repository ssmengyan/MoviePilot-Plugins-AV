<script setup lang="ts">
/**
 * 设置台 · 媒体库。
 *
 * Emby 地址 / API 密钥：**两栏都空 = 复用 MoviePilot「设置 → 媒体服务器」**里配置的 Emby
 * （后端 `__init__.py` 的 `_emby()` 就是这个回落逻辑）。数据归属：宿主配置，
 * 点「保存修改」时走 `emit('save', config)`，宿主负责 `PUT plugin/<id>`。
 *
 * 这一栏的值会随宿主配置保存，插件用它来判断番号是否已入库（打「已入库」标记）。
 */
import { ref } from 'vue'
import type { HostConfigDraft } from '../../composables/settingsModel'

const props = defineProps<{
  config: HostConfigDraft
  /** 跨栏校验提示（两栏只填一半）。 */
  validation: string
}>()

const emit = defineEmits<{
  (event: 'patch', patch: Partial<HostConfigDraft>): void
}>()

const showKey = ref(false)

function patch<K extends keyof HostConfigDraft>(key: K, value: HostConfigDraft[K]): void {
  emit('patch', { [key]: value } as Partial<HostConfigDraft>)
}

/** 两栏都空 = 复用宿主配置，这一句在界面上必须说清楚。 */
function mode(): 'reuse' | 'own' | 'half' {
  const host = (props.config.emby_host || '').trim()
  const key = (props.config.emby_apikey || '').trim()
  if (!host && !key) return 'reuse'
  if (host && key) return 'own'
  return 'half'
}
</script>

<template>
  <v-card variant="tonal" class="avh-panel">
    <v-card-item>
      <template #prepend>
        <v-icon icon="mdi-server" color="primary" />
      </template>
      <v-card-title>媒体库</v-card-title>
      <v-card-subtitle>Emby 地址与密钥 · 两栏都空 = 复用 MoviePilot 的媒体服务器</v-card-subtitle>
    </v-card-item>

    <v-card-text>
      <v-alert
        :type="mode() === 'half' ? 'warning' : mode() === 'own' ? 'success' : 'info'"
        variant="tonal"
        density="compact"
        class="text-caption mb-4"
      >
        <template v-if="mode() === 'reuse'">
          当前：复用 MoviePilot「设置 → 媒体服务器」里已配置的 Emby（两栏留空即是这个状态）。
        </template>
        <template v-else-if="mode() === 'own'">
          当前：使用下面填写的 Emby，不再走 MoviePilot 的媒体服务器配置。
        </template>
        <template v-else>
          {{ props.validation || 'Emby 地址与 API 密钥要一起填，否则会回落到 MoviePilot 的媒体服务器。' }}
        </template>
      </v-alert>

      <v-text-field
        :model-value="props.config.emby_host"
        label="Emby 地址"
        placeholder="http://emby:8096"
        hint="可留空；两栏都空时自动复用 MoviePilot 已配置的 Emby"
        persistent-hint
        variant="outlined"
        density="comfortable"
        clearable
        class="mb-4"
        @update:model-value="(value: any) => patch('emby_host', value ?? '')"
      />

      <v-text-field
        :model-value="props.config.emby_apikey"
        :type="showKey ? 'text' : 'password'"
        label="Emby API 密钥"
        hint="可留空；留空时自动复用 MoviePilot 已配置的 Emby"
        persistent-hint
        variant="outlined"
        density="comfortable"
        clearable
        :append-inner-icon="showKey ? 'mdi-eye-off' : 'mdi-eye'"
        @click:append-inner="showKey = !showKey"
        @update:model-value="(value: any) => patch('emby_apikey', value ?? '')"
      />
    </v-card-text>
  </v-card>
</template>

<style scoped>
.avh-panel {
  margin-bottom: 12px;
}
</style>
