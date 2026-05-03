from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class Step(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    action: Literal["instruct"] = "instruct"
    value: str
    timeout_s: int = 120
    max_loop_count: int = Field(default=20, alias="maxLoopCount")


class Assertion(BaseModel):
    kind: Literal["vlm", "ocr"]
    query: str | None = None
    contains: list[str] | None = None


class Case(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    id: str
    product: str = "im"
    preconditions: list[dict[str, Any]] = Field(default_factory=list)
    steps: list[Step]
    asserts: list[Assertion] = Field(default_factory=list)
    teardown: list[Step] | None = None


class ExecutedStep(BaseModel):
    step_index: int
    instruction: str
    bridge_ok: bool
    bridge_status: str | None = None
    raw_done: dict[str, Any] = Field(default_factory=dict)


class AssertResult(BaseModel):
    assertion_index: int
    kind: str = "vlm"
    pass_: bool = Field(alias="pass")
    reason: str = ""
    mode: Literal["vlm", "ocr", "skipped"] = "vlm"

    model_config = ConfigDict(populate_by_name=True)


class ErrorInfo(BaseModel):
    phase: str
    message: str
    detail: dict[str, Any] | None = None
