"""文档入库（阶段 2：把「加载 → 分块 → 向量化 → 写库」串成一条管道）。

这是阶段 2 验证「上传课件 → 检索 → 回答」的入口，也是未来 FastAPI
上传接口复用的逻辑。三步分别复用已实现模块：

    load_document   PDF 字节 -> 每页文本        （rag/loader.py）
    split_text      每页文本 -> chunk 列表       （rag/splitter.py）
    add_documents   chunk -> 向量 -> 写 collection（rag/vector_store.py）

Java 类比：
    ingest = 数据仓库的 ETL（Extract-Transform-Load）管道，
    这里是「文档 -> 知识库」的专用 ETL，最终落点是向量库 collection。
"""

import argparse
from pathlib import Path

from agent.rag.loader import LocalSource, load_document
from agent.rag.splitter import split_text
from agent.rag.vector_store import COLLECTION_PRIVATE, add_documents


def ingest_pdf(
    path: str,
    collection: str = COLLECTION_PRIVATE,
    chunk_size: int = 500,
    overlap: int = 50,
) -> int:
    """把单个 PDF 课件加载、分块、向量化后写入向量库，返回写入的 chunk 数。

    逐页分块并给每个 chunk 打 metadata（来源文件 + 页码），
    这样检索命中后能定位「这段出自第几页」，便于溯源。
    """
    pages = load_document(LocalSource(), path)

    chunks: list[str] = []
    metadatas: list[dict] = []
    for page_no, page in enumerate(pages, start=1):
        for chunk in split_text(page, chunk_size=chunk_size, overlap=overlap):
            chunks.append(chunk)
            metadatas.append({"source": Path(path).name, "page": page_no})

    add_documents(collection, chunks, metadatas)
    return len(chunks)


def ingest_directory(
    dir_path: str,
    collection: str = COLLECTION_PRIVATE,
    chunk_size: int = 500,
    overlap: int = 50,
) -> int:
    """批量入库一个目录下所有 PDF，返回总 chunk 数（单文件失败不中断）。"""
    base = Path(dir_path)
    if not base.is_dir():
        raise NotADirectoryError(f"目录不存在：{base}")

    total = 0
    for file in sorted(base.rglob("*.pdf")):
        try:
            total += ingest_pdf(str(file), collection, chunk_size, overlap)
        except Exception as exc:  # noqa: BLE001 —— 单文件失败不影响批量
            print(f"[跳过] {file.name}：{exc}")
    return total


def main() -> None:
    parser = argparse.ArgumentParser(description="把 PDF 课件入库到向量库")
    parser.add_argument("path", help="PDF 文件或目录路径")
    parser.add_argument(
        "--collection",
        default=COLLECTION_PRIVATE,
        help="目标 collection（默认 user_private，另可选 user_history / public）",
    )
    parser.add_argument("--chunk-size", type=int, default=500)
    parser.add_argument("--overlap", type=int, default=50)
    args = parser.parse_args()

    p = Path(args.path)
    if p.is_dir():
        n = ingest_directory(args.path, args.collection, args.chunk_size, args.overlap)
    else:
        n = ingest_pdf(args.path, args.collection, args.chunk_size, args.overlap)

    print(f"入库完成：共 {n} 个 chunk 写入 collection「{args.collection}」")


if __name__ == "__main__":
    main()