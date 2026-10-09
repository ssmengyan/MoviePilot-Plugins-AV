/* AVHelperNext · 鉴权：从 localStorage 里挖 MoviePilot 会话 JWT
 * 由 webui.html 原主脚本按块搬移（调用点零改写）；跨模块引用走 ES module 具名导入。 */
import { $ } from './util.js';


/* ============ 鉴权：从 localStorage 里挖 JWT ============ */
const JWT_RE = /eyJ[A-Za-z0-9_-]{5,}\.[A-Za-z0-9_-]{5,}\.[A-Za-z0-9_-]{5,}/;
let TOKEN = null, TOKEN_TRIED = false;

/** 让当前会话令牌失效（接口层遇到 401/403 时调用）：清缓存并允许重新扫描。 */
export function invalidateToken(){ TOKEN = null; TOKEN_TRIED = false; }

function extractJwt(v){
  if (typeof v !== 'string' || v.length < 20) return null;
  const m = v.match(JWT_RE);
  return m ? m[0] : null;
}
function scanStorage(storage){
  try {
    for (let i = 0; i < storage.length; i++){
      const k = storage.key(i);
      if (k == null) continue;
      let hit = extractJwt(storage.getItem(k));
      if (!hit)   hit = extractJwt(k);              // 少数实现把 token 当 key
      if (hit) return hit;
    }
  } catch (e) { /* localStorage 不可用（跨源/被禁用）：忽略，后面会走 cookie 兜底 */ }
  return null;
}
export function readToken(force){
  if (TOKEN && !force) return TOKEN;
  if (TOKEN_TRIED && !force) return TOKEN;
  TOKEN_TRIED = true;
  TOKEN = scanStorage(window.localStorage)
       || extractJwt(window.localStorage && window.localStorage.getItem('mp-token'))
       || scanStorage(window.sessionStorage)
       || extractJwt(document.cookie);
  if (!TOKEN) TOKEN = null;
  return TOKEN;
}
export function showAuthBar(msg){
  $('#authbarText').textContent = msg || '未取到登录凭据，请重新登录 MoviePilot';
  $('#authbar').classList.add('on');
}
export function hideAuthBar(){ $('#authbar').classList.remove('on'); }
/* MoviePilot 登录后会广播 mp-token 事件；若页面早于登录加载，这里能补上凭据 */
export function bindTokenEvents(){
  ['mp-token','mp-token-updated','storage'].forEach(ev =>
    window.addEventListener(ev, () => { if (readToken(true)) { hideAuthBar(); } }));
}
