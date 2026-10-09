<script setup lang="ts">
/**
 * 设置台 · 通知。
 *
 * 通知渠道沿用 MoviePilot 原生通知（`post_message`），**本插件不另建渠道**；
 * 这一栏只管已读位点与清空，数据走 `GET /notices`、`DELETE /notices`。
 *
 * 已读位点与内嵌应用（`ui/views/notify.js`）用同一个 localStorage 键：
 * 已读位点上移到设置台自己的键会让两边角标各说各话，所以这里**只读**旧键，
 * 本栏自己的位点写新键（打开本栏即算已读，与铃铛的行为一致）。
 */
import { computed, ref, watch } from 'vue'
import type { NoticeItem } from '../../composables/settingsModel'

const props = defineProps<{
  notices: NoticeItem[]
  loading: boolean
  /** 「清空通知」请求是否在跑。 */
  clearing: boolean
}>()

const emit = defineEmits<{
  (event: 'clear'): void
  (event: 'reload'): void
}>()

/** 内嵌应用用的键（只读，用于判断「那边已读到哪」）。 */
const LEGACY_SEEN_KEY = 'avh.noticesSeen'
/** 设置台自己的已读位点（不污染内嵌应用的键）。 */
const PANEL_SEEN_KEY = 'avhnext.settings.noticesSeen'

const panelSeen = ref(readStorage(PANEL_SEEN_KEY))
const legacySeen = ref(readStorage(LEGACY_SEEN_KEY))

function readStorage(key: string): string {
  try {
    return localStorage.getItem(key) || ''
  } catch {
    return ''
  }
}

const total = computed(() => props.notices.length)
/** 未读 = 时间戳晚于设置台已读位点（与内嵌应用同一套「按时间戳算」的口径）。 */
const unread = computed(() =>
  props.notices.filter(item => String(item.time || '') > panelSeen.value).length,
)

function markSeen(): void {
  const latest = props.notices.reduce(
    (acc, item) => (String(item.time || '') > acc ? String(item.time) : acc),
    panelSeen.value,
  )
  if (latest === panelSeen.value) return
  panelSeen.value = latest
  try {
    localStorage.setItem(PANEL_SEEN_KEY, latest)
  } catch {
    /* 写不了就只保留内存位点 */
  }
}

// 打开这一栏即算已读（和内嵌应用点铃铛一样）：先把未读数读出来，再上移位点。
watch(
  () => props.notices,
  () => {
    legacySeen.value = readStorage(LEGACY_SEEN_KEY)
    setTimeout(markSeen, 0)
  },
  { immediate: true },
)
</script>

<template>
  <v-card variant="tonal" class="avh-panel">
    <v-card-item>
      <template #prepend>
        <v-icon icon="mdi-bell" color="primary" />
      </template>
      <v-card-title>通知</v-card-title>
      <v-card-subtitle>渠道沿用 MoviePilot 原生通知 · 本插件不另建渠道</v-card-subtitle>
    </v-card-item>

    <v-card-text>
      <div class="avh-counts mb-3">
        <v-chip color="primary" variant="tonal" size="small">
          未读 {{ unread }} / 共 {{ total }}
        </v-chip>
        <v-chip v-if="legacySeen" variant="text" size="small" class="text-caption">
          内嵌应用已读到 {{ legacySeen }}
        </v-chip>
      </div>

      <p class="text-caption text-medium-emphasis mb-2">
        通知由 MoviePilot 原生的通知渠道发出（在「设置 → 通知」里配置），这里看到的只是插件自己的收件箱。
        打开本栏即算已读。
      </p>

      <v-list v-if="notices.length" density="compact" class="avh-notices mb-2">
        <v-list-item v-for="(item, index) in notices.slice(0, 20)" :key="index">
          <template #prepend>
            <v-icon
              :icon="item.kind === 'ok' ? 'mdi-check-circle-outline' : item.kind === 'warn' ? 'mdi-alert-outline' : 'mdi-robot-outline'"
              :color="item.kind === 'ok' ? 'success' : item.kind === 'warn' ? 'warning' : 'primary'"
              size="small"
            />
          </template>
          <v-list-item-title class="text-body-2">
            {{ item.title || item.body || '（无标题）' }}
          </v-list-item-title>
          <v-list-item-subtitle class="text-caption">
            {{ item.type || '系统消息' }} · {{ item.time || '—' }}
          </v-list-item-subtitle>
        </v-list-item>
        <v-list-item v-if="notices.length > 20">
          <v-list-item-title class="text-caption text-medium-emphasis">
            只显示最近 20 条，其余 {{ notices.length - 20 }} 条在数据台的铃铛里。
          </v-list-item-title>
        </v-list-item>
      </v-list>
      <v-alert v-else type="info" variant="tonal" density="compact" class="text-caption mb-0">
        暂无通知。
      </v-alert>
    </v-card-text>

    <v-card-actions>
      <v-btn
        variant="text"
        prepend-icon="mdi-refresh"
        :loading="props.loading"
        @click="emit('reload')"
      >刷新</v-btn>
      <v-spacer />
      <v-btn
        color="error"
        variant="tonal"
        prepend-icon="mdi-bell-off-outline"
        :disabled="!total"
        :loading="props.clearing"
        @click="emit('clear')"
      >清空通知</v-btn>
    </v-card-actions>
  </v-card>
</template>

<style scoped>
.avh-panel {
  margin-bottom: 12px;
}

.avh-counts {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}

.avh-notices {
  max-height: 40vh;
  overflow-y: auto;
  background: transparent;
}
</style>
