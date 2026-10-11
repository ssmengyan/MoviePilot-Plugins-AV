/* AVHelper · 右侧抽屉
 * 由 webui.html 原主脚本按块搬移（调用点零改写）；跨模块引用走 ES module 具名导入。 */
import { $ } from '../core/util.js';

export function openDrawer(title, html){
  $('#drawerTitle').textContent = title;
  $('#drawerBody').innerHTML = html;
  $('#drawerBody').scrollTop = 0;       // 换一部片要从头看，不继承上一部的滚动位置
  $('#scrim').classList.add('on');
  $('#drawer').classList.add('on');
}
