#!/usr/bin/env python3
"""Install the launcher and missing TeamCodex proxy without changing Codex settings."""

import os
import shutil
import subprocess
import sys
from pathlib import Path

from install_teamcodex import install_proxy, install_service


def install():
    arguments = sys.argv[1:]
    if arguments == ["--help"]:
        print("Usage: python3 install.py [--service | --hud-only]\n"
              "Default: install the launcher and TeamCodex if missing.\n"
              "--service: also enable the persistent Linux user service.\n"
              "--hud-only: install only the launcher; no npm or service changes.")
        return
    if any(arg not in ("--service", "--hud-only") for arg in arguments) or len(set(arguments)) > 1:
        raise SystemExit("Usage: python3 install.py [--service | --hud-only]")
    prefix = Path(os.environ.get("TEAMCODEX_HUD_PREFIX", Path.home() / ".local")).expanduser().resolve()
    target = prefix / "share/teamcodex-statusline"
    bin_dir = prefix / "bin"
    scripts = {"teamcodex-statusline": "statusline.py", "tcodex": "tcodex.py"}
    for command, script in scripts.items():
        link = bin_dir / command
        if (link.exists() or link.is_symlink()) and not (link.is_symlink() and link.resolve() == target / script):
            raise SystemExit(f"Existing command left untouched: {link}")
    proxy = None if "--hud-only" in arguments else install_proxy(prefix)
    target.mkdir(parents=True, exist_ok=True)
    bin_dir.mkdir(parents=True, exist_ok=True)
    source = Path(__file__).resolve().parent
    for filename in ("statusline.py", "tcodex.py", "tcodex_login.py", "LICENSE", "README.md"):
        shutil.copy2(source / filename, target / filename)
    for command, script in scripts.items():
        (target / script).chmod(0o755)
        link = bin_dir / command
        if not link.is_symlink():
            link.symlink_to(target / script)
    print(f"Installed: {bin_dir / 'tcodex'}")
    print(f"Preview:   {bin_dir / 'teamcodex-statusline'}")
    if "--service" in arguments and proxy is not None:
        install_service(proxy)
    print("Add an account: tcodex login --name codex-1")
    for dependency in ("codex", "tmux"):
        if not shutil.which(dependency):
            print(f"Install {dependency} before launching tcodex.")


if __name__ == "__main__":
    try:
        install()
    except (OSError, subprocess.CalledProcessError) as error:
        sys.exit(f"Installation failed: {error}")
