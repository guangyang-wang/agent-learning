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
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage

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
    "plan_messages": [HumanMessage(content="写代码并写报告")],
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
    assert body["requests"] == ["写代码并写报告"]  # 回传本会话累计请求


def test_plan_passes_thread_id_to_graph(client, fake_plan):
    r = client.post("/plan", json={"user_input": "写代码", "thread_id": "p1"})

    assert r.status_code == 200
    assert r.json()["thread_id"] == "p1"         # 传了就用它
    # thread_id 确实透传到图的 config，规划记忆才认得同一会话
    _, config = fake_plan.calls[0]
    assert config["configurable"]["thread_id"] == "p1"


def test_plan_generates_thread_id_when_absent(client):
    r = client.post("/plan", json={"user_input": "写代码"})
    assert r.status_code == 200
    assert r.json()["thread_id"]                # 未传 -> 服务端生成非空 id


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


# ==================== 会话历史：消息过滤（纯函数） ====================

def test_visible_messages_drops_tools_and_empty_ai():
    raw = [
        HumanMessage(content="问题"),
        AIMessage(content="", tool_calls=[{"name": "t", "args": {}, "id": "1"}]),  # 调工具那轮
        ToolMessage(content="工具返回", tool_call_id="1"),
        AIMessage(content="最终回答"),
    ]
    assert service.visible_messages(raw) == [
        {"role": "user", "content": "问题"},
        {"role": "assistant", "content": "最终回答"},
    ]


def test_visible_messages_joins_multimodal_blocks():
    raw = [AIMessage(content=[{"type": "text", "text": "前"}, {"type": "text", "text": "后"}])]
    assert service.visible_messages(raw) == [{"role": "assistant", "content": "前后"}]


# ==================== 会话历史：列出与读取 ====================

class _Tup:
    """假的 CheckpointTuple：只要有 config 和 checkpoint 两个属性。

    extra 用来补 plan 图才有的通道（plan_messages / plan / subtask_results 等）。
    """

    def __init__(self, thread_id, ts, messages, ns="", extra=None):
        self.config = {"configurable": {"thread_id": thread_id, "checkpoint_ns": ns}}
        channel_values = {"messages": messages}
        if extra:
            channel_values.update(extra)
        self.checkpoint = {"ts": ts, "channel_values": channel_values}


class _FakeCheckpointer:
    def __init__(self, tups):
        self._tups = tups

    def list(self, config, **kwargs):
        return iter(self._tups)

    def get_tuple(self, config):
        return self._tups[0] if self._tups else None


@pytest.fixture
def fake_checkpointer(monkeypatch):
    def install(tups):
        cp = _FakeCheckpointer(tups)
        monkeypatch.setattr(service, "get_checkpointer", lambda: cp)
        return cp

    return install


def test_list_sessions_dedupes_keeps_newest_and_skips_subgraph(fake_checkpointer):
    fake_checkpointer([
        _Tup("t2", "2026-10-15T10:00:00+00:00", [HumanMessage(content="第二次"), AIMessage(content="答2")]),
        _Tup("t2", "2026-10-15T09:00:00+00:00", [HumanMessage(content="旧的")]),  # 同会话旧快照 -> 跳过
        _Tup("t1", "2026-10-14T10:00:00+00:00", [HumanMessage(content="第一次"), AIMessage(content="答1")]),
        _Tup("sub", "2026-10-16T10:00:00+00:00", [HumanMessage(content="子图")], ns="child"),  # 子图 -> 跳过
    ])

    out = service.list_sessions()

    assert [s["thread_id"] for s in out] == ["t2", "t1"]      # 按时间倒序
    assert out[0]["preview"] == "第二次"                       # 取的是最新的那条
    assert out[0]["message_count"] == 2                       # 用户 + AI 各一条
    assert out[1]["updated_at"] == "2026-10-14T10:00:00+00:00"


def test_list_sessions_skips_threads_without_displayable_messages(fake_checkpointer):
    fake_checkpointer([_Tup("t1", "2026-10-15T10:00:00+00:00", [ToolMessage(content="只有工具", tool_call_id="1")])])
    assert service.list_sessions() == []


def test_list_sessions_respects_limit(fake_checkpointer):
    tups = [
        _Tup(f"t{i}", f"2026-10-{i:02d}T10:00:00+00:00", [HumanMessage(content=f"问{i}")])
        for i in range(1, 6)
    ]
    fake_checkpointer(tups)

    out = service.list_sessions(limit=2)

    assert len(out) == 2
    assert [s["thread_id"] for s in out] == ["t5", "t4"]


def test_get_session_returns_empty_for_unknown_thread(fake_checkpointer):
    fake_checkpointer([])
    assert service.get_session("nope") == []


def test_get_session_returns_visible_messages(fake_checkpointer):
    fake_checkpointer([_Tup("t1", "2026-10-15T10:00:00+00:00", [
        HumanMessage(content="问题"),
        AIMessage(content="回答"),
    ])])
    assert service.get_session("t1") == [
        {"role": "user", "content": "问题"},
        {"role": "assistant", "content": "回答"},
    ]


# ==================== 会话历史接口 ====================

def test_sessions_endpoint(client, monkeypatch):
    monkeypatch.setattr(service, "list_sessions", lambda limit=20: [
        {"thread_id": "t1", "updated_at": "2026-10-15T10:00:00+00:00", "message_count": 2, "preview": "你好"},
    ])
    r = client.get("/sessions")
    assert r.status_code == 200
    assert r.json()[0]["thread_id"] == "t1"


def test_session_detail_endpoint(client, monkeypatch):
    monkeypatch.setattr(service, "get_session", lambda tid: [
        {"role": "user", "content": "你好"},
        {"role": "assistant", "content": "你也好"},
    ])
    r = client.get("/sessions/t1")
    assert r.status_code == 200
    assert r.json() == {
        "thread_id": "t1",
        "messages": [
            {"role": "user", "content": "你好"},
            {"role": "assistant", "content": "你也好"},
        ],
    }


def test_session_detail_unknown_thread_maps_to_404(client, monkeypatch):
    monkeypatch.setattr(service, "get_session", lambda tid: [])
    r = client.get("/sessions/nope")
    assert r.status_code == 404
    assert "不存在" in r.json()["detail"]


# ==================== 规划会话历史：列出与读取 ====================

def test_list_plan_sessions_dedupes_and_skips_chat(fake_checkpointer):
    fake_checkpointer([
        _Tup("p1", "2026-10-15T10:00:00+00:00", [],
             extra={"plan_messages": [HumanMessage(content="写快排")]}),
        _Tup("p1", "2026-10-15T09:00:00+00:00", [],
             extra={"plan_messages": [HumanMessage(content="旧的")]}),   # 同会话旧快照 -> 跳过
        _Tup("t1", "2026-10-16T10:00:00+00:00", [HumanMessage(content="纯聊天")]),  # 无 plan_messages -> 跳过
    ])

    out = service.list_plan_sessions()

    assert [s["thread_id"] for s in out] == ["p1"]     # 只剩规划会话，取最新那条
    assert out[0]["preview"] == "写快排"
    assert out[0]["request_count"] == 1


def test_list_plan_sessions_counts_multiple_requests(fake_checkpointer):
    fake_checkpointer([
        _Tup("p1", "2026-10-15T10:00:00+00:00", [],
             extra={"plan_messages": [HumanMessage(content="第一问"), HumanMessage(content="第二问")]}),
    ])
    out = service.list_plan_sessions()
    assert out[0]["request_count"] == 2
    assert out[0]["preview"] == "第一问"               # 标题取首个请求


def test_get_plan_session_returns_requests_and_latest_plan(fake_checkpointer):
    fake_checkpointer([
        _Tup("p1", "2026-10-15T10:00:00+00:00", [], extra={
            "plan_messages": [HumanMessage(content="第一问"), HumanMessage(content="第二问")],
            "plan": [{"id": "1", "desc": "写代码", "agent": "code", "deps": [], "status": "success"}],
            "subtask_results": {"1": "产出"},
            "replan_count": 0,
        }),
    ])

    d = service.get_plan_session("p1")

    assert d["requests"] == ["第一问", "第二问"]
    assert d["plan"][0]["id"] == "1"
    assert d["final_output"] == "产出"


def test_get_plan_session_none_for_chat_thread(fake_checkpointer):
    fake_checkpointer([_Tup("t1", "2026-10-15T10:00:00+00:00", [HumanMessage(content="聊天")])])
    assert service.get_plan_session("t1") is None


# ==================== 规划会话历史接口 ====================

def test_plan_sessions_endpoint(client, monkeypatch):
    monkeypatch.setattr(service, "list_plan_sessions", lambda limit=20: [
        {"thread_id": "p1", "updated_at": "2026-10-15T10:00:00+00:00",
         "request_count": 2, "preview": "写快排"},
    ])
    r = client.get("/plan/sessions")
    assert r.status_code == 200
    assert r.json()[0]["thread_id"] == "p1"


def test_plan_session_detail_endpoint(client, monkeypatch):
    monkeypatch.setattr(service, "get_plan_session", lambda tid: {
        "thread_id": tid,
        "requests": ["写快排"],
        "plan": [{"id": "1", "desc": "写代码", "agent": "code", "deps": [], "status": "success"}],
        "subtask_results": {"1": "ok"},
        "final_output": "最终",
        "replan_count": 0,
    })
    r = client.get("/plan/sessions/p1")
    assert r.status_code == 200
    assert r.json()["requests"] == ["写快排"]
    assert r.json()["final_output"] == "最终"


def test_plan_session_detail_unknown_maps_to_404(client, monkeypatch):
    monkeypatch.setattr(service, "get_plan_session", lambda tid: None)
    r = client.get("/plan/sessions/nope")
    assert r.status_code == 404
    assert "不存在" in r.json()["detail"]
