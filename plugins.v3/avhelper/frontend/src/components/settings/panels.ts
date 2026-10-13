/**
 * 设置台栏目清单（设计文档 §4）。
 *
 * 单独一个 `.ts` 而不写在 `Console.vue` 里：`useSettingsDraft` 也要用它判断
 * 「该栏目是否持有草稿字段」（`dirtyMarker`），两处必须同一份来源。
 */
export interface SectionItem {
  key: string
  title: string
  icon: string
}

/** 设置台七栏（「常规」是本轮新增：切 `vue` 模式后宿主不再画 JSON 配置表单）。 */
export const SETTINGS_SECTIONS: SectionItem[] = [
  { key: 'general', title: '常规', icon: 'mdi-cog-outline' },
  { key: 'sites', title: '搜索站点', icon: 'mdi-web' },
  { key: 'rule', title: '下载规则', icon: 'mdi-filter-cog' },
  { key: 'notify', title: '通知', icon: 'mdi-bell' },
  { key: 'library', title: '媒体库', icon: 'mdi-server' },
  { key: 'runtime', title: '运行与缓存', icon: 'mdi-database-cog' },
  { key: 'about', title: '关于', icon: 'mdi-information-outline' },
]

/**
 * 各栏目「算不算脏」看的是自己那部分草稿，避免在某栏改了东西、
 * 切到别的栏看不到未保存标记。通知/关于两栏没有草稿字段。
 * （「运行与缓存」0.6.3 起有宿主配置字段 `cache_max_gb`，所以归 host 组。）
 */
export const DIRTY_GROUPS: Record<string, 'none' | 'rule' | 'host' | 'both'> = {
  general: 'host',
  sites: 'rule',
  rule: 'rule',
  notify: 'none',
  library: 'host',
  runtime: 'host',
  about: 'none',
}
