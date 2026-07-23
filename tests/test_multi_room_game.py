from fastapi.testclient import TestClient

import app.main as main_module
from app.domain.game import HoldemGame
from app.main import app


client = TestClient(app)


def reset_all_games():
    main_module.game = HoldemGame()
    main_module.room_games.clear()


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


def test_each_room_has_independent_game_state():
    reset_all_games()

    command("room-a", "a-user-1", "A상현", "참가")
    command("room-a", "a-user-2", "A철수", "참가")
    response_a = command("room-a", "a-user-1", "A상현", "시작")
    body_a = response_a.json()

    assert body_a["ok"] is True
    assert "현재 상태: PRE_FLOP" in body_a["status"]
    assert "A상현" in body_a["status"]
    assert "A철수" in body_a["status"]

    command("room-b", "b-user-1", "B영희", "참가")
    response_b = command("room-b", "b-user-1", "B영희", "상태")
    body_b = response_b.json()

    assert body_b["ok"] is True
    assert "현재 상태: WAITING" in body_b["message"]
    assert "B영희" in body_b["message"]
    assert "A상현" not in body_b["message"]
    assert "A철수" not in body_b["message"]


def test_same_person_id_can_play_separately_in_different_rooms():
    reset_all_games()

    command("room-a", "same-user", "상현A", "참가")
    command("room-b", "same-user", "상현B", "참가")

    response_a = command("room-a", "same-user", "상현A", "상태")
    response_b = command("room-b", "same-user", "상현B", "상태")

    body_a = response_a.json()
    body_b = response_b.json()

    assert body_a["ok"] is True
    assert body_b["ok"] is True

    assert "상현A" in body_a["message"]
    assert "상현B" not in body_a["message"]

    assert "상현B" in body_b["message"]
    assert "상현A" not in body_b["message"]


def test_reset_only_resets_that_room():
    reset_all_games()

    command("room-a", "a-user-1", "A상현", "참가")
    command("room-a", "a-user-2", "A철수", "참가")

    command("room-b", "b-user-1", "B영희", "참가")
    command("room-b", "b-user-2", "B민수", "참가")
    command("room-b", "b-user-1", "B영희", "시작")

    response_reset_a = command("room-a", "a-user-1", "A상현", "리셋")
    body_reset_a = response_reset_a.json()

    assert body_reset_a["ok"] is True
    assert "게임을 리셋했습니다" in body_reset_a["message"]
    assert "현재 상태: WAITING" in body_reset_a["status"]
    assert "참가자 없음" in body_reset_a["status"]

    response_status_b = command("room-b", "b-user-1", "B영희", "상태")
    body_status_b = response_status_b.json()

    assert body_status_b["ok"] is True
    assert "현재 상태: PRE_FLOP" in body_status_b["status"]
    assert "B영희" in body_status_b["status"]
    assert "B민수" in body_status_b["status"]