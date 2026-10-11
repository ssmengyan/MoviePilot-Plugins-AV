/* AVHelper · 通知（顶栏铃铛 → 右侧抽屉）
 * 由 webui.html 原主脚本按块搬移（调用点零改写）；跨模块引用走 ES module 具名导入。 */
import { renderPills } from '../app.js';
import { apiGet } from '../core/api.js';
import { S } from '../core/state.js';
import { $, esc, shortTime } from '../core/util.js';
import { toast } from '../ui/feedback.js';
import { imgTag } from '../ui/image.js';
import { loadingHtml } from '../ui/widgets.js';

const SEEN_KEY = 'avh.noticesSeen';
let SEEN_MEM = '';
function noticeSeenAt(){
  try { return localStorage.getItem(SEEN_KEY) || SEEN_MEM; } catch (e) { return SEEN_MEM; }
}
export function noticeUnread(){
  const seen = noticeSeenAt();
  return S.notices.filter(n => String(n.time || '') > seen).length;
}
function noticeMarkSeen(){
  const latest = S.notices.reduce((a, n) => (String(n.time || '') > a ? String(n.time) : a), noticeSeenAt());
  SEEN_MEM = latest;
  try { localStorage.setItem(SEEN_KEY, latest); } catch (e) { /* 写不了就只用内存位点 */ }
}
function notifyBodyHtml(){
  return '<div class="tg">'
    + (S.notices.length
      ? S.notices.map(n => {
          const kind = n.kind === 'ok' ? 'ok' : (n.kind === 'warn' ? 'warn' : '');
          return '<div class="msg ' + kind + '">'
            + '<div class="ico">🤖</div><div class="bub">'
            + '<div class="h">MoviePilot · ' + esc(n.type || '系统消息') + '</div>'
            + (n.title ? '<div style="font-weight:600;font-size:13px;margin-bottom:2px">' + esc(n.title) + '</div>' : '')
            + '<div class="b">' + esc(n.body || '') + '</div>'
            + (n.meta ? '<div class="meta-line">' + esc(n.meta) + '</div>' : '')
            + (n.image ? imgTag(n.image, '', '主图') + '<div class="noimg" style="display:none">主图加载失败</div>' : '')
            + '<div class="f">' + esc(shortTime(n.time)) + '</div>'
            + '</div></div>';
        }).join('')
      : '<div class="empty">暂无通知</div>')
    + '</div>';
}
export function openNotify(){
  $('#drawer').classList.remove('on');
  $('#modal').classList.remove('on');
  $('#drawerReload').style.display = 'none';
  const nb = $('#nBody');
  nb.innerHTML = loadingHtml('加载中…');
  nb.scrollTop = 0;                     // 抽屉每次都是新开的一张，别继承上次的滚动位置
  $('#scrim').classList.add('on');
  $('#ndrawer').classList.add('on');
  loadNotices(false).then(ok => {       // 打开即算已读：角标清零，通知列表照旧全留着
    if (!ok) return;
    noticeMarkSeen();
    renderPills();
  });
}
export function paintNotify(){
  if ($('#ndrawer').classList.contains('on')) $('#nBody').innerHTML = notifyBodyHtml();
}
function loadNotices(force){
  return apiGet('/notices').then(r => {
    if (!r.ok){ if (force) toast('通知读取失败', r.message || '', 'warn'); return false; }
    const d = r.data || {};
    S.notices = Array.isArray(d.notices) ? d.notices : (Array.isArray(d) ? d : S.notices);
    renderPills();
    paintNotify();
    return true;
  });
}
