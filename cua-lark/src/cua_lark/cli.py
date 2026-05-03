from __future__ import annotations

import asyncio
from pathlib import Path

import typer
from rich.console import Console

from cua_lark.config import Settings
from cua_lark.graph import build_m1_graph
from cua_lark.state import CaseState
from cua_lark.tools.bridge import BridgeClient

app = typer.Typer(no_args_is_help=True, add_completion=False)
console = Console()


async def _run_case(case_path: Path) -> None:
    settings = Settings()
    if not settings.vlm_api_key.strip():
        console.print("[red]请在 .env 中配置 VLM_API_KEY[/red]")
        raise typer.Exit(code=1)

    bridge = BridgeClient(settings)
    graph = build_m1_graph(bridge, settings)
    initial: CaseState = {
        "case_path": str(case_path.resolve()),
    }
    try:
        final = await graph.ainvoke(initial)
    finally:
        await bridge.shutdown()

    rp = final.get("report_path", "")
    console.print(f"[green]完成[/green] 状态={final.get('status')} 报告: {rp}")


@app.command("run")
def run_cmd(case: Path = typer.Argument(..., exists=True, dir_okay=False, readable=True)) -> None:
    """运行单条 YAML 用例（M1 最小图）。"""
    asyncio.run(_run_case(case))


def main() -> None:
    app()


if __name__ == "__main__":
    main()
