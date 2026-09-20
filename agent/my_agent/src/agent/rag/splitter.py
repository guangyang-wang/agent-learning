"""文本分块（阶段 2 任务 2）。

把长文档切成适合嵌入的 chunk，兼顾「语义完整」与「长度上限」。

核心算法 = 递归字符分割（Recursive Character Splitting），分两步：
    1. 递归切分：用一组「由强到弱」的分隔符逐级切（先段落 -> 再句子 -> 最后单字），
       保证 chunk 尽量落在语义边界上，而不是把一句话拦腰截断；
    2. 合并重叠：把小碎片拼回接近 chunk_size，相邻 chunk 之间保留 overlap 个字符重叠，
       避免知识点被边界切断。

Java 类比：
    String.split() 只能按单一分隔符切且会丢弃分隔符；
    这里的递归分割 = 自定义一个「会挑分隔符、会保留标点」的更聪明的 split。
    chunk = 类似分页，overlap = 相邻两页共用的那几行，防止信息正好卡在页缝里。

说明：langchain 的 RecursiveCharacterTextSplitter 就是这个算法的封装版
（多加了按 token 计量、keep_separator 开关等）。这里手写一遍是为了看清底层，
后续想切回封装版，把 split_text 内部换成 RecursiveCharacterTextSplitter 即可。
"""

from typing import Sequence

# 分隔符按「语义强度」从高到低排列，最后 "" 表示「逐字切」的兜底
_DEFAULT_SEPARATORS: tuple[str, ...] = (
    "\n\n",  # 段落
    "\n",    # 换行
    "。",    # 句号
    "！",    # 感叹号
    "？",    # 问号
    "；",    # 分号
    "，",    # 逗号
    "、",    # 顿号
    " ",     # 空格（英文单词边界）
    "",      # 兜底：逐字符切
)


def _split_by_separator(text: str, separator: str) -> list[str]:
    """按单个分隔符切分，并把分隔符保留在左侧片段尾部。

    Python 的 str.split() 会丢弃分隔符，这里手动把它拼回每个片段末尾，
    避免「句号被吞掉」导致 chunk 语义残缺。

    Java 对比：Java 的 String.split() 默认按正则切、丢分隔符、丢尾部空串；
    Python 的 str.split() 按字面量切、同样丢分隔符，所以都需要手动补回。
    """
    if separator == "":
        return list(text)  # 兜底：无分隔符可用，逐字切

    parts = text.split(separator)
    # 分隔符出现在两个片段之间，因此除最后一个片段外，每个片段末尾都应补回一个分隔符
    result = [p + separator for p in parts[:-1]]
    if parts[-1]:  # 最后一段后面没有分隔符，原样收下（若为空则丢弃）
        result.append(parts[-1])
    return result


def _hard_split(text: str, chunk_size: int) -> list[str]:
    """对「没有任何分隔符能再切」的超长片段（如超长英文单词/URL），按 chunk_size 硬切。"""
    return [text[i:i + chunk_size] for i in range(0, len(text), chunk_size)]


def _split_recursive(
    text: str, separators: Sequence[str], chunk_size: int
) -> list[str]:
    """递归核心：用「由强到弱」的分隔符逐级切，直到每个碎片 <= chunk_size。

    算法：
        1. 在 separators 里找到「当前文本里真正出现、且优先级最高」的分隔符；
        2. 用该分隔符切开；
        3. 每个碎片：长度达标就收下；过长则换「更弱」的分隔符递归再切；
           没有更弱分隔符可用时，按 chunk_size 硬切。
    """
    # 1. 选分隔符：默认用最弱分隔符兜底；一旦发现文本里出现了更强的，就提前用它
    separator = separators[-1]
    next_separators: list[str] = []
    for i, sep in enumerate(separators):
        if sep == "":
            separator = sep
            break
        if sep in text:
            separator = sep
            next_separators = list(separators[i + 1:])
            break

    # 2. 切开
    pieces = _split_by_separator(text, separator)

    # 3. 递归处理过长的碎片
    chunks: list[str] = []
    for piece in pieces:
        if len(piece) <= chunk_size:
            chunks.append(piece)
        elif next_separators:
            chunks.extend(_split_recursive(piece, next_separators, chunk_size))
        else:
            chunks.extend(_hard_split(piece, chunk_size))
    return chunks


def _merge_with_overlap(
    pieces: list[str], chunk_size: int, overlap: int
) -> list[str]:
    """把小碎片合并成接近 chunk_size 的 chunk，相邻 chunk 之间保留 overlap 个字符重叠。

    为什么要重叠：知识点可能刚好横跨分块边界。让相邻 chunk 有 overlap 个字符
    交集，能保证边界处语义不断裂，检索时命中率更高。
    """
    if not pieces:
        return []

    chunks: list[str] = []
    buffer = pieces[0]
    for piece in pieces[1:]:
        if len(buffer) + len(piece) <= chunk_size:
            buffer += piece
        else:
            chunks.append(buffer)
            # 下一段从上一段尾部「回退 overlap 个字符」开始，制造重叠
            buffer = buffer[-overlap:] + piece if overlap else piece
    chunks.append(buffer)
    return chunks


def split_text(
    text: str,
    chunk_size: int = 500,
    overlap: int = 50,
    separators: Sequence[str] = _DEFAULT_SEPARATORS,
) -> list[str]:
    """把长文本切成适合嵌入的 chunk 列表。

    两步：
        1. 递归切分（_split_recursive）：按语义边界切成 <= chunk_size 的碎片；
        2. 合并重叠（_merge_with_overlap）：拼回接近 chunk_size，相邻 chunk 保留 overlap。

    参数校验：overlap 必须小于 chunk_size，否则相邻 chunk 会完全重叠、无法推进。
    """
    if not text.strip():
        return []
    if chunk_size <= 0:
        raise ValueError(f"chunk_size 必须 > 0，当前为 {chunk_size}")
    if overlap < 0:
        raise ValueError(f"overlap 必须 >= 0，当前为 {overlap}")
    if overlap >= chunk_size:
        raise ValueError(f"overlap({overlap}) 必须小于 chunk_size({chunk_size})")

    pieces = _split_recursive(text, separators, chunk_size)
    return _merge_with_overlap(pieces, chunk_size, overlap)
