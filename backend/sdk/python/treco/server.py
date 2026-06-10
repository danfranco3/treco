"""
Start/stop/status for the Treco backend server.
PID stored in ~/.treco/server.pid.
Backend found relative to the installed package or via TRECO_BACKEND_DIR.
"""
import os
import signal
import subprocess
import sys
from pathlib import Path

PID_FILE = Path.home() / ".treco" / "server.pid"
DEFAULT_PORT = 8001


def _backend_dir() -> Path | None:
    env_dir = os.environ.get("TRECO_BACKEND_DIR")
    if env_dir and Path(env_dir).exists():
        return Path(env_dir)
    pkg = Path(__file__).parent
    candidates = [
        pkg.parent.parent.parent,
        Path.home() / ".treco" / "backend",
    ]
    for c in candidates:
        if (c / "app" / "main.py").exists():
            return c
    return None


def start(port: int = DEFAULT_PORT) -> None:
    if is_running():
        print(f"Treco server already running (PID {_read_pid()})")
        return
    backend = _backend_dir()
    if not backend:
        print(
            "Backend not found. Set TRECO_BACKEND_DIR or install treco[server].",
            file=sys.stderr,
        )
        sys.exit(1)
    PID_FILE.parent.mkdir(parents=True, exist_ok=True)
    proc = subprocess.Popen(
        [
            sys.executable, "-m", "uvicorn", "app.main:app",
            "--host", "0.0.0.0", "--port", str(port),
            "--log-level", "warning",
        ],
        cwd=backend,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True,
    )
    PID_FILE.write_text(str(proc.pid))
    print(f"Treco server started (PID {proc.pid}) on http://localhost:{port}")


def stop() -> None:
    pid = _read_pid()
    if not pid:
        print("Server not running.")
        return
    try:
        os.kill(pid, signal.SIGTERM)
        PID_FILE.unlink(missing_ok=True)
        print(f"Stopped PID {pid}")
    except ProcessLookupError:
        PID_FILE.unlink(missing_ok=True)
        print("Server was not running.")


def status() -> None:
    pid = _read_pid()
    if pid and _pid_alive(pid):
        print(f"Running (PID {pid})")
    else:
        print("Not running")


def is_running() -> bool:
    pid = _read_pid()
    return pid is not None and _pid_alive(pid)


def _read_pid() -> int | None:
    if PID_FILE.exists():
        try:
            return int(PID_FILE.read_text().strip())
        except ValueError:
            pass
    return None


def _pid_alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
        return True
    except (ProcessLookupError, PermissionError):
        return False
