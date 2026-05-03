from __future__ import annotations

import random
import string
from datetime import date
from pathlib import Path

import yaml

from cua_lark.schemas import Case
from cua_lark.state import CaseState


def _expand_templates(text: str) -> str:
    out = text.replace("{today}", date.today().isoformat())
    rand = "".join(random.choices(string.ascii_lowercase, k=8))
    out = out.replace("{random_name}", f"auto_{rand}")
    return out


async def load_case(state: CaseState) -> dict:
    path = Path(state["case_path"])
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    case = Case.model_validate(raw)

    plan_dicts = []
    for step in case.steps:
        expanded = step.model_copy(update={"value": _expand_templates(step.value)})
        plan_dicts.append(expanded.model_dump(by_alias=True))

    return {
        "case": case.model_dump(by_alias=True),
        "plan": plan_dicts,
        "cursor": 0,
        "history": [],
        "asserts": [],
        "status": "running",
        "error": None,
        "last_execute": None,
    }
