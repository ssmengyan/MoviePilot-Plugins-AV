/* AVHelperNext · 通用弹窗
 * 由 webui.html 原主脚本按块搬移（调用点零改写）；跨模块引用走 ES module 具名导入。 */
import { $ } from '../core/util.js';


/* ---------- 抽屉 / 弹窗 ---------- */
export function closeAll(){
  $('#scrim').classList.remove('on');
  $('#drawer').classList.remove('on');
  $('#ndrawer').classList.remove('on');
  $('#modal').classList.remove('on');
  $('#modal').classList.remove('wide');
  $('#drawerReload').style.display = 'none';
}
export function openModal(title, body, foot){
  $('#modal').classList.remove('wide');
  $('#modalTitle').textContent = title;
  $('#modalBody').innerHTML = body;
  $('#modalFoot').innerHTML = foot || '';
  $('#scrim').classList.add('on');
  $('#modal').classList.add('on');
}
