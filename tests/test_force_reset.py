from fastapi.testclient import TestClient

import app.main as main_module
from app.domain.game import HoldemGame
from app.main import app
from app.services.stats_store import JsonStatsStore


client = TestClient(app)


class CancellableTimer:
    def __init__(self):
        self.cancelled = False

    def cancel(self):
        self.cancelled = True


def reset_all_games(monkeypatch):
    main_module.game = HoldemGame()
    main_module.room_games.clear()
    main_module.latest_card_tokens.clear()
    main_module.turn_timers.clear()
    main_module.turn_timer_generations.clear()
    monkeypatch.setattr(main_module, "save_room_games", lambda: None)


def command(
    room_id: str,
    person_id: str,
    display_name: str,
    text: str,
    person_email: str | None = None,
):
    payload = {
        "room_id": room_id,
        "person_id": person_id,
        "display_name": display_name,
        "text": text,
    }

    if person_email is not None:
        payload["person_email"] = person_email

    return client.post(
        "/debug/command",
        json=payload,
    )


def setup_started_room(room_id: str):
    command(room_id, f"{room_id}-user-1", "상현", "참가")
    command(room_id, f"{room_id}-user-2", "철수", "참가")
    command(room_id, f"{room_id}-user-1", "상현", "시작")
    return main_module.get_game_for_room(room_id)


def test_force_reset_requires_authorized_email_and_keeps_state(monkeypatch):
    reset_all_games(monkeypatch)
    game = setup_started_room("room-a")
    main_module.latest_card_tokens["room-a"] = "token-a"

    response = command(
        "room-a",
        "room-a-user-1",
        "상현",
        "@FSS 강제리셋",
        person_email="other@lotte.net",
    )
    body = response.json()

    assert body["ok"] is False
    assert "권한이 없습니다" in body["message"]
    assert main_module.get_game_for_room("room-a") is game
    assert main_module.latest_card_tokens["room-a"] == "token-a"
    assert game.phase == main_module.GamePhase.PRE_FLOP


def test_force_reset_resets_only_current_room_and_runtime_state(monkeypatch):
    reset_all_games(monkeypatch)
    game_a = setup_started_room("room-a")
    game_b = setup_started_room("room-b")
    game_a.turn_timeout_counts["room-a-user-1"] = 2
    game_a.timeout_excluded_player_ids.append("room-a-user-x")
    game_a.pending_timeout_exclusion_ids.append("room-a-user-1")
    main_module.latest_card_tokens["room-a"] = "token-a"
    main_module.latest_card_tokens["room-b"] = "token-b"
    timer = CancellableTimer()
    main_module.turn_timers["room-a"] = timer

    response = command(
        "room-a",
        "room-a-user-1",
        "상현",
        "FSS 강제리셋",
        person_email="SH_LEE@LOTTE.NET",
    )
    body = response.json()
    reset_game = main_module.get_game_for_room("room-a")

    assert body["ok"] is True
    assert "강제리셋" in body["message"]
    assert "현재 상태: WAITING" in body["status"]
    assert reset_game is not game_a
    assert reset_game.players == []
    assert reset_game.turn_timeout_counts == {}
    assert reset_game.timeout_excluded_player_ids == []
    assert reset_game.pending_timeout_exclusion_ids == []
    assert "room-a" not in main_module.latest_card_tokens
    assert main_module.latest_card_tokens["room-b"] == "token-b"
    assert timer.cancelled is True
    assert main_module.get_game_for_room("room-b") is game_b
    assert game_b.phase == main_module.GamePhase.PRE_FLOP


def test_force_reset_allows_additional_admin_email(monkeypatch):
    reset_all_games(monkeypatch)
    game = setup_started_room("room-a")

    response = command(
        "room-a",
        "room-a-user-1",
        "admin",
        "FSS 강제리셋",
        person_email="MS-KIM1@LOTTE.NET",
    )

    assert response.json()["ok"] is True
    assert main_module.get_game_for_room("room-a") is not game


def test_ranking_reset_requires_admin_email_and_preserves_game(monkeypatch, tmp_path):
    reset_all_games(monkeypatch)
    game = setup_started_room("room-a")
    store = JsonStatsStore(str(tmp_path / "stats.json"))
    store._save(
        {
            "players": {
                "user-1": {
                    "display_name": "상현",
                    "games": 1,
                    "wins": 1,
                    "eliminations": 0,
                    "last_played_at": None,
                }
            }
        }
    )
    monkeypatch.setattr(main_module, "stats_store", store)

    unauthorized = command(
        "room-a",
        "room-a-user-2",
        "철수",
        "@FSS 랭킹리셋",
        person_email="other@lotte.net",
    ).json()

    assert unauthorized["ok"] is False
    assert "권한이 없습니다" in unauthorized["message"]
    assert "상현" in store.ranking_text()
    assert main_module.get_game_for_room("room-a") is game

    authorized = command(
        "room-a",
        "room-a-user-1",
        "상현",
        "@FSS 랭킹리셋",
        person_email="SH_LEE@LOTTE.NET",
    ).json()

    assert authorized["ok"] is True
    assert "랭킹과 전적을 초기화했습니다" in authorized["message"]
    assert store.ranking_text() == "아직 저장된 전적이 없습니다."
    assert main_module.get_game_for_room("room-a") is game
