/* AVHelper · 图片灯箱
 * 由 webui.html 原主脚本按块搬移（调用点零改写）；跨模块引用走 ES module 具名导入。 */
import { $ } from '../core/util.js';


/* ---------- Lightbox ---------- */
export const LB = { list: [], idx: 0 };   // 灯箱状态：当前图片列表与下标（由原来的两个 let 收拢，供 bindUi 读取）
export function openLb(list, idx){
  LB.list = (list || []).filter(Boolean);
  if (!LB.list.length) return;
  LB.idx = idx < 0 ? LB.list.length - 1 : (idx || 0);
  if (LB.idx < 0 || LB.idx >= LB.list.length) LB.idx = 0;
  showLb();
  $('#lb').classList.add('on');
}
function showLb(){
  $('#lbImg').src = LB.list[LB.idx] || '';
  $('#lbCtr').textContent = (LB.idx + 1) + ' / ' + LB.list.length;
}
export function lbStep(d){
  if (!LB.list.length) return;
  LB.idx = (LB.idx + d + LB.list.length) % LB.list.length;
  showLb();
}
