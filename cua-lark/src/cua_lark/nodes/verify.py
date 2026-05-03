from __future__ import annotations

import base64
import io
import json
import re
from typing import Any

from langchain_core.messages import HumanMessage
from langchain_openai import ChatOpenAI
from PIL import ImageGrab

from cua_lark.config import Settings
from cua_lark.schemas import AssertResult, Case
from cua_lark.state import CaseState


def _extract_json_object(text: str) -> dict[str, Any] | None:
    m = re.search(r"\{[\s\S]*\}", text)
    if not m:
        return None
    try:
        return json.loads(m.group())
    except json.JSONDecodeError:
        return None


def _screenshot_b64(state: CaseState) -> str:
    last = state.get("last_execute") or {}
    b64 = last.get("last_screenshot_base64")
    if isinstance(b64, str) and len(b64) > 100:
        return b64
    img = ImageGrab.grab()
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return base64.standard_b64encode(buf.getvalue()).decode("ascii")


async def verify_step(state: CaseState, settings: Settings) -> dict:
    case = Case.model_validate(state["case"])
    results: list[dict[str, Any]] = []

    err = state.get("error")
    if state.get("status") == "failed" and isinstance(err, dict) and err.get("phase") == "execute":
        results.append(
            AssertResult(
                assertion_index=-1,
                kind="skipped",
                pass_=False,
                reason="执行阶段已失败，跳过语义断言",
                mode="skipped",
            ).model_dump(by_alias=True)
        )
        return {"asserts": (state.get("asserts") or []) + results}

    if not case.asserts:
        results.append(
            AssertResult(
                assertion_index=0,
                kind="none",
                pass_=True,
                reason="未配置断言，视为通过",
                mode="skipped",
            ).model_dump(by_alias=True)
        )
        return {"asserts": (state.get("asserts") or []) + results}

    image_b64 = _screenshot_b64(state)
    llm = ChatOpenAI(
        model=settings.vlm_model,
        api_key=settings.vlm_api_key or "dummy",
        base_url=settings.vlm_base_url,
        temperature=0.0,
    )

    all_pass = True
    for i, assertion in enumerate(case.asserts):
        if assertion.kind == "ocr":
            # M1：无 OCR 引擎时仅做占位（M2 接 Paddle/RapidOCR）
            results.append(
                AssertResult(
                    assertion_index=i,
                    kind="ocr",
                    pass_=False,
                    reason="M1 未启用 OCR 回退，请使用 kind: vlm",
                    mode="skipped",
                ).model_dump(by_alias=True)
            )
            all_pass = False
            continue

        prompt = (
            "You are a test verifier. Reply with ONE JSON object only, no markdown.\n"
            'Schema: {"pass": <boolean>, "reason": <string in Chinese>}\n'
            f"Assertion to check: {assertion.query}\n"
        )
        msg = HumanMessage(
            content=[
                {"type": "text", "text": prompt},
                {
                    "type": "image_url",
                    "image_url": {"url": f"data:image/png;base64,{image_b64}"},
                },
            ]
        )
        try:
            resp = await llm.ainvoke([msg])
            text = (resp.content or "").strip() if hasattr(resp, "content") else str(resp)
            parsed = _extract_json_object(text) or {}
            passed = bool(parsed.get("pass"))
            reason = str(parsed.get("reason") or text[:500])
        except Exception as e:
            passed = False
            reason = f"VLM 断言调用失败: {e}"
            all_pass = False

        if not passed:
            all_pass = False

        results.append(
            AssertResult(
                assertion_index=i,
                kind="vlm",
                pass_=passed,
                reason=reason,
                mode="vlm",
            ).model_dump(by_alias=True)
        )

    patch: dict = {"asserts": (state.get("asserts") or []) + results}
    if not all_pass:
        patch["status"] = "failed"
        patch["error"] = {"phase": "verify", "message": "存在未通过的断言"}
    else:
        patch["status"] = "passed"
        patch["error"] = None
    return patch
