from __future__ import annotations

from typing import Any, Literal, NotRequired, TypedDict


class CaseState(TypedDict, total=False):
    """M1 LangGraph 状态（最小字段集，后续 M2 再对齐 Annotated reducer）。"""

    case_path: str
    run_id: NotRequired[str]  # 由 report 节点写入目录名后回填，与 reports/runs 下文件夹一致
    case: dict[str, Any]
    plan: list[dict[str, Any]]
    cursor: int
    history: list[dict[str, Any]]
    asserts: list[dict[str, Any]]
    status: Literal["running", "passed", "failed", "error"]
    error: dict[str, Any] | None
    last_execute: dict[str, Any] | None
    report_path: NotRequired[str]
