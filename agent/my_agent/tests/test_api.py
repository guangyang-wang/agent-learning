"""FastAPI 接口测试（阶段 1-3 暴露层）。

全部**离线**：把两张图、检索、入库都换成桩（stub），不触网、不开 sqlite。
覆盖：
    - /health 存活
    - /chat 返回回答 + 回传 thread_id（未传时服务端生成、传了则沿用）
    - /plan 返回计划结构 + 最终产出（sink 子任务）
    - /ingest 上传字节入库；解析失败 -> 400
    - /retrieve hit_private 两种取值
    - service.init() 幂等：已注入假图时不被真实建图覆盖
"""

import pytest
from fastapi.testclient import TestClient
from langchain_core.messages import AIMessage

from agent.api import service
from agent.api.app import app


class _FakeGraph:
    """最小图桩：记录 invoke 入参，返回固定 state。"""

    def __init__(self, result: dict) -> None:
        self._result = result
        self.calls: list[tuple[dict, dict | None]] = []

    def invoke(self, state: dict, config: dict | None = None) -> dict:
        self.calls.append((state, config))
        return self._result


_FAKE_PLAN_STATE = {
    "plan": [
        {"id": "1", "desc": "查资料", "agent": "knowledge", "deps": [], "status": "success"},
        {"id": "2", "desc": "写代码", "agent": "code", "deps": ["1"], "status": "success"},
        {"id": "3", "desc": "汇总报告", "agent": "writer", "deps": ["2"], "status": "success"},
    ],
    "subtask_results": {"1": "资料", "2": "代码", "3": "报告正文"},
    "replan_count": 0,
}


@pytest.fixture
def fake_react():
    return _FakeGraph({"messages": [AIMessage(content="桩回答")]})


@pytest.fixture
def fake_plan():
    return _FakeGraph(_FAKE_PLAN_STATE)


@pytest.fixture
def client(monkeypatch, fake_react, fake_plan):
    """预注入假图 / 假检索 / 假入库，再用 TestClient 触发 lifespan。

    service.init() 见到 _react_graph 非空会短路，因此不会去建真图、开 sqlite。
    """
    monkeypatch.setattr(service, "_react_graph", fake_react)
    monkeypatch.setattr(service, "_plan_graph", fake_plan)
    monkeypatch.setattr(service, "search", lambda query, top_k=4: (["片段A"], True))
    monkeypatch.setattr(service, "ingest_upload", lambda filename, data: 7)

    with TestClient(app) as c:
        yield c


# ==================== /health ====================

def test_health(client):
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}


# ==================== /chat ====================

def test_chat_returns_output_and_thread_id(client, fake_react):
    r = client.post("/chat", json={"user_input": "你好", "thread_id": "t1"})

    assert r.status_code == 200
    body = r.json()
    assert body["output"] == "桩回答"
    assert body["task_type"] == "simple"
    assert body["thread_id"] == "t1"          # 传了就用它
    # thread_id 确实透传到图的 config，短期记忆才认得同一会话
    _, config = fake_react.calls[0]
    assert config["configurable"]["thread_id"] == "t1"


def test_chat_generates_thread_id_when_absent(client):
    r = client.post("/chat", json={"user_input": "你好"})
    assert r.status_code == 200
    assert r.json()["thread_id"]                # 未传 -> 服务端生成非空 id


def test_chat_llm_failure_maps_to_502(monkeypatch, client):
    class _Boom:
        def invoke(self, *a, **k):
            raise RuntimeError("模型超时")

    monkeypatch.setattr(service, "_react_graph", _Boom())
    r = client.post("/chat", json={"user_input": "你好"})
    assert r.status_code == 502
    assert "模型超时" in r.json()["detail"]


# ==================== /plan ====================

def test_plan_returns_structure_and_final_output(client):
    r = client.post("/plan", json={"user_input": "写代码并写报告"})

    assert r.status_code == 200
    body = r.json()
    assert body["task_type"] == "complex"
    assert [s["id"] for s in body["plan"]] == ["1", "2", "3"]
    assert body["plan"][1]["deps"] == ["1"]
    assert body["subtask_results"]["2"] == "代码"
    assert body["final_output"] == "报告正文"   # 取 sink 子任务 3 的产出
    assert body["replan_count"] == 0


# ==================== /ingest ====================

def test_ingest_upload_returns_chunks(client):
    r = client.post(
        "/ingest",
        files={"file": ("课件.pdf", b"%PDF-1.4 fake", "application/pdf")},
    )

    assert r.status_code == 200
    body = r.json()
    assert body["filename"] == "课件.pdf"
    assert body["chunks"] == 7
    assert body["collection"] == "user_private"


def test_ingest_bad_pdf_maps_to_400(monkeypatch, client):
    def _boom(filename, data):
        raise ValueError("未能提取出任何文本（可能是扫描版 / 图片型 PDF）")

    monkeypatch.setattr(service, "ingest_upload", _boom)
    r = client.post("/ingest", files={"file": ("x.pdf", b"junk", "application/pdf")})

    assert r.status_code == 400
    assert "扫描版" in r.json()["detail"]


# ==================== /retrieve ====================

def test_retrieve_hit_private(client):
    r = client.post("/retrieve", json={"query": "课程讲了什么"})
    assert r.status_code == 200
    assert r.json() == {"chunks": ["片段A"], "hit_private": True}


def test_retrieve_miss_private(monkeypatch, client):
    monkeypatch.setattr(service, "search", lambda query, top_k=4: ([], False))
    r = client.post("/retrieve", json={"query": "无关问题"})
    assert r.status_code == 200
    assert r.json() == {"chunks": [], "hit_private": False}


# ==================== init() 幂等 ====================

def test_init_is_noop_when_graphs_injected(client, fake_react):
    service.init()
    assert service._react_graph is fake_react     # 没被真实建图覆盖
