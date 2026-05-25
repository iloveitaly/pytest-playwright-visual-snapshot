import atexit
import json
import os
import shutil
import subprocess
import threading
from concurrent.futures import Future
from pathlib import Path
from typing import Any

from .base import MatchResult


class ODiffBinaryNotFoundError(RuntimeError):
    pass


class _ODiffServer:
    """Manages a long-running `odiff --server` subprocess.

    Single writer (lock-protected stdin), single reader thread that
    demuxes responses into per-requestId Futures.
    """

    def __init__(self, binary_path: str, startup_timeout: float = 10.0) -> None:
        self._binary_path = binary_path
        self._startup_timeout = startup_timeout
        self._proc: subprocess.Popen | None = None
        self._write_lock = threading.Lock()
        self._pending: dict[int, Future] = {}
        self._next_id = 0
        self._ready = threading.Event()
        self._reader_thread: threading.Thread | None = None
        self._stopping = False

    def start(self) -> None:
        if self._proc is not None:
            return
        try:
            self._proc = subprocess.Popen(
                [self._binary_path, "--server"],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                bufsize=1,
            )
        except FileNotFoundError:
            raise ODiffBinaryNotFoundError(
                f"odiff binary not found at {self._binary_path!r}. "
                "Install via `brew install odiff` or `npm i -g odiff-bin`, "
                "or set ODIFF_BIN to its path."
            ) from None
        self._reader_thread = threading.Thread(target=self._read_loop, daemon=True)
        self._reader_thread.start()
        if not self._ready.wait(self._startup_timeout):
            self.stop()
            raise RuntimeError(
                f"odiff --server did not become ready within {self._startup_timeout}s"
            )

    def _read_loop(self) -> None:
        assert self._proc and self._proc.stdout
        for line in self._proc.stdout:
            line = line.strip()
            if not line:
                continue
            try:
                msg = json.loads(line)
            except json.JSONDecodeError:
                continue
            if msg.get("ready") and not self._ready.is_set():
                self._ready.set()
                continue
            req_id = msg.get("requestId")
            fut = self._pending.pop(req_id, None) if req_id is not None else None
            if fut is None:
                continue
            if "error" in msg:
                fut.set_exception(RuntimeError(msg["error"]))
            else:
                fut.set_result(msg)
        for fut in self._pending.values():
            if not fut.done():
                fut.set_exception(
                    RuntimeError("odiff server stdout closed unexpectedly")
                )
        self._pending.clear()

    def compare(
        self, base: Path, compare: Path, output: Path, options: dict[str, Any]
    ) -> dict[str, Any]:
        assert self._proc and self._proc.stdin
        with self._write_lock:
            req_id = self._next_id
            self._next_id += 1
            fut: Future = Future()
            self._pending[req_id] = fut
            payload = {
                "requestId": req_id,
                "base": str(base),
                "compare": str(compare),
                "output": str(output),
                "options": options,
            }
            self._proc.stdin.write(json.dumps(payload) + "\n")
            self._proc.stdin.flush()
        return fut.result()

    def stop(self) -> None:
        if self._stopping or self._proc is None:
            return
        self._stopping = True
        try:
            if self._proc.stdin:
                self._proc.stdin.close()
            try:
                self._proc.wait(timeout=2)
            except subprocess.TimeoutExpired:
                self._proc.terminate()
                try:
                    self._proc.wait(timeout=2)
                except subprocess.TimeoutExpired:
                    self._proc.kill()
        finally:
            self._proc = None


class ODiffMatcher:
    name = "odiff"

    def __init__(self, binary_path: str | None = None) -> None:
        self._binary_path = binary_path
        self._server: _ODiffServer | None = None
        self._server_lock = threading.Lock()

    def _resolve_binary(self) -> str:
        if self._binary_path:
            return self._binary_path
        env = os.environ.get("ODIFF_BIN")
        if env:
            return env
        found = shutil.which("odiff")
        if not found:
            raise ODiffBinaryNotFoundError(
                "odiff binary not found. Install via `brew install odiff` or "
                "`npm i -g odiff-bin`, or set ODIFF_BIN to its path."
            )
        return found

    def _ensure_server(self) -> _ODiffServer:
        if self._server is None:
            with self._server_lock:
                if self._server is None:
                    server = _ODiffServer(self._resolve_binary())
                    server.start()
                    atexit.register(server.stop)
                    self._server = server
        return self._server

    def compare(
        self,
        baseline_path: Path,
        actual_path: Path,
        diff_output_path: Path,
        *,
        threshold: float,
        fail_fast: bool = False,
    ) -> MatchResult:
        server = self._ensure_server()
        result = server.compare(
            base=baseline_path,
            compare=actual_path,
            output=diff_output_path,
            options={
                "threshold": threshold,
                "failOnLayoutDiff": True,
            },
        )

        if result.get("match") is True:
            return MatchResult(matched=True, score=0.0)

        reason = result.get("reason")
        if reason == "layout-diff":
            from PIL import Image

            return MatchResult(
                matched=False,
                size_mismatch=True,
                baseline_size=Image.open(baseline_path).size,
                actual_size=Image.open(actual_path).size,
            )
        if reason == "pixel-diff":
            return MatchResult(matched=False, score=float(result.get("diffCount", 0)))

        raise RuntimeError(f"odiff returned unexpected result: {result!r}")
