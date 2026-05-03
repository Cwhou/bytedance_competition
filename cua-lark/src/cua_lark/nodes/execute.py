from __future__ import annotations

from cua_lark.schemas import ExecutedStep
from cua_lark.state import CaseState
from cua_lark.tools.bridge import BridgeClient


def _scrub_done(d: dict) -> dict:
    out = dict(d)
    b64 = out.get("last_screenshot_base64")
    if isinstance(b64, str) and len(b64) > 200:
        out["last_screenshot_base64"] = f"<base64 {len(b64)} chars>"
    return out


async def execute_step(state: CaseState, bridge: BridgeClient) -> dict:
    plan = state.get("plan") or []
    cursor = int(state.get("cursor") or 0)
    if cursor >= len(plan):
        return {
            "status": "error",
            "error": {"phase": "execute", "message": "plan 为空或 cursor 越界"},
        }

    step = plan[cursor]
    instruction = step["value"]
    max_loop = int(step.get("maxLoopCount") or step.get("max_loop_count") or 20)
    timeout_s = float(step.get("timeout_s") or 120)

    try:
        done = await bridge.run_step(
            instruction,
            max_loop_count=max_loop,
            timeout_s=timeout_s,
        )
    except Exception as e:
        err = ExecutedStep(
            step_index=cursor,
            instruction=instruction,
            bridge_ok=False,
            bridge_status=None,
            raw_done={"error": str(e)},
        )
        return {
            "history": (state.get("history") or []) + [err.model_dump()],
            "last_execute": {"ok": False, "error": str(e)},
            "status": "failed",
            "error": {"phase": "execute", "message": str(e)},
        }

    ok = bool(done.get("ok"))
    bridge_status = done.get("status")
    executed = ExecutedStep(
        step_index=cursor,
        instruction=instruction,
        bridge_ok=ok,
        bridge_status=str(bridge_status) if bridge_status is not None else None,
        raw_done=_scrub_done(done),
    )

    patch: dict = {
        "history": (state.get("history") or []) + [executed.model_dump()],
        "last_execute": done,
    }
    if not ok:
        patch["status"] = "failed"
        patch["error"] = {
            "phase": "execute",
            "message": f"GUIAgent 未正常结束: status={bridge_status}",
            "detail": _scrub_done(done),
        }
    return patch
