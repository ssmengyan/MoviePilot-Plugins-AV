/**
 * 老实现 `ui/views/actors.js` 的 `cssUrl()`：把会破坏 CSS `url()` 的字符转义掉。
 *
 * 用在"同图模糊底"上（老 `.shot::before` / `.film .pic::before` 的 `--bg`）：
 * 图床地址里带 `'`、`(`、`)`、空格时，`url('…')` 会被提前截断，模糊底整块失效。
 *
 * 单独成文件是因为两个视图都要用它（作品史封面与详情预览图），
 * 逐字照抄老实现，**不要**顺手改成 `encodeURI` 或 `CSS.escape`。
 */
export function cssUrl(value: unknown): string {
  return String(value || '').replace(/["'()\\\s]/g, char => encodeURIComponent(char))
}
