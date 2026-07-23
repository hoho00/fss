from app.core.game_registry import GameType
from app.core.room_manager import RoomManager
from app.games.dice.domain.game import DiceGame


def test_room_manager_creates_and_replaces_room_games():
    manager = RoomManager()

    game, created = manager.get_or_create_game("room-1")
    replacement = manager.replace_game("room-1", GameType.DICE)

    assert created is True
    assert manager.game_type("room-1") == GameType.DICE
    assert isinstance(replacement, DiceGame)
    assert replacement is manager.games["room-1"]
    assert game is not replacement


def test_room_manager_bounds_processed_webhook_ids():
    manager = RoomManager(processed_id_limit=2)

    manager.mark_webhook_processed("one")
    manager.mark_webhook_processed("two")
    manager.mark_webhook_processed("two")
    manager.mark_webhook_processed("three")

    assert manager.processed_webhook_ids == ["two", "three"]
