import copy
import random
from datetime import datetime, timedelta, timezone

import pytest

from app.games.mahjong_efficiency.battle_card_builder import (
    build_battle_final_card, build_battle_menu_card, build_battle_result_card,
    build_battle_round_card, build_battle_status_card,
)
from app.games.mahjong_efficiency.battle_service import (
    BATTLE_HELP, BattlePlayer, BattleRound, MahjongBattle, MahjongBattleService,
)
from app.games.mahjong_efficiency.engine import counts_from_tiles, evaluate_discards
from app.games.mahjong_efficiency.service import TileInstance
from app.services.display_name import normalize_display_name
from app.platforms.webex.event_handler import WebexEventHandler


TENPAI_HAND = [0, 1, 2, 9, 10, 11, 18, 19, 20, 27, 27, 27, 31, 31]
CONTINUING_HAND = [0, 1, 2, 3, 5, 8, 9, 10, 14, 18, 20, 27, 31, 33]


class MemoryStore:
    def __init__(self, data=None): self.data = copy.deepcopy(data or {"battles": {}, "records": {}})
    def load(self): return copy.deepcopy(self.data)
    def save(self, data): self.data = copy.deepcopy(data)


class Clock:
    def __init__(self): self.value = datetime(2026, 1, 1, tzinfo=timezone.utc)
    def __call__(self): return self.value
    def advance(self, seconds): self.value += timedelta(seconds=seconds)


class FakeTimer:
    instances = []
    def __init__(self, delay, callback):
        self.delay, self.callback, self.cancelled, self.started = delay, callback, False, False
        FakeTimer.instances.append(self)
    def start(self): self.started = True
    def cancel(self): self.cancelled = True
    def fire(self):
        if not self.cancelled: self.callback()


class Client:
    def __init__(self): self.messages, self.cards, self.direct = [], [], []
    def send_room_message(self, room_id, markdown): self.messages.append((room_id, markdown))
    def send_room_card(self, room_id, markdown, card): self.cards.append((room_id, markdown, card))
    def send_direct_message(self, person_id, markdown): self.direct.append((person_id, markdown))


def message(command, person="p1", name="방장", room_type="group", room="room"):
    return {"text": command, "personId": person, "personDisplayName": name, "roomType": room_type, "roomId": room}


def service(store=None, clock=None, client=None, admins=()):
    FakeTimer.instances.clear(); client = client or Client()
    return MahjongBattleService(
        store=store or MemoryStore(), rng=random.Random(4), clock=clock or Clock(),
        timer_factory=FakeTimer, webex_client_factory=lambda: client,
        is_force_reset_admin=lambda person_id: person_id in admins,
    ), client


def fixed_round(tiles=CONTINUING_HAND, draws=(4, 6, 7, 11, 12, 13, 15, 16, 17, 21, 22, 23)):
    hand = [TileInstance(f"h{index}", tile) for index, tile in enumerate(tiles)]
    remaining = [tile for tile in range(34) for _ in range(4)]
    for tile in tiles: remaining.remove(tile)
    wall = []
    for index, tile in enumerate(draws):
        if tile in remaining:
            remaining.remove(tile); wall.append(TileInstance(f"w{index}", tile))
    wall.extend(TileInstance(f"r{index}", tile) for index, tile in enumerate(remaining))
    counts = list(counts_from_tiles(item.tile for item in wall))
    return BattleRound(
        hand, counts, evaluate_discards(tiles, remaining_counts=counts), wall=wall,
        drawn_tile_instance_id=hand[-1].instance_id,
    )


def active_game(tiles=CONTINUING_HAND):
    game, client = service(); game._generate_round = lambda: fixed_round(tiles)
    game.handle_command(client, message("패효율 대결 생성", name="방장 (회사)"))
    game.handle_command(client, message("패효율 대결 참가", "p2", "참가자(팀)"))
    game.handle_command(client, message("패효율 대결 시작"))
    return game, client, game.battles["room"]


def physical_for(battle, tile_type):
    return next(item for item in battle.current_round.hand if item.tile == tile_type)


def action(battle, person, tile):
    return {"roomId": battle.room_id, "personId": person, "inputs": {
        "action": "mahjong_battle_discard", "battle_id": battle.battle_id,
        "turn_no": battle.turn_no, "state_version": battle.state_version,
        "tile_instance_id": tile.instance_id,
    }}


def card_text(card): return "\n".join(str(item.get("text", "")) for item in card["body"])


def command_context(battle):
    return {
        "room_id": battle.room_id if battle else "room",
        "battle_id": battle.battle_id if battle else "",
        "state_version": battle.state_version if battle else 0,
    }


def expire_answer(game):
    game.clock.advance(10); FakeTimer.instances[-1].fire()


def expire_result(game):
    game.clock.advance(10); FakeTimer.instances[-1].fire()


def test_initial_state_is_one_legal_wall_with_thirteen_base_and_one_draw():
    game, client = service(); game.handle_command(client, message("패효율 대결 생성")); game.handle_command(client, message("패효율 대결 참가", "p2", "B")); battle = game.battles["room"]
    game.handle_command(client, message("패효율 대결 시작"))
    state = battle.current_round
    assert len(state.base_hand) == 13 and state.drawn_tile in state.hand
    assert len(state.hand) == 14 and len(state.wall) == 122
    assert len({item.instance_id for item in [*state.hand, *state.wall]}) == 136
    assert battle.round_id == 1 and battle.turn_no == 1


def test_round_card_separates_draw_and_all_tiles_are_clickable_for_same_common_hand():
    game, client, battle = active_game(); card = build_battle_round_card(battle)
    rows = [item for item in card["body"] if item.get("type") == "ColumnSet"]
    assert [len(row["columns"]) for row in rows] == [7, 6, 1]
    payloads = [c["items"][0]["selectAction"]["data"] for row in rows for c in row["columns"]]
    assert len(payloads) == 14 and {p["tile_instance_id"] for p in payloads} == {t.instance_id for t in battle.current_round.hand}
    assert all(set(p) == {"action", "battle_id", "turn_no", "state_version", "tile_instance_id"} for p in payloads)
    assert "기본 손패" in card_text(card) and "이번 쯔모" in card_text(card)


def test_hand_discard_absorbs_previous_draw_and_draws_one_from_same_wall():
    game, client, battle = active_game(); state = battle.current_round
    old_wall_ids = [item.instance_id for item in state.wall]
    old_draw = state.drawn_tile; best = next(tile for tile in state.evaluation.best_discards if tile != old_draw.tile)
    discarded = physical_for(battle, best)
    game.handle_action(client, action(battle, "p1", discarded))
    assert battle.phase == "ANSWERING" and battle.turn_no == 1
    expire_answer(game); assert battle.phase == "RESULT" and battle.turn_no == 1
    expire_result(game)
    assert battle.status == "active" and battle.turn_no == 2 and battle.round_id == 1
    assert old_draw.instance_id in {item.instance_id for item in battle.current_round.base_hand}
    assert discarded.instance_id not in {item.instance_id for item in battle.current_round.hand}
    assert battle.current_round.drawn_tile.instance_id == old_wall_ids[-1]
    assert len(battle.current_round.wall) == len(old_wall_ids) - 1


def test_tsumogiri_keeps_exact_base_hand_and_first_correct_sets_common_discard():
    game, client, battle = active_game(); state = battle.current_round
    base_ids = {item.instance_id for item in state.base_hand}
    assert state.drawn_tile.tile in state.evaluation.best_discards
    game.handle_action(client, action(battle, "p1", state.drawn_tile))
    expire_answer(game)
    assert {item.instance_id for item in battle.current_round.base_hand} == base_ids
    result = battle.completed_rounds[-1]
    assert result["common_discard"] == state.drawn_tile.tile and result["is_tsumogiri"]
    assert battle.player("p1").wins == 1 and battle.player("p1").score == 10


def test_all_wrong_or_timeout_uses_first_sorted_best_not_wrong_discard():
    game, client, battle = active_game(); state = battle.current_round
    wrong = next(item for item in state.evaluation.discards if not item.is_best)
    wrong_physical = physical_for(battle, wrong.tile); expected = state.evaluation.best_discards[0]
    game.handle_action(client, action(battle, "p1", wrong_physical))
    game.handle_action(client, action(battle, "p2", wrong_physical))
    assert not battle.completed_rounds
    expire_answer(game)
    assert battle.completed_rounds[-1]["common_discard"] == expected != wrong.tile
    assert wrong_physical.instance_id in {item.instance_id for item in battle.current_round.base_hand}


def test_all_submissions_wait_for_deadline_and_multiple_correct_players_all_score():
    game, client, battle = active_game(); bests = battle.current_round.evaluation.best_discards
    first = physical_for(battle, bests[0]); second = physical_for(battle, bests[-1])
    game.handle_action(client, action(battle, "p1", first))
    game.handle_action(client, action(battle, "p2", second))
    assert battle.phase == "ANSWERING" and not battle.completed_rounds
    assert battle.player("p1").score == battle.player("p2").score == 0
    expire_answer(game)
    assert battle.phase == "RESULT"
    assert battle.player("p1").score == battle.player("p2").score == 10
    assert battle.player("p1").wins == battle.player("p2").wins == 1
    assert battle.player("p1").best_discards == battle.player("p2").best_discards == 1
    assert battle.completed_rounds[-1]["common_discard"] == min(first.tile, second.tile)


def test_result_phase_lasts_ten_seconds_and_rejects_problem_card_silently():
    game, client, battle = active_game(); old = action(battle, "p1", battle.current_round.hand[0])
    expire_answer(game)
    assert battle.phase == "RESULT" and FakeTimer.instances[-1].delay == 10
    messages = len(client.messages); cards = len(client.cards)
    ignored = game.handle_action(client, old)
    assert ignored["ignored"] and len(client.messages) == messages and len(client.cards) == cards
    game.clock.advance(9); FakeTimer.instances[-1].fire()
    assert battle.phase == "RESULT"
    game.clock.advance(1); FakeTimer.instances[-1].fire()
    assert battle.phase == "ANSWERING" and battle.turn_no == 2


def test_tenpai_finishes_before_drawing_and_records_one_battle():
    game, client, battle = active_game(TENPAI_HAND); state = battle.current_round
    wall_count = len(state.wall); best = state.evaluation.best_discards[0]
    game.handle_action(client, action(battle, "p1", physical_for(battle, best)))
    expire_answer(game)
    assert battle.status == "finished" and len(state.wall) == wall_count
    assert battle.turn_no == 1 and battle.round_id == 1
    assert game.records["p1"]["completed_battles"] == 1
    result_card, final_card = client.cards[-2][2], client.cards[-1][2]
    assert "다음 쯔모" not in card_text(result_card)
    assert all(word in card_text(final_card) for word in ("최종 13장 손패", "최종 대기패", "최종 순위", "참가자"))


def test_no_fixed_ten_turn_limit_and_every_turn_has_new_deadline(monkeypatch):
    game, client, battle = active_game(); monkeypatch.setattr("app.games.mahjong_efficiency.battle_service.shanten", lambda tiles: 1)
    first_battle_id = battle.battle_id
    for expected_turn in range(2, 12):
        old_timer = FakeTimer.instances[-1]; old_deadline = battle.round_deadline_at
        best = battle.current_round.evaluation.best_discards[0]
        game.handle_action(client, action(battle, "p1", physical_for(battle, best)))
        expire_answer(game); assert battle.phase == "RESULT"
        expire_result(game)
        assert battle.status == "active" and battle.turn_no == expected_turn
        assert battle.battle_id == first_battle_id and battle.round_id == 1
        assert old_timer.cancelled and battle.round_deadline_at != old_deadline
        assert datetime.fromisoformat(battle.round_deadline_at) - game.clock() == timedelta(seconds=10)
    assert battle.turn_no == 11


def test_stale_click_and_old_timer_cannot_affect_next_turn():
    clock = Clock(); game, client = service(clock=clock); game._generate_round = fixed_round
    game.handle_command(client, message("패효율 대결 생성")); game.handle_command(client, message("패효율 대결 참가", "p2", "B")); game.handle_command(client, message("패효율 대결 시작")); battle = game.battles["room"]
    old = action(battle, "p2", battle.current_round.hand[0]); timer = FakeTimer.instances[-1]
    game.handle_action(client, action(battle, "p1", physical_for(battle, battle.current_round.evaluation.best_discards[0])))
    clock.advance(10); timer.fire(); assert battle.phase == "RESULT"
    current_turn = battle.turn_no; timer.callback()
    assert battle.turn_no == current_turn
    assert game.handle_action(client, old)["ignored"] is True


def test_lobby_status_result_and_final_cards_include_normalized_participants():
    game, client, battle = active_game(TENPAI_HAND)
    lobby = build_battle_menu_card(battle); status = build_battle_status_card(battle, game.clock())
    game.handle_action(client, action(battle, "p1", physical_for(battle, battle.current_round.evaluation.best_discards[0])))
    result, final = client.cards[-2][2], client.cards[-1][2]
    for card in (lobby, status, result, final):
        assert "참가자" in card_text(card) and "방장" in card_text(card) and "참가자" in card_text(card)
        assert "(회사)" not in card_text(card) and "(팀)" not in card_text(card)


@pytest.mark.parametrize("raw, expected", [
    ("이상현 (롯데쇼핑)", "이상현"), ("김철수(IT운영팀)", "김철수"),
    ("박영희 (외부) (게스트)", "박영희"), ("김(별명)철수", "김(별명)철수"),
])
def test_normalize_display_name_only_removes_trailing_groups(raw, expected):
    assert normalize_display_name(raw) == expected


def test_name_cleanup_does_not_change_person_id_host_permissions():
    game, client = service(); game.handle_command(client, message("패효율 대결 생성", "p1", "방장 (회사)")); battle = game.battles["room"]
    assert battle.players[0].display_name == "방장" and battle.host_person_id == "p1"
    game.handle_command(client, message("패효율 대결 종료", "p2", "방장"))
    assert battle.status == "lobby" and "방장 또는 강제리셋" in client.messages[-1][1]


def test_force_reset_admin_can_end_active_battle():
    game, client, battle = active_game()
    game.is_force_reset_admin = lambda person_id: person_id == "admin"
    game.handle_command(client, message("패효율 대결 종료", "admin", "관리자"))
    assert battle.status == "ended"
    assert client.cards[-1][1] == "관리자가 패효율 대결을 강제 종료했습니다."


def test_orphaned_lobby_participant_can_end_when_host_missing():
    game, client = service()
    game.handle_command(client, message("패효율 대결 생성", "host", "방장"))
    game.handle_command(client, message("패효율 대결 참가", "p2", "참가자"))
    battle = game.battles["room"]
    battle.host_person_id = ""
    game.handle_command(client, message("패효율 대결 종료", "p2", "참가자"))
    assert battle.status == "ended"


def test_clear_room_removes_persisted_battle():
    store = MemoryStore()
    game, client = service(store=store)
    game.handle_command(client, message("패효율 대결 생성"))
    assert "room" in store.data["battles"]
    assert game.clear_room("room") is True
    assert "room" not in game.battles
    assert "room" not in store.data["battles"]
    restored, _ = service(store=store)
    assert "room" not in restored.battles


def test_host_end_button_appears_on_lobby_and_active_menu():
    game, client = service()
    game.handle_command(client, message("패효율 대결 생성"))
    battle = game.battles["room"]
    lobby_titles = [action["title"] for action in build_battle_menu_card(battle, "p1")["actions"]]
    assert "대결 종료" in lobby_titles
    game.handle_command(client, message("패효율 대결 참가", "p2", "참가자"))
    game._generate_round = fixed_round
    game.handle_command(client, message("패효율 대결 시작"))
    active_host = [action["title"] for action in build_battle_menu_card(battle, "p1")["actions"]]
    active_guest = [action["title"] for action in build_battle_menu_card(battle, "p2")["actions"]]
    admin_titles = [
        action["title"]
        for action in build_battle_menu_card(battle, "admin", can_force_reset=True)["actions"]
    ]
    assert "대결 종료" in active_host
    assert "대결 종료" not in active_guest
    assert "강제 종료" in admin_titles



def test_participant_can_cancel_join_from_lobby_and_menu_has_button():
    game, client = service()
    game.handle_command(client, message("패효율 대결 생성"))
    game.handle_command(client, message("패효율 대결 참가", "p2", "참가자"))
    battle = game.battles["room"]
    assert "참가 취소" in [action["title"] for action in build_battle_menu_card(battle)["actions"]]

    game.handle_command(client, message("패효율 대결 참가 취소", "p2", "참가자"))

    assert battle.player("p2") is None
    assert "참가를 취소했습니다" in client.cards[-1][1]


def test_host_cannot_cancel_join_and_end_returns_status_card():
    game, client = service()
    game.handle_command(client, message("패효율 대결 생성"))
    battle = game.battles["room"]

    game.handle_command(client, message("패효율 대결 참가 취소"))
    assert battle.player("p1") is not None
    assert "대결 종료" in client.messages[-1][1]

    game.handle_command(client, message("패효율 대결 종료"))
    assert battle.status == "ended"
    assert client.cards[-1][1] == "방장이 패효율 대결을 종료했습니다."
    assert "진행 중인 패효율 대결이 없습니다." in card_text(client.cards[-1][2])


def test_restart_restores_exact_hand_draw_wall_turn_and_remaining_timer():
    store = MemoryStore(); clock = Clock(); game, client = service(store=store, clock=clock); game._generate_round = fixed_round
    game.handle_command(client, message("패효율 대결 생성")); game.handle_command(client, message("패효율 대결 참가", "p2", "B")); game.handle_command(client, message("패효율 대결 시작")); battle = game.battles["room"]
    snapshot = ([x.instance_id for x in battle.current_round.hand], battle.current_round.drawn_tile_instance_id, [x.instance_id for x in battle.current_round.wall], battle.turn_no)
    clock.advance(4); restored, _ = service(store=store, clock=clock); restored.restore_timers(); state = restored.battles["room"].current_round
    assert snapshot == ([x.instance_id for x in state.hand], state.drawn_tile_instance_id, [x.instance_id for x in state.wall], restored.battles["room"].turn_no)
    assert 5.9 <= FakeTimer.instances[-1].delay <= 6.0


def test_restart_restores_result_phase_and_starts_next_turn_once():
    store = MemoryStore(); clock = Clock(); game, client = service(store=store, clock=clock); game._generate_round = fixed_round
    game.handle_command(client, message("패효율 대결")); game.handle_command(client, message("패효율 대결 참가", "p2", "B")); game.handle_command(client, message("패효율 대결 시작"))
    expire_answer(game); assert game.battles["room"].phase == "RESULT"
    clock.advance(4); restored, _ = service(store=store, clock=clock); restored.restore_timers()
    battle = restored.battles["room"]
    assert battle.phase == "RESULT" and 5.9 <= FakeTimer.instances[-1].delay <= 6.0
    clock.advance(6); FakeTimer.instances[-1].fire()
    assert battle.phase == "ANSWERING" and battle.turn_no == 2
    current = battle.turn_no; FakeTimer.instances[-2].callback()
    assert battle.turn_no == current


def test_legacy_active_battle_is_invalidated_but_records_are_preserved():
    game, client, battle = active_game(); data = game.store.data
    del data["battles"]["room"]["current_round"]["drawn_tile_instance_id"]
    data["records"] = {"p1": {"completed_battles": 3}}
    restored, restored_client = service(store=MemoryStore(data))
    assert "room" not in restored.battles and restored.records["p1"]["completed_battles"] == 3
    restored.handle_command(restored_client, message("패효율 대결 상태"))
    assert "진행 방식이 변경" in restored_client.messages[-1][1]


def test_direct_entry_creates_lobby_without_create_button_and_replay_resets_game():
    game, client = service(); game.handle_command(client, message("패효율 대결", name="방장 (회사)")); battle = game.battles["room"]
    assert battle.status == "lobby" and battle.host_person_id == "p1"
    assert "대결 생성" not in {item["title"] for item in client.cards[-1][2]["actions"]}
    game.handle_command(client, message("패효율 대결 참가", "p2", "B")); game._generate_round = lambda: fixed_round(TENPAI_HAND); game.handle_command(client, message("패효율 대결 시작"))
    game.handle_action(client, action(battle, "p1", physical_for(battle, battle.current_round.evaluation.best_discards[0]))); expire_answer(game)
    old_id = battle.battle_id; final_actions = {item["title"] for item in client.cards[-1][2]["actions"]}
    assert final_actions == {"다시 하기", "메인 메뉴"}
    game.handle_command(client, message("패효율 대결 다시 하기"))
    assert battle.status == "lobby" and battle.phase == "WAITING" and battle.battle_id != old_id
    assert battle.current_round is None and not battle.completed_rounds
    assert all(p.score == p.responses == p.best_discards == 0 for p in battle.players)


def test_status_card_has_contextual_lobby_actions_and_validates_button_context():
    game, client = service()
    game.handle_command(client, message("패효율 대결 상태", "p2", "참가자"))
    empty_card = client.cards[-1][2]
    assert {item["title"] for item in empty_card["actions"]} == {"참가", "상태", "도움말", "메인 메뉴"}

    game.handle_command(client, message("패효율 대결 참가", "p1", "방장") | {
        "actionContext": command_context(None),
    })
    battle = game.battles["room"]
    host_card = build_battle_status_card(battle, game.clock(), "p1")
    guest_card = build_battle_status_card(battle, game.clock(), "p2")
    assert "시작" in {item["title"] for item in host_card["actions"]}
    assert "참가" not in {item["title"] for item in host_card["actions"]}
    assert "참가" in {item["title"] for item in guest_card["actions"]}

    stale = command_context(battle)
    game.handle_command(client, message("패효율 대결 참가", "p2", "참가자") | {"actionContext": stale})
    assert battle.player("p2") is not None
    duplicate = game.handle_command(client, message("패효율 대결 참가", "p3", "중복") | {"actionContext": stale})
    assert duplicate["ignored"] and battle.player("p3") is None


def test_text_and_button_start_share_permissions_and_service_logic():
    game, client = service()
    game.handle_command(client, message("패효율 대결", "p1", "방장"))
    game.handle_command(client, message("패효율 대결 참가", "p2", "참가자"))
    battle = game.battles["room"]
    before = command_context(battle)
    game.handle_command(client, message("패효율 대결 시작", "p2", "참가자") | {"actionContext": before})
    assert battle.status == "lobby" and "방장만" in client.messages[-1][1]
    game._generate_round = fixed_round
    game.handle_command(client, message("패효율 대결 시작", "p1", "방장") | {"actionContext": before})
    assert battle.status == "active"


def test_authorized_host_eviction_promotes_first_joined_and_persists():
    store = MemoryStore(); game, client = service(store=store, admins={"admin"})
    game.handle_command(client, message("패효율 대결", "host", "기존 방장"))
    game.handle_command(client, message("패효율 대결 참가", "next", "다음 참가자"))
    game.handle_command(client, message("패효율 대결 참가", "later", "후순위"))
    battle = game.battles["room"]
    context = command_context(battle)
    game.handle_command(client, message("패효율 대결 방장 강퇴", "admin", "관리자") | {"actionContext": context})
    assert battle.player("host") is None and battle.host_person_id == "next"
    restored, _ = service(store=store, admins={"admin"})
    assert restored.battles["room"].host_person_id == "next"
    assert "방장 강퇴" in {item["title"] for item in build_battle_status_card(battle, game.clock(), "admin", True)["actions"]}
    assert "방장 강퇴" not in {item["title"] for item in build_battle_status_card(battle, game.clock(), "later", False)["actions"]}


def test_host_eviction_rejects_unauthorized_active_other_room_and_duplicate():
    game, client = service(admins={"admin"})
    game.handle_command(client, message("패효율 대결", "host", "방장", room="room"))
    battle = game.battles["room"]
    context = command_context(battle)
    game.handle_command(client, message("패효율 대결 방장 강퇴", "user", "일반", room="room") | {"actionContext": context})
    assert battle.host_person_id == "host"
    game.handle_command(client, message("패효율 대결", "other-host", "다른 방장", room="other"))
    game.handle_command(client, message("패효율 대결 방장 강퇴", "admin", "관리자", room="room") | {"actionContext": context})
    assert battle.host_person_id == "" and game.battles["other"].host_person_id == "other-host"
    duplicate = game.handle_command(client, message("패효율 대결 방장 강퇴", "admin", "관리자", room="room") | {"actionContext": context})
    assert duplicate["ignored"] and battle.players == []

    active, active_client = service(admins={"admin"})
    active._generate_round = fixed_round
    active.handle_command(active_client, message("패효율 대결", "host", "방장"))
    active.handle_command(active_client, message("패효율 대결 참가", "p2", "참가자"))
    active.handle_command(active_client, message("패효율 대결 시작", "host", "방장"))
    running = active.battles["room"]
    active.handle_command(active_client, message("패효율 대결 방장 강퇴", "admin", "관리자"))
    assert running.status == "active" and running.host_person_id == "host"


def test_evicting_only_host_leaves_empty_host_and_admin_host_can_evict_self():
    game, client = service(admins={"host"})
    game.handle_command(client, message("패효율 대결", "host", "방장"))
    battle = game.battles["room"]
    game.handle_command(client, message("패효율 대결 방장 강퇴", "host", "방장"))
    assert battle.players == [] and battle.host_person_id == ""


def test_help_describes_single_continuous_battle_and_no_ten_round_wording():
    assert "10라운드" not in BATTLE_HELP and "한 판만" in BATTLE_HELP
    assert all(text in BATTLE_HELP for text in ("텐파이", "순당 10초", "+10점", "샨텐 악화"))


def test_general_status_shows_game_selector_then_battle_status_without_starting_holdem():
    game, _ = service()

    class Gateway(Client):
        def get_message(self, message_id): return message("@FSS 상태") | {"id": message_id}
        def is_bot_message(self, value): return False
        def get_attachment_action(self, action_id):
            return {"roomId": "room", "personId": "p1", "inputs": {"action": "game_status_selection", "command": "패효율 대결 상태"}}
        def get_room(self, room_id): return {"id": room_id, "type": "group"}
        def get_person(self, person_id): return {"id": person_id, "displayName": "방장"}
        def display_name_from_person(self, person, fallback): return person.get("displayName", fallback)

    gateway = Gateway(); handler = WebexEventHandler.__new__(WebexEventHandler)
    handler.webex_client_factory = lambda: gateway; handler.mahjong_battle_service = game
    handler.mahjong_efficiency_service = None
    result = handler.handle_message_locked({"data": {"id": "message-id", "roomId": "room"}})
    assert result["status_selection"] and "FSS 게임 선택" in card_text(gateway.cards[-1][2])
    assert "room" not in game.battles
    selected = handler.handle_attachment_locked({"data": {"id": "action-id", "roomId": "room"}})
    assert selected["mahjong_battle"] and "패효율 대결 상태" in card_text(gateway.cards[-1][2])
