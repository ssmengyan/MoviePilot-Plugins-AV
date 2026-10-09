/* AVHelperNext · 全局状态：默认规则 / S / 内存缓存 / 详情游标
 * 由 webui.html 原主脚本按块搬移（调用点零改写）；跨模块引用走 ES module 具名导入。 */


/* ============ 状态 ============ */
export const DEFAULT_RULE = {
  res:'1080p', mustCnsub:false, preferUncensored:true, allow4k:true, minSeeders:3,
  sites:[], prefSites:['馒头','Rousi'], btFallback:true, savePath:'/media/9kg/avi',
  category:'avi', downloader:'qb', trigger:'notify', maxPerDay:6, minIntervalMin:240
};
export const S = {
  view:'discover', period:'week', kind:'censored',
  actor:null, actorYear:'', actorAll:false, known:new Set(),
  favs:[], subs:[], tasks:[], queue:[], notices:[],
  sites:[{id:'',name:'馒头'},{id:'',name:'观众'},{id:'',name:'我堡'},{id:'',name:'高清杜比'},
         {id:'',name:'GGPT'},{id:'',name:'麒麟'},{id:'',name:'象站'},{id:'',name:'织梦'},
         {id:'',name:'皇后'},{id:'',name:'PTS'},{id:'',name:'UBits'},{id:'',name:'Rousi'}],
  rule: Object.assign({}, DEFAULT_RULE),
  sitePick:null, siteKeyword:'', siteSearchAt:'', siteTask:null,
  enabled:true, booted:false, bootError:''
};
export const CACHE = {};                 // 内存缓存：榜单 / 演员榜 / 演员 / 详情
export const cached = k => CACHE[k];
export const put = (k, v) => { CACHE[k] = v; return v; };
export const CURSOR = { number: '', id: '' };   // 详情游标：当前抽屉里的番号与其 javdb 内部 id（由原来的两个 let 收拢，跨模块共享）
