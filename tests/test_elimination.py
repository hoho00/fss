import pytest

from app.domain.card import Card, Rank, Suit
from app.domain.game import GamePhase, HoldemGame


def card(rank: Rank, suit: Suit) -> Card:
    return Card(rank=rank, suit=suit)


def set_fixed_showdown_cards(game: HoldemGame) -> None:
    game.players[0].hole_cards = [
        card(Rank.ACE, Suit.SPADE),
        card(Rank.ACE, Suit.HEART),
    ]

    game.players[1].hole_cards = [
        card(Rank.KING, Suit.SPADE),
        card(Rank.KING, Suit.HEART),
    ]

    # draw()가 pop()이라 마지막 카드부터 뽑힘
    game.deck.cards = [
        card(Rank.SEVEN, Suit.CLUB),
        card(Rank.FIVE, Suit.HEART),
        card(Rank.FOUR, Suit.SPADE),
        card(Rank.THREE, Suit.DIAMOND),
        card(Rank.TWO, Suit.CLUB),
    ]


def test_two_player_loser_is_eliminated_and_game_over_after_all_in_showdown():
    game = HoldemGame()

    game.join("user-1", "상현")
    game.join("user-2", "철수")
    game.start()

    set_fixed_showdown_cards(game)

    game.all_in("user-1")
    message = game.call("user-2")

    assert "쇼다운 결과" in message
    assert "승자: 상현" in message
    assert "탈락: 철수" in message
    assert "최종 우승: 상현님" in message

    assert game.phase == GamePhase.FINISHED
    assert game.game_over is True
    assert game.final_winner_name == "상현"

    assert len(game.players) == 1
    assert game.players[0].display_name == "상현"
    assert game.players[0].chips == 20000

    assert len(game.eliminated_players) == 1
    assert game.eliminated_players[0]["display_name"] == "철수"


def test_cannot_start_after_game_over():
    game = HoldemGame()

    game.join("user-1", "상현")
    game.join("user-2", "철수")
    game.start()

    set_fixed_showdown_cards(game)

    game.all_in("user-1")
    game.call("user-2")

    with pytest.raises(ValueError) as error:
        game.start()

    assert "게임이 종료되었습니다" in str(error.value)


def test_three_player_game_continues_when_one_player_is_eliminated():
    game = HoldemGame()

    game.join("user-1", "상현")
    game.join("user-2", "철수")
    game.join("user-3", "영희")
    game.start()

    # 3인 프리플랍 순서:
    # user-1: 딜러, 첫 액션
    # user-2: SB
    # user-3: BB
    game.players[0].hole_cards = [
        card(Rank.ACE, Suit.SPADE),
        card(Rank.ACE, Suit.HEART),
    ]

    game.players[2].hole_cards = [
        card(Rank.KING, Suit.SPADE),
        card(Rank.KING, Suit.HEART),
    ]

    game.deck.cards = [
        card(Rank.SEVEN, Suit.CLUB),
        card(Rank.FIVE, Suit.HEART),
        card(Rank.FOUR, Suit.SPADE),
        card(Rank.THREE, Suit.DIAMOND),
        card(Rank.TWO, Suit.CLUB),
    ]

    game.all_in("user-1")
    game.fold("user-2")
    message = game.call("user-3")

    assert "쇼다운 결과" in message
    assert "승자: 상현" in message
    assert "탈락: 영희" in message
    assert "최종 우승" not in message

    assert game.phase == GamePhase.FINISHED
    assert game.game_over is False

    remaining_names = [
        player.display_name
        for player in game.players
    ]

    assert remaining_names == ["상현", "철수"]

    eliminated_names = [
        player["display_name"]
        for player in game.eliminated_players
    ]

    assert eliminated_names == ["영희"]

    next_hand_message = game.start()

    assert "새 판을 시작했습니다" in next_hand_message
    assert game.phase == GamePhase.PRE_FLOP
    assert len(game.players) == 2


def test_elimination_state_is_serialized_and_restored():
    game = HoldemGame()

    game.join("user-1", "상현")
    game.join("user-2", "철수")
    game.start()

    set_fixed_showdown_cards(game)

    game.all_in("user-1")
    game.call("user-2")

    restored = HoldemGame.from_dict(game.to_dict())

    assert restored.game_over is True
    assert restored.final_winner_name == "상현"

    assert len(restored.players) == 1
    assert restored.players[0].display_name == "상현"

    assert len(restored.eliminated_players) == 1
    assert restored.eliminated_players[0]["display_name"] == "철수"

    status = restored.status()

    assert "최종 우승: 상현님" in status
    assert "탈락자: 철수" in status