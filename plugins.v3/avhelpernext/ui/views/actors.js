/* AVHelperNext · 视图 2：我的演员（收藏、作品史）
 * 由 webui.html 原主脚本按块搬移（调用点零改写）；跨模块引用走 ES module 具名导入。 */
import { render } from '../app.js';
import { apiGet } from '../core/api.js';
import { S, cached, put } from '../core/state.js';
import { $, esc } from '../core/util.js';
import { toast } from '../ui/feedback.js';
import { imgWithPlaceholder, preload } from '../ui/image.js';
import { emptyHtml, errHtml, loadingHtml } from '../ui/widgets.js';
import { actorAvatarOf, findFav, openMovie } from './detail.js';
import { PREFETCH_N, card, prefetchCards, prefetchDetail } from './discover.js';
import { runCheck, subActorDialog } from './subs.js';


/* ---------- 2. 我的演员（只显示收藏） ---------- */
export function renderActors(m){
  if (!S.favs.length){
    m.innerHTML = '<div class="empty">还没有收藏演员<br><br>'
      + '<button class="primary" id="btnBrowseActors">➕ 从演员榜挑选</button></div>';
    m.querySelector('#btnBrowseActors').onclick = openActorPicker;
    return;
  }
  m.innerHTML = '<div class="toolbar">'
    + '<span class="hint">共 ' + S.favs.length + ' 位</span>'
    + '<div style="flex:1"></div>'
    + '<button class="ghost" id="btnAddActor">➕ 添加演员</button></div>'
    + '<div class="actors">'
    + S.favs.map(a => '<div class="actor" data-n="' + esc(a.name) + '">'
        + '<div class="star">⭐</div>'
        + '<div class="av">' + imgWithPlaceholder(a.avatar || actorAvatarOf(a.name), a.name) + '</div>'
        + '<div class="nm">' + esc(a.name) + '</div><div class="zh">' + esc(a.zh || '') + '</div>'
        + '</div>').join('')
    + '</div>';
  m.querySelector('#btnAddActor').onclick = openActorPicker;
  m.querySelectorAll('.actor').forEach(el => el.onclick = () => openActor(el.dataset.n));
  preload(S.favs.map(a => a.avatar));
}
export function openActorPicker(){
  const key = 'actors';
  const body = ent => {
    if (!ent) return loadingHtml('正在抓取演员榜…');
    if (ent.error) return errHtml(ent.error, 'data-act="picker-retry"');
    const avail = (ent.data || []).filter(a => !findFav(a.name));
    if (!avail.length) return '<div class="hint">演员榜里的人都已收藏。</div>';
    return '<div class="hint" style="margin-bottom:12px">点 ➕ 加入收藏</div>'
      + '<div class="actors" style="grid-template-columns:repeat(auto-fill,minmax(120px,1fr))">'
      + avail.map(a => '<div class="actor" data-n="' + esc(a.name) + '" data-av="' + esc(a.avatar || '') + '" data-zh="' + esc(a.zh || '') + '" style="cursor:pointer">'
          + '<div class="av">' + imgWithPlaceholder(a.avatar, a.name) + '</div>'
          + '<div class="nm">' + esc(a.name) + '</div><div class="zh">' + esc(a.zh || '') + '</div>'
          + '<div style="margin-top:6px"><span class="tag">➕ 收藏</span></div></div>').join('')
      + '</div>';
  };
  const paint = () => {
    const ent = cached(key);
    const mb = $('#modalBody');
    mb.innerHTML = body(ent);
    mb.querySelectorAll('.actor').forEach(el => el.onclick = () => {
      const card = el;
      /* 就地更新这张卡片，不整块重建：重建会让点击落到已消失的节点上 */
      addFav(card.dataset.n, card.dataset.zh, card.dataset.av).then(ok => {
        if (!ok) return;
        const dressed = mb.querySelector('.actor[data-n="' + card.dataset.n.replace(/"/g, '') + '"]');
        if (dressed){
          const tag = dressed.querySelector('.tag');
          if (tag){ tag.textContent = '✓ 已收藏'; tag.className = 'tag on'; }
          dressed.style.cursor = 'default';
          dressed.onclick = null;
        }
      });
    });
    const rb = mb.querySelector('[data-act="picker-retry"]');
    if (rb) rb.onclick = () => { delete CACHE[key]; openActorPicker(); };
    if (ent && ent.data) preload(ent.data.map(a => a.avatar));
  };
  openModal('从演员榜挑选', '', '<button class="danger" data-act="modal-close">关闭</button>');
  paint();
  const hit = cached(key);
  if (!hit || hit.error){
    delete CACHE[key];
    apiGet('/actors').then(r => {
      if (!r.ok){ put(key, {error:r.message || '演员榜抓取失败，请稍后重试'}); toast('演员榜抓取失败', r.message || '请稍后重试', 'warn'); }
      else put(key, {data:(r.data && r.data.actors) || [], t:Date.now()});
      if ($('#modal').classList.contains('on')) paint();
    });
  }
}
export function addFav(name, zh, avatar){
  if (!name) return Promise.resolve(false);
  if (findFav(name)){ toast('已收藏', name); return Promise.resolve(true); }
  return apiPost('/favs', {name:name, zh:zh || '', avatar:avatar || ''}).then(r => {
    if (!r.ok){ toast('收藏失败', r.message || '请稍后重试', 'warn'); return false; }
    const f = r.data && r.data.name ? r.data : {name:name, zh:zh || '', avatar:avatar || ''};
    if (!findFav(f.name)) S.favs.push(f);
    renderPills();
    /* 弹窗开着时下面那层先不重绘（避免重建弹窗/打架），关闭弹窗时统一刷新 */
    if (!$('#modal').classList.contains('on')) render();
    toast('已收藏', f.name + ' 会出现在「我的演员」里', 'ok');
    return true;
  });
}
function delFav(name){
  return apiDelete('/favs', {name:name}).then(r => {
    if (!r.ok){ toast('取消收藏失败', r.message || '请稍后重试', 'warn'); return false; }
    S.favs = S.favs.filter(f => f.name !== name);
    renderPills();
    toast('已取消收藏', name, 'warn');
    return true;
  });
}
export function toggleFav(name, avatar){
  if (!name){ toast('无法收藏', '这部影片没有识别到演员', 'warn'); return; }
  const wasFav = !!findFav(name);
  const p = wasFav ? delFav(name) : addFav(name, '', avatar || actorAvatarOf(name));
  p.then(ok => {
    if (!ok) return;
    if ($('#drawer').classList.contains('on')){ refreshFavButtons(); return; }   // 详情抽屉开着：只刷新按钮文字
    render();
  });
}
function refreshFavButtons(){
  const b = $('#btnFavInDetail');
  if (!b) return;
  const d = (cached('detail:' + CURSOR.number) || {}).data || {};
  const name = (d.movie || {}).actor;
  if (!name) return;
  b.textContent = findFav(name) ? '★ 已收藏' : '☆ 收藏该演员';
}
export function openActor(name){
  if (!name) return;
  S.actor = name; S.view = 'actors';
  S.actorYear = ''; S.actorAll = false;     // 换演员时重置作品史的筛选/展开
  render();
  const m = $('#main'); if (m) m.scrollTop = 0;
}
/* 作品史里的封面走 CSS 背景（模糊底衬），URL 要转义掉会破坏 url() 的字符 */
export const cssUrl = u => String(u || '').replace(/["'()\\\s]/g, c => encodeURIComponent(c));
function filmRow(mv, i){
  const num = mv.number || '';
  return '<div class="film" data-i="' + i + '" data-num="' + esc(num) + '" data-id="' + esc(mv.id || '') + '">'
    + '<div class="pic"' + (mv.thumb ? ' style="--bg:url(\'' + cssUrl(mv.thumb) + '\')"' : '') + '>'
    + imgWithPlaceholder(mv.thumb, num) + '</div>'
    + '<div class="ft"><div class="fn">' + esc(num) + '</div>'
    + (mv.title ? '<div class="ftt">' + esc(mv.title) + '</div>' : '')
    + '<div class="fd"><span>' + esc(mv.date || '') + '</span>'
    + (mv.cnsub ? '<span class="tag on">中字</span>' : '<span class="tag">无中字</span>')
    + '<span>🧲 ' + (mv.magnets || 0) + '</span>'
    + (mv.lib ? '<span class="tag lib">已入库</span>' : '')
    + '</div></div></div>';
}
const FILM_FOLD = 12;                      // 作品史默认只铺 12 部，多的折起来
export function renderActorDetail(m){
  const name = S.actor;
  const key = 'page:actor:' + name;
  const entry = cached(key);
  const head = '<div class="toolbar"><button class="ghost" id="btnBack">← 返回</button></div>';
  if (!entry){
    m.innerHTML = head + loadingHtml('正在抓取演员档案与作品史…');
    m.querySelector('#btnBack').onclick = () => { S.actor = null; render(); };
    apiGet('/actor', {name:name}).then(r => {
      if (!r.ok) put(key, {error:r.message || '抓取失败，请稍后重试'});
      else put(key, {data:r.data || {}, t:Date.now()});
      if (!r.ok) toast('演员抓取失败', r.message || '抓取失败，请稍后重试', 'warn');
      if (S.view === 'actors' && S.actor === name) render();
    });
    return;
  }
  if (entry.error){
    m.innerHTML = head + errHtml(entry.error, 'data-act="actor-retry"');
    m.querySelector('#btnBack').onclick = () => { S.actor = null; render(); };
    return;
  }
  const d = entry.data || {};
  const e = d.entity || {};
  const movies = d.movies || [];
  const faved = !!findFav(name);
  const sub = S.subs.filter(s => s.type === 'actor' && s.name === name)[0] || null;
  /* 作品史：先按年份收敛，再对超长的折叠，避免一次把整页铺满 */
  const years = [], yearCount = {};
  movies.forEach(mv => {
    const y = String(mv.date || '').slice(0, 4);
    if (/^\d{4}$/.test(y)){ if (!yearCount[y]){ yearCount[y] = 0; years.push(y); } yearCount[y]++; }
  });
  const year = S.actorYear || '';
  const list = year ? movies.filter(mv => String(mv.date || '').slice(0, 4) === year) : movies;
  const fold = !S.actorAll && list.length > FILM_FOLD;
  const shown = fold ? list.slice(0, FILM_FOLD) : list;
  const yearBar = years.length > 1
    ? '<div class="filmyears" id="filmYears">'
      + '<button data-y="" class="' + (year ? '' : 'on') + '">全部 ' + movies.length + '</button>'
      + years.map(y => '<button data-y="' + y + '" class="' + (year === y ? 'on' : '') + '">'
          + y + '<span style="opacity:.65"> ' + yearCount[y] + '</span></button>').join('')
      + '</div>'
    : '';
  m.innerHTML = head
    + '<div class="profile">'
    + '<div class="av">' + imgWithPlaceholder(e.avatar, name) + '</div>'
    + '<div style="flex:1;min-width:240px">'
    + '<h2>' + esc(e.name || name) + (e.zh ? ' <span style="color:var(--fg3);font-size:14px">/ ' + esc(e.zh) + '</span>' : '') + '</h2>'
    + '<div class="kv">'
    + (e.videos_count ? '<span><b>作品</b> ' + esc(e.videos_count) + '</span>' : '')
    + (e.age ? '<span><b>年龄</b> ' + esc(e.age) + '</span>' : '')
    + (e.birthday ? '<span><b>生日</b> ' + esc(e.birthday) + '</span>' : '')
    + (e.height ? '<span><b>身高</b> ' + esc(e.height) + 'cm</span>' : '')
    + (e.cup ? '<span><b>罩杯</b> ' + esc(e.cup) + '</span>' : '')
    + (e.birthplace ? '<span><b>出身</b> ' + esc(e.birthplace) + '</span>' : '')
    + (e.instagram ? '<span><b>IG</b> ' + esc(e.instagram) + '</span>' : '')
    + '<span><b>本次返回作品</b> ' + movies.length + ' 部</span>'
    + '</div>'
    + '<div class="acts">'
    + '<button class="' + (faved ? 'ghost' : 'primary') + '" id="btnFav">' + (faved ? '★ 已收藏' : '☆ 收藏该演员') + '</button>'
    + '<button class="' + (sub ? 'ghost' : 'primary') + '" id="btnSubActor"' + (sub ? ' disabled' : '') + '>'
    + (sub ? '✓ 已订阅新片' : '📌 订阅该演员的新片') + '</button>'
    + '<button class="ghost" id="btnCheckActor">⚡ 检查她的新片</button>'
    + '</div>'
    + '</div></div>'
    + '<div class="secttl">作品史（按发行时间倒序，共 ' + movies.length + ' 部'
    + (year ? '，' + year + ' 年 ' + list.length + ' 部' : '') + '）</div>'
    + yearBar
    + (list.length
        ? '<div class="films">' + shown.map(filmRow).join('') + '</div>'
          + (list.length > FILM_FOLD
              ? '<div class="morebar"><button class="ghost" id="btnMoreFilms">'
                + (fold ? '展开其余 ' + (list.length - FILM_FOLD) + ' 部' : '收起') + '</button></div>'
              : '')
        : emptyHtml(year ? '该年份没有作品记录。' : '这位演员暂无作品数据。'));

  m.querySelector('#btnBack').onclick = () => { S.actor = null; render(); };
  m.querySelector('#btnFav').onclick = () => toggleFav(name, e.avatar || '');
  const sb = m.querySelector('#btnSubActor');
  if (sb && !sb.disabled) sb.onclick = () => subActorDialog(name, e.zh || '', e.avatar || '');
  m.querySelector('#btnCheckActor').onclick = () => runCheck(name);
  const yb = m.querySelector('#filmYears');
  if (yb) yb.onclick = ev => {
    const b = ev.target.closest('button'); if (!b) return;
    S.actorYear = b.dataset.y; S.actorAll = false; render();
  };
  const mb = m.querySelector('#btnMoreFilms');
  if (mb) mb.onclick = () => {
    const expanding = !S.actorAll;
    S.actorAll = expanding;
    render();
    if (!expanding){                       // 收起后回到「作品史」标题，避免停在半空
      const t = $('#main').querySelector('.secttl');
      if (t) t.scrollIntoView({block:'start'});
    }
  };
  m.querySelectorAll('.film').forEach(el => {
    el.onclick = ev => { ev.stopPropagation(); openMovie(el.dataset.num, el.dataset.id || ''); };
    el.onmouseenter = () => prefetchDetail(el.dataset.num, el.dataset.id || '');
  });
  prefetchCards(m, PREFETCH_N);
  preload(shown.map(x => x.thumb));
}
