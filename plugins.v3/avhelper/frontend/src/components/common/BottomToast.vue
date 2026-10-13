<script setup lang="ts">
/**
 * 底部居中的提示条（0.6.0）——本插件唯一自建的提示层。
 *
 * 为什么自建（而不是用宿主 `moviepilot:toast`）：真机产物实测宿主把它装在
 * **右下角**（vue-toastification + `position:"bottom-right"`，见 `composables/bottomToast.ts`
 * 的文件头），而用户要求「PT 站未找到资源」这类提示出现在界面中间下方。
 * 除这一条链路外，其它提示仍走宿主 toast（`AboutPanel` 里那句"不自建"的口径不变）。
 *
 * 交互：`position: fixed` 固定在视口底部居中，最多同时 4 条、4 秒自动收起，
 * 也可以点 × 立刻收起；`pointer-events` 只开在卡片上，不挡住底下的按钮。
 */
import {
  bottomToasts,
  dismissBottomToast,
  type BottomToastItem,
  type BottomToastLevel,
} from '../../composables/bottomToast'

const COLORS: Record<BottomToastLevel, string> = {
  success: 'success',
  info: 'info',
  warning: 'warning',
  error: 'error',
}

const ICONS: Record<BottomToastLevel, string> = {
  success: 'mdi-check-circle',
  info: 'mdi-information',
  warning: 'mdi-alert-circle',
  error: 'mdi-close-circle',
}

function colorOf(item: BottomToastItem): string {
  return COLORS[item.level] || 'info'
}

function iconOf(item: BottomToastItem): string {
  return ICONS[item.level] || 'mdi-information'
}
</script>

<template>
  <div class="avh-bottomtoast" data-avh="bottom-toast" aria-live="polite">
    <v-card
      v-for="item in bottomToasts"
      :key="item.id"
      class="avh-bottomtoast__item"
      :color="colorOf(item)"
      variant="flat"
      elevation="8"
    >
      <v-icon :icon="iconOf(item)" size="small" />
      <span class="avh-bottomtoast__text">{{ item.text }}</span>
      <v-btn
        icon="mdi-close"
        size="x-small"
        variant="text"
        :title="'收起这条提示'"
        @click="dismissBottomToast(item.id)"
      />
    </v-card>
  </div>
</template>

<style scoped>
.avh-bottomtoast {
  position: fixed;
  left: 50%;
  bottom: 28px;
  transform: translateX(-50%);
  /* 盖在宿主弹窗/抽屉之上：宿主 v-dialog 的 z-index 在 2400 上下 */
  z-index: 100000;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 8px;
  width: max-content;
  max-width: min(92vw, 620px);
  /* 容器不吃点击，只有卡片吃 —— 别挡住底下的按钮 */
  pointer-events: none;
}

.avh-bottomtoast__item {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 12px;
  border-radius: 8px;
  pointer-events: auto;
}

.avh-bottomtoast__text {
  font-size: 14px;
  line-height: 1.4;
  word-break: break-word;
}
</style>
