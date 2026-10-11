/* AVHelperNext · 视图 3：订阅（含规则弹窗）
 * 由 webui.html 原主脚本按块搬移（调用点零改写）；跨模块引用走 ES module 具名导入。 */
import { loadSubs, render, renderPills } from '../app.js';
import { apiDelete, apiPost } from '../core/api.js';
import { S } from '../core/state.js';
import { $, esc, shortTime } from '../core/util.js';
import { toast } from '../ui/feedback.js';
import { closeAll, openModal } from '../ui/modal.js';
import { emptyHtml } from '../ui/widgets.js';
import { addFav } from './actors.js';
import { findFav } from './detail.js';
import { paintNotify } from './notify.js';
import { loadTasks } from './tasks.js';


/* ---------- 3. 订阅 ---------- */
function ruleSummary(r){
  r = r || {};
  return (r.res || '1080p') + ' 优先'
    + (r.mustCnsub ? ' · 必须中字' : '')
    + (r.preferUncensored ? ' · 破解优先' : '')
    + (r.allow4k ? ' · 4K 择优' : '')
    + ' · 做种≥' + (r.minSeeders || 0)
    + (r.btFallback ? ' · BT 兜底' : '')
    + ' · ' + (r.trigger === 'auto' ? '命中自动下载' : '命中仅通知')
    + ((r.sites || []).length ? ' · 限 ' + r.sites.length + ' 站' : '');
}
export function renderSubs(m){
  m.innerHTML = '<div class="toolbar">'
    + '<span class="hint">默认规则：' + esc(ruleSummary(S.rule)) + '</span>'
    + '<div style="flex:1"></div>'
    + '<button class="ghost" id="btnRule">⚙ 默认规则</button>'
    + '<button class="ghost" id="btnCheckAll">⚡ 检查一次</button></div>'
    + (S.subs.length
      ? S.subs.map(s => {
          const last = s.last || s.created || '';
          return '<div class="q"><div class="top"><div>'
            + '<div style="font-weight:600">' + (s.type === 'actor' ? '👤' : '🎞') + ' ' + esc(s.name) + '</div>'
            + '<div class="hint" style="margin-top:3px">' + esc(ruleSummary(s.rule)) + '</div>'
            + '<div class="hint" style="margin-top:2px">命中 ' + (s.hits || 0) + ' 次 · 上次检查 ' + esc(last ? shortTime(last) : '—') + '</div>'
            + '</div><div style="display:flex;gap:6px">'
            + '<button class="ghost" data-check="' + esc(s.name) + '">检查</button>'
            + '<button class="danger" data-unsub="' + esc(s.id || '') + '">取消</button>'
            + '</div></div></div>';
        }).join('')
      : emptyHtml('还没有订阅'));
  m.querySelector('#btnRule').onclick = openRuleDialog;
  m.querySelector('#btnCheckAll').onclick = () => runCheck('');
  m.querySelectorAll('[data-check]').forEach(b => b.onclick = () => runCheck(b.dataset.check));
  m.querySelectorAll('[data-unsub]').forEach(b => b.onclick = () => unsub(b.dataset.unsub, b));
}
function unsub(id, btn){
  if (!id){ toast('取消失败', '这条订阅缺少 id，无法删除', 'warn'); return; }
  btn.disabled = true;
  apiDelete('/subs', {id:id}).then(r => {
    if (!r.ok){ btn.disabled = false; toast('取消订阅失败', r.message || '请稍后重试', 'warn'); return; }
    S.subs = S.subs.filter(s => String(s.id) !== String(id));
    renderPills();
    toast('已取消订阅', 'id=' + id, 'warn');
    if (S.view === 'subs') render();
  });
}
export function runCheck(name){
  toast('订阅检查', name ? ('正在检查 ' + name) : '正在检查全部订阅…');
  apiPost('/check', name ? {name:name} : {}).then(r => {
    if (!r.ok){ toast('检查失败', r.message || '请稍后重试', 'warn'); return; }
    const d = r.data || {};
    if (d.limited){
      toast('检查被限流', d.message || '距上次检查不足间隔，已跳过', 'warn');
    } else {
      toast('检查完成', d.message || ((d.notices || []).length + ' 条新通知'), 'ok');
    }
    (d.notices || []).forEach(n => S.notices.unshift(n));
    renderPills();
    if (S.view === 'subs') render();
    paintNotify();
    loadSubs(true);
    loadTasks(true);
  });
}
/* 规则编辑控件：订阅弹窗与「默认规则」弹窗共用 */
function ruleFieldsHtml(r){
  r = r || {};
  const sites = S.sites.map(s => s.name).filter(Boolean);
  const cur = id => (r.sites || []).indexOf(id) >= 0;
  const curPref = id => (r.prefSites || []).indexOf(id) >= 0;
  const numStyle = 'width:88px;background:var(--bg3);border:1px solid var(--line);border-radius:7px;padding:5px 8px;color:var(--fg)';
  const txtStyle = 'background:var(--bg3);border:1px solid var(--line);border-radius:7px;padding:7px 9px;color:var(--fg)';
  return ''
    + '<div class="fld"><label>分辨率策略</label>'
    + '<div class="tabs" id="resTabs">'
    + [['1080p','1080P 优先'],['2160p','4K 优先'],['only4k','仅 4K']].map(([v,n]) =>
        '<button data-r="' + v + '" class="' + (r.res === v ? 'on' : '') + '">' + n + '</button>').join('')
    + '</div></div>'
    + '<div class="sw"><div><div class="lbl">必须中文字幕</div><div class="dsc">打开则没有中字的种直接淘汰；默认关（AV 站中字少，关掉时中字仍加 32 分优先选）</div></div>'
    + '<input type="checkbox" id="cCn"' + (r.mustCnsub ? ' checked' : '') + '></div>'
    + '<div class="sw"><div><div class="lbl">破解 / 无码版优先</div></div>'
    + '<input type="checkbox" id="cUc"' + (r.preferUncensored ? ' checked' : '') + '></div>'
    + '<div class="sw"><div><div class="lbl">允许 4K 择优</div><div class="dsc">1080P 无好种时升级 4K</div></div>'
    + '<input type="checkbox" id="c4k"' + (r.allow4k ? ' checked' : '') + '></div>'
    + '<div class="sw"><div><div class="lbl">做种数下限</div><div class="dsc">低于此值不下载</div></div>'
    + '<input type="number" id="nSeed" value="' + esc(r.minSeeders) + '" style="' + numStyle + '"></div>'
    + '<div class="fld" style="margin-top:14px"><label>搜索站点（不选 = 全部已配置站点）</label>'
    + '<div class="chips" id="siteChips">'
    + (sites.length ? sites.map(s => '<span class="chip' + (cur(s) ? ' on' : '') + '" data-s="' + esc(s) + '">' + esc(s) + '</span>').join('')
                    : '<span class="hint">未取到站点列表</span>')
    + '</div></div>'
    + '<div class="fld"><label>优先站点（先搜这些站，命中即停）</label>'
    + '<div class="chips" id="prefChips">'
    + (sites.length ? sites.map(s => '<span class="chip' + (curPref(s) ? ' on' : '') + '" data-s="' + esc(s) + '">' + esc(s) + '</span>').join('')
                    : '<span class="hint">—</span>')
    + '</div></div>'
    + '<div class="sw"><div><div class="lbl">PT 搜不到时允许 BT 磁力兜底</div></div>'
    + '<input type="checkbox" id="cBt"' + (r.btFallback ? ' checked' : '') + '></div>'
    + '<div class="sw"><div><div class="lbl">命中后自动下载</div><div class="dsc">关闭则只通知，到「任务」页手动下载</div></div>'
    + '<input type="checkbox" id="cAuto"' + (r.trigger === 'auto' ? ' checked' : '') + '></div>'
    + '<div class="sw"><div><div class="lbl">检查频率上限</div><div class="dsc">每天最多检查次数</div></div>'
    + '<input type="number" id="nFreq" value="' + esc(r.maxPerDay) + '" style="' + numStyle + '"></div>'
    + '<div class="fld" style="margin-top:12px"><label>保存路径 / 下载器 / qB 分类</label>'
    + '<div style="display:flex;gap:8px">'
    + '<input type="text" id="pPath" value="' + esc(r.savePath || '') + '">'
    + '<input type="text" id="pDl" value="' + esc(r.downloader || 'qb') + '" style="width:90px;' + txtStyle + '">'
    + '<input type="text" id="pCat" value="' + esc(r.category || 'avi') + '" style="width:90px;' + txtStyle + '">'
    + '</div></div>';
}
function bindRuleFields(mb){
  mb.querySelector('#resTabs').onclick = e => {
    const b = e.target.closest('button'); if (!b) return;
    Array.prototype.forEach.call(b.parentNode.children, x => x.classList.toggle('on', x === b));
  };
  ['#siteChips','#prefChips'].forEach(sel => {
    const box = mb.querySelector(sel); if (!box) return;
    box.onclick = e => { const c = e.target.closest('.chip'); if (c) c.classList.toggle('on'); };
  });
}
function collectRule(mb, base){
  const resBtn = mb.querySelector('#resTabs .on');
  return {
    res: resBtn ? resBtn.dataset.r : '1080p',
    mustCnsub: mb.querySelector('#cCn').checked,
    preferUncensored: mb.querySelector('#cUc').checked,
    allow4k: mb.querySelector('#c4k').checked,
    minSeeders: parseInt(mb.querySelector('#nSeed').value, 10) || 0,
    maxPerDay: parseInt(mb.querySelector('#nFreq').value, 10) || 6,
    minIntervalMin: (base || S.rule).minIntervalMin,
    sites: Array.prototype.map.call(mb.querySelectorAll('#siteChips .chip.on'), c => c.dataset.s),
    prefSites: Array.prototype.map.call(mb.querySelectorAll('#prefChips .chip.on'), c => c.dataset.s),
    btFallback: mb.querySelector('#cBt').checked,
    trigger: mb.querySelector('#cAuto').checked ? 'auto' : 'notify',
    savePath: mb.querySelector('#pPath').value,
    category: mb.querySelector('#pCat').value,
    downloader: mb.querySelector('#pDl').value
  };
}
function openRuleDialog(){
  openModal('默认规则（手动搜索与新建订阅的基准）', ruleFieldsHtml(S.rule),
    '<button class="danger" onclick="AVH.closeAll()">取消</button><button class="primary" id="btnSaveRule">保存</button>');
  const mb = $('#modalBody');
  bindRuleFields(mb);
  $('#btnSaveRule').onclick = () => {
    const rule = collectRule(mb, S.rule);
    const btn = $('#btnSaveRule');
    btn.disabled = true;
    apiPost('/rule', {rule:rule}).then(r => {
      if (!r.ok){ btn.disabled = false; toast('保存失败', r.message || '请稍后重试', 'warn'); return; }
      S.rule = (r.data && r.data.rule) ? r.data.rule : Object.assign({}, S.rule, rule);
      closeAll();
      toast('默认规则已保存', '', 'ok');
      if (S.view === 'subs') render();
    });
  };
}
export function subActorDialog(name, zh, avatar){
  openModal('订阅演员 · ' + name, ruleFieldsHtml(S.rule),
    '<button class="danger" onclick="AVH.closeAll()">取消</button><button class="primary" id="btnDoSub">确认订阅</button>');
  const mb = $('#modalBody');
  bindRuleFields(mb);
  $('#btnDoSub').onclick = () => {
    const rule = collectRule(mb, S.rule);
    const btn = $('#btnDoSub');
    btn.disabled = true;
    apiPost('/subs', {type:'actor', name:name, rule:rule}).then(r => {
      if (!r.ok){ btn.disabled = false; toast('订阅失败', r.message || '请稍后重试', 'warn'); return; }
      if (!findFav(name)) addFav(name, zh, avatar);
      closeAll();
      toast('订阅已创建', name, 'ok');
      S.actor = null; S.view = 'subs'; render();
      loadSubs(true);
    });
  };
}
export function subscribeNumber(num){
  apiPost('/subs', {type:'number', name:num}).then(r => {
    if (!r.ok){ toast('订阅失败', r.message || '请稍后重试', 'warn'); return; }
    renderPills();
    toast('订阅已创建', '番号 ' + num, 'ok');
    closeAll();
    S.actor = null; S.view = 'subs'; render();
    loadSubs(true);
  });
}
