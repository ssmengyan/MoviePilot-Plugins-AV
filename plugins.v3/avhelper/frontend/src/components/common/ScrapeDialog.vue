<script setup lang="ts">
/**
 * 手动刮削对话框（0.7.4，取代 0.7.2 的「搜索刮削」面板）。
 *
 * 用户原话（2026-10-15）：
 * - 「『搜索候选』功能完全没用，不知道是干啥的，不需要这个搜索候选功能」
 * - 「『高级』下面的下拉栏感觉完全没用」
 * - **「我想要的效果是：点开影片刮削后，能手动选择影片的具体信息」**
 *
 * 于是这个组件只做一件事：**点开一部片 → 看清这次抓到了什么 → 自己勾要写哪几项 → 写入 Emby**。
 * 没有全库搜索框、没有「高级」折叠、没有全字段 diff 大表当主界面。
 *
 * 数据与写入（一个端点都不新造）：
 * | 用途 | 端点 |
 * | --- | --- |
 * | 抓取预览（只算不写） | `GET /scrape/preview?key=` |
 * | 按勾选写入 | `POST /scrape/run {keys:[key], fields:[…]}` |
 *
 * 两条口径（改之前先读）：
 *
 * 1. **勾选 = 白名单**：`fields` 里出现的字段名才会被写。字段名就是 Emby 的键
 *    （`Name` / `Overview` / `People` …），图片槽位用两个伪字段名 `Primary`（封面）/
 *    `Backdrop`（剧照）—— 后端 `_write_field_set()` 认这三个约定。**一个都不勾 = 一项都不写**
 *    （后端 `[]` 与"没给"是两种意思，别把"没勾"发成"没给"）。
 * 2. **默认勾上"这次真的抓到了值"的字段**（`target != null`）；`target` 为空的字段列在
 *    「没抓到的 N 项」里、默认不勾 —— 它出不出来由用户决定，别拿一堆空行把对话框顶满
 *    （这正是 0.7.2 之前那张 25 行 diff 表被嫌弃的原因）。
 */
import { computed, ref } from 'vue'
import EmptyState from './EmptyState.vue'
import { errorText, hostToast, unwrap, type PluginApi } from '../../composables/usePluginApi'

const props = withDefaults(
  defineProps<{
    /** 宿主请求器（壳已补插件 id）：所有请求都走它。 */
    api?: PluginApi | null
    /** 本插件实例 id：只用来拼图片代理地址。 */
    pluginId?: string
    /** 宿主 toast（`moviepilot:toast` 注入），拿不到时静默降级。 */
    toast?: unknown
  }>(),
  { api: null, pluginId: '' },
)

/** ⚠️ 必须是字符串数组（AGENTS.md §5 的坑：函数式写法编译出 `emits: <函数>`，事件静默失效）。 */
const emit = defineEmits(['done'])

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

// ---------------------------------------------------------------- 字段名 → 人话

/** Emby 的键 → 界面上的名字（认不出的键原样显示，绝不吞掉）。 */
const FIELD_LABELS: Record<string, string> = {
  Name: '标题',
  OriginalTitle: '原名',
  Overview: '简介',
  PremiereDate: '发行日',
  ProductionYear: '年份',
  Studios: '制作商',
  SeriesName: '系列',
  GenreItems: '标签',
  CommunityRating: '评分',
  People: '演员',
  ProviderIds: '番号标识',
}

const FIELD_HINTS: Record<string, string> = {
  Name: 'Emby 列表里显示的名字：番号 + 版本角标 + 标题',
  OriginalTitle: '日文原名（Emby 用它做二次匹配）',
  Overview: '简介正文：中文优先，没有中文才写日文',
  People: '写入的演员（只写女演员，导演不写）',
  ProviderIds: '番号标识，用于 Emby 侧识别（不会覆盖别的插件写的键）',
}

/** 值 → 一行可读文本（数组取成员名、对象展开成 `k=v`、Emby 时间戳只留日期）。 */
function valueText(value: unknown): string {
  if (value === null || value === undefined || value === '') return ''
  if (Array.isArray(value)) {
    return value
      .map(item => {
        if (item && typeof item === 'object') {
          const obj = item as Record<string, any>
          return text(obj.Name ?? obj.name)
        }
        return text(item)
      })
      .filter(Boolean)
      .join('、')
  }
  if (typeof value === 'object') {
    const obj = value as Record<string, any>
    return Object.keys(obj).map(key => `${key}=${text(obj[key])}`).join(' · ')
  }
  const raw = text(value)
  return /^\d{4}-\d{2}-\d{2}T/.test(raw) ? raw.slice(0, 10) : raw
}

/** 单元格里太长就截断（简介动辄几百字，铺满会把表挤爆；`title` 里放全文）。 */
function clip(value: string, size = 110): string {
  return value.length > size ? `${value.slice(0, size)}…` : value
}

// ---------------------------------------------------------------- 状态

interface FieldRow {
  name: string
  label: string
  hint: string
  current: string
  target: string
  changed: boolean
  hasValue: boolean
  /** 这个值是谁给的（`javdb` / `javtxt` / `llm`）；老后端没有这个键就是空串 */
  source: string
}

const open = ref(false)
const loading = ref(false)
const busy = ref(false)
const error = ref('')
/** 关键字段缺失时的提醒（`/scrape/preview` 的 `warnings`）。 */
const warnings = ref<string[]>([])
const key = ref('')
const number = ref('')
const title = ref('')
const payload = ref<any>(null)

/** 勾选状态：`picked[字段名]`；图片槽位单独两个开关（伪字段 `Primary` / `Backdrop`）。 */
const picked = ref<Record<string, boolean>>({})
const coverOn = ref(false)
const samplesOn = ref(false)
/** 「没抓到的 N 项」默认收起。 */
const showEmpty = ref(false)

const fieldRows = computed<FieldRow[]>(() => {
  const list = Array.isArray(payload.value?.fields) ? payload.value.fields : []
  return list.map((item: any) => {
    const name = text(item?.name)
    return {
      name,
      label: FIELD_LABELS[name] || name,
      hint: FIELD_HINTS[name] || '',
      current: valueText(item?.current),
      target: valueText(item?.target),
      changed: item?.changed === true,
      hasValue: item?.target !== null && item?.target !== undefined,
      source: text(item?.source),
    }
  })
})
const shownRows = computed(() => fieldRows.value.filter(row => row.hasValue || showEmpty.value))
const emptyCount = computed(() => fieldRows.value.filter(row => !row.hasValue).length)

const coverUrl = computed(() => text(payload.value?.images?.cover))
const sampleCount = computed(() => {
  const list = payload.value?.images?.samples
  return Array.isArray(list) ? list.length : 0
})
/** `/scrape/preview` 的 `people[]`：这次会写进 Emby 的演员（后端已按性别过滤）。 */
const people = computed<string[]>(() => {
  const list = payload.value?.people
  return Array.isArray(list) ? list.map((item: any) => text(item)).filter(Boolean) : []
})
/** 各数据源的结论（`{javdb: {status}}`）：让用户知道这些值是从哪来的。 */
const sourceRows = computed<{ name: string; status: string; why: string }[]>(() => {
  const src = payload.value?.sources
  if (!src || typeof src !== 'object') return []
  return Object.keys(src).map(name => {
    const row = (src as Record<string, any>)[name]
    const info = row && typeof row === 'object' ? row : {}
    return {
      name,
      status: text(info.status) || (row ? text(row) : ''),
      why: text(info.why) || text(info.error),
    }
  })
})

/** 勾选后**真正会写**的字段名（含图片伪字段）。 */
const writeFields = computed<string[]>(() => {
  const out = fieldRows.value
    .filter(row => row.hasValue && picked.value[row.name])
    .map(row => row.name)
  if (coverOn.value && coverUrl.value) out.push('Primary')
  if (samplesOn.value && sampleCount.value) out.push('Backdrop')
  return out
})
const checkedCount = computed(() => writeFields.value.length)

/** 图片代理地址（外网图必须经插件代理：`AGENTS.md` 铁律 3）。 */
function proxySrc(url: string): string {
  if (!url) return ''
  const id = props.pluginId || 'AVHelper'
  return `/api/v1/plugin/${id}/img?url=${encodeURIComponent(url)}`
}

// ---------------------------------------------------------------- 读 / 写

function resetChecks(): void {
  const next: Record<string, boolean> = {}
  for (const row of fieldRows.value) next[row.name] = row.hasValue
  picked.value = next
  coverOn.value = Boolean(coverUrl.value)
  samplesOn.value = sampleCount.value > 0
  showEmpty.value = false
}

/** 读 `GET /scrape/preview?key=`（**只算不写**，重复调用不产生任何 Emby 写请求）。 */
async function reload(): Promise<void> {
  if (!key.value) return
  loading.value = true
  error.value = ''
  warnings.value = []
  try {
    const data: any = await getJson('plugin/scrape/preview', { key: key.value })
    payload.value = data
    if (text(data?.number)) number.value = text(data.number)
    title.value = text(data?.title)
    warnings.value = Array.isArray(data?.warnings)
      ? data.warnings.map((item: any) => text(item)).filter(Boolean)
      : []
    resetChecks()
  } catch (err) {
    payload.value = null
    error.value = errorText(err)
  } finally {
    loading.value = false
  }
}

/** 打开对话框：`row` 是工作台的一行（`{key, number, title}`）。 */
function openFor(row: Record<string, any>): void {
  key.value = text(row?.key) || text(row?.number)
  number.value = text(row?.number) || key.value
  title.value = text(row?.title)
  payload.value = null
  error.value = ''
  warnings.value = []
  picked.value = {}
  coverOn.value = false
  samplesOn.value = false
  open.value = true
  void reload()
}

/** 写入 Emby：`fields` 是白名单（勾中的那几项），写前留底与闸门都在后端。 */
async function write(): Promise<void> {
  if (busy.value || !writeFields.value.length) return
  busy.value = true
  try {
    const body = { keys: [key.value], fields: writeFields.value }
    const result: any = await postJson('plugin/scrape/run', body)
    const rows = Array.isArray(result?.results) ? result.results : []
    const failed = rows.filter((row: any) => text(row?.error))
    const changed = rows.reduce(
      (sum: number, row: any) => sum + (Array.isArray(row?.changed) ? row.changed.length : 0),
      0,
    )
    if (failed.length) {
      t.warning(`写入未全部成功：${text(failed[0]?.error) || '原因未知'}`)
    } else {
      t.success(`已写入 ${number.value || key.value}：${changed} 个字段（勾选 ${checkedCount.value} 项）`)
    }
    open.value = false
    emit('done')
  } catch (err) {
    t.warning(`写入失败：${errorText(err)}`)
  } finally {
    busy.value = false
  }
}

/** 全不选 / 全选（"全选"只作用于**这次抓到了值**的那些字段，空字段照样不写）。 */
function toggleAll(value: boolean): void {
  const next: Record<string, boolean> = {}
  for (const row of fieldRows.value) next[row.name] = value && row.hasValue
  picked.value = next
  coverOn.value = value && Boolean(coverUrl.value)
  samplesOn.value = value && sampleCount.value > 0
}

defineExpose({ openFor })
</script>

<template>
  <v-dialog v-model="open" max-width="900" scrollable>
    <v-card>
      <v-toolbar density="comfortable" color="surface">
        <v-icon icon="mdi-auto-fix" color="primary" class="ms-2" />
        <v-toolbar-title class="text-body-1">
          手动刮削 · {{ number || key }}
          <span v-if="title" class="avh-sd__subtitle">{{ clip(title, 60) }}</span>
        </v-toolbar-title>
        <v-spacer />
        <v-chip v-if="!loading && !error" size="small" variant="tonal" class="me-2">
          将写入 {{ checkedCount }} 项
        </v-chip>
        <v-btn variant="text" icon="mdi-close" @click="open = false" />
      </v-toolbar>

      <v-divider />

      <v-card-text>
        <div v-if="loading" class="avh-sd__loading">
          正在抓取「{{ number || key }}」的信息…（javdb / Javtxt / 翻译逐个跑一遍，通常几秒）
        </div>

        <EmptyState
          v-else-if="error"
          text="抓取失败"
          :hint="`GET /scrape/preview 返回：${error}`"
        />

        <template v-else-if="payload">
          <v-alert
            v-for="(line, index) in warnings"
            :key="`warn#${index}`"
            type="warning"
            variant="tonal"
            density="compact"
            class="text-caption mb-2"
          >{{ line }}</v-alert>

          <!-- 封面：看得见再决定写不写 -->
          <div v-if="coverUrl || sampleCount" class="avh-sd__media">
            <div v-if="coverUrl" class="avh-sd__cover">
              <img :src="proxySrc(coverUrl)" alt="封面" referrerpolicy="no-referrer">
            </div>
            <div class="avh-sd__mediainfo">
              <div v-if="coverUrl" class="avh-sd__checkline">
                <v-checkbox
                  :model-value="coverOn"
                  density="compact"
                  hide-details
                  label="写入封面"
                  @update:model-value="(value: any) => (coverOn = Boolean(value))"
                />
                <span class="avh-sd__hint">右边这张图会写进 Emby 的主图（Primary）</span>
              </div>
              <div v-if="sampleCount" class="avh-sd__checkline">
                <v-checkbox
                  :model-value="samplesOn"
                  density="compact"
                  hide-details
                  :label="`写入剧照（${sampleCount} 张）`"
                  @update:model-value="(value: any) => (samplesOn = Boolean(value))"
                />
                <span class="avh-sd__hint">写进 Emby 的横版剧照位（Backdrop）</span>
              </div>
              <div v-if="!coverUrl" class="avh-sd__hint">这次没抓到封面图</div>
            </div>
          </div>

          <div v-if="sourceRows.length" class="avh-sd__sources">
            <span class="avh-sd__hint">数据源：</span>
            <v-chip
              v-for="row in sourceRows"
              :key="row.name"
              size="x-small"
              variant="tonal"
              class="me-1"
              :title="row.why"
            >{{ row.name }} {{ row.status }}</v-chip>
          </div>

          <!-- 字段表：勾 = 写，不勾 = 不动 -->
          <div class="avh-sd__head">
            <span>抓到的信息（勾上的才会写进 Emby）</span>
            <v-spacer />
            <v-btn variant="text" size="x-small" @click="toggleAll(true)">全选</v-btn>
            <v-btn variant="text" size="x-small" @click="toggleAll(false)">全不选</v-btn>
          </div>

          <div v-if="shownRows.length" class="avh-sd__tablewrap">
            <table class="avh-sd__table">
              <colgroup>
                <col style="width:40px">
                <col style="width:110px">
                <col>
                <col>
              </colgroup>
              <thead>
                <tr>
                  <th />
                  <th>字段</th>
                  <th>来源</th>
                  <th>Emby 现在的值</th>
                  <th>这次抓到的值</th>
                </tr>
              </thead>
              <tbody>
                <tr
                  v-for="row in shownRows"
                  :key="row.name"
                  :class="{ 'avh-sd__row--off': !row.hasValue }"
                >
                  <td>
                    <v-checkbox
                      :model-value="Boolean(picked[row.name]) && row.hasValue"
                      :disabled="!row.hasValue"
                      density="compact"
                      hide-details
                      @update:model-value="(value: any) => (picked = { ...picked, [row.name]: Boolean(value) })"
                    />
                  </td>
                  <td :title="row.hint">
                    {{ row.label }}
                    <v-chip v-if="row.changed" size="x-small" color="warning" variant="tonal" class="ms-1">
                      有变化
                    </v-chip>
                  </td>
                  <!-- 「这条是谁给的」：javdb 骨架 / javtxt 中文 / llm 译文。
                       没值或老后端不给时留空，不猜。 -->
                  <td>
                    <code v-if="row.source" class="avh-sd__src">{{ row.source }}</code>
                    <span v-else class="avh-sd__hint">—</span>
                  </td>
                  <td class="avh-sd__cell" :title="row.current">{{ clip(row.current) || '—' }}</td>
                  <td class="avh-sd__cell" :title="row.target">
                    <span v-if="row.hasValue">{{ clip(row.target) }}</span>
                    <span v-else class="avh-sd__hint">没抓到</span>
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
          <EmptyState v-else text="这次什么都没抓到" hint="三个数据源都没有这部片的值，换一部或稍后重试" />

          <div v-if="emptyCount" class="avh-sd__more">
            <v-btn variant="text" size="x-small" @click="showEmpty = !showEmpty">
              {{ showEmpty ? '收起' : `展开没抓到的 ${emptyCount} 项` }}
            </v-btn>
          </div>

          <template v-if="people.length">
            <div class="avh-sd__head">要写入的演员（{{ people.length }}）</div>
            <div class="avh-sd__people">
              <v-chip v-for="name in people" :key="name" size="x-small" variant="tonal" class="me-1 mb-1">
                {{ name }}
              </v-chip>
              <span class="avh-sd__hint">只写女演员，导演不写；不想要演员就取消上面「演员」那一行的勾</span>
            </div>
          </template>
        </template>
      </v-card-text>

      <v-divider />
      <v-card-actions>
        <v-btn variant="text" :loading="loading" @click="reload">↻ 重新抓取</v-btn>
        <v-spacer />
        <span class="avh-sd__hint">
          写入前会自动存一份完整的 Emby 原数据（出问题可回滚），界面上不出现这一步
        </span>
        <v-btn variant="text" @click="open = false">取消</v-btn>
        <v-btn
          color="primary"
          variant="flat"
          :disabled="!checkedCount || loading"
          :loading="busy"
          @click="write"
        >写入 Emby（{{ checkedCount }} 项）</v-btn>
      </v-card-actions>
    </v-card>
  </v-dialog>
</template>

<style scoped>
.avh-sd__subtitle {
  margin-left: 8px;
  font-size: 12px;
  color: rgba(var(--v-theme-on-surface), 0.55);
}

.avh-sd__hint {
  font-size: 12px;
  color: rgba(var(--v-theme-on-surface), 0.5);
}

/* 溯源小字（`javdb` / `javtxt` / `llm`）：等宽、弱化，只作注脚 */
.avh-sd__src {
  font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
  font-size: 11px;
  color: rgba(var(--v-theme-on-surface), 0.6);
}

.avh-sd__loading {
  padding: 40px 20px;
  text-align: center;
  font-size: 13px;
  color: rgba(var(--v-theme-on-surface), 0.6);
}

.avh-sd__media {
  display: flex;
  gap: 14px;
  align-items: flex-start;
  margin-bottom: 10px;
}

.avh-sd__cover img {
  width: 118px;
  border-radius: 6px;
  border: 1px solid rgba(var(--v-theme-on-surface), 0.16);
  display: block;
}

.avh-sd__mediainfo {
  flex: 1;
  min-width: 0;
}

.avh-sd__checkline {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
}

.avh-sd__sources {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 4px;
  margin-bottom: 8px;
}

.avh-sd__head {
  display: flex;
  align-items: center;
  gap: 8px;
  margin: 14px 0 6px;
  font-size: 12px;
  letter-spacing: 0.4px;
  color: rgba(var(--v-theme-on-surface), 0.55);
}

.avh-sd__tablewrap {
  overflow-x: auto;
}

.avh-sd__table {
  width: 100%;
  table-layout: fixed;
  border-collapse: collapse;
  font-size: 12.5px;
}

.avh-sd__table th,
.avh-sd__table td {
  padding: 4px 8px;
  text-align: left;
  vertical-align: top;
  border-bottom: 1px solid rgba(var(--v-theme-on-surface), 0.08);
}

.avh-sd__table th {
  font-weight: 600;
  color: rgba(var(--v-theme-on-surface), 0.6);
  border-bottom: 1px solid rgba(var(--v-theme-on-surface), 0.16);
}

.avh-sd__cell {
  white-space: normal;
  word-break: break-word;
  line-height: 1.5;
}

.avh-sd__row--off {
  opacity: 0.55;
}

.avh-sd__more {
  margin-top: 4px;
}

.avh-sd__people {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
}
</style>
