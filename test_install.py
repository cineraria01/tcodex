import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path


def check() -> None:
    with tempfile.TemporaryDirectory() as directory:
        home = Path(directory)
        prefix = home / 'local with spaces'
        fakebin = home / 'bin'
        fakebin.mkdir()
        (fakebin / 'env').symlink_to('/usr/bin/env')
        npm = fakebin / 'npm'
        npm.write_text(f'#!{sys.executable}\n' + '''
from pathlib import Path
import sys
assert sys.argv[1:4] == ['install', '--global', '--prefix']
assert sys.argv[5] == '--ignore-scripts'
assert sys.argv[6].endswith('#408297e8300a0ac8ad7d7e895e14612e7db7e303')
entry = Path(sys.argv[4]) / 'lib/node_modules/teamcodex/src/index.js'
entry.parent.mkdir(parents=True)
entry.write_text('unused test entry')
''')
        npm.chmod(0o755)
        for name in ('node', 'git', 'systemctl', 'loginctl'):
            tool = fakebin / name
            tool.write_text(f'#!{sys.executable}\n' + '''
import json, os, sys
print(json.dumps({'argv': sys.argv[1:], 'provider': os.environ.get('TEAMCLAUDE_PROVIDER'), 'config': os.environ.get('TEAMCLAUDE_CONFIG')}))
''')
            tool.chmod(0o755)
        env = {**os.environ, 'HOME': str(home), 'PATH': str(fakebin),
               'TEAMCODEX_HUD_PREFIX': str(prefix)}
        installer = str(Path(__file__).with_name('install.py'))
        options = ['--service'] if sys.platform == 'linux' else []
        result = subprocess.run([sys.executable, installer, *options], env=env,
                                check=False, capture_output=True, text=True, timeout=10)
        assert result.returncode == 0, result.stderr
        command = prefix / 'bin/teamcodex'
        result = subprocess.run([str(command), '--help'], env=env, check=False, capture_output=True, text=True)
        data = json.loads(result.stdout)
        assert data['provider'] == 'codex'
        assert data['config'] == str(home / '.config/teamcodex.json')
        assert data['argv'][1:] == ['codex', '--help']
        assert (prefix / 'share/teamcodex-statusline/tcodex_login.py').is_file()
        if sys.platform != 'linux':
            print('PASS: pinned proxy install, separate wrapper, spaces')
            return
        unit = home / '.config/systemd/user/teamcodex.service'
        assert 'Restart=always' in unit.read_text()
        assert f'ExecStart="{command}" server' in unit.read_text()
        unit.write_text('user-owned service')
        env['PATH'] = str(command.parent) + os.pathsep + str(fakebin)
        result = subprocess.run([sys.executable, installer, '--service'], env=env,
                                check=False, capture_output=True, text=True, timeout=10)
        assert result.returncode != 0 and unit.read_text() == 'user-owned service'
    print('PASS: pinned proxy install, separate wrapper, spaces, persistent unit, existing service preservation')


if __name__ == '__main__':
    check()
