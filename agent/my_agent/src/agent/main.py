"""程序入口 —— 阶段 3：ReAct 底座 + Plan-and-Execute 编排。

两种执行模式的入口：
    run_qa   ：简单任务 —— 单 Agent ReAct 循环（阶段1/2，带短期记忆）
    run_plan ：复杂任务 —— Plan-and-Execute 子图（阶段3）
                规划 → 按依赖拓扑分发 → 每个子 Agent 内部复用 ReAct → 汇总产出

Java 类比：main 方法 = 启动一次「会话」；run_qa / run_plan = 两种模式的入口方法，
工作流引擎（图）负责把节点串起来跑完。
"""

import sys

from langchain_core.messages import HumanMessage

from agent.graph.plan_graph import build_plan_graph
from agent.graph.react_graph import build_react_graph
from agent.memory.short_term import get_checkpointer


def run_qa(question: str, thread_id: str = "default") -> str:
    """简单任务入口：跑一次 ReAct 问答（阶段1/2，带 Checkpointer 短期记忆）。

    同一个 thread_id 连续多轮，LangGraph 会加载上一轮 checkpoint 接上历史 messages。
    """
    graph = build_react_graph(checkpointer=get_checkpointer())

    result = graph.invoke(
        {
            "messages": [HumanMessage(content=question)],
            "user_input": question,
            "iteration_count": 0,
        },
        config={"configurable": {"thread_id": thread_id}},
    )
    return result["messages"][-1].content


def _final_output(plan: list[dict], results: dict) -> tuple[str | None, str]:
    """从子任务产出里挑出「最终输出」。

    优先取「没人依赖它」的收尾子任务（sink）——它代表整条流水线的终点产出。
    若该子任务没有产出（失败/被放弃），退回到最后一个有产出的子任务。
    """
    depended = {dep for t in plan for dep in t.get("deps", [])}
    sinks = [t for t in plan if t["id"] not in depended]
    for t in reversed(sinks):
        if t["id"] in results:
            return t["id"], results[t["id"]]
    for t in reversed(plan):
        if t["id"] in results:
            return t["id"], results[t["id"]]
    return None, "(没有可用产出)"


def run_plan(question: str) -> dict:
    """复杂任务入口：跑一次 Plan-and-Execute 子图，返回最终 State。

    不接 Checkpointer（每次全新会话）——Plan 图的记忆/恢复是后续阶段的议题。
    """
    graph = build_plan_graph()
    return graph.invoke(
        {"user_input": question, "messages": [], "iteration_count": 0},
        config={"recursion_limit": 60},
    )


def main() -> None:
    # Windows 控制台默认 GBK，打印中文会抛 UnicodeEncodeError，切成 UTF-8；
    # 部分 IDE 会重定向 stdout（没有 reconfigure），跳过即可。
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except AttributeError:
        pass

    question = "用 Python 实现一个快速排序函数，并写一份简短的实验报告说明思路和测试结果"
    print(f"[复杂任务] {question}\n")

    result = run_plan(question)
    plan = result["plan"]
    results = result.get("subtask_results", {})

    print("=== 执行计划 ===")
    for t in plan:
        print(
            f"  [{t['id']}] {t['agent']:9s} {t['status']:8s} "
            f"deps={t['deps']} :: {t['desc']}"
        )

    ok = sum(1 for t in plan if t["status"] == "success")
    print(f"\n成功 {ok}/{len(plan)} 步，重规划 {result.get('replan_count', 0)} 次")

    tid, output = _final_output(plan, results)
    print(f"\n=== 最终输出（子任务 {tid}）===")
    print(output)


if __name__ == "__main__":
    main()
