/* AVHelperNext · 通用小控件：空态/错误态/骨架/标签页
 * 由 webui.html 原主脚本按块搬移（调用点零改写）；跨模块引用走 ES module 具名导入。 */
import { render } from '../app.js';
import { S } from '../core/state.js';
import { esc } from '../core/util.js';
import { imgWithPlaceholder } from './image.js';
import { findMovie } from '../views/detail.js';

export const loadingHtml = t => '<div class="loading">' + esc(t || '加载中…') + '</div>';
export function errHtml(msg, retryAttr){
  return '<div class="errbox">⚠️ ' + esc(msg || '抓取失败，请稍后重试')
    + (retryAttr ? '<br><br><button class="primary" ' + retryAttr + '>重试</button>' : '') + '</div>';
}
export function emptyHtml(html){ const d = document.createElement('div'); d.className = 'empty'; d.innerHTML = html; return d.innerHTML; }

export function periodTabsHtml(){
  return [['day','日榜'],['week','周榜'],['month','月榜']]
    .map(([p,n]) => '<button data-p="' + p + '" class="' + (S.period === p ? 'on' : '') + '">' + n + '</button>').join('');
}
export function zoneTabsHtml(){
  return [['censored','有码'],['uncensored','无码'],['fc2','FC2']]
    .map(([z,n]) => '<button data-z="' + z + '" class="' + (S.kind === z ? 'on' : '') + '">' + n + '</button>').join('');
}
export function bindTabs(m){
  m.querySelector('#periodTabs').onclick = e => {
    const b = e.target.closest('button'); if (!b) return;
    S.period = b.dataset.p; render();
  };
  m.querySelector('#zoneTabs').onclick = e => {
    const b = e.target.closest('button'); if (!b) return;
    S.kind = b.dataset.z; render();
  };
}
export function skeletonHtml(number){
  const mv = findMovie(number) || {};
  return '<div class="hero"><div class="big">'
    + (mv.cover ? imgWithPlaceholder(mv.cover, number) : '<div class="hint">正在获取封面…</div>')
    + '</div><div class="info">'
    + '<h2>' + esc(number) + '</h2>'
    + '<div class="kv">'
    + (mv.date ? '<span><b>发行</b> ' + esc(mv.date) + '</span>' : '')
    + (mv.actor ? '<span><b>演员</b> ' + esc(mv.actor) + '</span>' : '')
    + '</div>'
    + '<div class="hint" style="margin-top:10px">⏳ 正在抓取影片详情（预览图与磁力随后填充）…</div>'
    + '</div></div>';
}
