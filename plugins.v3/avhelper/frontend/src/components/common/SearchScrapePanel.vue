<script setup lang="ts">
/**
 * 搜索刮削（0.7.2 加）：把「手动刮削」从"列表 → 全字段 diff 大表 → 刮削"改成搜索式交互。
 *
 * 用户原话要义（2026-10-15，见 `docs/AVHelper-刮削改进一期方案.md` §2.3 / §4 R8）：
 * 「手动刮削预览信息过多；希望像搜索一样只显示几个搜到的结果；找到想要的点确认，数据直接导入；
 *   自动刮削无所谓」。所以本组件的交互是：
 *
 * ```
 * ① 输入框（番号或关键词，回车即搜）
 * ② 候选行 ×N（番号 / 封面缩略 / 标题 / 演员一行）—— 像站点搜索那样，只有几条
 * ③ 点选一条 → 精简确认卡：只画将写入的关键字段（中文标题 / 原名 / 演员数 / 封面缩略 / 发行日）
 * ④ 「确认导入」→ POST /scrape/run（keys 只带这一个番号）
 * ```
 *
 * 端点（**全部已有，本组件一个新端点都不开、也不自己拼 javdb 调用**）：
 * | 用途 | 端点 | 备注 |
 * | --- | --- | --- |
 * | 搜索候选 | `GET /search?keyword=` | `api_search()`：javdb 搜索 + 番号校验，返回 `{movies[:24], actors[:24]}`；本组件只吃 `movies[]`（候选卡片用不着演员行，见 §4 R8） |
 * | 确认卡取值 | `GET /scrape/preview?key=` | **点选之后才发**：确认卡上的值必须是"真会写进去的那份"，而不是搜索行里那份（`_movie()` 的 `title` 与写侧 `Name` 的口径不同） |
 * | 确认导入 | `POST /scrape/run {keys:[key], force:false}` | 与工作台行内「刮削」同一条链路（0.7.0 写入链不动） |
 *
 * 候选卡片为什么是一行一条（而不是 `NumCard` 那种网格）：
 * 用户要的是"**只显示几个**搜到的结果"，`SearchDialog` 的 `.searchrow` 正是这个密度
 * （番号 + 缩略图 + 标题 + 演员一行），所以照抄它的行版式与 `Thumb variant="mini"`，
 * 不引入表格、不引入全字段 diff。
 *
 * 「高级：字段级 diff」折叠（默认收起、**收起时不发任何请求**）：
 * `/scrape/preview` 与字段级 diff 表**原样保留**（用户没让删），只是降级到折叠里；
 * 展开后可以：① 点「预览字段差异」看当前点选那一条的 diff；② 直接看下方说明。
 * 工作台行内那颗「预览」按钮也由本组件承载（`defineExpose({ openPreview })`），
 * 全页只有一份 diff 表实现与一处预览状态。
 *
 * 降级纪律（与 `ScrapeView` 一致）：搜索失败 / 预览失败 / 导入失败都只出一句可读原因
 * 并保留重试入口，**不白屏、不抛未捕获异常**；预览失败也**不影响**「确认导入」
 * （导入走的是后端自己的取数链，不依赖这次预览）。
 */
import { computed, ref } from 'vue'
import EmptyState from './EmptyState.vue'
import ErrorState from './ErrorState.vue'
import Thumb from './Thumb.vue'
import { errorText, hostToast, unwrap, type PluginApi } from '../../composables/usePluginApi'

const props = withDefaults(
  defineProps<{
    /** 宿主请求器（壳已补插件 id）：本组件的全部请求都走它。 */
    api?: PluginApi | null
    /** 本插件实例 id：给 `Thumb` 拼图片代理地址用。 */
    pluginId?: string
    /** 宿主 toast（`moviepilot:toast` 注入），拿不到时静默降级。 */
    toast?: unknown
  }>(),
  { api: null, pluginId: '', toast: null },
)

/**
 * ⚠️ 必须是字符串数组，不能写成"返回空函数的类型式写法"（AGENTS.md §5 的坑：
 * `defineEmits(consoleEmits())` 会编译出 `emits: <函数>`，Vue 的 `normalizeEmitsOptions`
 * 只认数组/对象 → 事件一个都没声明 → 全退化成 fallthrough attrs 层层下传，**一次点击双发**）。
 * 这里用**内联字面量数组**（照 `views/ScrapeView.vue` 的写法）：`defineEmits()` 的实参必须是
 * 编译器在这个位置**静态看得见**的东西，跨模块常量在 `<script setup>` 里不保证被内联。
 */
const emit = defineEmits(['refreshSide', 'done'])

const t = hostToast(props.toast as any)

// ---------------------------------------------------------------- 请求封装

function text(value: unknown): string {
  return value === null || value === undefined ? '' : String(value)
}

async function getJson(path: string, params?: Record<string, unknown>): Promise<any> {
  const api = props.api
  if (!api || typeof api.get !== 'function') throw new Error('宿主 api 不可用')
  const payload: any = unwrap<any>(await api.get(path, params ? { params } : undefined))
  if (payload && typeof payload === 'object' && payload.success === false) {
    throw new Error(text(payload.message) || '接口返回失败')
  }
  return payload
}

async function postJson(path: string, body: Record<string, unknown>): Promise<any> {
  const api = props.api
  if (!api || typeof api.post !== 'function') throw new Error('宿主 api 不可用')
  const payload: any = unwrap<any>(await api.post(path, body))
  if (payload && typeof payload === 'object' && payload.success === false) {
    throw new Error(text(payload.message) || '接口返回失败')
  }
  return payload
}

/** 从若干候选键里取第一个是数组的值（后端字段名变动时不至于整块空掉）。 */
function firstArray(source: any, keys: string[]): any[] | null {
  if (!source || typeof source !== 'object') return null
  for (const key of keys) {
    if (Array.isArray(source[key])) return source[key]
  }
  return null
}

/** 值 → 一行文本（对象/数组压成 JSON，null 显示 `—`；与 `ScrapeView` 同一口径）。 */
function valueText(value: unknown): string {
  if (value === null || value === undefined || value === '') return '—'
  if (typeof value === 'object') {
    try {
      return JSON.stringify(value)
    } catch {
      return String(value)
    }
  }
  return String(value)
}

// ---------------------------------------------------------------- ① 搜索

/** 结果里的电影（后端 `api_search` 的 `movies[]`，即 `_movie()` 的形状）。 */
interface SearchMovie {
  number?: string
  id?: string
  title?: string
  /** 后端给的是图片代理地址（`image_url()`），`Thumb` 认这个标记就不再套一层。 */
  thumb?: string
  cover?: string
  actor?: string
  date?: string
  cnsub?: boolean
  uncensored?: boolean
  magnets?: number
  /** 已在 Emby 库里时是对象 `{id,name,path,url}`；确认卡用它提示"这部在不在库里"。 */
  lib?: { id?: string; name?: string; path?: string; url?: string } | null
}

const keyword = ref('')
const searching = ref(false)
const searchError = ref('')
const movies = ref<SearchMovie[]>([])
/** 有没有搜过（区分"还没搜"与"搜到 0 条"）。 */
const searched = ref(false)
/** 上次搜的词（重试用它，用户改了输入框也不会把重试指向新词）。 */
const lastKeyword = ref('')

/** 候选卡片封面：`thumb` 是列表缩略图（147×200），与搜索弹窗同一取法。 */
function coverOf(movie: SearchMovie): string {
  return text(movie.thumb || movie.cover)
}

/** 一次搜索（`GET /search?keyword=`）；成功后把候选整份换掉。 */
async function doSearch(): Promise<void> {
  const kw = keyword.value.trim()
  if (!kw) {
    t.warning('先输入番号或关键词')
    return
  }
  if (searching.value) return
  searching.value = true
  searchError.value = ''
  lastKeyword.value = kw
  try {
    const payload: any = await getJson('plugin/search', { keyword: kw })
    const list = firstArray(payload, ['movies', 'list', 'films']) || []
    movies.value = list.filter((item: any) => item && typeof item === 'object')
    searched.value = true
    const count = movies.value.length
    if (count) t.success(`搜到 ${count} 条候选`)
    else t.warning('没有匹配的影片')
  } catch (err) {
    // 失败**不清**上一次的候选：重搜失败时用户手上那份结果还在
    searchError.value = errorText(err)
    t.warning(`搜索失败：${searchError.value}`)
  } finally {
    searching.value = false
  }
}

/** 错误态「重试」：重放上一次那次搜索（不是输入框里现在的词）。 */
async function retrySearch(): Promise<void> {
  keyword.value = lastKeyword.value
  await doSearch()
}

/** 清空（换一次干净的搜索）；不动工作台的列表阅读位置。 */
function resetSearch(): void {
  keyword.value = ''
  movies.value = []
  searched.value = false
  searchError.value = ''
  lastKeyword.value = ''
  pick.value = null
}

// ---------------------------------------------------------------- ② 选中与 ③ 确认卡

/** 当前点选的那条候选（`null` = 还没选）。 */
const pick = ref<SearchMovie | null>(null)
/** 确认卡的开合（与 `pick` 分开：关掉确认卡不清掉选中，候选列表上的高亮还在）。 */
const confirmOpen = ref(false)
/** 确认卡正在取数（`GET /scrape/preview`）。 */
const detailLoading = ref(false)
/** 确认卡的取数失败原因（**只有这一块**降级，不影响列表与「高级」折叠）。 */
const detailError = ref('')
/** `GET /scrape/preview` 的原样回包：确认卡的五个关键字段与「高级」里的 diff 表都吃它。 */
const previewData = ref<any>(null)
/** 取数后定下来的番号（后端算出来的，可能比候选行更规范）。 */
const previewNumber = ref('')

interface PreviewField {
  name: string
  current: string
  target: string
  changed: boolean
}

/** 字段级 diff 表的数据（`previewData.fields[]` 归一后的形状）。 */
const previewFields = computed<PreviewField[]>(() => {
  const list = firstArray(previewData.value, ['fields']) || []
  return list.map((item: any) => ({
    name: text(item?.name),
    current: valueText(item?.current),
    target: valueText(item?.target),
    changed: item?.changed === true,
  }))
})

const previewChanged = computed(() => previewFields.value.filter(item => item.changed).length)

/** 后端给的告警（没读到 Emby 条目、多实例等），确认卡与高级折叠都照实显示。 */
const previewWarnings = computed<string[]>(() => {
  const raw = previewData.value?.warnings
  return Array.isArray(raw) ? raw.map((item: any) => text(item)).filter(Boolean) : []
})

const previewSources = computed<Record<string, any> | null>(() => {
  const raw = previewData.value?.sources
  return raw && typeof raw === 'object' ? raw : null
})

/**
 * 从 `GET /scrape/preview` 的回包里取**将写入**的那个字段值。
 *
 * 用目标值优先、当前值兜底的顺序（`changed=false` 说明目标值与现值相同，等值；只有后端
 * 这次没给 target 时退到现值）——确认卡画的是"将写入什么"，不是"现在是什么"。
 */
function targetOf(name: string): string {
  const hit = previewFields.value.filter(item => item.name === name)[0]
  if (!hit) return ''
  return hit.target !== '—' ? hit.target : (hit.current !== '—' ? hit.current : '')
}

/** 中文标题（写侧 `Name` 的取值，即 `{番号}{角标} {中文标题}`）。 */
const titleZh = computed(() => text(previewData.value?.title_zh) || targetOf('Name'))

/** 原名（写侧 `OriginalTitle`；后端还给了 `title_jp` 时优先用它）。 */
const titleJp = computed(() => text(previewData.value?.title_jp) || targetOf('OriginalTitle'))

/** 演员数（写侧 `People` 数组的长度；后端这次不写 `People` 就是 0）。 */
const actorCount = computed<number | null>(() => {
  const raw = previewData.value
  if (!raw || typeof raw !== 'object') return null
  const list = firstArray(raw, ['fields']) || []
  const hit = list.filter((item: any) => text(item?.name) === 'People')[0]
  if (!hit) return null
  return Array.isArray(hit.target) ? hit.target.length : 0
})

/** 封面缩略：预览算出来的封面优先（那才是会写进 Emby 的那张），取不到退回候选行那张。 */
const coverSrc = computed(() => {
  const planned = text(previewData.value?.images?.cover)
  return planned || (pick.value ? coverOf(pick.value) : '')
})

/** 发行日：预览里的 `PremiereDate`（ISO 串）只画到日。 */
const releaseDate = computed(() => targetOf('PremiereDate').slice(0, 10))

/**
 * 点选一条候选：先把确认卡开出来（loading 态），再去取「将写入」的那份值。
 *
 * 为什么点选就发这一发 `GET /scrape/preview`（而不是等用户点「确认导入」）：
 * 确认卡要画的五个字段里，中文标题 / 原名 / 演员数只有写侧取数层知道（搜索行的 `title`
 * 是 javdb 原题，与 `Name` 口径不同）；先取回来，用户看到的才是"真会写进去的东西"。
 * 这一发**只读不写**（`preview_one()` 不调任何写方法），失败也只降级这一块。
 */
async function selectPick(movie: SearchMovie): Promise<void> {
  pick.value = movie
  confirmOpen.value = true
  detailLoading.value = true
  detailError.value = ''
  previewData.value = null
  previewNumber.value = text(movie.number)
  try {
    const key = text(movie.number)
    const payload: any = await getJson('plugin/scrape/preview', { key })
    previewData.value = payload
    if (payload?.number) previewNumber.value = text(payload.number)
  } catch (err) {
    detailError.value = errorText(err)
  } finally {
    detailLoading.value = false
  }
}

// ---------------------------------------------------------------- ④ 确认导入

/** 在飞的导入动作（`''` = 空闲）；按钮转圈 + 防重复点。 */
const importing = ref(false)
/** 最近一次导入的结论（留在页面上，别只靠 toast）。 */
const importResult = ref<{ ok: boolean; text: string; errors: string[] } | null>(null)

/** `POST /scrape/run` 的结论 → 一句话 + 失败明细（与工作台同一口径）。 */
function summarizeRun(payload: any): { ok: boolean; text: string; errors: string[] } {
  const results = Array.isArray(payload?.results) ? payload.results : []
  const errors: string[] = []
  let okCount = 0
  for (const item of results) {
    const err = text(item?.error)
    const status = text(item?.status)
    if (err || status === 'error' || status === 'failed') {
      errors.push(`${text(item?.key) || '(未知)'}：${err || status || '失败'}`)
      continue
    }
    okCount += 1
  }
  const declared = payload?.ok
  const ok = declared === undefined ? errors.length === 0 : declared !== false && errors.length === 0
  return {
    ok,
    text: `成功 ${okCount} 条${errors.length ? ` · 失败 ${errors.length} 条` : ''}`,
    errors,
  }
}

/**
 * 「确认导入」：`POST /scrape/run {keys:[番号]}` —— 与工作台行内「刮削」**同一条写入链路**
 * （0.7.0 的取数 → 写前留底 → Emby 写入不动，后端自己会失效投影缓存）。
 */
async function confirmImport(): Promise<void> {
  if (importing.value) return
  const key = previewNumber.value || text(pick.value?.number)
  if (!key) return
  importing.value = true
  importResult.value = null
  t.info(`正在导入 ${key} …`)
  try {
    const payload: any = await postJson('plugin/scrape/run', { keys: [key], force: false })
    const summary = summarizeRun(payload)
    importResult.value = summary
    if (summary.ok) {
      t.success(`导入完成：${summary.text}`)
      confirmOpen.value = false
    } else {
      t.warning(`导入未全部成功：${summary.text}`)
    }
    emit('refreshSide')
    emit('done')
  } catch (err) {
    importResult.value = { ok: false, text: '导入请求失败', errors: [errorText(err)] }
    t.warning(`导入失败：${errorText(err)}`)
  } finally {
    importing.value = false
  }
}

// ---------------------------------------------------------------- 高级：字段级 diff（默认收起）

/** 「高级」折叠是否展开。**收起时不发任何请求**（diff 表只在展开后、且用户点了才取）。 */
const advancedOpen = ref(false)
/** 字段级 diff 弹窗（工作台行内「预览」与本折叠共用这一份状态）。 */
const previewDialog = ref<{
  open: boolean
  loading: boolean
  error: string
  key: string
  number: string
}>({ open: false, loading: false, error: '', key: '', number: '' })

/**
 * 打开字段级 diff（`GET /scrape/preview?key=`）。
 *
 * 两条入口：① 工作台行内「预览」（`defineExpose` 给 `ScrapeView` 调）；
 * ② 「高级」折叠里点「预览字段差异」（预览当前点选的那条候选）。
 * 结果落进 `previewData`，所以「确认导入」的确认卡会跟着用同一份值（两处天然一致）。
 */
async function openPreview(target: { key?: string; number?: string }): Promise<void> {
  const key = text(target?.key || target?.number)
  if (!key) return
  previewDialog.value = { open: true, loading: true, error: '', key, number: text(target?.number || key) }
  previewData.value = null
  previewNumber.value = text(target?.number || key)
  try {
    const payload: any = await getJson('plugin/scrape/preview', { key })
    previewData.value = payload
    if (payload?.number) {
      previewNumber.value = text(payload.number)
      previewDialog.value.number = text(payload.number)
    }
  } catch (err) {
    previewDialog.value.error = errorText(err)
  } finally {
    previewDialog.value.loading = false
  }
}

/** 折叠里那颗按钮：预览当前点选的那条候选（没选就提示先选一条）。 */
function previewPicked(): void {
  const movie = pick.value
  if (!movie) {
    t.info('先在候选里点一条影片')
    return
  }
  void openPreview({ key: text(movie.number), number: text(movie.number) })
}

defineExpose({ openPreview })
</script>

<template>
  <div class="avh-pick">
    <!-- ① 搜索入口：番号或关键词，回车即搜 -->
    <div class="avh-pick__bar">
      <v-text-field
        v-model="keyword"
        class="avh-pick__input"
        placeholder="番号或关键词（如 MIDV-946、三上悠亜）…"
        autocomplete="off"
        density="compact"
        variant="outlined"
        hide-details
        prepend-inner-icon="mdi-magnify"
        :disabled="searching"
        @keydown.enter="doSearch"
      />
      <v-btn
        color="primary"
        variant="flat"
        size="small"
        :loading="searching"
        :disabled="searching"
        prepend-icon="mdi-magnify"
        @click="doSearch"
      >{{ searching ? '搜索中…' : '搜索刮削' }}</v-btn>
      <span class="avh-pick__hint">
        走 <code>GET /search</code>（javdb 搜索 + 番号校验）· 点一条候选即可确认导入
      </span>
    </div>

    <!-- 搜到的东西：只有几条候选卡片，没有表格、没有全字段 diff -->
    <div class="avh-pick__secttl">
      <span>搜索候选{{ searched ? `（${movies.length}）` : '' }}</span>
      <v-btn
        v-if="searched"
        variant="text"
        size="x-small"
        class="ms-1"
        @click="resetSearch"
      >清空</v-btn>
      <span class="avh-pick__hint">候选最多 24 条（后端 <code>movies[:24]</code>）</span>
    </div>

    <ErrorState
      v-if="searchError"
      :message="`搜索失败：${searchError}`"
      :retrying="searching"
      @retry="retrySearch"
    />

    <EmptyState
      v-else-if="searched && !movies.length"
      text="没有匹配的影片"
      hint="换个番号或关键词再搜一次；番号带不带连字符都行"
    />

    <EmptyState
      v-else-if="!searched"
      text="输入番号或关键词后回车，从候选里点一条"
      hint="点中之后会出现一张精简确认卡：只画将写入的关键字段，确认即导入 Emby"
    />

    <div v-else class="avh-pick__list">
      <div
        v-for="(movie, index) in movies"
        :key="`${movie.number}#${index}`"
        class="avh-pickrow"
        :class="{ 'avh-pickrow--on': pick === movie }"
        :title="movie.title || movie.number || ''"
        @click="selectPick(movie)"
      >
        <div class="avh-pickrow__mini">
          <Thumb variant="mini" :src="coverOf(movie)" :alt="text(movie.number)" :plugin-id="pluginId" />
        </div>
        <div class="avh-pickrow__main">
          <div class="avh-pickrow__num">
            {{ movie.number }}
            <span v-if="movie.cnsub" class="avh-pick__tag avh-pick__tag--cn">中字</span>
            <span v-if="movie.uncensored" class="avh-pick__tag avh-pick__tag--uc">破解</span>
            <span v-if="movie.lib" class="avh-pick__tag avh-pick__tag--lib">已入库</span>
            <span v-else class="avh-pick__tag avh-pick__tag--warn">不在库</span>
          </div>
          <div class="avh-pickrow__actor">{{ movie.actor || '—' }}</div>
          <div class="avh-pickrow__ttl avh-pick__hint">{{ movie.title || '—' }}</div>
        </div>
        <span class="avh-pick__hint">选它 ›</span>
      </div>
    </div>

    <!-- 最近一次导入的结论（留在页面上，不只靠 toast） -->
    <div v-if="importResult" class="mt-2">
      <v-alert
        :type="importResult.ok ? 'success' : 'warning'"
        variant="tonal"
        density="compact"
        class="text-caption"
      >
        <div>{{ importResult.text }}</div>
        <div v-for="(line, index) in importResult.errors" :key="index">{{ line }}</div>
      </v-alert>
    </div>

    <!-- 高级（默认收起）：字段级 diff 表与 /scrape/preview 原样保留，只是不再是主路径 -->
    <div class="avh-pick__adv">
      <button class="avh-pick__advhead" @click="advancedOpen = !advancedOpen">
        <v-icon :icon="advancedOpen ? 'mdi-chevron-down' : 'mdi-chevron-right'" size="small" />
        <span>高级：字段级 diff（默认收起）</span>
      </button>
      <div v-if="advancedOpen" class="avh-pick__advbody">
        <span class="avh-pick__hint">
          展开不会自动请求：点下面那颗按钮才调 <code>GET /scrape/preview</code>，
          画出当前值 ⇄ 目标值的全字段对照（与工作台行内「预览」是同一张表）。
        </span>
        <v-btn
          variant="outlined"
          size="x-small"
          prepend-icon="mdi-compare-horizontal"
          :disabled="!pick"
          @click="previewPicked"
        >预览字段差异{{ pick ? `（${text(pick.number)}）` : '' }}</v-btn>
      </div>
    </div>

    <!-- ③ 精简确认卡：只画将写入的关键字段，不再展开全字段 diff -->
    <v-dialog v-model="confirmOpen" max-width="620" scrollable attach="body">
      <v-card>
        <v-toolbar density="comfortable" color="surface">
          <v-icon icon="mdi-check-decagram-outline" color="primary" class="ms-2" />
          <v-toolbar-title class="text-body-1">确认导入 · {{ previewNumber }}</v-toolbar-title>
          <v-spacer />
          <v-btn variant="text" icon="mdi-close" @click="confirmOpen = false" />
        </v-toolbar>

        <v-divider />

        <v-card-text>
          <div v-if="detailLoading" class="avh-pick__loading">正在读取将写入的字段…</div>

          <template v-else>
            <v-alert
              v-if="detailError"
              type="warning"
              variant="tonal"
              density="compact"
              class="text-caption mb-2"
            >读取预览失败（GET /scrape/preview）：{{ detailError }}——仍可直接导入</v-alert>

            <v-alert
              v-for="(line, index) in previewWarnings"
              :key="`warn#${index}`"
              type="warning"
              variant="tonal"
              density="compact"
              class="text-caption mb-2"
            >{{ line }}</v-alert>

            <div class="avh-confirm">
              <div class="avh-confirm__mini">
                <Thumb
                  variant="mini"
                  :src="coverSrc"
                  :alt="previewNumber"
                  :plugin-id="pluginId"
                />
              </div>
              <div class="avh-confirm__main">
                <div class="avh-confirm__row">
                  <span class="avh-confirm__k">中文标题</span>
                  <span class="avh-confirm__v">{{ titleZh || '—' }}</span>
                </div>
                <div class="avh-confirm__row">
                  <span class="avh-confirm__k">原名</span>
                  <span class="avh-confirm__v">{{ titleJp || '—' }}</span>
                </div>
                <div class="avh-confirm__row">
                  <span class="avh-confirm__k">演员数</span>
                  <span class="avh-confirm__v">{{ actorCount === null ? '—' : `${actorCount} 人` }}</span>
                </div>
                <div class="avh-confirm__row">
                  <span class="avh-confirm__k">发行日</span>
                  <span class="avh-confirm__v">{{ releaseDate || '—' }}</span>
                </div>
                <div class="avh-confirm__row">
                  <span class="avh-confirm__k">封面</span>
                  <span class="avh-confirm__v avh-pick__hint">
                    {{ coverSrc ? '见左侧缩略图（写入 Emby 的那张）' : '没有可用封面' }}
                  </span>
                </div>
              </div>
            </div>
          </template>
        </v-card-text>

        <v-divider />
        <v-card-actions>
          <span class="avh-pick__hint">
            确认后会写入 Emby：标题 / 原名 / 简介 / 演员 / 封面 / 发行日等字段，
            覆盖这部片现在的取值。想看全字段对照请展开「高级」。
          </span>
          <v-spacer />
          <v-btn variant="text" @click="confirmOpen = false">取消</v-btn>
          <v-btn
            color="primary"
            variant="flat"
            prepend-icon="mdi-download"
            :loading="importing"
            :disabled="importing"
            @click="confirmImport"
          >确认导入</v-btn>
        </v-card-actions>
      </v-card>
    </v-dialog>

    <!-- 字段级 diff 表（与工作台行内「预览」同一份实现） -->
    <v-dialog v-model="previewDialog.open" max-width="880" scrollable attach="body">
      <v-card>
        <v-toolbar density="comfortable" color="surface">
          <v-icon icon="mdi-compare-horizontal" color="primary" class="ms-2" />
          <v-toolbar-title class="text-body-1">
            刮削预览 · {{ previewDialog.number || previewDialog.key }}
          </v-toolbar-title>
          <v-spacer />
          <v-chip v-if="!previewDialog.loading && !previewDialog.error" size="small" variant="tonal" class="me-2">
            变更 {{ previewChanged }} / {{ previewFields.length }} 项
          </v-chip>
          <v-btn variant="text" icon="mdi-close" @click="previewDialog.open = false" />
        </v-toolbar>

        <v-divider />

        <v-card-text>
          <div v-if="previewDialog.loading" class="avh-pick__loading">正在计算字段差异…</div>

          <v-alert
            v-else-if="previewDialog.error"
            type="warning"
            variant="tonal"
            density="compact"
            class="text-caption"
          >预览失败（GET /scrape/preview）：{{ previewDialog.error }}</v-alert>

          <template v-else>
            <v-alert
              v-for="(line, index) in previewWarnings"
              :key="`pvwarn#${index}`"
              type="warning"
              variant="tonal"
              density="compact"
              class="text-caption mb-2"
            >{{ line }}</v-alert>

            <div v-if="previewFields.length" class="avh-tablewrap">
              <table class="avh-table avh-table--diff">
                <colgroup>
                  <col style="width:150px">
                  <col>
                  <col>
                </colgroup>
                <thead>
                  <tr>
                    <th>字段</th>
                    <th>当前值</th>
                    <th>目标值</th>
                  </tr>
                </thead>
                <tbody>
                  <tr
                    v-for="field in previewFields"
                    :key="field.name"
                    :class="{ 'avh-diff__changed': field.changed }"
                  >
                    <td>
                      <span>{{ field.name }}</span>
                      <v-chip v-if="field.changed" size="x-small" color="warning" variant="tonal" class="ms-1">
                        有变化
                      </v-chip>
                    </td>
                    <td class="avh-diff__cell">{{ field.current }}</td>
                    <td class="avh-diff__cell">{{ field.target }}</td>
                  </tr>
                </tbody>
              </table>
            </div>
            <EmptyState
              v-else
              text="没有可预览的字段"
              hint="GET /scrape/preview 返回的 fields 里没有条目（或后端还没算）"
            />

            <div v-if="previewSources" class="avh-pick__secttl">本次取值来源</div>
            <div v-if="previewSources" class="avh-srcgrid">
              <div v-for="(value, key) in previewSources" :key="String(key)" class="avh-srcgrid__item">
                <span class="avh-srcgrid__k">{{ key }}</span>
                <span>{{ valueText(value) }}</span>
              </div>
            </div>
          </template>
        </v-card-text>

        <v-divider />
        <v-card-actions>
          <span class="avh-pick__hint">
            预览不写任何东西；确认无误后在确认卡上点「确认导入」才真正写 Emby。
          </span>
          <v-spacer />
          <v-btn variant="text" @click="previewDialog.open = false">关闭</v-btn>
        </v-card-actions>
      </v-card>
    </v-dialog>
  </div>
</template>

<style scoped>
/* 工具条：与站点搜索页同款几何（`.toolbar` + `.spacer` + `.hint`） */
.avh-pick__bar {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
  margin-bottom: 8px;
}

.avh-pick__input {
  min-width: 280px;
  flex: 0 1 380px;
}

.avh-pick__hint {
  font-size: 12px;
  color: rgba(var(--v-theme-on-surface), 0.5);
}

.avh-pick__secttl {
  display: flex;
  align-items: baseline;
  gap: 8px;
  margin: 12px 0 8px;
  font-size: 12px;
  letter-spacing: 0.4px;
  color: rgba(var(--v-theme-on-surface), 0.5);
}

.avh-pick__loading {
  padding: 44px 20px;
  text-align: center;
  font-size: 13px;
  color: rgba(var(--v-theme-on-surface), 0.5);
}

.avh-pick__list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

/*
 * 候选行：照抄 `SearchDialog.vue` 的 `.searchrow`（番号 + 74×100 小图 + 标题 + 演员一行 + 右侧提示），
 * 只多一条"选中"高亮（用户点过的那条要看得见是哪条）。
 */
.avh-pickrow {
  display: flex;
  gap: 10px;
  align-items: center;
  padding: 9px 12px;
  cursor: pointer;
  border: 1px solid rgba(var(--v-theme-on-surface), 0.12);
  border-radius: 8px;
  background: rgba(var(--v-theme-on-surface), 0.04);
  transition: 0.15s;
}

.avh-pickrow:hover {
  border-color: rgb(var(--v-theme-primary));
}

.avh-pickrow--on {
  border-color: rgb(var(--v-theme-primary));
  background: rgba(var(--v-theme-primary), 0.14);
}

.avh-pickrow__mini {
  width: 54px;
  height: 74px;
  flex: none;
  overflow: hidden;
  border-radius: 6px;
}

.avh-pickrow__mini :deep(.avh-thumb) {
  height: 100%;
}

/*
 * 缺图占位的番号**只画一行**：`Thumb` 的占位是居中 + 允许换行（详情页那种大方块要这样），
 * 而候选行是固定高的窄条，`SNOS-297` 这种长番号会折成两行、把"长番号"和"短番号"的
 * 卡片高度画成不一样（实测 74px vs 86px）。这里收成单行 + 省略号，行高就齐了。
 */
.avh-pickrow__mini :deep(.avh-thumb__noimg) {
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  padding: 4px;
  font-size: 11px;
}

.avh-pickrow__main {
  flex: 1;
  min-width: 0;
}

.avh-pickrow__num {
  display: flex;
  align-items: center;
  gap: 4px;
  font-weight: 700;
}

.avh-pickrow__actor {
  margin-top: 2px;
  font-size: 12px;
  color: rgba(var(--v-theme-on-surface), 0.72);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.avh-pickrow__ttl {
  margin-top: 2px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

/* `.tag` 系列：与 `SearchDialog.vue` / `CandTable.vue` 同一套观感 */
.avh-pick__tag {
  display: inline-block;
  padding: 1px 6px;
  font-size: 10.5px;
  font-weight: 400;
  border-radius: 4px;
  border: 1px solid rgba(var(--v-theme-on-surface), 0.16);
  color: rgba(var(--v-theme-on-surface), 0.5);
}

.avh-pick__tag--cn {
  border-color: rgba(var(--v-theme-success), 0.45);
  background: rgba(var(--v-theme-success), 0.18);
  color: rgb(var(--v-theme-on-surface));
}

.avh-pick__tag--uc {
  border-color: rgba(var(--v-theme-secondary), 0.5);
  background: rgba(var(--v-theme-secondary), 0.3);
  color: rgb(var(--v-theme-on-surface));
}

.avh-pick__tag--lib {
  border-color: rgba(var(--v-theme-primary), 0.5);
  background: rgba(var(--v-theme-primary), 0.22);
  color: rgb(var(--v-theme-on-surface));
}

/*
 * 「不在库」用 warning：它提示的是"这次导入很可能找不到 Emby 条目"，
 * 是这条候选上最值得先看见的一件事（`/scrape/run` 会回「找不到该番号对应的 Emby 条目」）。
 */
.avh-pick__tag--warn {
  border-color: rgba(var(--v-theme-warning), 0.5);
  background: rgba(var(--v-theme-warning), 0.2);
  color: rgb(var(--v-theme-on-surface));
}

/* 高级折叠：默认收起，行首一颗箭头按钮 */
.avh-pick__adv {
  margin-top: 14px;
  border-top: 1px solid rgba(var(--v-theme-on-surface), 0.08);
  padding-top: 8px;
}

.avh-pick__advhead {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 4px 0;
  font-size: 12px;
  color: rgba(var(--v-theme-on-surface), 0.5);
  background: none;
  border: 0;
  cursor: pointer;
}

.avh-pick__advhead:hover {
  color: rgb(var(--v-theme-primary));
}

.avh-pick__advbody {
  display: flex;
  align-items: center;
  gap: 12px;
  flex-wrap: wrap;
  padding: 6px 0 2px;
}

/* 确认卡：左缩略图 + 右五行「字段 / 值」（只画关键字段） */
.avh-confirm {
  display: flex;
  gap: 14px;
  align-items: flex-start;
}

.avh-confirm__mini {
  width: 84px;
  height: 116px;
  flex: none;
  overflow: hidden;
  border-radius: 6px;
}

.avh-confirm__mini :deep(.avh-thumb) {
  height: 100%;
}

.avh-confirm__main {
  flex: 1;
  min-width: 0;
}

.avh-confirm__row {
  display: flex;
  gap: 10px;
  align-items: baseline;
  padding: 4px 0;
  border-bottom: 1px solid rgba(var(--v-theme-on-surface), 0.06);
}

.avh-confirm__k {
  flex: none;
  width: 64px;
  font-size: 12px;
  color: rgba(var(--v-theme-on-surface), 0.5);
}

.avh-confirm__v {
  flex: 1;
  min-width: 0;
  font-size: 13px;
  word-break: break-word;
}

/* 表格 / diff / 来源网格：与 `ScrapeView.vue` 同一套（本组件原样搬过来，全页只有这一份 diff 表） */
.avh-tablewrap {
  overflow-x: auto;
}

.avh-table {
  width: 100%;
  table-layout: fixed;
  border-collapse: collapse;
  font-size: 12.5px;
}

.avh-table th,
.avh-table td {
  padding: 6px 8px;
  text-align: left;
  vertical-align: middle;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  border-bottom: 1px solid rgba(var(--v-theme-on-surface), 0.08);
}

.avh-table th {
  font-weight: 600;
  color: rgba(var(--v-theme-on-surface), 0.6);
  border-bottom: 1px solid rgba(var(--v-theme-on-surface), 0.16);
}

.avh-table--diff td {
  white-space: normal;
  word-break: break-word;
  vertical-align: top;
}

.avh-diff__changed {
  background: rgba(var(--v-theme-warning), 0.16);
}

.avh-diff__cell {
  font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
  font-size: 12px;
  line-height: 1.6;
}

.avh-srcgrid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
  gap: 6px 16px;
}

.avh-srcgrid__item {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: 10px;
  font-size: 12px;
}

.avh-srcgrid__k {
  color: rgba(var(--v-theme-on-surface), 0.6);
}
</style>
