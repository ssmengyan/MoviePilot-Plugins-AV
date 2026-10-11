<script setup lang="ts">
/**
 * 视图：下载历史（0.3.4 新增的第七栏，见 `docs/AVHelper-下载历史设计.md` §5.1）。
 *
 * 用户诉求原话是"像 MP 的媒体整理那样能看下载过哪些片"：所以这一页是**台账表格**，
 * 不是卡片墙 —— 一行一部，封面/番号/标题/演员/大小/完成时间/库状态/操作八列，
 * 信息密度对齐 MP「媒体整理」。
 *
 * 数据只有一个来源：`GET plugin/downloads`（插件自管的 SQLite 台账）。**不碰 store**：
 * `/bootstrap` 那份快照里没有台账（也不该为了这一页去加字段），所以本视图自己拉、
 * 自己过滤、自己就地更新。
 *
 * 三条纪律（都是本项目的既有约定，别在这里破例）：
 * 1. `api` 是壳（`Console.vue` 的 `bindPluginApi`）已经补好实例 id 的请求器，
 *    所以这里只写 `plugin/downloads`；再补一次 id 会变成 `plugin/<id>/<id>/downloads`。
 * 2. 颜色全走 `rgb(var(--v-theme-…))`，不写死深色值（老宿主主题浅色时也能看）。
 * 3. 破坏性操作先过宿主确认弹窗（`moviepilot:confirm`，拿不到时 `useHostConfirm`
 *    自动降级 `window.confirm`），与订阅页「取消」、设置台「清空通知」同一道闸。
 */
import { computed, onMounted, ref } from 'vue'
// 台账这张表只在**本页**用，所以类型与纯函数收在自己的 composable 里
// （`storeTypes.ts` / `usePluginStore.ts` 这一批由另一条线在改，别去共享文件里加字段）。
import EmptyState from '../common/EmptyState.vue'
import ErrorState from '../common/ErrorState.vue'
import Thumb from '../common/Thumb.vue'
import { errorText, hostToast, unwrap, type PluginApi } from '../../composables/usePluginApi'
import { useHostConfirm } from '../../composables/useHostDialogs'
import {
  completedText,
  displayNumber,
  filterRecords,
  inLibrary,
  parseDownloadList,
  recordKey,
  sizeLabel,
  type DownloadCounts,
  type DownloadRecord,
} from '../../composables/downloadHistory'

const props = withDefaults(
  defineProps<{
    /**
     * 宿主注入的已认证请求器（`Console.vue` 的 `currentApi()`）。
     *
     * 本视图**不**要 `store`：台账数据不在 `/bootstrap` 里，走 store 得给它加字段，
     * 而 `usePluginStore.ts` 这一批由另一条线在改 —— 不越界。`null` 时按请求失败处理。
     */
    api?: PluginApi | null
    /** 本插件实例 id：只给 `Thumb` 拼图片代理地址用（端点前缀由 `api` 负责）。 */
    pluginId?: string
    /** 宿主 toast（`moviepilot:toast` 注入），拿不到时静默降级。 */
    toast?: unknown
  }>(),
  { api: null, pluginId: '', toast: null },
)

/** 端点：设计文档 §4 的 `GET /downloads` 与 `DELETE /downloads?key=…`。 */
const ENDPOINT = 'plugin/downloads'

const t = hostToast(props.toast as any)
const confirm = useHostConfirm()

/** 台账全量（后端已按完成时间倒序，前端不再排序）。 */
const items = ref<DownloadRecord[]>([])
/** 后端给的三个计数；后端没给时退回本地计数（见 `counts`）。 */
const serverCounts = ref<DownloadCounts | null>(null)
/** 加载**中**（首屏与手动刷新都会置上；刷新时列表保留，只把按钮转起来）。 */
const loading = ref(false)
/** 读失败的原因（进 `ErrorState`）。 */
const error = ref('')
/** 是否已经成功读过一次（决定空态文案是"还没有记录"还是"没匹配到"）。 */
const loaded = ref(false)

/** 搜索词：番号 / 标题 / 演员，本地过滤（设计文档 §5.1）。 */
const query = ref('')
/** 「只看不在库」开关。 */
const onlyMissing = ref(false)
/** 正在删的那一行（同一时刻只允许一条，按钮转圈用）。 */
const deletingKey = ref('')

/** 首屏骨架行数：够铺满一屏、又不至于把表格撑得很长。 */
const SKELETON_ROWS = 6

/** 过滤后的行（搜索 + 只看不在库）。 */
const rows = computed<DownloadRecord[]>(() =>
  filterRecords(items.value, query.value, onlyMissing.value),
)

/** 是否有过滤条件（搜索词或开关）——决定空态说"还没记录"还是"没匹配到"。 */
const filtered = computed(() => !!String(query.value || '').trim() || onlyMissing.value)

/** 显示用计数：后端给了就用后端的，否则本地数一遍（口径与设计文档 §4 一致）。 */
const counts = computed<Required<DownloadCounts>>(() => {
  const given = serverCounts.value
  const local = {
    total: items.value.length,
    inLibrary: items.value.filter(item => inLibrary(item)).length,
    missing: items.value.filter(item => !inLibrary(item)).length,
  }
  if (!given) return local
  // 过滤只作用于**显示**，所以计数永远按全量算（后端那份也是全量口径）；缺项用本地补。
  return {
    total: typeof given.total === 'number' ? given.total : local.total,
    inLibrary: typeof given.inLibrary === 'number' ? given.inLibrary : local.inLibrary,
    missing: typeof given.missing === 'number' ? given.missing : local.missing,
  }
})

/** 工具条那句概况：`共 n 条 · 在库 x · 不在库 y`（「不在库」就是被删/没入库的那批）。 */
const summary = computed(
  () => `共 ${counts.value.total} 条 · 在库 ${counts.value.inLibrary} · 不在库 ${counts.value.missing}`,
)

/** 库状态文案：`lib` 存在 → 「在库」，`null` → 「不在库（可能已删除）」（契约里就这一句）。 */
function libraryText(item: DownloadRecord): string {
  return inLibrary(item) ? '在库' : '不在库（可能已删除）'
}

/**
 * 从任意响应里取出列表。
 *
 * `unwrap` 先过一道（宿主 axios 可能给整份信封也可能给裸数据），再交给
 * `parseDownloadList` 认契约写法与"套了 data"的写法 —— 两条容错链子都不猜。
 */
function readList(response: unknown): ReturnType<typeof parseDownloadList> {
  return parseDownloadList(unwrap<any>(response))
}

/**
 * 读台账。
 *
 * - `notify` = 手动刷新（非静默）：先提示"正在刷新…"，失败时给一句 toast；
 * - 首屏与请求失败后的重试都是 `notify = false`：失败落进 `ErrorState` 就够，
 *   页面刚打开就弹 toast 反而吵。
 *
 * 失败时**不清空**已有列表：网络抖一下不该把用户正在看的表清成空白（静默重试的常见纪律）。
 */
async function load(notify = false): Promise<void> {
  if (loading.value) return
  loading.value = true
  error.value = ''
  if (notify) t.info('正在刷新下载历史…')
  try {
    const client = props.api
    if (!client || typeof client.get !== 'function') throw new Error('宿主 api 不可用')
    const response = await client.get(ENDPOINT)
    const parsed = readList(response)
    items.value = parsed.items
    serverCounts.value = parsed.counts
    loaded.value = true
  } catch (err) {
    error.value = errorText(err)
    if (notify) t.warning(`下载历史读取失败：${error.value}`)
  } finally {
    loading.value = false
  }
}

/**
 * 「移除记录」：只删台账里这一行，**不动文件、也不动 Emby**。
 *
 * 走宿主确认弹窗（拿不到注入时降级 `window.confirm`）；确认后
 * `DELETE plugin/downloads?key=<归一化 key 或番号>`，成功就用返回的 items **就地刷新**
 * （契约 §4：删完再回一份列表）—— 不整表重拉，免得用户滚到的位置被打回去。
 */
async function removeRecord(item: DownloadRecord): Promise<void> {
  const key = recordKey(item, 0)
  if (!key || deletingKey.value) return
  const label = displayNumber(item) || key
  const ok = await confirm({
    type: 'warn',
    title: '移除记录',
    content: `将从下载历史里移除「${label}」这条记录（只删台账记录，不动已下载的文件与 Emby 里的条目）。移除后这个番号再出现在榜单/搜索里时会重新显得"没下载过"。确认继续？`,
    confirmText: '移除记录',
    cancelText: '先留着',
  })
  if (!ok) return

  const client = props.api
  if (!client || typeof client.delete !== 'function') {
    t.warning('移除记录失败')
    t.info('宿主请求器不支持 DELETE，无法执行该操作')
    return
  }
  deletingKey.value = key
  try {
    const response = await client.delete(ENDPOINT, { params: { key } })
    const parsed = readList(response)
    items.value = parsed.items
    serverCounts.value = parsed.counts
    // 要看记录条目的数量变化，右栏「运行概况」不涉及台账，所以本视图只给自己刷新。
    loaded.value = true
    t.success('已移除记录')
    t.info(label)
  } catch (err) {
    t.warning(`移除记录失败：${errorText(err)}`)
  } finally {
    deletingKey.value = ''
  }
}

/** 行 key（台账本来就唯一；`v-for` 的 `:key` 直接用 `recordKey`）。 */
function rowKey(item: DownloadRecord, index: number): string {
  return recordKey(item, index)
}

/**
 * 这一行是不是正在删。
 *
 * 比较的是**行 key 而不是番号**：`recordKey` 优先用后端给的 `key`（归一后唯一），
 * 拿番号比会在 `IPZZ-961` 与 `IPZZ961` 两种写法并存时把两行的按钮一起转圈。
 */
function isDeleting(item: DownloadRecord, index: number): boolean {
  return !!deletingKey.value && deletingKey.value === rowKey(item, index)
}

/** 骨架行：只用来占位，`v-for` 需要个数字数组（别用 `Array(n)`，Vue 会警告）。 */
const skeletonRows = Array.from({ length: SKELETON_ROWS }, (_, index) => index)

// 首次挂载就读：这一栏没有轮询（台账只在自己删/插件写入时变化，没有秒级需求），
// 每次切到本栏壳都会重挂组件（`:key="section"`），所以"进来就是最新的"。
onMounted(() => {
  void load(false)
})
</script>

<template>
  <div class="avh-history">
    <!-- 工具条：一句说明 + 搜索 + 只看不在库 + 刷新（设计文档 §5.1 的四件套） -->
    <div class="avh-history__toolbar">
      <span class="avh-history__hint">插件下载过的番号都在这里，文件删了也留着记录</span>

      <div class="avh-history__spacer" />

      <v-text-field
        v-model="query"
        class="avh-history__q"
        density="compact"
        variant="outlined"
        hide-details
        clearable
        single-line
        prepend-inner-icon="mdi-magnify"
        placeholder="番号 / 标题 / 演员"
        aria-label="按番号、标题或演员过滤下载历史"
      />

      <!-- 开关只显示 `lib == null` 的行：批量清点"记录在、库里没有"的那批 -->
      <v-switch
        v-model="onlyMissing"
        class="avh-history__switch"
        color="primary"
        density="compact"
        hide-details
        label="只看不在库"
      />

      <v-btn variant="outlined" size="small" :loading="loading" @click="load(true)">↻ 刷新</v-btn>
    </div>

    <!-- 库状态与规模：在库绿、不在库灰；过滤只改下面表格里的**行数**，计数仍按全量 -->
    <div v-if="!error && (loaded || items.length)" class="avh-history__stats">
      <v-chip
        size="x-small"
        variant="flat"
        color="success"
        label
      >在库 {{ counts.inLibrary }}</v-chip>
      <v-chip
        size="x-small"
        variant="outlined"
        label
      >不在库 {{ counts.missing }}</v-chip>
      <span class="avh-history__hint">{{ summary }}</span>
    </div>

    <div v-if="loading && !items.length" class="avh-history__tablewrap" aria-busy="true">
      <!-- 骨架：首屏还没数据时铺几行空的，表格宽度与列宽都不跳（比一行"加载中"更稳） -->
      <div class="avh-history__loading">正在读取下载历史…</div>
      <table class="avh-history__table">
        <colgroup>
          <col class="avh-history__col-pic" />
          <col class="avh-history__col-no" />
          <col />
          <col class="avh-history__col-actor" />
          <col class="avh-history__col-size" />
          <col class="avh-history__col-time" />
          <col class="avh-history__col-lib" />
          <col class="avh-history__col-act" />
        </colgroup>
        <thead>
          <tr>
            <th>封面</th>
            <th>番号</th>
            <th>标题</th>
            <th>演员</th>
            <th>大小</th>
            <th>完成时间</th>
            <th>库状态</th>
            <th class="avh-history__act">操作</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="row in skeletonRows" :key="`sk-${row}`">
            <td><div class="avh-history__sk avh-history__sk--pic" /></td>
            <td><div class="avh-history__sk" /></td>
            <td><div class="avh-history__sk" /></td>
            <td><div class="avh-history__sk" /></td>
            <td><div class="avh-history__sk" /></td>
            <td><div class="avh-history__sk" /></td>
            <td><div class="avh-history__sk" /></td>
            <td><div class="avh-history__sk" /></td>
          </tr>
        </tbody>
      </table>
    </div>

    <!-- 错误态：给足可重试的按钮（重试是静默的，失败会再落回这里） -->
    <ErrorState
      v-else-if="error"
      :message="`下载历史读取失败：${error}`"
      :retrying="loading"
      @retry="load(false)"
    />

    <div v-else-if="rows.length" class="avh-history__tablewrap">
      <table class="avh-history__table">
        <colgroup>
          <col class="avh-history__col-pic" />
          <col class="avh-history__col-no" />
          <col />
          <col class="avh-history__col-actor" />
          <col class="avh-history__col-size" />
          <col class="avh-history__col-time" />
          <col class="avh-history__col-lib" />
          <col class="avh-history__col-act" />
        </colgroup>
        <thead>
          <tr>
            <th>封面</th>
            <th>番号</th>
            <th>标题</th>
            <th>演员</th>
            <th>大小</th>
            <th>完成时间</th>
            <th>库状态</th>
            <th class="avh-history__act">操作</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="(item, index) in rows" :key="rowKey(item, index)">
            <!-- 封面：48×64 竖版小图（`Thumb` 自带"直连失败回落插件代理、再失败显示占位"） -->
            <td class="avh-history__pic">
              <Thumb
                class="avh-history__thumb"
                variant="tposter"
                :src="String(item.thumb || '')"
                alt="无图"
                :plugin-id="pluginId"
              />
            </td>
            <td class="avh-history__no">{{ displayNumber(item) }}</td>
            <!-- 标题长了省略号，`title` 给全量（照候选表 `.avh-cand__spec` 的处理） -->
            <td class="avh-history__title" :title="String(item.title || '')">
              {{ String(item.title || '') || '—' }}
            </td>
            <td :title="String(item.actor || '')">{{ String(item.actor || '') || '—' }}</td>
            <td>{{ sizeLabel(item) }}</td>
            <td :title="String(item.completedAt || item.createdAt || '')">{{ completedText(item) }}</td>
            <!-- 在库绿、不在库灰：`title` 带上库内路径，判断"是不是同一部片"时不用点进去 -->
            <td :title="String(item.lib?.path || '')">
              <v-chip
                size="x-small"
                label
                :variant="inLibrary(item) ? 'flat' : 'outlined'"
                :color="inLibrary(item) ? 'success' : undefined"
                class="avh-history__lib"
              >{{ libraryText(item) }}</v-chip>
            </td>
            <td class="avh-history__act">
              <v-btn
                variant="outlined"
                size="small"
                :loading="isDeleting(item, index)"
                @click="removeRecord(item)"
              >移除记录</v-btn>
            </td>
          </tr>
        </tbody>
      </table>
    </div>

    <!-- 空态：有过滤条件时说"没匹配到"，否则说"还没有记录" -->
    <EmptyState
      v-else-if="filtered && loaded"
      text="没有匹配的下载记录"
      hint="试试清空搜索词，或关掉「只看不在库」"
    />

    <EmptyState
      v-else
      text="还没有下载记录<br>插件下载过的番号会自动登记在这里，删掉文件也不会消失"
    />
  </div>
</template>

<style scoped>
/* 工具条：与下载页/演员页同款（`.toolbar` + `.hint` + `.spacer`） */
.avh-history__toolbar {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
  margin-bottom: 8px;
}

.avh-history__hint {
  font-size: 12px;
  color: rgba(var(--v-theme-on-surface), 0.5);
}

.avh-history__spacer {
  flex: 1;
}

/* 搜索框宽度固定：不跟着输入内容长短伸缩，工具条高度就不会跳 */
.avh-history__q {
  width: 220px;
  flex: none;
}

/* 开关自带上下留白，压掉一部分，让它和按钮在同一条基线上 */
.avh-history__switch {
  flex: none;
  margin: 0;
}

.avh-history__stats {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
  margin-bottom: 10px;
}

/* 骨架表格顶上那句说明：与演员页 `.avh-loading` 同一号字，但居中留白小一些 */
.avh-history__loading {
  padding: 14px 8px 4px;
  text-align: center;
  font-size: 13px;
  color: rgba(var(--v-theme-on-surface), 0.5);
}

/* 表格外框：与候选表 `.avh-cand` 同一套底色/描边/圆角 */
.avh-history__tablewrap {
  overflow: hidden;
  border: 1px solid rgba(var(--v-theme-on-surface), 0.12);
  border-radius: 10px;
  background: rgb(var(--v-theme-surface));
}

/*
 * `table-layout: fixed` + `<colgroup>` 显式列宽（照候选表）。
 *
 * 固定布局下表格宽度严格等于容器宽度，长标题不再参与列宽计算；代价是所有单元格
 * 必须自己 `overflow:hidden` + 省略号，否则内容会溢到相邻列上。
 * 唯一的弹性列是「标题」（唯一 `<col>` 不带 class 的那条）。
 */
.avh-history__table {
  table-layout: fixed;
  width: 100%;
  border-collapse: collapse;
  font-size: 12.5px;
}

.avh-history__col-pic {
  width: 60px;
}

.avh-history__col-no {
  width: 108px;
}

.avh-history__col-actor {
  width: 110px;
}

.avh-history__col-size {
  width: 84px;
}

/* 完整时间戳「YYYY-MM-DD HH:MM:SS」不截断（表格里时间排成一列才好扫） */
.avh-history__col-time {
  width: 152px;
}

/* 「不在库（可能已删除）」是这一页最长的一格文案，给足宽度免得被省略号吃掉 */
.avh-history__col-lib {
  width: 170px;
}

.avh-history__col-act {
  width: 100px;
}

.avh-history__table th,
.avh-history__table td {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.avh-history__table th {
  padding: 8px;
  text-align: left;
  font-weight: 500;
  color: rgba(var(--v-theme-on-surface), 0.5);
  border-bottom: 1px solid rgba(var(--v-theme-on-surface), 0.12);
}

.avh-history__table td {
  /* 单行定高（正文行约 19px + 上下 9px），矮一行就能多塞几部 */
  height: 38px;
  padding: 9px 8px;
  vertical-align: middle;
  border-bottom: 1px solid rgba(var(--v-theme-on-surface), 0.08);
}

/* 封面列：整行被 64px 的竖图撑起（唯一不自设高度的一格） */
.avh-history__table td.avh-history__pic {
  height: auto;
  padding: 6px 8px;
  vertical-align: middle;
}

.avh-history__thumb {
  width: 48px;
  height: 64px;
  border-radius: 6px;
  border: 1px solid rgba(var(--v-theme-on-surface), 0.12);
}

/* 番号是扫表的锚点，给它一行里最重的字重（照候选表的`.avh-cand__no`口径） */
.avh-history__no {
  font-size: 13px;
  font-weight: 600;
  font-variant-numeric: tabular-nums;
}

/* 标题列是唯一的弹性列（`<colgroup>` 里那条不带 class 的 `<col>`）：
   表格剩余宽度都给它，长标题靠下面那条省略号规则兜 */
.avh-history__title {
  color: rgba(var(--v-theme-on-surface), 0.87);
}

.avh-history__act {
  text-align: right;
  white-space: nowrap;
}

/* 库状态标签：跟表格同一号字（`v-chip` 默认字比表格大一点，会显得突兀） */
.avh-history__lib {
  font-size: 11.5px;
}

/* 骨架格：主题前景色 8% 铺一条，按文字高度给高（不引入动画，避免抢注意力） */
.avh-history__sk {
  height: 12px;
  border-radius: 3px;
  background: rgba(var(--v-theme-on-surface), 0.08);
}

.avh-history__sk--pic {
  width: 48px;
  height: 64px;
  border-radius: 6px;
}
</style>
