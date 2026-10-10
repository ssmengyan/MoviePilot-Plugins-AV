<script setup lang="ts">
/**
 * 顶栏搜索结果（老实现 `ui/views/search.js` 的 `doSearch` + `ui/index.html` 的 `#qInput`/`#qBtn`）。
 *
 * 老实现把结果开在一个 `wide` 弹窗里（`openModal('搜索「kw」', …, '<button class="danger">关闭</button>')`
 * + `$('#modal').classList.add('wide')`），这里等价地用一个 `v-dialog`（`max-width="920"` ≈ 老 `.modal.wide`）：
 *
 * | 老实现 | 这里 |
 * | --- | --- |
 * | 弹窗标题先 `搜索「kw」`，结果回来后改成 `搜索「kw」 · n 部影片` / `… · n 部影片 / m 位演员` | 同一句话、同一个出现时机（标题由 `title` 计算属性驱动） |
 * | 正文加载态 `loadingHtml('正在搜索…')` | 同一个 `.avh-search__loading`、同一句文案 |
 * | 失败 `errHtml(r.message \|\| '搜索失败，请稍后重试', 'id="sRetry"')` + 那颗「重试」重跑 `doSearch(kw)` | `ErrorState` 同一句文案 + `@retry` 重跑同一次搜索 |
 * | 演员区：`<div class="hint">演员</div>` + `.actors` 网格（头像 + 艺名 + 中文名），点一下 `closeAll(); openActor(name)` | 同一句话、同一个网格（`common/ActorRow.vue`），点一下 `emit('openActor')` |
 * | 影片区：`<div class="hint">影片</div>` + `.searchrow`（`mini` 封面、番号、`演员 · 日期 · 🧲 n` + 中字/破解/已入库 tag、标题截断 60 字、右侧「查看 ›」） | 同一字段、同一顺序、同一句「查看 ›」；点一下 `closeAll(); openMovie(num, id)` → `emit('openMovie')` |
 * | 没有影片时的兜底 `<div class="hint">没有匹配的影片</div>` | 同一句 |
 * | `preload(movies.map(x => x.thumb))`：把结果封面预热一遍 | 同（`new Image()` 预取，失败静默） |
 *
 * **图片纪律**：结果封面走 `common/Thumb.vue`（`referrerpolicy="no-referrer"` + 直连失败回落 `/img`），
 * 与老实现 `imgTag()` 的同一条链；老实现用的是 `mv.thumb`（列表缩略图），这里也用 `thumb`，
 * 不换 `cover`（详情页那张大图）。
 */
import { computed, ref, watch } from 'vue'
import ActorRow from '../common/ActorRow.vue'
import EmptyState from '../common/EmptyState.vue'
import ErrorState from '../common/ErrorState.vue'
import Thumb from '../common/Thumb.vue'
import { errorText, type PluginApi } from '../../composables/usePluginApi'
import type { FavActor } from '../../composables/storeTypes'

const props = withDefaults(
  defineProps<{
    /** 弹窗是否打开（壳控制；老实现是 `$('#modal').classList.add('on')`）。 */
    open?: boolean
    /** 本插件实例 id：给 `Thumb` 拼图片代理地址用。 */
    pluginId?: string
    /** 宿主请求器：`GET plugin/search?keyword=` 走它。 */
    api?: PluginApi | null
  }>(),
  { open: false, pluginId: '', api: null },
)

const emit = defineEmits<{
  /** 请求关闭弹窗。 */
  (event: 'close'): void
  /** 点影片行：`closeAll(); openMovie(number, id)` —— 由壳开详情抽屉。 */
  (event: 'openMovie', payload: { number: string; id: string }): void
  /** 点演员卡：`closeAll(); openActor(name)` —— 由壳切到「我的演员」栏。 */
  (event: 'openActor', name: string): void
}>()

/** 结果里的影片（后端 `api_search` 的 `movies[]`，即 `_movie()` 的形状）。 */
interface SearchMovie {
  number?: string
  id?: string
  title?: string
  /** 列表缩略图（老实现用它，不是 `cover`）。 */
  thumb?: string
  actor?: string
  date?: string
  /** 磁力条数（0 也照画 `🧲 0`）。 */
  magnets?: number
  cnsub?: boolean
  uncensored?: boolean
  /** 已入库（Emby 命中）。 */
  lib?: unknown
}

/** 搜索关键词（老实现每次进函数时 `kw.trim()`）。 */
const keyword = ref('')
const loading = ref(false)
/** 失败文案（老 `errHtml(r.message || '搜索失败，请稍后重试', …)`）。 */
const error = ref('')
const movies = ref<SearchMovie[]>([])
const actors = ref<FavActor[]>([])
/** 有没有搜过（老实现靠 `#modalBody` 的内容判断；这里显式记一笔，好区分"没搜过"与"搜到 0 部"）。 */
const searched = ref(false)

/** 老实现那句标题：先 `搜索「kw」`，结果回来再补计数。 */
const title = computed(() => {
  const head = `搜索「${keyword.value}」`
  if (!searched.value) return head
  const actorPart = actors.value.length ? ` / ${actors.value.length} 位演员` : ''
  return `${head} · ${movies.value.length} 部影片${actorPart}`
})

/** 老实现：只有 >60 字才截断（`(mv.title || '').slice(0, 60)` 是无条件 slice，这里照抄）。 */
function titleText(movie: SearchMovie): string {
  return String(movie.title || '').slice(0, 60)
}

/** 把结果封面预热一遍（老 `preload(movies.map(x => x.thumb))`）。 */
function preload(list: SearchMovie[]): void {
  list.forEach(movie => {
    const url = String(movie.thumb || '')
    if (!url) return
    const image = new Image()
    image.decoding = 'async'
    image.src = url
  })
}

/**
 * 搜一次（老 `doSearch(kw)`）：
 * `GET plugin/search?keyword=` → `{movies, actors}`。
 *
 * 业务失败与传输失败折成同一句提示（老实现那两条分支的最后落点都是 `errHtml`）。
 */
async function search(raw: string): Promise<void> {
  const kw = String(raw || '').trim()
  if (!kw) return
  keyword.value = kw
  loading.value = true
  error.value = ''
  try {
    const api = props.api
    if (!api || typeof api.get !== 'function') {
      error.value = '宿主请求器不可用'
      return
    }
    const res: any = await api.get('plugin/search', { params: { keyword: kw } })
    const payload = res && typeof res === 'object' && 'data' in res ? res.data : res
    if (payload && typeof payload === 'object' && payload.success === false) {
      error.value = String(payload.message || payload.detail || '搜索失败，请稍后重试')
      return
    }
    const rawMovies = Array.isArray(payload?.movies) ? payload.movies : []
    const rawActors = Array.isArray(payload?.actors) ? payload.actors : []
    movies.value = rawMovies.filter((item: any) => item && typeof item === 'object')
    actors.value = rawActors
      .filter((item: any) => item && typeof item === 'object' && item.name)
      .map((item: any) => ({
        name: String(item.name || ''),
        zh: String(item.zh || ''),
        avatar: String(item.avatar || ''),
      }))
    searched.value = true
    preload(movies.value)
  } catch (err) {
    // 老 `apiGet` 把传输失败折成一句返回值 → 照样进 errHtml；这里同一落点。
    const status = Number((err as any)?.response?.status || (err as any)?.status || 0)
    error.value = status ? `请求失败（HTTP ${status}）` : errorText(err)
  } finally {
    loading.value = false
  }
}

/** 弹窗关闭：老 `closeAll()` 会把 `#modal` 的 wide 与内容一起收起；这里把结果清掉，下次重搜。 */
function reset(): void {
  loading.value = false
  error.value = ''
  movies.value = []
  actors.value = []
  searched.value = false
}

watch(
  () => props.open,
  value => {
    // 关掉时清空；打开时**不要**清（壳紧接着就调 `search()`，清了会把它的结果抹掉）。
    if (!value) reset()
  },
)

/** 错误态「重试」：老 `#sRetry` → `doSearch(kw)`。 */
function retry(): void {
  void search(keyword.value)
}

function pickMovie(movie: SearchMovie): void {
  emit('openMovie', { number: String(movie.number || ''), id: String(movie.id || '') })
}

function pickActor(name: string): void {
  if (name) emit('openActor', name)
}

defineExpose({ search })
</script>

<template>
  <v-dialog
    :model-value="open"
    max-width="920"
    scrollable
    attach="body"
    @update:model-value="(value: boolean) => { if (!value) emit('close') }"
  >
    <v-card>
      <v-card-title class="d-flex align-center">
        <span class="avh-search__title">{{ title }}</span>
        <v-spacer />
      </v-card-title>

      <v-card-text>
        <div v-if="loading" class="avh-search__loading">正在搜索…</div>

        <ErrorState v-else-if="error" :message="error" :retrying="loading" @retry="retry" />

        <template v-else>
          <!-- 演员区（老实现：`<div class="hint">演员</div>` + `.actors` 网格） -->
          <template v-if="actors.length">
            <div class="avh-search__secttl avh-hint">演员</div>
            <div class="avh-actors avh-search__actors">
              <ActorRow
                v-for="actor in actors"
                :key="actor.name"
                :name="String(actor.name || '')"
                :zh="actor.zh || ''"
                :avatar="actor.avatar || ''"
                :plugin-id="pluginId"
                @select="pickActor"
              />
            </div>
          </template>

          <!-- 影片区（老实现：`.searchrow`） -->
          <div v-if="searched" class="avh-search__secttl avh-hint">影片</div>
          <div
            v-for="(movie, index) in movies"
            :key="`${movie.number}#${index}`"
            class="avh-searchrow"
            :title="movie.title || movie.number || ''"
            @click="pickMovie(movie)"
          >
            <div class="avh-searchrow__mini">
              <Thumb variant="mini" :src="movie.thumb" :alt="String(movie.number || '')" :plugin-id="pluginId" />
            </div>
            <div class="avh-searchrow__main">
              <div class="avh-searchrow__num">{{ movie.number }}</div>
              <div class="avh-searchrow__sub avh-hint">
                <span>{{ movie.actor || '—' }} · {{ movie.date || '' }} · 🧲 {{ movie.magnets || 0 }}</span>
                <span v-if="movie.cnsub" class="avh-tag avh-tag--on">中字</span>
                <span v-if="movie.uncensored" class="avh-tag avh-tag--uc">破解</span>
                <span v-if="movie.lib" class="avh-tag avh-tag--lib">已入库</span>
              </div>
              <div class="avh-searchrow__ttl avh-hint">{{ titleText(movie) }}</div>
            </div>
            <span class="avh-hint">查看 ›</span>
          </div>
          <div v-if="searched && !movies.length" class="avh-hint">没有匹配的影片</div>

          <EmptyState v-if="!searched" text="输入番号或演员名后点「搜索」" />
        </template>
      </v-card-text>

      <v-card-actions>
        <v-spacer />
        <v-btn color="error" variant="outlined" @click="emit('close')">关闭</v-btn>
      </v-card-actions>
    </v-card>
  </v-dialog>
</template>

<style scoped>
.avh-hint {
  font-size: 12px;
  color: rgba(var(--v-theme-on-surface), 0.5);
}

.avh-search__title {
  font-size: 16px;
  font-weight: 600;
}

/* 老 `.loading` */
.avh-search__loading {
  padding: 44px 20px;
  text-align: center;
  font-size: 13px;
  color: rgba(var(--v-theme-on-surface), 0.5);
}

/* 老实现的内联 `margin-bottom:8px` / `margin-bottom:16px` */
.avh-search__secttl {
  margin-bottom: 8px;
}

/* 老实现把弹窗里的演员网格收窄到 110px（主界面是 136px） */
.avh-search__actors {
  display: grid;
  gap: 12px;
  grid-template-columns: repeat(auto-fill, minmax(110px, 1fr));
  margin-bottom: 16px;
}

/* 老 `.searchrow` */
.avh-searchrow {
  display: flex;
  gap: 10px;
  align-items: center;
  padding: 9px 12px;
  margin-bottom: 8px;
  cursor: pointer;
  border: 1px solid rgba(var(--v-theme-on-surface), 0.12);
  border-radius: 8px;
  background: rgba(var(--v-theme-on-surface), 0.04);
}

.avh-searchrow:hover {
  border-color: rgb(var(--v-theme-primary));
}

/* 老 `.searchrow .mini`：74×100 竖版小图 */
.avh-searchrow__mini {
  width: 74px;
  height: 100px;
  flex: none;
  overflow: hidden;
  border-radius: 6px;
}

.avh-searchrow__mini :deep(.avh-thumb) {
  height: 100%;
}

.avh-searchrow__main {
  flex: 1;
  min-width: 0;
}

.avh-searchrow__num {
  font-weight: 700;
}

.avh-searchrow__sub {
  display: flex;
  gap: 4px;
  flex-wrap: wrap;
  align-items: center;
  margin-top: 3px;
}

.avh-searchrow__ttl {
  margin-top: 2px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

/* `.tag` / `.tag.on` / `.tag.uc` / `.tag.lib` 的等价样式（老 `app.css` 同名规则） */
.avh-tag {
  display: inline-block;
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
  background: rgba(var(--v-theme-secondary), 0.3);
  color: rgb(var(--v-theme-on-surface));
}

.avh-tag--lib {
  border-color: rgba(var(--v-theme-primary), 0.5);
  background: rgba(var(--v-theme-primary), 0.22);
  color: rgb(var(--v-theme-on-surface));
}
</style>
