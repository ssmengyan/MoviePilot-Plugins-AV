<script setup lang="ts">
/**
 * 候选种表格（列、顺序、文案、行样式全部照抄 `views/tasks.js` 的 `candTable(t, idx)`）。
 *
 * 老实现的 DOM：
 * ```
 * <div class="q" style="padding:0;overflow:hidden">
 *   <div class="thd">
 *     <div class="tposter" data-num>{封面}</div>
 *     <div><div class="tno">{番号}</div><div class="hint">来自订阅：{演员} · 搜到 n · 合格 m</div></div>
 *     <div style="flex:1"></div>
 *     [订阅为自动下载，但无候选合格]
 *     [待确认标记 chip「PT/BT 待确认」/「所有源均未找到」 ← 0.6.0 加]
 *     [📌 订阅该影片 ← 0.6.0 加，只有"没得挑"的卡片才画]
 *     [取消任务]
 *   </div>
 *   <table><colgroup>7 个 col</colgroup><thead><tr>
 *     站点 | 标记 | 规格 | 大小 | 做种 | 匹配分 | 操作
 *   </tr></thead><tbody>
 *     PT 行…（合格行绿底、淘汰行淡化、BT 行深底）
 *     [— PT 没有合格候选，以下为 BT 磁力兜底 —]
 *     BT 行…
 *     [没有搜到任何候选]
 *   </tbody></table>
 * </div>
 * ```
 * 行样式语义（`app.css`）：`tr.best` = 被规则选中的最佳候选、`tr.dead` = 被淘汰、
 * `tr.bt` = BT 兜底行；每行下面还有一条 `tr.candsub` 显示种子原名（`title`）。
 *
 * 与老实现的两处**有意为之**的排版差异（老实现的 9 列在真实数据下横向过宽，
 * 被卡片 `.avh-cand{overflow:hidden}` 裁掉右侧，「下载」按钮整个看不见）：
 *
 * 1. 老实现把「中字」「破解」各占一列，于是每一行都固定渲染「有/无」和「破解/—」，
 *    既占两列宽度又几乎全是无信息量的占位符。现在合并成第 2 列「标记」，**只画存在的
 *    标签**（顺序 `中字 → 破解 → 免费 → 优先站`，复用同一套 `.avh-tag*` 配色），
 *    四个都没有才画一个弱化的 `—`；「标记」列吃剩余宽度（`auto`），标签少也不会撑宽表格。
 * 2. 表格改用 `table-layout: fixed` + `<colgroup>` 显式列宽。固定布局下浏览器只按列宽
 *    分配，不会让长内容（规格串、站点名）把表格撑过容器，因此宽度严格等于容器宽度、
 *    最后一列「操作」永远不会被挤出卡片右侧；代价是内容不再撑列，`th`/`td` 必须自带
 *    `overflow:hidden` + `text-overflow:ellipsis`（标题行 `.avh-cand__ttl` 同理）。
 *
 * 行为差异：老实现用 `data-dl` / `data-task` / `data-force` 属性 + `bindDownloadButtons()`
 * 事件委托，并在点击时把按钮 `disabled`；Vue 里改成 `download` 事件 + 组件内
 * 按站点记 in-flight（按钮转圈禁用），点击语义（含「仍要下载」的 `force`）不变。
 */
import { computed, ref } from 'vue'
import Thumb from './Thumb.vue'
import { filledThumbs, scoreLevel } from './common'
import type { Candidate, SearchTask } from '../../composables/storeTypes'

const props = withDefaults(
  defineProps<{
    /** 任务体（含番号、封面、来源与候选）。 */
    task: SearchTask
    /** 本插件实例 id（传给 Thumb 拼图片代理）。 */
    pluginId?: string
    /** 是否画「取消任务」（只有任务页那颗；站点搜索页不画）。 */
    cancelable?: boolean
    /**
     * 「📌 订阅该影片」按钮的状态（0.6.0 加）：
     * `hidden` = 不画（这张卡片有得挑，不需要订阅等资源）、`ready` = 可点、`done` = 已订阅（禁用）。
     */
    subscribeState?: 'hidden' | 'ready' | 'done'
  }>(),
  { pluginId: '', cancelable: false, subscribeState: 'hidden' },
)

const emit = defineEmits<{
  /** 点「下载」/「仍要下载」：`force=true` 表示下载被规则淘汰的候选。 */
  (event: 'download', payload: { taskId: string; site: string; force: boolean }): void
  /** 点「取消任务」：把这条待确认任务从任务页与角标里去掉。 */
  (event: 'cancel', payload: { taskId: string }): void
  /** 点「📌 订阅该影片」：由任务页去建一条番号订阅（组件自己不碰 store）。 */
  (event: 'subscribe', payload: { taskId: string }): void
}>()

/**
 * 渲染行：候选行，或 BT 兜底说明行。
 *
 * `btnote` 行也带一个空 `cand`，只为让模板里两个分支引用同一个字段（说明行不读它），
 * 免得在模板里到处写空值判断。
 */
interface Row {
  kind: 'cand' | 'btnote'
  key: string
  cand: Candidate
}

/** 正在提交的站点：老实现只禁用被点的那个按钮，这里按"任务+站点"记，别锁整表。 */
const pending = ref<Record<string, boolean>>({})

const cands = computed<Candidate[]>(() => (Array.isArray(props.task.cands) ? props.task.cands : []))
const passedCount = computed(() => cands.value.filter(item => item.pass !== false).length)
const taskId = computed(() => String(props.task.id ?? ''))

/**
 * PT 候选 → [BT 兜底说明行] → BT 候选（老实现 `pt.map(...) + btNote + bt.map(...)` 的同一顺序）。
 * 说明行只在真有 BT 候选时出现。
 */
const rows = computed<Row[]>(() => {
  const pt = cands.value.filter(item => item.src !== 'BT')
  const bt = cands.value.filter(item => item.src === 'BT')
  const out: Row[] = pt.map((cand, index) => ({ kind: 'cand', key: `pt-${index}`, cand }))
  if (bt.length) {
    out.push({ kind: 'btnote', key: 'bt-note', cand: {} })
    bt.forEach((cand, index) => out.push({ kind: 'cand', key: `bt-${index}`, cand }))
  }
  return out
})

/** `来自订阅：演员` / `手动搜索 · 演员：演员`（老实现 `origin` 的逐字文案）。 */
const origin = computed(() => {
  const actor = props.task.actor ? String(props.task.actor) : ''
  if (props.task.source === 'sub') return `来自订阅${actor ? `：${actor}` : ''}`
  return `手动搜索${actor ? ` · 演员：${actor}` : ''}`
})

function isPass(cand: Candidate): boolean {
  return cand.pass !== false
}

/**
 * 「标记」列的标签（列合并后由 `中字`/`破解`/`免费`/`优先站` 四类拼成）。
 *
 * 顺序固定：中字 → 破解 → 免费 → 优先站。**只返回存在的标签**：老实现「中字」列
 * 每行都画「有/无」、「破解」列每行都画「破解/—」，两个占位符吃掉两列宽度却没有信息量。
 * 四个都没有时返回空数组，由模板画一个弱化的 `—`（沿用 `.avh-cand__hint` 的观感）。
 */
function marks(cand: Candidate): Array<{ text: string; cls: string }> {
  const out: Array<{ text: string; cls: string }> = []
  if (cand.cnsub) out.push({ text: '中字', cls: 'avh-tag--on' })
  if (cand.uncensored) out.push({ text: '破解', cls: 'avh-tag--uc' })
  if (cand.free) out.push({ text: '免费', cls: 'avh-tag--free' })
  if (cand.pref) out.push({ text: '优先站', cls: 'avh-tag--pref' })
  return out
}

/** 行 class：`best`/`dead`/`bt` + 有原名时加 `has-sub`（老实现 `rowOf` 的同一套拼法）。 */
function rowClass(cand: Candidate): string[] {
  return [
    cand.picked ? 'best' : '',
    isPass(cand) ? '' : 'dead',
    cand.src === 'BT' ? 'bt' : '',
    titleOf(cand) ? 'has-sub' : '',
  ].filter(Boolean)
}

function titleOf(cand: Candidate): string {
  return String(cand.title || '').trim()
}

/** 做种数：BT 兜底行显示「未知」，PT 行 null/undefined 显示 `—`（老实现逐字）。 */
function seedersText(cand: Candidate): string {
  if (cand.src === 'BT') return '未知'
  return String(cand.seeders === null || cand.seeders === undefined ? '—' : cand.seeders)
}

/** 匹配分：淘汰行显示「淘汰」，其余 `—` 表示后端没给分。 */
function scoreText(cand: Candidate): string {
  if (!isPass(cand)) return '淘汰'
  return String(cand.score === null || cand.score === undefined ? '—' : cand.score)
}

function siteKey(cand: Candidate): string {
  return `${taskId.value}|${String(cand.site || '')}`
}

function onDownload(cand: Candidate): void {
  const key = siteKey(cand)
  if (pending.value[key]) return
  pending.value = { ...pending.value, [key]: true }
  emit('download', { taskId: taskId.value, site: String(cand.site || ''), force: !isPass(cand) })
}

/** 「取消任务」在飞（老实现只把按钮置灰，见 `cancelTask` 里的 `btn.disabled = true`）。 */
const canceling = ref(false)

/** 点「取消任务」：老 `data-cancel` 那颗按钮（文案与 title 逐字一致）。 */
function onCancel(): void {
  if (canceling.value || !taskId.value) return
  canceling.value = true
  emit('cancel', { taskId: taskId.value })
}

/** 解除「取消任务」的进行中态（成功或失败都要调，否则按钮永远转圈）。 */
function clearCanceling(): void {
  canceling.value = false
}

/**
 * 任务卡上的待确认标记（0.6.0 加）—— 取值口径与后端 `tasks.rule_verdict()` 的
 * `pending` 一一对应，前端不自己推断（`''` = 有候选可挑，不画标记）：
 * `pt-only` = PT 没搜到且 BT 兜底关着；`none` = PT 与 BT 都没有可用资源。
 */
const pendingMark = computed<{ text: string; color: string; hint: string } | null>(() => {
  const kind = String(props.task.pending || '')
  if (kind === 'pt-only') {
    return { text: 'PT/BT 待确认', color: 'info', hint: 'PT 没搜到，BT 兜底已关闭' }
  }
  if (kind === 'none') {
    return { text: '所有源均未找到', color: 'warning', hint: 'PT 与 BT 都没有可用资源' }
  }
  return null
})

/** 「📌 订阅该影片」在飞：与取消任务同一套"自己置灰、动作结束后由父组件解锁"。 */
const subscribing = ref(false)

function onSubscribe(): void {
  if (subscribing.value || !taskId.value) return
  subscribing.value = true
  emit('subscribe', { taskId: taskId.value })
}

/** 解除「订阅该影片」的进行中态（成功失败都要调）。 */
function clearSubscribing(): void {
  subscribing.value = false
}

/**
 * 解除按钮的进行中态（成功或失败都要调，否则按钮永远转圈）。
 * 不传 `site` 表示整表解锁（常用于「刷新任务」之后）。
 */
function clearPending(site?: string): void {
  const next = { ...pending.value }
  if (site === undefined) {
    Object.keys(next).forEach(key => delete next[key])
  } else {
    Object.keys(next).forEach(key => {
      if (key === `${taskId.value}|${site}`) delete next[key]
    })
  }
  pending.value = next
}

defineExpose({ clearPending, clearCanceling, clearSubscribing })

/**
 * 封面地址：任务自带优先，其次用 `queueThumb` 后台补回来的那张。
 *
 * 老实现是 `applyThumb()` 直接把结果回写进 `S.task.siteTask` 再重绘；
 * 这里改成读共享的 `filledThumbs`，所以**任何**用 CandTable 的视图
 * （站点搜索、任务页）都能拿到补图，不必各自回写。
 */
const poster = computed(() => {
  const own = String(props.task?.thumb || '')
  if (own) return own
  return String(filledThumbs.value[String(props.task?.number || '')] || '')
})
</script>

<template>
  <div class="avh-cand">
    <div class="avh-cand__head">
      <Thumb
        class="avh-cand__poster"
        variant="tposter"
        :src="poster"
        alt="无图"
        :plugin-id="pluginId"
      />
      <div>
        <div class="avh-cand__no">{{ task.number || '' }}</div>
        <div class="avh-cand__hint avh-cand__origin">
          {{ origin }} · 搜到 {{ cands.length }} · 合格 {{ passedCount }}
        </div>
      </div>
      <div class="avh-cand__spacer" />
      <span v-if="task.auto && task.source === 'sub'" class="avh-cand__hint">
        订阅为自动下载，但无候选合格
      </span>
      <!-- 待确认标记：PT 没中且兜底关着 → 「PT/BT 待确认」；PT 与 BT 都没有 → 「所有源均未找到」 -->
      <template v-if="pendingMark">
        <v-chip
          class="avh-cand__mark"
          :color="pendingMark.color"
          variant="tonal"
          size="small"
          label
        >{{ pendingMark.text }}</v-chip>
        <span class="avh-cand__hint">{{ pendingMark.hint }}</span>
      </template>
      <!-- 「📌 订阅该影片」：只在"这张卡片没得挑"时由任务页传 ready/done 才画。
           类名别用 `avh-cand__sub` —— 那是种子原名行的既有类名（行样式已占用）。 -->
      <v-btn
        v-if="subscribeState !== 'hidden'"
        class="avh-cand__subscribe"
        variant="outlined"
        size="small"
        :disabled="subscribeState === 'done'"
        :loading="subscribing"
        title="等这部片有资源时自动下载（订阅检查会盯它）"
        @click="onSubscribe"
      >{{ subscribeState === 'done' ? '已订阅' : '📌 订阅该影片' }}</v-btn>
      <!-- 老 `data-cancel` 那颗 .danger 按钮：只有任务页传 cancelable 才画 -->
      <v-btn
        v-if="cancelable"
        class="avh-cand__cancel"
        variant="outlined"
        size="small"
        color="error"
        :loading="canceling"
        title="不再等这部片：从待确认里移除（想找回就重新搜一次）"
        @click="onCancel"
      >取消任务</v-btn>
    </div>

    <table class="avh-cand__table">
      <!--
        固定表格布局的显式列宽（`table-layout: fixed` 下只认这里的第一行/col 宽度）。
        「标记」列留 `auto` 吸收剩余宽度；「操作」列给足 92px（下限 84px）保证
        「仍要下载」这颗四字按钮 + 左右 8px 内边距放得下、永不被挤出卡片右边界。
      -->
      <colgroup>
        <col class="avh-cand__col-site" />
        <col class="avh-cand__col-mark" />
        <col class="avh-cand__col-spec" />
        <col class="avh-cand__col-size" />
        <col class="avh-cand__col-seed" />
        <col class="avh-cand__col-score" />
        <col class="avh-cand__col-act" />
      </colgroup>
      <thead>
        <tr>
          <th>站点</th>
          <th>标记</th>
          <th>规格</th>
          <th>大小</th>
          <th>做种</th>
          <th>匹配分</th>
          <th class="avh-cand__act">操作</th>
        </tr>
      </thead>
      <tbody>
        <template v-for="row in rows" :key="row.key">
          <!-- 行内没有用元素包一层（两个分支都是 <tr>），保证 tbody 里只有表格行 -->
          <tr v-if="row.kind === 'btnote'">
            <td colspan="7" class="avh-cand__hint avh-cand__btnote">
              — PT 没有合格候选，以下为 BT 磁力兜底 —
            </td>
          </tr>

          <template v-else>
            <tr :class="rowClass(row.cand)">
              <td>
                <span v-if="row.cand.src === 'BT'" class="avh-tag">BT</span>
                {{ row.cand.site || '' }}
              </td>
              <!-- 「标记」：只画存在的标签，顺序 中字 → 破解 → 免费 → 优先站；全无则弱化 — -->
              <td class="avh-cand__marks">
                <template v-if="marks(row.cand).length">
                  <span
                    v-for="mark in marks(row.cand)"
                    :key="mark.text"
                    class="avh-tag"
                    :class="mark.cls"
                  >{{ mark.text }}</span>
                </template>
                <span v-else class="avh-cand__hint">—</span>
              </td>
              <!-- 「规格」不再是信息大户：保留原文，`title` 兜全文，视觉弱化 + 省略号截断 -->
              <td class="avh-cand__spec" :title="row.cand.spec || ''">{{ row.cand.spec || '' }}</td>
              <td>{{ row.cand.size || '' }}</td>
              <td>{{ seedersText(row.cand) }}</td>
              <td :title="row.cand.breakdown || ''">
                <span
                  class="avh-score"
                  :class="`avh-score--${scoreLevel(row.cand.score, isPass(row.cand))}`"
                >{{ scoreText(row.cand) }}</span>
              </td>
              <td class="avh-cand__act">
                <v-btn
                  v-if="isPass(row.cand)"
                  class="avh-cand__dl"
                  variant="outlined"
                  size="small"
                  :loading="!!pending[siteKey(row.cand)]"
                  @click="onDownload(row.cand)"
                >下载</v-btn>
                <v-btn
                  v-else
                  class="avh-cand__dl"
                  variant="outlined"
                  size="small"
                  :title="row.cand.breakdown || ''"
                  :loading="!!pending[siteKey(row.cand)]"
                  @click="onDownload(row.cand)"
                >仍要下载</v-btn>
              </td>
            </tr>
            <tr v-if="titleOf(row.cand)" :class="['avh-cand__sub', ...rowClass(row.cand)]">
              <td colspan="7">
                <div class="avh-cand__ttl" :title="titleOf(row.cand)">{{ titleOf(row.cand) }}</div>
              </td>
            </tr>
          </template>
        </template>

        <tr v-if="!cands.length">
          <td colspan="7" class="avh-cand__hint avh-cand__empty">没有搜到任何候选</td>
        </tr>
      </tbody>
    </table>
  </div>
</template>

<style scoped>
/* 对齐老 `.q`（调用方内联 `padding:0;overflow:hidden`） */
.avh-cand {
  overflow: hidden;
  margin-bottom: 10px;
  border: 1px solid rgba(var(--v-theme-on-surface), 0.12);
  border-radius: 10px;
  background: rgb(var(--v-theme-surface));
}

.avh-cand__head {
  display: flex;
  align-items: center;
  gap: 12px;
  flex-wrap: wrap;
  padding: 12px 14px;
  border-bottom: 1px solid rgba(var(--v-theme-on-surface), 0.12);
}

/* `.tposter`：48×64 小封面 */
.avh-cand__poster {
  width: 48px;
  height: 64px;
  flex: none;
  border-radius: 6px;
  border: 1px solid rgba(var(--v-theme-on-surface), 0.12);
}

.avh-cand__no {
  font-size: 15px;
  font-weight: 700;
  letter-spacing: 0.2px;
}

.avh-cand__hint {
  font-size: 12px;
  color: rgba(var(--v-theme-on-surface), 0.5);
}

.avh-cand__origin {
  margin-top: 3px;
}

.avh-cand__spacer {
  flex: 1;
}

/*
 * `table-layout: fixed`：列宽只认 `<colgroup>`（表格第一条 col / 首行 th），
 * 长内容（规格串、站点名、种子原名）不再参与列宽计算，所以表格宽度**严格等于容器宽度**，
 * 卡片 `.avh-cand{overflow:hidden}` 不会再裁掉右半张表——这是本次要修的真实缺陷。
 * 代价：所有单元格必须自己 `overflow:hidden` + 省略号，否则内容会溢到相邻列上。
 */
.avh-cand__table {
  table-layout: fixed;
  width: 100%;
  border-collapse: collapse;
  font-size: 12.5px;
}

/* 列宽：**七列全部给显式宽度**，不留"弹性列"。
   `table-layout: fixed` 下，表格宽度（100%）大于各列宽度之和时，多出来的空间由浏览器
   **按列宽比例摊到每一列上**（CSS 2.1 §17.5.2.1，Chrome/Firefox 实测一致）。
   所以宽屏下七列会均衡变宽（老实现那种"铺满一整行"的观感），而列宽之比仍由下面这组
   基准值决定；窄屏时反向等比收缩，且因为布局是 fixed，**永远不会把「操作」列挤出卡片**。
   （曾经把「标记」列写成 `auto`：宽屏下它一个人吃掉 632px，中间空出一大片，
   改为全列显式后同一行里最宽的一列是 287px。） */
.avh-cand__col-site {
  width: 96px;
}

.avh-cand__col-mark {
  width: 180px;
}

.avh-cand__col-spec {
  width: 120px;
}

.avh-cand__col-size {
  width: 88px;
}

.avh-cand__col-seed {
  width: 72px;
}

.avh-cand__col-score {
  width: 80px;
}

.avh-cand__col-act {
  width: 92px;
}

/* 单元格截断：fixed 布局下不给省略号就会溢到邻列 */
.avh-cand__table th,
.avh-cand__table td {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.avh-cand__table th {
  padding: 8px;
  text-align: left;
  font-weight: 500;
  color: rgba(var(--v-theme-on-surface), 0.5);
  border-bottom: 1px solid rgba(var(--v-theme-on-surface), 0.12);
}

.avh-cand__table td {
  /* 定高（约一行文字 + 上下 9px）配合上面的 overflow:hidden，给行高一个上限，
     内容按单行省略号处理而不是把行撑高 */
  height: 38px;
  padding: 9px 8px;
  vertical-align: middle;
  border-bottom: 1px solid rgba(var(--v-theme-on-surface), 0.08);
}

/* 「操作」列：右对齐 + 按钮不换行，保证按钮完整贴右边界显示 */
.avh-cand__table th.avh-cand__act,
.avh-cand__table td.avh-cand__act {
  text-align: right;
}

.avh-cand__table td.avh-cand__act {
  white-space: nowrap;
}

/* 「标记」列：标签排列不换行（宽度靠 auto 列吸收，标签少也不会撑宽表格） */
.avh-cand__marks {
  white-space: nowrap;
}

/* 「规格」列：信息密度低，视觉弱化一档，长串走省略号（全文看 `title`） */
.avh-cand__spec {
  color: rgba(var(--v-theme-on-surface), 0.5);
}

/* 行语义：best 绿底、dead 淡化、bt 深一档（老 `tr.best/tr.dead/tr.bt`） */
.avh-cand__table tr.best td {
  background: rgba(var(--v-theme-success), 0.14);
}

.avh-cand__table tr.dead td {
  opacity: 0.42;
}

.avh-cand__table tr.bt td {
  background: rgba(var(--v-theme-on-surface), 0.05);
}

.avh-cand__table tr.has-sub td {
  border-bottom: 0;
}

.avh-cand__sub td {
  /* 种子原名整行横跨 7 列：左右内边距与数据单元格统一取 8px（本次从 10px 收紧） */
  padding: 0 8px 9px;
}

.avh-cand__ttl {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  font-size: 11.5px;
  color: rgba(var(--v-theme-on-surface), 0.5);
}

.avh-cand__btnote {
  padding: 6px 10px;
}

.avh-cand__empty {
  padding: 10px;
}

/* `.tag` 系列（老 `app.css` 同名规则；底色走主题语义色） */
.avh-tag {
  display: inline-block;
  margin-right: 4px;
  padding: 1px 6px;
  font-size: 10.5px;
  border-radius: 4px;
  border: 1px solid rgba(var(--v-theme-on-surface), 0.16);
  color: rgba(var(--v-theme-on-surface), 0.5);
}

.avh-tag--on {
  border-color: rgba(var(--v-theme-success), 0.45);
  background: rgba(var(--v-theme-success), 0.18);
  color: rgb(var(--v-theme-on-surface));
}

.avh-tag--uc {
  border-color: rgba(var(--v-theme-secondary), 0.5);
  background: rgba(var(--v-theme-secondary), 0.2);
  color: rgb(var(--v-theme-on-surface));
}

.avh-tag--free {
  border-color: rgba(var(--v-theme-warning), 0.5);
  background: rgba(var(--v-theme-warning), 0.18);
  color: rgb(var(--v-theme-on-surface));
}

.avh-tag--pref {
  border-color: rgba(var(--v-theme-primary), 0.5);
  background: rgba(var(--v-theme-primary), 0.22);
  color: rgb(var(--v-theme-on-surface));
}

/* `.score` 档位色（hi=成功、mid=警告、lo=中性） */
.avh-score {
  font-weight: 700;
  font-variant-numeric: tabular-nums;
}

.avh-score--hi {
  color: rgb(var(--v-theme-success));
}

.avh-score--mid {
  color: rgb(var(--v-theme-warning));
}

.avh-score--lo {
  color: rgba(var(--v-theme-on-surface), 0.5);
}

.avh-cand__dl {
  white-space: nowrap;
}
</style>
