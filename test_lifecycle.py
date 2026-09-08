"""Offline lifecycle check with real tmux and PTYs; no login or inference."""

import fcntl
import json
import os
from pathlib import Path
import pty
import shutil
import signal
import struct
import subprocess
import sys
import tempfile
import termios
import time


def eventually(predicate):
    deadline = time.monotonic() + 8
    while time.monotonic() < deadline:
        if predicate():
            return
        time.sleep(0.05)
    raise AssertionError("lifecycle condition timed out")


def alive(pid):
    result = subprocess.run(["ps", "-p", str(pid), "-o", "stat="], capture_output=True, text=True)
    return result.returncode == 0 and not result.stdout.strip().startswith("Z")


def check():
    tmux = shutil.which("tmux")
    assert tmux, "Install tmux to run this check"
    root = Path(__file__).resolve().parent
    for mode in ("close", "detach", "keep-alive", "two-clients", "attach-failure", "keep-attach-failure"):
        with tempfile.TemporaryDirectory(prefix="tcodex-test-") as directory:
            path = Path(directory)
            socket = path.name
            base = [tmux, "-L", socket, "-f", "/dev/null"]
            wrapper = path / "tmux"
            wrapper.write_text(f"#!{sys.executable}\n" +
                               "import os, sys\na = sys.argv[1:]\n" +
                               f"a[a.index('-L') + 1] = {socket!r}\n" +
                               ("if 'attach-session' in a: sys.exit(1)\n" if mode.endswith("attach-failure") else "") +
                               f"os.execv({tmux!r}, [{tmux!r}] + a)\n")
            wrapper.chmod(0o755)
            proxy = path / "teamcodex"
            record = path / "processes.json"
            proxy.write_text(f"#!{sys.executable}\n" +
                             "import json, os, subprocess, sys, time\nfrom pathlib import Path\n" +
                             "child = subprocess.Popen(['sleep', '300'])\n" +
                             f"Path({str(record)!r}).write_text(json.dumps([os.getpid(), child.pid, sys.argv[1:]]))\n" +
                             "time.sleep(300)\n")
            proxy.chmod(0o755)
            arguments = (["--keep-alive"] if mode.startswith("keep") else []) + ["resume", "test-id"]
            runner = ("import tcodex, shutil\noriginal = shutil.which\n" +
                      f"tcodex.shutil.which = lambda name: {str(wrapper)!r} if name == 'tmux' else " +
                      f"{str(proxy)!r} if name == 'teamcodex' else original(name)\n" +
                      "tcodex.read_status = lambda path: {}\ntcodex.render = lambda data: ['footer']\n" +
                      f"raise SystemExit(tcodex.launch({arguments!r}))\n")
            masters, clients, pids = [], [], []

            def connect(command):
                master, slave = pty.openpty()
                fcntl.ioctl(slave, termios.TIOCSWINSZ, struct.pack("HHHH", 40, 120, 0, 0))
                client = subprocess.Popen(command, cwd=root, stdin=slave, stdout=slave, stderr=slave,
                                          env={**os.environ, "TERM": "xterm-256color"}, start_new_session=True)
                os.close(slave)
                masters.append(master)
                clients.append(client)
                return master

            def sessions():
                result = subprocess.run(base + ["list-sessions", "-F", "#{session_name} #{session_attached}"],
                                        capture_output=True, text=True)
                return result.stdout.strip()

            try:
                master = connect([sys.executable, "-c", runner])
                if mode.endswith("attach-failure"):
                    eventually(lambda: clients[0].poll() is not None)
                    eventually(lambda: not sessions())
                    assert clients[0].returncode != 0
                else:
                    eventually(lambda: sessions().endswith(" 1") and record.exists())
                    parent, child, forwarded = json.loads(record.read_text())
                    pids = [parent, child]
                    assert forwarded == ["run", "--", "resume", "test-id"], forwarded
                    session = sessions().split()[0]
                    panes = subprocess.check_output(base + ["list-panes", "-t", session, "-F", "#{pane_pid}"], text=True)
                    pids += [int(pid) for pid in panes.splitlines()]
                    if mode == "two-clients":
                        second = connect(base + ["attach-session", "-t", session])
                        eventually(lambda: sessions().endswith(" 2"))
                    if mode == "detach":
                        subprocess.run(base + ["detach-client", "-s", session], check=True)
                    else:
                        os.close(master)
                        masters.remove(master)
                    eventually(lambda: clients[0].poll() is not None)
                    if mode in ("keep-alive", "two-clients"):
                        expected = " 0" if mode == "keep-alive" else " 1"
                        eventually(lambda: sessions().endswith(expected))
                        assert all(alive(pid) for pid in pids)
                        if mode == "two-clients":
                            os.close(second)
                            masters.remove(second)
                        else:
                            # Normal Codex exit still closes its session in keep-alive mode.
                            os.kill(parent, signal.SIGTERM)
                    eventually(lambda: not sessions())
                    eventually(lambda: not any(alive(pid) for pid in pids))
                print(f"PASS: {mode}")
            finally:
                subprocess.run(base + ["kill-server"], capture_output=True)
                for master in masters:
                    os.close(master)
                for client in clients:
                    if client.poll() is None:
                        client.terminate()
                    client.wait(timeout=5)
                if record.exists():
                    for pid in json.loads(record.read_text())[:2]:
                        if alive(pid):
                            os.kill(pid, signal.SIGTERM)


if __name__ == "__main__":
    check()
