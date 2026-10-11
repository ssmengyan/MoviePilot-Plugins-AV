/* AVHelperNext · 视图 5：下载队列
 * 由 webui.html 原主脚本按块搬移（调用点零改写）；跨模块引用走 ES module 具名导入。 */
import { apiGet } from '../core/api.js';
import { S } from '../core/state.js';
import { esc } from '../core/util.js';
import { toast } from '../ui/feedback.js';
import { imgWithPlaceholder } from '../ui/image.js';
import { loadTasks } from './tasks.js';

/* ---------- 5. 下载队列（从任务页拆出来的独立页） ---------- */
export function renderQueue(m){
  m.innerHTML = '<div class="toolbar">'
    + '<span class="hint">进度取自下载器，每 5 秒自动刷新</span>'
    + '<div style="flex:1"></div>'
    + '<button class="ghost" id="btnRefreshQueue">↻ 刷新进度</button></div>'
    + (S.queue.length
        ? S.queue.map(queueRow).join('')
        : '<div class="empty">下载队列为空<br>在「任务」页挑好候选点「下载」，进度在这里看</div>');
  m.querySelector('#btnRefreshQueue').onclick = () => { loadTasks(true); toast('下载队列', '正在刷新进度…'); };
  queueMissingThumbs(S.queue);
}
function queueRow(q){
  const pct = Math.max(0, Math.min(100, Number(q.progress) || 0));
  const done = q.state === 'done';
  const meta = [q.site, q.spec, q.size].filter(Boolean).map(esc).join(' · ');
  return '<div class="q"><div class="qhd">'
    + '<div class="tposter" data-num="' + esc(q.number || '') + '">' + imgWithPlaceholder(q.thumb, '无图') + '</div>'
    + '<div style="flex:1;min-width:0">'
    + '<div class="qn">' + esc(q.number || '') + '</div>'
    + '<div class="hint" style="margin-top:3px">' + (meta || '—') + '</div>'
    + '<div class="hint" style="margin-top:2px">' + esc(q.savePath || '')
    + (q.added ? ' · ' + esc(q.added) : '') + '</div>'
    + '</div>'
    + '<div class="right"><div class="qn">' + pct + '%</div>'
    + '<div class="hint">' + (done ? '已下载' : '下载中…') + '</div></div>'
    + '</div>'
    + '<div class="bar' + (done ? ' done' : '') + '"><i style="width:' + pct + '%"></i></div></div>';
}
/* 缺封面的番号：串行、限量地补一次详情（结果缓存 7 天），补到就地换上。
   串行 = 同一时间只起一个 javdb 子进程（与详情预热同一条纪律）；限量 = 打开列表页不会打爆站点。
   只换图不重绘整块——用户可能正点着「下载」，重绘会把按钮状态打回去。 */
const TFILL = { queue:[], busy:false, tried:{} };
export function queueThumb(number){
  const num = String(number || '');
  if (!num || TFILL.tried[num]) return;
  TFILL.tried[num] = true;
  TFILL.queue.push(num);
  pumpThumbFill();
}
function pumpThumbFill(){
  if (TFILL.busy) return;
  const num = TFILL.queue.shift();
  if (!num) return;
  TFILL.busy = true;
  apiGet('/detail', {number:num}).then(r => {
    const mv = (r.ok && r.data && r.data.movie) || null;
    if (mv && mv.thumb) applyThumb(num, mv.thumb);
  }).catch(() => {}).then(() => { TFILL.busy = false; pumpThumbFill(); });
}
function applyThumb(number, thumb){
  const same = x => x && String(x.number) === String(number);
  [].slice.call(document.querySelectorAll('.tposter[data-num]')).forEach(el => {
    if (el.dataset.num === String(number)) el.innerHTML = imgWithPlaceholder(thumb, '无图');
  });
  S.tasks.filter(same).forEach(t => { if (!t.thumb) t.thumb = thumb; });
  S.queue.filter(same).forEach(q => { if (!q.thumb) q.thumb = thumb; });
  if (same(S.siteTask) && !S.siteTask.thumb) S.siteTask.thumb = thumb;
}
/* 列表里凡是没图的番号，每轮最多补 3 个（补上的下一轮就不再排队） */
export function queueMissingThumbs(items){
  (items || []).filter(x => x && x.number && !x.thumb).map(x => x.number).slice(0, 3).forEach(queueThumb);
}
