# tcodex

Codex CLI를 실행하면서 하단에 여러 계정의 사용률과 선택 상태를 보여주는 터미널 실행기입니다.
계정 전환은 외부 TeamCodex 프록시가 담당합니다. 하단에는 구독 기간 종료일과 D-day도 표시합니다.

![tcodex terminal preview](docs/terminal-preview.svg)

실제 터미널 캡처를 SVG로 옮긴 미리보기입니다. 작업 경로는 `~/project`로 치환했습니다.

[teamclaude-statusline](https://github.com/cineraria01/teamclaude-statusline)의 표시 방식을
[TeamCodex](https://github.com/sangrokjung/teamclaude)용으로 옮긴 읽기 전용 상태줄입니다.

```text
TeamCodex | 2 accounts | switch 98% | > selected, * busy
  FLEET      x2       avg   5h [    -     ] 7d [ 34% 5d5h ]
> 1.codex-1  pro      ready 5h [    -     ] 7d [ 69% 5d5h ] End [ 09/14 D-3  ]
  2.codex-2  pro      ready 5h [    -     ] 7d [ 0% 6d23h ] End [ 10/08 D-27 ]
Cache last: 98.9% | 148,864/150,566 in | new 1,702
```

예시는 사용률이며 잔여량이 아닙니다. 시간은 쿼터 초기화까지 남은 시간입니다.
컬러 터미널에서는 사용률에 따라 막대가 초록·노랑·빨강으로 채워집니다.
계정 행은 Claude 상태바처럼 짙은 회색과 밝은 회색 배경을 번갈아 사용합니다.

`Cache last`는 해당 tcodex 창의 가장 최근 요청에서 캐시로 읽은 입력 비율과
캐시/전체 입력 토큰, 비캐시 입력(`new`)을 표시합니다. 응답 사용량이 기록되면
2초마다 갱신하며, 요청 진행 중에는 직전 수치를 유지합니다. 구독 한도 절감률은 아닙니다.
해당 CLI 프로세스가 연 대화 로그만 읽으며 다른 창과 서브에이전트는 제외합니다.
로그를 특정할 수 없으면 `unavailable`, 사용량 기록 전에는 `waiting`을 표시합니다.
이 표시는 `lsof`와 `ps`가 필요하며, 단독 `teamcodex-statusline` 실행에는 나타나지 않습니다.

## 사용

macOS의 기존 실행기와 Linux의 로그인·상시 서비스를 검증했습니다. Python 3.9 이상과 공식 Codex CLI가 필요하며, Codex 실행 화면에는 실행 중인 TeamCodex가 필요합니다.
설치기는 TeamCodex가 없으면 포크 `cineraria01/teamclaude`(브랜치 `qjc/resilient-routing`)의 최신 커밋을 별도 경로에 함께 설치합니다. Node.js/npm과 Git이 필요하며, 하단 고정 실행에는 tmux도 필요합니다. 자세한 안내는 [설치 및 계정 등록](docs/SETUP.md)을 참고하세요.

```sh
brew install tmux                 # macOS, 최초 한 번
git clone https://github.com/cineraria01/tcodex.git
cd tcodex
python3 install.py               # 실행기 + 없는 경우 TeamCodex 설치
# Linux에서 프록시를 상시 실행하려면:
python3 install.py --service     # 사용자 systemd 서비스 + 로그인 종료 후 유지
tcodex login --name codex-1
tcodex login --name codex-2      # 추가할 계정마다 반복
teamcodex-statusline              # 현재 상태 한 번 표시
teamcodex-statusline --watch      # 별도 터미널에서 2초마다 갱신
tcodex                           # Codex와 계정 상태줄을 같은 화면에 표시
tcodex resume SESSION_ID          # 지정한 기존 대화 재개
```

`tcodex login`은 tmux나 실행 중인 프록시 없이 사용할 수 있습니다. 출력된 인증 링크를
브라우저에서 열고 로그인하세요. 다른 계정은 시크릿 창을 사용하면 편합니다.
원격 서버에서 마지막 `localhost` 페이지가 열리지 않으면 주소창의
`http://localhost:1455/auth/callback?...` 전체를 **로그인 중인 터미널에 붙여넣고 Enter**를 누릅니다.
입력은 화면에 표시되지 않으며, 현재 로그인과 일치하는 로컬 주소만 전달합니다.
주소를 다른 사람에게 전달하거나 채팅에 붙여넣을 필요가 없습니다. 로컬 브라우저가 직접
콜백에 연결하면 자동으로 완료되고, `Ctrl-C`는 로그인 프로세스까지 정리합니다.
`tcodex login --device-auth`도 사용할 수 있습니다.

Linux의 `--service`는 `teamcodex.service`를 활성화하고 `Restart=always`로 재시작합니다.
설치 시 `loginctl enable-linger`가 거절되면 출력된 관리자 명령을 실행해야 로그아웃 뒤에도
유지됩니다. 상태는 `systemctl --user status teamcodex`, 로그는
`journalctl --user -u teamcodex -f`로 확인합니다. 서비스는 수동 `teamcodex server`와
동시에 실행하지 마세요. macOS 자동 시작은 [launchd 안내](docs/SETUP.md#3-macos-로그인-시-자동-시작-선택)를 따릅니다.
자동 시작을 설정하지 않은 경우 별도 터미널에서 `teamcodex server`를 켜두세요.

`~/.local/bin`이 PATH에 있어야 합니다. `tcodex`는 현재 폴더에서 `teamcodex run`을
실행합니다. 실제 Codex 화면 아래에 tmux 패널을 배치하며, 기존 Codex·Claude 설정 파일을
수정하지 않습니다. 기본적으로 터미널을 닫거나 `Ctrl-b d`로 마지막 연결을 끊으면
해당 세션도 종료되며 진행 중인 작업은 중단됩니다. 저장된 대화는
`tcodex resume SESSION_ID`로 재개할 수 있습니다.

창을 닫아도 작업을 계속 실행하려면 시작할 때 `--keep-alive`를 첫 인수로 지정하세요.
이 경우에만 `Ctrl-b d`로 분리한 뒤 다시 연결할 수 있습니다.

```sh
tcodex --keep-alive               # 명시적으로 백그라운드 유지
tmux -L teamcodex-hud attach
```

Codex 인수는 그대로 전달됩니다. 예: `tcodex -m MODEL`,
`tcodex --dangerously-bypass-approvals-and-sandbox`. 마지막 옵션은 승인 확인과 샌드박스를
해제합니다. 실행기가 기본으로 추가하지 않으며, 생략 시 기존 Codex 설정을 따릅니다.

Codex를 종료하면 해당 tmux 세션도 종료됩니다. 기존 일반 tmux 세션은 별도 소켓으로
분리됩니다. 70열 이상, 계정 수 + 12행 이상인 터미널을 사용하세요.

### Fast 모드 표시

`/fast on`을 실행해도 입력창 아래에 상태가 보이지 않으면 Codex의
`tui.status_line` 목록에 `"fast-mode"`가 있는지 확인하세요. `/statusline`에서
해당 항목을 선택하거나, `~/.codex/config.toml`의 기존 `[tui]` 섹션을 수정합니다.
`CODEX_HOME`을 지정했다면 해당 디렉터리의 `config.toml`을 사용합니다.
기존 항목을 유지하면서 `"fast-mode"`만 추가하세요. 다음은 예시입니다.

```toml
[tui]
status_line = ["model-with-reasoning", "fast-mode", "git-branch", "context-remaining", "total-input-tokens", "total-output-tokens", "five-hour-limit", "weekly-limit"]
```

파일을 직접 수정했다면 `tcodex`를 다시 실행하세요. Codex CLI 0.153.4에서
`gpt-6-astra medium · Fast on` 표시를 확인했습니다. 이 항목은 현재 모드 설정을
표시하며, 모드를 켜거나 서버의 실제 우선 처리를 검증하지 않습니다.
설치기는 개인 Codex 설정을 변경하지 않으므로 이 설정은 별도로 적용합니다.

## 표시 의미

- `>`: 프록시가 선택한 계정. 해당 Codex 대화에 고정된 계정이라는 뜻은 아닙니다.
- `*` / `busy`: 현재 요청 처리 중. 여러 대화가 동시에 사용하면 여러 계정이 표시될 수 있습니다.
- `ready`, `off`, `wait`, `limit`, `error`: 사용 가능, 제외, 제한 대기, 쿼터/용량 제한, 인증 등 오류.
- `cool 8m`: 모델 용량 오류 뒤 냉각까지 남은 시간. 냉각 중인 계정에는 선택 표시 `>`를 붙이지 않습니다. `*`는 이미 진행 중인 요청이며 냉각 상태보다 우선하지 않습니다. `back`은 최근 정상 응답을 완료한 계정입니다.
- `End`: 프록시가 보고한 종료일을 우선하고, 없으면 같은 계정의 로컬 로그인 ID 토큰에 기록된 `chatgpt_subscription_active_until`을 표시합니다. OAuth 토큰 만료 시각은 쓰지 않습니다. 날짜는 현지 시간 기준이며 3일 이하 빨강·7일 이하 노랑·나머지 초록입니다. 시작일도 있으면 구독 기간 경과 비율만큼 막대를 채웁니다.
- 로그인 정보의 날짜는 마지막 인증 당시의 기록이며 실시간 결제 조회가 아닙니다. 날짜가 지났으면 `past`, 없으면 `-`입니다. `past`만으로 구독 종료나 계정 사용 불가를 판정하지 않습니다.
- `5h`, `7d`: 프록시가 보고하는 세션·주간 사용률과 리셋 시간. 미보고 값은 `-`입니다.
- `FLEET avg`: 활성화되고 오류가 없는 계정 중 측정된 값의 단순 평균. 요금제별 용량 가중 합계가 아닙니다.
- 주간 리셋 순으로 표시하되 원래 계정 번호는 유지합니다. 상태줄은 실제 라우팅 순서를 변경하지 않습니다.

Codex가 제공하지 않는 Fable 쿼터는 표시하지 않습니다. 사용량 값은 TeamCodex의
관측 주기에 따르며, 화면의 2초 갱신이 OpenAI 쿼터를 새로 조회한다는 뜻은 아닙니다.
응답 오류 시 오래된 값을 현재 상태처럼 표시하지 않습니다.

## 연결 범위

Codex CLI의 기본 `tui.status_line`은 내장 항목만 지원합니다. 이 프로젝트는 공식 CLI를
수정하지 않고 하단 패널로 표시합니다. Orca의 그래픽 채팅 화면에 직접 삽입하는 기능은
없으며, Orca 안의 터미널에서는 `tcodex`로 사용할 수 있습니다.

`~/.config/teamcodex.json`의 로컬 프록시 포트와 프록시 인증키를 읽고
`/teamclaude/status`를 조회합니다. 구독 날짜는 동일 설정 파일의 ID 토큰을 로컬에서
해석해 표시용 메타데이터만 사용합니다. OAuth 토큰은 전송하지 않으며 별도 캐시도 저장하지
않습니다. 환경 HTTP 프록시와 HTTP 리다이렉트를 사용하지 않습니다.

## 검증 / 제거

두 계정 사이에서 같은 CLI 프로세스의 대화가 유지되는 것을 수동 계정 제외로 확인했습니다.
실제 한도를 소진한 시험은 아니며, 429 자동 전환은 검증한 upstream의 모의 서버 테스트 범위입니다.
계정 전환 후 모든 도구 호출의 중복 실행 방지까지 보장하는 것은 아닙니다.
아래 검사는 계정 로그인이나 모델 호출 없이 렌더링, 로컬 HTTP 인증, 리다이렉트 거부,
설치 재실행 및 기존 명령 보존을 확인합니다.

```sh
python3 test_statusline.py
python3 test_login.py
python3 test_install.py
python3 test_lifecycle.py          # tmux 필요; 실제 연결 종료와 자식 프로세스 정리 검사
```

기존 TeamCodex가 있으면 그대로 사용합니다. `python3 install.py --hud-only`는 npm과 서비스 설정 없이 실행기만 설치합니다.

설치 위치는 `~/.local/share/teamcodex-statusline`이며 글로벌 명령 두 개는 이 위치로
연결된 심볼릭 링크입니다. 제거 시 이 폴더와 자신이 설치한
`~/.local/bin/tcodex`, `~/.local/bin/teamcodex-statusline` 링크만 제거하면 됩니다.
TeamCodex 서버와 계정 설정은 별개입니다. Linux 자동 시작을 제거하려면 먼저
`systemctl --user disable --now teamcodex`를 실행하고 자신이 설치한
`~/.config/systemd/user/teamcodex.service`를 제거한 뒤 `systemctl --user daemon-reload`를 실행합니다. 설치 테스트는 `TEAMCODEX_HUD_PREFIX`로
별도 경로를 지정할 수 있습니다.

MIT. 막대 표시 방식과 FLEET 설계는 cineraria01/teamclaude-statusline에서 가져왔습니다.
