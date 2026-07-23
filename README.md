# FSS

FSS는 Webex 기반 멀티 게임 플랫폼입니다.

현재는 텍사스 홀덤과 주사위 게임이 구현되어 있지만, FSS 자체는 특정 게임 전용 봇이 아닙니다.  
앞으로 여러 게임을 하나의 Webex Bot 안에서 선택하고 실행할 수 있는 구조를 목표로 합니다.

## 목표 구조

FSS의 최종 목표는 다음과 같습니다.

```text
FSS
├─ 공통 기능
│  ├─ Webex Bot 연동
│  ├─ Webex Webhook 처리
│  ├─ 방별 게임 상태 관리
│  ├─ 버튼 카드 생성
│  ├─ 사용자 전적/랭킹 저장
│  └─ 게임 라우팅
│
└─ 게임 모듈
   ├─ Holdem
   ├─ Blackjack
   ├─ Mafia
   ├─ Dice
   └─ 기타 게임

현재 구현된 게임은 Holdem입니다.

현재 지원 게임
1. 텍사스 홀덤
2. 주사위 게임
3. 바보 라이어게임

현재 구현된 홀덤 기능은 다음과 같습니다.

Webex 그룹방 참가
방별 독립 게임 진행
2명 이상 게임 시작
SB/BB/딜러 로테이션
프리플랍 / 플랍 / 턴 / 리버 / 쇼다운
체크 / 콜 / 폴드 / 레이즈 / 올인
메인팟 / 사이드팟 정산
족보 판별
홀카드 DM 전송
전적 / 랭킹 저장
게임 종료 후 같은 참가자로 새게임 시작
완전 리셋 후 새 참가자 모집
Webex 명령어

현재는 홀덤이 기본 게임으로 동작합니다.

@FSS 참가
@FSS 시작
@FSS 상태
@FSS 내카드
@FSS 체크
@FSS 콜
@FSS 폴드
@FSS 레이즈 600
@FSS 올인
@FSS 랭킹
@FSS 전적
@FSS 랭킹리셋 (관리자 전용)
@FSS 새게임
@FSS 리셋

게임 선택:

@FSS 게임선택 홀덤
@FSS 게임선택 주사위
@FSS 게임선택 바보라이어게임

바보 라이어게임:

@FSS 참가
@FSS 참가취소
@FSS 시작
@FSS 제시어
@FSS 설명 설명내용
@FSS 투표 참가자명
@FSS 정답 제시어
@FSS 종료
@FSS 전체랭킹

바보 라이어게임은 일반 라이어게임과 별개이며, 모든 참가자는 자신의 제시어만 DM으로 받고 역할은 알 수 없습니다.

주사위 게임은 2명 이상이 `참가`한 뒤 `시작`하면 봇이 각 참가자의 주사위를 굴려 최고 숫자를 공개합니다. 동점자는 공동 우승입니다.
@FSS 도움말
버튼 UX

Webex 카드 버튼을 통해 주요 액션을 실행할 수 있습니다.

게임 시작 전에는 다음 버튼을 제공합니다.

참가 / 시작 / 상태 / 랭킹 / 전적 / 도움말 / 리셋

게임 진행 중에는 다음 버튼을 제공합니다.

상태 / 내카드 / 체크 또는 콜 / 폴드 / 올인 / 레이즈

게임 종료 후에는 다음 버튼을 제공합니다.

상태 / 새게임 / 리셋 / 랭킹 / 전적
향후 멀티게임 방향

현재는 명령어가 홀덤 기준으로 동작하지만, 추후에는 방마다 게임을 선택하는 구조로 확장할 예정입니다.

예상 흐름은 다음과 같습니다.

@FSS 게임선택 홀덤
@FSS 참가
@FSS 시작

또는:

@FSS 게임선택 블랙잭
@FSS 참가
@FSS 시작

즉, 하나의 Webex 방에서는 하나의 게임이 진행되고, FSS가 현재 방의 게임 타입을 기억한 뒤 해당 게임 모듈로 명령을 라우팅하는 구조를 목표로 합니다.

현재 아키텍처 상태

현재 코드는 아직 홀덤 중심으로 구성되어 있습니다.

app/
├─ main.py
├─ commands/
├─ domain/
├─ services/
└─ tests/

향후 리팩토링 목표는 다음과 같습니다.

app/
├─ main.py
├─ core/
│  ├─ room_manager.py
│  ├─ game_router.py
│  └─ webex_context.py
│
├─ services/
│  ├─ webex/
│  └─ stats/
│
└─ games/
   ├─ holdem/
   │  ├─ domain/
   │  ├─ services/
   │  ├─ commands/
   │  └─ tests/
   │
   └─ blackjack/

다만 현재 홀덤 기능이 안정화된 상태이므로, 당장 대규모 폴더 이동은 하지 않습니다.
먼저 홀덤을 안정 버전으로 유지하고, 두 번째 게임을 추가할 때 공통 기능과 게임별 기능을 분리합니다.

실행 방법

가상환경 활성화:

.venv\Scripts\activate.bat

FastAPI 실행:

uvicorn app.main:app --host 0.0.0.0 --port 8000

### 리치마작 패효율 연습

Webex 봇과의 1:1 개인채팅에서 `패효율 시작` 또는 `마작 시작`을 입력하고,
14패 카드에서 버릴 패를 누릅니다. `패효율 상태`, `패효율 기록`, `패효율 종료`,
`패효율 도움말`을 지원합니다. 진행 상태와 개인 기록은 person ID 기준으로 암호화해
저장하며 기본 경로는 `data/mahjong_efficiency.json`입니다.

### 그룹방 패효율 대결

Webex 그룹방에서 `패효율 대결` 메뉴를 열고 대결을 생성한 뒤 참가자를 받습니다.
최소 2명부터 방장이 시작할 수 있으며, 10라운드 동안 같은 14패 문제에서 10초 안에
최선 타패를 고릅니다. 최초 정답은 +10점이고 비효율·샨텐 악화 타패는 감점됩니다.
대결 상태와 기록은 개인 연습 및 홀덤과 분리된 `data/mahjong_battles.json`에 저장됩니다.

ngrok 실행:

ngrok http 8000

테스트 실행:

python -m pytest -x -vv

특정 테스트 실행:

python -m pytest tests/test_stats_store.py -vv
python -m pytest tests/test_card_token.py -vv
환경 변수

.env 예시:

WEBEX_BOT_TOKEN=your-webex-bot-token
WEBEX_BOT_PERSON_ID=your-webex-bot-person-id
WEBEX_WEBHOOK_NAME=FSS Webhook
WEBEX_WEBHOOK_TARGET_URL=https://your-ngrok-url.ngrok-free.app/webex/webhook

주의:

WEBEX_ROOM_ID=

WEBEX_ROOM_ID를 고정하면 특정 방만 동작할 수 있습니다.
멀티룸으로 사용하려면 보통 WEBEX_ROOM_ID는 제거합니다.

### 운영 안전 설정

`/debug/*` API는 기본적으로 비활성화됩니다. 신뢰할 수 있는 개발 환경에서만 다음 값을 설정합니다.

```env
FSS_DEBUG_API_ENABLED=true
FSS_DEBUG_API_TOKEN=충분히-긴-임의의-토큰
FSS_ADMIN_EMAIL=sh_lee@lotte.net
FSS_FORCE_RESET_ADMIN_PERSON_IDS=your-webex-person-id
```

`FSS_FORCE_RESET_ADMIN_PERSON_IDS`에는 강제리셋과 패효율 대결 방장 강퇴를
허용할 Webex `personId`를 쉼표로 구분해 입력합니다. 표시 이름이나 이메일은
이 권한 판정에 사용되지 않습니다.

디버그 API 호출 시 `X-FSS-Debug-Token` 헤더를 함께 전송해야 합니다.
게임 상태와 전적은 `data/`에 저장되며 Docker Compose는 이 디렉터리를 호스트에 마운트합니다.
현재 방 잠금과 타이머는 프로세스 메모리를 사용하므로 Uvicorn은 단일 worker로 실행해야 합니다.

저장 파일

JSON 저장 파일은 AES-256-GCM으로 암호화되며, 홀카드·남은 덱·참가자와
전적을 평문으로 남기지 않습니다. 실행 전에 `.env`에 최소 32자의 고유한
`FSS_DATA_ENCRYPTION_KEY`를 반드시 설정해야 합니다. 키를 분실하거나 바꾸면
기존 파일은 복구할 수 없으므로 데이터 파일과 별도로 안전하게 백업하세요.

키 생성 예시(PowerShell):

```powershell
python -c "import secrets; print(secrets.token_urlsafe(48))"
```

data/games.json
data/stats.json

향후 장기 운영 시에는 SQLite 전환을 고려합니다.

games.json  → SQLite
stats.json  → SQLite
개발 원칙

FSS는 홀덤 전용 봇이 아닙니다.

새 기능을 추가할 때는 다음 기준을 따릅니다.

Webex 처리, 방 관리, 저장소, 전적 기능은 가능한 공통 기능으로 둔다.
홀덤 규칙, 홀덤 버튼, 홀덤 메시지는 홀덤 모듈에만 둔다.
두 번째 게임을 추가할 때 공통 기능과 게임별 기능을 분리한다.
기존 홀덤 안정성을 깨지 않도록 테스트를 먼저 유지한다.
