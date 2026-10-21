"""多 Agent 对等辩论子图（阶段4）。

主观评审任务：立论 / 批判 / 仲裁 三个对等 Agent 轮流发言，写入消息池，
    满足收敛条件后由仲裁 Agent 输出评审报告。

关键点：
    - 无预先规划（独立于 Plan 架构的第二类多 Agent 形态）
    - 观点语义去重，防止重复
    - 最大辩论轮次 + 收敛条件，防止永不收敛 / token 爆炸

图结构：
    START -> propose -> critique --(should_converge)--> propose / arbitrate
    arbitrate -> END

Java 类比：
    debate_messages 是共享的「会议纪要」List，三个 Agent 轮流 append；
    should_converge 是循环的出口判断（满足条件就 break，交给主持人总结）；
    arbitrate 是主持人，最后输出一份完整评审报告。
"""

import re
from difflib import SequenceMatcher

from langchain_core.messages import HumanMessage, SystemMessage
from langgraph.graph import END, START, StateGraph

from agent.llm.factory import get_llm
from agent.rag.retriever import retrieve_with_fallback
from agent.state import AgentState

# 最大辩论轮次（一轮 = 立论 + 批判）。到达后强制进入仲裁，防止无限循环。
MAX_DEBATE_ROUNDS = 3
# 同角色相邻发言的相似度阈值：超过即视为「观点重复」，提前收敛。
REPEAT_SIMILARITY_THRESHOLD = 0.85
# 注入提示词的长度上限，避免论文全文 / 检索结果把上下文撑爆。
MAX_PAPER_CHARS = 6000
MAX_EVIDENCE_CHARS = 4000
# 检索查询只取用户输入开头一段：论文全文做 embedding 查询既慢也不准。
_RETRIEVAL_QUERY_CHARS = 500

_ROLE_LABELS = {
    "propose": "立论 Agent",
    "critique": "批判 Agent",
    "arbitrator": "仲裁 Agent",
}

# 批判 Agent 明确表示「没有新观点」时的短句标记（走提前收敛）。
_NO_NEW_MARKERS = (
    "无新增观点",
    "没有新的质疑",
    "无新增有效质疑",
    "未发现新的问题",
)

PROPOSE_SYSTEM = (
    "你是论文评审辩论中的「立论 Agent」。你的职责是基于原文，客观总结论文的优点、"
    "亮点和可取之处，并为论文中合理的部分辩护。你必须引用提供的原文依据；"
    "找不到依据时明确写「未找到原文依据」，绝不编造。"
    "不要重复此前立论已经提出的观点。只输出本轮发言正文，不要输出角色名或额外解释。"
)

CRITIQUE_SYSTEM = (
    "你是论文评审辩论中的「批判 Agent」。你的职责是找出论文的逻辑漏洞、论证缺陷、"
    "方法问题、数据问题和规范性错误。每条质疑都必须引用原文依据；"
    "无法引用原文的只能标注为「推测」。不要重复此前批判已经提出的问题。"
    "如果本轮确实没有新的有效质疑，只输出「本轮无新增观点」。"
    "只输出本轮发言正文，不要输出角色名或额外解释。"
)

ARBITRATE_SYSTEM = (
    "你是论文评审辩论中的「仲裁 Agent」。你不站队，负责综合立论与批判双方的观点，"
    "去重、核实依据，给出一份可直接使用的完整评审报告。"
    "报告中必须区分「有原文依据的结论」和「推测性意见」，不能编造依据。"
    "只输出 Markdown 格式的评审报告正文。"
)


# ==================== 通用工具 ====================

def _text_of(content) -> str:
    """把模型返回的 content 统一成字符串（兼容多模态内容块）。"""
    if isinstance(content, list):
        return "".join(
            block.get("text", "") for block in content if isinstance(block, dict)
        )
    return str(content or "")


def _chat(system_prompt: str, user_prompt: str) -> str:
    """单轮 LLM 调用：角色提示词 + 本轮上下文，返回正文。"""
    response = get_llm().invoke(
        [
            SystemMessage(content=system_prompt),
            HumanMessage(content=user_prompt),
        ]
    )
    return _text_of(response.content).strip()


def _truncate(text: str, limit: int) -> str:
    """超长文本截断，保留开头并明确标注被截断。"""
    text = str(text or "").strip()
    if len(text) <= limit:
        return text
    return text[:limit] + "\n…（内容过长，已截断）"


def _paper(state: AgentState) -> str:
    """评审对象：用户请求本身（可能直接贴了论文全文）。"""
    return _truncate(state.get("user_input", ""), MAX_PAPER_CHARS)


def _retrieve_evidence(query: str) -> str:
    """为辩论双方取 RAG 依据。

    评审对象可能是直接贴进来的论文，也可能已上传入库。这里统一查一次，
    把命中的原文片段注入提示词，让「必须引用原文」有可引用的材料。
    检索失败不阻断辩论：明确告诉模型依据不可用，避免它编造。
    """
    query = str(query or "").strip()[:_RETRIEVAL_QUERY_CHARS]
    if not query:
        return "（无评审对象，无法检索依据）"

    try:
        chunks, hit_private = retrieve_with_fallback(query)
    except Exception as exc:  # noqa: BLE001 —— 检索故障不应让整场评审挂掉
        return (
            f"（检索不可用：{type(exc).__name__}: {exc}。"
            "请仅依据用户提供的内容评审。）"
        )

    if not chunks:
        return "（无课件依据）未在课件库中检索到相关原文，请仅依据用户提供的内容评审。"

    header = "" if hit_private else "（以下来自个人沉淀库，非课件原文，仅供参考）\n"
    return _truncate(header + "\n\n---\n\n".join(chunks), MAX_EVIDENCE_CHARS)


def _format_pool(pool: list[dict]) -> str:
    """把辩论消息池格式化成可读的「会议纪要」。"""
    if not pool:
        return "（暂无发言）"
    lines = []
    for message in pool:
        role = message.get("role", "unknown")
        label = _ROLE_LABELS.get(role, role)
        lines.append(f"【{label}】\n{message.get('content', '')}")
    return "\n\n".join(lines)


# ==================== 收敛判断 ====================

# 去空白和标点后再比较，避免「换行 / 标点不同」被误判成新观点。
_PUNCT_RE = re.compile(r"[\s，。！？；：、,.!?;:（）()【】\[\]“”\"'`#*\-]+")


def _normalize(text: str) -> str:
    return _PUNCT_RE.sub("", str(text or ""))


def _similarity(a: str, b: str) -> float:
    """文本相似度（0~1）：字符序列相似度 + 字符二元组 Jaccard，取较大值。

    不用 embedding 做语义相似度，是为了让收敛判断**确定性、离线可测、零额外成本**；
    中文按字符比较已经能识别「换个说法重复同一句话」。
    """
    na, nb = _normalize(a), _normalize(b)
    if not na or not nb:
        return 0.0

    # autojunk=False：长文本里高频汉字不能被当成「无用字符」剔掉，否则相似度失真。
    sequence_score = SequenceMatcher(None, na, nb, autojunk=False).ratio()

    bigrams_a = {na[i : i + 2] for i in range(len(na) - 1)}
    bigrams_b = {nb[i : i + 2] for i in range(len(nb) - 1)}
    union = bigrams_a | bigrams_b
    jaccard = len(bigrams_a & bigrams_b) / len(union) if union else 0.0

    return max(sequence_score, jaccard)


def _is_no_new(content: str) -> bool:
    """批判 Agent 是否明确表示「本轮没有新观点」（只对短句生效，避免误判长文）。"""
    text = str(content or "").strip()
    return len(text) <= 60 and any(marker in text for marker in _NO_NEW_MARKERS)


def _is_repetitive(pool: list[dict], role: str = "critique") -> bool:
    """最新一条发言是否与同角色的历史发言重复。

    规则：
        1. 最新发言明确说「无新增观点」-> 重复
        2. 与同角色任意一条历史发言相似度 >= 阈值 -> 重复
        首轮发言没有历史可比，永远不算重复。
    """
    entries = [
        str(m.get("content", ""))
        for m in pool
        if m.get("role") == role
    ]
    if not entries:
        return False

    latest = entries[-1]
    if _is_no_new(latest):
        return True
    if len(entries) < 2:
        return False

    return any(
        _similarity(latest, previous) >= REPEAT_SIMILARITY_THRESHOLD
        for previous in entries[:-1]
    )


def _stop_reason(state: AgentState) -> str:
    """说明本次辩论为什么停下，供仲裁报告和前端展示。"""
    round_no = state.get("debate_round", 0)
    if round_no >= MAX_DEBATE_ROUNDS:
        return f"达到最大辩论轮次（{MAX_DEBATE_ROUNDS} 轮）"
    if _is_repetitive(state.get("debate_messages", []), "critique"):
        return "批判 Agent 本轮没有提出新观点（与历史批判重复），提前收敛"
    return "双方观点已收敛"


def should_converge(state: AgentState) -> str:
    """条件边：继续下一轮「立论 -> 批判」，还是进入仲裁。

    两个收敛条件（满足任一即停）：
        1. 达到最大轮次 MAX_DEBATE_ROUNDS（硬上限，防死循环）
        2. 批判 Agent 本轮观点与历史批判重复（软收敛，防无效辩论烧 token）
    """
    if state.get("debate_round", 0) >= MAX_DEBATE_ROUNDS:
        return "arbitrate"
    if _is_repetitive(state.get("debate_messages", []), "critique"):
        return "arbitrate"
    return "propose"


# ==================== 三个对等 Agent 节点 ====================

def _build_propose_prompt(state: AgentState, round_no: int) -> str:
    return (
        f"评审对象（用户请求 / 论文内容）：\n{_paper(state)}\n\n"
        f"RAG 检索到的原文依据：\n{_retrieve_evidence(state.get('user_input', ''))}\n\n"
        f"此前辩论记录：\n{_format_pool(state.get('debate_messages', []))}\n\n"
        f"当前是第 {round_no} 轮立论。请：\n"
        "1. 总结论文的优点 / 亮点（3~5 条），每条注明原文依据；\n"
        "2. 若此前有批判意见，请针对性回应（可辩护、可承认并修正）；\n"
        "3. 不得重复此前立论已经提过的观点。"
    )


def propose_node(state: AgentState) -> dict:
    """立论 Agent：总结优点，必须引用原文依据。"""
    round_no = state.get("debate_round", 0) + 1
    content = _chat(PROPOSE_SYSTEM, _build_propose_prompt(state, round_no))
    return {
        "debate_messages": [{"role": "propose", "content": content}],
    }


def _build_critique_prompt(state: AgentState, round_no: int) -> str:
    return (
        f"评审对象（用户请求 / 论文内容）：\n{_paper(state)}\n\n"
        f"RAG 检索到的原文依据：\n{_retrieve_evidence(state.get('user_input', ''))}\n\n"
        f"此前辩论记录：\n{_format_pool(state.get('debate_messages', []))}\n\n"
        f"当前是第 {round_no} 轮批判。请：\n"
        "1. 针对论文本身和立论观点，提出新的质疑（逻辑漏洞 / 论证缺陷 / 方法问题 / 规范问题）；\n"
        "2. 每条质疑注明原文依据，无依据的标注「推测」；\n"
        "3. 不得重复此前批判已经提过的问题；\n"
        "4. 如果本轮没有新的有效质疑，只输出「本轮无新增观点」。"
    )


def critique_node(state: AgentState) -> dict:
    """批判 Agent：质疑漏洞，必须引用 RAG 依据。

    一轮 = 立论 + 批判，因此轮次在这里自增；条件边随后据此判断是否收敛。
    """
    round_no = state.get("debate_round", 0) + 1
    content = _chat(CRITIQUE_SYSTEM, _build_critique_prompt(state, round_no))
    return {
        "debate_messages": [{"role": "critique", "content": content}],
        "debate_round": round_no,
    }


def _build_arbitrate_prompt(state: AgentState) -> str:
    return (
        f"评审对象（用户请求 / 论文内容）：\n{_paper(state)}\n\n"
        f"RAG 检索到的原文依据：\n{_retrieve_evidence(state.get('user_input', ''))}\n\n"
        f"完整辩论记录：\n{_format_pool(state.get('debate_messages', []))}\n\n"
        f"收敛说明：{_stop_reason(state)}\n\n"
        "请综合双方观点，输出完整评审报告，Markdown 结构如下：\n"
        "# 论文评审报告\n"
        "## 一、总体结论（给出建议等级：通过 / 小修 / 大修 / 不通过，并用一句话说明理由）\n"
        "## 二、主要优点（逐条注明原文依据）\n"
        "## 三、问题清单（用表格：严重程度 | 问题 | 原文依据 | 修改建议）\n"
        "## 四、修改优先级（先改什么、后改什么）\n"
        "## 五、评审说明（辩论轮次、收敛原因、依据局限）\n\n"
        "要求：合并重复意见；双方有争议时说明采信哪一方及理由；"
        "没有原文依据的判断必须标注「推测」。"
    )


def arbitrate_node(state: AgentState) -> dict:
    """仲裁 Agent：输出最终评审报告。"""
    report = _chat(ARBITRATE_SYSTEM, _build_arbitrate_prompt(state))
    return {
        "debate_messages": [{"role": "arbitrator", "content": report}],
        "final_output": report,
    }


# ==================== 图组装 ====================

def build_debate_graph(checkpointer=None):
    """构建多 Agent 辩论子图。

    图结构：
        START -> propose -> critique
        critique --(should_converge)--> propose（继续下一轮）/ arbitrate（收敛）
        arbitrate -> END

    Java 类比：do { 立论; 批判; } while (!converged && round < max); 然后输出总结。
    """
    graph = StateGraph(AgentState)

    graph.add_node("propose", propose_node)
    graph.add_node("critique", critique_node)
    graph.add_node("arbitrate", arbitrate_node)

    graph.add_edge(START, "propose")
    graph.add_edge("propose", "critique")
    graph.add_conditional_edges(
        "critique",
        should_converge,
        {"propose": "propose", "arbitrate": "arbitrate"},
    )
    graph.add_edge("arbitrate", END)

    return graph.compile(checkpointer=checkpointer)
