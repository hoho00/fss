from fastapi.testclient import TestClient

import app.main as main_module
from app.domain.game import HoldemGame
from app.main import app


client = TestClient(app)


class FakeTimer:
    instances = []

    def __init__(self, seconds, callback, args=()):
        self.seconds = seconds
        self.callback = callback
        self.args = args
        self.started = False
        self.cancelled = False
        self.daemon = False
        FakeTimer.instances.append(self)

    def start(self):
        self.started = True

    def cancel(self):
        self.cancelled = True

    def fire(self):
        self.callback(*self.args)


class FakeWebexClient:
    sent_cards = []

    def send_room_card(self, room_id, markdown, card):
        self.sent_cards.append(
            {
                "room_id": room_id,
                "markdown": markdown,
                "card": card,
            }
        )

    def send_direct_message(self, person_id, markdown):
        pass


class FailingWebexClient(FakeWebexClient):
    def send_room_card(self, room_id, markdown, card):
        raise RuntimeError("room not found")


def reset_timeout_state(monkeypatch):
    main_module.game = HoldemGame()
    main_module.room_games.clear()
    main_module.latest_card_tokens.clear()
    main_module.turn_timers.clear()
    main_module.turn_timer_generations.clear()
    FakeTimer.instances.clear()
    FakeWebexClient.sent_cards.clear()
    monkeypatch.setattr(main_module, "turn_timer_factory", FakeTimer)
    monkeypatch.setattr(main_module, "TURN_TIMEOUT_SECONDS", 0.01)
    monkeypatch.setattr(main_module, "WebexClient", FakeWebexClient)
    monkeypatch.setattr(main_module, "save_room_games", lambda: None)


def command(room_id: str, person_id: str, display_name: str, text: str):
    return client.post(
        "/debug/command",
        json={
            "room_id": room_id,
            "person_id": person_id,
            "display_name": display_name,
            "text": text,
        },
    )


def start_room(room_id: str = "room-a"):
    command(room_id, "user-1", "상현", "참가")
    command(room_id, "user-2", "철수", "참가")
    command(room_id, "user-3", "영희", "참가")
    command(room_id, "user-1", "상현", "시작")
    return main_module.get_game_for_room(room_id)


def test_turn_timer_auto_folds_current_player_and_notifies_webex(monkeypatch):
    reset_timeout_state(monkeypatch)
    game = start_room()
    current_player = game.players[game.current_turn_index]

    main_module._refresh_turn_timer("room-a")

    assert FakeTimer.instances[-1].seconds == 0.01
    FakeTimer.instances[-1].fire()

    assert current_player.folded is True
    assert game.turn_timeout_counts[current_player.person_id] == 1
    assert FakeWebexClient.sent_cards
    assert (
        f"{current_player.display_name}님이 시간 초과로 자동 폴드되었습니다. (1/3) - 3번 초과 시 게임 강퇴"
        in FakeWebexClient.sent_cards[-1]["markdown"]
    )


def test_stale_turn_timer_does_not_fold_next_player(monkeypatch):
    reset_timeout_state(monkeypatch)
    game = start_room()
    first_player = game.players[game.current_turn_index]

    main_module._refresh_turn_timer("room-a")
    stale_timer = FakeTimer.instances[-1]
    main_module._refresh_turn_timer("room-a")

    stale_timer.fire()

    assert first_player.folded is False
    assert game.turn_timeout_counts == {}


def test_webex_delivery_failure_does_not_break_timeout_or_next_timer(monkeypatch):
    reset_timeout_state(monkeypatch)
    game = start_room()
    current_player = game.players[game.current_turn_index]
    monkeypatch.setattr(main_module, "WebexClient", FailingWebexClient)

    main_module._refresh_turn_timer("room-a")
    failed_timer = FakeTimer.instances[-1]
    failed_timer.fire()

    assert current_player.folded is True
    assert game.turn_timeout_counts[current_player.person_id] == 1
    assert FakeTimer.instances[-1] is not failed_timer
    assert FakeTimer.instances[-1].started is True


def test_third_timeout_excludes_player_after_hand_settlement(monkeypatch):
    reset_timeout_state(monkeypatch)
    game = start_room()
    timeout_player = game.players[game.current_turn_index]
    game.turn_timeout_counts[timeout_player.person_id] = 2

    main_module._refresh_turn_timer("room-a")
    FakeTimer.instances[-1].fire()

    assert timeout_player.person_id in game.pending_timeout_exclusion_ids

    while game.phase != main_module.GamePhase.FINISHED:
        current_player = game.players[game.current_turn_index]
        if current_player.person_id == timeout_player.person_id:
            raise AssertionError("excluded pending player should stay folded")
        game.fold(current_player.person_id)

    assert timeout_player.person_id in game.timeout_excluded_player_ids
    assert timeout_player.person_id not in [
        player.person_id
        for player in game.players
    ]

    game.phase = main_module.GamePhase.WAITING
    response = command("room-a", timeout_player.person_id, "상현", "참가")
    body = response.json()

    assert body["ok"] is False
    assert "다시 참가할 수 없습니다" in body["message"]


def test_timer_is_not_created_when_no_actionable_turn(monkeypatch):
    reset_timeout_state(monkeypatch)
    game = start_room()
    game.current_turn_index = None

    main_module._refresh_turn_timer("room-a")

    assert FakeTimer.instances == []


def test_turn_timers_are_independent_per_room(monkeypatch):
    reset_timeout_state(monkeypatch)
    game_a = start_room("room-a")
    game_b = start_room("room-b")
    player_a = game_a.players[game_a.current_turn_index]
    player_b = game_b.players[game_b.current_turn_index]

    main_module._refresh_all_turn_timers()

    assert set(main_module.turn_timers) == {"room-a", "room-b"}

    room_a_timer = main_module.turn_timers["room-a"]
    room_a_timer.fire()

    assert player_a.folded is True
    assert player_b.folded is False
    assert game_a.turn_timeout_counts[player_a.person_id] == 1
    assert game_b.turn_timeout_counts == {}
