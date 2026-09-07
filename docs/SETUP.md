# TeamCodex 프록시 준비

`tcodex`는 실행기와 상태줄입니다. OAuth 로그인과 계정 자동 전환은
[sangrokjung/teamclaude의 TeamCodex](https://github.com/sangrokjung/teamclaude)가 담당합니다.
이 안내는 macOS에서 확인한 upstream **1.3.0**, 커밋
`408297e8300a0ac8ad7d7e895e14612e7db7e303`을 고정해 사용합니다.
Node.js/npm, Python 3.9 이상, 공식 `codex` 명령이 먼저 설치되어 있어야 합니다.

이미 `teamcodex status`가 정상이고 설정이 `~/.config/teamcodex.json`에 있다면
이 단계는 건너뛰고 [실행기 설치](../README.md#사용)로 돌아가세요.

## 1. 별도 위치에 설치

upstream 패키지는 `teamclaude` 명령도 포함하므로 별도 npm prefix에 설치합니다.
아래 PATH를 셸 시작 파일에도 추가하세요.

```sh
export PATH="$HOME/.local/bin:$PATH"
mkdir -p "$HOME/.local/bin"
npm install --global --prefix "$HOME/.local/share/teamcodex-global" --ignore-scripts \
  git+https://github.com/sangrokjung/teamclaude.git#408297e8300a0ac8ad7d7e895e14612e7db7e303
```

`teamcodex` 명령만 노출합니다. 아래 블록은 기존 파일이 있으면 덮어쓰지 않고 실패합니다.
기존 명령이 있다면 해당 설치를 먼저 확인하세요.

```sh
(
  set -euC
  cat > "$HOME/.local/bin/teamcodex" <<'SH'
#!/bin/sh
if [ "${1-}" = codex ]; then shift; fi
exec env TEAMCLAUDE_PROVIDER=codex \
  TEAMCLAUDE_CONFIG="$HOME/.config/teamcodex.json" \
  TEAMCODEX_CODEX_BIN="$(command -v codex)" \
  node "$HOME/.local/share/teamcodex-global/lib/node_modules/teamcodex/src/index.js" codex "$@"
SH
  chmod 755 "$HOME/.local/bin/teamcodex"
)
```

## 2. 계정 등록과 서버 실행

```sh
teamcodex login --name codex-1
teamcodex login --name codex-2
teamcodex accounts
teamcodex server
```

각 로그인 화면에서 서로 다른 본인 계정을 선택합니다. 별도 로그인 디렉터리에서 인증하므로
기존 Codex의 인증 파일을 복사할 필요가 없습니다. 계정 설정 파일에는 토큰이 들어 있으므로
Git에 추가하지 마세요. 기본 프록시 포트는 `3457`, 전환 임계치는 사용률 `98%`입니다.

서버를 실행한 터미널을 유지하고 다른 터미널에서 `tcodex`를 실행하세요.
`teamcodex status`로 연결을 확인할 수 있습니다. 모든 계정의 한도가 소진되면
즉시 계속 응답할 수 있는 것은 아닙니다. 대화 재개는 `tcodex resume SESSION_ID`입니다.

## 3. macOS 로그인 시 자동 시작 (선택)

수동 서버를 `teamcodex stop`으로 종료한 뒤 아래를 실행합니다.
현재 PATH를 저장하므로 Node.js 설치 경로를 바꿨다면 plist를 갱신해야 합니다.
기존 동일 이름의 서비스 파일은 덮어쓰지 않습니다.

```sh
python3 - <<'PY'
import os
from pathlib import Path
import plistlib

home = Path.home()
logs = home / '.local/state/teamcodex'
logs.mkdir(parents=True, exist_ok=True, mode=0o700)
path = home / 'Library/LaunchAgents/io.github.cineraria01.tcodex.plist'
path.parent.mkdir(parents=True, exist_ok=True)
with path.open('xb') as stream:
    plistlib.dump({
        'Label': 'io.github.cineraria01.tcodex',
        'ProgramArguments': [str(home / '.local/bin/teamcodex'), 'server'],
        'RunAtLoad': True,
        'KeepAlive': True,
        'ThrottleInterval': 10,
        'EnvironmentVariables': {'HOME': str(home), 'PATH': os.environ['PATH']},
        'StandardOutPath': str(logs / 'server.log'),
        'StandardErrorPath': str(logs / 'server-error.log'),
    }, stream)
path.chmod(0o600)
PY
launchctl bootstrap "gui/$(id -u)" "$HOME/Library/LaunchAgents/io.github.cineraria01.tcodex.plist"
teamcodex status
```

자동 시작 서비스를 정지할 때는 아래 명령을 사용하세요. `KeepAlive` 때문에
`teamcodex stop`만 실행하면 다시 시작됩니다.

```sh
launchctl bootout "gui/$(id -u)/io.github.cineraria01.tcodex"
```

자동 시작 설정까지 제거하려면 bootout 후 위 plist 파일만 제거합니다.
프록시의 별도 npm prefix, 실행기 설치 폴더, 계정 설정 파일은 각각 독립적입니다.
계정 설정 파일을 지우면 저장한 로그인을 잃으므로 실행기 제거와 구분하세요.
