/* AVHelper · 视图 1：发现榜单（含卡片与后台预热）
 * 由 webui.html 原主脚本按块搬移（调用点零改写）；跨模块引用走 ES module 具名导入。 */
import { render } from '../app.js';
import { apiGet } from '../core/api.js';
import { CACHE, S, cached, put } from '../core/state.js';
import { esc } from '../core/util.js';
import { toast } from '../ui/feedback.js';
import { imgWithPlaceholder } from '../ui/image.js';
import { bindTabs, emptyHtml, errHtml, loadingHtml, periodTabsHtml, zoneTabsHtml } from '../ui/widgets.js';
import { openMovie } from './detail.js';


/* ---------- 1. 发现榜单 ---------- */
export function renderDiscover(m){
  if (S.bootError){
    m.innerHTML = '<div class="toolbar"><div class="tabs" id="periodTabs">' + periodTabsHtml() + '</div>'
      + '<div class="tabs" id="zoneTabs">' + zoneTabsHtml() + '</div></div>'
      + errHtml('插件状态读取失败：' + S.bootError + '（仍可尝试直接抓取榜单）', 'data-act="rank-retry"');
    bindTabs(m);
    return;
  }
  const key = 'rank:' + S.period + ':' + S.kind;
  const entry = cached(key);

  m.innerHTML = '<div class="toolbar">'
    + '<div class="tabs" id="periodTabs">' + periodTabsHtml() + '</div>'
    + '<div class="tabs" id="zoneTabs">' + zoneTabsHtml() + '</div>'
    + (entry && entry.data ? '<span class="hint">' + entry.data.length + ' 部</span>' : '')
    + '<div style="flex:1"></div>'
    + '<button class="ghost" id="btnReload">↻ 重新抓取</button></div>'
    + '<div id="rankBody">' + (entry ? '' : loadingHtml('正在抓取榜单…')) + '</div>';

  bindTabs(m);
  m.querySelector('#btnReload').onclick = () => loadDiscoverForce(true);

  const body = m.querySelector('#rankBody');
  const paint = ent => {
    if (!body.isConnected) return;
    body.innerHTML = rankBodyHtml(ent);
    bindCards(body);
    prefetchCards(body, PREFETCH_N);
  };
  if (entry) paint(entry);
  else {
    loadDiscover(false)
      .then(paint)
      .catch(e => paint({error:'抓取失败，请稍后重试（' + (e && e.message ? e.message : e) + '）'}));
  }
}
function rankBodyHtml(entry){
  if (entry.error) return errHtml(entry.error, 'data-act="rank-retry"');
  const items = entry.data || [];
  if (!items.length) return emptyHtml('该榜单暂无数据，换个周期 / 分类试试');
  return '<div class="grid">' + items.map(card).join('') + '</div>';
}
function loadDiscover(force){
  const key = 'rank:' + S.period + ':' + S.kind;
  const entry = cached(key);
  if (entry && !force) return Promise.resolve(entry);
  return apiGet('/rankings', {period:S.period, kind:S.kind}).then(r => {
    let e;
    if (!r.ok){ e = put(key, {error:r.message || '抓取失败，请稍后重试'}); toast('榜单抓取失败', r.message || '抓取失败，请稍后重试', 'warn'); }
    else e = put(key, {data:(r.data && r.data.movies) || [], t:Date.now()});
    return e;
  });
}
export function loadDiscoverForce(showToast){
  const key = 'rank:' + S.period + ':' + S.kind;
  delete CACHE[key];
  if (showToast) toast('javdb-cli', '正在重新抓取榜单…');
  loadDiscover(true).then(() => {
    if (showToast){
      const e = cached(key);
      toast(e && !e.error ? '榜单已更新' : '重新抓取失败',
        e && !e.error ? ((e.data || []).length + ' 条') : ((e && e.error) || ''),
        e && e.error ? 'warn' : 'ok');
    }
    if (S.view === 'discover') render();
  });
}
export function card(mv){
  const num = mv.number || '';
  const merged = mv.actor && S.favs.some(f => f.name === mv.actor);
  return '<div class="card" data-num="' + esc(num) + '" data-id="' + esc(mv.id || '') + '">'
    + '<div class="thumb">'
    + imgWithPlaceholder(mv.thumb, num)
    + '<div class="badges">'
    + (mv.cnsub ? '<span class="badge cn">中字</span>' : '')
    + (mv.uncensored ? '<span class="badge uc">破解</span>' : '')
    + (merged ? '<span class="badge new">⭐已收藏演员</span>' : '')
    + (mv.lib ? '<span class="badge lib">✔已入库</span>' : '')
    + '</div></div>'
    + '<div class="meta">'
    + '<div class="num">' + esc(num) + '</div>'
    + '<div class="sub"><span>' + esc(mv.actor || '—') + '</span><span>🧲 ' + (mv.magnets || 0) + '</span></div>'
    + '<div class="sub"><span>' + esc(mv.date || '') + '</span><span>' + (mv.duration ? esc(mv.duration) + '′' : '') + '</span></div>'
    + '</div></div>';
}
/* 详情预热：抓一次详情约 3 秒，先在后台按序取回来，点开时就是缓存命中。
   串行 1 条（不并发压多个 javdb 子进程）；失败不写错误条目，留给真正打开时报错重试。 */
const PRE = { queue:[], busy:false };
export const PREFETCH_N = 6;             // 每屏后台预热前几张：调大=点开更快、后台开销更多
export function prefetchDetail(num, id){
  if (!num || CACHE['detail:' + num]) return;
  if (PRE.queue.some(x => x.num === num)) return;
  PRE.queue.push({num:num, id:id || ''});
  pumpPrefetch();
}
function pumpPrefetch(){
  if (PRE.busy) return;
  const job = PRE.queue.shift();
  if (!job) return;
  if (CACHE['detail:' + job.num]){ pumpPrefetch(); return; }
  PRE.busy = true;
  apiGet('/detail', {number:job.num, id:job.id}).then(r => {
    if (r.ok) put('detail:' + job.num, {data:r.data || {}, t:Date.now()});
  }).catch(() => {}).then(() => { PRE.busy = false; pumpPrefetch(); });
}
export function prefetchCards(root, n){
  root.querySelectorAll('.card, .film').forEach((c, i) => {
    if (i < n) prefetchDetail(c.dataset.num, c.dataset.id || '');
  });
}
function bindCards(root, sel){
  root.querySelectorAll(sel || '.card').forEach(c => {
    const num = c.dataset.num || '', id = c.dataset.id || '';
    c.onclick = () => openMovie(num, id);
    c.onmouseenter = () => prefetchDetail(num, id);   // 悬停即抢跑，点下去时多半已经在路上
  });
}
