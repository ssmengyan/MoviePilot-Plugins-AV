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
 * | 状态文案 `q.state === 'done' ? '已下载' : '下载中…'`；进度条 `bar.done` 换绿 | 老实现那两句现在只剩「下载中…」（只画在下载中那一节）；完成条目按 §5.3 不再画百分比/状态/进度条，所以 `.bar.done` 那条绿色规则已随之下线 |
 * | 空态 `下载队列为空<br>在「任务」页挑好候选点「下载」，进度在这里看` | `EmptyState`，文案逐字一致（含 `<br>`；**队列整体为空**时才是它，某一节为空只画一行小字提示） |
 * | 封面 `imgWithPlaceholder(q.thumb,'无图')`；`applyThumb` 补到就地换图 | `common/Thumb.vue`（`variant="tposter"`）＋ `common.queueThumb`／`queueMissingThumbs` 串行补图，**只回填不重绘**（`filledThumbs` 变了只换 `<img>` 的 src） |
 * | `queueMissingThumbs(S.queue)`（每轮最多 3 个、补过的番号不再排队） | 同（`common.queueMissingThumbs`），队列每次变化补一轮 |
 * | 轮询：`startTaskPolling()` 每 5 秒 `loadTasks(false)`，靠 `S.view` 是 tasks 或 downloads 判断"只在任务/下载页" | 本视图挂载且 `document.visibilityState === 'visible'` 时每 5 秒 `store.refreshTasks(true)`；**卸载或不可见即停**（不会在别的栏目里偷偷轮询） |
 *
 * **按 `state` 拆两节（下载历史契约 §5.3，本轮新增，用户诉求①）**：
 * 「已完成下载不再显示进度，直接当历史停住」——所以队列拆成「下载中」（`state !== 'done'`，
 * 照旧进度/百分比/封面）与「已完成」（`state === 'done'`：番号/标题/大小/完成时间/库状态，
 * **没有进度条、没有任何"进行中"交互**，就是一条静态历史行）。
 *
 * 为什么「已完成」这一节通常**是空的**：契约 §3 起，条目一旦变成 `done`，后端就把它写进下载台账
 * 并**从队列里删掉**（历史归台账，队列只留下载中）。留着这一节是为了兼容两种过渡情形 ——
 * ① 升级前留下的旧快照里那些 `done` 条目（后端删得掉队列，删不掉已经取到的快照）；
 * ② 轮询间隙：下载器刚报完成、后端这一轮还没清掉的那几秒。
 * 完成清单的权威位置是「下载历史」页，所以小节标题右侧写了那句指路。
 * 真机 2026-10-11 探针：队列 19 条里 17 条是 `done`（旧快照），这一节眼下反而是满的。
 *
 * 刻意**不做**（老实现也没有，别顺手加）：
 * - 没有行内动作（取消下载 / 重试 / 打开目录）：老下载页只有 `↻ 刷新进度` 一个按钮；
 * - 不渲染 `item.category` / `item.hash` / `item.downloader` / `item.id`：老 `queueRow` 没用它们；
 * - 不在节内重排：两节各自的顺序仍是 `S.queue` 的原样顺序（老实现不过滤，这里只按 `state` 一刀切）；
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

/**
 * 完成行比队列项多出来的**可选**字段（契约 §5.3 要求「已完成」列出 标题/完成时间/库状态）。
 *
 * 为什么要单独声明：契约 §4 的台账条目（`GET /downloads`）才有 `title` / `completedAt` / `lib`，
 * 而真机实测（2026-10-11 探针：队列 19 条、17 条 `done`）队列条目的**全部键**只有
 * `id/number/thumb/site/spec/size/hash/downloader/category/savePath/state/progress/added`。
 * 所以这里按可选读：后端哪天把台账字段并进旧队列行（或直接给队列项带上），界面自动就能显示；
 * 拿不到就退回 `added`／留空，**绝不编造**「不在库」这种结论（那是台账 + Emby 实时命中的口径）。
 */
type DoneRow = QueueItem & {
  /** 片名（台账口径）。 */
  title?: string
  /** 完成时间（台账的 `completed_at`；旧队列快照没有）。 */
  completedAt?: string
  /** 实时 Emby 命中（`null` = 不在库），与契约 §4 的 `lib` 同名同形。 */
  lib?: { id?: string; name?: string; path?: string; url?: string } | null
}

/** 完成判定就是 `state === 'done'`（老实现同款，不认别的字符串）。 */
function isDone(item: QueueItem): boolean {
  return item.state === 'done'
}

/** 「下载中」：`state !== 'done'` —— 老实现画的那一套（百分比 + 进度条）只留给这一节（契约 §5.3）。 */
const activeRows = computed<QueueItem[]>(() => rows.value.filter(item => !isDone(item)))

/** 「已完成」：`state === 'done'` —— 静态历史行，没有进度条与一切"进行中"交互（契约 §5.3）。 */
const doneRows = computed<DoneRow[]>(() => rows.value.filter(item => isDone(item)) as DoneRow[])

/** 进度百分比：老实现 `Math.max(0, Math.min(100, Number(q.progress) || 0))`（NaN 也归 0）。 */
function progressOf(item: QueueItem): number {
  return Math.max(0, Math.min(100, Number(item.progress) || 0))
}

/** `站点 · 规格 · 大小`，全缺省时显示 `—`（老实现 `meta || '—'`）。 */
function metaOf(item: QueueItem): string {
  return [item.site, item.spec, item.size].filter(Boolean).join(' · ') || '—'
}

/** 保存路径 ＋（有 `added` 时）` · 加入时间`；老实现无条件渲染这一行，空串也占位。 */
function pathOf(item: QueueItem): string {
  return String(item.savePath || '') + (item.added ? ` · ${item.added}` : '')
}

/**
 * 完成行的「大小 · 完成时间 · 库状态」一行（契约 §5.3 的列）。
 *
 * 三个字段都按"拿得到才画"处理：
 * - 完成时间：台账的 `completedAt` 优先；旧队列快照只有 `added`（提交下载那一刻），
 *   就照实写「加入 …」而不是硬写成"完成"（两种情形差着整段下载时间，别骗用户）；
 * - 库状态：`lib` 键存在才画（`null` = 不在库）；键都没有就整段不出现 —— 凭一个拿不到的字段
 *   写「不在库」是编造，也会让用户以为台账在说这部片已经没了。
 */
function doneInfoOf(item: DoneRow): string {
  const completed = String(item.completedAt || '')
  const added = String(item.added || '')
  const when = completed ? `完成 ${completed}` : added ? `加入 ${added}` : ''
  const lib = 'lib' in item ? (item.lib ? '在库' : '不在库') : ''
  return [item.size, when, lib].filter(Boolean).join(' · ') || '—'
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

    <template v-if="rows.length">
      <!-- ===== 下载中：老实现的全套（封面 / 元信息 / 路径 / 百分比 / 进度条） ===== -->
      <div class="avh-downloads__secttl">下载中（{{ activeRows.length }}）</div>

      <template v-if="activeRows.length">
        <div v-for="(item, index) in activeRows" :key="rowKey(item, index)" class="avh-q">
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
              <div class="avh-q__hint">下载中…</div>
            </div>
          </div>
          <div class="avh-bar">
            <i :style="{ width: `${progressOf(item)}%` }" />
          </div>
        </div>
      </template>
      <!-- 一节为空只给一行小字（整体为空的 `EmptyState` 在下面），别把一个空态画两遍 -->
      <div v-else class="avh-downloads__hint">没有下载中的任务</div>

      <!--
        ===== 已完成：静态历史行（契约 §5.3）=====
        没有进度条、没有百分比、没有状态文案、没有任何"进行中"交互 —— 用户的诉求就是
        「已完成下载不再显示进度，直接当历史停住」。这一节通常为空：契约 §3 起，条目一变 `done`
        就被后端写进下载台账并从队列里删掉；留着它只为兼容旧快照与轮询间隙（见文件头注释）。
      -->
      <div class="avh-downloads__secttl">
        <span>已完成（{{ doneRows.length }}）</span>
        <span class="avh-downloads__secttl-note">完整清单见「下载历史」</span>
      </div>

      <template v-if="doneRows.length">
        <div v-for="(item, index) in doneRows" :key="rowKey(item, index)" class="avh-q avh-q--done">
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
              <!-- 标题是台账口径的可选字段（真机队列暂不携带），有才画这一行 -->
              <div v-if="item.title" class="avh-q__ttl">{{ item.title }}</div>
              <div class="avh-q__hint avh-q__meta">{{ doneInfoOf(item) }}</div>
            </div>
          </div>
        </div>
      </template>
      <div v-else class="avh-downloads__hint">
        暂无已完成条目<br>完成的下载会记入「下载历史」，这里只在旧快照与刷新间隙里短暂出现
      </div>
    </template>

    <!--
      队列整体为空时的空态：老实现那两句逐字保留，**末尾补一句指路**（0.3.4 加）。
      为什么必须补：完成条目现在会被后端写进台账并**从队列摘掉**（设计文档 §3），
      于是「没有任何下载在进行」时这一页永远是空的 —— 不告诉用户「完成的在下载历史里」，
      新加的第七栏就等于藏起来了（真机验收时确认过：队列 0 条时整页只剩这三行）。
    -->
    <EmptyState v-else text="下载队列为空<br>在「任务」页挑好候选点「下载」，进度在这里看<br>完成的下载在「下载历史」栏，删了文件也还在" />
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

/* 对齐 `app.css` 的 `.secttl`：12px、弱化色、字距 .4px（与 `TasksView` 的小标题同一套口径） */
.avh-downloads__secttl {
  display: flex;
  align-items: baseline;
  gap: 10px;
  margin: 20px 0 8px;
  font-size: 12px;
  letter-spacing: 0.4px;
  color: rgba(var(--v-theme-on-surface), 0.5);
}

/* 小节标题右侧那句指路（契约 §5.3）：靠右、不参与标题的字距，免得挤成标题的一部分 */
.avh-downloads__secttl-note {
  margin-left: auto;
  letter-spacing: 0;
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

/* 完成行的片名（台账可选字段，见 `DoneRow` 注释）：比 `.hint` 稍亮一档，读起来像"一行记录" */
.avh-q__ttl {
  margin-top: 3px;
  font-size: 12.5px;
  line-height: 1.5;
  color: rgba(var(--v-theme-on-surface), 0.7);
}

/*
 * 完成行没有进度条，`.avh-q__hd` 那 8px 的"给进度条留的"下边距就变成了行尾的空档，收掉。
 */
.avh-q--done .avh-q__hd {
  margin-bottom: 0;
}

/* 对齐 `.qhd .right` */
.avh-q__right {
  margin-left: auto;
  text-align: right;
  white-space: nowrap;
}

/* 对齐 `.bar` / `.bar i`（老实现是 --acc2 → --acc 的渐变）
   只有「下载中」那一节画进度条：完成行是静态历史行，契约 §5.3 明确要去掉进度，
   所以老实现的 `.bar.done i` 换绿那条规则已随之下线（没有使用者了）。 */
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
</style>
