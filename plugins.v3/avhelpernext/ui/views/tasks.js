/* AVHelperNext · 视图 4：任务（待确认候选、搜种、下载）
 * 由 webui.html 原主脚本按块搬移（调用点零改写）；跨模块引用走 ES module 具名导入。 */
import { render, renderPills } from '../app.js';
import { apiGet, apiPost } from '../core/api.js';
import { S } from '../core/state.js';
import { esc } from '../core/util.js';
import { hint, toast } from '../ui/feedback.js';
import { imgWithPlaceholder } from '../ui/image.js';
import { queueMissingThumbs } from './downloads.js';


/* ---------- 4. 任务（只放待确认的候选；下载进度在「下载」页） ---------- */
let taskTimer = null;
export function renderTasks(m){
  const pend = S.tasks.filter(t => t.state === 'await');
  const dling = S.queue.filter(q => q.state !== 'done').length;
  m.innerHTML = '<div class="toolbar">'
    + (dling ? '<span class="hint">⏬ ' + dling + ' 个已提交，进度看「下载」页</span>' : '')
    + '<div style="flex:1"></div>'
    + '<button class="ghost" id="btnRefreshTasks">↻ 刷新任务</button></div>'
    + (pend.length
        ? '<div class="secttl">待确认（' + pend.length + '）</div>' + pend.map((t,i) => candTable(t, i)).join('')
        : '<div class="empty">没有待确认的任务</div>');
  m.querySelector('#btnRefreshTasks').onclick = () => { loadTasks(true); toast('任务', '正在刷新…'); };
  bindDownloadButtons(m);
  queueMissingThumbs(pend);
}
export function candTable(t, idx){
  const cands = t.cands || [];
  const pt = cands.filter(c => c.src !== 'BT');
  const bt = cands.filter(c => c.src === 'BT');
  const rowOf = c => {
    const pass = c.pass !== false;
    const cls = (c.picked ? 'best ' : '') + (pass ? '' : 'dead ') + (c.src === 'BT' ? 'bt' : '');
    const title = String(c.title || '').trim();      // 种子原名，常写着「无码破解」之类
    return '<tr class="' + cls + (title ? 'has-sub' : '') + '">'
      + '<td>' + (c.src === 'BT' ? '<span class="tag">BT</span>' : '') + esc(c.site || '') + '</td>'
      + '<td>' + esc(c.spec || '') + '</td>'
      + '<td>' + (c.cnsub ? '<span class="tag on">有</span>' : '<span class="tag">无</span>') + '</td>'
      + '<td>' + (c.uncensored ? '<span class="tag uc">破解</span>' : '<span class="tag">—</span>') + '</td>'
      + '<td>' + esc(c.size || '') + '</td>'
      + '<td>' + (c.src === 'BT' ? '<span class="hint">未知</span>' : esc(c.seeders == null ? '—' : c.seeders)) + '</td>'
      + '<td>' + (c.free ? '<span class="tag free">免费</span>' : '') + (c.pref ? '<span class="tag pref">优先站</span>' : '') + '</td>'
      + '<td title="' + esc(c.breakdown || '') + '"><span class="score '
      + (!pass ? 'lo' : (Number(c.score) >= 80 ? 'hi' : Number(c.score) >= 55 ? 'mid' : 'lo')) + '">'
      + (pass ? esc(c.score == null ? '—' : c.score) : '淘汰') + '</span></td>'
      + '<td>' + (pass
          ? '<button class="ghost" data-dl="' + esc(c.site || '') + '" data-task="' + esc(t.id || '') + '">下载</button>'
          : '<button class="ghost" data-dl="' + esc(c.site || '') + '" data-task="' + esc(t.id || '')
            + '" data-force="1" title="' + esc(c.breakdown || '') + '">仍要下载</button>') + '</td></tr>'
      + (title ? '<tr class="candsub ' + cls + '"><td colspan="9"><div class="ttl" title="'
          + esc(title) + '">' + esc(title) + '</div></td></tr>' : '');
  };
  const origin = t.source === 'sub'
    ? ('来自订阅' + (t.actor ? '：' + esc(t.actor) : ''))
    : ('手动搜索' + (t.actor ? ' · 演员：' + esc(t.actor) : ''));
  return '<div class="q" style="padding:0;overflow:hidden">'
    + '<div class="thd">'
    + '<div class="tposter" data-num="' + esc(t.number || '') + '">' + imgWithPlaceholder(t.thumb, '无图') + '</div>'
    + '<div>'
    + '<div class="tno">' + esc(t.number || '') + '</div>'
    + '<div class="hint" style="margin-top:3px">' + origin + ' · 搜到 ' + cands.length
    + ' · 合格 ' + cands.filter(c => c.pass !== false).length + '</div>'
    + '</div>'
    + '<div style="flex:1"></div>'
    + (t.auto && t.source === 'sub' ? '<span class="hint">订阅为自动下载，但无候选合格</span>' : '')
    + '</div>'
    + '<table><thead><tr><th>站点</th><th>规格</th><th>中字</th><th>破解</th><th>大小</th><th>做种</th><th>标记</th><th>匹配分</th><th></th></tr></thead><tbody>'
    + pt.map(rowOf).join('')
    + (bt.length ? '<tr><td colspan="9" class="hint" style="padding:6px 10px">— PT 没有合格候选，以下为 BT 磁力兜底 —</td></tr>' + bt.map(rowOf).join('') : '')
    + (cands.length ? '' : '<tr><td colspan="9" class="hint" style="padding:10px">没有搜到任何候选</td></tr>')
    + '</tbody></table>'
    + '</div>';
}
/* 后台搜种：结果落进任务列表，但**不跳页**——只在底部给一条小提示，用户接着看手里的详情 */
export function ptSearch(number, actor, thumb, btn){
  const body = {number:number};
  if (actor) body.actor = actor;
  if (thumb) body.thumb = thumb;      // 详情页顺手把封面带过去，任务列表里就有图了
  const done = () => { if (btn){ btn.disabled = false; btn.textContent = '🔎 搜索 PT 站'; } };
  apiPost('/tasks/search', body).then(r => {
    done();
    if (!r.ok){ toast('搜种失败', r.message || '抓取失败，请稍后重试', 'warn'); return; }
    const task = r.data && r.data.task ? r.data.task : r.data;
    if (task && task.id != null){
      S.tasks = S.tasks.filter(t => String(t.id) !== String(task.id));
      S.tasks.unshift(task);
    }
    renderPills();
    loadTasks(true);                  // 后台把任务列表刷好，角标跟着更新
    const n = task && task.cands ? task.cands.length : 0;
    hint((task && task.number) || number, n ? '已搜索完成' : '没有找到候选', n ? '' : 'warn');
  });
}
function startDownload(taskId, site, btn, force){
  if (btn) btn.disabled = true;
  apiPost('/tasks/download', force ? {id:taskId, site:site, force:true} : {id:taskId, site:site}).then(r => {
    if (!r.ok){
      if (btn) btn.disabled = false;
      toast('下载失败', r.message || '请稍后重试', 'warn');
      return;
    }
    const notice = r.data && r.data.notice ? r.data.notice : (r.data && r.data.id ? r.data : null);
    if (notice && (notice.body || notice.title)){ S.notices.unshift(notice); renderPills(); }
    toast('已提交下载', site + ' · 进度见「下载」页', 'ok');
    loadTasks(true);
  });
}
export function loadTasks(force){
  return apiGet('/tasks').then(r => {
    if (!r.ok){ if (force) toast('任务读取失败', r.message || '请稍后重试', 'warn'); return false; }
    const d = r.data || {};
    if (Array.isArray(d.tasks)) S.tasks = d.tasks;
    if (Array.isArray(d.queue)) S.queue = d.queue;
    renderPills();
    if (S.view === 'tasks' || S.view === 'downloads') render();
    return true;
  });
}
export function startTaskPolling(){
  if (taskTimer) return;
  taskTimer = setInterval(() => {
    if (S.view === 'tasks' || S.view === 'downloads') loadTasks(false);
  }, 5000);
}
export function bindDownloadButtons(root){
  (root || document).querySelectorAll('[data-dl]').forEach(b => b.onclick = () => {
    const t = S.tasks.filter(x => String(x.id) === String(b.dataset.task))[0] || S.siteTask;
    if (t) startDownload(t.id, b.dataset.dl, b, b.dataset.force === '1');
  });
}
