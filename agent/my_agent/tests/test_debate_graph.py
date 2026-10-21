"""多 Agent 辩论子图测试（阶段4）。

全部**离线**：把 LLM 调用和 RAG 检索都换成桩（stub），不触网、秒级跑完。
覆盖：
    - 文本相似度 / 「无新增观点」识别
    - 收敛判断（最大轮次 / 批判观点重复 / 继续下一轮）
    - 三个节点写入消息池的格式
    - 端到端：正常跑满轮次、观点重复提前收敛、首轮即无新观点
"""

import agent.graph.debate_graph as dg
from agent.graph.debate_graph import (
    _is_no_new,
    _is_repetitive,
    _retrieve_evidence,
    _similarity,
    _stop_reason,
    arbitrate_node,
    build_debate_graph,
    critique_node,
    propose_node,
    should_converge,
)

REPORT = "# 论文评审报告\n## 一、总体结论\n建议小修。\n## 二、主要优点\n- 结构完整"


# ==================== 测试基建 ====================

def _pool(*items):
    """造辩论消息池：_pool(("propose", "优点"), ("critique", "问题"))。"""
    return [{"role": role, "content": content} for role, content in items]


def _state(**kwargs):
    base = {
        "user_input": "请评审这篇论文",
        "messages": [],
        "iteration_count": 0,
        "debate_messages": [],
        "debate_round": 0,
    }
    base.update(kwargs)
    return base


def _invoke(graph, user_input="请评审这篇论文"):
    return graph.invoke(
        {
            "user_input": user_input,
            "messages": [],
            "iteration_count": 0,
            "debate_messages": [],
            "debate_round": 0,
        },
        config={"recursion_limit": 30},
    )


def _install_fakes(monkeypatch, critique_fn):
    """替换 LLM 与 RAG：立论 / 批判 / 仲裁按 system prompt 区分。"""
    counts = {"propose": 0, "critique": 0}

    def fake_chat(system_prompt, user_prompt):
        if "立论 Agent" in system_prompt:
            counts["propose"] += 1
            return f"第 {counts['propose']} 轮立论：论文结构清晰、实验完整。"
        if "批判 Agent" in system_prompt:
            counts["critique"] += 1
            return critique_fn(counts["critique"])
        return REPORT

    monkeypatch.setattr(dg, "_retrieve_evidence", lambda query: "原文依据片段")
    monkeypatch.setattr(dg, "_chat", fake_chat)
    return counts


# ==================== 相似度与重复识别 ====================

def test_similarity_ignores_whitespace_and_punctuation():
    assert _similarity("实验样本不足，结论存疑。", "实验样本不足 结论存疑") == 1.0


def test_similarity_low_for_different_opinions():
    a = "实验只用了单个数据集，样本覆盖不足，结论外推能力存疑。"
    b = "缺少与强基线方法的对比，无法证明改进来自所提模块。"
    assert _similarity(a, b) < dg.REPEAT_SIMILARITY_THRESHOLD


def test_similarity_handles_empty():
    assert _similarity("", "内容") == 0.0
    assert _similarity("内容", "") == 0.0


def test_is_no_new_recognizes_short_marker():
    assert _is_no_new("本轮无新增观点。") is True
    assert _is_no_new("没有新的质疑") is True


def test_is_no_new_ignores_long_text_that_mentions_marker():
    text = "本轮无新增观点。" + "这是一段很长的补充论证。" * 20
    assert _is_no_new(text) is False


def test_is_repetitive_first_round_is_not_repetitive():
    assert _is_repetitive(_pool(("critique", "样本不足")), "critique") is False


def test_is_repetitive_detects_same_opinion():
    pool = _pool(
        ("critique", "实验只用了单个数据集，结论外推能力存疑。"),
        ("critique", "实验只用了单个数据集，结论外推能力存疑。"),
    )
    assert _is_repetitive(pool, "critique") is True


def test_is_repetitive_allows_new_opinion():
    pool = _pool(
        ("critique", "实验只用了单个数据集，结论外推能力存疑。"),
        ("critique", "缺少与强基线方法的对比，无法证明改进来自所提模块。"),
    )
    assert _is_repetitive(pool, "critique") is False


def test_is_repetitive_only_compares_same_role():
    pool = _pool(
        ("propose", "本轮无新增观点"),
        ("critique", "实验样本不足"),
    )
    assert _is_repetitive(pool, "critique") is False


# ==================== 收敛判断 ====================

def test_should_converge_at_max_rounds():
    state = _state(debate_round=dg.MAX_DEBATE_ROUNDS)
    assert should_converge(state) == "arbitrate"


def test_should_converge_on_repeated_critique():
    state = _state(
        debate_round=2,
        debate_messages=_pool(
            ("critique", "实验只用了单个数据集，结论外推能力存疑。"),
            ("critique", "实验只用了单个数据集，结论外推能力存疑。"),
        ),
    )
    assert should_converge(state) == "arbitrate"


def test_should_converge_on_no_new_opinion_in_first_round():
    state = _state(
        debate_round=1,
        debate_messages=_pool(("critique", "本轮无新增观点")),
    )
    assert should_converge(state) == "arbitrate"


def test_should_continue_when_new_opinion():
    state = _state(
        debate_round=1,
        debate_messages=_pool(("critique", "实验只用了单个数据集，结论外推能力存疑。")),
    )
    assert should_converge(state) == "propose"


def test_stop_reason_explains_max_rounds():
    reason = _stop_reason(_state(debate_round=dg.MAX_DEBATE_ROUNDS))
    assert "最大辩论轮次" in reason


def test_stop_reason_explains_repetition():
    state = _state(
        debate_round=2,
        debate_messages=_pool(
            ("critique", "实验样本不足。"),
            ("critique", "实验样本不足。"),
        ),
    )
    assert "没有提出新观点" in _stop_reason(state)


# ==================== RAG 依据 ====================

def test_retrieve_evidence_joins_hits(monkeypatch):
    monkeypatch.setattr(
        dg, "retrieve_with_fallback", lambda query, top_k=4: (["片段一", "片段二"], True)
    )
    text = _retrieve_evidence("请评审论文")
    assert "片段一" in text and "片段二" in text
    assert "无课件依据" not in text


def test_retrieve_evidence_marks_miss(monkeypatch):
    monkeypatch.setattr(dg, "retrieve_with_fallback", lambda query, top_k=4: ([], False))
    assert "无课件依据" in _retrieve_evidence("请评审论文")


def test_retrieve_evidence_handles_error(monkeypatch):
    def boom(query, top_k=4):
        raise RuntimeError("embedding 服务不可用")

    monkeypatch.setattr(dg, "retrieve_with_fallback", boom)
    text = _retrieve_evidence("请评审论文")
    assert "检索不可用" in text
    assert "embedding 服务不可用" in text


# ==================== 节点写入 ====================

def test_propose_appends_message_and_injects_evidence(monkeypatch):
    seen = {}

    def fake_chat(system_prompt, user_prompt):
        seen["user"] = user_prompt
        return "优点：结构清晰"

    monkeypatch.setattr(dg, "_retrieve_evidence", lambda query: "原文依据片段")
    monkeypatch.setattr(dg, "_chat", fake_chat)

    out = propose_node(_state())

    assert out["debate_messages"] == [{"role": "propose", "content": "优点：结构清晰"}]
    assert "原文依据片段" in seen["user"]        # 依据确实注入了提示词


def test_critique_appends_message_and_increments_round(monkeypatch):
    monkeypatch.setattr(dg, "_retrieve_evidence", lambda query: "依据")
    monkeypatch.setattr(dg, "_chat", lambda system_prompt, user_prompt: "问题：样本不足")

    out = critique_node(_state(
        debate_round=0,
        debate_messages=_pool(("propose", "优点：结构清晰")),
    ))

    assert out["debate_round"] == 1
    assert out["debate_messages"] == [{"role": "critique", "content": "问题：样本不足"}]


def test_arbitrate_writes_final_output(monkeypatch):
    monkeypatch.setattr(dg, "_retrieve_evidence", lambda query: "依据")
    monkeypatch.setattr(dg, "_chat", lambda system_prompt, user_prompt: REPORT)

    out = arbitrate_node(_state(
        debate_round=2,
        debate_messages=_pool(
            ("propose", "优点"),
            ("critique", "问题"),
        ),
    ))

    assert out["final_output"] == REPORT
    assert out["debate_messages"][0]["role"] == "arbitrator"


# ==================== 端到端（离线桩） ====================

def test_graph_stops_at_max_rounds(monkeypatch):
    critiques = [
        "问题一：实验只用了单个数据集，样本覆盖不足，结论外推能力存疑。",
        "问题二：缺少与强基线方法的对比，无法证明本文改进来自所提模块。",
        "问题三：消融实验不完整，部分超参数的选择依据没有交代。",
    ]
    counts = _install_fakes(monkeypatch, lambda n: critiques[n - 1])

    result = _invoke(build_debate_graph())

    roles = [m["role"] for m in result["debate_messages"]]
    assert roles.count("propose") == dg.MAX_DEBATE_ROUNDS
    assert roles.count("critique") == dg.MAX_DEBATE_ROUNDS
    assert roles[-1] == "arbitrator"
    assert result["debate_round"] == dg.MAX_DEBATE_ROUNDS
    assert result["final_output"] == REPORT
    assert counts == {"propose": dg.MAX_DEBATE_ROUNDS, "critique": dg.MAX_DEBATE_ROUNDS}


def test_graph_converges_early_when_critique_repeats(monkeypatch):
    duplicate = "实验只用了单个数据集，样本覆盖不足，结论外推能力存疑。"
    counts = _install_fakes(monkeypatch, lambda n: duplicate)

    result = _invoke(build_debate_graph())

    roles = [m["role"] for m in result["debate_messages"]]
    assert counts["propose"] == 2               # 第二轮批判重复 -> 提前收敛
    assert counts["critique"] == 2
    assert roles[-1] == "arbitrator"
    assert result["debate_round"] == 2
    assert result["debate_round"] < dg.MAX_DEBATE_ROUNDS


def test_graph_converges_when_first_critique_has_no_new_opinion(monkeypatch):
    counts = _install_fakes(monkeypatch, lambda n: "本轮无新增观点")

    result = _invoke(build_debate_graph())

    assert counts == {"propose": 1, "critique": 1}
    assert result["debate_round"] == 1
    assert result["debate_messages"][-1]["role"] == "arbitrator"
    assert result["final_output"] == REPORT
