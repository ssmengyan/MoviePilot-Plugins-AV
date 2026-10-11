<script setup lang="ts">
/**
 * 番号卡片（封面 + 番号 + 演员 + 日期 + 时长 + 「中字/破解/已入库」标记 + 磁力数）。
 *
 * 对应老实现 `views/discover.js` 的 `card(mv)`（`app.css` 的 `.card` / `.thumb` /
 * `.badges` / `.badge.*` / `.meta`）。文案与标记顺序逐字对齐：
 * ```
 * <div class="card" data-num data-id>
 *   <div class="thumb">
 *     <img …><div class="noimg">番号</div>
 *     <div class="badges">
 *       [中字] [破解] [⭐已收藏演员] [✔已入库]
 *     </div>
 *   </div>
 *   <div class="meta">
 *     <div class="num">{番号}</div>
 *     <div class="sub"><span>{演员或 —}</span><span>🧲 {磁力数}</span></div>
 *     <div class="sub"><span>{日期}</span><span>{时长}′</span></div>
 *   </div>
 * </div>
 * ```
 * 差异：老实现用 `data-num`/`data-id` + `bindCards()` 绑点击与悬停预热详情，
 * Vue 里改成 `select` / `hover` 事件（`hover` 供详情预热用），字段与文案不变。
 */
import Thumb from './Thumb.vue'

/** 卡片数据：`/rankings` 的 `movies[]` 与 `/detail` 的 `movie` 同shape（后端 `_movie()`）。 */
export interface CardMovie {
  number?: string
  title?: string
  thumb?: string
  cover?: string
  date?: string
  /** 分钟数（后端是 int，0 表示没解析到）。 */
  duration?: number | string
  cnsub?: boolean
  uncensored?: boolean
  /** 磁力条数。 */
  magnets?: number
  actor?: string
  /** javdb 内部 id（打开详情时回传，能省一次跳转）。 */
  id?: string
  /** 已在 Emby 库中时是对象 `{id,name,path,url}`，否则没有该字段。 */
  lib?: { id?: string; name?: string; path?: string; url?: string } | null
}

const props = withDefaults(
  defineProps<{
    movie: CardMovie
    /** 本插件实例 id（传给 Thumb 拼图片代理）。 */
    pluginId?: string
    /** 演员已在「我的演员」里：加一个 `⭐已收藏演员` 角标（老实现 `merged`）。 */
    actorFavorited?: boolean
  }>(),
  { pluginId: '', actorFavorited: false },
)

const emit = defineEmits<{
  /** 点卡片：把番号与 javdb id 交出去（对应老 `openMovie(num, id)`）。 */
  (event: 'select', payload: { number: string; id: string }): void
  /** 鼠标进入卡片：供调用方预热详情（老 `bindCards` 的 `onmouseenter`）。 */
  (event: 'hover', payload: { number: string; id: string }): void
}>()

const number = () => String(props.movie.number || '')
const id = () => String(props.movie.id || '')

/** 时长：老实现 `mv.duration ? esc(mv.duration) + '′' : ''`（0 与空串都不显示）。 */
const durationText = () => {
  const value = props.movie.duration
  return value ? `${value}′` : ''
}
</script>

<template>
  <div
    class="avh-card"
    :title="movie.title || number()"
    @click="emit('select', { number: number(), id: id() })"
    @mouseenter="emit('hover', { number: number(), id: id() })"
  >
    <div class="avh-card__thumb">
      <Thumb variant="thumb" :src="movie.thumb" :alt="number()" :plugin-id="pluginId" />
      <div class="avh-card__badges">
        <span v-if="movie.cnsub" class="avh-badge avh-badge--cn">中字</span>
        <span v-if="movie.uncensored" class="avh-badge avh-badge--uc">破解</span>
        <span v-if="actorFavorited" class="avh-badge avh-badge--new">⭐已收藏演员</span>
        <span v-if="movie.lib" class="avh-badge avh-badge--lib">✔已入库</span>
      </div>
    </div>
    <div class="avh-card__meta">
      <div class="avh-card__num">{{ number() }}</div>
      <div class="avh-card__sub">
        <span>{{ movie.actor || '—' }}</span>
        <span>🧲 {{ movie.magnets || 0 }}</span>
      </div>
      <div class="avh-card__sub">
        <span>{{ movie.date || '' }}</span>
        <span>{{ durationText() }}</span>
      </div>
    </div>
  </div>
</template>

<style scoped>
/* 对齐 `app.css` 的 `.card`（网格列由父级 `.grid` 提供） */
.avh-card {
  display: flex;
  flex-direction: column;
  overflow: hidden;
  cursor: pointer;
  border: 1px solid rgba(var(--v-theme-on-surface), 0.12);
  border-radius: 10px;
  background: rgb(var(--v-theme-surface));
  transition: 0.15s;
}

.avh-card:hover {
  border-color: rgb(var(--v-theme-primary));
  transform: translateY(-2px);
}

/* `.thumb`：3:4 竖版封面 + 渐变底（缺图时不至于一片死黑） */
.avh-card__thumb {
  position: relative;
  aspect-ratio: 3 / 4;
  overflow: hidden;
}

/*
 * 让内层 `Thumb` 撑满这 3:4 的盒子。
 *
 * 老实现的 `.thumb img{width:100%;height:100%;object-fit:cover}` 与
 * `.thumb .noimg{position:absolute;inset:0;...}` 都挂在**同一个** 3:4 容器上；
 * 通用件 `Thumb` 自己不带高度（形态由使用方决定），不补这一条就会出现两个偏差：
 *   1. 封面按自身比例渲染（竖图 2:3 比盒子高、横图 3:2 比盒子矮），
 *      `object-fit:cover` 形同虚设 —— 老实现是"永远铺满 3:4 并裁切"；
 *   2. 缺图时 `.noimg` 是 `inset:0` 的绝对定位盒，父级零高 → 番号占位**看不见**
 *      （老实现会把番号画在封面位置上）。
 */
.avh-card__thumb :deep(.avh-thumb) {
  height: 100%;
}

.avh-card__badges {
  position: absolute;
  left: 6px;
  top: 6px;
  display: flex;
  gap: 4px;
  flex-wrap: wrap;
}

/* `.badge` 系列：底色走主题语义色 + 半透明，不写死深色值 */
.avh-badge {
  padding: 1px 6px;
  font-size: 10px;
  border-radius: 4px;
  color: #fff;
  border: 1px solid rgba(255, 255, 255, 0.14);
  background: rgba(0, 0, 0, 0.6);
}

.avh-badge--cn {
  background: rgba(var(--v-theme-success), 0.85);
}

.avh-badge--uc {
  background: rgba(var(--v-theme-secondary), 0.85);
}

.avh-badge--new {
  background: rgba(var(--v-theme-warning), 0.85);
}

.avh-badge--lib {
  background: rgba(var(--v-theme-primary), 0.85);
}

.avh-card__meta {
  padding: 8px 9px 10px;
}

.avh-card__num {
  font-size: 13px;
  font-weight: 700;
}

.avh-card__sub {
  display: flex;
  justify-content: space-between;
  gap: 6px;
  margin-top: 3px;
  font-size: 11px;
  color: rgba(var(--v-theme-on-surface), 0.5);
}

.avh-card__sub span {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
</style>
