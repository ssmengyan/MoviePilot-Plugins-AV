/* AVHelper · 图片：<img> 生成、失败占位与预加载（保留 no-referrer 纪律）
 * 由 webui.html 原主脚本按块搬移（调用点零改写）；跨模块引用走 ES module 具名导入。 */
import { esc } from '../core/util.js';


/* 图片：加载失败时隐藏自身并显示相邻的 .noimg 占位 */
export function imgTag(url, cls, alt){
  return '<img ' + (cls ? 'class="' + cls + '" ' : '') + 'src="' + esc(url || '') + '" alt="' + esc(alt || '') + '" loading="lazy" decoding="async"'
    + ' onerror="this.style.display=\'none\';this.nextElementSibling&&(this.nextElementSibling.style.display=\'flex\')">';
}
export function imgWithPlaceholder(url, alt, cls){
  return imgTag(url, cls, alt) + '<div class="noimg" style="display:none">' + esc(alt || '无图') + '</div>';
}
export const preload = urls => urls.forEach(u => { if (u) { const im = new Image(); im.decoding = 'async'; im.src = u; } });
export const IMG_FALLBACK = 'data:image/svg+xml;charset=utf-8,' + encodeURIComponent(
  '<svg xmlns="http://www.w3.org/2000/svg" width="300" height="400"><rect width="100%" height="100%" fill="#1c232d"/>' +
  '<text x="50%" y="50%" fill="#6b7887" font-size="16" text-anchor="middle">图片加载失败</text></svg>');
