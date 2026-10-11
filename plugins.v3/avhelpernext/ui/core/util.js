/* AVHelperNext · 通用工具（无 DOM 副作用）
 * 由 webui.html 原主脚本按块搬移（调用点零改写）；跨模块引用走 ES module 具名导入。 */

/* ============ 工具 ============ */
export const $ = s => document.querySelector(s);
export const esc = s => String(s == null ? '' : s).replace(/[&<>"]/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));
export const nowStr = () => new Date().toLocaleTimeString('zh-CN',{hour12:false});
const normNum = s => String(s == null ? '' : s).replace(/[^A-Za-z0-9]/g,'').toUpperCase();
function copyText(text, btn){
  const done = () => toast('已复制', '磁力链接已复制到剪贴板');
  if (navigator.clipboard && navigator.clipboard.writeText){
    navigator.clipboard.writeText(text).then(done, () => fallback());
  } else fallback();
  function fallback(){
    const ta = document.createElement('textarea');
    ta.value = text; ta.style.position = 'fixed'; ta.style.opacity = '0';
    document.body.appendChild(ta); ta.select();
    try { document.execCommand('copy'); done(); }
    catch (e) { toast('复制失败', '请手动选中链接复制', 'warn'); }
    ta.remove();
  }
}
/* 长缩略图（剧情长图）：后端只解析 URL（/longimage，缓存 7 天），图片由浏览器直连加载。
   ⚠️ images.projectjav.com 校验 Referer：带本页地址（或 javdb 地址）一律 403，所以必须
   referrerpolicy="no-referrer"；浏览器直连不通（本机没走代理）时再退回插件图片代理 /img。 */
export function shortTime(t){
  if (!t) return '—';
  const s = String(t);
  if (/^\d{4}-\d{2}-\d{2}T/.test(s)) return s.replace('T', ' ').slice(0, 16);
  return s;
}
