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
 *
 * 差异 2（下载历史契约 §5.2，老实现没有）：徽标末尾多一颗 `[✔已下载]`。
 * 上面那四颗的顺序**不动**（中字 → 破解 → ⭐已收藏演员 → ✔已入库），新徽标排在最后。
 * 只在 `downloaded && !lib` 时画：已经在 Emby 库里的片子看「✔已入库」就够了，
 * 两颗都画反而是同一件事说两遍（投放条件见模板里的注释）。
 *
 * 差异 3（2026-10-12 加，`mode="library"`）：给「已入库的番号」栏用的库卡片。
 * 那一栏的数据来自 Emby 库本身（`/library`），**没有** javdb 的磁力数 / 发行日 / 时长，
 * 照榜单那两行画就会是「🧲 0 · 空日期」。所以库模式换两行：
 * ```
 * 第二行：{演员或 —}              {入库 2026-10-09}
 * 第三行：{库内文件名，超长省略号}  [▶ 观看]（直达 Emby 观看地址的新标签页链接）
 * ```
 * 卡片本体在两种模式下**都是**"点开在线详情"，与发现榜单完全一致（用户对「已入库的番号」
 * 的要求就是"参考发现榜单的列表形式和功能逻辑"）；「观看」是卡片上多出来的一条直达路径，
 * 满足"点击可直接跳转到对应的 MB 观看地址"。
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
  /**
   * 番号在下载台账里且已完成下载（后端 `_movie()` 的 `downloaded`，契约 §5.2）。
   *
   * 与 `lib` 的区别：`lib` = 此刻 Emby 库里真有这部片；`downloaded` = 下载台账里记过这个番号，
   * **文件可能已经被删**（台账不因文件消失而消失，这正是它存在的意义）。
   */
  downloaded?: boolean
  /**
   * 入库时间（Emby 的 `DateCreated`，本地时间写法；`/library` 的 `addedAt`）。
   * 只有库模式会画它，其它来源的卡片没有这个字段。
   */
  addedAt?: string
}

const props = withDefaults(
  defineProps<{
    movie: CardMovie
    /** 本插件实例 id（传给 Thumb 拼图片代理）。 */
    pluginId?: string
    /** 演员已在「我的演员」里：加一个 `⭐已收藏演员` 角标（老实现 `merged`）。 */
    actorFavorited?: boolean
    /**
     * 卡片形态：`rank` = 榜单/演员作品史/搜索（老实现原样），
     * `library` = 「已入库的番号」栏（见文件头差异 3）。默认 `rank`，别的调用方一行都不用改。
     */
    mode?: 'rank' | 'library'
  }>(),
  { pluginId: '', actorFavorited: false, mode: 'rank' },
)

const emit = defineEmits<{
  /** 点卡片：把番号与 javdb id 交出去（对应老 `openMovie(num, id)`）。 */
  (event: 'select', payload: { number: string; id: string }): void
  /** 鼠标进入卡片：供调用方预热详情（老 `bindCards` 的 `onmouseenter`）。 */
  (event: 'hover', payload: { number: string; id: string }): void
}>()

const number = () => String(props.movie.number || '')
const id = () => String(props.movie.id || '')

/** 是不是库模式（「已入库的番号」栏）。 */
const library = () => props.mode === 'library'

/** 时长：老实现 `mv.duration ? esc(mv.duration) + '′' : ''`（0 与空串都不显示）。 */
const durationText = () => {
  const value = props.movie.duration
  return value ? `${value}′` : ''
}

/** 入库时间：只画到日（`2026-10-05 12:34:56` → `入库 2026-10-05`）；拿不到就不画这一段。 */
const addedText = () => {
  const day = String(props.movie.addedAt || '').slice(0, 10)
  return day ? `入库 ${day}` : ''
}

/** 库内文件名：`/media/9kg/avi/IPZZ-961.mp4` → `IPZZ-961.mp4`（两种斜杠都认）。 */
const fileName = () => String(props.movie.lib?.path || '').replace(/\\/g, '/').split('/').pop() || ''

/** Emby 观看地址（`lib.url`）；没有就整颗「观看」不画。 */
const watchUrl = () => String(props.movie.lib?.url || '')
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
        <!--
          「已下载」（契约 §5.2）：`downloaded && !lib` 才画 —— 在库的片子上面那颗已经说明白了，
          重复标记只会让用户以为自己漏看了什么。徽标顺序：前四颗保持老实现原样，这颗排最末。
        -->
        <span v-if="movie.downloaded && !movie.lib" class="avh-badge avh-badge--dl">✔已下载</span>
      </div>
    </div>
    <div class="avh-card__meta">
      <div class="avh-card__num">{{ number() }}</div>
      <div class="avh-card__sub">
        <span>{{ movie.actor || '—' }}</span>
        <!-- 库模式第二行右侧是入库时间；榜单模式下仍是磁力条数（老实现口径，一颗都不改） -->
        <span v-if="library()">{{ addedText() }}</span>
        <span v-else>🧲 {{ movie.magnets || 0 }}</span>
      </div>
      <div class="avh-card__sub">
        <template v-if="library()">
          <!-- 库内文件名：`title` 给完整路径，判断"是不是同一部片"时不用点进去 -->
          <span :title="String(movie.lib?.path || '')">{{ fileName() }}</span>
          <!--
            「▶ 观看」：直达 Emby 观看地址（`lib.url`，详情页那颗「在 Emby 中打开」同一个地址）。
            用 `<a target="_blank">` 而不是 `window.open`：中键/右键新标签页、悬停看地址、
            弹窗拦截器都按标准链接处理；`@click.stop` 保证不会连带触发卡片的"点开详情"。
          -->
          <a
            v-if="watchUrl()"
            class="avh-card__watch"
            :href="watchUrl()"
            target="_blank"
            rel="noopener"
            title="在 Emby（MB）里观看"
            @click.stop
          >▶ 观看</a>
        </template>
        <template v-else>
          <span>{{ movie.date || '' }}</span>
          <span>{{ durationText() }}</span>
        </template>
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

/*
 * 「已下载」为什么**不复用** `--lib` 的 `primary`：
 * 两颗徽标虽然互斥（`downloaded && !lib`），但说的是两件事 —— `primary` 那颗＝此刻真的在 Emby 库里，
 * 这颗＝下载台账里记过（文件可能已删）。同色会让人扫一眼分不清看到的是哪一颗，
 * 而"库里没有、但下载过"恰恰是最需要一眼认出来的情形（防重复下载）。
 * 取 `info`：与 `primary` 同属冷色、明度接近，落在同一批卡片上既不抢眼又能区分；
 * 其余四颗已占用 success / secondary / warning / primary，`info` 是唯一没被用掉的语义色。
 */
.avh-badge--dl {
  background: rgba(var(--v-theme-info), 0.85);
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

/*
 * 「▶ 观看」（库模式）：一颗小链接，样式走主色、不抢番号与徽标的注意力。
 * 它**不**继承 `.avh-card__sub span` 的省略号（那条只管 `span`）：链接要整体可见、
 * 不许被压缩，所以 `flex: none`；文件名那一格才吃剩余宽度。
 */
.avh-card__watch {
  flex: none;
  font-size: 11px;
  color: rgb(var(--v-theme-primary));
  text-decoration: none;
  white-space: nowrap;
}

.avh-card__watch:hover {
  text-decoration: underline;
}
</style>
