/**
 * 只放行 http(s) 的外部链接（0.9.3 B3）。
 *
 * 界面上的动态链接（候选发布页 `_page_url`、Emby 观看地址 `lib.url`）都是后端 / 站点给的
 * 字符串，直接绑到 `:href` 时 `javascript:`、`data:` 就变成一个可点的执行面。统一走这里：
 * 拿不到合法地址就返回空串，模板里按「没有链接」处理（`v-if` 不画那颗入口）。
 *
 * 口径与老的 `CandTable.postUrl()` 一致：**只认绝对 http(s)**，相对地址一律不认
 * （相对地址在插件弹窗里会指到 MoviePilot 自己的页面，点了是个 404）。
 */
export function safeUrl(value: unknown): string {
  const raw = String(value ?? '').trim()
  if (!raw) return ''
  return /^https?:\/\//i.test(raw) ? raw : ''
}
