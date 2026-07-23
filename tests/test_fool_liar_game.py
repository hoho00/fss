from datetime import datetime, timedelta, timezone
import random

import pytest

import app.main as main_module
from app.commands.parser import CommandParser
from app.core.game_registry import GameType
from app.domain.game import GamePhase, HoldemGame
from app.games.fool_liar.domain.game import FoolLiarGame, FoolLiarPhase
from app.games.fool_liar.domain.word_repository import JsonWordPairRepository, Word, WordPair
from app.games.fool_liar.services.fool_liar_bot_service import FoolLiarBotService
from app.services.game_store import JsonGameStore
from app.services.stats_store import JsonStatsStore


PAIR = WordPair(
    "테스트",
    Word("아이스크림", ("아이스 크림", "ice cream")),
    Word("빙수", ()),
)


def waiting_game(count=3):
    game = FoolLiarGame()
    for index in range(count):
        game.join(f"user-{index + 1}", f"참가자{index + 1}")
    return game


def started_game(count=3):
    game = waiting_game(count)
    game.start(PAIR, rng=random.Random(7))
    return game


def finish_descriptions(game):
    while game.phase == FoolLiarPhase.EXPLAINING:
        actor = game.current_actor_person_id()
        game.submit_description(actor, f"{game._player_name(actor)}의 설명")


def vote_for_unique_target(game, target_id):
    fallback = next(player.person_id for player in game.players if player.person_id != target_id)
    for player in game.players:
        game.submit_vote(player.person_id, fallback if player.person_id == target_id else target_id)


def test_word_pair_data_has_at_least_1000_distinct_prompts():
    pairs = JsonWordPairRepository().load_all()
    prompts = {word.text for pair in pairs for word in (pair.a, pair.b)}

    assert len(prompts) >= 1000
    assert all(pair.category and pair.a.text and pair.b.text for pair in pairs)


def test_same_prompt_can_be_paired_with_many_related_words():
    pairs = JsonWordPairRepository()._load_base_pairs()
    partners = {
        pair.b.text if pair.a.text == "김치찌개" else pair.a.text
        for pair in pairs
        if "김치찌개" in {pair.a.text, pair.b.text}
    }

    assert len(partners) >= 8
    assert {"된장찌개", "순두부찌개", "부대찌개"}.issubset(partners)


def test_start_assigns_hidden_words_and_random_description_order():
    game = started_game(4)
    fool_word_count = sum(word == game.fool_word.text for word in game.personal_words.values())

    assert fool_word_count == 1
    assert set(game.description_order) == {player.person_id for player in game.players}
    assert game.general_word.text not in game.status()
    assert game.fool_word.text not in game.status()
    assert "설명 순서" in game._start_message()


def test_player_count_cancel_and_maximum_rules():
    game = waiting_game(2)
    with pytest.raises(ValueError, match="최소 3명"):
        game.start(PAIR)
    game.cancel_join("user-2")
    assert len(game.players) == 1

    full_game = waiting_game(10)
    with pytest.raises(ValueError, match="최대 10명"):
        full_game.join("user-11", "참가자11")


def test_description_order_rejects_other_player_and_timeout_skips():
    game = started_game()
    actor = game.current_actor_person_id()
    other = next(player.person_id for player in game.players if player.person_id != actor)
    with pytest.raises(ValueError, match="현재 설명 차례"):
        game.submit_description(other, "설명")

    game.handle_timeout()
    assert game.descriptions[0]["skipped"] is True
    assert game.current_actor_person_id() != actor


def test_commands_are_rejected_after_each_phase_deadline():
    expired = datetime.now(timezone.utc) - timedelta(seconds=1)

    explaining = started_game()
    explaining.deadline_at = expired.isoformat()
    with pytest.raises(ValueError, match="제한시간"):
        explaining.submit_description(explaining.current_actor_person_id(), "늦은 설명")

    voting = started_game()
    finish_descriptions(voting)
    voting.deadline_at = expired.isoformat()
    with pytest.raises(ValueError, match="제한시간"):
        voting.submit_vote(voting.players[0].person_id, voting.players[1].person_id)

    answering = started_game()
    answering.phase = FoolLiarPhase.ANSWERING
    answering.deadline_at = expired.isoformat()
    with pytest.raises(ValueError, match="제한시간"):
        answering.submit_answer(answering.fool_person_id, answering.general_word.text)


def test_all_descriptions_move_to_private_vote_without_intermediate_counts():
    game = started_game()
    finish_descriptions(game)
    voter = game.players[0].person_id
    target = game.players[1].person_id
    message = game.submit_vote(voter, target)

    assert game.phase == FoolLiarPhase.VOTING
    assert len(game.descriptions) == len(game.players) * 2
    assert {item["round"] for item in game.descriptions} == {1, 2}
    assert "득표" not in message
    with pytest.raises(ValueError, match="자기 자신"):
        game.submit_vote(game.players[1].person_id, game.players[1].person_id)


def test_vote_tie_then_revote_tie_makes_fool_win():
    game = started_game()
    finish_descriptions(game)
    ids = [player.person_id for player in game.players]
    for index, voter in enumerate(ids):
        game.submit_vote(voter, ids[(index + 1) % len(ids)])
    assert game.phase == FoolLiarPhase.REVOTING

    for index, voter in enumerate(ids):
        game.submit_vote(voter, ids[(index + 1) % len(ids)])
    assert game.phase == FoolLiarPhase.FINISHED
    assert game.winner_person_ids == [game.fool_person_id]


def test_no_votes_before_timeout_makes_fool_win():
    game = started_game()
    finish_descriptions(game)
    game.handle_timeout()
    assert game.winner_person_ids == [game.fool_person_id]


def test_wrong_accusation_immediately_makes_fool_win():
    game = started_game()
    finish_descriptions(game)
    normal_id = next(player.person_id for player in game.players if player.person_id != game.fool_person_id)
    vote_for_unique_target(game, normal_id)
    assert game.winner_person_ids == [game.fool_person_id]
    assert game.normal_finished is True


def test_identified_fool_can_win_with_alias_ignoring_spacing_and_case():
    game = started_game()
    game.general_word = Word("Ice Cream", ("아이스크림",))
    finish_descriptions(game)
    vote_for_unique_target(game, game.fool_person_id)
    assert game.phase == FoolLiarPhase.ANSWERING

    game.submit_answer(game.fool_person_id, "  ICEcream ")
    assert game.answer_correct is True
    assert game.winner_person_ids == [game.fool_person_id]


def test_identified_fool_timeout_makes_normal_players_win():
    game = started_game()
    finish_descriptions(game)
    vote_for_unique_target(game, game.fool_person_id)
    game.handle_timeout()

    assert game.answer_correct is False
    assert set(game.winner_person_ids) == set(game._normal_player_ids())
    assert game.general_word.text in game.final_result_text()
    assert game.fool_word.text in game.final_result_text()


def test_state_round_trip_preserves_secret_phase_votes_and_deadline():
    game = started_game()
    game.submit_description(game.current_actor_person_id(), "첫 설명")
    restored = FoolLiarGame.from_dict(game.to_dict())

    assert restored.phase == game.phase
    assert restored.personal_words == game.personal_words
    assert restored.description_order == game.description_order
    assert restored.descriptions == game.descriptions
    assert restored.deadline_at == game.deadline_at


def test_stats_are_recorded_once_with_role_details(tmp_path):
    game = started_game()
    finish_descriptions(game)
    vote_for_unique_target(game, game.fool_person_id)
    game.submit_answer(game.fool_person_id, game.general_word.text)
    store = JsonStatsStore(str(tmp_path / "stats.json"))

    store.record_fool_liar_game(game)
    game.stats_recorded = False
    store.record_fool_liar_game(game)

    record = store.fool_liar_player_record_text(game.fool_person_id, "바보")
    assert "게임: 1회" in record
    assert "바보 역할: 1회" in record
    assert "정답 성공: 1회" in record
    assert "전체 게임 통합 랭킹" in store.overall_ranking_text()
    assert game._player_name(game.fool_person_id) in store.overall_ranking_text()


def test_cancelled_game_is_not_recorded_and_reset_is_game_specific(tmp_path):
    store = JsonStatsStore(str(tmp_path / "stats.json"))
    cancelled = started_game()
    cancelled.reset()
    store.record_fool_liar_game(cancelled)
    assert store.fool_liar_ranking_text() == "아직 저장된 바보 라이어게임 전적이 없습니다."

    finished = started_game()
    finish_descriptions(finished)
    vote_for_unique_target(finished, next(p.person_id for p in finished.players if p.person_id != finished.fool_person_id))
    store.record_fool_liar_game(finished)
    store.reset_fool_liar_ranking()
    assert store.fool_liar_ranking_text() == "아직 저장된 바보 라이어게임 전적이 없습니다."


def test_game_store_restores_fool_liar_room(tmp_path):
    store = JsonGameStore(str(tmp_path / "games.json"))
    game = started_game()
    store.save_all(
        {"room": game},
        room_game_types={"room": GameType.FOOL_LIAR},
    )
    restored = store.load_all()["room"]

    assert isinstance(restored, FoolLiarGame)
    assert restored.personal_words == game.personal_words
    assert store.load_game_types()["room"] == GameType.FOOL_LIAR


def test_platform_recruit_command_selects_only_fool_liar_game(monkeypatch, tmp_path):
    main_module.game = HoldemGame()
    main_module.room_games.clear()
    main_module.room_game_types.clear()
    main_module.latest_card_tokens.clear()
    monkeypatch.setattr(main_module, "save_room_games", lambda: None)
    monkeypatch.setattr(main_module, "stats_store", JsonStatsStore(str(tmp_path / "stats.json")))

    result = main_module._handle_game_selection_command("room", "@FSS 게임선택 바보라이어게임")
    service = main_module.get_bot_service("room")

    assert result["ok"] is True
    assert main_module.get_game_type_for_room("room") == GameType.FOOL_LIAR
    assert isinstance(main_module.get_game_for_room("room"), FoolLiarGame)
    assert isinstance(service, FoolLiarBotService)


def test_debug_room_game_selection_changes_the_actual_debug_game(monkeypatch):
    main_module.game = HoldemGame()
    monkeypatch.setattr(main_module, "save_room_games", lambda: None)

    result = main_module._handle_game_selection_command(
        main_module.DEBUG_ROOM_ID, "@FSS 게임선택 바보라이어게임"
    )

    assert result["ok"] is True
    assert isinstance(main_module.get_game_for_room(main_module.DEBUG_ROOM_ID), FoolLiarGame)
    assert main_module.get_game_type_for_room(main_module.DEBUG_ROOM_ID) == GameType.FOOL_LIAR


def test_start_dm_preflight_blocks_game_without_revealing_words():
    game = waiting_game()

    class FailedClient:
        def send_direct_message(self, person_id, markdown):
            if person_id == "user-2":
                raise RuntimeError("blocked")
            assert PAIR.a.text not in markdown
            assert PAIR.b.text not in markdown
            return {}

    result = main_module._preflight_start_direct_messages(FailedClient(), game, "@FSS 시작")

    assert result["ok"] is False
    assert game.phase == FoolLiarPhase.WAITING
    assert "참가자2" in result["message"]


def test_holdem_start_dm_preflight_blocks_game_when_a_player_is_unreachable():
    game = HoldemGame()
    game.join("user-1", "영현")
    game.join("user-2", "철수")

    class FailedClient:
        def send_direct_message(self, person_id, markdown):
            if person_id == "user-2":
                raise RuntimeError("blocked")
            return {}

    result = main_module._preflight_start_direct_messages(FailedClient(), game, "@FSS 시작")

    assert result["ok"] is False
    assert game.phase == GamePhase.WAITING
    assert "철수" in result["message"]


def test_holdem_actual_card_dm_failure_rolls_start_back(monkeypatch):
    game = HoldemGame()
    game.join("user-1", "영현")
    game.join("user-2", "철수")
    snapshot = game.to_dict()
    game.start()
    main_module.room_games["holdem-room"] = game
    main_module.room_game_types["holdem-room"] = GameType.HOLDEM
    monkeypatch.setattr(main_module, "save_room_games", lambda: None)

    class FailedClient:
        def send_direct_message(self, person_id, markdown):
            if person_id == "user-2":
                raise RuntimeError("blocked")
            return {}

        def send_room_card(self, room_id, markdown, card):
            return {}

    result = {
        "ok": True,
        "message": "started",
        "status": game.status(),
        "deal_private_cards": True,
        "_start_snapshot": snapshot,
    }

    main_module._send_webex_result(FailedClient(), "holdem-room", "user-1", result)

    assert result["ok"] is False
    assert main_module.get_game_for_room("holdem-room").phase == GamePhase.WAITING


def test_word_command_is_private_and_start_returns_only_dm_secrets():
    game = waiting_game()

    class FixedRepository:
        def choose(self):
            return PAIR

    service = FoolLiarBotService(game, CommandParser(), word_repository=FixedRepository())
    start = service.handle_text_command("user-1", "참가자1", "시작")
    word = service.handle_text_command("user-1", "참가자1", "제시어")

    assert start["ok"] is True
    assert game.general_word.text not in start["message"]
    assert game.fool_word.text not in start["message"]
    assert len(start["direct_messages"]) == len(game.players) + 1
    assert word["private"] is True
    assert word["silent_public"] is True
    assert "당신의 제시어" in word["message"]


def test_help_uses_standard_game_selection_command():
    service = FoolLiarBotService(waiting_game(), CommandParser())

    result = service.handle_text_command("user-1", "참가자1", "도움말")

    assert result["ok"] is True
    assert "@FSS 게임선택 바보라이어게임" in result["message"]


def test_fool_liar_reuses_holdem_name_cleanup_across_game_and_stats(tmp_path):
    game = FoolLiarGame()
    game.join("user-1", "기존 참가자 (구회사)")
    game.join("user-2", "참가자2（회사）")
    game.join("user-3", "참가자3 (회사)")
    store = JsonStatsStore(str(tmp_path / "stats.json"))

    class FixedRepository:
        def choose(self):
            return PAIR

    service = FoolLiarBotService(
        game,
        CommandParser(),
        stats_store=store,
        word_repository=FixedRepository(),
    )
    result = service.handle_text_command("user-1", "기존 참가자 (새회사)", "시작")

    assert result["ok"] is True
    assert [player.display_name for player in game.players] == [
        "기존 참가자",
        "참가자2",
        "참가자3",
    ]
    assert all("회사" not in item["message"] for item in result["direct_messages"])

    game.descriptions.append(
        {"person_id": "user-1", "display_name": "기존 참가자 (회사)", "text": "설명"}
    )
    service.handle_text_command("user-1", "기존 참가자 (회사)", "도움말")
    game.normal_finished = True
    game.winner_person_ids = ["user-1"]
    game.stats_recorded = False
    store.record_fool_liar_game(game)

    assert game.descriptions[0]["display_name"] == "기존 참가자"
    assert "기존 참가자 (" not in store.fool_liar_ranking_text()


def test_direct_message_failure_rolls_start_back_to_lobby():
    game = started_game()
    result = {
        "ok": True,
        "message": "start",
        "direct_messages": [{"person_id": "user-2", "message": "secret"}],
        "abort_on_dm_failure": True,
    }

    class FailedClient:
        def send_direct_message(self, person_id, markdown):
            raise RuntimeError("blocked")

    main_module._dispatch_direct_messages(FailedClient(), result, game)
    assert result["ok"] is False
    assert game.phase == FoolLiarPhase.WAITING
    assert "참가자2" in result["message"]


def test_answer_stage_public_text_does_not_reveal_role_or_words():
    game = started_game()
    finish_descriptions(game)
    message = None
    fool = game.fool_person_id
    fallback = next(player.person_id for player in game.players if player.person_id != fool)
    for player in game.players:
        message = game.submit_vote(player.person_id, fallback if player.person_id == fool else fool)

    assert game.phase == FoolLiarPhase.ANSWERING
    assert "바보" not in message
    assert game.general_word.text not in message
    assert game.fool_word.text not in message


def test_expired_restored_turn_is_processed_once(monkeypatch, tmp_path):
    game = started_game()
    game.deadline_at = (datetime.now(timezone.utc) - timedelta(seconds=1)).isoformat()
    main_module.room_games.clear()
    main_module.room_game_types.clear()
    main_module.turn_timers.clear()
    main_module.turn_timer_generations.clear()
    main_module.room_games["liar-room"] = FoolLiarGame.from_dict(game.to_dict())
    main_module.room_game_types["liar-room"] = GameType.FOOL_LIAR
    monkeypatch.setattr(main_module, "stats_store", JsonStatsStore(str(tmp_path / "stats.json")))
    monkeypatch.setattr(main_module, "save_room_games", lambda: None)

    class FakeTimer:
        instances = []
        def __init__(self, seconds, callback, args):
            self.callback, self.args, self.cancelled = callback, args, False
            self.daemon = False
            self.__class__.instances.append(self)
        def start(self):
            pass
        def cancel(self):
            self.cancelled = True
        def fire(self):
            self.callback(*self.args)

    class FakeWebexClient:
        def send_direct_message(self, person_id, markdown):
            return {}
        def send_room_card(self, markdown, card, room_id=None):
            return {}

    monkeypatch.setattr(main_module, "turn_timer_factory", FakeTimer)
    monkeypatch.setattr(main_module, "WebexClient", FakeWebexClient)
    main_module._refresh_turn_timer("liar-room")
    FakeTimer.instances[-1].fire()
    restored = main_module.get_game_for_room("liar-room")

    assert len(restored.descriptions) == 1
    FakeTimer.instances[0].fire()
    assert len(restored.descriptions) == 1
