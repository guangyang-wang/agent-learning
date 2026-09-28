"""Plan-and-Execute 子图（阶段3）。

复杂流程任务：顶层规划 -> 多 Agent 按依赖序执行 -> 汇总。
每个子 Agent 内部仍是 ReAct 循环（复用底层推理底座）。

关键点：
    - 计划结构校验，失败重新规划（阶段3-1，planner，本文件已实现）
    - 子任务按依赖拓扑序执行（阶段3-2，dispatcher）
    - 子任务失败 -> 局部重规划（阶段3-4，replan）

Java 类比：
    planner   = 项目经理，产出「任务分解表」（谁做什么 + 依赖谁）
    dispatcher= 调度器，按依赖顺序派活
    每个子任务 = 一道工序，失败只返工这一道，不推倒整条流水线
"""

import json
import re

from langchain_core.messages import HumanMessage
from langgraph.graph import StateGraph

from agent.llm.factory import get_llm
from agent.state import AgentState

# ---- 计划结构常量（dispatcher / replan 阶段3-2 / 3-4 复用） ----

# 子任务可挂载的执行 Agent（对应「五大固定团队」去掉顶层的路由 Agent）
VALID_AGENTS = {"knowledge", "code", "writer", "reviewer"}
# 子任务状态机
VALID_STATUSES = {"pending", "running", "success", "failed"}
# 计划步骤上限（防止 LLM 拆出几十步导致不可控）
MAX_STEPS = 8
# 规划失败最大重试次数（每次把错误回喂给 LLM 让它修正）
MAX_PLAN_RETRIES = 3


# ==================== 计划生成（阶段3-1） ====================

def _build_plan_prompt(user_input: str, last_error: str | None = None) -> str:
    """构造规划提示词：固定 JSON 输出格式 + 明确约束规则。"""
    rules = [
        "只输出一个 JSON 数组，不要输出任何解释文字或 markdown 代码围栏",
        "子任务总数 1~8 个",
        '每个元素含字段：id（字符串编号，如 "1"）、desc（一句话描述）、agent（执行者）、deps（依赖的子任务 id 数组，无依赖则 []）',
        "agent 只能从 knowledge / code / writer / reviewer 四个中选",
        "deps 里的 id 必须存在于其它子任务的 id 中，不能依赖自己，不能形成环",
        "最后一个子任务通常是 writer 或 reviewer，负责产出最终结果",
    ]
    if last_error:
        rules.append(f"（上次输出无效，原因：{last_error}。请修正后重新只输出 JSON 数组。）")

    prompt = (
        "你是任务规划器，把用户的复杂任务拆解成有依赖关系的子任务序列（DAG）。\n\n"
        "可用执行 Agent：\n"
        "- knowledge：知识检索（RAG 查课件 / 资料）\n"
        "- code：代码编写与调试\n"
        "- writer：报告 / 文档撰写\n"
        "- reviewer：评审与审查\n\n"
        "输出规则：\n"
        + "\n".join(f"- {r}" for r in rules)
        + f"\n\n用户任务：\n{user_input}\n"
    )
    return prompt


def _extract_json_array(text: str) -> list:
    """从 LLM 输出里提取 JSON 数组（容错解析）。

    LLM 常在 JSON 外面套 markdown 围栏或解释文字，直接 json.loads 会失败。
    策略：去掉 ```json 围栏 -> 定位第一个 [ 到最后一个 ] -> 再 json.loads。
    """
    cleaned = re.sub(r"```(?:json)?", "", text).strip()
    start = cleaned.find("[")
    end = cleaned.rfind("]")
    if start == -1 or end == -1 or end <= start:
        raise ValueError(f"未找到 JSON 数组：{text[:100]}")
    return json.loads(cleaned[start : end + 1])


def _has_cycle(plan: list[dict]) -> bool:
    """用 Kahn 拓扑排序检测环：能排完所有节点则无环，反之有环。

    前提：调用前须保证 deps 引用的 id 都合法存在（_validate_plan 已先校验依赖完整性）。
    """
    ids = [t["id"] for t in plan]
    indegree = {tid: 0 for tid in ids}          # 入度 = 该任务依赖了多少个前置
    dependents = {tid: [] for tid in ids}        # tid -> 谁依赖它

    for task in plan:
        for dep in task.get("deps", []):
            indegree[task["id"]] += 1
            dependents[dep].append(task["id"])

    # 入度为 0 的先做，做完把「依赖它的」入度 -1，直到全部排完
    queue = [tid for tid, d in indegree.items() if d == 0]
    visited = 0
    while queue:
        node = queue.pop()
        visited += 1
        for nxt in dependents[node]:
            indegree[nxt] -= 1
            if indegree[nxt] == 0:
                queue.append(nxt)

    return visited != len(ids)


def _validate_plan(plan: list) -> list[str]:
    """结构校验：返回错误列表，空列表表示通过。

    校验四类问题（对应阶段3-1「结构校验步骤数 / 依赖」）：
        1. 步骤数（空 / 超上限）
        2. 字段完整性（id 唯一、desc 必填、agent 合法、status 合法）
        3. 依赖完整性（deps 引用的 id 必须存在、不能自依赖）
        4. 依赖无环（Kahn 拓扑排序）
    """
    if not isinstance(plan, list):
        return ["plan 不是 JSON 数组"]

    errors: list[str] = []

    # 1. 步骤数
    if not plan:
        errors.append("计划为空")
    elif len(plan) > MAX_STEPS:
        errors.append(f"步骤数 {len(plan)} 超过上限 {MAX_STEPS}")

    # 2. 字段完整性
    ids: set = set()
    for i, task in enumerate(plan):
        if not isinstance(task, dict):
            errors.append(f"第 {i} 步不是对象")
            continue
        tid = task.get("id")
        if not tid:
            errors.append(f"第 {i} 步缺少 id")
        elif tid in ids:
            errors.append(f"id 重复：{tid}")
        else:
            ids.add(tid)
        if not task.get("desc"):
            errors.append(f"子任务 {tid or i} 缺少 desc")
        if task.get("agent") not in VALID_AGENTS:
            errors.append(f"子任务 {tid or i} 的 agent 非法：{task.get('agent')}")
        if task.get("status", "pending") not in VALID_STATUSES:
            errors.append(f"子任务 {tid or i} 的 status 非法：{task.get('status')}")

    # 3. 依赖完整性
    for task in plan:
        if not isinstance(task, dict):
            continue
        tid = task.get("id")
        for dep in task.get("deps", []):
            if dep == tid:
                errors.append(f"子任务 {tid} 不能依赖自己")
            elif dep not in ids:
                errors.append(f"子任务 {tid} 依赖不存在的 {dep}")

    # 4. 依赖无环（仅当无其它错误时做，保证 _has_cycle 的前提成立）
    if not errors and _has_cycle(plan):
        errors.append("计划存在循环依赖")

    return errors


def _normalize_plan(plan: list) -> list[dict]:
    """给每个子任务补上 status=pending（初始状态），保证结构完整。"""
    return [{**task, "status": task.get("status", "pending")} for task in plan]


def _default_plan(user_input: str) -> list[dict]:
    """确定性兜底：LLM 规划彻底失败时，用固定三步线性计划。

    不依赖 LLM，100% 能产出，保证任务不因规划失败而整体挂掉（降级不失败）。
    代价是拆得粗一些，后续执行质量略降，但不影响任务继续推进。
    """
    return [
        {"id": "1", "desc": "检索任务相关的课件/资料", "agent": "knowledge", "deps": [], "status": "pending"},
        {"id": "2", "desc": f"执行核心任务：{user_input}", "agent": "code", "deps": ["1"], "status": "pending"},
        {"id": "3", "desc": "汇总产出最终结果", "agent": "writer", "deps": ["2"], "status": "pending"},
    ]


def _generate_plan(user_input: str) -> list[dict]:
    """让 LLM 生成计划，做结构校验，失败回喂重试，最终降级到默认模板计划。"""
    llm = get_llm()
    last_error: str | None = None

    for _ in range(MAX_PLAN_RETRIES):
        response = llm.invoke(
            [HumanMessage(content=_build_plan_prompt(user_input, last_error))]
        )
        try:
            plan = _extract_json_array(str(response.content))
        except ValueError as exc:
            last_error = f"JSON 解析失败：{exc}"
            continue

        errors = _validate_plan(plan)
        if not errors:
            return _normalize_plan(plan)
        last_error = "；".join(errors)

    # 重试耗尽仍失败 -> 降级到确定性模板计划（不抛异常，保证任务继续推进）
    return _default_plan(user_input)


def planner_node(state: AgentState) -> dict:
    """规划节点：生成任务计划 plan，做结构校验（步骤数 / 依赖）。

    返回 {"plan": [...]} 写入全局 State，供 dispatcher（阶段3-2）按拓扑序消费。
    """
    plan = _generate_plan(state["user_input"])
    return {"plan": plan}


# ==================== 后续阶段（3-2 / 3-4）占位 ====================

def dispatcher_node(state: AgentState) -> dict:
    """按拓扑序分发子任务，更新 current_subtask_id。"""
    # TODO(阶段3-2)：依赖序执行
    raise NotImplementedError("dispatcher 节点待实现（阶段3-2）")


def replan_node(state: AgentState) -> dict:
    """局部重规划：子任务失败时回填失败信息，只重规划失败部分。"""
    # TODO(阶段3-4)：更新 plan 中失败子任务，保留成功子任务结果
    raise NotImplementedError("replan 节点待实现（阶段3-4）")


def build_plan_graph() -> StateGraph:
    """构建 Plan-and-Execute 子图。"""
    # TODO(阶段3-2/3-4)：planner -> dispatcher -> (子 Agent 流水线) -> replan 兜底
    raise NotImplementedError("Plan 子图待实现（阶段3-2/3-4）")