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
from langgraph.graph import END, START, StateGraph

from agent.graph.react_graph import build_react_graph
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


# ==================== 子任务分发（阶段3-2） ====================

def _next_runnable(plan: list[dict]) -> dict | None:
    """按拓扑序选出下一个可执行的子任务（没有则返回 None）。

    拓扑序的稳定实现：按 plan 声明顺序扫描，返回第一个
    「status 为 pending 且其 deps 全部 success」的子任务。
    依赖全部满足才选它，天然保证前置任务先于后继任务执行；
    同级（互相无依赖）任务按声明顺序串行执行，结果确定可复现。

    Java 类比：Kahn 拓扑排序里「入度为 0 就出队」，这里改成
    「依赖集合已被满足就出队」，边扫边选，无需预先算出完整拓扑序。
    """
    succeeded = {t["id"] for t in plan if t.get("status") == "success"}
    for task in plan:
        if task.get("status") != "pending":
            continue
        if all(dep in succeeded for dep in task.get("deps", [])):
            return task
    return None


def dispatcher_node(state: AgentState) -> dict:
    """按拓扑序分发子任务：选中下一个可执行子任务并置为 running。

    返回 {"plan": 更新后的计划, "current_subtask_id": 子任务 id}，
    executor（阶段3-3）据 current_subtask_id 取任务执行，执行完把
    status 改成 success/failed 再回到本节点，循环直到计划跑完。

    没有可执行子任务时返回 {} 空更新：此时要么全部完成，要么卡死
    （失败/依赖失败），由 dispatch_route 条件边决定去 END 还是 replan。
    """
    plan = state["plan"]
    task = _next_runnable(plan)
    if task is None:
        return {}

    # 只把选中的那条改成 running，其余原样返回（plan 无 reducer，整体覆盖写回）
    new_plan = [
        {**t, "status": "running"} if t["id"] == task["id"] else t for t in plan
    ]
    return {"plan": new_plan, "current_subtask_id": task["id"]}


def dispatch_route(state: AgentState) -> str:
    """dispatcher 的条件边：决定 执行 / 结束 / 重规划。

    判断顺序：
        1. 有 running 的子任务 -> "execute"（刚分派出去，去执行它）
        2. 计划非空且全部 success -> "end"（流水线跑完）
        3. 其余（有 failed 或依赖失败的 pending，导致无任务可跑）-> "replan"
    """
    plan = state.get("plan", [])

    current = state.get("current_subtask_id")
    if current and any(
        t["id"] == current and t.get("status") == "running" for t in plan
    ):
        return "execute"

    if plan and all(t.get("status") == "success" for t in plan):
        return "end"

    return "replan"


# ==================== 子任务执行（阶段3-3，复用 ReAct 循环） ====================

# 四个子 Agent 的角色人格：executor 按子任务的 agent 字段取对应 prompt，
# 套到同一个 ReAct 循环上——这就是「上层编排复用底层 ReAct 推理」。
SUBTASK_SYSTEM_PROMPTS = {
    "knowledge": (
        "你是「知识检索 Agent」，负责检索与任务相关的课件/资料，并做知识点提取与资料溯源。"
        "需要时调用检索工具；只依据检索到的内容作答，检索不到就明确说明「未找到课件依据」，"
        "不要编造。最后输出本步骤的检索结论与关键依据。"
    ),
    "code": (
        "你是「代码实验 Agent」，负责代码编写、运行调试与报错修复。"
        "需要时调用计算/代码相关工具；遇到报错要定位原因、修正后重试。"
        "最后输出可用的代码及简要说明。"
    ),
    "writer": (
        "你是「内容写作 Agent」，负责把已有中间结果汇总成结构化文档/报告。"
        "必须基于给定的前置子任务结果来写，不要凭空重造内容。"
        "最后输出条理清晰的最终文档。"
    ),
    "reviewer": (
        "你是「评审辩论 Agent」，负责审查上游产出的漏洞、边界问题与不规范处并给出修改建议。"
        "每条意见尽量引用上游内容作为依据。最后输出评审意见清单。"
    ),
}


def _build_subtask_input(
    task: dict, results: dict, user_input: str
) -> str:
    """把「总任务 + 本步骤 + 已完成的前置结果」拼成子任务的输入消息。

    带上前置结果是为了让 writer 汇总、reviewer 审查时有据可依，
    对应《架构设计》场景二步骤 9「从全局 State 汇总中间结果，而非重新生成」。
    """
    lines = [
        f"用户总任务：{user_input}",
        "",
        f"当前子任务（第 {task['id']} 步，执行者 {task['agent']}）：{task['desc']}",
    ]
    if results:
        lines.append("")
        lines.append("已完成的前置子任务结果（供参考/汇总）：")
        for tid, text in results.items():          # dict 保持插入序 = 执行序
            lines.append(f"- [{tid}] {text}")
    lines.append("")
    lines.append("请完成当前子任务，直接给出本步骤的产出结果。")
    return "\n".join(lines)


def _run_subtask(task: dict, results: dict, user_input: str) -> str:
    """跑一个子任务：按角色挂 system prompt，复用 ReAct 子图跑完取最终回答。

    每个子任务是独立的 ReAct 会话（不接 Checkpointer，避免污染父会话记忆）。
    """
    graph = build_react_graph(
        system_prompt=SUBTASK_SYSTEM_PROMPTS[task["agent"]]
    )
    result = graph.invoke(
        {
            "messages": [
                HumanMessage(content=_build_subtask_input(task, results, user_input))
            ],
            "user_input": user_input,
            "iteration_count": 0,
        }
    )
    return str(result["messages"][-1].content)


def executor_node(state: AgentState) -> dict:
    """执行 current_subtask_id 指向的子任务（内部复用 ReAct 循环）。

    取出子任务 -> 按 agent 挂角色 prompt 跑 ReAct -> 结果写入 subtask_results，
    并把该子任务 status 置为 success / failed（失败交给 replan 局部重规划）。
    """
    plan = state["plan"]
    cid = state["current_subtask_id"]
    task = next((t for t in plan if t["id"] == cid), None)
    if task is None:
        return {}

    results = dict(state.get("subtask_results", {}))
    try:
        output = _run_subtask(task, results, state.get("user_input", ""))
        status = "success"
    except Exception as exc:  # noqa: BLE001 —— 子任务失败不炸整条流水线，交 replan
        output = f"执行失败：{exc}"
        status = "failed"

    new_plan = [
        {**t, "status": status} if t["id"] == cid else t for t in plan
    ]
    if status == "success":                        # 只沉淀成功产出，失败的不污染下文
        results[cid] = output
    return {"plan": new_plan, "subtask_results": results}


# ==================== 后续阶段（3-4）占位 ====================

def replan_node(state: AgentState) -> dict:
    """局部重规划：子任务失败时回填失败信息，只重规划失败部分。"""
    # TODO(阶段3-4)：更新 plan 中失败子任务，保留成功子任务结果
    raise NotImplementedError("replan 节点待实现（阶段3-4）")


def build_plan_graph(checkpointer=None):
    """构建 Plan-and-Execute 子图。

    图结构：
        START -> planner -> dispatcher
        dispatcher --(dispatch_route)--> executor / END / replan
        executor -> dispatcher   （执行完一条子任务，回到调度器选下一条）
        replan   -> dispatcher   （局部重规划后，重新调度）

    Java 类比：planner 是项目经理出计划，dispatcher 是调度器按依赖派活，
    executor 是一道工序（内部还是 ReAct），replan 是返工重排。
    """
    graph = StateGraph(AgentState)

    graph.add_node("planner", planner_node)
    graph.add_node("dispatcher", dispatcher_node)
    graph.add_node("executor", executor_node)
    graph.add_node("replan", replan_node)

    graph.add_edge(START, "planner")
    graph.add_edge("planner", "dispatcher")
    graph.add_conditional_edges(
        "dispatcher",
        dispatch_route,
        {"execute": "executor", "end": END, "replan": "replan"},
    )
    graph.add_edge("executor", "dispatcher")
    graph.add_edge("replan", "dispatcher")

    return graph.compile(checkpointer=checkpointer)