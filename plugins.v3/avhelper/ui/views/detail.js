/* AVHelper · 影片详情抽屉（以图为主，含长缩略图）
 * 由 webui.html 原主脚本按块搬移（调用点零改写）；跨模块引用走 ES module 具名导入。 */
import { renderPills } from '../app.js';
import { apiGet, apiPost, apiUrl } from '../core/api.js';
import { CACHE, CURSOR, S, cached, put } from '../core/state.js';
import { $, esc } from '../core/util.js';
import { openDrawer } from '../ui/drawer.js';
import { toast } from '../ui/feedback.js';
import { IMG_FALLBACK, imgTag, imgWithPlaceholder } from '../ui/image.js';
import { openLb } from '../ui/lightbox.js';
import { closeAll } from '../ui/modal.js';
import { errHtml, skeletonHtml } from '../ui/widgets.js';
import { cssUrl, openActor, toggleFav } from './actors.js';
import { subscribeNumber } from './subs.js';
import { ptSearch } from './tasks.js';


/* ---------- 影片详情（抽屉，以图为主） ---------- */
export function findFav(name){ return S.favs.filter(f => f.name === name)[0] || null; }
export function actorAvatarOf(name){
  const f = findFav(name);
  if (f && f.avatar) return f.avatar;
  const key = 'actor:' + name;
  const e = cached(key);
  if (e && e.data && e.data.entity && e.data.entity.avatar) return e.data.entity.avatar;
  const a = (cached('actors') || {}).data;
  if (a){ const hit = a.filter(x => x.name === name)[0]; if (hit && hit.avatar) return hit.avatar; }
  const p = (cached('page:actor:' + name) || {}).data;
  if (p && p.entity && p.entity.avatar) return p.entity.avatar;
  return '';
}
export function openMovie(number, id){
  if (!number) return;
  const key = 'detail:' + number;
  if (CURSOR.number !== number) CURSOR.id = '';
  if (id) CURSOR.id = id;
  CURSOR.number = number;
  detailFresh = number;                 // 标记「刚打开」：首帧画完滚回顶部
  openDrawer('影片详情 · ' + number, '');
  $('#drawerReload').style.display = '';
  $('#drawerReload').onclick = () => { delete CACHE[key]; paintDetail(number); };
  paintDetail(number);
}
export function paintDetail(number){
  const key = 'detail:' + number;
  const entry = cached(key);
  const db = $('#drawerBody');
  if (entry && !entry.error){ db.innerHTML = detailHtml(entry.data, number); bindDetail(number); detailTopIfFresh(number); return; }
  if (entry && entry.error){ db.innerHTML = errHtml(entry.error, 'data-act="detail-retry"'); detailTopIfFresh(number); return; }
  db.innerHTML = skeletonHtml(number);   // 先用列表卡片数据把壳画出来，别让用户对着空白等
  apiGet('/detail', {number:number, id:(CURSOR.number === number ? CURSOR.id : '')}).then(r => {
    if (!r.ok){ put(key, {error: r.message || '抓取失败，请稍后重试'}); toast('详情抓取失败', r.message || '抓取失败，请稍后重试', 'warn'); }
    else put(key, {data:r.data || {}, t:Date.now()});
    if ($('#drawer').classList.contains('on') && CURSOR.number === number) paintDetail(number);
  });
}
/* 刚打开的那一部：首帧画完把抽屉滚回顶部。浏览器有「滚动锚定」，光换 innerHTML 它可能
   又把上一部的偏移找回来；而同一个番号的重绘（长图回填 / 重新抓取）不该动用户的滚动位置。 */
let detailFresh = '';
function detailTopIfFresh(number){
  if (detailFresh !== number) return;
  detailFresh = '';
  $('#drawerBody').scrollTop = 0;
}
/* 详情还没回来时，用列表里已有的卡片数据先渲染封面/番号/日期/演员 */
export function findMovie(num){
  const keys = Object.keys(CACHE);
  for (let i = 0; i < keys.length; i++){
    const e = CACHE[keys[i]];
    const list = e && e.data && (Array.isArray(e.data) ? e.data : e.data.movies);
    if (!Array.isArray(list)) continue;
    const hit = list.filter(x => x && x.number === num)[0];
    if (hit) return hit;
  }
  return null;
}
function detailHtml(d, number){
  d = d || {};
  const mv = d.movie || {};
  const num = mv.number || number;
  const actors = d.actors || [];
  const previews = d.previews || [];
  const magnets = d.magnets || [];
  const imgs = [mv.cover].concat(previews).filter(Boolean);
  const faved = mv.actor ? !!findFav(mv.actor) : false;
  return '<div class="hero">'
    + '<div class="big">'
    + (mv.cover
        ? '<img src="' + esc(mv.cover) + '" alt="' + esc(num) + '" onclick="AVH.openLb(' + esc(JSON.stringify(imgs)) + ',0)"'
          + ' onerror="this.onerror=null;this.src=\'' + IMG_FALLBACK + '\'">'
        : '<div class="hint">后端未返回封面（/img 代理可能不可用）</div>')
    + '</div>'
    + '<div class="info">'
    + '<h2>' + esc(num) + '</h2>'
    + (mv.lib
        ? '<div class="librow">✅ 已在 Emby 库中'
          + (mv.lib.url ? ' · <a href="' + esc(mv.lib.url) + '" target="_blank" rel="noopener">在 Emby 中打开 ↗</a>' : '')
          + '</div>'
        : '')
    + '<div style="color:var(--fg2);font-size:13px;line-height:1.7">' + esc(mv.title || '') + '</div>'
    + '<div class="actorchips">'
    + (actors.length
        ? actors.map(a => '<div class="actorchip" data-actor="' + esc(a.name || '') + '">'
            + imgWithPlaceholder(a.avatar, a.name || '演员')
            + '<span>' + esc(a.name || '') + (a.zh ? ' / ' + esc(a.zh) : '') + '</span><span class="hint">看全部作品 ›</span></div>').join('')
        : (mv.actor
            ? '<div class="actorchip" data-actor="' + esc(mv.actor) + '">' + imgWithPlaceholder(mv.actor_avatar, mv.actor)
              + '<span>' + esc(mv.actor) + '</span><span class="hint">看全部作品 ›</span></div>'
            : '<span class="hint">未识别到演员</span>'))
    + '</div>'
    + '<div class="kv">'
    + '<span><b>发行</b> ' + esc(mv.date || '—') + '</span>'
    + '<span><b>时长</b> ' + esc(mv.duration || '—') + ' 分钟</span>'
    + '<span><b>中文字幕</b> ' + (mv.cnsub ? '<span style="color:var(--ok)">有</span>' : '<span style="color:var(--fg3)">无</span>') + '</span>'
    + '<span><b>磁力</b> ' + (mv.magnets || magnets.length || 0) + ' 个</span>'
    + (mv.maker ? '<span><b>片商</b> ' + esc(mv.maker) + '</span>' : '')
    + (mv.score ? '<span><b>评分</b> ' + esc(mv.score) + '</span>' : '')
    + '</div>'
    + '<div class="acts">'
    + '<button class="primary" id="btnPtSearch">🔎 搜索 PT 站</button>'
    + '<button class="ghost" id="btnSubNum">📌 订阅这个番号</button>'
    + (mv.actor
        ? '<button class="ghost" id="btnFavInDetail">' + (faved ? '★ 已收藏' : '☆ 收藏该演员') + '</button>'
        : '')
    + '</div>'
    + '</div></div>'
    + '<div class="secttl">预览图（' + previews.length + ' 张）</div>'
    + '<div class="shots">'
    + (previews.length
        ? previews.map((p,i) => '<div class="shot" data-lb="' + i + '"'
            + (p ? ' style="--bg:url(\'' + cssUrl(p) + '\')"' : '') + '>'
            + imgTag(p, '', '预览图') + '<div class="noimg" style="display:none">预览图加载失败</div></div>').join('')
        : '<span class="hint">该片没有预览图</span>')
    + '</div>'
    + '<div class="secttl">磁力链接（' + magnets.length + ' 条）</div>'
    + magnetListHtml(magnets)
    + '<div class="longwrap" id="longWrap"></div>';
}
function magnetListHtml(magnets){
  if (!magnets.length) return '<div class="hint">没有磁力链接</div>';
  return '<div>' + magnets.map(mg => {
    const hash = mg.hash || '';
    const magnet = hash ? ('magnet:?xt=urn:btih:' + hash) : '';
    return '<div class="row mag" style="align-items:flex-start">'
      + '<div class="mg">'
      + '<div class="mn">' + esc(mg.name || hash || '未命名') + '</div>'
      + '<div class="mh">'
      + '<span class="tag' + (mg.cnsub ? ' on' : '') + '">' + (mg.cnsub ? '中字' : '无中字') + '</span>'
      + (mg.hd ? '<span class="tag pref">高清</span>' : '')
      + (mg.size ? '<span class="tag">' + esc(mg.size) + '</span>' : '')
      + '</div>'
      + (magnet ? '<div class="mh" style="margin-top:4px">'
          + '<a href="' + esc(magnet) + '" style="color:var(--acc)" title="用系统下载器打开">' + esc(hash) + '</a></div>' : '')
      + '</div>'
      + '<button class="ghost" data-dlhash="' + esc(hash) + '" data-dlname="' + esc(mg.name || '') + '">⬇ 下载</button>'
      + '</div>';
  }).join('') + '</div>';
}
/* 磁力「下载」：直接推给下载器，不用先复制再粘到下载器里（保存路径/分类/下载器取全局规则） */
function dlMagnet(number, hash, name, btn){
  if (!hash) return;
  const old = btn.textContent;
  btn.disabled = true; btn.textContent = '⏳ 提交中…';
  apiPost('/magnet-download', {number:number, hash:hash, name:name || ''}).then(r => {
    if (!r.ok){
      btn.disabled = false; btn.textContent = old;
      toast('下载失败', r.message || '请检查下载器配置', 'warn');
      return;
    }
    btn.textContent = '✅ 已提交';
    if (r.data && Array.isArray(r.data.queue)){ S.queue = r.data.queue; renderPills(); }
    toast('已提交下载', (r.data && r.data.message) || '进度见「下载」页', 'ok');
  });
}
function bindDetail(number){
  const db = $('#drawerBody');
  const d = (cached('detail:' + number) || {}).data || {};
  const mv = d.movie || {};
  const previews = d.previews || [];
  const imgs = [mv.cover].concat(previews).filter(Boolean);

  db.querySelectorAll('.actorchip').forEach(el => el.onclick = () => {
    const n = el.dataset.actor; if (!n) return; closeAll(); openActor(n);
  });
  db.querySelectorAll('.shots [data-lb]').forEach(el => el.onclick = () => {
    let i = parseInt(el.dataset.lb, 10) + 1;
    if (!mv.cover) i = parseInt(el.dataset.lb, 10);
    openLb(imgs, i);
  });
  const bs = db.querySelector('#btnPtSearch');
  if (bs) bs.onclick = () => {
    bs.disabled = true; bs.textContent = '⏳ 搜索中…';
    ptSearch(number, mv.actor || '', mv.thumb || '', bs);
  };
  const bn = db.querySelector('#btnSubNum');
  if (bn) bn.onclick = () => subscribeNumber(number);
  const bf = db.querySelector('#btnFavInDetail');
  if (bf) bf.onclick = () => toggleFav(mv.actor, mv.actor_avatar || '');
  db.querySelectorAll('[data-dlhash]').forEach(b =>
    b.onclick = () => dlMagnet(number, b.dataset.dlhash, b.dataset.dlname, b));
  loadLong(number, d.longimage || '');     // 详情画完就自己去补长缩略图，不用再点按钮
}
const LONG_STATE = {};   // number -> {url} 已拿到 | {err} 失败 | {loading:true} 解析中
function longHint(text, warn){
  return '<div class="hint"' + (warn ? ' style="color:var(--warn)"' : '') + '>' + esc(text) + '</div>';
}
function longFail(w, number, text, url){
  w.innerHTML = longHint(text, true)
    + (url ? '<div class="hint" style="word-break:break-all;margin-top:4px">' + esc(url) + '</div>' : '')
    + '<div style="margin-top:6px"><button class="ghost" id="btnLongRetry">重试</button></div>';
  w.querySelector('#btnLongRetry').onclick = () => loadLong(number, '', true);
}
function paintLong(w, number, url){
  w.innerHTML = longHint('⏳ 正在加载长缩略图…');
  const im = new Image();
  im.alt = '长缩略图';
  im.className = 'longimg';
  im.decoding = 'async';
  im.referrerPolicy = 'no-referrer';            // 关键：带 Referer 图床直接 403
  im.onload = () => { w.innerHTML = ''; w.appendChild(im); im.onclick = () => openLb([im.src], 0); };
  im.onerror = () => {
    if (im.dataset.fb !== '1'){ im.dataset.fb = '1'; im.src = apiUrl('/img', {url:url}); return; }
    longFail(w, number, '长缩略图加载失败：浏览器直连与插件代理都没取到。', url);
  };
  w.appendChild(im);
  im.src = url;
}
function loadLong(number, knownUrl, force){
  const w = $('#longWrap');
  if (!w || !number) return;
  if (force) delete LONG_STATE[number];            // 「重试」：连后端缓存一起绕过（/longimage?force=1）
  if (knownUrl) LONG_STATE[number] = {url: knownUrl};
  const st = LONG_STATE[number];
  if (st && st.url) return paintLong(w, number, st.url);
  if (st && st.err) return longFail(w, number, st.err, '');
  w.innerHTML = longHint('⏳ 正在获取长缩略图…');    // 首次解析要几秒，别让用户对着空位
  if (st && st.loading) return;                    // 已有请求在飞：等它回来统一重绘
  LONG_STATE[number] = {loading: true};
  apiGet('/longimage', force ? {number:number, force:1} : {number:number}).then(r => {
    const url = r.ok ? String((r.data && (r.data.url || r.data.longimage)) || '') : '';
    LONG_STATE[number] = r.ok
      ? (url ? {url: url} : {err: '该番号在 projectjav / javfree 里都没找到长图。'})
      : {err: '长图地址查询失败：' + (r.message || '请稍后重试')};
    const e = cached('detail:' + number);
    if (e && e.data) e.data.longimage = url;
    if ($('#drawer').classList.contains('on') && CURSOR.number === number) loadLong(number);
  });
}
