<script setup lang="ts">
/**
 * 错误态（老实现 `ui/ui/widgets.js` 的 `errHtml(msg, retryAttr)` + `app.css` 的 `.errbox`）。
 *
 * 老实现的 DOM：
 * ```
 * <div class="errbox">⚠️ {msg}<br><br><button class="primary" data-act="...">重试</button></div>
 * ```
 * 老代码用 `data-act` 属性做事件委托（`app.js` 的 `bindUi()` 统一接 `rank-retry` /
 * `detail-retry` / `actor-retry` / `picker-retry`）；Vue 里改成显式 `retry` 事件，
 * 但**文案、⚠️ 前缀、按钮名「重试」逐字不变**。
 */
withDefaults(
  defineProps<{
    /** 错误文案（老实现由调用方拼好，如「插件状态读取失败：…（仍可尝试直接抓取榜单）」）。 */
    message?: string
    /** 是否显示「重试」按钮（老实现没有 retryAttr 时不画按钮）。 */
    retryable?: boolean
    /** 重试按钮文案。 */
    retryText?: string
    /** 重试中（按钮转圈并禁用）。 */
    retrying?: boolean
  }>(),
  {
    message: '',
    retryable: true,
    retryText: '重试',
    retrying: false,
  },
)

const emit = defineEmits<{
  /** 用户点了「重试」。 */
  (event: 'retry'): void
}>()
</script>

<template>
  <div class="avh-errbox" role="alert">
    <div class="avh-errbox__msg">⚠️ {{ message || '抓取失败，请稍后重试' }}</div>
    <div v-if="retryable" class="avh-errbox__act">
      <v-btn
        color="primary"
        variant="flat"
        size="small"
        :loading="retrying"
        @click="emit('retry')"
      >{{ retryText }}</v-btn>
    </div>
  </div>
</template>

<style scoped>
/* 对齐 `app.css` 的 `.errbox`（语义色走主题的 error 通道，不写死深色值） */
.avh-errbox {
  padding: 20px 18px;
  border-radius: 10px;
  text-align: center;
  font-size: 13px;
  line-height: 1.9;
  color: rgb(var(--v-theme-error));
  background: rgba(var(--v-theme-error), 0.12);
  border: 1px solid rgba(var(--v-theme-error), 0.38);
}

.avh-errbox__msg {
  word-break: break-word;
}

.avh-errbox__act {
  margin-top: 12px;
}
</style>
