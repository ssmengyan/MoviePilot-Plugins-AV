<script setup lang="ts">
/**
 * 设置台 · 演员（0.9.0 演员线 S5 新增）。
 *
 * 方案依据：docs/AVHelper-演员刮削子系统方案.md §6「设置台新增「演员」栏：Gfriends 开关（默认开）、
 * javdb 兜底开关（默认开）、索引状态与「刷新索引」、自动同步开关与每轮条数、「一键补齐缺失头像」
 * （dry-run 预览 → 应用 → 计数）」。
 *
 * 观感与写法照 ScrapePanel.vue / RulePanel.vue（同一套 v-card + v-switch +
 * 「说明一句在控件下面」的排布）。
 *
 * 两处口径写死在代码里，改之前先读契约：
 * 1. **设置项不进宿主配置**：六个键（actorEnabled / actorGfriends / actorJavdbFallback /
 *    actorAutoSync / actorBatchSize / actorInterval）走 POST /rule 那份 kv，与「刮削」两栏
 *    完全同一套机制（见 panels.ts 的 ACTOR_DEFAULTS 说明）。本栏只 emit('patch')，
 *    壳合并进 POST /rule，**本栏不发任何写请求**。
 * 2. **两个按钮各调各的端点**（后端契约原文，不自己发明）：
 *    - 「刷新索引」→ POST /actor/gfriends/refresh（回 {success, index}）；
 *    - 「一键补齐缺失头像」→ POST /actor/scrape {dry_run:true, limit:actorBatchSize} 先拿计划，
 *      再 {dry_run:false, limit:actorBatchSize} 真跑（回 {success, ok, dry_run, counts, items, errors}）；
 *    - 索引状态 → GET /actor/sources（回 {success, sources[], index:{count, fetched_at, stale, source}}），
 *      进本栏时读一次，读不到只显示原因、不白屏。
 */
import { computed, onMounted, ref, watch } from 'vue'
import { errorText, hostToast, unwrap, type PluginApi } from '../../composables/usePluginApi'
import { useHostConfirm } from '../../composables/useHostDialogs'
import { shortTime } from '../../composables/storeTypes'
import type { ActorSettings } from './panels'

const props = withDefaults(
  defineProps<{
    /** 演员设置草稿（壳持有：GET /rule 的演员键 + 本栏还没提交的补丁）。 */
    settings: ActorSettings
    /** 宿主请求器（壳已补插件 id）：索引状态、刷新索引、一键补齐都用它。 */
    api?: PluginApi | null
    /** 宿主 toast（moviepilot:toast 注入），拿不到时静默降级。 */
    toast?: unknown
    /**
     * 读演员设置（`GET /rule`）失败的原因（0.9.1 加）：
     * 空串 = 没问题；非空时面板顶上出一行黄条 —— 这时勾选框里显示的是**默认值**，
     * 不是用户存的值，必须说出来（以前这种情况界面一声不响）。
     */
    loadError?: string
  }>(),
  { api: null, loadError: '' },
)

/** ⚠️ 必须是字符串数组（AGENTS.md §5：函数式写法编译出 emits: <函数>，事件静默失效）。 */
const emit = defineEmits(['patch'])

const t = hostToast(props.toast as any)
const confirm = useHostConfirm()

/** 打补丁到演员草稿（只传改动的字段，保存时由壳合并提交）。 */
function patch(key: keyof ActorSettings, value: unknown): void {
  emit('patch', { [key]: value })
}

function textOf(value: unknown): string {
  return value === null || value === undefined ? '' : String(value)
}

async function getJson(path: string): Promise<any> {
  const api = props.api
  if (!api || typeof api.get !== 'function') throw new Error('宿主 api 不可用')
  const payload: any = unwrap<any>(await api.get(path))
  if (payload && typeof payload === 'object' && payload.success === false) {
    throw new Error(textOf(payload.message) || '接口返回失败')
  }
  return payload
}

async function postJson(path: string, body: Record<string, unknown>): Promise<any> {
  const api = props.api
  if (!api || typeof api.post !== 'function') throw new Error('宿主 api 不可用')
  const payload: any = unwrap<any>(await api.post(path, body))
  if (payload && typeof payload === 'object' && payload.success === false) {
    throw new Error(textOf(payload.message) || '接口返回失败')
  }
  return payload
}

/** 条数/间隔的本地夹取（后端还会再夹一次，这里只是不让界面出现 0 / 负数 / 小数）。 */
function intField(value: unknown, fallback: number, min: number, max: number): number {
  const num = Number(String(value ?? '').trim())
  if (!Number.isFinite(num)) return fallback
  return Math.min(max, Math.max(min, Math.round(num)))
}

// ---------------------------------------------------------------- 索引状态（GET /actor/sources）

/** gFriends 索引此刻的样子（index 字段；缺字段一律显示「—」）。 */
interface IndexState {
  count: number
  fetched_at: string
  stale: boolean
  source: string
}

/** 源清单一行（sources[]）。 */
interface SourceRow {
  name: string
  enabled: boolean
  note: string
}

const sources = ref<SourceRow[]>([])
const index = ref<IndexState | null>(null)
const indexLoading = ref(false)
const indexError = ref('')

/** 索引条数与更新时间：空索引时说「索引还没拉过」，不显示 0 条。 */
const indexText = computed(() => {
  const value = index.value
  if (!value) return ''
  if (!value.count) return '索引还没拉过（刷新一次即会下载并解析）'
  const when = value.fetched_at ? shortTime(value.fetched_at) : '时间未知'
  return '索引 ' + value.count + ' 条 · 更新于 ' + when
})

/** index 回包 → 界面状态（两处端点回包形状相同，抽一处）。 */
function applyIndex(raw: any): void {
  if (raw && typeof raw === 'object') {
    index.value = {
      count: Number(raw.count) || 0,
      fetched_at: textOf(raw.fetched_at),
      stale: raw.stale === true,
      source: textOf(raw.source),
    }
  } else {
    index.value = null
  }
}

async function loadSources(notify = false): Promise<void> {
  if (indexLoading.value) return
  indexLoading.value = true
  indexError.value = ''
  try {
    const payload: any = await getJson('plugin/actor/sources')
    const list = Array.isArray(payload?.sources) ? payload.sources : []
    // 行形状是 {role, id, name, enabled}（后端 api_actor_sources 原样给）；note 是可选的补充说明
    sources.value = list.map((row: any) => ({
      name: textOf(row?.name) || textOf(row?.id) || '(未命名源)',
      enabled: row?.enabled === undefined ? true : !!row.enabled,
      note: textOf(row?.note) || textOf(row?.role),
    }))
    applyIndex(payload?.index)
    if (notify) t.info(indexText.value || '索引状态已刷新')
  } catch (err) {
    // 端点还没上线（404）/ 后端没实现：只显示原因，开关与草稿照常可用
    indexError.value = errorText(err)
    if (notify) t.warning('索引状态读取失败：' + indexError.value)
  } finally {
    indexLoading.value = false
  }
}

/** 「刷新索引」：POST /actor/gfriends/refresh（下载并重新解析索引，非破坏性，不要二次确认）。 */
const refreshing = ref(false)

async function refreshIndex(): Promise<void> {
  if (refreshing.value) return
  refreshing.value = true
  indexError.value = ''
  t.info('正在刷新 gFriends 索引（会下载并重新解析）…')
  try {
    const payload: any = await postJson('plugin/actor/gfriends/refresh', {})
    if (payload?.index && typeof payload.index === 'object') applyIndex(payload.index)
    // 回包里没有 index：重读一次 /actor/sources，界面仍然是最新的那份
    else await loadSources(false)
    t.success('索引已刷新：' + (indexText.value || '条数未知'))
  } catch (err) {
    indexError.value = errorText(err)
    t.warning('刷新索引失败：' + indexError.value)
  } finally {
    refreshing.value = false
  }
}

// ---------------------------------------------------------------- 一键补齐缺失头像（POST /actor/scrape）

/**
 * 回包归一：{ok, dry_run, counts, items[], errors[]}（契约里 counts 是开放形状）。
 *
 * 计数两条路都走：**优先**读 counts 里认得的三类键（uploaded/applied/ok、skipped/skip、
 * failed/error），**否则**按 items[] 的 action/status 自己数 —— 后端把 counts 的键名定下来
 * 之前，界面不会因为少一个键就报「0 张」。
 */
interface ActorCounts {
  up: number
  skip: number
  fail: number
  errors: string[]
}

function countOf(source: Record<string, unknown>, keys: string[]): number | null {
  for (const key of keys) {
    const value = source[key]
    if (value === undefined || value === null) continue
    const num = Number(value)
    if (Number.isFinite(num)) return num
  }
  return null
}

function countActors(payload: any): ActorCounts {
  const counts = (payload?.counts && typeof payload.counts === 'object' ? payload.counts : {}) as Record<string, unknown>
  const items = Array.isArray(payload?.items) ? payload.items : []
  let up = countOf(counts, ['uploaded', 'applied', 'ok', 'done'])
  let skip = countOf(counts, ['skipped', 'skip'])
  let fail = countOf(counts, ['failed', 'error', 'errors'])
  if (up === null || skip === null || fail === null) {
    let okCount = 0
    let skipCount = 0
    let failCount = 0
    for (const item of items) {
      const action = textOf(item?.action ?? item?.status).toLowerCase()
      if (/fail|error/.test(action)) failCount += 1
      else if (/skip|no_avatar|person_missing|has_image/.test(action)) skipCount += 1
      else okCount += 1
    }
    if (up === null) up = okCount
    if (skip === null) skip = skipCount
    if (fail === null) fail = failCount
  }
  const errors = (Array.isArray(payload?.errors) ? payload.errors : [])
    .map((item: unknown) => textOf(item))
    .filter(Boolean)
  return { up: up || 0, skip: skip || 0, fail: fail || 0, errors }
}

/** 结论条：dry_run 与真跑**同一套计数**（方案口径：dry-run 报告与实际一致）。 */
interface FillResult {
  ok: boolean
  text: string
  notes: string[]
  errors: string[]
}

const fillResult = ref<FillResult | null>(null)
const filling = ref(false)

function fillText(counts: ActorCounts, dryRun: boolean): string {
  const line = '上传 ' + counts.up + ' / 跳过 ' + counts.skip + ' / 失败 ' + counts.fail
  return dryRun ? '补齐计划（dry_run，零写请求）：' + line : line
}

/** 失败明细只摆前几条（errors 可能上百条，全铺出来会把面板顶烂）。 */
function headErrors(errors: string[]): string[] {
  const head = errors.slice(0, 5)
  if (errors.length > head.length) head.push('…… 另有 ' + (errors.length - head.length) + ' 条失败明细（后端日志里有全部）')
  return head
}

/**
 * 「一键补齐缺失头像」：**两段式**（与「刮削」栏的「同步演员头像」同一条纪律）——
 * 先 {dry_run:true} 只读拿计划 → 再确认 → {dry_run:false} 真跑。
 *
 * limit 取「每轮条数」（actorBatchSize）：与定时 tick 同一口径，一次别把整库拉起来。
 * 计划里 up === 0 时**不再问第二遍**（没有可写的东西，真跑只会把同一份只读计划重算一遍）。
 */
async function fillMissingAvatars(): Promise<void> {
  if (filling.value) return
  const limit = props.settings.actorBatchSize
  const proceed = await confirm({
    type: 'warn',
    title: '一键补齐缺失头像',
    content:
      '这一步只读：先跑一次 dry_run 计划（零写请求，不会向 Emby 写任何东西）。\n\n' +
      '真正的上传在你看到计划条数、再确认一次之后才发生：届时会把头像写进 Emby 的 Person 实体' +
      '（Primary 图），每批最多 ' + limit + ' 位。' +
      '\n\n本批只处理「缺头像」的演员；设了 images 锁的不会被覆盖（锁要在演员详情里解锁）。',
    confirmText: '先看计划',
    cancelText: '取消',
  })
  if (!proceed) return
  filling.value = true
  fillResult.value = null
  try {
    t.info('正在读取补齐计划（dry_run，零写请求）…')
    let plan: ActorCounts
    try {
      const planPayload: any = await postJson('plugin/actor/scrape', { dry_run: true, limit })
      plan = countActors(planPayload)
    } catch (err) {
      fillResult.value = { ok: false, text: '补齐计划读取失败', notes: [], errors: [errorText(err)] }
      t.warning('补齐计划读取失败：' + errorText(err))
      return
    }
    fillResult.value = {
      ok: plan.fail === 0 && !plan.errors.length,
      text: fillText(plan, true),
      notes: plan.up ? [] : ['本次没有需要上传的头像（缺头像的演员不在这一批，或两个源都没图）'],
      errors: headErrors(plan.errors),
    }
    if (!plan.up) {
      t.info('没有需要上传的头像：' + fillText(plan, false))
      return
    }
    const go = await confirm({
      type: 'warn',
      title: '补齐缺失头像（写入 Emby）',
      content:
        'dry_run 计划：' + fillText(plan, false) + '。\n\n' +
        '确认后真的开始上传：把这 ' + plan.up + ' 张头像写进 Emby 的 Person 实体（Primary 图）；' +
        '计划里已跳过的 ' + plan.skip + ' 位不会动，也没有别的写入。',
      confirmText: '上传 ' + plan.up + ' 张',
      cancelText: '取消',
    })
    if (!go) {
      t.info('已取消，没有向 Emby 写入任何东西')
      return
    }
    t.info('正在上传 ' + plan.up + ' 张头像…')
    const payload: any = await postJson('plugin/actor/scrape', { dry_run: false, limit })
    const done = countActors(payload)
    fillResult.value = {
      ok: done.fail === 0 && !done.errors.length,
      text: fillText(done, false),
      notes: [],
      errors: headErrors(done.errors),
    }
    if (fillResult.value.ok) t.success('补齐完成：' + fillText(done, false))
    else t.warning('补齐未全部成功：' + fillText(done, false))
  } catch (err) {
    fillResult.value = { ok: false, text: '补齐请求失败', notes: [], errors: [errorText(err)] }
    t.warning('补齐失败：' + errorText(err))
  } finally {
    filling.value = false
  }
}

/** 进本栏时读一次索引状态（壳只在真正点进「演员」栏时才挂载本组件）。 */
onMounted(() => {
  void loadSources(false)
})

// 0.9.1：读演员设置失败 → 自动重试一次。
// 为什么要有：用户 2026-10-27 报「点『演员』页签后无任何内容」，其中一个可能就是
// 这一栏的两次 GET 在设置窗口刚打开时抢跑（宿主 api 还没就绪）。失败一次就永久显示默认值
// 是 0.9.0 的写法；现在失败后延迟 1.5 秒再试一次（壳那边的闸门只在成功后闭合，所以再来一次就成功）。
watch(
  () => props.loadError,
  (error, before) => {
    if (!error || before) return
    window.setTimeout(() => { void loadSources(false) }, 1500)
  },
)
</script>

<template>
  <v-card variant="tonal" class="avh-panel">
    <v-card-item>
      <template #prepend>
        <v-icon icon="mdi-account-star" color="primary" />
      </template>
      <v-card-title>演员</v-card-title>
      <v-card-subtitle>演员刮削子系统 · 头像源 / gFriends 索引 / 自动同步 · 与「下载规则」同一份插件设置（POST /rule）</v-card-subtitle>
    </v-card-item>

    <v-card-text>
      <v-alert
        v-if="props.loadError"
        type="warning"
        variant="tonal"
        density="compact"
        class="text-caption mb-3"
      >演员设置读取失败（下面显示的是默认值）：{{ props.loadError }}</v-alert>

      <!-- ===== 子系统总开关 ===== -->
      <v-switch
        :model-value="props.settings.actorEnabled"
        color="primary"
        hide-details
        inset
        label="启用演员刮削子系统"
        class="mb-1"
        @update:model-value="(value: any) => patch('actorEnabled', value === true)"
      />
      <p class="text-caption text-medium-emphasis mb-4">
        关掉 = 不抓演员、不写头像（已经写进去的数据保持不动）。影片刮削本身不受影响。
      </p>

      <!-- ===== 头像来源 ===== -->
      <div class="text-caption text-medium-emphasis mb-1">头像来源</div>
      <v-switch
        :model-value="props.settings.actorGfriends"
        color="primary"
        hide-details
        inset
        label="gFriends 索引图（整图，最高清）"
        class="mb-1"
        @update:model-value="(value: any) => patch('actorGfriends', value === true)"
      />
      <v-switch
        :model-value="props.settings.actorJavdbFallback"
        color="primary"
        hide-details
        inset
        label="javdb 演员页缩略图（兜底，比整图小）"
        class="mb-1"
        @update:model-value="(value: any) => patch('actorJavdbFallback', value === true)"
      />
      <p class="text-caption text-medium-emphasis mb-4">
        两个都关 = 没有头像可用，只抓文字资料。顺序是先 gFriends 后 javdb（后端按这个顺序取第一张能用的）。
        MetaTube 已于 0.8.1 整体下线，不再有第三个源。
      </p>

      <!-- ===== gFriends 索引状态 ===== -->
      <div class="text-caption text-medium-emphasis mb-1">gFriends 索引</div>
      <div class="avh-row mb-2">
        <v-btn
          variant="outlined"
          size="small"
          prepend-icon="mdi-refresh"
          :loading="refreshing"
          @click="refreshIndex"
        >刷新索引</v-btn>
        <v-btn
          variant="text"
          size="small"
          prepend-icon="mdi-database-eye-outline"
          :loading="indexLoading"
          @click="loadSources(true)"
        >重新读取状态</v-btn>
        <span class="text-caption text-medium-emphasis">POST /actor/gfriends/refresh · GET /actor/sources</span>
      </div>

      <v-alert
        v-if="indexError"
        type="warning"
        variant="tonal"
        density="compact"
        class="text-caption mb-3"
      >索引状态读取失败：{{ indexError }}</v-alert>

      <div v-if="index" class="avh-row mb-2">
        <v-chip size="x-small" :color="index.stale ? 'warning' : 'success'" variant="flat" label>
          {{ index.stale ? '索引已过期' : '索引可用' }}
        </v-chip>
        <span class="text-caption text-medium-emphasis">{{ indexText }}</span>
        <span v-if="index.source" class="text-caption text-medium-emphasis">· 来源 {{ index.source }}</span>
      </div>

      <div v-if="sources.length" class="avh-row mb-3">
        <v-chip
          v-for="item in sources"
          :key="item.name"
          size="x-small"
          :color="item.enabled ? 'primary' : undefined"
          variant="tonal"
          label
          :title="item.note || item.name"
        >{{ item.enabled ? item.name : item.name + '（已关）' }}</v-chip>
      </div>
      <p class="text-caption text-medium-emphasis mb-4">
        索引是一份 gFriends 的「演员名 → 头像地址」表（拉一次缓存在本地，过期后由后端自动重拉）。
        「刷新索引」立刻重下并重解析，不影响已经写进 Emby 的头像。
      </p>

      <!-- ===== 自动同步 ===== -->
      <div class="text-caption text-medium-emphasis mb-1">自动同步</div>
      <v-switch
        :model-value="props.settings.actorAutoSync"
        color="primary"
        hide-details
        inset
        label="影片刮完后把该片女演员登记进队列，由定时任务慢慢补"
        class="mb-1"
        @update:model-value="(value: any) => patch('actorAutoSync', value === true)"
      />
      <div class="avh-grid mb-2">
        <v-text-field
          :model-value="String(props.settings.actorBatchSize)"
          label="每轮条数"
          hint="定时任务每轮最多处理多少位（1–200，默认 20）"
          persistent-hint
          variant="outlined"
          density="comfortable"
          type="number"
          min="1"
          max="200"
          @update:model-value="(value: any) => patch('actorBatchSize', intField(value, 20, 1, 200))"
        />
        <v-text-field
          :model-value="String(props.settings.actorInterval)"
          label="间隔（秒）"
          hint="每两位之间的最小间隔（1–60，默认 2）"
          persistent-hint
          variant="outlined"
          density="comfortable"
          type="number"
          min="1"
          max="60"
          @update:model-value="(value: any) => patch('actorInterval', intField(value, 2, 1, 60))"
        />
      </div>
      <p class="text-caption text-medium-emphasis mb-4">
        队列不长在界面上：失败按 6h → 24h → 72h → 7d → 14d 退避，退避到顶后只等手动重刮。
        下面这次「一键补齐」会立刻跑一批，不用等定时任务。
      </p>

      <!-- ===== 一键补齐缺失头像 ===== -->
      <div class="text-caption text-medium-emphasis mb-1">一键补齐缺失头像</div>
      <div class="avh-row mb-2">
        <v-btn
          variant="outlined"
          size="small"
          prepend-icon="mdi-account-sync-outline"
          :loading="filling"
          @click="fillMissingAvatars"
        >一键补齐缺失头像</v-btn>
        <span class="text-caption text-medium-emphasis">
          POST /actor/scrape（先 dry_run 看计划，再确认应用；每批 {{ props.settings.actorBatchSize }} 位）
        </span>
      </div>

      <v-alert
        v-if="fillResult"
        :type="fillResult.ok ? 'success' : 'warning'"
        variant="tonal"
        density="compact"
        class="text-caption mb-0"
      >
        <div>{{ fillResult.text }}</div>
        <div v-for="(line, index) in fillResult.notes" :key="'note#' + index">{{ line }}</div>
        <div v-for="(line, index) in fillResult.errors" :key="index">{{ line }}</div>
      </v-alert>
    </v-card-text>
  </v-card>
</template>

<style scoped>
.avh-panel {
  margin-bottom: 12px;
}

/* 与 ScrapePanel / RulePanel 同一套「自动铺列」网格（窄屏自然折成一列） */
.avh-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
  gap: 12px 16px;
}

.avh-row {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
}
</style>
