from fastapi.testclient import TestClient

import app.main as main_module
from app.core.game_registry import GameType
from app.domain.game import HoldemGame
from app.games.dice.domain.game import DiceGame
from app.main import app
from app.services.game_store import JsonGameStore
from app.services.stats_store import JsonStatsStore


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


def test_room_can_select_play_and_restart_dice_game(monkeypatch):
    reset_platform(monkeypatch)
    rolls = iter([6, 3, 4, 4])
    monkeypatch.setattr(
        "app.games.dice.domain.game.random.randint",
        lambda _start, _end: next(rolls),
    )

    selection = command("dice-room", "user-1", "상현", "@FSS 게임선택 주사위").json()

    assert selection["ok"] is True
    assert "주사위 게임을 선택했습니다" in selection["message"]
    assert main_module.get_game_type_for_room("dice-room") == GameType.DICE

    command("dice-room", "user-1", "상현", "참가")
    command("dice-room", "user-2", "철수", "참가")
    result = command("dice-room", "user-1", "상현", "시작").json()

    assert result["ok"] is True
    assert "상현: 6" in result["message"]
    assert "철수: 3" in result["message"]
    assert "우승: 상현 (6)" in result["message"]

    restart = command("dice-room", "user-1", "상현", "새게임").json()
    assert restart["ok"] is True
    assert "공동 우승: 상현, 철수 (4)" in restart["message"]


def test_dice_game_state_is_saved_with_its_room_game_type(tmp_path):
    store = JsonGameStore(str(tmp_path / "games.json"))
    dice_game = DiceGame()
    dice_game.join("user-1", "상현")
    dice_game.join("user-2", "철수")

    store.save_all(
        room_games={"dice-room": dice_game},
        room_game_types={"dice-room": GameType.DICE},
    )

    loaded_games = store.load_all()
    loaded_types = store.load_game_types()

    assert loaded_types["dice-room"] == GameType.DICE
    assert isinstance(loaded_games["dice-room"], DiceGame)
    assert loaded_games["dice-room"].status() == dice_game.status()


def test_dice_help_explains_game_selection_and_rules(monkeypatch):
    reset_platform(monkeypatch)
    command("dice-room", "user-1", "상현", "게임선택 주사위")

    result = command("dice-room", "user-1", "상현", "도움말").json()

    assert result["ok"] is True
    assert "게임선택 주사위" in result["message"]
    assert "참가 → 시작" in result["message"]
    assert "동점자는 공동 우승" in result["message"]


def test_dice_ranking_and_personal_record_are_available(monkeypatch, tmp_path):
    reset_platform(monkeypatch)
    store = JsonStatsStore(str(tmp_path / "stats.json"))
    monkeypatch.setattr(main_module, "stats_store", store)
    rolls = iter([6, 3])
    monkeypatch.setattr(
        "app.games.dice.domain.game.random.randint",
        lambda _start, _end: next(rolls),
    )

    command("dice-room", "user-1", "상현", "게임선택 주사위")
    command("dice-room", "user-1", "상현", "참가")
    command("dice-room", "user-2", "철수", "참가")
    command("dice-room", "user-1", "상현", "시작")

    ranking = command("dice-room", "user-1", "상현", "랭킹").json()
    record = command("dice-room", "user-1", "상현", "전적").json()

    assert "주사위 랭킹" in ranking["message"]
    assert "상현 - 우승 1회 / 참가 1회 / 패배 0회" in ranking["message"]
    assert record["private"] is True
    assert "상현님의 주사위 전적" in record["message"]
    assert "우승: 1회" in record["message"]


def test_dice_ranking_reset_keeps_holdem_stats(monkeypatch, tmp_path):
    reset_platform(monkeypatch)
    store = JsonStatsStore(str(tmp_path / "stats.json"))
    store._save(
        {
            "players": {
                "user-1": {
                    "display_name": "상현",
                    "games": 2,
                    "wins": 1,
                    "eliminations": 1,
                    "last_played_at": None,
                    "dice": {
                        "games": 3,
                        "wins": 2,
                        "losses": 1,
                        "last_played_at": None,
                    },
                }
            }
        }
    )
    monkeypatch.setattr(main_module, "stats_store", store)
    command("dice-room", "user-1", "상현", "게임선택 주사위")

    result = main_module._handle_ranking_reset_command(
        room_id="dice-room",
        person_email="sh_lee@lotte.net",
    )

    assert result["ok"] is True
    assert "주사위 랭킹과 전적" in result["message"]
    assert store.dice_ranking_text() == "아직 저장된 주사위 전적이 없습니다."
    assert "상현 - 우승 1회 / 참가 2회" in store.ranking_text()
