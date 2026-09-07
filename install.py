#!/usr/bin/env python3
"""Install just the HUD and launcher under ~/.local; no Codex config changes."""

import os
from pathlib import Path
import shutil


def install():
    prefix = Path(os.environ.get("TEAMCODEX_HUD_PREFIX", Path.home() / ".local")).expanduser().resolve()
    target = prefix / "share/teamcodex-statusline"
    bin_dir = prefix / "bin"
    scripts = {"teamcodex-statusline": "statusline.py", "tcodex": "tcodex.py"}
    for command, script in scripts.items():
        link = bin_dir / command
        if (link.exists() or link.is_symlink()) and not (link.is_symlink() and link.resolve() == target / script):
            raise SystemExit(f"Existing command left untouched: {link}")
    target.mkdir(parents=True, exist_ok=True)
    bin_dir.mkdir(parents=True, exist_ok=True)
    source = Path(__file__).resolve().parent
    for filename in ("statusline.py", "tcodex.py", "LICENSE", "README.md"):
        shutil.copy2(source / filename, target / filename)
    for command, script in scripts.items():
        (target / script).chmod(0o755)
        link = bin_dir / command
        if not link.is_symlink():
            link.symlink_to(target / script)
    print(f"Installed: {bin_dir / 'tcodex'}")
    print(f"Preview:   {bin_dir / 'teamcodex-statusline'}")


if __name__ == "__main__":
    install()
