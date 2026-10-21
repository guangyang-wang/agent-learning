"""阶段 4 端到端验证：论文评审 -> 多 Agent 辩论 -> 完整评审报告。

运行：
    python scripts/verify_debate.py

说明：
    不接 Checkpointer，每次都是一场全新辩论（debate_messages 从空池开始）。
    若论文已提前入库，立论 / 批判会引用 RAG 检索到的原文片段；
    否则基于脚本里直接提供的论文内容评审。
"""

import sys

from agent.graph.debate_graph import MAX_DEBATE_ROUNDS, build_debate_graph

# 一篇故意留下常见缺陷的样例论文：单数据集、无基线对比、无消融、结论过度外推。
PAPER = """题目：基于深度学习的课堂专注度检测方法研究

摘要：本文提出一种基于卷积神经网络的课堂专注度检测方法。我们在自建数据集
上进行了实验，取得了 95% 的准确率，证明了方法的有效性。

1 引言
课堂专注度直接影响学习效果。现有方法多依赖人工观察，效率低且主观性强。
本文利用摄像头采集的图像，通过 CNN 自动判断学生是否专注。

2 方法
使用 ResNet-18 提取图像特征，最后一层接二分类器，输出"专注 / 不专注"。
训练时使用交叉熵损失和 Adam 优化器，学习率 0.001，训练 50 个 epoch。

3 实验
数据集来自某高校 2 个班级的课堂录像，共 1200 张图像，按 8:2 划分训练集和测试集。
测试集准确率达到 95%，说明本方法可以准确检测课堂专注度。

4 结论
本文方法准确率高、易于部署，可广泛应用于各类课堂的专注度检测。
"""

QUESTION = "请评审下面这篇课程论文，找出逻辑漏洞、论证缺陷，并给出修改建议：\n\n" + PAPER


def main() -> None:
    graph = build_debate_graph()
    result = graph.invoke(
        {
            "user_input": QUESTION,
            "messages": [],
            "iteration_count": 0,
            "debate_messages": [],
            "debate_round": 0,
        },
        config={"recursion_limit": 30},
    )

    pool = result.get("debate_messages", [])
    labels = {
        "propose": "立论 Agent",
        "critique": "批判 Agent",
        "arbitrator": "仲裁 Agent",
    }

    print("=" * 60)
    print(f"辩论发言（共 {len(pool)} 条，{result.get('debate_round', 0)} 轮"
          f"，上限 {MAX_DEBATE_ROUNDS} 轮）")
    print("=" * 60)
    for i, message in enumerate(pool, 1):
        role = labels.get(message.get("role"), message.get("role", "未知"))
        print(f"\n[{i}] {role}")
        print(message.get("content", ""))

    print("\n" + "=" * 60)
    print("最终评审报告")
    print("=" * 60)
    print(result.get("final_output", "（没有产出报告）"))


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except AttributeError:
        pass
    main()
