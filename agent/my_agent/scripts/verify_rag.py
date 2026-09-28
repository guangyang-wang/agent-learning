"""阶段 2 端到端验证：上传课件 → 检索 → 回答。

前置（顺序执行）：
    1. python scripts/make_test_pdf.py        生成测试课件
    2. python -m agent.rag.ingest data/sample_courseware.pdf   入库

本脚本做两件事：
    1. 直接检索：验证 retriever 能从向量库命中正确片段
    2. 完整问答：跑 ReAct 图，验证 LLM 会调 rag_search 检索课件并据此作答
"""

import sys

from langchain_core.messages import HumanMessage

from agent.graph.react_graph import build_react_graph
from agent.memory.short_term import get_checkpointer
from agent.rag.retriever import retrieve_with_fallback

QUESTION = "根据课件，二次函数的顶点坐标公式是什么？"


def step1_direct_retrieve() -> None:
    print("=" * 60)
    print("步骤 1：直接检索（retriever 命中正确片段？）")
    print("=" * 60)
    chunks, hit_private = retrieve_with_fallback(QUESTION)
    print(f"是否命中私有课件库：{hit_private}，命中片段数：{len(chunks)}")
    for i, c in enumerate(chunks, 1):
        print(f"\n[片段 {i}]\n{c}")


def step2_react_qa() -> None:
    print("\n" + "=" * 60)
    print("步骤 2：完整 ReAct 问答（LLM 调 rag_search → 检索 → 作答）")
    print("=" * 60)
    graph = build_react_graph(checkpointer=get_checkpointer())
    result = graph.invoke(
        {
            "messages": [HumanMessage(content=QUESTION)],
            "user_input": QUESTION,
            "iteration_count": 0,
        },
        config={"configurable": {"thread_id": "verify-rag"}},
    )

    messages = result["messages"]
    print(f"\n消息流转（共 {len(messages)} 条）：")
    for m in messages:
        t = type(m).__name__
        if getattr(m, "tool_calls", None):
            print(f"  [{t}] 调用工具：{[c['name'] for c in m.tool_calls]}")
        else:
            content = getattr(m, "content", "")
            preview = content[:90].replace("\n", " ")
            print(f"  [{t}] {preview}")

    print("\n最终回答：")
    print(messages[-1].content)


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except AttributeError:
        pass
    step1_direct_retrieve()
    step2_react_qa()
