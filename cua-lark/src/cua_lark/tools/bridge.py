from __future__ import annotations

import asyncio
import contextlib
import json
import os
import shutil
from pathlib import Path
from typing import Any

from cua_lark.config import Settings

# Node 的 done 行可能含整页截图 base64，远超 asyncio 默认 readline 限制（64 KiB）
_STDIO_LINE_LIMIT = 32 * 1024 * 1024


def _worker_script() -> Path:
    # .../src/cua_lark/tools/bridge.py -> parents[3] = cua-lark 项目根
    return Path(__file__).resolve().parents[3] / "bridge-node" / "worker.mjs"


class BridgeClient:
    """常驻 Node 子进程：stdin 一行 JSON -> stdout JSONL，直至 type=done。"""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self._proc: asyncio.subprocess.Process | None = None
        self._stderr_task: asyncio.Task[None] | None = None

    async def start(self) -> None:
        if self._proc and self._proc.returncode is None:
            return
        node = shutil.which("node")
        if not node:
            raise RuntimeError("未找到 node，请先安装 Node.js")

        root = self.settings.ui_tars_desktop_root.resolve()
        if not root.is_dir():
            raise RuntimeError(f"UI_TARS_DESKTOP_ROOT 不是有效目录: {root}")

        worker = _worker_script()
        if not worker.is_file():
            raise RuntimeError(f"未找到 bridge worker: {worker}")

        env = {**os.environ, **self.settings.bridge_env()}
        nm = root / "node_modules"
        if nm.is_dir():
            prev = env.get("NODE_PATH", "")
            sep = os.pathsep
            env["NODE_PATH"] = f"{nm}{sep}{prev}" if prev else str(nm)

        self._proc = await asyncio.create_subprocess_exec(
            node,
            str(worker),
            cwd=str(root),
            env=env,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            limit=_STDIO_LINE_LIMIT,
        )
        self._stderr_task = asyncio.create_task(self._drain_stderr())

    async def _drain_stderr(self) -> None:
        if not self._proc or not self._proc.stderr:
            return
        while True:
            line = await self._proc.stderr.readline()
            if not line:
                break
            # 保留 Node 侧 logger 输出便于排障
            try:
                msg = line.decode("utf-8", errors="replace").rstrip()
            except Exception:
                msg = repr(line)
            if msg:
                print(msg, flush=True)

    async def shutdown(self) -> None:
        proc = self._proc
        if self._stderr_task:
            self._stderr_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._stderr_task
            self._stderr_task = None
        if proc and proc.returncode is None and proc.stdin:
            try:
                proc.stdin.write(b'{"op":"shutdown"}\n')
                await proc.stdin.drain()
            except Exception:
                pass
            try:
                proc.stdin.close()
                await proc.stdin.wait_closed()
            except Exception:
                pass
            try:
                await asyncio.wait_for(proc.wait(), timeout=8)
            except asyncio.TimeoutError:
                proc.kill()
                with contextlib.suppress(ProcessLookupError):
                    await proc.wait()
        self._proc = None

    async def run_step(
        self,
        instruction: str,
        *,
        max_loop_count: int = 20,
        timeout_s: float = 120.0,
    ) -> dict[str, Any]:
        await self.start()
        assert self._proc is not None and self._proc.stdin and self._proc.stdout

        payload = {
            "op": "run",
            "instruction": instruction,
            "maxLoopCount": max_loop_count,
        }
        line = json.dumps(payload, ensure_ascii=False) + "\n"
        self._proc.stdin.write(line.encode("utf-8"))
        await self._proc.stdin.drain()

        steps: list[dict[str, Any]] = []
        deadline = asyncio.get_event_loop().time() + timeout_s

        while True:
            remaining = deadline - asyncio.get_event_loop().time()
            if remaining <= 0:
                raise TimeoutError(f"Bridge run_step 超时 ({timeout_s}s)")
            line_b = await asyncio.wait_for(self._proc.stdout.readline(), timeout=remaining)
            if not line_b:
                raise RuntimeError("Bridge stdout 已关闭，未收到 done")
            try:
                msg = json.loads(line_b.decode("utf-8"))
            except json.JSONDecodeError as e:
                raise RuntimeError(f"Bridge 非 JSON 行: {line_b[:200]!r}") from e

            if msg.get("type") == "step":
                steps.append(msg)
            elif msg.get("type") == "error":
                steps.append(msg)
            elif msg.get("type") == "done" and msg.get("op") == "run":
                return {"events": steps, **msg}
            elif msg.get("type") == "done":
                # 其他 op 的 done 不应穿插；若出现则忽略或并入
                continue
