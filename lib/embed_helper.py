#!/usr/bin/env python3
"""A helper process that keeps the embedding model loaded, so a command that needs a
vector gets it in about a second instead of loading the model (about 6 s) itself.

Nobody starts or stops it by hand. The first command that needs the model (through
`embedder.get_embedder()`) starts it in the background and waits until it is ready;
after IDLE_SECONDS without a request it exits and frees its memory (about 0.5 GB).
If it can't be reached or doesn't answer, the command loads the model itself, as
before: the helper can only make things faster.

It listens on a Unix socket (a file-like address only this user's processes on this
machine can use; no network port), in a folder kept in RAM (/run/user/<uid>, else
/tmp). One request per connection, one JSON line each way:

    {"op": "query" | "document", "text": "..."}  ->  {"ok": true, "vector": "<base64 float32>"}
    {"op": "ping"}                               ->  {"ok": true, "version": ..., "pid": ..., ...}
    {"op": "stop"}                               ->  {"ok": true}

It records the version of the model files and of its own code at start; a command
that finds a different version stops it and starts a fresh one.

    gm-recall.sh status     ... shows whether it is running
    gm-recall.sh stop       ends it now

Tests: GM_EMBED_SOCKET names another socket, GM_EMBED_IDLE another idle time, and a
helper started with GM_EMBEDDER=fake serves the fake embedder.
"""

import base64
import contextlib
import fcntl
import hashlib
import json
import os
import socket
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

IDLE_SECONDS = 30 * 60          # decided 2026-11-15
READY_SECONDS = 20              # how long a command waits for a new helper to load the model
ANSWER_SECONDS = 15             # how long a command waits for an answer


def _runtime_dir() -> Path:
    for candidate in (os.environ.get("XDG_RUNTIME_DIR"), f"/run/user/{os.getuid()}"):
        if candidate and Path(candidate).is_dir() and os.access(candidate, os.W_OK):
            return Path(candidate)
    return Path("/tmp")


def socket_path() -> Path:
    if os.environ.get("GM_EMBED_SOCKET"):
        return Path(os.environ["GM_EMBED_SOCKET"])
    from embedder import models_dir
    where = hashlib.sha256(str(models_dir()).encode()).hexdigest()[:8]   # one per model folder
    return _runtime_dir() / f"gm-embed-{os.getuid()}-{where}.sock"


def version() -> str:
    """What the helper was started with: the model files and this code."""
    from embedder import FILES, _local
    parts = [f"{p}:{_local(p).stat().st_size}:{int(_local(p).stat().st_mtime)}"
             for p in FILES if _local(p).exists()]
    for code in ("embedder.py", "embed_helper.py"):
        path = Path(__file__).parent / code
        parts.append(f"{code}:{int(path.stat().st_mtime)}")
    parts.append(os.environ.get("GM_EMBEDDER", ""))
    parts.append(os.environ.get("GM_EMBED_VERSION_EXTRA", ""))    # tests: a "changed" version
    return hashlib.sha256("|".join(parts).encode()).hexdigest()[:12]


# ---------- the client side ----------

def _ask(request: dict, timeout: float = ANSWER_SECONDS) -> dict:
    """One request; raises OSError (or ValueError) when the helper can't answer."""
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as s:
        s.settimeout(timeout)
        s.connect(str(socket_path()))
        s.sendall((json.dumps(request) + "\n").encode())
        data = b""
        while not data.endswith(b"\n"):
            chunk = s.recv(65536)
            if not chunk:
                break
            data += chunk
    answer = json.loads(data.decode() or "{}")
    if not answer.get("ok"):
        raise OSError(answer.get("error") or "the helper refused")
    return answer


def ping():
    """The helper's state, or None when none is running."""
    try:
        return _ask({"op": "ping"}, timeout=3)
    except (OSError, ValueError):
        return None


def stop() -> bool:
    try:
        _ask({"op": "stop"}, timeout=5)
        return True
    except (OSError, ValueError):
        return False


def _start() -> None:
    """Start a helper in the background (one at a time: a lock beside the socket)."""
    path = socket_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path.with_suffix(".lock"), "w") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        if ping():                                  # another command started one meanwhile
            return
        with contextlib.suppress(FileNotFoundError):
            path.unlink()                           # a stale socket from a helper that died
        with open(path.with_suffix(".log"), "a") as log:   # in RAM, like the socket
            subprocess.Popen([sys.executable, str(Path(__file__).resolve()), "serve"],
                             stdin=subprocess.DEVNULL, stdout=log, stderr=log,
                             start_new_session=True, close_fds=True)
        deadline = time.time() + READY_SECONDS
        while time.time() < deadline:
            if ping():
                return
            time.sleep(0.2)
    raise OSError("the helper didn't become ready in time")


def ready() -> bool:
    """A helper of the current version is running, started if need be."""
    state = ping()
    if state and state.get("version") != version():
        stop()                                      # outdated: model or code changed
        time.sleep(0.5)
        state = None
    if not state:
        _start()
    return True


class HelperEmbedder:
    """The embedder interface (query, document), answered by the helper; if it
    can't be reached, the model is loaded here instead, and the helper isn't tried
    again by this process."""

    def __init__(self, name: str):
        self.name = name
        self._local = None

    def _vector(self, op: str, text: str):
        import numpy as np
        if self._local is None:
            try:
                ready()
                answer = _ask({"op": op, "text": text})
                return np.frombuffer(base64.b64decode(answer["vector"]), dtype=np.float32)
            except (OSError, ValueError, KeyError):
                from embedder import Embedder, FakeEmbedder
                self._local = FakeEmbedder() if self.name == "fake" else Embedder()
        return getattr(self._local, op)(text)

    def query(self, text: str):
        return self._vector("query", text)

    def document(self, text: str):
        return self._vector("document", text)


# ---------- the helper itself ----------

def _read_line(conn) -> dict:
    data = b""
    while not data.endswith(b"\n"):
        chunk = conn.recv(65536)
        if not chunk:
            break
        data += chunk
    return json.loads(data.decode() or "{}")


def _answer(request: dict, model, state: dict) -> dict:
    """The answer to one request; `state` counts what was served and when."""
    op = request.get("op")
    if op in ("query", "document"):
        vector = getattr(model, op)(str(request.get("text", "")))
        state["served"] += 1
        state["last_used"] = time.time()
        return {"ok": True, "vector": base64.b64encode(vector.astype("float32").tobytes()).decode()}
    if op == "ping":
        return {"ok": True, "pid": os.getpid(), "model": model.name, **state}
    return {"ok": False, "error": f"unknown op {op!r}"}


def serve() -> int:
    from embedder import Embedder, FakeEmbedder
    model = FakeEmbedder() if os.environ.get("GM_EMBEDDER") == "fake" else Embedder()
    model.document("ready")                         # load the model before saying so
    path = socket_path()
    state = {"version": version(), "started": time.time(), "last_used": time.time(),
             "served": 0, "idle_seconds": float(os.environ.get("GM_EMBED_IDLE") or IDLE_SECONDS)}
    server = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    try:
        server.bind(str(path))
    except OSError:                                 # another helper got there first
        return 0
    os.chmod(path, 0o600)
    server.listen(8)
    try:
        while True:
            server.settimeout(max(0.1, state["idle_seconds"] - (time.time() - state["last_used"])))
            try:
                conn, _ = server.accept()
            except TimeoutError:
                return 0                            # idle long enough: exit, free the memory
            with conn:
                conn.settimeout(ANSWER_SECONDS)
                try:
                    request = _read_line(conn)
                    if request.get("op") == "stop":
                        conn.sendall(b'{"ok": true}\n')
                        return 0
                    answer = _answer(request, model, state)
                except (OSError, ValueError) as error:
                    answer = {"ok": False, "error": str(error)}
                with contextlib.suppress(OSError):
                    conn.sendall((json.dumps(answer) + "\n").encode())
    finally:
        server.close()
        with contextlib.suppress(FileNotFoundError):
            path.unlink()


def status_lines() -> list[str]:
    state = ping()
    if not state:
        return ["Helper: not running (the next command that needs the model starts it)"]
    now = time.time()
    left = state["idle_seconds"] - (now - state["last_used"])
    return [f"Helper: running (pid {state['pid']}, up {int((now - state['started']) / 60)} min, "
            f"{state['served']} texts embedded, exits in {max(0, int(left / 60))} min unless used)"
            + ("" if state["version"] == version() else "; outdated, replaced at the next use")]


def main() -> int:
    action = sys.argv[1] if len(sys.argv) > 1 else "status"
    if action == "serve":
        return serve()
    if action == "status":
        print("\n".join(status_lines()))
        return 0
    if action == "stop":
        print("[SUCCESS] The helper stopped." if stop() else "The helper wasn't running.")
        return 0
    print("[ERROR] Use: embed_helper.py status | stop | serve", file=sys.stderr)
    return 1


if __name__ == "__main__":
    sys.exit(main())
