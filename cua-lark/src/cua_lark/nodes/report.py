from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path

from cua_lark.state import CaseState


def _safe_dir_segment(name: str, *, max_len: int = 80) -> str:
    """目录名片段：去掉 Windows / 跨平台非法字符。"""
    cleaned = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", name).strip(" .")
    if not cleaned:
        return "case"
    return cleaned[:max_len]


async def report_step(state: CaseState) -> dict:
    case_path = Path(state.get("case_path") or "case.yaml")
    stem = _safe_dir_segment(case_path.stem)
    # 写入报告的时刻 + 用例文件名（无扩展名）；%f 微秒降低同秒同用例碰撞概率
    report_dir_name = f"{datetime.now().strftime('%Y-%m-%d_%H-%M-%S_%f')}_{stem}"

    root = Path(__file__).resolve().parents[3] / "reports" / "runs" / report_dir_name
    root.mkdir(parents=True, exist_ok=True)

    status = state.get("status") or "unknown"
    lines = [
        f"# CUA-Lark 运行报告 ({report_dir_name})",
        "",
        f"- 生成时间: {datetime.now().isoformat(timespec='seconds')}",
        f"- 状态: **{status}**",
        f"- 用例文件: `{state.get('case_path', '')}`",
        "",
        "## 执行步骤",
        "",
    ]
    for h in state.get("history") or []:
        lines.append(f"- step {h.get('step_index')}: ok={h.get('bridge_ok')} status={h.get('bridge_status')}")
        lines.append(f"  - instruction: {h.get('instruction', '')[:200]}")
    lines.extend(["", "## 断言", ""])
    for a in state.get("asserts") or []:
        lines.append(
            f"- [{a.get('kind')}] pass={a.get('pass')} — {a.get('reason', '')[:300]}"
        )
    if state.get("error"):
        lines.extend(["", "## 错误", "", f"```json\n{state['error']}\n```"])

    out = root / "report.md"
    out.write_text("\n".join(lines), encoding="utf-8")
    return {"report_path": str(out), "run_id": report_dir_name}
