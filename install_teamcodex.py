import os
import shlex
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Final

UPSTREAM: Final = 'git+https://github.com/sangrokjung/teamclaude.git#408297e8300a0ac8ad7d7e895e14612e7db7e303'


def install_proxy(prefix: Path) -> Path:
    existing = shutil.which('teamcodex')
    if existing:
        print(f'Using existing TeamCodex: {existing}')
        return Path(existing).absolute()
    command = prefix / 'bin/teamcodex'
    if command.exists() or command.is_symlink():
        raise SystemExit(f'Existing command left untouched: {command}. Add its directory to PATH.')
    for dependency in ('npm', 'node', 'git'):
        if not shutil.which(dependency):
            raise SystemExit(f'Install {dependency} first, then rerun python3 install.py.')
    npm_prefix = prefix / 'share/teamcodex-global'
    subprocess.run(['npm', 'install', '--global', '--prefix', str(npm_prefix),
                    '--ignore-scripts', UPSTREAM], check=True)
    entry = npm_prefix / 'lib/node_modules/teamcodex/src/index.js'
    if not entry.is_file():
        raise SystemExit(f'TeamCodex entry point is missing: {entry}')
    command.parent.mkdir(parents=True, exist_ok=True)
    with command.open('x') as stream:
        stream.write('#!/bin/sh\n'
                     'if [ "${1-}" = codex ]; then shift; fi\n'
                     'exec env TEAMCLAUDE_PROVIDER=codex \\\n'
                     '  TEAMCLAUDE_CONFIG="$HOME/.config/teamcodex.json" \\\n'
                     '  TEAMCODEX_CODEX_BIN="$(command -v codex)" \\\n'
                     f'  node {shlex.quote(str(entry))} codex "$@"\n')
    command.chmod(0o755)
    return command


def install_service(command: Path) -> None:
    if sys.platform != 'linux' or not shutil.which('systemctl'):
        raise SystemExit('--service requires Linux user systemd. See docs/SETUP.md for macOS launchd.')
    def quote(value: str) -> str:
        return '"' + value.replace('\\', '\\\\').replace('"', '\\"').replace('%', '%%') + '"'

    path = Path.home() / '.config/systemd/user/teamcodex.service'
    content = ('# Installed by tcodex\n[Unit]\nDescription=TeamCodex account proxy\n'
               'After=network-online.target\n\n[Service]\nType=simple\n'
               f'ExecStart={quote(str(command))} server\n'
               f'Environment={quote("PATH=" + str(command.parent) + os.pathsep + os.environ.get("PATH", ""))}\n'
               'Restart=always\nRestartSec=5\nUMask=0077\n\n'
               '[Install]\nWantedBy=default.target\n')
    if path.exists() and not path.read_text().startswith('# Installed by tcodex\n'):
        raise SystemExit(f'Existing service left untouched: {path}')
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)
    path.chmod(0o600)
    subprocess.run(['systemctl', '--user', 'daemon-reload'], check=True)
    subprocess.run(['systemctl', '--user', 'enable', '--now', 'teamcodex.service'], check=True)
    linger = subprocess.run(['loginctl', 'enable-linger', str(os.getuid())], check=False)
    if linger.returncode:
        print('To keep the service running after logout, ask an administrator to run:\n'
              f'  sudo loginctl enable-linger {os.getuid()}', file=sys.stderr)
    print('Service enabled. Status: systemctl --user status teamcodex')
