from fastapi.testclient import TestClient

import app.main as main_module
from app.core.game_registry import GameType
from app.domain.game import HoldemGame
from app.games.sword_upgrade.domain.game import DESTROY_CHANCE, SwordUpgradeGame
from app.main import app
from app.services.game_store import JsonGameStore


client = TestClient(app)


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


def reset_platform(monkeypatch):
    main_module.game = HoldemGame()
    main_module.room_games.clear()
    main_module.room_game_types.clear()
    main_module.latest_card_tokens.clear()
    monkeypatch.setattr(main_module, "save_room_games", lambda: None)
    monkeypatch.setattr(main_module, "stats_store", None)


def test_success_rate_decreases_by_ten_percent():
    assert SwordUpgradeGame.success_rate(1) == 0.9
    assert SwordUpgradeGame.success_rate(2) == 0.8
    assert SwordUpgradeGame.success_rate(9) == 0.1
    assert SwordUpgradeGame.success_rate(10) == 0.0


def test_create_and_enhance_sword_success(monkeypatch):
    reset_platform(monkeypatch)
    monkeypatch.setattr(
        "app.games.sword_upgrade.domain.game.random.random",
        lambda: 0.0,
    )

    selection = command("sword-room", "user-1", "상현", "@FSS 게임선택 검키우기").json()
    assert selection["ok"] is True
    assert "검키우기 게임을 선택했습니다" in selection["message"]
    assert main_module.get_game_type_for_room("sword-room") == GameType.SWORD_UPGRADE

    created = command("sword-room", "user-1", "상현", "검생성").json()
    assert created["ok"] is True
    assert "검을 생성했습니다" in created["message"]
    assert "0강" in created["message"]

    enhanced = command("sword-room", "user-1", "상현", "강화").json()
    assert enhanced["ok"] is True
    assert "강화 성공" in enhanced["message"]
    assert "+1강" in enhanced["message"]


def test_enhance_failure_drops_one_level(monkeypatch):
    reset_platform(monkeypatch)
    rolls = iter([0.0, 0.99, 0.99])
    monkeypatch.setattr(
        "app.games.sword_upgrade.domain.game.random.random",
        lambda: next(rolls),
    )

    command("sword-room", "user-1", "상현", "게임선택 검키우기")
    command("sword-room", "user-1", "상현", "검생성")
    command("sword-room", "user-1", "상현", "강화")

    failed = command("sword-room", "user-1", "상현", "강화").json()
    assert failed["ok"] is True
    assert "강화 실패" in failed["message"]
    assert "1강 → 0강" in failed["message"]

    game = main_module.get_game_for_room("sword-room")
    assert isinstance(game, SwordUpgradeGame)
    assert game.swords["user-1"].level == 0


def test_enhance_failure_can_destroy_sword(monkeypatch):
    reset_platform(monkeypatch)
    # First enhance succeeds, second fails and destroy roll hits.
    rolls = iter([0.0, 0.99, DESTROY_CHANCE / 2])
    monkeypatch.setattr(
        "app.games.sword_upgrade.domain.game.random.random",
        lambda: next(rolls),
    )

    command("sword-room", "user-1", "상현", "게임선택 검키우기")
    command("sword-room", "user-1", "상현", "검생성")
    command("sword-room", "user-1", "상현", "강화")

    destroyed = command("sword-room", "user-1", "상현", "강화").json()
    assert destroyed["ok"] is True
    assert "파괴" in destroyed["message"]

    game = main_module.get_game_for_room("sword-room")
    assert "user-1" not in game.swords


def test_multiple_players_have_independent_swords(monkeypatch):
    reset_platform(monkeypatch)
    monkeypatch.setattr(
        "app.games.sword_upgrade.domain.game.random.random",
        lambda: 0.0,
    )

    command("sword-room", "user-1", "상현", "게임선택 검키우기")
    command("sword-room", "user-1", "상현", "검생성")
    command("sword-room", "user-2", "철수", "검생성")
    command("sword-room", "user-1", "상현", "강화")
    command("sword-room", "user-1", "상현", "강화")

    status = command("sword-room", "user-1", "상현", "상태").json()
    assert status["ok"] is True
    assert "상현: +2강" in status["message"]
    assert "철수: +0강" in status["message"]


def test_cannot_create_duplicate_sword(monkeypatch):
    reset_platform(monkeypatch)
    command("sword-room", "user-1", "상현", "게임선택 검키우기")
    command("sword-room", "user-1", "상현", "검생성")

    duplicate = command("sword-room", "user-1", "상현", "검생성").json()
    assert duplicate["ok"] is False
    assert "이미 검이 있습니다" in duplicate["message"]


def test_cannot_enhance_without_sword(monkeypatch):
    reset_platform(monkeypatch)
    command("sword-room", "user-1", "상현", "게임선택 검키우기")

    result = command("sword-room", "user-1", "상현", "강화").json()
    assert result["ok"] is False
    assert "먼저 검을 생성" in result["message"]


def test_sword_game_state_persists(tmp_path):
    store = JsonGameStore(str(tmp_path / "games.json"))
    game = SwordUpgradeGame()
    game.create_sword("user-1", "상현")
    game.swords["user-1"].level = 3

    store.save_all(
        room_games={"sword-room": game},
        room_game_types={"sword-room": GameType.SWORD_UPGRADE},
    )

    loaded_games = store.load_all()
    loaded_types = store.load_game_types()

    assert loaded_types["sword-room"] == GameType.SWORD_UPGRADE
    assert isinstance(loaded_games["sword-room"], SwordUpgradeGame)
    assert loaded_games["sword-room"].swords["user-1"].level == 3


def test_sword_help_explains_rules(monkeypatch):
    reset_platform(monkeypatch)
    command("sword-room", "user-1", "상현", "게임선택 검키우기")

    result = command("sword-room", "user-1", "상현", "도움말").json()
    assert result["ok"] is True
    assert "게임선택 검키우기" in result["message"]
    assert "1강 90%" in result["message"]
    assert "파괴" in result["message"]


def test_sword_card_actions_include_create_and_enhance(monkeypatch):
    reset_platform(monkeypatch)
    command("sword-room", "user-1", "상현", "게임선택 검키우기")
    game = main_module.get_game_for_room("sword-room")
    actions = main_module._build_available_card_actions(game)
    commands = [command for _, command in actions]

    assert "검생성" in commands
    assert "강화" in commands
