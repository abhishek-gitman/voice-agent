# ============================================================
# Start/stop local voice agent subprocess
# ============================================================

import os
import signal
import subprocess
import sys
import threading
import time
from collections import deque
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CONFIG_PATH = ROOT / "config" / "agent_runtime.json"
LOG_LIMIT = 400


@dataclass
class AgentSupervisor:
    _proc: subprocess.Popen | None = None
    _logs: deque[str] = field(default_factory=lambda: deque(maxlen=LOG_LIMIT))
    _lock: threading.Lock = field(default_factory=threading.Lock)

    def status(self) -> dict:
        running = self._proc is not None and self._proc.poll() is None
        return {
            "running": running,
            "pid": self._proc.pid if running and self._proc else None,
            "config_path": str(CONFIG_PATH),
        }

    def logs(self, tail: int = 120) -> list[str]:
        with self._lock:
            items = list(self._logs)
        return items[-tail:]

    def start(self) -> dict:
        if self._proc and self._proc.poll() is None:
            return {"ok": False, "error": "Agent is already running", **self.status()}

        if not CONFIG_PATH.is_file():
            return {"ok": False, "error": f"Missing config: {CONFIG_PATH}"}

        venv_python = ROOT / ".venv" / "bin" / "python"
        python = str(venv_python if venv_python.is_file() else sys.executable)
        cmd = [
            python,
            "-m",
            "runtime.bot",
            "--config",
            str(CONFIG_PATH),
        ]
        self._proc = subprocess.Popen(
            cmd,
            cwd=str(ROOT),
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
            env={**os.environ, "PYTHONUNBUFFERED": "1"},
        )
        threading.Thread(target=self._read_output, daemon=True).start()
        time.sleep(0.3)
        return {"ok": True, **self.status()}

    def stop(self) -> dict:
        if not self._proc or self._proc.poll() is not None:
            self._proc = None
            return {"ok": True, "running": False}

        self._proc.send_signal(signal.SIGINT)
        try:
            self._proc.wait(timeout=8)
        except subprocess.TimeoutExpired:
            self._proc.kill()
        self._proc = None
        return {"ok": True, "running": False}

    def _read_output(self) -> None:
        proc = self._proc
        if not proc or not proc.stdout:
            return
        for line in proc.stdout:
            with self._lock:
                self._logs.append(line.rstrip())
        with self._lock:
            code = proc.poll()
            self._logs.append(f"--- agent process exited (code={code}) ---")
