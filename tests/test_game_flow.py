from fastapi.testclient import TestClient

import app.main as main_module
from app.main import app
from app.domain.game import HoldemGame


client = TestClient(app)


def reset_game():
    main_module.game = HoldemGame()
    return main_module.game


def prepare_two_player_game():
    reset_game()

    client.post(
        "/debug/join",
        json={
            "person_id": "user-1",
            "display_name": "상현",
        },
    )

    client.post(
        "/debug/join",
        json={
            "person_id": "user-2",
            "display_name": "철수",
        },
    )

    client.post("/debug/start")


def open_flop():
    prepare_two_player_game()

    client.post(
        "/debug/call",
        json={
            "person_id": "user-1",
        },
    )

    client.post(
        "/debug/check",
        json={
            "person_id": "user-2",
        },
    )


def open_turn():
    open_flop()

    client.post(
        "/debug/check",
        json={
            "person_id": "user-2",
        },
    )

    client.post(
        "/debug/check",
        json={
            "person_id": "user-1",
        },
    )


def open_river():
    open_turn()

    client.post(
        "/debug/check",
        json={
            "person_id": "user-2",
        },
    )

    client.post(
        "/debug/check",
        json={
            "person_id": "user-1",
        },
    )


def test_join_two_players():
    reset_game()

    response = client.post(
        "/debug/join",
        json={
            "person_id": "user-1",
            "display_name": "상현",
        },
    )

    assert response.status_code == 200
    assert response.json()["ok"] is True
    assert "상현님이 참가했습니다" in response.json()["message"]

    response = client.post(
        "/debug/join",
        json={
            "person_id": "user-2",
            "display_name": "철수",
        },
    )

    assert response.status_code == 200
    assert response.json()["ok"] is True
    assert "철수님이 참가했습니다" in response.json()["message"]


def test_start_game_with_two_players():
    reset_game()

    client.post(
        "/debug/join",
        json={
            "person_id": "user-1",
            "display_name": "상현",
        },
    )

    client.post(
        "/debug/join",
        json={
            "person_id": "user-2",
            "display_name": "철수",
        },
    )

    response = client.post("/debug/start")

    assert response.status_code == 200

    body = response.json()

    assert body["ok"] is True
    assert "게임을 시작했습니다" in body["message"]
    assert "현재 상태: PRE_FLOP" in body["status"]
    assert "팟: 300" in body["status"]
    assert "현재 최고 베팅: 200" in body["status"]
    assert "현재 차례: 상현" in body["status"]
    assert "상현 (D/SB)" in body["status"]
    assert "철수 (BB)" in body["status"]


def test_private_cards_after_start():
    reset_game()

    client.post(
        "/debug/join",
        json={
            "person_id": "user-1",
            "display_name": "상현",
        },
    )

    client.post(
        "/debug/join",
        json={
            "person_id": "user-2",
            "display_name": "철수",
        },
    )

    client.post("/debug/start")

    response = client.get("/debug/private-cards/user-1")

    assert response.status_code == 200

    body = response.json()

    assert body["ok"] is True
    assert "상현님의 카드:" in body["message"]


def test_small_blind_call_waits_for_big_blind_action():
    prepare_two_player_game()

    response = client.post(
        "/debug/call",
        json={
            "person_id": "user-1",
        },
    )

    assert response.status_code == 200

    body = response.json()

    assert body["ok"] is True
    assert "상현님이 100칩 콜했습니다" in body["message"]
    assert "플랍 오픈" not in body["message"]
    assert "현재 상태: PRE_FLOP" in body["status"]
    assert "팟: 400" in body["status"]
    assert "현재 최고 베팅: 200" in body["status"]
    assert "현재 차례: 철수" in body["status"]


def test_big_blind_check_opens_flop():
    prepare_two_player_game()

    client.post(
        "/debug/call",
        json={
            "person_id": "user-1",
        },
    )

    response = client.post(
        "/debug/check",
        json={
            "person_id": "user-2",
        },
    )

    assert response.status_code == 200

    body = response.json()

    assert body["ok"] is True
    assert "철수님이 체크했습니다" in body["message"]
    assert "플랍 오픈" in body["message"]
    assert "현재 상태: FLOP" in body["status"]
    assert "팟: 400" in body["status"]
    assert "현재 최고 베팅: 0" in body["status"]
    assert "현재 차례: 철수" in body["status"]


def test_small_blind_fold_big_blind_wins():
    prepare_two_player_game()

    response = client.post(
        "/debug/fold",
        json={
            "person_id": "user-1",
        },
    )

    assert response.status_code == 200

    body = response.json()

    assert body["ok"] is True
    assert "상현님이 폴드했습니다" in body["message"]
    assert "철수님이 팟 300칩을 획득했습니다" in body["message"]
    assert "현재 상태: FINISHED" in body["status"]
    assert "팟: 0" in body["status"]


def test_flop_check_check_opens_turn():
    open_flop()

    response = client.post(
        "/debug/check",
        json={
            "person_id": "user-2",
        },
    )

    assert response.status_code == 200
    body = response.json()

    assert body["ok"] is True
    assert "철수님이 체크했습니다" in body["message"]
    assert "현재 상태: FLOP" in body["status"]
    assert "현재 차례: 상현" in body["status"]

    response = client.post(
        "/debug/check",
        json={
            "person_id": "user-1",
        },
    )

    assert response.status_code == 200
    body = response.json()

    assert body["ok"] is True
    assert "상현님이 체크했습니다" in body["message"]
    assert "턴 오픈" in body["message"]
    assert "현재 상태: TURN" in body["status"]
    assert "현재 차례: 철수" in body["status"]


def test_turn_check_check_opens_river():
    open_turn()

    response = client.post(
        "/debug/check",
        json={
            "person_id": "user-2",
        },
    )

    assert response.status_code == 200
    body = response.json()

    assert body["ok"] is True
    assert "철수님이 체크했습니다" in body["message"]
    assert "현재 상태: TURN" in body["status"]
    assert "현재 차례: 상현" in body["status"]

    response = client.post(
        "/debug/check",
        json={
            "person_id": "user-1",
        },
    )

    assert response.status_code == 200
    body = response.json()

    assert body["ok"] is True
    assert "상현님이 체크했습니다" in body["message"]
    assert "리버 오픈" in body["message"]
    assert "현재 상태: RIVER" in body["status"]
    assert "현재 차례: 철수" in body["status"]


def test_river_check_check_finishes_with_showdown_result():
    open_river()

    response = client.post(
        "/debug/check",
        json={
            "person_id": "user-2",
        },
    )

    assert response.status_code == 200
    body = response.json()

    assert body["ok"] is True
    assert "철수님이 체크했습니다" in body["message"]
    assert "현재 상태: RIVER" in body["status"]
    assert "현재 차례: 상현" in body["status"]

    response = client.post(
        "/debug/check",
        json={
            "person_id": "user-1",
        },
    )

    assert response.status_code == 200
    body = response.json()

    assert body["ok"] is True
    assert "상현님이 체크했습니다" in body["message"]
    assert "쇼다운 결과" in body["message"]
    assert "승자:" in body["message"]
    assert "현재 상태: FINISHED" in body["status"]
    assert "현재 차례: 없음" in body["status"]
    assert "팟: 0" in body["status"]


def test_small_blind_raise_big_blind_call_opens_flop():
    prepare_two_player_game()

    response = client.post(
        "/debug/raise",
        json={
            "person_id": "user-1",
            "amount": 600,
        },
    )

    assert response.status_code == 200
    body = response.json()

    assert body["ok"] is True
    assert "상현님이 600칩으로 레이즈했습니다" in body["message"]
    assert "현재 상태: PRE_FLOP" in body["status"]
    assert "팟: 800" in body["status"]
    assert "현재 최고 베팅: 600" in body["status"]
    assert "최소 레이즈: 400" in body["status"]
    assert "현재 차례: 철수" in body["status"]

    response = client.post(
        "/debug/call",
        json={
            "person_id": "user-2",
        },
    )

    assert response.status_code == 200
    body = response.json()

    assert body["ok"] is True
    assert "철수님이 400칩 콜했습니다" in body["message"]
    assert "플랍 오픈" in body["message"]
    assert "현재 상태: FLOP" in body["status"]
    assert "팟: 1200" in body["status"]
    assert "현재 최고 베팅: 0" in body["status"]
    assert "현재 차례: 철수" in body["status"]

def test_raise_under_minimum_fails():
    prepare_two_player_game()

    response = client.post(
        "/debug/raise",
        json={
            "person_id": "user-1",
            "amount": 250,
        },
    )

    assert response.status_code == 200
    body = response.json()

    assert body["ok"] is False
    assert "최소 레이즈 금액은 100칩입니다" in body["message"]

def test_small_blind_all_in_big_blind_call_runs_to_showdown():
    prepare_two_player_game()

    response = client.post(
        "/debug/command",
        json={
            "person_id": "user-1",
            "display_name": "상현",
            "text": "올인",
        },
    )

    assert response.status_code == 200
    body = response.json()

    assert body["ok"] is True
    assert "상현님이 9900칩 올인했습니다" in body["message"]
    assert "현재 상태: PRE_FLOP" in body["status"]
    assert "팟: 10200" in body["status"]
    assert "현재 최고 베팅: 10000" in body["status"]
    assert "현재 차례: 철수" in body["status"]

    response = client.post(
        "/debug/command",
        json={
            "person_id": "user-2",
            "display_name": "철수",
            "text": "콜",
        },
    )

    assert response.status_code == 200
    body = response.json()

    assert body["ok"] is True
    assert "철수님이 9800칩 콜했습니다" in body["message"]
    assert "플랍 오픈" in body["message"]
    assert "턴 오픈" in body["message"]
    assert "리버 오픈" in body["message"]
    assert "쇼다운 결과" in body["message"]
    assert "승자:" in body["message"]
    assert "현재 상태: FINISHED" in body["status"]
    assert "팟: 0" in body["status"]
    assert "현재 차례: 없음" in body["status"]


def test_parse_all_in_command_through_debug_command():
    prepare_two_player_game()

    response = client.post(
        "/debug/command",
        json={
            "person_id": "user-1",
            "display_name": "상현",
            "text": "올인",
        },
    )

    assert response.status_code == 200
    body = response.json()

    assert body["ok"] is True
    assert "올인했습니다" in body["message"]