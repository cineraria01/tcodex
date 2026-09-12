#!/usr/bin/env python3
"""Launch Codex with a read-only TeamCodex footer in an isolated tmux session."""

import os
import shlex
import shutil
import subprocess
import sys
import uuid
from pathlib import Path

from statusline import read_status, render
from tcodex_login import login


def launch(arguments):
    keep_alive = bool(arguments and arguments[0] == "--keep-alive")
    if keep_alive:
        arguments = arguments[1:]
    if arguments and arguments[0] == "login":
        return login(arguments[1:])
    if arguments == ["--help"]:
        print("Usage: tcodex [Codex arguments]\n"
              "  tcodex                  Codex + live account footer\n"
              "  tcodex login [--name NAME]  Add an account with browser callback paste\n"
              "  tcodex resume ID        Continue an existing conversation\n"
              "  tcodex --keep-alive [Codex arguments]  Keep running after detach\n"
              "  Closing the terminal or Ctrl-b d stops the session by default.\n"
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
    rows = len(render(data)) + 1
    if size.lines < rows + 10 or size.columns < 70:
        sys.exit(f"Enlarge the terminal to at least 70 columns and {rows + 10} rows.")
    session = "codex-" + uuid.uuid4().hex[:8]
    base = [tmux, "-L", "teamcodex-hud", "-f", "/dev/null"]
    env = dict(os.environ)
    env.pop("TMUX", None)
    env.pop("TMUX_PANE", None)
    statusline = Path(__file__).resolve().with_name("statusline.py")
    cwd = os.getcwd()
    # Every tmux client runs from the home directory so a freshly spawned HUD
    # server never inherits a project directory. tmux 3.7 keeps the server's
    # start directory forever; once that directory is deleted, new panes ignore
    # `-c` and start in the dead directory, and Codex exits with ENOENT.
    home = str(Path.home())
    # A separate socket leaves the user's normal tmux server and config alone.
    def run(*args):
        return subprocess.run([*base, *args], check=True, env=env, cwd=home,
                              capture_output=True, text=True).stdout.strip()

    created = False
    try:
        top = run("new-session", "-d", "-P", "-F", "#{pane_id}", "-s", session,
                  "-n", "Codex", "-c", cwd, "-x", str(size.columns), "-y", str(size.lines),
                  "-e", "CODEX_HOME=" + env.get("CODEX_HOME", str(Path.home() / ".codex")),
                  "/bin/sleep", "60")
        created = True
        run("set-option", "-t", session, "status", "off")
        run("set-option", "-t", session, "mouse", "on")
        run("set-window-option", "-t", session, "pane-border-style", "fg=colour238")
        footer = run("split-window", "-d", "-P", "-F", "#{pane_id}", "-v", "-l", str(rows), "-t", top,
                     sys.executable, str(statusline), "--watch", "--codex-pane", top)
        for event in ("client-attached", "client-resized"):
            run("set-hook", "-t", session, event, f"resize-pane -t {footer} -y {rows}")
        if not keep_alive:
            # Setting this before the first attachment destroys the new session immediately.
            run("set-hook", "-a", "-t", session, "client-attached",
                f"set-option -t {session} destroy-unattached on")
        run("select-pane", "-t", top)
        # Exiting Codex also closes the footer, including in keep-alive mode.
        # The explicit cd keeps the caller's directory even on a HUD server whose
        # own start directory no longer exists (see the note above).
        command = ("cd " + shlex.quote(cwd) + " && "
                   + shlex.join([proxy, "run", "--", *arguments]) + "; "
                   + shlex.join([*base, "kill-session", "-t", session]))
        run("respawn-pane", "-k", "-t", top, "/bin/sh", "-c", command)
    except subprocess.CalledProcessError as error:
        if created:
            subprocess.run([*base, "kill-session", "-t", session], env=env, cwd=home, capture_output=True)
        sys.exit("Could not start the Codex footer: " + (error.stderr or str(error)).strip())
    try:
        return subprocess.call([*base, "attach-session", "-t", session], env=env, cwd=home)
    finally:
        # Failed attachment must not orphan a new session or stop another attached client.
        state = subprocess.run([*base, "display-message", "-p", "-t", session,
                                "#{session_attached} #{session_last_attached}"],
                               env=env, cwd=home, capture_output=True, text=True).stdout.split()
        if state and state[0] == "0" and (not keep_alive or len(state) == 1):
            subprocess.run([*base, "kill-session", "-t", session], env=env, cwd=home, capture_output=True)


if __name__ == "__main__":
    sys.exit(launch(sys.argv[1:]))
