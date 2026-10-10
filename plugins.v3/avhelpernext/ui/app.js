/* AVHelperNext · 应用入口：视图路由、事件绑定、启动序列与 window.AVH
 * 由 webui.html 原主脚本按块搬移（调用点零改写）；跨模块引用走 ES module 具名导入。 */
import { apiDelete, apiGet } from './core/api.js';
import { bindTokenEvents, hideAuthBar, readToken, showAuthBar } from './core/auth.js';
import { CACHE, CURSOR, DEFAULT_RULE, S, cached } from './core/state.js';
import { $ } from './core/util.js';
import { hint, toast } from './ui/feedback.js';
import { LB, lbStep, openLb } from './ui/lightbox.js';
import { closeAll } from './ui/modal.js';
import { loadingHtml } from './ui/widgets.js';
import { openActor, openActorPicker, renderActorDetail, renderActors } from './views/actors.js';
import { openMovie, paintDetail } from './views/detail.js';
import { loadDiscoverForce, renderDiscover } from './views/discover.js';
import { renderQueue } from './views/downloads.js';
import { noticeUnread, openNotify, paintNotify } from './views/notify.js';
import { doSearch } from './views/search.js';
import { renderSiteSearch } from './views/sitesearch.js';
import { renderSubs } from './views/subs.js';
import { loadTasks, renderTasks, startTaskPolling } from './views/tasks.js';


/* ============ 视图骨架 ============ */
export function renderPills(){
  const pend = S.tasks.filter(t => t.state === 'await').length;
  $('#pillFavs').textContent = S.favs.length;
  $('#pillSubs').textContent = S.subs.length;
  $('#pillTasks').textContent = pend;
  $('#pillQueue').textContent = S.queue.filter(q => q.state !== 'done').length;
  const n = noticeUnread();
  const bc = $('#bellCount');
  bc.textContent = n;
  bc.classList.toggle('zero', !n);
  Array.prototype.forEach.call($('#nav').children, b => b.classList.toggle('on', b.dataset.v === S.view));
}
export function render(){
  renderPills();
  const m = $('#main');
  if (S.actor && S.view === 'actors'){ renderActorDetail(m); return; }
  if (!S.booted && S.view === 'discover'){ m.innerHTML = loadingHtml('正在读取插件状态…'); return; }
  ({discover:renderDiscover, actors:renderActors, subs:renderSubs, tasks:renderTasks,
    downloads:renderQueue, sites:renderSiteSearch}[S.view] || renderDiscover)(m);
}

/* ============ 启动 ============ */
function applyBootstrap(d){
  d = d || {};
  if (typeof d.enabled === 'boolean') S.enabled = d.enabled;
  if (Array.isArray(d.sites) && d.sites.length) S.sites = d.sites;
  if (Array.isArray(d.favs)) S.favs = d.favs;
  if (Array.isArray(d.subs)) S.subs = d.subs;
  if (Array.isArray(d.tasks)) S.tasks = d.tasks;
  if (Array.isArray(d.queue)) S.queue = d.queue;
  if (Array.isArray(d.notices)) S.notices = d.notices;
  if (Array.isArray(d.known)) S.known = new Set(d.known);
  if (d.defaultRule && typeof d.defaultRule === 'object') S.rule = Object.assign({}, DEFAULT_RULE, d.defaultRule);
  if (S.rule.sites && !S.rule.sites.length && S.sites.length){
    S.rule.sites = S.sites.slice(0, 5).map(s => s.name).filter(Boolean);
  }
  if (S.rule.prefSites && !S.rule.prefSites.length && S.sites.length){
    S.rule.prefSites = S.sites.slice(0, 2).map(s => s.name).filter(Boolean);
  }
}
/* 站点列表兜底：bootstrap 没给就单查 /sites（订阅规则弹窗要用） */
function ensureSites(){
  if (S.sites && S.sites.length) return Promise.resolve(true);
  return apiGet('/sites').then(r => {
    if (!r.ok) return false;
    const d = r.data || {};
    const list = Array.isArray(d.sites) ? d.sites : (Array.isArray(d) ? d : []);
    if (list.length) S.sites = list;
    return list.length > 0;
  });
}
function loadBootstrap(){
  return apiGet('/bootstrap').then(r => {
    if (!r.ok){ S.bootError = r.message || 'bootstrap 失败'; return false; }
    applyBootstrap(r.data);
    S.bootError = '';
    return ensureSites().then(() => true);
  });
}
/* 首屏：拉状态 → 重绘 */
function bootAndRender(){
  S.bootError = '';
  renderPills();
  return loadBootstrap().then(ok => {
    if (!readToken()) showAuthBar('未取到登录凭据，请重新登录 MoviePilot');
    if (!S.enabled) toast('插件未启用', '请先在 MoviePilot 插件设置里启用 AVHelper', 'warn');
    if (!ok && !S.bootError) S.bootError = '接口无响应';
    S.booted = true;
    render();
    if (ok) loadTasks(false);
    return ok;
  });
}
export function loadSubs(force){
  return apiGet('/subs').then(r => {
    if (!r.ok){ if (force) toast('订阅读取失败', r.message || '', 'warn'); return false; }
    const d = r.data || {};
    if (Array.isArray(d.subs)) S.subs = d.subs;
    else if (Array.isArray(d)) S.subs = d;
    renderPills();
    if (S.view === 'subs') render();
    return true;
  });
}
function bindUi(){
  /* 重试按钮统一走事件委托：这些块会被反复重绘，逐个绑定容易漏 */
  document.addEventListener('click', e => {
    const b = e.target.closest('[data-act]');
    if (!b) return;
    const act = b.dataset.act;
    if (act === 'rank-retry'){
      if (S.bootError && !cached('rank:' + S.period + ':' + S.kind)) bootAndRender();
      else loadDiscoverForce(true);
    } else if (act === 'detail-retry'){
      if (CURSOR.number){ delete CACHE['detail:' + CURSOR.number]; paintDetail(CURSOR.number); }
    } else if (act === 'actor-retry'){
      if (S.actor){ delete CACHE['page:actor:' + S.actor]; render(); }
    } else if (act === 'picker-retry'){
      delete CACHE['actors'];
      openActorPicker();
    } else if (act === 'modal-close'){
      /* 弹窗里改过收藏（暂停了下层重绘），关窗时补一次 */
      closeAll();
      renderPills();
      render();
    }
  });
  $('#nav').addEventListener('click', e => {
    const b = e.target.closest('button[data-v]'); if (!b) return;
    S.view = b.dataset.v; S.actor = null;
    closeAll(); render();
    if (S.view === 'tasks' || S.view === 'downloads') loadTasks(false);
    if (S.view === 'subs') loadSubs(false);
  });
  $('#bellBtn').onclick = openNotify;
  $('#nClose').onclick = closeAll;
  $('#nClear').onclick = () => {
    apiDelete('/notices').then(r => {
      if (!r.ok){ toast('清空失败', r.message || '请稍后重试', 'warn'); return; }
      S.notices = []; renderPills(); paintNotify();
      toast('已清空', '通知已清空', 'ok');
    });
  };
  $('#authRetry').onclick = () => {
    const t = readToken(true);
    if (t){ hideAuthBar(); toast('已取到登录凭据', '正在重试接口…', 'ok'); loadBootstrap().then(() => render()); }
    else toast('仍未取到凭据', '请确认已在 MoviePilot 登录', 'warn');
  };
  $('#scrim').onclick = closeAll;
  $('#drawerClose').onclick = closeAll;
  $('#lbPrev').onclick = e => { e.stopPropagation(); lbStep(-1); };
  $('#lbNext').onclick = e => { e.stopPropagation(); lbStep(1); };
  $('#lbClose').onclick = () => $('#lb').classList.remove('on');
  $('#lb').onclick = e => { if (e.target.id === 'lb') $('#lb').classList.remove('on'); };
  $('#lbImg').onerror = () => { $('#lbCtr').textContent = (LB.idx + 1) + ' / ' + LB.list.length + '（图片加载失败）'; };
  document.addEventListener('keydown', e => {
    if ($('#lb').classList.contains('on')){
      if (e.key === 'Escape'){ $('#lb').classList.remove('on'); return; }
      if (e.key === 'ArrowLeft'){ lbStep(-1); return; }
      if (e.key === 'ArrowRight'){ lbStep(1); return; }
    }
    if (e.key === 'Escape'){
      if ($('#modal').classList.contains('on') || $('#drawer').classList.contains('on')
          || $('#ndrawer').classList.contains('on')) closeAll();
    }
  });
  $('#qBtn').onclick = () => doSearch($('#qInput').value);
  $('#qInput').addEventListener('keydown', e => { if (e.key === 'Enter') doSearch(e.target.value); });
}

/* ============ 过渡：让外部（联邦壳 AppFrame）能指定首屏栏目 ============
   壳的数据台在 S6 期间仍是 iframe，点左栏会重挂 iframe；带上 ?view=<key> 就落在对应栏目，
   不再每次都回到「发现榜单」。**只读一次、只认白名单**：
   - 缺省 / 空 / 非法值一律不写 S.view，行为与没有这个参数时逐字节一致（A/B 工装靠这条）；
   - 取值与 #nav 的 data-v 一一对应（sites = 站点搜索，见 index.html 的导航按钮）。 */
const VIEW_KEYS = ['discover', 'actors', 'subs', 'tasks', 'downloads', 'sites'];
function applyViewQuery(){
  let key = '';
  try { key = new URLSearchParams(location.search).get('view') || ''; } catch (e) { return; }
  if (VIEW_KEYS.indexOf(key) >= 0) S.view = key;
}

/* 挂到 window：HTML 内联事件（onclick）需要 AVH.openLb / AVH.closeAll */
window.AVH = {
  S:S, render:render, closeAll:closeAll, openMovie:openMovie, openActor:openActor,
  openLb:openLb, openActorPicker:openActorPicker, doSearch:doSearch,
  toast:toast, hint:hint, loadTasks:loadTasks,
  clearCache:function(prefix){ Object.keys(CACHE).forEach(k => { if (!prefix || k.indexOf(prefix) === 0) delete CACHE[k]; }); }
};
bindTokenEvents();
bindUi();
applyViewQuery();   // 必须在第一次 render() 之前：否则会先画一帧「发现榜单」
render();
startTaskPolling();
bootAndRender();
