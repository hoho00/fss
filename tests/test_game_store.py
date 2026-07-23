from app.domain.game import GamePhase, HoldemGame
from app.services.game_store import JsonGameStore


def test_game_to_dict_and_from_dict_restores_waiting_players():
    game = HoldemGame()

    game.join("user-1", "상현")
    game.join("user-2", "철수")

    restored = HoldemGame.from_dict(game.to_dict())

    assert restored.phase == GamePhase.WAITING
    assert len(restored.players) == 2
    assert restored.players[0].person_id == "user-1"
    assert restored.players[0].display_name == "상현"
    assert restored.players[0].chips == 10000
    assert restored.players[1].person_id == "user-2"
    assert restored.players[1].display_name == "철수"


def test_game_to_dict_and_from_dict_restores_started_game():
    game = HoldemGame()

    game.join("user-1", "상현")
    game.join("user-2", "철수")
    game.start()

    restored = HoldemGame.from_dict(game.to_dict())

    assert restored.phase == GamePhase.PRE_FLOP
    assert len(restored.players) == 2
    assert len(restored.players[0].hole_cards) == 2
    assert len(restored.players[1].hole_cards) == 2
    assert restored.pot == 300
    assert restored.current_highest_bet == 200
    assert restored.current_turn_index == 0
    assert restored.deck is not None
    assert restored.deck.remaining_count() == game.deck.remaining_count()


def test_game_to_dict_and_from_dict_restores_after_action():
    game = HoldemGame()

    game.join("user-1", "상현")
    game.join("user-2", "철수")
    game.start()
    game.call("user-1")

    restored = HoldemGame.from_dict(game.to_dict())

    assert restored.phase == GamePhase.PRE_FLOP
    assert restored.pot == 400
    assert restored.current_highest_bet == 200
    assert restored.current_turn_index == 1
    assert restored.players[0].chips == 9800
    assert restored.players[0].current_bet == 200
    assert restored.players[0].acted is True


def test_json_game_store_saves_and_loads_room_games(tmp_path):
    file_path = tmp_path / "games.json"
    store = JsonGameStore(str(file_path))

    room_a_game = HoldemGame()
    room_a_game.join("a-user-1", "A상현")
    room_a_game.join("a-user-2", "A철수")
    room_a_game.start()

    room_b_game = HoldemGame()
    room_b_game.join("b-user-1", "B영희")

    store.save_all(
        {
            "room-a": room_a_game,
            "room-b": room_b_game,
        }
    )

    loaded_games = store.load_all()

    assert "room-a" in loaded_games
    assert "room-b" in loaded_games

    assert loaded_games["room-a"].phase == GamePhase.PRE_FLOP
    assert "A상현" in loaded_games["room-a"].status()
    assert "A철수" in loaded_games["room-a"].status()

    assert loaded_games["room-b"].phase == GamePhase.WAITING
    assert "B영희" in loaded_games["room-b"].status()


def test_json_game_store_loads_empty_when_file_does_not_exist(tmp_path):
    file_path = tmp_path / "missing.json"
    store = JsonGameStore(str(file_path))

    loaded_games = store.load_all()

    assert loaded_games == {}

def test_json_game_store_saves_and_loads_card_tokens(tmp_path):
    file_path = tmp_path / "games.json"
    store = JsonGameStore(str(file_path))

    room_a_game = HoldemGame()
    room_a_game.join("a-user-1", "A상현")

    store.save_all(
        room_games={
            "room-a": room_a_game,
        },
        latest_card_tokens={
            "room-a": "token-a",
            "room-b": "token-b",
        },
    )

    loaded_games = store.load_all()
    loaded_tokens = store.load_card_tokens()

    assert "room-a" in loaded_games
    assert loaded_tokens["room-a"] == "token-a"
    assert loaded_tokens["room-b"] == "token-b"


def test_json_game_store_saves_and_loads_processed_webhook_ids(tmp_path):
    store = JsonGameStore(str(tmp_path / "games.json"))

    store.save_all({}, processed_webhook_ids=["message-1", "action-1"])

    assert store.load_processed_webhook_ids() == ["message-1", "action-1"]
