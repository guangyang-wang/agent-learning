"""文档加载与解析（阶段 2 任务 1）。

职责拆成两层，解耦「字节从哪来」和「字节怎么解析」：
    存储层 Source      只负责 key -> bytes（本地 / 阿里云 OSS 可插拔）
    解析层 parse_pdf    只负责 bytes -> 每页文本（纯函数，不因存储变化而改）

这样阶段 2 用 LocalSource 本地跑通，阶段 8 换 OssSource 接阿里云，
解析层一行都不用改。

Java 类比：
    DocumentSource = 抽象类 / 接口（面向接口编程），LocalSource / OssSource 是两种实现
    parse_pdf      = 拿到字节流后的解析工具类，不关心字节从哪个数据源来
"""

import io
from abc import ABC, abstractmethod
from pathlib import Path

from pypdf import PdfReader


# ==================== 解析层 ====================

def parse_pdf(data: bytes) -> list[str]:
    """把 PDF 字节解析成「每页文本」列表（一页一个元素）。

    容错策略：
        - 某一页解析失败或为空 -> 跳过该页，不拖垮整份
        - 整份都提不出文本（扫描版/图片型）-> 抛 ValueError，明确提示
    """
    reader = PdfReader(io.BytesIO(data))
    pages: list[str] = []

    for page in reader.pages:
        try:
            text = (page.extract_text() or "").strip()
        except Exception:  # noqa: BLE001 —— 单页失败只丢这一页
            continue
        if text:
            pages.append(text)

    if not pages:
        raise ValueError("未能提取出任何文本（可能是扫描版 / 图片型 PDF）")

    return pages


# ==================== 存储层 ====================

class DocumentSource(ABC):
    """文档来源抽象：给定 key，返回原始字节。

    Java 类比：接口，定义统一接口 read()，由具体来源实现。
    """

    @abstractmethod
    def read(self, key: str) -> bytes:
        """按 key 读取文档原始字节。"""
        raise NotImplementedError


class LocalSource(DocumentSource):
    """本地磁盘来源（阶段 2 开发 / 测试用）。"""

    def read(self, key: str) -> bytes:
        path = Path(key)
        if not path.exists():
            raise FileNotFoundError(f"文件不存在：{path}")
        return path.read_bytes()


class OssSource(DocumentSource):
    """阿里云 OSS 来源（阶段 8 接入，当前占位）。

    届时用 oss2 SDK 下载：bucket.get_object(key).read()，
    接入后解析层 parse_pdf 无需任何改动。
    """

    def read(self, key: str) -> bytes:
        # TODO(阶段8)：接入 oss2，从 OSS 下载字节
        #   import oss2
        #   auth = oss2.Auth(access_key_id, access_key_secret)
        #   bucket = oss2.Bucket(auth, endpoint, bucket_name)
        #   return bucket.get_object(key).read()
        raise NotImplementedError("OSS 来源待实现（阶段8）")


# ==================== 组合层 ====================

def load_document(source: DocumentSource, key: str) -> list[str]:
    """从指定来源加载单个文档：先读字节，再解析成页文本列表。"""
    return parse_pdf(source.read(key))


def load_directory(dir_path: str) -> list[str]:
    """批量加载本地目录下所有 PDF，返回所有页文本的扁平列表。

    说明：这是本地来源的便捷函数（「扫目录」本身就是本地概念）。
    阶段 8 接 OSS 后，批量加载语义会从「扫本地目录」变成
    「Java 传一批 OSS key 逐个加载」，届时改为按 key 列表加载，此函数届时调整。
    """
    base = Path(dir_path)
    if not base.is_dir():
        raise NotADirectoryError(f"目录不存在：{base}")

    source = LocalSource()
    all_pages: list[str] = []
    for file in sorted(base.rglob("*.pdf")):
        try:
            all_pages.extend(load_document(source, str(file)))
        except Exception:  # noqa: BLE001 —— 单文件失败不影响批量加载
            continue

    return all_pages