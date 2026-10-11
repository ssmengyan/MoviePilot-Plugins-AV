<script setup lang="ts">
/**
 * 设置台 · 通知。
 *
 * 通知渠道沿用 MoviePilot 原生通知（`post_message`），**本插件不另建渠道**；
 * 这一栏只管已读位点与清空，数据走 `GET /notices`、`DELETE /notices`。
 *
 * **已读位点与顶栏铃铛共用同一个键**（S6-8 统一）：
 * `avhnext.settings.noticesSeen` —— 唯一实现在 `composables/noticesSeen.ts`。
 * 这个键原来是本栏专用的（本栏先上线），顶栏通知抽屉做出来之后两边统一到它，
 * 于是"打开本栏"与"打开铃铛抽屉"上移的是同一个位点，两边不会各说各话。
 * 老内嵌应用的键 `avh.noticesSeen` 不再读、不再写（键只留一个的口径见任务约定）。
 *
 * 打开这一栏即算已读（与老 `openNotify()` 点铃铛同一条语义）：`markNoticesSeen()`。
 */
import { computed, watch } from 'vue'
import type { NoticeItem } from '../../composables/settingsModel'
import { markNoticesSeen, seenAt } from '../../composables/noticesSeen'

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

const total = computed(() => props.notices.length)

/**
 * 未读 = 时间戳晚于共享已读位点的条数（与顶栏角标、老 `noticeUnread()` 同一套口径）。
 *
 * `seenAt` 是模块级 ref：`markSeen()` 一改，这个 computed 与顶栏角标**同时**重算，
 * 屏幕上不会出现"设置台说 3 条未读、铃铛已经清零"这种自相矛盾的画面。
 */
const unread = computed(() =>
  props.notices.filter(item => String(item.time || '') > seenAt.value).length,
)

/** 打开这一栏即算已读：先把未读数读出来（`unread` 已缓存），再上移位点。 */
watch(
  () => props.notices,
  () => markNoticesSeen(props.notices),
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
        <v-chip v-if="seenAt" variant="text" size="small" class="text-caption">
          已读到 {{ seenAt }}
        </v-chip>
      </div>

      <p class="text-caption text-medium-emphasis mb-2">
        通知由 MoviePilot 原生的通知渠道发出（在「设置 → 通知」里配置），这里看到的只是插件自己的收件箱。
        打开本栏即算已读；这里的「未读」与数据台顶栏铃铛上的角标是同一个位点。
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
