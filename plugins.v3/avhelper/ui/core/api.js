/* AVHelper · 接口层：基址推导与 fetch 封装（错误分支与原实现逐字一致）
 * 由 webui.html 原主脚本按块搬移（调用点零改写）；跨模块引用走 ES module 具名导入。 */
import { readToken, showAuthBar } from './auth.js';


/* ============ 接口层 ============ */
const API_BASE = '/api/v1/plugin/AVHelper';

export function apiUrl(path, params){
  let u = API_BASE + path;
  const qs = [];
  Object.keys(params || {}).forEach(k => {
    const v = params[k];
    if (v === undefined || v === null || v === '') return;
    qs.push(encodeURIComponent(k) + '=' + encodeURIComponent(v));
  });
  return qs.length ? u + '?' + qs.join('&') : u;
}
async function request(method, path, params, body){
  const headers = {};
  const tk = readToken();
  if (tk) headers['Authorization'] = 'Bearer ' + tk;
  const opt = { method: method, headers: headers, cache: 'no-store' };
  if (body !== undefined){
    headers['Content-Type'] = 'application/json';
    opt.body = JSON.stringify(body);
  }
  let resp;
  try { resp = await fetch(apiUrl(path, params), opt); }
  catch (e) { return { ok:false, message:'网络请求失败：' + (e && e.message ? e.message : e), net:true }; }
  if (resp.status === 401 || resp.status === 403){
    invalidateToken(); readToken(true);
    showAuthBar('登录凭据已失效，请重新登录 MoviePilot');
    return { ok:false, message:'登录凭据已失效（HTTP ' + resp.status + '）', auth:true };
  }
  if (!resp.ok) return { ok:false, message:'请求失败（HTTP ' + resp.status + '）' };
  let js = null;
  try { js = await resp.json(); }
  catch (e) { return { ok:false, message:'返回内容不是合法 JSON（可能被网关改写）' }; }
  if (!js || typeof js !== 'object') return { ok:false, message:'返回内容为空' };
  if (js.success === false) return { ok:false, message: js.message || js.detail || '接口返回失败' };
  return { ok:true, data: (js.data !== undefined ? js.data : js) };
}
export const apiGet    = (p, q)    => request('GET',    p, q);
export const apiPost   = (p, b)    => request('POST',   p, null, b);
export const apiDelete = (p, q)    => request('DELETE', p, q);
