from app.commands.parser import CommandParser
from app.domain.game import HoldemGame
from app.services.holdem_bot_service import HoldemBotService
from app.services.stats_store import JsonStatsStore


def test_record_command_uses_json_stats_store_player_record_method(tmp_path):
    service = HoldemBotService(
        game=HoldemGame(),
        command_parser=CommandParser(),
        stats_store=JsonStatsStore(str(tmp_path / "stats.json")),
    )

    result = service.handle_text_command(
        person_id="user-1",
        display_name="상현",
        text="전적",
    )

    assert result["ok"] is True
    assert result["private"] is True
    assert result["silent_public"] is True
    assert result["message"] == "상현님의 저장된 전적이 아직 없습니다."


def test_reset_command_includes_the_requester_name():
    service = HoldemBotService(
        game=HoldemGame(),
        command_parser=CommandParser(),
    )

    result = service.handle_text_command(
        person_id="user-1",
        display_name="상현",
        text="리셋",
    )

    assert result["ok"] is True
    assert result["message"] == "상현님이 게임을 리셋했습니다."
