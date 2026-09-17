"""LangGraph 编排层。

路由（router） + 三张独立子图（react / plan / debate）。
父图用 add_node 把三张子图包装起来，由分类器 add_conditional_edges 分流。
"""

from agent.graph.router import build_parent_graph

__all__ = ["build_parent_graph"]
