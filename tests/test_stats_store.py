import threading

from app.domain.game import HoldemGame
from app.domain.player import Player
from app.games.dice.domain.game import DiceGame, DiceGamePhase
from app.services.stats_store import JsonStatsStore


def make_store(tmp_path) -> JsonStatsStore:
    return JsonStatsStore(str(tmp_path / "stats.json"))


def make_finished_game() -> HoldemGame:
    game = HoldemGame()

    winner = Player(
        person_id="user-1",
        display_name="상현",
        chips=20000,
    )

    loser = {
        "person_id": "user-2",
        "display_name": "철수",
        "chips": 0,
    }

    game.players = [
        winner,
    ]
    game.eliminated_players = [
        loser,
    ]
    game.game_over = True
    game.final_winner_name = "상현"

    return game


def test_ranking_text_returns_empty_message_when_no_stats(tmp_path):
    store = make_store(tmp_path)

    result = store.ranking_text()

    assert result == "아직 저장된 전적이 없습니다."


def test_player_record_text_returns_empty_message_when_no_stats(tmp_path):
    store = make_store(tmp_path)

    result = store.player_record_text(
        person_id="user-1",
        display_name="상현",
    )

    assert result == "상현님의 저장된 전적이 아직 없습니다."


def test_record_game_over_saves_winner_and_loser_stats(tmp_path):
    store = make_store(tmp_path)
    game = make_finished_game()

    store.record_game_over(game)

    ranking = store.ranking_text()

    assert "랭킹" in ranking
    assert "1. 상현 - 우승 1회 / 참가 1회 / 탈락 0회 / 승률 100.0%" in ranking
    assert "2. 철수 - 우승 0회 / 참가 1회 / 탈락 1회 / 승률 0.0%" in ranking


def test_player_record_text_for_winner(tmp_path):
    store = make_store(tmp_path)
    game = make_finished_game()

    store.record_game_over(game)

    result = store.player_record_text(
        person_id="user-1",
        display_name="상현",
    )

    assert "상현님의 전적" in result
    assert "참가: 1회" in result
    assert "최종 우승: 1회" in result
    assert "탈락: 0회" in result
    assert "승률: 100.0%" in result
    assert "최근 플레이:" in result
    assert "T" not in result
    assert "+00:00" not in result


def test_player_record_text_for_loser(tmp_path):
    store = make_store(tmp_path)
    game = make_finished_game()

    store.record_game_over(game)

    result = store.player_record_text(
        person_id="user-2",
        display_name="철수",
    )

    assert "철수님의 전적" in result
    assert "참가: 1회" in result
    assert "최종 우승: 0회" in result
    assert "탈락: 1회" in result
    assert "승률: 0.0%" in result
    assert "최근 플레이:" in result
    assert "T" not in result
    assert "+00:00" not in result


def test_record_game_over_accumulates_stats(tmp_path):
    store = make_store(tmp_path)

    first_game = make_finished_game()
    store.record_game_over(first_game)

    second_game = make_finished_game()
    store.record_game_over(second_game)

    winner_record = store.player_record_text(
        person_id="user-1",
        display_name="상현",
    )

    loser_record = store.player_record_text(
        person_id="user-2",
        display_name="철수",
    )

    assert "참가: 2회" in winner_record
    assert "최종 우승: 2회" in winner_record
    assert "탈락: 0회" in winner_record
    assert "승률: 100.0%" in winner_record

    assert "참가: 2회" in loser_record
    assert "최종 우승: 0회" in loser_record
    assert "탈락: 2회" in loser_record
    assert "승률: 0.0%" in loser_record


def test_record_game_over_ignores_game_not_over(tmp_path):
    store = make_store(tmp_path)

    game = make_finished_game()
    game.game_over = False

    store.record_game_over(game)

    assert store.ranking_text() == "아직 저장된 전적이 없습니다."


def test_holdem_game_is_recorded_only_once(tmp_path):
    store = make_store(tmp_path)
    game = make_finished_game()
    game.game_id = "holdem-game-1"

    store.record_game_over(game)
    store.record_game_over(game)

    assert "참가: 1회" in store.player_record_text("user-1", "영현")


def test_concurrent_game_results_do_not_overwrite_each_other(tmp_path):
    store = make_store(tmp_path)
    first = make_finished_game()
    second = make_finished_game()
    first.game_id = "holdem-game-1"
    second.game_id = "holdem-game-2"

    threads = [
        threading.Thread(target=store.record_game_over, args=(game,))
        for game in (first, second)
    ]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    assert "참가: 2회" in store.player_record_text("user-1", "영현")


def test_dice_stats_are_kept_separate_from_holdem_stats(tmp_path):
    store = make_store(tmp_path)
    game = DiceGame()
    game.join("user-1", "상현")
    game.join("user-2", "철수")
    game.phase = DiceGamePhase.FINISHED
    game.winner_person_ids = ["user-1"]

    store.record_dice_game(game)

    assert "주사위 랭킹" in store.dice_ranking_text()
    assert "상현 - 우승 1회 / 참가 1회 / 패배 0회" in store.dice_ranking_text()
    assert "철수 - 우승 0회 / 참가 1회 / 패배 1회" in store.dice_ranking_text()
    assert "상현님의 주사위 전적" in store.dice_player_record_text("user-1", "상현")
    assert store.ranking_text() == "아직 저장된 전적이 없습니다."


def test_dice_game_is_recorded_only_once_and_has_no_holdem_record(tmp_path):
    store = make_store(tmp_path)
    game = DiceGame()
    game.join("user-1", "영현")
    game.join("user-2", "철수")
    game.phase = DiceGamePhase.FINISHED
    game.winner_person_ids = ["user-1"]
    game.game_id = "dice-game-1"

    store.record_dice_game(game)
    store.record_dice_game(game)

    assert "참가: 1회" in store.dice_player_record_text("user-1", "영현")
    assert store.player_record_text("user-1", "영현") == "영현님의 저장된 홀덤 전적은 아직 없습니다."


def test_format_korean_datetime():
    store = JsonStatsStore()

    result = store._format_korean_datetime("2026-07-14T01:23:45.123456+00:00")

    assert result == "2026-07-14 10:23"


def test_format_korean_datetime_returns_dash_when_empty():
    store = JsonStatsStore()

    assert store._format_korean_datetime(None) == "-"


def test_format_korean_datetime_returns_original_value_when_invalid():
    store = JsonStatsStore()

    assert store._format_korean_datetime("invalid-date") == "invalid-date"
