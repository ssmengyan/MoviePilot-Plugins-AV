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
 *   </div>
 *   <table><thead><tr>
 *     站点 | 规格 | 中字 | 破解 | 大小 | 做种 | 标记 | 匹配分 | (空)
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
 * 差异：老实现用 `data-dl` / `data-task` / `data-force` 属性 + `bindDownloadButtons()`
 * 事件委托，并在点击时把按钮 `disabled`；Vue 里改成 `download` 事件 + 组件内
 * 按站点记 in-flight（按钮转圈禁用），点击语义（含「仍要下载」的 `force`）不变。
 */
import { computed, ref } from 'vue'
import Thumb from './Thumb.vue'
import { scoreLevel } from './common'
import type { Candidate, SearchTask } from '../../composables/storeTypes'

const props = withDefaults(
  defineProps<{
    /** 任务体（含番号、封面、来源与候选）。 */
    task: SearchTask
    /** 本插件实例 id（传给 Thumb 拼图片代理）。 */
    pluginId?: string
  }>(),
  { pluginId: '' },
)

const emit = defineEmits<{
  /** 点「下载」/「仍要下载」：`force=true` 表示下载被规则淘汰的候选。 */
  (event: 'download', payload: { taskId: string; site: string; force: boolean }): void
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

defineExpose({ clearPending })
</script>

<template>
  <div class="avh-cand">
    <div class="avh-cand__head">
      <Thumb
        class="avh-cand__poster"
        variant="tposter"
        :src="task.thumb"
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
    </div>

    <table class="avh-cand__table">
      <thead>
        <tr>
          <th>站点</th>
          <th>规格</th>
          <th>中字</th>
          <th>破解</th>
          <th>大小</th>
          <th>做种</th>
          <th>标记</th>
          <th>匹配分</th>
          <th />
        </tr>
      </thead>
      <tbody>
        <template v-for="row in rows" :key="row.key">
          <!-- 行内没有用元素包一层（两个分支都是 <tr>），保证 tbody 里只有表格行 -->
          <tr v-if="row.kind === 'btnote'">
            <td colspan="9" class="avh-cand__hint avh-cand__btnote">
              — PT 没有合格候选，以下为 BT 磁力兜底 —
            </td>
          </tr>

          <template v-else>
            <tr :class="rowClass(row.cand)">
              <td>
                <span v-if="row.cand.src === 'BT'" class="avh-tag">BT</span>
                {{ row.cand.site || '' }}
              </td>
              <td>{{ row.cand.spec || '' }}</td>
              <td>
                <span class="avh-tag" :class="row.cand.cnsub ? 'avh-tag--on' : ''">
                  {{ row.cand.cnsub ? '有' : '无' }}
                </span>
              </td>
              <td>
                <span class="avh-tag" :class="row.cand.uncensored ? 'avh-tag--uc' : ''">
                  {{ row.cand.uncensored ? '破解' : '—' }}
                </span>
              </td>
              <td>{{ row.cand.size || '' }}</td>
              <td>{{ seedersText(row.cand) }}</td>
              <td>
                <span v-if="row.cand.free" class="avh-tag avh-tag--free">免费</span>
                <span v-if="row.cand.pref" class="avh-tag avh-tag--pref">优先站</span>
              </td>
              <td :title="row.cand.breakdown || ''">
                <span
                  class="avh-score"
                  :class="`avh-score--${scoreLevel(row.cand.score, isPass(row.cand))}`"
                >{{ scoreText(row.cand) }}</span>
              </td>
              <td>
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
              <td colspan="9">
                <div class="avh-cand__ttl" :title="titleOf(row.cand)">{{ titleOf(row.cand) }}</div>
              </td>
            </tr>
          </template>
        </template>

        <tr v-if="!cands.length">
          <td colspan="9" class="avh-cand__hint avh-cand__empty">没有搜到任何候选</td>
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

.avh-cand__table {
  width: 100%;
  border-collapse: collapse;
  font-size: 12.5px;
}

.avh-cand__table th {
  padding: 8px 10px;
  text-align: left;
  font-weight: 500;
  white-space: nowrap;
  color: rgba(var(--v-theme-on-surface), 0.5);
  border-bottom: 1px solid rgba(var(--v-theme-on-surface), 0.12);
}

.avh-cand__table td {
  padding: 9px 10px;
  vertical-align: middle;
  border-bottom: 1px solid rgba(var(--v-theme-on-surface), 0.08);
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
  padding: 0 10px 9px;
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
