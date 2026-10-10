<script setup lang="ts">
/**
 * 视图：订阅（S6 第四个原生化视图）。
 *
 * 对照老实现 `ui/views/subs.js`（`renderSubs` / `ruleSummary` / `unsub` / `runCheck` /
 * `openRuleDialog` / `subscribeNumber`）与它的调用方 `ui/app.js`（`bindUi` 的 nav 分支、
 * `renderPills`），逐条对齐的是**行为与文案**，DOM 换成 Vuetify 组件：
 *
 * | 老实现 | 这里 |
 * | --- | --- |
 * | 工具条 `<span class="hint">默认规则：{ruleSummary(S.rule)}</span>` + 右侧 `⚙ 默认规则`、`⚡ 检查一次` | 同一句话 + 同一个「检查一次」(`⚡` 由 `mdi-lightning-bolt` 画，文字不变) |
 * | `⚙ 默认规则` → `openRuleDialog()`：**弹出完整规则编辑器**（`ruleFieldsHtml` / `bindRuleFields` / `collectRule`）→ `POST /rule` | **不做编辑器**：规则唯一归属是设置台「下载规则」栏（`RulePanel.vue`）。本视图只读回显 + 一个「去设置台改规则」按钮 → 先 `toast` 说明去处，再 `emit('switch')`（写法照 S6-1 站点搜索的「改范围」） |
 * | 列表 `S.subs.map(...)`：`.q > .top`，左列 `👤/🎞 + name`、`hint` 行 `ruleSummary(s.rule)`、`hint` 行 `命中 n 次 · 上次检查 {shortTime(last)}`；右列 `检查` / `取消` | 同一结构、同一顺序、同一文案；图标 `mdi-account` / `mdi-movie-open`（老实现是 emoji），**行内规则摘要照旧逐字用 `ruleSummary(s.rule)`** |
 * | `last = s.last || s.created || ''`，空 → `—`（`shortTime` 自身也把空串映射成 `—`） | 同（`lastText`） |
 * | 空态 `emptyHtml('还没有订阅')` | `EmptyState`，文案逐字一致 |
 * | `data-unsub` 点击 → `unsub(id, btn)`：**无确认，直接删**；`id` 为空 → `toast('取消失败','这条订阅缺少 id，无法删除','warn')` | 先过宿主确认（`useHostConfirm`，与设置台「清空通知」「清理缓存」同一道闸）再删；**id 缺失分支与文案原样保留**。这是本视图**刻意的一处交互变化**，理由见文件末尾 |
 * | 删除成功 `toast('已取消订阅', 'id=' + id, 'warn')` + 就地过滤 `S.subs` | `t.warning('已取消订阅')` + `t.info('id={id} · {订阅名}')`；就地移除由 `store.unsubscribe` 负责 |
 * | 删除失败 `toast('取消订阅失败', r.message || '请稍后重试', 'warn')` | 同文案的 `t.warning(res.message || '取消订阅失败，请稍后重试')` |
 * | `runCheck(name)`：先 `toast('订阅检查', name ? '正在检查 ' + name : '正在检查全部订阅…')`，**再**发请求 | 同一个顺序：先 `t.info(...)` 再 `await store.runCheck(name)` |
 * | `d.limited` 时 `toast('检查被限流', d.message \|\| '距上次检查不足间隔，已跳过', 'warn')` | `res.kind === 'limited'` 走 `t.warning`（**限流是业务结果不是失败**，`res.ok` 仍为 `true`）；文案取 `res.message`，空则同一条兜底句 |
 * | 非限流 `toast('检查完成', d.message \|\| (通知条数 + ' 条新通知'), 'ok')` | `t.success('检查完成')` + `t.info(res.message)`（后端 `已检查 n 条订阅` / `没有可检查的订阅`，store 已兜底过） |
 * | 失败 `toast('检查失败', r.message \|\| '请稍后重试', 'warn')` | `t.warning('检查失败：{原因}')`（写法照 S6-2/S6-3 对同一条 toast 的处理） |
 * | 检查完成后 `renderPills()` + `loadSubs(true)` + `loadTasks(true)` + `paintNotify()` | `store.runCheck` 已同步 `subs/tasks/queue/notices`（角标是 store 派生值），列表随响应式更新 → 不需要手动重绘 |
 * | `bindUi` 切到订阅栏 → `loadSubs(false)`（静默，`GET /subs`） | **不做**：订阅数据本来就由壳的 `/bootstrap` 15 秒轮询维护，`store` 已有同一份；老实现那次 `loadSubs` 属于"每个视图自己拉一遍"的旧架构 |
 * | `subscribeNumber(num)`：`POST /subs` 后 `renderPills()` + `toast('订阅已创建','番号 n','ok')` + 切到本页 | 本视图**不做**入口（老实现的调用点在详情抽屉/演员页）：`store.subscribeNumber` 已备好，等那些视图迁移时接 |
 *
 * 刻意**不做**（老实现也没有，别顺手加）：
 * - 不加 5 秒轮询：老订阅页没有任何轮询（订阅状态只在检查后变化，次数也受限流约束）；
 * - 不画 `s.rule` 的完整字段表：老实现只在行内显示一行 `ruleSummary`，这里逐字沿用；
 * - 不做规则编辑器（见上表第二行）：订阅的 `rule` 由后端在创建时用全局规则合并生成，
 *   老实现的「默认规则」弹窗改的也是**全局**规则 → 与设置台「下载规则」栏是同一个东西，
 *   两处都做就是两套编辑器抢一份状态。
 *
 * 与老实现的行为差异（刻意，只有这一条）：**「取消」多了一道确认框**。
 * 老实现点一下就删、错了不可恢复（订阅要重建还得回到演员页/详情页重订）。本视图每次删除前
 * 用宿主 `moviepilot:confirm` 拦一道（拿不到注入时 `useHostConfirm` 会降级 `window.confirm`），
 * 文案与本视图其余提示同风格。想回到"点一下即删"只删 `onUnsubscribe` 里的 `confirm` 那几行即可。
 */
import { computed, ref } from 'vue'
import EmptyState from '../common/EmptyState.vue'
import { hostToast, type PluginApi } from '../../composables/usePluginApi'
import { useHostConfirm } from '../../composables/useHostDialogs'
import type { PluginStore } from '../../composables/usePluginStore'
import { shortTime, toRule, type RuleValue, type Subscription } from '../../composables/storeTypes'

const props = withDefaults(
  defineProps<{
    /** 数据台单一数据源（`Console.vue` 建好后传进来）。 */
    store: PluginStore
    /** 本插件实例 id（本视图不画图，保留是为了与其余原生视图同一组 props）。 */
    pluginId?: string
    /** 宿主请求器（本视图不直接发请求，动作全走 store；保留同一组 props）。 */
    api?: PluginApi | null
    /** 宿主 toast（`moviepilot:toast` 注入），拿不到时静默降级。 */
    toast?: unknown
  }>(),
  { pluginId: '', api: null, toast: null },
)

const emit = defineEmits<{
  /** 用户点「去设置台改规则」：请壳把弹窗切到设置台（宿主合同里的 switch）。 */
  (event: 'switch'): void
  /** 检查完成：请壳刷新右栏「运行概况」（限流窗口/检查次数只有它读得到）。 */
  (event: 'refreshSide'): void
}>()

const t = hostToast(props.toast as any)
const confirm = useHostConfirm()

/** 正在检查的订阅名；`''` = 没有在检查。用来给对应那一行的按钮转圈。 */
const checking = ref('')
/** 全部订阅检查的哨兵值（老实现 `runCheck('')` 表示检查全部）。 */
const ALL = ''

/** 列表：老实现直接 `S.subs.map(...)`，不过滤、不排序、不分组。 */
const subs = computed<Subscription[]>(() =>
  Array.isArray(props.store.subs.value) ? props.store.subs.value : [],
)

/** 空数组也**不画一行**（老实现 `.length ? … : 空态`，两者是互斥的）。 */
const hasSubs = computed(() => subs.value.length > 0)

/** 工具条那行默认规则（老 `ruleSummary(S.rule)`；store 的 `rule` 已按后端默认值归一）。 */
const defaultSummary = computed(() => ruleSummary(props.store.rule.value))

/**
 * 老实现 `ruleSummary(r)`：拼一串 `1080p 优先 · 必须中字 · 破解优先 · 4K 择优 · 做种≥3 ·
 * BT 兜底 · 命中自动/仅通知 · 限 n 站`。**逐字照抄**，连分隔符与缺省值都不改
 * （`res` 缺省 `1080p`、`minSeeders` 缺省 0、`trigger === 'auto'` 才算自动下载）。
 */
function ruleSummary(raw: RuleValue | null | undefined): string {
  const r = raw || {}
  return (
    `${r.res || '1080p'} 优先` +
    (r.mustCnsub ? ' · 必须中字' : '') +
    (r.preferUncensored ? ' · 破解优先' : '') +
    (r.allow4k ? ' · 4K 择优' : '') +
    ` · 做种≥${r.minSeeders || 0}` +
    (r.btFallback ? ' · BT 兜底' : '') +
    ` · ${r.trigger === 'auto' ? '命中自动下载' : '命中仅通知'}` +
    ((r.sites || []).length ? ` · 限 ${(r.sites || []).length} 站` : '')
  )
}

/** 每条订阅的规则副本（缺省按 `storeTypes` 的后端镜像补齐，与 `ruleSummary` 的兜底一致）。 */
function subRule(sub: Subscription): RuleValue {
  return toRule(sub.rule)
}

/** 老实现 `s.last || s.created || ''` → `shortTime`；全空时 `shortTime('')` 自己给 `—`。 */
function lastText(sub: Subscription): string {
  const raw = String(sub.last || sub.created || '')
  return raw ? shortTime(raw) : '—'
}

/** 命中次数：老实现 `(s.hits || 0)`（0 也照画，不省略）。 */
function hitsText(sub: Subscription): number {
  return Number(sub.hits) || 0
}

/** 类型图标：老实现 `s.type === 'actor' ? '👤' : '🎞'`（**只有 `actor` 算演员**）。 */
function typeIcon(sub: Subscription): string {
  return sub.type === 'actor' ? 'mdi-account' : 'mdi-movie-open'
}

/** 行 key：老实现没有 key 概念；这里优先唯一 id，其次 `类型:名字`。 */
function rowKey(sub: Subscription, index: number): string {
  return String(sub.id ?? `${sub.type || ''}:${sub.name || ''}#${index}`)
}

/** 用来提示/确认的订阅名（缺名字时退回 id，别显示 `undefined`）。 */
function labelOf(sub: Subscription): string {
  return String(sub.name || sub.id || '')
}

// ---------- 只读规则回显（老 `ruleFieldsHtml` 的**字段清单**，不是控件） ----------

/** 老 `ruleFieldsHtml` 里的分辨率 tab 文案（`res` → 中文），未知值原样显示。 */
const RES_LABELS: Record<string, string> = {
  '1080p': '1080P 优先',
  '2160p': '4K 优先',
  only4k: '仅 4K',
}

/** 分辨率策略：老实现三个 tab 的选中态，这里退化成一行只读文案。 */
const resText = computed(() => {
  const value = String(props.store.rule.value.res || '1080p')
  return RES_LABELS[value] || value
})

/**
 * 只读回显的其余项：名称与设置台「下载规则」栏（`RulePanel.vue`）的标签对齐，
 * 取值口径与 `ruleSummary` 完全一致（布尔项用 ✓ / ✗，数字项带单位）。
 * 老弹窗里还有 `savePath` / `downloader` / `category` / `minIntervalMin`，那是编辑项；
 * 本栏是"规则长什么样"的说明牌，只列老 `ruleSummary` 覆盖的那一串 + 每日上限。
 */
const ruleRows = computed<Array<{ label: string; text: string; on: boolean }>>(() => {
  const r = props.store.rule.value
  return [
    { label: '必须中文字幕', text: r.mustCnsub ? '开' : '关', on: !!r.mustCnsub },
    { label: '破解 / 无码版优先', text: r.preferUncensored ? '开' : '关', on: !!r.preferUncensored },
    { label: '允许 4K 择优', text: r.allow4k ? '开' : '关', on: !!r.allow4k },
    { label: '做种数下限', text: `${r.minSeeders || 0} 个`, on: false },
    { label: 'PT 搜不到时允许 BT 磁力兜底', text: r.btFallback ? '开' : '关', on: !!r.btFallback },
    {
      label: '命中后自动下载',
      text: r.trigger === 'auto' ? '自动下载' : '仅通知',
      on: r.trigger === 'auto',
    },
    { label: '每日检查上限', text: `${r.maxPerDay || 6} 次`, on: false },
    {
      label: '搜索站点范围',
      text: (r.sites || []).length ? `限 ${(r.sites || []).length} 站` : '全部站点',
      on: false,
    },
  ]
})

// ---------- 动作 ----------

/** 有请求在飞时，两个入口按钮与所有行内按钮一起禁用（老实现各自 `btn.disabled`）。 */
const checkBusy = computed(() => checking.value !== '')

/**
 * 「检查一次」/ 行内「检查」：老 `runCheck(name)`。
 *
 * 顺序照老实现：**先**提示正在检查，**再**发请求；限流（`kind === 'limited'`）走警告级提示、
 * 不算失败（`res.ok` 仍为 `true`）。
 */
async function runCheck(name: string): Promise<void> {
  if (checkBusy.value) return
  checking.value = name || ALL
  t.info(name ? `正在检查 ${name}` : '正在检查全部订阅…')
  try {
    const res = await props.store.runCheck(name)
    if (!res.ok) {
      t.warning(`检查失败：${res.message || '请稍后重试'}`)
      return
    }
    if (res.kind === 'limited') {
      t.warning(res.message || '距上次检查不足间隔，已跳过')
    } else {
      t.success('检查完成')
      t.info(res.message || '检查完成')
    }
    emit('refreshSide')
  } finally {
    checking.value = ''
  }
}

/**
 * 行内「取消」：老 `unsub(id, btn)`。
 *
 * 差异（刻意，见文件头）：删除前多一道宿主确认；其余分支（缺 id 的提示、失败提示、
 * 成功后的就地移除）与老实现一致。
 */
async function onUnsubscribe(sub: Subscription): Promise<void> {
  const id = String(sub.id ?? '')
  if (!id) {
    t.warning('取消失败')
    t.info('这条订阅缺少 id，无法删除')
    return
  }
  const name = labelOf(sub)
  const ok = await confirm({
    type: 'warn',
    title: '取消订阅',
    content: `将取消订阅「${name}」，之后的订阅检查不再包含它。此操作不可恢复，需要时得重新订阅。确认继续？`,
    confirmText: '取消订阅',
    cancelText: '先留着',
  })
  if (!ok) return
  const res = await props.store.unsubscribe(id)
  if (!res.ok) {
    t.warning(res.message || '取消订阅失败，请稍后重试')
    return
  }
  // 老实现 `toast('已取消订阅', 'id=' + id, 'warn')`：正文同样带 id（真机是数字，便于对日志）。
  t.warning('已取消订阅')
  t.info(`id=${id}${name && name !== id ? ` · ${name}` : ''}`)
  emit('refreshSide')
}

/** 「去设置台改规则」：本视图不做编辑器，改规则只有设置台「下载规则」一栏（先说明去处再跳）。 */
function goRuleSettings(): void {
  t.info('规则在「设置台 → 下载规则」里改')
  emit('switch')
}
</script>

<template>
  <div class="avh-subs">
    <div class="avh-subs__toolbar">
      <span class="avh-subs__hint">默认规则：{{ defaultSummary }}</span>
      <div class="avh-subs__spacer" />
      <v-btn variant="outlined" size="small" prepend-icon="mdi-cog-outline" @click="goRuleSettings">
        去设置台改规则
      </v-btn>
      <v-btn
        variant="outlined"
        size="small"
        prepend-icon="mdi-lightning-bolt"
        :loading="checkBusy"
        :disabled="checkBusy || !hasSubs"
        @click="runCheck(ALL)"
      >检查一次</v-btn>
    </div>

    <!-- 规则只读回显：老实现这里是「默认规则」编辑弹窗，现在唯一归属是设置台「下载规则」栏。 -->
    <div class="avh-subs__rulecard">
      <div class="avh-subs__rulehd">
        <div class="avh-subs__ruletitle">默认规则（手动搜索与新建订阅的基准）</div>
        <div class="avh-subs__hint">分辨率策略：{{ resText }}</div>
        <div class="avh-subs__hint">规则在「设置台 → 下载规则」里改</div>
      </div>
      <div class="avh-subs__rulegrid">
        <div v-for="row in ruleRows" :key="row.label" class="avh-subs__ruleitem">
          <span class="avh-subs__rulelabel">{{ row.label }}</span>
          <span class="avh-subs__rulevalue" :class="{ 'avh-subs__rulevalue--on': row.on }">
            {{ row.text }}
          </span>
        </div>
      </div>
    </div>

    <div v-if="hasSubs">
      <div v-for="(sub, index) in subs" :key="rowKey(sub, index)" class="avh-sub">
        <div class="avh-sub__hd">
          <v-icon :icon="typeIcon(sub)" size="20" class="avh-sub__icon" />
          <div class="avh-sub__main">
            <div class="avh-sub__name">{{ sub.name }}</div>
            <div class="avh-subs__hint avh-sub__rule">{{ ruleSummary(subRule(sub)) }}</div>
            <div class="avh-subs__hint avh-sub__stat">
              命中 {{ hitsText(sub) }} 次 · 上次检查 {{ lastText(sub) }}
            </div>
          </div>
          <div class="avh-sub__right">
            <v-btn
              variant="outlined"
              size="small"
              :loading="checking === String(sub.name || '')"
              :disabled="checkBusy"
              @click="runCheck(String(sub.name || ''))"
            >检查</v-btn>
            <v-btn
              variant="outlined"
              color="error"
              size="small"
              :disabled="checkBusy"
              @click="onUnsubscribe(sub)"
            >取消</v-btn>
          </div>
        </div>
      </div>
    </div>

    <EmptyState v-else text="还没有订阅" />
  </div>
</template>

<style scoped>
/* 对齐 `app.css` 的 `.toolbar` / `.hint` / `.spacer` */
.avh-subs__toolbar {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
  margin-bottom: 14px;
}

.avh-subs__hint {
  font-size: 12px;
  color: rgba(var(--v-theme-on-surface), 0.5);
}

.avh-subs__spacer {
  flex: 1;
}

/* 对齐 `.q`：卡片底色 + 描边 + 10px 圆角 */
.avh-subs__rulecard,
.avh-sub {
  padding: 12px;
  margin-bottom: 10px;
  border: 1px solid rgba(var(--v-theme-on-surface), 0.12);
  border-radius: 10px;
  background: rgba(var(--v-theme-on-surface), 0.04);
}

.avh-subs__rulehd {
  margin-bottom: 10px;
}

.avh-subs__ruletitle {
  font-size: 14px;
  font-weight: 600;
  margin-bottom: 3px;
}

/* 只读回显：自动铺列，窄屏自然折成一列 */
.avh-subs__rulegrid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
  gap: 6px 18px;
}

.avh-subs__ruleitem {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: 10px;
  font-size: 12.5px;
}

.avh-subs__rulelabel {
  color: rgba(var(--v-theme-on-surface), 0.6);
}

.avh-subs__rulevalue {
  color: rgba(var(--v-theme-on-surface), 0.85);
  white-space: nowrap;
}

.avh-subs__rulevalue--on {
  color: rgb(var(--v-theme-success));
}

/* 对齐 `.q .top`：左右两端对齐 */
.avh-sub__hd {
  display: flex;
  align-items: flex-start;
  gap: 10px;
}

.avh-sub__icon {
  opacity: 0.7;
  margin-top: 3px;
}

/* 老实现的内联 `flex:1;min-width:0` */
.avh-sub__main {
  flex: 1;
  min-width: 0;
}

.avh-sub__name {
  font-size: 14px;
  font-weight: 600;
}

.avh-sub__rule {
  margin-top: 3px;
}

.avh-sub__stat {
  margin-top: 2px;
}

/* 老实现右列 `display:flex;gap:6px` */
.avh-sub__right {
  display: flex;
  gap: 6px;
  white-space: nowrap;
}
</style>
