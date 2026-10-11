<script setup lang="ts">
/**
 * 演员行 / 演员卡（头像 + 艺名 + 中文名 + 收藏态）。
 *
 * 对应老实现 `views/actors.js` 的**两处同一结构**：
 * 1. `renderActors()` 的「我的演员」卡片 —— 右上角 `⭐`、点击进作品史；
 * 2. `openActorPicker()` 的「从演员榜挑选」卡片 —— 无星标、点击就地加收藏，
 *    已收藏的换成 `<span class="tag on">✓ 已收藏</span>`。
 *
 * DOM/文案逐字对齐：
 * ```
 * <div class="actor">
 *   <div class="star">⭐</div>
 *   <div class="av"><img …><div class="noimg">名字</div></div>
 *   <div class="nm">{name}</div><div class="zh">{zh}</div>
 *   <div style="margin-top:6px"><span class="tag">➕ 收藏</span></div>   <!-- 仅挑选态 -->
 * </div>
 * ```
 * 差异：老实现用 `data-n`/`data-av`/`data-zh` + 事件委托，Vue 里改成 props + emit，
 * 行为（点卡片 = 打开作品史 / 加收藏）不变。
 */
import Thumb from './Thumb.vue'

const props = withDefaults(
  defineProps<{
    /** 艺名（后端 `name`）。 */
    name: string
    /** 中文名（后端 `zh`，可能为空）。 */
    zh?: string
    /** 头像地址（后端 `avatar`，通常是插件图片代理地址）。 */
    avatar?: string
    /** 本插件实例 id（传给 Thumb 拼图片代理）。 */
    pluginId?: string
    /** 已收藏：显示右上角 `⭐`；挑选态下换成「✓ 已收藏」标签。 */
    favorited?: boolean
    /** 挑选态（演员榜弹窗：可点「➕ 收藏」）；否则是「我的演员」卡片。 */
    picker?: boolean
    /** 就地加收藏正在飞（挑选态：禁用并转圈）。 */
    adding?: boolean
  }>(),
  {
    zh: '',
    avatar: '',
    pluginId: '',
    favorited: false,
    picker: false,
    adding: false,
  },
)

const emit = defineEmits<{
  /** 点卡片：`picker` 时是"加入收藏"，否则是"打开作品史"。 */
  (event: 'select', name: string): void
  /** 挑选态点「➕ 收藏」（与 select 同一个动作，分开是为了后续想加二次确认时不改调用点）。 */
  (event: 'add', name: string): void
}>()

function onSelect(): void {
  if (props.picker && props.favorited) return
  if (props.picker) {
    emit('add', props.name)
    return
  }
  emit('select', props.name)
}
</script>

<template>
  <div
    class="avh-actor"
    :class="{ 'avh-actor--picker': picker, 'avh-actor--faved': picker && favorited }"
    :title="name"
    @click="onSelect"
  >
    <div v-if="!picker && favorited" class="avh-actor__star">⭐</div>
    <Thumb
      class="avh-actor__av"
      variant="av"
      :src="avatar"
      :alt="name"
      :plugin-id="pluginId"
    />
    <div class="avh-actor__nm">{{ name }}</div>
    <div class="avh-actor__zh">{{ zh || '' }}</div>
    <div v-if="picker" class="avh-actor__tag">
      <span class="avh-tag" :class="favorited ? 'avh-tag--on' : ''">
        {{ favorited ? '✓ 已收藏' : '➕ 收藏' }}
      </span>
    </div>
  </div>
</template>

<style scoped>
/* 对齐 `app.css` 的 `.actor`（网格由父级 `.actors` 提供，这里只画卡片本身） */
.avh-actor {
  position: relative;
  padding: 12px 10px;
  text-align: center;
  cursor: pointer;
  border: 1px solid rgba(var(--v-theme-on-surface), 0.12);
  border-radius: 10px;
  background: rgb(var(--v-theme-surface));
  transition: 0.15s;
}

.avh-actor:hover {
  border-color: rgb(var(--v-theme-secondary));
  transform: translateY(-2px);
}

.avh-actor__star {
  position: absolute;
  right: 8px;
  top: 8px;
  font-size: 14px;
}

.avh-actor__av {
  width: 76px;
  height: 76px;
  margin: 0 auto 8px;
  border-radius: 50%;
  overflow: hidden;
  border: 2px solid rgba(var(--v-theme-on-surface), 0.12);
}

.avh-actor__nm {
  font-size: 13px;
  font-weight: 600;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.avh-actor__zh {
  min-height: 16px;
  font-size: 11px;
  color: rgba(var(--v-theme-on-surface), 0.5);
}

.avh-actor__tag {
  margin-top: 6px;
}

/* `.tag` / `.tag.on` 的等价样式（老 `app.css` 同名规则） */
.avh-tag {
  display: inline-block;
  margin-right: 4px;
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

/* 已收藏的挑选卡：不再有可点感（老实现 `cursor:default` + 解绑 onclick） */
.avh-actor--faved {
  cursor: default;
}

.avh-actor--faved:hover {
  transform: none;
  border-color: rgba(var(--v-theme-on-surface), 0.12);
}

.avh-actor--picker {
  cursor: pointer;
}
</style>
