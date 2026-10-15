"""Plan-and-Execute 子图测试（阶段3）。

全部**离线**：把 LLM 调用和子任务执行都换成桩（stub），不触网、秒级跑完。
覆盖：
    - 计划结构校验（步骤数 / 字段 / 依赖完整性 / 无环）
    - 容错 JSON 解析
    - 拓扑序分发（dispatcher + 条件边）
    - 失败局部重规划（恢复 + 超预算放弃）
    - 端到端流程（成功 / 一次失败后恢复 / 反复失败放弃）
"""

import pytest

import agent.graph.plan_graph as pg
from agent.graph.plan_graph import (
    _extract_json_array,
    _has_cycle,
    _next_runnable,
    _validate_plan,
    _validate_revision,
    dispatcher_node,
    dispatch_route,
    replan_node,
)


# ==================== 测试基建 ====================

def _item(id_, agent="code", deps=None, desc="任务", status="pending"):
    """造一个计划项，字段齐全。"""
    return {"id": id_, "desc": desc, "agent": agent, "deps": deps or [], "status": status}


def _linear_plan():
    """1 -> 2 -> 3 的线性计划。"""
    return [
        _item("1", "knowledge", [], "查资料"),
        _item("2", "code", ["1"], "写代码"),
        _item("3", "writer", ["2"], "汇总"),
    ]


def _stub_graph(monkeypatch, fail_times=0):
    """把 planner / 子任务执行 / 重规划都换成桩，返回各子任务被执行的次数。

    fail_times：子任务 "2" 前若干次执行抛异常，用于制造失败。
    """
    fixed = _linear_plan()
    monkeypatch.setattr(
        pg, "planner_node", lambda state: {"plan": [dict(t) for t in fixed]}
    )

    calls: dict = {}

    def fake_run(task, results, user_input):
        cid = task["id"]
        calls[cid] = calls.get(cid, 0) + 1
        if cid == "2" and calls[cid] <= fail_times:
            raise RuntimeError("模拟失败")
        return f"[{cid}] ok"

    monkeypatch.setattr(pg, "_run_subtask", fake_run)
    monkeypatch.setattr(
        pg,
        "_revise_tasks",
        lambda u, done, failed: {
            t["id"]: {"id": t["id"], "desc": t["desc"] + "（修正）", "agent": t["agent"]}
            for t in failed
        },
    )
    return calls


def _invoke(graph):
    return graph.invoke(
        {"user_input": "测试任务", "messages": [], "iteration_count": 0},
        config={"recursion_limit": 50},
    )


# ==================== 容错 JSON 解析 ====================

def test_extract_json_array_strips_markdown_fence():
    assert _extract_json_array('```json\n[{"id": "1"}]\n```') == [{"id": "1"}]


def test_extract_json_array_ignores_surrounding_text():
    text = '这是计划：\n[{"id": "1", "desc": "x"}]\n以上。'
    assert _extract_json_array(text) == [{"id": "1", "desc": "x"}]


def test_extract_json_array_raises_when_no_array():
    with pytest.raises(ValueError):
        _extract_json_array("这里没有数组")


# ==================== 计划结构校验 ====================

def test_validate_plan_accepts_valid_dag():
    assert _validate_plan(_linear_plan()) == []


def test_validate_plan_rejects_empty():
    assert _validate_plan([]) == ["计划为空"]


def test_validate_plan_rejects_too_many_steps():
    plan = [_item(str(i)) for i in range(pg.MAX_STEPS + 1)]
    assert any("超过上限" in e for e in _validate_plan(plan))


def test_validate_plan_rejects_duplicate_id():
    plan = [_item("1"), _item("1")]
    assert any("id 重复" in e for e in _validate_plan(plan))


def test_validate_plan_rejects_bad_agent():
    plan = [_item("1", agent="router")]        # router 不在子 Agent 白名单
    assert any("agent 非法" in e for e in _validate_plan(plan))


def test_validate_plan_rejects_self_dependency():
    plan = [_item("1", deps=["1"])]
    assert any("不能依赖自己" in e for e in _validate_plan(plan))


def test_validate_plan_rejects_missing_dependency():
    plan = [_item("1", deps=["9"])]
    assert any("依赖不存在" in e for e in _validate_plan(plan))


def test_validate_plan_rejects_cycle():
    plan = [_item("1", deps=["2"]), _item("2", deps=["1"])]
    assert any("循环依赖" in e for e in _validate_plan(plan))


# ==================== 环检测（Kahn） ====================

def test_has_cycle_false_for_dag():
    assert _has_cycle(_linear_plan()) is False


def test_has_cycle_true_for_cycle():
    plan = [_item("1", deps=["2"]), _item("2", deps=["1"])]
    assert _has_cycle(plan) is True


# ==================== 拓扑序选择 ====================

def test_next_runnable_picks_first_ready_task():
    assert _next_runnable(_linear_plan())["id"] == "1"


def test_next_runnable_skips_unmet_dependencies():
    plan = _linear_plan()
    plan[0]["status"] = "success"
    assert _next_runnable(plan)["id"] == "2"


def test_next_runnable_returns_none_when_blocked():
    plan = _linear_plan()
    plan[0]["status"] = "success"
    plan[1]["status"] = "failed"          # 2 失败 -> 3 被卡死
    assert _next_runnable(plan) is None


def test_next_runnable_returns_none_when_all_done():
    plan = _linear_plan()
    for t in plan:
        t["status"] = "success"
    assert _next_runnable(plan) is None


# ==================== dispatcher 节点与条件边 ====================

def test_dispatcher_marks_selected_running():
    out = dispatcher_node({"plan": _linear_plan()})
    assert out["current_subtask_id"] == "1"
    assert out["plan"][0]["status"] == "running"
    assert out["plan"][1]["status"] == "pending"      # 其它子任务不动


def test_dispatcher_returns_empty_when_nothing_runnable():
    plan = _linear_plan()
    plan[0]["status"] = "success"
    plan[1]["status"] = "failed"
    assert dispatcher_node({"plan": plan}) == {}


def test_dispatch_route_execute_on_running_task():
    plan = _linear_plan()
    plan[0]["status"] = "running"
    assert dispatch_route({"plan": plan, "current_subtask_id": "1"}) == "execute"


def test_dispatch_route_end_when_no_pending():
    plan = _linear_plan()
    for t in plan:
        t["status"] = "success"
    assert dispatch_route({"plan": plan, "current_subtask_id": "3"}) == "end"


def test_dispatch_route_replan_when_deadlocked():
    plan = _linear_plan()
    plan[0]["status"] = "success"
    plan[1]["status"] = "failed"
    assert dispatch_route({"plan": plan, "current_subtask_id": "2"}) == "replan"


# ==================== 重规划结果校验 ====================

def test_validate_revision_accepts_covering_result():
    revised = [{"id": "2", "desc": "改", "agent": "code"}]
    assert _validate_revision(revised, {"2"}) == []


def test_validate_revision_rejects_missing_id():
    assert any("遗漏" in e for e in _validate_revision([], {"2"}))


def test_validate_revision_rejects_bad_agent():
    revised = [{"id": "2", "desc": "x", "agent": "bogus"}]
    assert any("agent 非法" in e for e in _validate_revision(revised, {"2"}))


def test_validate_revision_rejects_id_not_failed():
    revised = [{"id": "9", "desc": "x", "agent": "code"}]
    assert any("不属于失败子任务" in e for e in _validate_revision(revised, {"2"}))


# ==================== replan 节点 ====================

def test_replan_resets_failed_and_keeps_success(monkeypatch):
    plan = _linear_plan()
    plan[0]["status"] = "success"
    plan[1] = {**plan[1], "status": "failed", "error": "boom"}
    monkeypatch.setattr(
        pg,
        "_revise_tasks",
        lambda u, done, failed: {
            t["id"]: {"id": t["id"], "desc": t["desc"] + "（修正）", "agent": t["agent"]}
            for t in failed
        },
    )

    out = replan_node({"plan": plan, "user_input": "x", "replan_count": 0})
    by_id = {t["id"]: t for t in out["plan"]}

    assert by_id["1"]["status"] == "success"      # 已成功的原封不动
    assert by_id["2"]["status"] == "pending"      # 失败的重置为待跑
    assert "修正" in by_id["2"]["desc"]            # 用了修正后的描述
    assert "error" not in by_id["2"]              # 清掉上一轮失败原因
    assert out["replan_count"] == 1


def test_replan_gives_up_over_budget():
    plan = _linear_plan()
    plan[0]["status"] = "success"
    plan[1]["status"] = "failed"

    out = replan_node(
        {"plan": plan, "user_input": "x", "replan_count": pg.MAX_REPLAN}
    )
    by_id = {t["id"]: t["status"] for t in out["plan"]}

    assert by_id["1"] == "success"                # 成功部分保留
    assert by_id["2"] == "failed"
    assert by_id["3"] == "failed"                 # 被卡住的 pending 一并终态
    assert out["replan_count"] == pg.MAX_REPLAN + 1


# ==================== 子图缓存 ====================

def test_subtask_graph_cached_per_role():
    a = pg._subtask_graph("writer")
    b = pg._subtask_graph("writer")
    c = pg._subtask_graph("code")
    assert a is b                                 # 同角色复用同一张图
    assert a is not c                             # 不同角色不同图


# ==================== 端到端（离线桩） ====================

def test_graph_success_path(monkeypatch):
    _stub_graph(monkeypatch)
    r = _invoke(pg.build_plan_graph())

    assert [t["status"] for t in r["plan"]] == ["success", "success", "success"]
    assert set(r["subtask_results"]) == {"1", "2", "3"}
    assert r.get("replan_count", 0) == 0


def test_graph_recovers_from_one_failure(monkeypatch):
    calls = _stub_graph(monkeypatch, fail_times=1)
    r = _invoke(pg.build_plan_graph())

    assert [t["status"] for t in r["plan"]] == ["success", "success", "success"]
    assert calls["2"] == 2                        # 失败一次 + 重跑一次
    assert r["replan_count"] == 1
    assert "修正" in next(t for t in r["plan"] if t["id"] == "2")["desc"]


def test_graph_gives_up_after_repeated_failure(monkeypatch):
    _stub_graph(monkeypatch, fail_times=99)
    r = _invoke(pg.build_plan_graph())

    by_id = {t["id"]: t["status"] for t in r["plan"]}
    assert by_id["1"] == "success"                # 成功部分保留
    assert by_id["2"] == "failed"
    assert by_id["3"] == "failed"                 # 被卡住的一并终态
    assert r["subtask_results"] == {"1": "[1] ok"}
    assert r["replan_count"] == pg.MAX_REPLAN + 1
