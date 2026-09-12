# teamclaude · teamcodex(tcodex) · 상태라인 2종 — 새 머신 설치 프롬프트

새 머신의 Claude Code(또는 Codex)에 이 문서 전체를 붙여 넣거나, 한 줄로 이렇게 시킨다:

> https://raw.githubusercontent.com/cineraria01/tcodex/main/docs/INSTALL-ALL.md 를 읽고 그 절차를 순서대로 수행해. 업스트림 저장소에서는 절대 설치하지 마.

---

당신은 이 머신에 Claude·Codex 다계정 프록시와 상태라인 두 개를 설치한다. **모든 소스는
GitHub `cineraria01` 계정의 포크에서만 가져온다.** `sangrokjung/teamclaude`,
`jung-wan-kim/teamclaude`, npm의 `@karpeleslab/teamclaude`는 **절대 설치하지 말 것**
(같은 이름의 원본이지만 우리 수정이 없다). 다른 머신의 `~/.config/teamclaude.json`·
`teamcodex.json`(토큰 포함)을 복사해 오지 말고 이 머신에서 새로 로그인한다.

구성요소 셋과 출처:

| 구성요소 | 저장소 | 설치 위치 |
|---|---|---|
| 프록시 본체(Claude :3456 + Codex :3457, 한 설치본) | `cineraria01/teamclaude` 브랜치 `qjc/resilient-routing`의 최신 커밋(설치기가 브랜치 tip을 받는다) | `~/.local/share/teamcodex-global/lib/node_modules/teamcodex` |
| tcodex 실행기 + Codex 상태라인 + 프록시 설치기 | `cineraria01/tcodex` | `~/.local/bin/tcodex`, `~/.local/share/teamcodex-statusline` |
| Claude 상태라인 + 계정 선택기 | `cineraria01/teamclaude-statusline` | `~/.claude/statusline-*.py`, `~/.claude/teamclaude-selector.sh` |

## 0. 전제 조건 확인

macOS 기준(Homebrew). Linux면 §4의 launchd 대신 `python3 install.py --service`(systemd)와
README의 Linux 절을 따른다.

```sh
brew install tmux node git python3   # 없는 것만
node -v; npm -v; git --version; tmux -V; python3 --version   # node 20+, python 3.9+
command -v claude; command -v codex   # Claude Code·Codex CLI가 먼저 설치돼 있어야 한다
echo "$PATH" | tr ':' '\n' | grep -x "$HOME/.local/bin" || echo 'PATH에 ~/.local/bin 추가 필요'
```

`~/.local/bin`이 PATH에 없으면 셸 rc에 `export PATH="$HOME/.local/bin:$PATH"`를 추가하고
새 셸을 연다.

## 1. 프록시 본체 + tcodex 설치 (cineraria01/tcodex의 install.py)

```sh
mkdir -p ~/src && cd ~/src
git clone https://github.com/cineraria01/tcodex.git
cd tcodex
grep -n 'UPSTREAM' install_teamcodex.py   # cineraria01/teamclaude.git#qjc/resilient-routing 인지 확인
python3 install.py
```

이 한 번으로 생기는 것:
- `~/.local/share/teamcodex-global/…/teamcodex` — 포크 소스(npm 글로벌, 브랜치 tip)
- `~/.local/bin/teamcodex` — Codex 풀 래퍼(`TEAMCLAUDE_CONFIG=~/.config/teamcodex.json`)
- `~/.local/bin/tcodex` → `~/.local/share/teamcodex-statusline/tcodex.py`,
  `~/.local/bin/teamcodex-statusline`

이미 `teamcodex` 명령이 PATH에 있으면 installer가 그것을 그대로 쓰고 설치를 건너뛴다
(`Using existing TeamCodex`). 그 경우 그것이 원본인지 확인하고 지운 뒤 다시 돌린다.

### 1-1. 로컬 전용 패치 05 (Codex 실행 인자에서 chatgpt_base_url 오버라이드 제거)

포크에 넣지 않은 로컬 전용 수정이다(업스트림 테스트가 이 인자를 기대해서 포크에는 없다).
`src/codex.js`에서 아래 두 줄을 지운다:

```sh
PKG=~/.local/share/teamcodex-global/lib/node_modules/teamcodex
cd "$PKG" && patch -p1 <<'EOF'
--- a/src/codex.js
+++ b/src/codex.js
@@ -211,8 +211,6 @@
     'model_provider="teamcodex_proxy"',
     '-c',
     `model_providers.teamcodex_proxy={ ${provider} }`,
-    '-c',
-    `chatgpt_base_url="http://127.0.0.1:${port}"`,
   ];
   if (userArgs[0] === 'resume') {
     return [...userArgs, ...overrides];
EOF
node --check src/codex.js && echo ok
```

줄 번호가 어긋나 hunk가 실패하면 `grep -n chatgpt_base_url src/codex.js`로 찾아 그 `'-c'`
줄과 함께 두 줄만 손으로 지운다.

### 1-2. Claude 풀 래퍼 `~/.local/bin/teamclaude` 만들기

포크 `package.json`의 `bin.teamclaude`(`src/teamclaude.js`)를 별도 설정 파일로 띄우는 래퍼다.

```sh
cat > ~/.local/bin/teamclaude <<EOF
#!/bin/sh
# Claude pool (:3456). Same install as teamcodex (cineraria01/teamclaude fork).
exec env TEAMCLAUDE_CONFIG=\$HOME/.config/teamclaude.json $(command -v node) \$HOME/.local/share/teamcodex-global/lib/node_modules/teamcodex/src/teamclaude.js "\$@"
EOF
chmod 755 ~/.local/bin/teamclaude
teamclaude --help | head -3
```

## 2. 계정 로그인

각 계정을 **도구당 한 번만** 로그인한다(재로그인은 세션을 하나씩 누적시키므로 일시 오류에
재로그인하지 말 것). 서버가 떠 있지 않아도 로그인은 된다.

```sh
teamclaude login                 # Claude 계정마다 반복 (브라우저 OAuth)
teamclaude accounts
tcodex login --name codex-1      # Codex 계정마다 반복, 이름은 codex-1, codex-2 …
teamcodex accounts
```

원격 머신이라 브라우저가 못 열리면 출력된 인증 URL을 로컬 브라우저에서 열고, 마지막
`http://localhost:…/auth/callback?...` 전체 주소를 로그인 중인 터미널에 붙여 넣는다.

## 3. 프록시 설정값 (우리 운영값)

로그인이 설정 파일을 만든 뒤에 아래 키를 덧붙인다. 토큰이 든 파일이므로 git에 넣지 말 것.

```sh
python3 - <<'PY'
import json, os
def patch(path, updates):
    p = os.path.expanduser(path); d = json.load(open(p))
    d.update(updates); json.dump(d, open(p, 'w'), indent=2, ensure_ascii=False); os.chmod(p, 0o600)
    print(p, {k: d[k] for k in updates})
patch('~/.config/teamclaude.json', {
    'switchThreshold': 0.98,
    'rateLimitFailovers': 3,        # 429 때 계정 4개를 다 돌아본다(기본 1)
    'continuityMode': False,        # 제한 응답을 15분 내부 재시도하며 다른 세션까지 세우던 것 해제
    'quotaProbeSeconds': 300,
    'launchModel': 'claude-fable-5-1[1m]',   # 새 claude 세션 기본 모델(없으면 sonnet 주입)
})
patch('~/.config/teamcodex.json', {
    'switchThreshold': 0.98,
    'rateLimitFailovers': 1,
    'continuityMode': True,
    'modelFallbacks': {'gpt-5.6-sol': ['gpt-5.6-terra']},
})
PY
```

포트는 기본값(Claude 3456 · Codex 3457)을 그대로 쓴다. Claude 쪽 `proxy.apiKey`는 로그인이
만든 값을 유지한다(상태라인이 이 키로 status를 읽는다).

## 4. 상시 실행 — launchd + tmux (macOS)

프록시를 tmux 세션 안에서 띄워 TUI 대시보드를 볼 수 있게 한다.

```sh
TMUX_BIN=$(command -v tmux)
for pool in teamclaude teamcodex; do
cat > ~/.local/bin/$pool-tmux-server <<EOF
#!/bin/sh
# Run the $pool proxy inside a detached tmux session so its TUI can be viewed:
#   tmux -L $pool attach -t proxy   (Ctrl-b d detaches; 'q' in the TUI stops the proxy — launchd restarts it)
# Restart: tmux -L $pool kill-session -t proxy
TMUX=$TMUX_BIN; SOCK=$pool; SES=proxy
export TERM=xterm-256color LANG=en_US.UTF-8 LC_ALL=en_US.UTF-8
if ! "\$TMUX" -L "\$SOCK" has-session -t "\$SES" 2>/dev/null; then
  "\$TMUX" -L "\$SOCK" -f /dev/null new-session -d -s "\$SES" -x 170 -y 48 \\
    "exec \$HOME/.local/bin/$pool server" || exit 1
  "\$TMUX" -L "\$SOCK" set-option -t "\$SES" mouse on >/dev/null 2>&1
  "\$TMUX" -L "\$SOCK" set-option -t "\$SES" status off >/dev/null 2>&1
  "\$TMUX" -L "\$SOCK" set-option -t "\$SES" remain-on-exit off >/dev/null 2>&1
fi
while "\$TMUX" -L "\$SOCK" has-session -t "\$SES" 2>/dev/null; do sleep 3; done
exit 0
EOF
chmod 755 ~/.local/bin/$pool-tmux-server
done

mkdir -p ~/.local/state/teamcodex ~/Library/Logs
python3 - <<'PY'
import os, plistlib
from pathlib import Path
home = Path.home(); uid = os.getuid()
node_dir = str(Path(os.popen('command -v node').read().strip()).parent)
path_env = f"/opt/homebrew/bin:{home}/.local/bin:{node_dir}:/usr/local/bin:/usr/bin:/bin"
for label, wrapper, out in [
    ('com.local.teamclaude', 'teamclaude-tmux-server', home/'Library/Logs/teamclaude.log'),
    ('com.local.teamcodex',  'teamcodex-tmux-server',  home/'.local/state/teamcodex/server.log'),
]:
    p = home/'Library/LaunchAgents'/f'{label}.plist'
    p.parent.mkdir(parents=True, exist_ok=True)
    plistlib.dump({
        'Label': label,
        'ProgramArguments': [str(home/'.local/bin'/wrapper)],
        'RunAtLoad': True, 'KeepAlive': True, 'ThrottleInterval': 10,
        'ProcessType': 'Background',
        'EnvironmentVariables': {'HOME': str(home), 'PATH': path_env},
        'StandardOutPath': str(out), 'StandardErrorPath': str(out),
    }, p.open('wb'))
    p.chmod(0o600); print('wrote', p)
PY
launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/com.local.teamclaude.plist
launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/com.local.teamcodex.plist
sleep 3
curl -s -o /dev/null -w 'claude %{http_code}\n' http://127.0.0.1:3456/teamclaude/status
curl -s -o /dev/null -w 'codex  %{http_code}\n' http://127.0.0.1:3457/teamclaude/status
teamclaude status; teamcodex status
```

운영 요령:
- 재시작은 `tmux -L teamclaude kill-session -t proxy`(launchd가 다시 띄움). Codex 쪽 재시작은
  실행 중인 tcodex 세션을 죽이니 주의. `teamclaude restart`는 포그라운드라 쓰지 않는다.
- `enable|disable|priority|login|reauth`는 살아 있는 서버에 즉시 반영되므로 재시작 불필요.
- 대시보드: `tmux -L teamclaude attach -t proxy` / `tmux -L teamcodex attach -t proxy`,
  `Ctrl-b d`로 분리. TUI에서 `q`는 서버 종료(launchd가 재기동).

## 5. Claude 상태라인 + 계정 선택기 (cineraria01/teamclaude-statusline)

`teamclaude`가 PATH에 있고 계정이 하나 이상 있어야 installer가 진행된다(§1-2·§2 완료 후).

```sh
cd ~/src && git clone https://github.com/cineraria01/teamclaude-statusline
cd teamclaude-statusline && NO_PROBE=1 NO_RELOAD_PATCH=1 ./install.sh
```

- `NO_PROBE=1`·`NO_RELOAD_PATCH=1`: `probe` 명령과 reload 패치는 karpeleslab 원본용이다. 포크
  빌드에는 그 명령이 없고 enable/disable/priority가 이미 라이브 반영된다.
- 설치되는 것: `~/.claude/statusline-teamclaude.py`·`statusline-wrapper.py`·
  `statusline-autoupdate.sh`·`teamclaude-selector.sh`, `settings.json`의 `statusLine`,
  셸 rc의 `claude` 함수 블록(`teamclaude run --`으로 프록시 경유 실행).
- 자동 업데이트는 기본 꺼짐(`~/.claude/teamclaude-statusline-config.json`의 `autoUpdate: false`).

Claude Code 설정에 도구 검색을 켠다(비 Anthropic base URL에서는 기본 꺼져 있어 MCP 도구
정의가 매 요청 27만 토큰을 먹는다):

```sh
python3 - <<'PY'
import json, os
p = os.path.expanduser('~/.claude/settings.json'); d = json.load(open(p))
d.setdefault('env', {})['ENABLE_TOOL_SEARCH'] = 'true'
json.dump(d, open(p, 'w'), indent=2, ensure_ascii=False); print(d['env'])
PY
```

새 셸을 열고 `type claude`가 함수(`teamclaude run`)로 나오는지, `claude`를 띄웠을 때 하단에
계정별 Ses/Wk/Fbl 막대가 그려지는지 확인한다.

## 6. Codex 상태라인 (tcodex) 확인

§1에서 이미 설치됐다. 확인만 한다:

```sh
teamcodex-statusline           # 계정별 5h/7d 사용률, End(구독 종료 D-day)
cd ~/some-project && tcodex    # Codex 화면 아래 tmux 패널로 상태줄
```

`tcodex`는 `--dangerously-bypass-approvals-and-sandbox` 같은 Codex 인자를 그대로 넘긴다.
창을 닫아도 유지하려면 `tcodex --keep-alive`.

## 7. 최종 점검표

- [ ] `grep -c isOverloadEvent ~/.local/share/teamcodex-global/lib/node_modules/teamcodex/src/server.js` ≥ 1 — 포크에만 있는 수정이 들어 있다(원본이면 0). `npm ls -g --prefix ~/.local/share/teamcodex-global`은 `teamcodex@1.3.0`
- [ ] `grep -c chatgpt_base_url ~/.local/share/teamcodex-global/lib/node_modules/teamcodex/src/codex.js` → 0 (패치 05)
- [ ] `launchctl list | grep -E 'teamclaude|teamcodex'` 두 줄, 상태 0
- [ ] `teamclaude status`·`teamcodex status`에 계정이 보이고 `curl` status 200
- [ ] `claude -p "OK" --model claude-fable-5-1` 응답, 하단 상태라인 표시
- [ ] `tcodex` 실행 시 하단 상태줄 표시
- [ ] `~/.config/teamclaude.json`·`teamcodex.json`이 0600이고 어떤 git 저장소에도 없음

## 하지 말 것

- 업스트림(sangrokjung·jung-wan-kim·karpeleslab)에서 설치하거나 그쪽에 PR·이슈를 보내지 않는다.
- 토큰이 든 설정 파일을 다른 머신에서 복사하지 않는다(refresh 토큰은 회전+재사용 감지라 서로를 로그아웃시킨다).
- 같은 계정을 한 도구에서 두 번 로그인하지 않는다. 재인증은 `teamclaude reauth <이름>`·`tcodex login --name <기존이름>`으로만.
