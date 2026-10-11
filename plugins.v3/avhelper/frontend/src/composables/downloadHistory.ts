/**
 * 「下载历史」台账（0.3.4）的类型与纯函数。
 *
 * 契约见 `docs/AVHelper-下载历史设计.md` §4：`GET plugin/downloads` 回
 * `{success, items[], counts{total,inLibrary,missing}}`，`DELETE plugin/downloads?key=…`
 * 删完再回一份同形状的列表。
 *
 * 为什么单独开一个文件、而不是塞进 `composables/storeTypes.ts`：
 * 本批改动里 `storeTypes.ts` / `usePluginStore.ts` 由另一条线在动（徽标与下载页拆分），
 * 台账这张表只在历史页用到，所以类型与解析都收在自己的文件里，共享文件一个字节都不碰。
 */

/**
 * 台账里每一条（字段名冻结，见设计文档 §4）。
 *
 * `sizeText` / `thumb` 都是**后端算好给的**（`size_text()` / `image_url()`），
 * 前端不再自己换算：同一个字节数在两处显示成不同写法比缺省更糟。
 */
export interface DownloadRecord {
  /** 归一化 key（`IPZZ-961` / `ipzz00961` / `IPZZ961` 归一后的形态），删除时回传它。 */
  key?: string
  /** 展示用番号（javdb 口径 `IPZZ-961`）。 */
  number?: string
  title?: string
  actor?: string
  /** 图床原地址或插件图片代理地址；台账里没图则是空串。 */
  thumb?: string
  /** 字节数（未知 0，本页不直接显示它）。 */
  size?: number
  /** 后端格式化好的大小（如 `1.2 GB`）。 */
  sizeText?: string
  hash?: string
  /** `downloading` | `downloaded`（台账里落的多是后者）。 */
  state?: string
  /** `plugin`=插件提交 | `library`=在 Emby 库里发现 | `queue`=老队列迁移。 */
  source?: string
  createdAt?: string
  completedAt?: string
  path?: string
  /**
   * 实时 Emby 命中；不在库里是 `null`。
   *
   * `null` 有两种含义（从没入库 / 已被删），设计文档 §4 要求前端**统一**显示
   * 「不在库（可能已删除）」——所以这里不做区分。
   */
  lib?: { id?: string; name?: string; path?: string; url?: string } | null
}

/** 后端给的三个计数（`/downloads` 顺带算出，前端不再自己数一遍规范口径）。 */
export interface DownloadCounts {
  total?: number
  inLibrary?: number
  missing?: number
}

/** 一次列表请求解析出来的东西。 */
export interface DownloadListPayload {
  items: DownloadRecord[]
  /** 后端给不出计数时为 `null`，调用方退回本地计数。 */
  counts: DownloadCounts | null
}

/** 只认真正的列表：非数组一律当"没给"。 */
function asItems(value: unknown): DownloadRecord[] | null {
  return Array.isArray(value) ? (value as DownloadRecord[]) : null
}

/** 计数只认对象；一个数字都没有就返回 `null`（不拿空对象去冒充后端计数）。 */
function asCounts(value: unknown): DownloadCounts | null {
  if (!value || typeof value !== 'object' || Array.isArray(value)) return null
  const raw = value as Record<string, unknown>
  const keys: Array<keyof DownloadCounts> = ['total', 'inLibrary', 'missing']
  if (!keys.some(k => typeof raw[k] === 'number')) return null
  const counts: DownloadCounts = {}
  keys.forEach(k => {
    if (typeof raw[k] === 'number') counts[k] = raw[k] as number
  })
  return counts
}

/**
 * 从任意形态的响应里取出 `items` / `counts`。
 *
 * 三种形态都认（与 `usePluginApi.unwrap` 同一条容错纪律）：
 * 1. 契约写法：`{success:true, items:[…], counts:{…}}`（**不套 `data`**，所以 `unwrap` 不动它）；
 * 2. 套了信封：`{success:true, data:{items:[…]}}`（宿主/后端若改形态，界面不该跟着死）；
 * 3. 裸数组。
 */
export function parseDownloadList(response: unknown): DownloadListPayload {
  const raw = response as Record<string, any> | null | undefined
  let items = asItems(raw)
  let counts = asCounts(raw?.counts)
  if (!items) items = asItems(raw?.items)
  if (!items) items = asItems(raw?.data)
  if (!items) items = asItems(raw?.data?.items)
  if (!counts) counts = asCounts(raw?.data?.counts)
  return { items: items || [], counts }
}

/**
 * 归一化 key：去空白、去连字符、转大写。**与后端 `emby.norm_key()` 逐条同规则**：
 *
 * ```python
 * raw = re.sub(r"[^0-9A-Za-z]", "", str(text or "")).upper()
 * return re.sub(r"0*(\d+)", lambda m: str(int(m.group(1))), raw)   # 还要抹掉数字段前导零
 * ```
 *
 * 抹前导零这一步不能省：台账里的 `key` 用的就是后端归一化结果，用户按 javdb 的写法
 * 搜 `ipzz961` 时，两边不抹零就会变成 `IPZZ961` vs `IPZZ00961`、**搜不到自己刚下过的片**。
 *
 * 本页两处用得到：搜索时让用户输入哪种写法都能命中，以及 `recordKey` 的兜底。
 */
export function normKey(value: unknown): string {
  const raw = String(value ?? '')
    .replace(/[^0-9A-Za-z]/g, '')
    .toUpperCase()
  if (!raw) return ''
  return raw.replace(/0*(\d+)/g, (_, digits: string) => String(parseInt(digits, 10)))
}

/** 一行是否有对应的 Emby 记录（`lib` 是 `null` = 不在库，见设计文档 §4）。 */
export function inLibrary(item: DownloadRecord): boolean {
  const lib = item?.lib
  return !!lib && typeof lib === 'object'
}

/** 列表这一行的 key（台账本就是唯一的，缺字段时才退回序号）。 */
export function recordKey(item: DownloadRecord, index: number): string {
  const explicit = String(item?.key || '').trim()
  if (explicit) return explicit
  const number = normKey(item?.number)
  if (number) return number
  return `#${index}`
}

/**
 * 展示用番号：`number` 为空时退回原始 `key`（老实现那套"能列出来就别空着"）。
 */
export function displayNumber(item: DownloadRecord): string {
  const number = String(item?.number || '').trim()
  if (number) return number
  return String(item?.key || '').trim()
}

/**
 * 完成时间：`completedAt` 为空时用 `createdAt`（设计文档 §5.1 的明确要求），
 * 两者都空显示 `—`（与订阅页 `lastText` 对空时间的口径一致）。
 */
export function completedText(item: DownloadRecord): string {
  const raw = String(item?.completedAt || item?.createdAt || '').trim()
  return raw || '—'
}

/** 大小：后端 `sizeText` 优先，缺省显示 `—`（不一味拼 `0 B`）。 */
export function sizeLabel(item: DownloadRecord): string {
  const text = String(item?.sizeText || '').trim()
  return text || '—'
}

/** 库状态文案（`lib == null` 的两种含义在设计文档 §4 里就统一成这一句）。 */
export function libraryLabel(item: DownloadRecord): string {
  return inLibrary(item) ? '在库' : '不在库（可能已删除）'
}

/**
 * 本地过滤：搜索词按**番号（归一后）/ 标题 / 演员**匹配，可选「只看不在库」。
 *
 * 归一化只对番号做：标题与演员是人名/片名，去掉连字符反而可能误命中；
 * 但用户搜 `ipzz-961` 与 `IPZZ961` 必须都能查到同一部，所以番号那一栏归一后包含匹配。
 *
 * 顺序**不动**：后端按 `completed_at DESC, created_at DESC` 给（设计文档 §2 的索引口径），
 * 前端再排一遍就是两套口径。
 */
export function filterRecords(
  items: DownloadRecord[],
  query: string,
  onlyMissing: boolean,
): DownloadRecord[] {
  const text = String(query || '').trim().toLowerCase()
  const key = normKey(text)
  return (items || []).filter(item => {
    if (!item) return false
    if (onlyMissing && inLibrary(item)) return false
    if (!text) return true
    const number = normKey(item.number || item.key)
    const title = String(item.title || '').toLowerCase()
    const actor = String(item.actor || '').toLowerCase()
    return (
      (!!key && number.includes(key)) ||
      title.includes(text) ||
      actor.includes(text)
    )
  })
}
