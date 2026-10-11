<script setup lang="ts">
/**
 * 视图：下载队列（S6 第二个原生化视图）。
 *
 * 对照老实现 `ui/views/downloads.js`（`renderQueue` / `queueRow` / `queueThumb` /
 * `pumpThumbFill` / `applyThumb` / `queueMissingThumbs`）与它的调用方
 * `ui/views/tasks.js`（`loadTasks` / `startTaskPolling`），逐条对齐的是**行为与文案**，
 * DOM 换成 Vuetify 组件：
 *
 * | 老实现 | 这里 |
 * | --- | --- |
 * | 工具条 `<span class="hint">进度取自下载器，每 5 秒自动刷新</span>` + 右侧 `↻ 刷新进度` | 同一句话、同一个按钮（`variant="outlined"` ≈ 老 `.ghost` 描边） |
 * | `#btnRefreshQueue` → `loadTasks(true)`（**非静默**：失败 toast「任务读取失败」） + `toast('下载队列','正在刷新进度…')` | `store.refreshTasks(false)` + `t.info('正在刷新进度…')`；失败 `t.warning('任务读取失败：{原因}')` |
 * | 行 `queueRow(q)`：`.q > .qhd > (.tposter ＋ 番号/元信息/保存路径) ＋ .right(百分比/状态)` + `.bar` | 同一结构、同一顺序（`.avh-q` / `.avh-q__hd` / `.avh-bar`） |
 * | 元信息 `[site, spec, size].filter(Boolean).join(' · ')`，全空 → `—` | 同 |
 * | 保存路径行 `savePath` ＋（有 `added` 时）` · added`，无条件渲染 | 同（空串也保留那一行） |
 * | 进度 `Math.max(0, Math.min(100, Number(progress) || 0))` → `width:{pct}%` | 同 |
 * | 状态文案 `q.state === 'done' ? '已下载' : '下载中…'`；进度条 `bar.done` 换绿 | 同（**不用** `StatusChip`：老实现是 `.hint` 纯文本，换 chip 会改字号与位置） |
 * | 空态 `下载队列为空<br>在「任务」页挑好候选点「下载」，进度在这里看` | `EmptyState`，文案逐字一致（含 `<br>`） |
 * | 封面 `imgWithPlaceholder(q.thumb,'无图')`；`applyThumb` 补到就地换图 | `common/Thumb.vue`（`variant="tposter"`）＋ `common.queueThumb`／`queueMissingThumbs` 串行补图，**只回填不重绘**（`filledThumbs` 变了只换 `<img>` 的 src） |
 * | `queueMissingThumbs(S.queue)`（每轮最多 3 个、补过的番号不再排队） | 同（`common.queueMissingThumbs`），队列每次变化补一轮 |
 * | 轮询：`startTaskPolling()` 每 5 秒 `loadTasks(false)`，靠 `S.view` 是 tasks 或 downloads 判断"只在任务/下载页" | 本视图挂载且 `document.visibilityState === 'visible'` 时每 5 秒 `store.refreshTasks(true)`；**卸载或不可见即停**（不会在别的栏目里偷偷轮询） |
 *
 * 刻意**不做**（老实现也没有，别顺手加）：
 * - 没有行内动作（取消下载 / 重试 / 打开目录）：老下载页只有 `↻ 刷新进度` 一个按钮；
 * - 不渲染 `item.category` / `item.hash` / `item.downloader` / `item.id`：老 `queueRow` 没用它们；
 * - 不按 `state` 过滤或重排：老实现按 `S.queue` 原样顺序画（下载中的不一定在前）；
 * - 不在轮询里刷右栏「运行概况」：老 `loadTasks` 只重画自己（`renderPills` 是本地计数、不发请求），
 *   右栏本来就由壳的 `/bootstrap` 15 秒轮询负责。
 */
import { computed, onBeforeUnmount, onMounted, watch } from 'vue'
import EmptyState from '../common/EmptyState.vue'
import Thumb from '../common/Thumb.vue'
import { filledThumbs, queueMissingThumbs } from '../common/common'
import { hostToast, type PluginApi } from '../../composables/usePluginApi'
import type { PluginStore } from '../../composables/usePluginStore'
import type { QueueItem } from '../../composables/storeTypes'

const props = withDefaults(
  defineProps<{
    /** 数据台单一数据源（`Console.vue` 建好后传进来）。 */
    store: PluginStore
    /** 本插件实例 id：给 `Thumb` 拼图片代理地址用。 */
    pluginId?: string
    /**
     * 用请求器补封面（`plugin/detail`，经 `common.queueThumb` 串行发）。
     * 不传时本轮不补图，列表照常显示占位。
     */
    api?: PluginApi | null
    /** 宿主 toast（`moviepilot:toast` 注入），拿不到时静默降级。 */
    toast?: unknown
  }>(),
  { pluginId: '', api: null, toast: null },
)

const t = hostToast(props.toast as any)

/** 轮询间隔：与老 `startTaskPolling()` 的 5000ms 一致（下载器进度本身就更新得慢）。 */
const POLL_MS = 5000

/** 队列原样取（老实现直接 `S.queue.map(queueRow)`，不过滤、不排序）。 */
const rows = computed<QueueItem[]>(() =>
  Array.isArray(props.store.queue.value) ? props.store.queue.value : [],
)

/** 进度百分比：老实现 `Math.max(0, Math.min(100, Number(q.progress) || 0))`（NaN 也归 0）。 */
function progressOf(item: QueueItem): number {
  return Math.max(0, Math.min(100, Number(item.progress) || 0))
}

/** 完成判定就是 `state === 'done'`（老实现同款，不认别的字符串）。 */
function isDone(item: QueueItem): boolean {
  return item.state === 'done'
}

/** `站点 · 规格 · 大小`，全缺省时显示 `—`（老实现 `meta || '—'`）。 */
function metaOf(item: QueueItem): string {
  return [item.site, item.spec, item.size].filter(Boolean).join(' · ') || '—'
}

/** 保存路径 ＋（有 `added` 时）` · 加入时间`；老实现无条件渲染这一行，空串也占位。 */
function pathOf(item: QueueItem): string {
  return String(item.savePath || '') + (item.added ? ` · ${item.added}` : '')
}

/** 行 key：老实现按数组顺序画、没有 key 概念；这里优先用队列里唯一的 hash / id。 */
function rowKey(item: QueueItem, index: number): string {
  return String(item.hash || item.id || `${item.number || ''}#${index}`)
}

/**
 * 封面地址：优先队列项自带（后端 `image_url()` 通常给的是插件代理地址），
 * 其次是 `common.queueThumb` 补回来的结果——两者都改 `:src`，**不重建整块列表**，
 * 免得用户正看着的进度条/滚动位置被打回去（老 `applyThumb` 的同一纪律）。
 */
function thumbOf(item: QueueItem): string {
  return String(item.thumb || filledThumbs.value[String(item.number || '')] || '')
}

/**
 * 手动刷新（老 `#btnRefreshQueue`）：先起请求**再**提示，顺序与老实现一致。
 *
 * 这一条走非静默（老实现传的就是 `loadTasks(true)`），失败时给 toast；
 * 后台轮询则一律静默，不把界面打成错误态。
 */
async function refreshQueue(): Promise<void> {
  const inflight = props.store.refreshTasks(false)
  t.info('正在刷新进度…')
  if (!(await inflight)) {
    t.warning(`任务读取失败：${props.store.error.value || '请稍后重试'}`)
  }
}

/** 每轮列表变化补一轮缺图：老实现是在 `renderQueue` 末尾调一次 `queueMissingThumbs(S.queue)`。 */
watch(
  rows,
  (items) => {
    if (props.api) queueMissingThumbs(props.api, items)
  },
  { immediate: true },
)

// ---------- 5 秒轮询（只在"本视图挂载 ＋ 页面可见"时跑） ----------

/** `setInterval` 句柄；`null` = 当前没有轮询。 */
let timer: number | null = null

function startPolling(): void {
  if (timer !== null) return
  timer = window.setInterval(() => {
    void props.store.refreshTasks(true)
  }, POLL_MS)
}

function stopPolling(): void {
  if (timer === null) return
  window.clearInterval(timer)
  timer = null
}

/** 切到别的标签页/最小化：立刻停（老实现靠浏览器节流，这里显式停，回来看时 5 秒内自会刷新）。 */
function onVisibilityChange(): void {
  if (document.visibilityState === 'visible') startPolling()
  else stopPolling()
}

onMounted(() => {
  if (document.visibilityState === 'visible') startPolling()
  document.addEventListener('visibilitychange', onVisibilityChange)
})

onBeforeUnmount(() => {
  // 卸载即停：切到别的栏目（原生视图或 iframe）都不该再打 `/tasks`。
  stopPolling()
  document.removeEventListener('visibilitychange', onVisibilityChange)
})
</script>

<template>
  <div class="avh-downloads">
    <div class="avh-downloads__toolbar">
      <span class="avh-downloads__hint">进度取自下载器，每 5 秒自动刷新</span>
      <div class="avh-downloads__spacer" />
      <v-btn variant="outlined" size="small" @click="refreshQueue">↻ 刷新进度</v-btn>
    </div>

    <div v-if="rows.length">
      <div v-for="(item, index) in rows" :key="rowKey(item, index)" class="avh-q">
        <div class="avh-q__hd">
          <Thumb
            class="avh-q__poster"
            variant="tposter"
            :src="thumbOf(item)"
            alt="无图"
            :plugin-id="pluginId"
          />
          <div class="avh-q__main">
            <div class="avh-q__no">{{ item.number || '' }}</div>
            <div class="avh-q__hint avh-q__meta">{{ metaOf(item) }}</div>
            <div class="avh-q__hint avh-q__path">{{ pathOf(item) }}</div>
          </div>
          <div class="avh-q__right">
            <div class="avh-q__no">{{ progressOf(item) }}%</div>
            <div class="avh-q__hint">{{ isDone(item) ? '已下载' : '下载中…' }}</div>
          </div>
        </div>
        <div class="avh-bar" :class="{ 'avh-bar--done': isDone(item) }">
          <i :style="{ width: `${progressOf(item)}%` }" />
        </div>
      </div>
    </div>

    <EmptyState v-else text="下载队列为空<br>在「任务」页挑好候选点「下载」，进度在这里看" />
  </div>
</template>

<style scoped>
/* 对齐 `app.css` 的 `.toolbar` / `.hint` / `.spacer` */
.avh-downloads__toolbar {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
  margin-bottom: 14px;
}

.avh-downloads__hint {
  font-size: 12px;
  color: rgba(var(--v-theme-on-surface), 0.5);
}

.avh-downloads__spacer {
  flex: 1;
}

/* 对齐 `.q`：卡片底色 + 描边 + 10px 圆角 */
.avh-q {
  padding: 12px;
  margin-bottom: 10px;
  border: 1px solid rgba(var(--v-theme-on-surface), 0.12);
  border-radius: 10px;
  background: rgba(var(--v-theme-on-surface), 0.04);
}

/* 对齐 `.qhd` */
.avh-q__hd {
  display: flex;
  align-items: flex-start;
  gap: 12px;
  margin-bottom: 8px;
}

/* 对齐 `.tposter`：48×64 小封面 */
.avh-q__poster {
  width: 48px;
  height: 64px;
  flex: none;
  border-radius: 6px;
  border: 1px solid rgba(var(--v-theme-on-surface), 0.12);
}

/* 老实现的内联 `flex:1;min-width:0` */
.avh-q__main {
  flex: 1;
  min-width: 0;
}

/* 对齐 `.qhd .qn` */
.avh-q__no {
  font-size: 14px;
  font-weight: 600;
}

.avh-q__hint {
  font-size: 12px;
  color: rgba(var(--v-theme-on-surface), 0.5);
}

.avh-q__meta {
  margin-top: 3px;
}

.avh-q__path {
  margin-top: 2px;
}

/* 对齐 `.qhd .right` */
.avh-q__right {
  margin-left: auto;
  text-align: right;
  white-space: nowrap;
}

/* 对齐 `.bar` / `.bar i` / `.bar.done i`（老实现是 --acc2 → --acc 的渐变） */
.avh-bar {
  height: 7px;
  border-radius: 99px;
  overflow: hidden;
  background: rgba(var(--v-theme-on-surface), 0.12);
}

.avh-bar i {
  display: block;
  width: 0;
  height: 100%;
  transition: width 0.3s;
  background: linear-gradient(
    90deg,
    rgba(var(--v-theme-primary), 0.6),
    rgb(var(--v-theme-primary))
  );
}

.avh-bar--done i {
  background: linear-gradient(
    90deg,
    rgba(var(--v-theme-success), 0.6),
    rgb(var(--v-theme-success))
  );
}
</style>
