"""上传课件原文件与元数据存储。

职责：把用户上传的 PDF 原样留一份，并记录「谁、什么时候、多少片段」，
供上传历史列表与下载接口使用。

存储结构（data/uploads/）：
    <upload_id>.pdf    原始文件
    <upload_id>.json   元数据（文件名、大小、chunk 数、sha256、上传时间）

为什么用 uuid 做文件名：
    1. 同名文件不会互相覆盖（原始文件名只用于展示 / 下载时的文件名）
    2. 彻底避免把用户传入的文件名拼进路径（路径穿越）
    3. 元数据与文件一一对应，列表就是扫一遍 *.json

Java 类比：附件表 + 对象存储。json 是附件记录，pdf 是对象存储里的对象；
upload_id 是主键，sha256 用于按内容去重。
"""

import hashlib
import json
import re
import uuid
from datetime import datetime, timezone
from pathlib import Path

from agent.config import settings

_ID_RE = re.compile(r"^[0-9a-f]{32}$")


def sha256_of(data: bytes) -> str:
    """内容摘要，用于判断「同一份文件是否已上传过」。"""
    return hashlib.sha256(data).hexdigest()


def _base_dir() -> Path:
    base = Path(settings.upload_dir)
    base.mkdir(parents=True, exist_ok=True)
    return base


def _record_path(upload_id: str) -> Path:
    # 只接受自己生成的 32 位十六进制 id，挡住 ../ 之类的路径拼接
    if not _ID_RE.match(upload_id):
        raise ValueError(f"非法 upload_id：{upload_id}")
    return _base_dir() / f"{upload_id}.json"


def _read_record(path: Path) -> dict | None:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None  # 损坏 / 写了一半的记录直接跳过，不影响列表


def _write_record(record: dict) -> None:
    path = _record_path(record["upload_id"])
    tmp = path.with_suffix(".json.tmp")
    tmp.write_text(
        json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    tmp.replace(path)  # 原子替换，避免读到写了一半的 json


def find_by_sha256(digest: str) -> dict | None:
    """按内容摘要查已有上传记录（当前记录量小，扫描即可）。"""
    for path in _base_dir().glob("*.json"):
        record = _read_record(path)
        if record and record.get("sha256") == digest:
            return record
    return None


def save_upload(
    data: bytes, filename: str, chunks: int, collection: str, digest: str
) -> dict:
    """保存原文件 + 元数据，返回完整记录。"""
    upload_id = uuid.uuid4().hex
    stored_name = f"{upload_id}.pdf"

    # 浏览器一般只给文件名，但仍要剥掉可能携带的目录部分
    display_name = Path(filename).name or "upload.pdf"

    (_base_dir() / stored_name).write_bytes(data)

    record = {
        "upload_id": upload_id,
        "filename": display_name,
        "stored_name": stored_name,
        "size": len(data),
        "chunks": chunks,
        "collection": collection,
        "sha256": digest,
        "uploaded_at": datetime.now(timezone.utc).isoformat(),
    }
    _write_record(record)
    return record


def list_uploads() -> list[dict]:
    """列出全部上传记录，按上传时间倒序。"""
    records = [
        record
        for path in _base_dir().glob("*.json")
        if (record := _read_record(path)) is not None
    ]
    records.sort(key=lambda r: r.get("uploaded_at", ""), reverse=True)
    return records


def get_upload(upload_id: str) -> dict | None:
    """取单条记录；id 非法或不存在返回 None。"""
    try:
        path = _record_path(upload_id)
    except ValueError:
        return None
    return _read_record(path)


def get_upload_file(upload_id: str) -> tuple[Path, dict] | None:
    """返回（原文件路径, 记录）；记录或文件缺失返回 None。"""
    record = get_upload(upload_id)
    if record is None:
        return None
    path = _base_dir() / record["stored_name"]
    if not path.is_file():
        return None
    return path, record