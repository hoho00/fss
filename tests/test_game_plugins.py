from app.commands.parser import CommandParser
from app.core.game_registry import GAME_PLUGINS, GameType


def test_every_registered_game_can_create_restore_and_build_actions():
    for game_type, plugin in GAME_PLUGINS.items():
        game = plugin.create_game()
        restored = plugin.restore_game(game.to_dict())
        service = plugin.create_service(restored, CommandParser(), None, "room")

        assert plugin.game_type == game_type
        assert isinstance(restored, plugin.game_class)
        assert callable(service.handle_text_command)
        assert isinstance(plugin.build_actions(restored), list)


def test_registry_contains_all_supported_game_types():
    assert set(GAME_PLUGINS) == set(GameType)
