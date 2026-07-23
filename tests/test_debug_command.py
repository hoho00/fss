from fastapi.testclient import TestClient

import app.main as main_module
from app.domain.game import HoldemGame
from app.main import app


client = TestClient(app)


def reset_game():
    main_module.game = HoldemGame()


def command(person_id: str, display_name: str, text: str):
    return client.post(
        "/debug/command",
        json={
            "person_id": person_id,
            "display_name": display_name,
            "text": text,
        },
    )


def test_debug_command_join_start_and_status():
    reset_game()

    response = command("user-1", "상현", "참가")
    assert response.status_code == 200
    assert response.json()["ok"] is True
    assert "상현님이 참가했습니다" in response.json()["message"]

    response = command("user-2", "철수", "참가")
    assert response.status_code == 200
    assert response.json()["ok"] is True
    assert "철수님이 참가했습니다" in response.json()["message"]

    response = command("user-1", "상현", "시작")
    assert response.status_code == 200
    assert response.json()["ok"] is True
    assert "게임을 시작했습니다" in response.json()["message"]

    response = command("user-1", "상현", "상태")
    assert response.status_code == 200
    assert response.json()["ok"] is True
    assert "현재 상태: PRE_FLOP" in response.json()["message"]


def test_debug_command_raise_and_call_opens_flop():
    reset_game()

    command("user-1", "상현", "참가")
    command("user-2", "철수", "참가")
    command("user-1", "상현", "시작")

    response = command("user-1", "상현", "레이즈 600")
    assert response.status_code == 200
    assert response.json()["ok"] is True
    assert "상현님이 600칩으로 레이즈했습니다" in response.json()["message"]

    response = command("user-2", "철수", "콜")
    assert response.status_code == 200
    assert response.json()["ok"] is True
    assert "철수님이 400칩 콜했습니다" in response.json()["message"]
    assert "플랍 오픈" in response.json()["message"]


def test_debug_command_unknown():
    reset_game()

    response = command("user-1", "상현", "몰라")

    assert response.status_code == 200
    assert response.json()["ok"] is False
    assert "알 수 없는 명령어입니다" in response.json()["message"]