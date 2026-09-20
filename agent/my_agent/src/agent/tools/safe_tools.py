"""安全工具（自动执行，无需人机确认）。

定义要点：
    - 每个工具用 @tool 装饰器把「普通函数」包装成「BaseTool 对象」。
    - docstring（描述）是给 LLM 看的"接口说明书"，决定模型何时、怎么调用它，务必写清楚。

本文件包含 3 个安全工具：
    calculator        数学表达式计算 —— 阶段1 已实现
    get_current_time  查询当前日期时间 —— 阶段1 已实现
    rag_search        课件/资料检索   —— 阶段2 占位，逻辑待实现
"""

import ast
import math
import operator
from datetime import datetime

from langchain_core.tools import tool


# ==================== 工具 1：数学表达式计算 ====================

@tool
def calculator(expression: str) -> str:
    """计算数学表达式并返回结果，例如 "2+3*4"、"sqrt(16)"、"2**10"。

    Args:
        expression: 数学表达式字符串，支持 + - * / // % ** 及常见数学函数。
    """
    try:
        return str(_safe_eval(expression))
    except Exception as exc:  # noqa: BLE001 —— 把错误信息回传给模型，让它知道失败原因
        return f"计算失败：{exc}"


# ---- 安全求值：白名单 AST 解析 ----
# 不用裸 eval()，因为它能执行任意 Python 代码（如 __import__('os').system(...)）。
# 这里把表达式解析成 AST，只放行白名单里的节点类型，其余一律拒绝。

_BINARY_OPS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.FloorDiv: operator.floordiv,
    ast.Mod: operator.mod,
    ast.Pow: operator.pow,
}
_UNARY_OPS = {
    ast.UAdd: operator.pos,
    ast.USub: operator.neg,
}
_MATH_FUNCS = {
    "sqrt": math.sqrt, "sin": math.sin, "cos": math.cos, "tan": math.tan,
    "log": math.log, "log10": math.log10, "log2": math.log2,
    "exp": math.exp, "floor": math.floor, "ceil": math.ceil,
    "abs": abs, "round": round, "pi": math.pi, "e": math.e,
}


def _eval_node(node: ast.AST) -> float:
    """递归求值单个 AST 节点，只放行白名单里的类型。"""
    if isinstance(node, ast.Expression):  # 顶层包裹
        return _eval_node(node.body)
    if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
        return node.value  # 数字字面量
    if isinstance(node, ast.BinOp) and type(node.op) in _BINARY_OPS:
        return _BINARY_OPS[type(node.op)](
            _eval_node(node.left), _eval_node(node.right)
        )
    if isinstance(node, ast.UnaryOp) and type(node.op) in _UNARY_OPS:
        return _UNARY_OPS[type(node.op)](_eval_node(node.operand))
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
        if node.func.id in _MATH_FUNCS:  # 只放行白名单里的数学函数
            return _MATH_FUNCS[node.func.id](*(_eval_node(a) for a in node.args))
    raise ValueError(f"不支持的表达式：{ast.unparse(node)}")


def _safe_eval(expression: str) -> float:
    """安全求值：解析为 AST 后只放行白名单节点，杜绝任意代码执行。"""
    return _eval_node(ast.parse(expression, mode="eval"))


# ==================== 工具 2：查询当前日期时间 ====================

@tool
def get_current_time() -> str:
    """查询当前本地日期和时间，回答"今天几号""现在几点"这类问题时使用。"""
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


# ==================== 工具 3：RAG 课件检索（阶段2 占位） ====================

@tool
def rag_search(query: str) -> str:
    """在用户的私有课件/教材/试卷库中检索相关内容，回答课程问题时优先使用。

    Args:
        query: 检索关键词或问题。
    """
    # TODO(阶段2)：调用 rag/retriever.py 做真实向量检索，当前先占位
    raise NotImplementedError("RAG 检索待实现（阶段2）")