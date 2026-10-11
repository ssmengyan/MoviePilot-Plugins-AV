/* AVHelper · 轻反馈：toast 与 hint
 * 由 webui.html 原主脚本按块搬移（调用点零改写）；跨模块引用走 ES module 具名导入。 */
import { $, esc } from '../core/util.js';


export function toast(title, text, kind){
  const el = document.createElement('div');
  el.className = 'toast ' + (kind || '');
  el.innerHTML = '<b>' + esc(title) + '</b>' + esc(text == null ? '' : text);
  $('#toasts').appendChild(el);
  setTimeout(() => { el.style.opacity = '0'; el.style.transition = '.3s'; setTimeout(() => el.remove(), 320); }, 4200);
}

/* 后台任务的小提示（搜索完成之类）：底部居中，新的排在下面，各条自己计时、渐入渐出 */
const HINT_MS = 2000;         // 停留时长（用户要求 2 秒）
const HINT_FADE = 320;        // 与 CSS 里的 transition 对齐
export function hint(number, text, kind){
  const box = $('#hints');
  if (!box) return;
  const el = document.createElement('div');
  el.className = 'hintItem ' + (kind || '');
  el.innerHTML = '<b>' + esc(number || '') + '</b><span class="tick">'
    + (kind === 'warn' ? '•' : '✓') + '</span>' + esc(text || '已搜索完成');
  box.appendChild(el);
  while (box.children.length > 5) box.removeChild(box.firstChild);   // 连点也不至于糊满屏
  requestAnimationFrame(() => el.classList.add('on'));               // 下一帧再加 on，过渡才会走
  setTimeout(() => {
    el.classList.remove('on');
    setTimeout(() => el.remove(), HINT_FADE);
  }, HINT_MS);
}
