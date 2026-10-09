/* AVHelperNext · 视图 6：站点搜索（不经 javdb，直接查 PT 站索引）
 * 由 webui.html 原主脚本按块搬移（调用点零改写）；跨模块引用走 ES module 具名导入。 */
import { render, renderPills } from '../app.js';
import { apiPost } from '../core/api.js';
import { S } from '../core/state.js';
import { $, esc, nowStr } from '../core/util.js';
import { toast } from '../ui/feedback.js';
import { queueThumb } from './downloads.js';
import { bindDownloadButtons, candTable, loadTasks } from './tasks.js';


/* ---------- 6. 站点搜索（不经 javdb，直接查 PT 站索引） ---------- */
function sitePickList(){
  const names = (S.sites || []).map(s => s.name).filter(Boolean);
  if (!S.sitePick) S.sitePick = ['馒头','Rousi'].filter(n => names.indexOf(n) >= 0);
  return names;
}
function doSiteSearch(){
  const input = $('#ssInput');
  const kw = (input && input.value ? input.value : '').trim();
  if (!kw){ toast('站点搜索', '先输入番号或关键词', 'warn'); return; }
  S.siteKeyword = kw;
  const btn = $('#ssBtn');
  if (btn){ btn.disabled = true; btn.textContent = '搜索中…'; }
  const sites = (S.sitePick || []).slice();
  apiPost('/tasks/search', sites.length ? {keyword:kw, sites:sites} : {keyword:kw}).then(r => {
    if (btn){ btn.disabled = false; btn.textContent = '搜索站点'; }
    if (!r.ok){ toast('搜索失败', r.message || '请稍后重试', 'warn'); return; }
    const task = (r.data && r.data.task) ? r.data.task : r.data;
    S.siteTask = task || null;
    S.siteSearchAt = nowStr();
    if (task && task.id != null){
      S.tasks = S.tasks.filter(t => String(t.id) !== String(task.id));
      S.tasks.unshift(task);
    }
    const box = $('#ssResult');
    if (box && task){ box.innerHTML = candTable(task, 0); bindDownloadButtons(box); }
    renderPills();
    queueThumb(task && task.number);   // 后端没有这个番号的封面时，后台补一次（补到就换上）
    const n = task && task.cands ? task.cands.length : 0;
    toast(n ? '搜到 ' + n + ' 个候选' : '没有候选',
      n ? kw + ' · 选一个点「下载」' : ((task && task.reason) || '换个关键词或站点再试'),
      n ? 'ok' : 'warn');
    loadTasks(false);
  });
}
export function renderSiteSearch(m){
  const names = sitePickList();
  const picked = S.sitePick || [];
  const infoOf = n => (S.sites || []).filter(s => s.name === n)[0] || {};
  m.innerHTML = '<div class="toolbar">'
    + '<input id="ssInput" placeholder="番号或关键词（如 MIDV-946）…" autocomplete="off" '
    + 'style="min-width:280px;background:var(--bg3);border:1px solid var(--line);border-radius:8px;padding:7px 10px;color:var(--fg)">'
    + '<button class="primary" id="ssBtn">搜索站点</button>'
    + '<button class="ghost" id="ssPref">只搜馒头 + 肉丝</button>'
    + '<button class="ghost" id="ssAll">全选站点</button>'
    + '<div style="flex:1"></div>'
    + '<span class="hint">' + (S.siteSearchAt
        ? '上次搜索 ' + esc(S.siteSearchAt)
        : '命中即停 · 站点间隔 3-8 秒') + '</span>'
    + '</div>'
    + '<div class="fld"><label>搜索范围（点站点名切换）</label>'
    + '<div class="chips" id="ssChips">'
    + names.map(n => {
        const label = infoOf(n).adapterLabel || '';
        return '<span class="chip' + (picked.indexOf(n) >= 0 ? ' on' : '') + '" data-s="' + esc(n) + '" title="' + esc(label) + '">'
          + esc(n) + (label ? '<span class="hint">（' + esc(label) + '）</span>' : '') + '</span>';
      }).join('')
    + '</div></div>'
    + '<div id="ssResult">' + (S.siteTask && (S.siteTask.cands || []).length
        ? candTable(S.siteTask, 0)
        : '<div class="empty">输入番号或关键词后点「搜索站点」</div>')
    + '</div>';

  const input = m.querySelector('#ssInput');
  if (input){
    input.value = S.siteKeyword || '';
    input.onkeydown = e => { if (e.key === 'Enter') doSiteSearch(); };
  }
  m.querySelector('#ssBtn').onclick = doSiteSearch;
  m.querySelector('#ssPref').onclick = () => {
    S.sitePick = ['馒头','Rousi'].filter(n => names.indexOf(n) >= 0);
    render();
  };
  m.querySelector('#ssAll').onclick = () => { S.sitePick = names.slice(); render(); };
  m.querySelector('#ssChips').onclick = e => {
    const chip = e.target.closest('.chip'); if (!chip) return;
    const n = chip.dataset.s;
    if (!S.sitePick) S.sitePick = [];
    const i = S.sitePick.indexOf(n);
    if (i >= 0) S.sitePick.splice(i, 1); else S.sitePick.push(n);
    chip.classList.toggle('on');
  };
  bindDownloadButtons(m);
}

/* ---------- 7. 通知（顶栏铃铛 → 右侧抽屉） ---------- */
/* 「已读」只销角标、不删记录：通知永远留在列表里，铃铛上的数字只统计没看过的新通知。
   已读位点按本机记（localStorage，隐私模式下退回内存变量），看一次就一直归零，
   之后来的新通知才会重新把数字顶上去。 */
