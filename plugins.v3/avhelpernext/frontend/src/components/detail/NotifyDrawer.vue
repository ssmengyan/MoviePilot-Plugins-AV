<script setup lang="ts">
/**
 * 通知抽屉（老实现 `ui/views/notify.js` 的 `notifyBodyHtml()` / `openNotify()` +
 * `ui/index.html` 的 `#bellBtn` / `#ndrawer` / `#nClear` / `#nClose`）。
 *
 * 放在 `detail/` 的理由：它和 `DetailDrawer.vue` 是**同一类东西** —— 壳持有的右侧浮层
 * （老实现里两个 `<aside class="drawer">` 就在 `ui/index.html` 根层级的相邻两行），
 * 抽屉宽度也一样由 `v-navigation-drawer` 的 `width` 给出（老 `.drawer.ndrawer{width:min(470px,96vw)}`）。
 * 没有单独开 `components/notify/` 目录：这里只有这一个组件，为它单开一层目录
 * 反而会让"浮层都在 detail/"这条现成规律多出一个例外。
 *
 * 逐条对齐老 `notifyBodyHtml()`（文案一字不改）：
 *
 * | 老实现 | 这里 |
 * | --- | --- |
 * | `openNotify()`：关详情抽屉/弹窗 → 清空 `#nBody` 滚动位置 → 显示遮罩 + `#ndrawer` | `:model-value="open"` 的 `v-navigation-drawer`（`temporary` 自带遮罩）；每次打开把正文滚回顶部（同一个"新开的一张"语义） |
 * | 打开即 `loadNotices(false)` → 成功才 `noticeMarkSeen()` + `renderPills()`（角标清零） | 列表来自壳的 store（`/bootstrap` 15s 轮询已经在拉，**不新开轮询**）；`open` 变真时 `markNoticesSeen()` 上移位点 → 角标归零 |
 * | 拉不到只静默（`force=false` 时不 toast），界面照画上一份快照 | 同：只画 store 里已有的快照，不额外报错 |
 * | 条目：`<div class="msg ok\|warn\|">` + `<div class="ico">🤖</div>` + `.bub`（`.h` 头、可选标题、`.b` 正文、可选 `.meta-line`、可选图片、`.f` 时间） | 同一结构、同一顺序、同一字段；`kind` 只认 `ok`/`warn`，其余走中性（老实现同一套映射） |
 * | `.h` 文案：`'MoviePilot · ' + esc(n.type \|\| '系统消息')` | 同一句（`type` 缺省 `系统消息`） |
 * | 标题：`n.title ? <div style="font-weight:600;font-size:13px;margin-bottom:2px">esc(n.title)</div> : ''` | 同一句、同一样式、同样"没有就不画" |
 * | 正文 `.b`：`esc(n.body \|\| '')`，CSS `white-space:pre-line` | 同一字段 + `pre-line`（换行照旧保留） |
 * | `.meta-line`：`n.meta ? esc(n.meta) : ''` | 同 |
 * | 图片：`n.image ? imgTag(n.image,'','主图') + <div class="noimg" style="display:none">主图加载失败</div> : ''` | 同一条链走 `common/Thumb.vue`（`referrerpolicy="no-referrer"` + **直连失败才**回落 `/img` 代理），占位文案沿用 `主图加载失败` |
 * | `.f`：`esc(shortTime(n.time))` | 同（`storeTypes.shortTime`，ISO 才裁剪成 `YYYY-MM-DD HH:MM`） |
 * | 空态：`<div class="empty">暂无通知</div>` | `common/EmptyState.vue` 同一句话（同一个 `.empty` 样式源） |
 * | `#nClear`：`apiDelete('/notices')` → 成功 `toast('已清空','通知已清空','ok')`、`S.notices=[]`、重画；失败 `toast('清空失败', message,'warn')` | 按钮在抽屉头部（同一个位置），弹**宿主确认**（`moviepilot:confirm`，拿不到降级 `window.confirm`）后由壳调 `store.clearNotices()`；成功/失败各一句 toast |
 * | `#nClose` → `closeAll()`；`Escape` 由全局 keydown 关掉 `#ndrawer` | 「关闭」按钮 `emit('close')`；Esc 由 `v-navigation-drawer` 自己处理（`DetailDrawer` 同款） |
 *
 * 与老实现的**行为差异**（都在报告里列了）：
 * 1. 老实现点「清空」**没有二次确认**（`app.js` 直接 `apiDelete`），这里按任务要求加宿主确认
 *    —— 与设置台「清空通知」（`Console.vue` 的 `clearNotices()`）同一套；
 * 2. 老实现每次打开都 `GET /notices`；这里**不新开请求**，用 `/bootstrap` 15s 轮询带回的同一份
 *    `store.notices`（任务约定："不要再新开轮询"）。第一帧就画，没有 `加载中…` 那一下；
 * 3. 图片回落链比老实现多一跳：老实现直连失败直接给「主图加载失败」，这里先试插件 `/img` 代理
 *    （`Thumb` 的既有纪律，与详情抽屉/搜索弹窗一致），代理也失败才显示同一句话；
 * 4. 角标与位点：老实现写 `avh.noticesSeen`，这里与设置台统一到
 *    `avhnext.settings.noticesSeen`（`composables/noticesSeen.ts` 一处实现）。
 *
 * **不**做（老实现也没有）：不在抽屉里做已读/未读分色，不逐条删除，不做"全部已读"以外的动作。
 */
import { computed, nextTick, ref, watch } from 'vue'
import EmptyState from '../common/EmptyState.vue'
import Thumb from '../common/Thumb.vue'
import type { NoticeItem } from '../../composables/settingsModel'
import { useHostConfirm } from '../../composables/useHostDialogs'
import { markNoticesSeen } from '../../composables/noticesSeen'
import { shortTime } from '../../composables/storeTypes'

const props = withDefaults(
  defineProps<{
    /** 抽屉是否打开（壳控制；老实现是 `$('#ndrawer').classList.add('on')`）。 */
    open?: boolean
    /** 通知列表：壳的 `store.notices`（与 `/bootstrap` 同一份数据）。 */
    notices?: NoticeItem[]
    /** 本插件实例 id：给 `Thumb` 拼图片代理地址用。 */
    pluginId?: string
    /** 「清空」请求在跑（确认框关闭后到请求结束之间的按钮态）。 */
    clearing?: boolean
  }>(),
  { open: false, notices: () => [], pluginId: '', clearing: false },
)

const emit = defineEmits<{
  /** 请求关闭抽屉（老 `#nClose` → `closeAll()`）。 */
  (event: 'close'): void
  /** 「清空」已确认，请求壳执行清空（不可恢复，文案由壳给）。 */
  (event: 'clear'): void
}>()

/** 宿主要求复用的确认弹窗；拿不到时 `useHostConfirm` 内部降级 `window.confirm`。 */
const confirm = useHostConfirm()

/** 正文容器（每次打开滚回顶部，老 `nb.scrollTop = 0`）。 */
const bodyEl = ref<HTMLElement | null>(null)

/**
 * `kind` → 老实现的配色类（`ok` → 绿、`warn` → 黄、其余中性）。
 * 老实现把类名当字符串拼进 HTML，这里换成布尔量给 `:class` 用，映射逐字一致。
 */
function kindOf(item: NoticeItem): 'ok' | 'warn' | '' {
  if (item.kind === 'ok') return 'ok'
  if (item.kind === 'warn') return 'warn'
  return ''
}

/** `.h` 那句：`'MoviePilot · ' + (n.type || '系统消息')`。 */
function headText(item: NoticeItem): string {
  return `MoviePilot · ${item.type || '系统消息'}`
}

/** 「清空」：先过宿主确认（老实现没有这一步，见文件头差异 1），确认后才让壳发请求。 */
async function askClear(): Promise<void> {
  if (props.clearing) return
  const ok = await confirm({
    type: 'warn',
    title: '清空通知',
    content: `将清空全部 ${props.notices.length} 条通知，且无法恢复。确认继续？`,
    confirmText: '清空',
    cancelText: '取消',
  })
  if (!ok) return
  emit('clear')
}

/**
 * 打开即算已读：老 `openNotify()` 是「拉一次 → `noticeMarkSeen()` → `renderPills()`」，
 * 列表照旧全留、只有角标清零。这里数据已在 store 里，直接上移位点即可。
 *
 * 打开时还把正文滚回顶部（老 `nb.scrollTop = 0`）；`nextTick` 是因为此刻抽屉可能
 * 刚挂载/刚从 `display:none` 出来，容器高度与 scrollHeight 还没量准。
 */
watch(
  () => props.open,
  value => {
    if (!value) return
    markNoticesSeen(props.notices)
    void nextTick(() => {
      if (bodyEl.value) bodyEl.value.scrollTop = 0
    })
  },
  { immediate: true },
)

/**
 * 抽屉开着的时候来了新通知（`/bootstrap` 轮询带回）：照样算已读，角标不该在
 * 用户眼皮底下重新亮起来 —— 与"打开即已读"同一条语义。
 */
watch(
  () => props.notices,
  list => {
    if (props.open) markNoticesSeen(list)
  },
)

/** 画给模板的时间（老 `shortTime(n.time)`：`''` → `—`）。 */
const rows = computed(() =>
  (props.notices || []).map((item, index) => ({
    key: `${item.time || ''}#${index}`,
    item,
    kind: kindOf(item),
    head: headText(item),
    time: shortTime(item.time),
  })),
)
</script>

<template>
  <!--
    与 `DetailDrawer.vue` 同款的两处细节：
    - `disable-resize-watcher` 必需：Vuetify 的 `VNavigationDrawer` 有一条
      `watch(isTemporary, val => isActive = !val)`，会在 `mobile` 判定第一次落地时
      把**受控**的 `modelValue` 顶成 `true`（详情抽屉实测踩过：1440px 下抽屉一挂载
      就 `--active`，遮罩挡住整页）。关掉它，开关只由壳决定。
    - `temporary` 自带遮罩与 Esc 关闭（等价老 `.scrim.on` + 全局 keydown 的 Escape）。
  -->
  <v-navigation-drawer
    :model-value="open"
    location="right"
    temporary
    disable-resize-watcher
    :width="470"
    class="avh-notify"
    @update:model-value="(value: boolean) => { if (!value) emit('close') }"
  >
    <div class="avh-notify__head">
      <b class="avh-notify__title">🔔 通知</b>
      <div class="avh-notify__spacer" />
      <v-btn
        variant="outlined"
        size="small"
        :disabled="!rows.length"
        :loading="clearing"
        @click="askClear"
      >清空</v-btn>
      <v-btn variant="outlined" size="small" @click="emit('close')">关闭</v-btn>
    </div>

    <div ref="bodyEl" class="avh-notify__body">
      <template v-if="rows.length">
        <div
          v-for="row in rows"
          :key="row.key"
          class="avh-notify__msg"
          :class="row.kind ? `avh-notify__msg--${row.kind}` : ''"
        >
          <div class="avh-notify__ico">🤖</div>
          <div class="avh-notify__bub">
            <div class="avh-notify__h">{{ row.head }}</div>
            <div v-if="row.item.title" class="avh-notify__ttl">{{ row.item.title }}</div>
            <div class="avh-notify__b">{{ row.item.body || '' }}</div>
            <div v-if="row.item.meta" class="avh-notify__meta">{{ row.item.meta }}</div>
            <!-- 图片纪律照抄：总是 `referrerpolicy="no-referrer"`，直连失败才回落 /img；
                 两跳都失败时 `Thumb` 的占位文案就是老实现那句「主图加载失败」。
                 `:lazy="false"`：老实现固定 `loading="lazy"`，但通知列表本来就只有一屏到两屏，
                 惰性加载会让"图片能不能加载"这件事取决于滚动位置（验收时看不见下面几行的图）。
                 eager 化是本组件唯一对 `imgTag` 的偏离，报告里已列。 -->
            <Thumb
              v-if="row.item.image"
              class="avh-notify__img"
              variant="plain"
              :src="row.item.image"
              alt="主图加载失败"
              :plugin-id="pluginId"
              :lazy="false"
            />
            <div class="avh-notify__f">{{ row.time }}</div>
          </div>
        </div>
      </template>

      <!-- 老 `notifyBodyHtml()` 的空态：`<div class="empty">暂无通知</div>` -->
      <EmptyState v-else text="暂无通知" />
    </div>
  </v-navigation-drawer>
</template>

<style scoped>
/* 老 `.drawer .dh` */
.avh-notify__head {
  display: flex;
  align-items: center;
  gap: 12px;
  flex: none;
  padding: 14px 18px;
  border-bottom: 1px solid rgba(var(--v-theme-on-surface), 0.12);
}

.avh-notify__title {
  font-size: 14px;
}

.avh-notify__spacer {
  flex: 1;
}

/* 老 `.drawer .db{overflow:auto;padding:18px}` */
.avh-notify__body {
  flex: 1 1 auto;
  min-height: 0;
  overflow: auto;
  padding: 18px;
  /* 老 `.tg` 是 `max-width:620px` 的容器；抽屉本身只有 470px，这里不必再限宽。 */
}

/* 老 `.msg{display:flex;gap:10px;margin-bottom:14px}` */
.avh-notify__msg {
  display: flex;
  gap: 10px;
  margin-bottom: 14px;
}

/* 老 `.msg .ico`：32px 蓝圆 + 🤖；`.msg.ok .ico` 绿、`.msg.warn .ico` 黄 */
.avh-notify__ico {
  width: 32px;
  height: 32px;
  flex: none;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 50%;
  font-size: 15px;
  background: rgba(var(--v-theme-primary), 0.85);
}

.avh-notify__msg--ok .avh-notify__ico {
  background: rgba(var(--v-theme-success), 0.85);
}

.avh-notify__msg--warn .avh-notify__ico {
  background: rgba(var(--v-theme-warning), 0.85);
}

/* 老 `.msg .bub`：气泡（左上角直角，其余圆角）；`.msg .bub .h` 是 `var(--acc)` 的小标题 */
.avh-notify__bub {
  min-width: 0;
  max-width: 520px;
  padding: 10px 13px;
  border: 1px solid rgba(var(--v-theme-on-surface), 0.12);
  border-radius: 2px 12px 12px 12px;
  background: rgba(var(--v-theme-on-surface), 0.04);
}

.avh-notify__h {
  margin-bottom: 4px;
  font-size: 11px;
  font-weight: 600;
  color: rgb(var(--v-theme-primary));
}

.avh-notify__msg--ok .avh-notify__h {
  color: rgb(var(--v-theme-success));
}

.avh-notify__msg--warn .avh-notify__h {
  color: rgb(var(--v-theme-warning));
}

/* 老实现的内联 `font-weight:600;font-size:13px;margin-bottom:2px` */
.avh-notify__ttl {
  margin-bottom: 2px;
  font-size: 13px;
  font-weight: 600;
}

/* 老 `.msg .bub .b{font-size:13px;white-space:pre-line}` */
.avh-notify__b {
  font-size: 13px;
  white-space: pre-line;
}

/* 老 `.meta-line` */
.avh-notify__meta {
  margin-top: 7px;
  padding: 6px 9px;
  border-radius: 6px;
  font-size: 11.5px;
  line-height: 1.7;
  color: rgba(var(--v-theme-on-surface), 0.7);
  background: rgba(var(--v-theme-on-surface), 0.06);
}

/* 老 `.msg .bub img{width:150px;border-radius:8px;margin-top:8px;display:block}` */
.avh-notify__img {
  width: 150px;
  height: 200px;
  margin-top: 8px;
  border-radius: 8px;
}

.avh-notify__img :deep(img) {
  border-radius: 8px;
}

/* 老 `.msg .bub .f{font-size:11px;color:var(--fg3);margin-top:6px}` */
.avh-notify__f {
  margin-top: 6px;
  font-size: 11px;
  color: rgba(var(--v-theme-on-surface), 0.5);
}
</style>
