<script setup lang="ts">
/**
 * 设置台 · 刮削规则（v4 刮削线 S9 新增）。
 *
 * 契约 §3.8 要求的四件东西，全在这一栏：
 * 1. **后缀清洗词表**（可增删的字符串列表）→ `cleanSuffixes`，随 `POST /rule` 保存；
 * 2. **命名模板**（变量 `{number}` / `{badge}` / `{title}`）→ `nameTemplate`，带实时预览；
 * 3. **演员 / 标签自定义映射编辑**（左查询、右编辑）→ `GET /namemap/actors`、`GET /namemap/tags`、
 *    `POST /namemap/set`（这三个端点是契约 §3.7 里就有的，**当场写库、不等顶条保存**）；
 * 4. **单条文件名规则试跑沙盒** —— ⚠️ **契约 §3.7 没有对应端点**（§3.1 只有 Python 侧
 *    `parse_av_number()`），所以这里按后端同一套规则在**前端本地**做预览，并在界面上明确标注
 *    「本地预览」。**不发明后端接口名**：沙盒一次网络请求都不发。
 *
 * 沙盒的权威实现是后端 `emby.parse_av_number()`（S2）；这里的复刻按契约 §0 的口径写死三条：
 *  - `display_number` 带连字符、数字段补到 3 位（`CAWB-040`、`IPZZ-912`、`FC2-PPV-1234567`）；
 *  - `norm_key` 是**干净号**：去非字母数字 + 大写 + 抹数字段前导零（`IPZZ-912-UC` → `IPZZ912`），
 *    与旧的 `norm_key()`（保留后缀）**不是一回事**（契约 D1）；
 *  - FC2 的规范键带 `PPV`（契约 D12：`FC2PPV4828968`）。
 * 复刻件只用于预览，**不参与写库**：界面上的数字与后端不一致时以后端为准（报告里已登记为未验证项）。
 */
import { computed, onMounted, ref } from 'vue'
import Thumb from '../common/Thumb.vue'
import { errorText, hostToast, unwrap, type PluginApi } from '../../composables/usePluginApi'
import type { ScrapeSettings } from './panels'

const props = withDefaults(
  defineProps<{
    /** 刮削设置草稿（本栏只改 `cleanSuffixes` / `nameTemplate`）。 */
    settings: ScrapeSettings
    /** 本插件实例 id：映射列表里演员头像走 `Thumb` → 插件图片代理要用它。 */
    pluginId?: string
    /** 宿主请求器（壳已补插件 id）：映射编辑用它，沙盒不用。 */
    api?: PluginApi | null
    /** 宿主 toast（`moviepilot:toast` 注入），拿不到时静默降级。 */
    toast?: unknown
  }>(),
  { pluginId: '', api: null },
)

/** ⚠️ 必须是字符串数组（AGENTS.md §5 的坑）。 */
const emit = defineEmits(['patch'])

const t = hostToast(props.toast as any)

function patch(key: keyof ScrapeSettings, value: unknown): void {
  emit('patch', { [key]: value })
}

// ---------- ⓪ 数据源 / 字段择优 / 限流（0.8.0 / P1-5，契约 §3.11 / §3.13） ----------
//
// **站点与字段清单由后端下发**（`GET /scrape/graph`）：前端不许自己编站点名/字段名 ——
// 编出来的值会被后端写入校验丢掉（`api_rule` 的 `ignored`），白让用户敲一遍。
// 这里的「当前生效的链」是**后端算的**（已保存配置），所以改完要保存才会变；页面上标注了这一点。

const graph = ref<Record<string, any> | null>(null)
const graphError = ref('')
const graphLoading = ref(false)

const enabledSources = computed<string[]>(() => props.settings.sources || [])
const allSources = computed<Record<string, any>[]>(() => {
  const list = graph.value?.all_sources
  return Array.isArray(list) ? list : []
})
const fieldNames = computed<string[]>(() => {
  const list = graph.value?.fields
  return Array.isArray(list) && list.length ? list : []
})
const chains = computed<Record<string, string[]>>(() => {
  const raw = graph.value?.chains
  return raw && typeof raw === 'object' ? raw : {}
})
/** 字段名 → 人话（拿不到翻译就用原名，别硬编一张表）。 */
const FIELD_LABELS: Record<string, string> = {
  title_jp: '日文标题', origin_title: '原标题', title_zh: '中文标题',
  plot_jp: '日文简介', plot_zh: '中文简介', actors: '演员', tags: '标签',
  studio: '片商', publisher: '发行商', series: '系列', director: '导演',
  release_date: '发行日', duration: '时长', score: '评分',
  cover_url: '封面', thumb_url: '缩略图', preview_video_url: '预告片',
  preview_images: '剧照', javdb_id: '来源 ID',
}
function fieldLabel(name: string): string {
  return FIELD_LABELS[name] || name
}

async function loadGraph(): Promise<void> {
  if (graphLoading.value) return
  graphLoading.value = true
  graphError.value = ''
  try {
    const api = props.api
    if (!api || typeof api.get !== 'function') throw new Error('宿主 api 不可用')
    const payload: any = unwrap<any>(await api.get('plugin/scrape/graph'))
    if (payload && typeof payload === 'object' && payload.success === false) {
      throw new Error(String(payload.message || '取数图读取失败'))
    }
    graph.value = payload && typeof payload === 'object' ? payload : null
  } catch (err) {
    graphError.value = errorText(err)
    graph.value = null
  } finally {
    graphLoading.value = false
  }
}

onMounted(() => {
  void loadGraph()
})

function toggleSource(id: string, on: boolean): void {
  const current = new Set(enabledSources.value)
  if (on) current.add(id)
  else current.delete(id)
  current.add('javdb')                       // 骨架源不可关（与后端 ALWAYS_ON 同一口径）
  patch('sources', [...current])
}

// 字段择优：稀疏的「字段 + 站点」对（19 个字段 × 2 列多选太重，实际通常只填一两项）
const pickField = ref('')
const pickSource = ref('')
const pickKind = ref<'fieldPriority' | 'fieldBlacklist'>('fieldPriority')

function fieldMap(name: 'fieldPriority' | 'fieldBlacklist'): Record<string, string[]> {
  const raw = props.settings[name]
  return raw && typeof raw === 'object' ? { ...raw } : {}
}
function pickRows(name: 'fieldPriority' | 'fieldBlacklist'): { field: string; source: string }[] {
  const out: { field: string; source: string }[] = []
  for (const [field, sites] of Object.entries(fieldMap(name))) {
    for (const source of sites) out.push({ field, source })
  }
  return out
}
function addPick(): void {
  const field = pickField.value || fieldNames.value[0] || ''
  const source = pickSource.value || enabledSources.value[0] || ''
  if (!field || !source) return
  const kind = pickKind.value
  const current = fieldMap(kind)
  const list = [...(current[field] || [])]
  if (!list.includes(source)) list.push(source)
  current[field] = list
  patch(kind, current)
}
function removePick(kind: 'fieldPriority' | 'fieldBlacklist', field: string, source: string): void {
  const current = fieldMap(kind)
  const list = (current[field] || []).filter(item => item !== source)
  if (list.length) current[field] = list
  else delete current[field]
  patch(kind, current)
}

// 限流：默认间隔 + 逐 host 覆盖（值由后端夹到 0.2~60 秒，归零等于关限流、不许）
const newHost = ref('')
const newRate = ref('')
const rateRows = computed(() => Object.entries(props.settings.rateLimits || {}))

function addRate(): void {
  const host = String(newHost.value || '').trim()
  const rate = String(newRate.value || '').trim()
  if (!host || !rate) return
  patch('rateLimits', { ...(props.settings.rateLimits || {}), [host]: rate })
  newHost.value = ''
  newRate.value = ''
}
function removeRate(host: string): void {
  const next = { ...(props.settings.rateLimits || {}) }
  delete next[host]
  patch('rateLimits', next)
}

// ---------- ① 后缀清洗词表 ----------

/** 新词输入框。 */
const newSuffix = ref('')

const suffixes = computed(() => props.settings.cleanSuffixes || [])

/** 加一个词（去空格、去重、大小写不敏感地判重，顺序就是剥离顺序）。 */
function addSuffix(): void {
  const word = String(newSuffix.value || '').trim()
  if (!word) return
  if (suffixes.value.some(item => item.toLowerCase() === word.toLowerCase())) {
    t.info(`词表里已经有「${word}」了`)
    newSuffix.value = ''
    return
  }
  patch('cleanSuffixes', [...suffixes.value, word])
  newSuffix.value = ''
}

function removeSuffix(index: number): void {
  patch('cleanSuffixes', suffixes.value.filter((_, i) => i !== index))
}

/** 恢复默认词表（面板里改坏了不用手打回去）。 */
function resetSuffixes(): void {
  patch('cleanSuffixes', ['-UC', '_4K', '-4K', '-C', '-L', '-VR', '-ISO', 'CD1', 'CD2', '中字', '流出'])
}

// ---------- ② 命名模板 ----------

/** 模板里认得的变量（后端按同一套变量渲染 Emby 的 `Name`）。 */
const TEMPLATE_VARS = ['{number}', '{badge}', '{title}'] as const

function insertVar(token: string): void {
  const current = String(props.settings.nameTemplate || '')
  patch('nameTemplate', `${current}${token}`)
}

// ---------- ④ 试跑沙盒（本地预览，不发请求） ----------

/** 文件名词干里这些词不是番号前缀（分辨率/容器/编码），别把 `FHD-1234` 当成番号。 */
const NOT_PREFIX = new Set([
  'MP4', 'MKV', 'AVI', 'WMV', 'MOV', 'FHD', 'HD', 'SD', 'UHD', 'XXX', 'HEVC', 'AVC',
  'X264', 'X265', 'H264', 'H265', 'AAC', 'HDR', 'VR', 'ISO', 'CD', 'PPV',
])

interface PreviewTag {
  label: string
  tone: 'cn' | 'uc' | 'res' | 'part' | 'other'
}

interface PreviewResult {
  matched: boolean
  displayNumber: string
  normKey: string
  tags: PreviewTag[]
  /** 变量渲染出来的 Emby `Name`（`{title}` 用占位「中文标题」）。 */
  renderedName: string
  /** 认出来了但没吃完的尾巴（提示用户词表可能缺词）。 */
  rest: string
}

/** 词 → 版本标签（与契约 §3.1 的 `version_tags` 键一一对应）。 */
function tagOf(word: string): PreviewTag | null {
  const w = word.toUpperCase().replace(/^[-_\s]+/, '')
  if (!w) return null
  if (w.includes('中字') || w.includes('中文字幕') || w === 'C' || w === 'CN') return { label: '中字', tone: 'cn' }
  if (w.includes('流出') || w.includes('UC') || w.includes('无码') || w.includes('破解')) return { label: '流出', tone: 'uc' }
  if (w.includes('4K') || w.includes('2160')) return { label: '4K', tone: 'res' }
  if (/^CD\d+$/.test(w)) return { label: w, tone: 'part' }
  if (w === 'ISO') return { label: 'ISO', tone: 'other' }
  if (w === 'VR') return { label: 'VR', tone: 'other' }
  if (/^L$/.test(w)) return { label: 'L', tone: 'part' }
  return null
}

/**
 * 本地预览：按「先剥后缀、再认番号」两步走（契约 §5.1 的三步在这里合成两步 ——
 * 第三步的「清洗词表」就是用户在①里维护的那份）。
 */
function parsePreview(raw: string): PreviewResult {
  const empty: PreviewResult = { matched: false, displayNumber: '', normKey: '', tags: [], renderedName: '', rest: '' }
  const input = String(raw || '').trim()
  if (!input) return empty
  // 只取文件名（用户可能整条路径粘进来），去扩展名
  const base = input.replace(/\\/g, '/').split('/').pop() || ''
  let text = base.replace(/\.[A-Za-z0-9]{2,5}$/, '')

  const tags: PreviewTag[] = []
  const pushTag = (tag: PreviewTag | null) => {
    if (tag && !tags.some(item => item.label === tag.label)) tags.push(tag)
  }

  // 第一步：循环剥离词表里的后缀 + 常见标记（大小写不敏感，允许 `-` / `_` / 空格 / 无分隔）
  const words = [...suffixes.value, '中字', '流出', '无码', '破解', '4K'].sort((a, b) => b.length - a.length)
  let changed = true
  while (changed) {
    changed = false
    const head = text
    for (const word of words) {
      const w = word.trim()
      if (!w) continue
      const escaped = w.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
      const re = new RegExp(`[-_\\s]*${escaped}$`, 'i')
      if (re.test(text)) {
        text = text.replace(re, '')
        pushTag(tagOf(w))
        changed = true
        break
      }
    }
    if (text === head) changed = false
    // 纯数字尾巴上的 CD1/CD2 这类词（`xxx-CD1`）已由词表覆盖；这里防死循环
  }
  text = text.replace(/[-_\s]+$/, '').trim()

  // 第二步：认番号
  const upper = text.toUpperCase()
  let displayNumber = ''
  let normKey = ''
  // FC2（契约 D12：规范键带 PPV，展示号 `FC2-PPV-<num>`）
  const fc2 = /FC2[-_\s]*(?:PPV[-_\s]*)?(\d{4,})/.exec(upper)
  if (fc2) {
    const num = String(Number.parseInt(fc2[1], 10))
    displayNumber = `FC2-PPV-${num}`
    normKey = `FC2PPV${num}`
  } else {
    // 标准番号：字母前缀 2–10 位 + 可选分隔 + 2–5 位数字（数字后面不能再跟字母数字）
    const std = /([A-Z]{2,10})[-_\s]?(\d{2,5})(?![0-9A-Z])/.exec(upper)
    if (std && !NOT_PREFIX.has(std[1])) {
      const prefix = std[1]
      const digits = std[2]
      displayNumber = `${prefix}-${digits.length >= 4 ? digits : digits.padStart(3, '0')}`
      normKey = `${prefix}${Number.parseInt(digits, 10)}`
    }
  }

  if (!displayNumber) {
    return { ...empty, tags, rest: text }
  }

  // 角标顺序按契约 §3.6.1（中字 → 流出 → 4K），再拼进模板的 {badge}（模板里是直接接在番号后面）
  const order = ['中字', '流出', '4K', 'ISO', 'VR']
  const badge = tags
    .filter(tag => tag.tone === 'cn' || tag.tone === 'uc' || tag.tone === 'res')
    .map(tag => tag.label)
    .sort((a, b) => order.indexOf(a) - order.indexOf(b))
    .join('')
  const renderedName = String(props.settings.nameTemplate || '{number}{badge} {title}')
    .split('{number}').join(displayNumber)
    .split('{badge}').join(badge)
    .split('{title}').join('中文标题')

  return { matched: true, displayNumber, normKey, tags, renderedName, rest: text }
}

const sampleName = ref('')
const preview = computed(() => parsePreview(sampleName.value))

/** 一句话结论（写给人看，不写 JSON）。 */
const previewSummary = computed(() => {
  const result = preview.value
  if (!String(sampleName.value || '').trim()) return '输入一段文件名（可带路径与扩展名）后立刻看到解析结果。'
  if (!result.matched) return '没认出番号：检查①里的词表是否缺词，或者换个写法再试。'
  return `display_number = ${result.displayNumber} · norm_key = ${result.normKey}`
})

// ---------- ③ 演员 / 标签映射 ----------

type Entity = 'actor' | 'tag'

interface MapRow {
  canonical_id?: string
  zh?: string
  jp?: string
  tw?: string
  avatar?: string
  aliases?: unknown
  source?: string
  is_delete_rule?: boolean
}

const entity = ref<Entity>('actor')
const q = ref('')
const rows = ref<MapRow[]>([])
const listLoading = ref(false)
const listError = ref('')
const selected = ref<MapRow | null>(null)
const draftName = ref('')
const draftZh = ref('')
const draftJp = ref('')
const saving = ref(false)

const entityLabel = computed(() => (entity.value === 'actor' ? '演员' : '标签'))

async function loadMap(): Promise<void> {
  if (listLoading.value) return
  listLoading.value = true
  listError.value = ''
  try {
    const api = props.api
    if (!api || typeof api.get !== 'function') throw new Error('宿主 api 不可用')
    const path = entity.value === 'actor' ? 'plugin/namemap/actors' : 'plugin/namemap/tags'
    const payload: any = unwrap<any>(await api.get(path, { params: { q: q.value, limit: 30 } }))
    if (payload && typeof payload === 'object' && payload.success === false) {
      throw new Error(String(payload.message || '映射读取失败'))
    }
    rows.value = Array.isArray(payload?.items) ? payload.items : []
  } catch (err) {
    // 后端还没落地（404）或网关出错：只显示原因，列表空着，不抛未捕获异常
    listError.value = errorText(err)
    rows.value = []
  } finally {
    listLoading.value = false
  }
}

function switchEntity(next: Entity): void {
  if (entity.value === next) return
  entity.value = next
  selected.value = null
  rows.value = []
  void loadMap()
}

/** 选中一行 → 灌进右边编辑器（`name` 用 canonical_id，缺了退回日文名/中文名）。 */
function pickRow(row: MapRow): void {
  selected.value = row
  draftName.value = String(row?.canonical_id || row?.jp || row?.zh || '')
  draftZh.value = String(row?.zh || '')
  draftJp.value = String(row?.jp || '')
}

/** 别名 / tw 的只读展示（写入端只有 name/zh/jp，别假装能改它们）。 */
function extrasOf(row: MapRow): string {
  const out: string[] = []
  if (row?.tw) out.push(`繁：${String(row.tw)}`)
  const aliases = Array.isArray(row?.aliases) ? row.aliases : []
  if (aliases.length) out.push(`别名：${aliases.slice(0, 3).map(item => String(item)).join('、')}`)
  if (row?.source) out.push(`来源：${String(row.source)}`)
  if (row?.is_delete_rule) out.push('命中即剔除')
  return out.join(' · ')
}

/** 保存一条映射：`POST /namemap/set {name, zh, jp?, entity_type?}`（当场写库）。 */
async function saveMapping(): Promise<void> {
  if (saving.value) return
  const name = String(draftName.value || '').trim()
  if (!name) {
    t.warning('请先填「键 / 原名」')
    return
  }
  saving.value = true
  try {
    const api = props.api
    if (!api || typeof api.post !== 'function') throw new Error('宿主 api 不可用')
    const body: Record<string, unknown> = { name, zh: String(draftZh.value ?? ''), entity_type: entity.value }
    const jp = String(draftJp.value || '').trim()
    if (jp) body.jp = jp
    const payload: any = unwrap<any>(await api.post('plugin/namemap/set', body))
    if (payload && typeof payload === 'object' && payload.success === false) {
      throw new Error(String(payload.message || '映射保存失败'))
    }
    t.success(`已保存${entityLabel.value}映射`)
    if (payload?.canonical_id) t.info(`canonical_id = ${payload.canonical_id}`)
    await loadMap()
  } catch (err) {
    t.warning(`映射保存失败：${errorText(err)}`)
  } finally {
    saving.value = false
  }
}

// 首次进这一栏就把当前实体（默认演员）列表拉一次；拿不到就是空态 + 原因。
void loadMap()
</script>

<template>
  <v-card variant="tonal" class="avh-panel">
    <v-card-item>
      <template #prepend>
        <v-icon icon="mdi-file-document-edit-outline" color="primary" />
      </template>
      <v-card-title>刮削规则</v-card-title>
      <v-card-subtitle>数据源与取数链 · 字段择优 · 限流 · 后缀清洗 · 命名模板 · 演员/标签映射 · 文件名试跑（本地预览）</v-card-subtitle>
    </v-card-item>

    <v-card-text>
      <!-- ===== ⓪ 数据源（P1-5）：清单由后端 /scrape/graph 下发，前端不许自己编 ===== -->
      <div class="text-subtitle-2 mb-1">数据源</div>
      <p class="text-caption text-medium-emphasis mb-2">
        关掉的源<b>一个请求都不会发</b>（取数图里直接没有它）。JavDB 是骨架源，不可关。
        <span v-if="graphError" class="text-warning">取数图读取失败：{{ graphError }}</span>
      </p>
      <div class="avh-row mb-2">
        <v-chip
          v-for="src in allSources"
          :key="src.id"
          size="small"
          :color="enabledSources.includes(src.id) ? 'primary' : undefined"
          :variant="enabledSources.includes(src.id) ? 'flat' : 'tonal'"
          :disabled="src.always_on"
          @click="toggleSource(src.id, !enabledSources.includes(src.id))"
        >{{ src.label || src.id }}<span v-if="src.phase === 2" class="ms-1">（第二段）</span></v-chip>
        <v-btn
          variant="text"
          size="x-small"
          :loading="graphLoading"
          @click="loadGraph"
        >↻ 刷新当前链</v-btn>
      </div>
      <div v-if="!allSources.length" class="text-caption text-medium-emphasis mb-2">
        （拿不到数据源清单：后端未就绪或接口未上线）
      </div>

      <!-- ===== ⓪b 字段择优（P1-5）：稀疏的「字段 + 站点」对 ===== -->
      <div class="text-subtitle-2 mb-1 mt-3">字段择优</div>
      <p class="text-caption text-medium-emphasis mb-2">
        <b>先问的源</b>：只对选中的那个字段生效（链上其余站点顺序不变）；<b>不用的源</b>：该字段不采用它。
        两者都留空 = 用默认链。字段与站点清单来自后端，写错的值会被保存接口拦掉。
      </p>
      <div class="avh-row mb-2">
        <v-select
          v-model="pickKind"
          class="avh-pick-input"
          density="compact"
          variant="outlined"
          hide-details
          :items="[{ title: '先问的源', value: 'fieldPriority' }, { title: '不用的源', value: 'fieldBlacklist' }]"
        />
        <v-select
          v-model="pickField"
          class="avh-pick-input"
          density="compact"
          variant="outlined"
          hide-details
          placeholder="字段"
          :items="fieldNames.map(name => ({ title: fieldLabel(name), value: name }))"
        />
        <v-select
          v-model="pickSource"
          class="avh-pick-input"
          density="compact"
          variant="outlined"
          hide-details
          placeholder="站点"
          :items="enabledSources.map(id => ({ title: id, value: id }))"
        />
        <v-btn variant="outlined" size="small" prepend-icon="mdi-plus" @click="addPick">添加</v-btn>
      </div>
      <div class="avh-chips mb-1">
        <v-chip
          v-for="row in pickRows('fieldPriority')"
          :key="`p#${row.field}#${row.source}`"
          size="small"
          color="primary"
          variant="tonal"
          closable
          @click:close="removePick('fieldPriority', row.field, row.source)"
        >先问 {{ fieldLabel(row.field) }} → {{ row.source }}</v-chip>
        <span v-if="!pickRows('fieldPriority').length" class="text-caption text-medium-emphasis">（没有字段优先级）</span>
      </div>
      <div class="avh-chips mb-3">
        <v-chip
          v-for="row in pickRows('fieldBlacklist')"
          :key="`b#${row.field}#${row.source}`"
          size="small"
          variant="tonal"
          closable
          @click:close="removePick('fieldBlacklist', row.field, row.source)"
        >不用 {{ fieldLabel(row.field) }} ← {{ row.source }}</v-chip>
        <span v-if="!pickRows('fieldBlacklist').length" class="text-caption text-medium-emphasis">（没有字段排除）</span>
      </div>

      <!-- ===== ⓪c 限流（P1-2 / P1-5）：默认间隔 + 逐 host 覆盖 ===== -->
      <div class="text-subtitle-2 mb-1">限流</div>
      <p class="text-caption text-medium-emphasis mb-2">
        每个域名两次请求的<b>最小间隔</b>（秒，0.2~60）。只影响"调用方没写死间隔"的取数：
        <code>javtxt</code> 的 2 秒是硬要求，调这里不会让它变快。被站点拦截后该域名会自动冷却 6 小时。
      </p>
      <div class="avh-row mb-2">
        <v-text-field
          :model-value="props.settings.defaultRateLimit"
          class="avh-pick-input"
          density="compact"
          variant="outlined"
          hide-details
          single-line
          type="number"
          label="默认间隔（秒）"
          @update:model-value="(value: any) => patch('defaultRateLimit', String(value ?? ''))"
        />
        <v-text-field
          v-model="newHost"
          class="avh-pick-input"
          density="compact"
          variant="outlined"
          hide-details
          single-line
          placeholder="域名，如 javtxt.com"
        />
        <v-text-field
          v-model="newRate"
          class="avh-pick-input"
          density="compact"
          variant="outlined"
          hide-details
          single-line
          type="number"
          placeholder="秒"
        />
        <v-btn variant="outlined" size="small" prepend-icon="mdi-plus" @click="addRate">添加</v-btn>
      </div>
      <div class="avh-chips mb-3">
        <v-chip
          v-for="[host, rate] in rateRows"
          :key="`rate#${host}`"
          size="small"
          variant="tonal"
          closable
          @click:close="removeRate(host)"
        >{{ host }} = {{ rate }}s</v-chip>
        <span v-if="!rateRows.length" class="text-caption text-medium-emphasis">（没有按域名覆盖）</span>
      </div>

      <!-- ===== ⓪d 当前生效的链（后端算的，只读） ===== -->
      <div class="text-subtitle-2 mb-1">当前生效的链</div>
      <p class="text-caption text-medium-emphasis mb-1">
        这一份是<b>后端按已保存的配置</b>算出来的（改完要保存才会变）；每个字段按链的顺序问，
        取第一个非空值。
      </p>
      <div v-if="Object.keys(chains).length" class="avh-chain mb-4">
        <div v-for="(chain, field) in chains" :key="`chain#${field}`" class="avh-chain__row">
          <span class="avh-chain__k">{{ fieldLabel(String(field)) }}</span>
          <span class="avh-chain__v">{{ chain.join(' → ') || '（没有可用数据源）' }}</span>
        </div>
      </div>
      <p v-else class="text-caption text-medium-emphasis mb-4">（拿不到链：后端未就绪或接口未上线）</p>

      <!-- ===== ① 后缀清洗词表 ===== -->
      <div class="text-subtitle-2 mb-1">后缀清洗词表</div>
      <p class="text-caption text-medium-emphasis mb-2">
        解析番号前从文件名末尾<strong>逐个剥离</strong>这些词，剥离结果决定番号与版本角标（<code>中字</code> / <code>流出</code> / <code>4K</code>）。
        顺序就是剥离顺序；大小写不敏感。
      </p>
      <div class="avh-chips mb-2">
        <v-chip
          v-for="(word, index) in suffixes"
          :key="`${word}#${index}`"
          size="small"
          variant="tonal"
          closable
          @click:close="removeSuffix(index)"
        >{{ word }}</v-chip>
        <span v-if="!suffixes.length" class="text-caption text-medium-emphasis">（词表为空：不做任何后缀清洗）</span>
      </div>
      <div class="avh-row mb-4">
        <v-text-field
          v-model="newSuffix"
          class="avh-suffix-input"
          density="compact"
          variant="outlined"
          hide-details
          single-line
          placeholder="新增一个词，如 -UC / _4K / CD1"
          @keydown.enter="addSuffix"
        />
        <v-btn variant="outlined" size="small" prepend-icon="mdi-plus" @click="addSuffix">添加</v-btn>
        <v-btn variant="text" size="small" @click="resetSuffixes">恢复默认</v-btn>
      </div>

      <v-divider class="my-4" />

      <!-- ===== ② 命名模板 ===== -->
      <div class="text-subtitle-2 mb-1">命名模板（Emby Name）</div>
      <v-text-field
        :model-value="props.settings.nameTemplate"
        label="命名模板"
        hint="可用变量见下面三颗按钮；空模板按默认值 {number}{badge} {title} 处理"
        persistent-hint
        variant="outlined"
        density="comfortable"
        clearable
        class="mb-2"
        @update:model-value="(value: any) => patch('nameTemplate', String(value ?? ''))"
      />
      <div class="avh-row mb-1">
        <v-chip
          v-for="token in TEMPLATE_VARS"
          :key="token"
          size="small"
          variant="outlined"
          @click="insertVar(token)"
        >{{ token }}</v-chip>
        <span class="text-caption text-medium-emphasis">
          {number} 展示番号 · {badge} 版本角标（无角标时是空串）· {title} 中文标题（取不到时保留原标题）
        </span>
      </div>
      <p class="text-caption text-medium-emphasis mb-4">
        预览：<code>{{ preview.renderedName || '（先在下面试跑一段文件名）' }}</code>
      </p>

      <v-divider class="my-4" />

      <!-- ===== ④ 试跑沙盒（本地预览） ===== -->
      <div class="text-subtitle-2 mb-1">
        单条文件名试跑
        <v-chip size="x-small" color="warning" variant="tonal" class="ms-2">本地预览</v-chip>
      </div>
      <p class="text-caption text-medium-emphasis mb-2">
        契约 §3.7 <strong>没有</strong>这条试跑端点，所以这里用前端复刻的规则当场算，<strong>不发任何请求</strong>；
        真正落库的是后端 <code>parse_av_number()</code>，两边不一致时以后端为准。
      </p>
      <v-text-field
        v-model="sampleName"
        label="文件名（可带路径与扩展名）"
        placeholder="例如：/media/9kg/avi/IPZZ-912-UC_4K.mp4"
        variant="outlined"
        density="comfortable"
        clearable
        hide-details
        class="mb-2"
      />
      <v-alert
        :type="preview.matched ? 'success' : 'info'"
        variant="tonal"
        density="compact"
        class="text-caption mb-2"
      >{{ previewSummary }}</v-alert>
      <div v-if="preview.matched" class="avh-preview mb-2">
        <div class="avh-preview__row">
          <span class="avh-preview__k">display_number</span>
          <code>{{ preview.displayNumber }}</code>
        </div>
        <div class="avh-preview__row">
          <span class="avh-preview__k">norm_key</span>
          <code>{{ preview.normKey }}</code>
        </div>
        <div class="avh-preview__row">
          <span class="avh-preview__k">version_tags</span>
          <span>
            <v-chip
              v-for="tag in preview.tags"
              :key="tag.label"
              size="x-small"
              variant="tonal"
              class="me-1"
            >{{ tag.label }}</v-chip>
            <span v-if="!preview.tags.length" class="text-caption text-medium-emphasis">（无）</span>
          </span>
        </div>
        <div class="avh-preview__row">
          <span class="avh-preview__k">Emby Name</span>
          <span>
            <code>{{ preview.renderedName }}</code>
            <span class="text-caption text-medium-emphasis ms-2">
              （角标按契约 §3.6.1 直接接在番号后面，没有额外分隔符）
            </span>
          </span>
        </div>
      </div>

      <v-divider class="my-4" />

      <!-- ===== ③ 演员 / 标签映射 ===== -->
      <div class="text-subtitle-2 mb-1">演员 / 标签自定义映射</div>
      <p class="text-caption text-medium-emphasis mb-2">
        左查询、右编辑；保存走 <code>POST /namemap/set</code>，<strong>当场写库</strong>（不等顶条「保存修改」）。
      </p>
      <div class="avh-row mb-2">
        <v-btn-toggle
          :model-value="entity"
          mandatory
          density="comfortable"
          variant="outlined"
          color="primary"
          @update:model-value="(value: any) => value && switchEntity(value)"
        >
          <v-btn value="actor">演员</v-btn>
          <v-btn value="tag">标签</v-btn>
        </v-btn-toggle>
        <v-text-field
          v-model="q"
          class="avh-map-q"
          density="compact"
          variant="outlined"
          hide-details
          single-line
          clearable
          prepend-inner-icon="mdi-magnify"
          :placeholder="entity === 'actor' ? '查演员名（中文 / 日文 / 别名）' : '查标签名'"
          @keydown.enter="loadMap"
        />
        <v-btn variant="outlined" size="small" :loading="listLoading" @click="loadMap">查询</v-btn>
      </div>

      <div class="avh-map">
        <!-- 左：查询结果 -->
        <div class="avh-map__left">
          <v-alert
            v-if="listError"
            type="warning"
            variant="tonal"
            density="compact"
            class="text-caption mb-2"
          >{{ entityLabel }}映射读取失败：{{ listError }}</v-alert>
          <div v-if="rows.length" class="avh-map__list">
            <div
              v-for="(row, index) in rows"
              :key="row.canonical_id || `${row.zh || ''}#${index}`"
              class="avh-map__item"
              :class="{ 'avh-map__item--on': selected === row }"
              @click="pickRow(row)"
            >
              <Thumb
                v-if="entity === 'actor'"
                class="avh-map__avatar"
                variant="av"
                :src="String(row.avatar || '')"
                :alt="String(row.zh || row.jp || '头像')"
                :plugin-id="pluginId"
              />
              <div class="avh-map__main">
                <div class="avh-map__name">{{ row.zh || row.jp || row.canonical_id || '(无名)' }}</div>
                <div class="avh-map__sub">{{ row.jp || '' }}</div>
                <div v-if="extrasOf(row)" class="avh-map__sub">{{ extrasOf(row) }}</div>
              </div>
            </div>
          </div>
          <div v-else-if="!listError" class="text-caption text-medium-emphasis">
            {{ listLoading ? '正在读取…' : '没有匹配的记录（后端还没有返回数据，或查询词没命中）' }}
          </div>
        </div>

        <!-- 右：编辑 -->
        <div class="avh-map__right">
          <v-text-field
            v-model="draftName"
            label="键 / 原名（name）"
            hint="写库的查找键：演员用规范 id 或原名，标签用站点标签名"
            persistent-hint
            variant="outlined"
            density="comfortable"
            class="mb-2"
          />
          <v-text-field
            v-model="draftZh"
            :label="entity === 'actor' ? '中文名（zh）' : '标准简中（zh，留空 = 命中即剔除）'"
            variant="outlined"
            density="comfortable"
            :class="entity === 'actor' ? 'mb-2' : 'mb-1'"
          />
          <v-text-field
            v-if="entity === 'actor'"
            v-model="draftJp"
            label="日文原名（jp，可留空）"
            variant="outlined"
            density="comfortable"
            class="mb-3"
          />
          <p v-else class="text-caption text-medium-emphasis mb-3">
            标签的 <code>zh</code> 留空 = 删除规则（后端 <code>tag_lookup()</code> 返回空串即剔除该标签）。
          </p>
          <v-btn
            color="primary"
            variant="flat"
            size="small"
            prepend-icon="mdi-content-save"
            :loading="saving"
            @click="saveMapping"
          >保存这一条映射</v-btn>
        </div>
      </div>
    </v-card-text>
  </v-card>
</template>

<style scoped>
.avh-panel {
  margin-bottom: 12px;
}

.avh-row {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
}

.avh-chips {
  display: flex;
  align-items: center;
  gap: 6px;
  flex-wrap: wrap;
}

.avh-suffix-input {
  max-width: 260px;
}

/* P1-5：字段择优/限流的行内小输入（三四个一排，窄屏自动换行） */
.avh-pick-input {
  max-width: 190px;
  min-width: 130px;
}

/* P1-5：当前生效的链（等宽小字，只读预览） */
.avh-chain {
  max-height: 320px;
  overflow-y: auto;
  padding: 8px 10px;
  border: 1px solid rgba(var(--v-theme-on-surface), 0.12);
  border-radius: 6px;
}

.avh-chain__row {
  display: flex;
  gap: 8px;
  align-items: baseline;
  padding: 2px 0;
  font-size: 12px;
}

.avh-chain__k {
  flex: 0 0 84px;
  color: rgba(var(--v-theme-on-surface), 0.55);
}

.avh-chain__v {
  font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
  color: rgba(var(--v-theme-on-surface), 0.8);
}

.avh-preview {
  padding: 10px 12px;
  border: 1px solid rgba(var(--v-theme-on-surface), 0.12);
  border-radius: 10px;
  background: rgba(var(--v-theme-on-surface), 0.04);
}

.avh-preview__row {
  display: flex;
  align-items: baseline;
  gap: 10px;
  font-size: 12.5px;
  line-height: 2;
}

.avh-preview__k {
  flex: 0 0 110px;
  color: rgba(var(--v-theme-on-surface), 0.6);
}

.avh-map {
  display: grid;
  grid-template-columns: minmax(220px, 1fr) minmax(240px, 1fr);
  gap: 12px;
}

.avh-map__list {
  max-height: 320px;
  overflow: auto;
  border: 1px solid rgba(var(--v-theme-on-surface), 0.12);
  border-radius: 10px;
}

.avh-map__item {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 8px 10px;
  cursor: pointer;
  border-bottom: 1px solid rgba(var(--v-theme-on-surface), 0.08);
}

.avh-map__item:last-child {
  border-bottom: 0;
}

.avh-map__item:hover,
.avh-map__item--on {
  background: rgba(var(--v-theme-primary), 0.12);
}

.avh-map__avatar {
  width: 34px;
  height: 34px;
  flex: none;
  border-radius: 50%;
}

.avh-map__main {
  min-width: 0;
}

.avh-map__name {
  font-size: 13px;
  font-weight: 600;
}

.avh-map__sub {
  font-size: 11px;
  color: rgba(var(--v-theme-on-surface), 0.5);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.avh-map-q {
  max-width: 260px;
}

.avh-map__right {
  padding: 10px 12px;
  border: 1px solid rgba(var(--v-theme-on-surface), 0.12);
  border-radius: 10px;
  background: rgba(var(--v-theme-on-surface), 0.04);
}
</style>
