#!/usr/bin/env python3
"""Launch Codex with a read-only TeamCodex footer in an isolated tmux session."""

import os
from pathlib import Path
import shlex
import shutil
import subprocess
import sys
import uuid

from statusline import read_status, render


def launch(arguments):
    if arguments == ["--help"]:
        print("Usage: tcodex [Codex arguments]\n"
              "  tcodex                  Codex + live account footer\n"
              "  tcodex resume ID        Continue an existing conversation\n"
              "  Ctrl-b d                Detach without stopping Codex\n"
              "  tmux -L teamcodex-hud attach   Reattach\n"
              "Requires: tmux, Python 3, running TeamCodex proxy")
        return 0
    tmux, proxy = shutil.which("tmux"), shutil.which("teamcodex")
    if not tmux or not proxy:
        sys.exit("Requires tmux and teamcodex. macOS: brew install tmux")
    if not sys.stdin.isatty() or not sys.stdout.isatty():
        sys.exit("Open tcodex in a terminal. For scripts, use teamcodex run -- exec ...")
    try:
        data = read_status(Path.home() / ".config/teamcodex.json")
    except Exception:
        sys.exit("TeamCodex proxy unavailable. Start it with: teamcodex server")
    size = shutil.get_terminal_size()
    rows = len(render(data))
    if size.lines < rows + 10 or size.columns < 70:
        sys.exit(f"Enlarge the terminal to at least 70 columns and {rows + 10} rows.")
    session = "codex-" + uuid.uuid4().hex[:8]
    base = [tmux, "-L", "teamcodex-hud", "-f", "/dev/null"]
    env = dict(os.environ)
    env.pop("TMUX", None)
    env.pop("TMUX_PANE", None)
    statusline = Path(__file__).resolve().with_name("statusline.py")
    # A separate socket leaves the user's normal tmux server and config alone.
    def run(*args):
        return subprocess.run([*base, *args], check=True, env=env, capture_output=True, text=True).stdout.strip()

    created = False
    try:
        top = run("new-session", "-d", "-P", "-F", "#{pane_id}", "-s", session,
                  "-n", "Codex", "-c", os.getcwd(), "-x", str(size.columns), "-y", str(size.lines),
                  "-e", "CODEX_HOME=" + env.get("CODEX_HOME", str(Path.home() / ".codex")),
                  "/bin/sleep", "60")
        created = True
        run("set-option", "-t", session, "status", "off")
        run("set-option", "-t", session, "mouse", "on")
        run("set-window-option", "-t", session, "pane-border-style", "fg=colour238")
        footer = run("split-window", "-d", "-P", "-F", "#{pane_id}", "-v", "-l", str(rows), "-t", top,
                     sys.executable, str(statusline), "--watch")
        for event in ("client-attached", "client-resized"):
            run("set-hook", "-t", session, event, f"resize-pane -t {footer} -y {rows}")
        run("select-pane", "-t", top)
        # Only the selected Codex process exiting closes this dedicated session.
        command = (shlex.join([proxy, "run", "--", *arguments]) + "; "
                   + shlex.join([*base, "kill-session", "-t", session]))
        run("respawn-pane", "-k", "-t", top, "/bin/sh", "-c", command)
    except subprocess.CalledProcessError as error:
        if created:
            subprocess.run([*base, "kill-session", "-t", session], env=env, capture_output=True)
        sys.exit("Could not start the Codex footer: " + error.stderr.strip())
    return subprocess.call([*base, "attach-session", "-t", session], env=env)


if __name__ == "__main__":
    sys.exit(launch(sys.argv[1:]))
