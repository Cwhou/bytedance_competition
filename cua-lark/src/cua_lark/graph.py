from __future__ import annotations

from langgraph.graph import END, START, StateGraph

from cua_lark.config import Settings
from cua_lark.nodes.execute import execute_step
from cua_lark.nodes.load_case import load_case
from cua_lark.nodes.report import report_step
from cua_lark.nodes.verify import verify_step
from cua_lark.state import CaseState
from cua_lark.tools.bridge import BridgeClient


def build_m1_graph(bridge: BridgeClient, settings: Settings):
    async def _execute(state: CaseState) -> dict:
        return await execute_step(state, bridge)

    async def _verify(state: CaseState) -> dict:
        return await verify_step(state, settings)

    g = StateGraph(CaseState)
    g.add_node("load_case", load_case)
    g.add_node("execute", _execute)
    g.add_node("verify", _verify)
    g.add_node("report", report_step)

    g.add_edge(START, "load_case")
    g.add_edge("load_case", "execute")
    g.add_edge("execute", "verify")
    g.add_edge("verify", "report")
    g.add_edge("report", END)
    return g.compile()
