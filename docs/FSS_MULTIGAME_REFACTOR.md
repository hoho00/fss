# FSS 멀티게임 리팩토링 계획

## 2026-07 구조 개선 반영

- `RoomManager`로 방별 게임, 게임 종류, 카드 토큰, Webhook 처리 ID와 잠금을 캡슐화했다.
- `TurnTimerManager`로 타이머와 generation 관리를 분리했다.
- `GamePlugin` 등록 정보로 게임 생성, 복구, 서비스, 버튼, 타이머 정책을 연결했다.
- Webex Webhook 라우터와 플랫폼 공통 메시징 계약을 추가했다.
- 게임별 통계 기록 처리기와 홀덤 직렬화기를 게임 모듈로 분리했다.
- 운영 환경의 디버그 API 보호와 Docker `data/` 영속화를 추가했다.
- `GameCommandCoordinator`로 일반 명령 실행, DM 사전 검사, 저장과 타이머 갱신을 이동했다.
- `WebexEventHandler`와 `WebexResponseSender`로 Webhook 해석과 출력 변환을 분리했다.
- `AdminCommandService`와 `TurnTimeoutHandler`로 관리자 명령과 시간 초과 처리를 분리했다.
- 게임 디버그 API를 `app/api/game_debug_router.py`로 이동했다.
- `ApplicationContainer`가 저장소, 관리자, 타이머, 파서와 Webex 빌더 생성을 담당한다.

`app/main.py`에는 FastAPI 조립과 기존 테스트·내부 호출을 위한 얇은 호환 함수가 남아 있다.
실제 게임 및 플랫폼 처리 규칙은 위 서비스와 라우터가 담당한다. 홀덤 전체 파일 이동은 별도의 작은 단계로 계속 진행한다.

FSS는 홀덤 전용 봇이 아니라 Webex 기반 멀티게임 플랫폼이다.

현재는 텍사스 홀덤이 첫 번째 게임으로 구현되어 있으며, 코드 구조도 아직 홀덤 중심으로 되어 있다.  
다만 현재 홀덤 기능이 안정화된 상태이므로, 당장 대규모 폴더 이동은 하지 않는다.

이 문서는 향후 FSS를 멀티게임 플랫폼으로 확장하기 위한 리팩토링 계획을 정리한다.

---

## 현재 구조

현재 구조는 대략 다음과 같다.

```text
app/
├─ main.py
├─ commands/
│  ├─ command.py
│  └─ parser.py
│
├─ domain/
│  ├─ card.py
│  ├─ deck.py
│  ├─ game.py
│  ├─ hand_evaluator.py
│  └─ player.py
│
├─ services/
│  ├─ game_store.py
│  ├─ holdem_bot_service.py
│  ├─ stats_store.py
│  ├─ webex_card_builder.py
│  └─ webex_client.py
│
└─ tests/

현재 문제점은 다음과 같다.

1. app/domain/game.py 가 사실상 HoldemGame 전용이다.
2. app/services/holdem_bot_service.py 가 Webex 공통 처리와 홀덤 처리를 같이 담당한다.
3. app/main.py 안에 홀덤 액션 버튼 생성 로직이 들어 있다.
4. GameStore가 홀덤 게임 상태 저장소 역할을 하고 있다.
5. 명령어 파서가 현재는 홀덤 기준으로 되어 있다.
목표 구조

향후 목표 구조는 다음과 같다.

app/
├─ main.py
│
├─ core/
│  ├─ room_manager.py
│  ├─ game_router.py
│  ├─ game_registry.py
│  └─ webex_context.py
│
├─ commands/
│  ├─ command.py
│  └─ parser.py
│
├─ services/
│  ├─ stats_store.py
│  └─ webex/
│     ├─ webex_client.py
│     └─ card_builder.py
│
└─ games/
   ├─ holdem/
   │  ├─ domain/
   │  │  ├─ card.py
   │  │  ├─ deck.py
   │  │  ├─ game.py
   │  │  ├─ hand_evaluator.py
   │  │  └─ player.py
   │  │
   │  ├─ services/
   │  │  ├─ holdem_bot_service.py
   │  │  ├─ holdem_game_store.py
   │  │  └─ holdem_action_builder.py
   │  │
   │  └─ commands/
   │     └─ holdem_command_mapper.py
   │
   └─ blackjack/
      ├─ domain/
      ├─ services/
      └─ commands/
리팩토링 원칙

리팩토링할 때는 다음 원칙을 따른다.

1. 테스트가 통과하는 상태에서만 다음 단계로 이동한다.
2. 한 번에 폴더 전체를 옮기지 않는다.
3. Webex 공통 처리와 게임별 처리를 분리한다.
4. 홀덤 안정성을 깨지 않는다.
5. 두 번째 게임을 추가할 때 공통 구조를 확정한다.
공통 영역과 게임별 영역 구분
FSS 공통 영역

다음은 FSS 공통 기능이다.

- Webex Webhook 수신
- Webex 메시지 전송
- Webex 카드 버튼 생성
- 방별 게임 상태 관리
- 방별 현재 게임 타입 저장
- 사용자 전적/랭킹 저장
- 명령어 기본 파싱
- 오래된 카드 버튼 처리
- 멀티룸 처리
홀덤 전용 영역

다음은 홀덤 전용 기능이다.

- 홀덤 게임 상태
- 홀덤 플레이어 상태
- 홀덤 카드 분배
- SB/BB/딜러 로테이션
- 프리플랍/플랍/턴/리버 진행
- 체크/콜/폴드/레이즈/올인
- 메인팟/사이드팟 정산
- 포커 족보 판별
- 홀덤용 액션 버튼 구성
- 홀덤용 상태 메시지
- 홀덤용 쇼다운 메시지
단계별 리팩토링 계획
Phase 1. 문서화

현재 단계.

목표:

- FSS가 멀티게임 플랫폼임을 README에 명시
- 홀덤 코드가 첫 번째 게임 모듈임을 주석으로 표시
- 리팩토링 계획 문서 작성

작업:

- README.md 작성
- app/domain/game.py 상단 주석 추가
- app/domain/card.py 상단 주석 추가
- app/domain/hand_evaluator.py 상단 주석 추가
- docs/FSS_MULTIGAME_REFACTOR.md 작성

완료 조건:

python -m pytest -x -vv
Phase 2. 이름 정리

목표:

현재 기능은 그대로 유지하면서 이름만 더 명확하게 한다.

예상 변경:

app/services/game_store.py
→ app/services/holdem_game_store.py

JsonGameStore
→ JsonHoldemGameStore

app/services/holdem_bot_service.py
→ 당장은 유지

주의:

- import 경로 변경으로 테스트가 깨질 수 있으므로 작은 단위로 진행한다.
- 기존 JsonGameStore 이름을 바로 삭제하지 말고 alias를 둘 수 있다.

예시:

class JsonHoldemGameStore:
    ...


JsonGameStore = JsonHoldemGameStore

완료 조건:

python -m pytest -x -vv
Phase 3. 홀덤 버튼 생성 로직 분리

현재 app/main.py 안에 있는 _build_available_card_actions()는 홀덤 전용이다.

목표:

app/main.py
→ Webex 요청/응답 흐름만 담당

app/games/holdem/services/holdem_action_builder.py
→ 홀덤 버튼 목록 생성 담당

예상 이동 대상:

_build_available_card_actions()

새 위치 예상:

app/games/holdem/services/holdem_action_builder.py

예상 함수:

def build_holdem_card_actions(game: HoldemGame) -> list[tuple[str, str]]:
    ...

완료 조건:

python -m pytest tests/test_webex_available_actions.py -vv
python -m pytest -x -vv
Phase 4. 홀덤 도메인 이동

목표:

app/domain에 있는 홀덤 전용 파일을 app/games/holdem/domain으로 이동한다.

이동 대상:

app/domain/game.py
→ app/games/holdem/domain/game.py

app/domain/hand_evaluator.py
→ app/games/holdem/domain/hand_evaluator.py

app/domain/player.py
→ app/games/holdem/domain/player.py

app/domain/deck.py
→ app/games/holdem/domain/deck.py

검토 대상:

app/domain/card.py

card.py는 블랙잭 등 다른 카드 게임에서도 재사용할 수 있으므로 둘 중 하나를 선택한다.

선택지 1:

app/common/card.py

선택지 2:

app/games/holdem/domain/card.py

일단은 홀덤 안으로 이동하고, 블랙잭 추가 시 공통화하는 것이 안전하다.

완료 조건:

python -m pytest -x -vv
Phase 5. Game Router 추가

목표:

방마다 어떤 게임을 실행 중인지 관리한다.

예상 명령어:

@FSS 게임선택 홀덤
@FSS 게임선택 블랙잭

예상 구조:

room_id → game_type
room_id → game_instance

예상 파일:

app/core/game_router.py
app/core/game_registry.py
app/core/room_manager.py

예상 게임 타입:

class GameType(str, Enum):
    HOLDEM = "HOLDEM"
    BLACKJACK = "BLACKJACK"

완료 조건:

- 방마다 게임 타입을 저장할 수 있다.
- 기본값은 HOLDEM이다.
- 기존 @FSS 참가 / 시작 / 상태 명령어는 그대로 동작한다.
Phase 6. 두 번째 게임 추가

두 번째 게임을 추가할 때 FSS 멀티게임 구조가 실제로 검증된다.

후보:

1. 블랙잭
2. 주사위 게임
3. 사다리
4. 마피아
5. 초성퀴즈

추천 순서:

1. 주사위 게임
2. 블랙잭
3. 마피아

이유:

주사위 게임은 상태/룰이 단순해서 Game Router 검증용으로 좋다.
블랙잭은 카드/턴/전적 구조를 재사용할 수 있다.
마피아는 DM/비공개 역할/투표가 필요해서 난이도가 높다.
당장 하지 않을 것

현재 안정 버전을 지키기 위해 다음 작업은 당장 하지 않는다.

1. app/domain 전체 이동
2. main.py 대규모 분리
3. JSON 저장소 전체 재설계
4. SQLite 전환
5. Game Router 강제 도입
6. 홀덤 명령어 전체 변경
다음 작업 후보

현재 문서화 이후 바로 할 수 있는 작업은 다음과 같다.

1. JsonGameStore 이름을 JsonHoldemGameStore로 정리
2. _build_available_card_actions()를 홀덤 전용 파일로 분리
3. README에 현재 지원 게임 목록 업데이트
4. tests 구조를 games/holdem 기준으로 나눌 준비

추천 다음 작업:

_build_available_card_actions()를 main.py에서 분리한다.

이 작업은 비교적 작고, FSS 공통 코드와 홀덤 전용 코드를 나누는 첫 실질적인 리팩토링이다.
