from fastapi.testclient import TestClient

from app.domain.card import Card, Rank, Suit
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


def prepare_two_player_game():
    reset_game()

    command("user-1", "상현", "참가")
    command("user-2", "철수", "참가")
    command("user-1", "상현", "시작")


def open_flop():
    prepare_two_player_game()

    command("user-1", "상현", "콜")
    command("user-2", "철수", "체크")


def open_turn():
    open_flop()

    command("user-2", "철수", "체크")
    command("user-1", "상현", "체크")


def open_river():
    open_turn()

    command("user-2", "철수", "체크")
    command("user-1", "상현", "체크")


def test_start_without_two_players_fails():
    reset_game()

    command("user-1", "상현", "참가")

    response = command("user-1", "상현", "시작")
    body = response.json()

    assert response.status_code == 200
    assert body["ok"] is False
    assert "최소 2명 이상" in body["message"]


def test_duplicate_join_does_not_add_player_twice():
    reset_game()

    response = command("user-1", "상현", "참가")
    assert response.json()["ok"] is True

    response = command("user-1", "상현", "참가")
    body = response.json()

    assert body["ok"] is True
    assert "이미 참가 중입니다" in body["message"]

    response = command("user-1", "상현", "상태")
    status = response.json()["message"]

    assert "1. 상현" in status
    assert "2. 상현" not in status


def test_join_after_game_started_fails():
    prepare_two_player_game()

    response = command("user-3", "영희", "참가")
    body = response.json()

    assert body["ok"] is False
    assert "게임 시작 후에는 참가할 수 없습니다" in body["message"]


def test_start_while_game_in_progress_fails():
    prepare_two_player_game()

    response = command("user-1", "상현", "시작")
    body = response.json()

    assert body["ok"] is False
    assert "이미 게임이 진행 중입니다" in body["message"]


def test_non_participant_cannot_act():
    prepare_two_player_game()

    response = command("user-999", "외부인", "콜")
    body = response.json()

    assert body["ok"] is False
    assert "현재 차례는 상현님입니다" in body["message"]


def test_wrong_turn_player_cannot_act():
    prepare_two_player_game()

    response = command("user-2", "철수", "콜")
    body = response.json()

    assert body["ok"] is False
    assert "현재 차례는 상현님입니다" in body["message"]


def test_small_blind_cannot_check_preflop_when_call_needed():
    prepare_two_player_game()

    response = command("user-1", "상현", "체크")
    body = response.json()

    assert body["ok"] is False
    assert "체크할 수 없습니다" in body["message"]


def test_big_blind_cannot_call_when_no_call_amount():
    prepare_two_player_game()

    command("user-1", "상현", "콜")

    response = command("user-2", "철수", "콜")
    body = response.json()

    assert body["ok"] is False
    assert "콜할 금액이 없습니다" in body["message"]


def test_flop_first_player_cannot_call_when_no_bet():
    open_flop()

    response = command("user-2", "철수", "콜")
    body = response.json()

    assert body["ok"] is False
    assert "콜할 금액이 없습니다" in body["message"]


def test_flop_wrong_turn_cannot_check():
    open_flop()

    # 플랍에서는 현재 차례가 철수여야 함
    response = command("user-1", "상현", "체크")
    body = response.json()

    assert body["ok"] is False
    assert "현재 차례는 철수님입니다" in body["message"]


def test_raise_to_same_as_current_highest_fails():
    prepare_two_player_game()

    response = command("user-1", "상현", "레이즈 200")
    body = response.json()

    assert body["ok"] is False
    assert "현재 최고 베팅보다 커야 합니다" in body["message"]


def test_raise_under_min_raise_fails():
    prepare_two_player_game()

    response = command("user-1", "상현", "레이즈 250")
    body = response.json()

    assert body["ok"] is False
    assert "최소 레이즈 금액은 100칩입니다" in body["message"]


def test_raise_more_than_chips_fails():
    prepare_two_player_game()

    response = command("user-1", "상현", "레이즈 20000")
    body = response.json()

    assert body["ok"] is False
    assert "보유 칩보다 많이 레이즈할 수 없습니다" in body["message"]


def test_raise_then_opponent_fold_awards_pot_to_raiser():
    prepare_two_player_game()

    response = command("user-1", "상현", "레이즈 600")
    body = response.json()

    assert body["ok"] is True
    assert "팟: 800" in body["status"]
    assert "현재 차례: 철수" in body["status"]

    response = command("user-2", "철수", "폴드")
    body = response.json()

    assert body["ok"] is True
    assert "철수님이 폴드했습니다" in body["message"]
    assert "상현님이 팟 800칩을 획득했습니다" in body["message"]
    assert "현재 상태: FINISHED" in body["status"]
    assert "팟: 0" in body["status"]


def test_action_after_finished_fails():
    prepare_two_player_game()

    command("user-1", "상현", "폴드")

    response = command("user-2", "철수", "체크")
    body = response.json()

    assert body["ok"] is False
    assert "현재 액션할 수 없는 상태입니다" in body["message"]


def test_next_hand_after_finished_rotates_dealer():
    prepare_two_player_game()

    command("user-1", "상현", "폴드")

    response = command("user-1", "상현", "시작")
    body = response.json()

    assert body["ok"] is True
    assert "새 판을 시작했습니다" in body["message"]
    assert "현재 상태: PRE_FLOP" in body["status"]

    # 2인 게임에서는 딜러가 SB
    assert "상현 (BB)" in body["status"]
    assert "철수 (D/SB)" in body["status"]
    assert "현재 차례: 철수" in body["status"]


def test_all_in_command_sets_player_all_in_and_passes_turn():
    prepare_two_player_game()

    response = command("user-1", "상현", "올인")
    body = response.json()

    assert body["ok"] is True
    assert "상현님이 9900칩 올인했습니다" in body["message"]
    assert "상현 (D/SB) - 0칩" in body["status"]
    assert "올인" in body["status"]
    assert "현재 최고 베팅: 10000" in body["status"]
    assert "현재 차례: 철수" in body["status"]


def test_all_in_then_opponent_fold_awards_pot():
    prepare_two_player_game()

    command("user-1", "상현", "올인")

    response = command("user-2", "철수", "폴드")
    body = response.json()

    assert body["ok"] is True
    assert "철수님이 폴드했습니다" in body["message"]
    assert "상현님이 팟 10200칩을 획득했습니다" in body["message"]
    assert "현재 상태: FINISHED" in body["status"]
    assert "팟: 0" in body["status"]


def test_all_in_then_opponent_call_runs_board_to_showdown():
    prepare_two_player_game()

    command("user-1", "상현", "올인")

    response = command("user-2", "철수", "콜")
    body = response.json()

    assert body["ok"] is True
    assert "철수님이 9800칩 콜했습니다" in body["message"]
    assert "플랍 오픈" in body["message"]
    assert "턴 오픈" in body["message"]
    assert "리버 오픈" in body["message"]
    assert "쇼다운 결과" in body["message"]
    assert "현재 상태: FINISHED" in body["status"]
    assert "팟: 0" in body["status"]


def test_private_cards_before_start_returns_no_cards():
    reset_game()

    command("user-1", "상현", "참가")

    response = command("user-1", "상현", "내카드")
    body = response.json()

    assert body["ok"] is True
    assert "아직 카드가 없습니다" in body["message"]


def test_unknown_command_fails():
    reset_game()

    response = command("user-1", "상현", "뭐함")
    body = response.json()

    assert body["ok"] is False
    assert "알 수 없는 명령어입니다" in body["message"]

def test_help_command_returns_available_commands():
    reset_game()

    response = command("user-1", "상현", "도움말")
    body = response.json()

    assert response.status_code == 200
    assert body["ok"] is True
    assert "사용 가능 명령어" in body["message"]
    assert "참가" in body["message"]
    assert "시작" in body["message"]
    assert "내카드" in body["message"]
    assert "레이즈 600" in body["message"]
    assert "올인" in body["message"]
    assert "리셋" in body["message"]
    assert "현재 상태: WAITING" in body["status"]

def test_reset_command_clears_game_state():
    reset_game()

    command("user-1", "상현", "참가")
    command("user-2", "철수", "참가")

    response = command("user-1", "상현", "리셋")
    body = response.json()

    assert response.status_code == 200
    assert body["ok"] is True
    assert "게임을 리셋했습니다" in body["message"]
    assert "현재 상태: WAITING" in body["status"]
    assert "참가자 없음" in body["status"]

def test_reset_command_is_blocked_during_active_hand():
    prepare_two_player_game()

    response = command("user-1", "상현", "리셋")
    body = response.json()

    assert response.status_code == 200
    assert body["ok"] is False
    assert "게임 진행 중에는 리셋할 수 없습니다" in body["message"]
    assert "현재 상태: PRE_FLOP" in body["status"]

def test_reset_command_is_blocked_during_active_hand():
    prepare_two_player_game()

    response = command("user-1", "상현", "리셋")
    body = response.json()

    assert response.status_code == 200
    assert body["ok"] is False
    assert "게임 진행 중에는 리셋할 수 없습니다" in body["message"]
    assert "현재 상태: PRE_FLOP" in body["status"]


def test_reset_command_clears_game_state_while_waiting():
    reset_game()

    command("user-1", "상현", "참가")
    command("user-2", "철수", "참가")

    response = command("user-1", "상현", "리셋")
    body = response.json()

    assert response.status_code == 200
    assert body["ok"] is True
    assert "게임을 리셋했습니다" in body["message"]
    assert "현재 상태: WAITING" in body["status"]
    assert "참가자 없음" in body["status"]


def test_can_join_again_after_reset():
    reset_game()

    command("user-1", "상현", "참가")
    command("user-2", "철수", "참가")

    reset_response = command("user-1", "상현", "리셋")
    reset_body = reset_response.json()

    assert reset_body["ok"] is True
    assert "게임을 리셋했습니다" in reset_body["message"]

    response = command("user-1", "상현", "참가")
    body = response.json()

    assert response.status_code == 200
    assert body["ok"] is True
    assert "상현님이 참가했습니다" in body["message"]

def test_blocked_reset_keeps_current_players():
    prepare_two_player_game()

    reset_response = command("user-1", "상현", "리셋")
    reset_body = reset_response.json()

    assert reset_body["ok"] is False
    assert "게임 진행 중에는 리셋할 수 없습니다" in reset_body["message"]

    response = command("user-1", "상현", "참가")
    body = response.json()

    assert response.status_code == 200
    assert body["ok"] is True
    assert "상현님은 이미 참가 중입니다" in body["message"]

def test_my_cards_command_is_private_and_silent_public():
    prepare_two_player_game()

    response = command("user-1", "상현", "내카드")
    body = response.json()

    assert response.status_code == 200
    assert body["ok"] is True
    assert body["private"] is True
    assert body["silent_public"] is True
    assert body["public_message"] is None
    assert "상현님의 카드:" in body["message"]

def test_duplicate_join_after_game_started_says_already_joined():
    prepare_two_player_game()

    response = command("user-1", "상현", "참가")
    body = response.json()

    assert body["ok"] is True
    assert "이미 참가 중입니다" in body["message"]

def test_start_command_requests_private_card_deal_to_all_players():
    reset_game()

    command("user-1", "상현", "참가")
    command("user-2", "철수", "참가")

    response = command("user-1", "상현", "시작")
    body = response.json()

    assert response.status_code == 200
    assert body["ok"] is True
    assert body["deal_private_cards"] is True
    assert body["private"] is False
    assert "게임을 시작했습니다" in body["message"]

def test_record_command_is_private_and_silent_public():
    reset_game()

    response = command("user-1", "상현", "전적")
    body = response.json()

    assert response.status_code == 200
    assert body["ok"] is True
    assert body["private"] is True
    assert body["silent_public"] is True
    assert body["public_message"] is None

def test_new_tournament_keeps_same_players_and_resets_chips_after_game_over():
    reset_game()

    command("user-1", "상현", "참가")
    command("user-2", "철수", "참가")

    command("user-1", "상현", "시작")

    current_game = main_module.get_game_for_room(main_module.DEBUG_ROOM_ID)

    # 랜덤 쇼다운에 의존하지 않도록 상현이 반드시 이기게 만든다.
    current_game.players[0].hole_cards = [
        Card(suit=Suit.SPADE, rank=Rank.ACE),
        Card(suit=Suit.HEART, rank=Rank.ACE),
    ]
    current_game.players[1].hole_cards = [
        Card(suit=Suit.CLUB, rank=Rank.KING),
        Card(suit=Suit.DIAMOND, rank=Rank.QUEEN),
    ]
    current_game.community_cards = [
        Card(suit=Suit.CLUB, rank=Rank.TWO),
        Card(suit=Suit.DIAMOND, rank=Rank.SEVEN),
        Card(suit=Suit.HEART, rank=Rank.NINE),
        Card(suit=Suit.SPADE, rank=Rank.JACK),
        Card(suit=Suit.CLUB, rank=Rank.THREE),
    ]

    command("user-1", "상현", "올인")
    command("user-2", "철수", "콜")

    ended_game = main_module.get_game_for_room(main_module.DEBUG_ROOM_ID)

    assert ended_game.game_over is True
    assert ended_game.final_winner_name == "상현"

    response = command("user-1", "상현", "새게임")
    body = response.json()

    assert body["ok"] is True
    assert "같은 참가자로 새 토너먼트를 시작했습니다" in body["message"]
    assert "현재 상태: PRE_FLOP" in body["status"]
    assert "상현" in body["status"]
    assert "철수" in body["status"]

    current_game = main_module.get_game_for_room(main_module.DEBUG_ROOM_ID)

    assert len(current_game.players) == 2
    assert current_game.game_over is False
    assert current_game.eliminated_players == []

    player_ids = {
        player.person_id
        for player in current_game.players
    }

    assert player_ids == {"user-1", "user-2"}

    total_chips = sum(
        player.chips + player.total_bet
        for player in current_game.players
    )

    assert total_chips == 20000