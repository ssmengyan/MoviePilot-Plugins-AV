/* AVHelper · 顶栏搜索
 * 由 webui.html 原主脚本按块搬移（调用点零改写）；跨模块引用走 ES module 具名导入。 */
import { apiGet } from '../core/api.js';
import { $, esc } from '../core/util.js';
import { imgTag, imgWithPlaceholder, preload } from '../ui/image.js';
import { closeAll, openModal } from '../ui/modal.js';
import { errHtml, loadingHtml } from '../ui/widgets.js';
import { openActor } from './actors.js';
import { openMovie } from './detail.js';


/* ---------- 搜索 ---------- */
export function doSearch(kw){
  kw = (kw || '').trim(); if (!kw) return;
  openModal('搜索「' + kw + '」', loadingHtml('正在搜索…'), '<button class="danger" onclick="AVH.closeAll()">关闭</button>');
  $('#modal').classList.add('wide');
  apiGet('/search', {keyword:kw}).then(r => {
    const mb = $('#modalBody');
    if (!$('#modal').classList.contains('on')) return;
    if (!r.ok){ mb.innerHTML = errHtml(r.message || '搜索失败，请稍后重试', 'id="sRetry"'); const b = mb.querySelector('#sRetry'); if (b) b.onclick = () => doSearch(kw); return; }
    const d = r.data || {};
    const movies = d.movies || [];
    const actors = d.actors || [];
    $('#modalTitle').textContent = '搜索「' + kw + '」 · ' + movies.length + ' 部影片' + (actors.length ? ' / ' + actors.length + ' 位演员' : '');
    mb.innerHTML = (actors.length
        ? '<div class="hint" style="margin-bottom:8px">演员</div>'
          + '<div class="actors" style="grid-template-columns:repeat(auto-fill,minmax(110px,1fr));margin-bottom:16px">'
          + actors.map(a => '<div class="actor" data-n="' + esc(a.name) + '">'
              + '<div class="av">' + imgWithPlaceholder(a.avatar, a.name) + '</div>'
              + '<div class="nm">' + esc(a.name) + '</div><div class="zh">' + esc(a.zh || '') + '</div></div>').join('')
          + '</div>'
        : '')
      + (movies.length
        ? '<div class="hint" style="margin-bottom:8px">影片</div>'
          + movies.map(mv => '<div class="searchrow" data-num="' + esc(mv.number) + '" data-id="' + esc(mv.id || '') + '">'
              + '<div class="mini">' + imgTag(mv.thumb, '', mv.number) + '<div class="noimg" style="display:none">无图</div></div>'
              + '<div style="flex:1;min-width:0">'
              + '<div style="font-weight:700">' + esc(mv.number) + '</div>'
              + '<div class="hint" style="margin-top:3px">' + esc(mv.actor || '—') + ' · ' + esc(mv.date || '') + ' · 🧲 ' + (mv.magnets || 0)
              + (mv.cnsub ? '<span class="tag on">中字</span>' : '') + (mv.uncensored ? '<span class="tag uc">破解</span>' : '')
              + (mv.lib ? '<span class="tag lib">已入库</span>' : '') + '</div>'
              + '<div class="hint" style="margin-top:2px">' + esc((mv.title || '').slice(0, 60)) + '</div>'
              + '</div><span class="hint">查看 ›</span></div>').join('')
        : '<div class="hint">没有匹配的影片</div>');
    mb.querySelectorAll('.searchrow').forEach(el => el.onclick = () => { closeAll(); openMovie(el.dataset.num, el.dataset.id || ''); });
    mb.querySelectorAll('.actor').forEach(el => el.onclick = () => { closeAll(); openActor(el.dataset.n); });
    preload(movies.map(x => x.thumb));
  });
}
