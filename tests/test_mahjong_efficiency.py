import copy
import random

from app.games.mahjong_efficiency.card_builder import build_hand_card, build_result_card
from app.games.mahjong_efficiency.engine import (
    counts_from_tiles,
    evaluate_discards,
    seven_pairs_shanten,
    shanten,
    standard_shanten,
    thirteen_orphans_shanten,
)
from app.games.mahjong_efficiency.service import (
    MahjongEfficiencyService,
    MahjongSession,
    TileInstance,
)
from app.games.mahjong_efficiency.store import MahjongEfficiencyStore
from app.platforms.webex.event_handler import WebexEventHandler


COMPLETE_STANDARD = [0, 1, 2, 9, 10, 11, 18, 19, 20, 27, 27, 27, 31, 31]


class MemoryStore:
    def __init__(self, data=None):
        self.data = copy.deepcopy(data or {"sessions": {}, "records": {}})
        self.save_count = 0

    def load(self):
        return copy.deepcopy(self.data)

    def save(self, data):
        self.data = copy.deepcopy(data)
        self.save_count += 1


class FakeClient:
    def __init__(self):
        self.messages = []
        self.cards = []

    def send_room_message(self, room_id, markdown):
        self.messages.append((room_id, markdown))

    def send_room_card(self, room_id, markdown, card):
        self.cards.append((room_id, markdown, card))


def direct_message(text="패효율 시작", person_id="p1", room_id="direct-1"):
    return {
        "text": text,
        "personId": person_id,
        "roomId": room_id,
        "roomType": "direct",
    }


def action_for(session, tile=None, person_id=None, **changes):
    tile = tile or session.hand[0]
    inputs = {
        "action": "mahjong_discard",
        "game_id": session.game_id,
        "round_id": session.round_id,
        "state_version": session.state_version,
        "tile_instance_id": tile.instance_id,
    }
    inputs.update(changes)
    return {
        "personId": person_id or session.person_id,
        "roomId": session.room_id,
        "inputs": inputs,
    }


def test_three_supported_shanten_shapes_and_minimum_selection():
    chiitoi = [0, 0, 1, 1, 9, 9, 10, 10, 18, 18, 27, 27, 31, 31]
    kokushi = [0, 8, 9, 17, 18, 26, 27, 28, 29, 30, 31, 32, 33, 33]
    assert standard_shanten(COMPLETE_STANDARD) == -1
    assert seven_pairs_shanten(chiitoi) == -1
    assert thirteen_orphans_shanten(kokushi) == -1
    assert shanten(COMPLETE_STANDARD) == -1
    assert shanten(chiitoi) == -1
    assert shanten(kokushi) == -1


def test_ukeire_uses_actual_wall_counts_and_discard_information():
    hand = COMPLETE_STANDARD[:-1] + [5]
    wall = [0] * 34
    wall[31] = 1
    evaluated = evaluate_discards(hand, remaining_counts=wall).for_tile(5)
    assert evaluated.shanten == 0
    assert evaluated.ukeire == ((31, 1),)
    assert evaluated.ukeire_count == 1

    derived = evaluate_discards(hand, discards=[31, 31]).for_tile(5)
    # One 31 tile is in hand and two are discarded, so exactly one remains.
    assert dict(derived.ukeire)[31] == 1


def test_duplicate_discards_are_evaluated_once_and_best_ties_all_count_as_correct():
    evaluation = evaluate_discards(COMPLETE_STANDARD)
    assert len(evaluation.discards) == len(set(COMPLETE_STANDARD))
    assert len(evaluation.best_discards) >= 2
    for tile in evaluation.best_discards:
        selected = evaluation.for_tile(tile)
        assert selected.is_best is True
        assert selected.efficiency_loss == 0
        assert selected.ukeire_count == evaluation.highest_ukeire_count


def test_efficiency_loss_and_shanten_loss_are_separate_and_order_independent():
    evaluation = evaluate_discards(COMPLETE_STANDARD)
    same_shanten_wrong = next(item for item in evaluation.discards if not item.is_best)
    assert same_shanten_wrong.shanten == evaluation.best_shanten
    assert same_shanten_wrong.efficiency_loss > 0

    hand = [0, 0, 1, 1, 2, 2, 9, 9, 10, 10, 18, 18, 27, 31]
    worsened = next(item for item in evaluate_discards(hand).discards if item.shanten_loss > 0)
    assert worsened.is_best is False
    assert worsened.shanten_loss > 0

    forward = evaluate_discards(COMPLETE_STANDARD).best_discards
    reverse = evaluate_discards(list(reversed(COMPLETE_STANDARD))).best_discards
    assert forward == reverse


def test_direct_start_creates_legal_136_tile_session_and_group_is_rejected():
    store = MemoryStore()
    service = MahjongEfficiencyService(store=store, rng=random.Random(4))
    client = FakeClient()
    result = service.handle_command(client, direct_message())
    session = service.sessions["p1"]
    assert result["ok"] is True
    assert len(session.hand) == 14 and len(session.wall) == 122
    all_counts = counts_from_tiles([item.tile for item in session.hand + session.wall])
    assert all(value == 4 for value in all_counts)
    assert len({item.instance_id for item in session.hand + session.wall}) == 136
    game_id = session.game_id
    resumed = service.handle_command(client, direct_message("마작 시작"))
    assert resumed["resumed"] is True
    assert service.sessions["p1"].game_id == game_id

    group = direct_message(person_id="p2", room_id="group")
    group["roomType"] = "group"
    service.handle_command(client, group)
    assert "p2" not in service.sessions
    assert client.messages[-1][1] == "마작 패효율은 봇과의 개인채팅에서 이용해주세요."


def test_discard_draw_is_atomic_and_stale_duplicate_does_not_draw_twice():
    store = MemoryStore()
    service = MahjongEfficiencyService(store=store, rng=random.Random(7))
    client = FakeClient()
    service.handle_command(client, direct_message())
    session = service.sessions["p1"]
    original_action = action_for(session)
    result = service.handle_action(client, original_action)
    assert result["ok"] is True and result["completed"] is False
    assert len(session.hand) == 14 and len(session.wall) == 121
    assert len(session.discards) == 1
    assert session.round_id == 2 and session.state_version == 2

    before = (len(session.wall), len(session.discards), session.state_version)
    duplicate = service.handle_action(client, original_action)
    assert duplicate["ignored"] is True
    assert (len(session.wall), len(session.discards), session.state_version) == before


def test_action_owner_instance_and_state_are_server_validated():
    service = MahjongEfficiencyService(store=MemoryStore(), rng=random.Random(9))
    client = FakeClient()
    service.handle_command(client, direct_message())
    session = service.sessions["p1"]
    before = session.to_dict()
    intruder = service.handle_action(client, action_for(session, person_id="p2"))
    stale = service.handle_action(client, action_for(session, state_version=999))
    missing = service.handle_action(client, action_for(session, tile_instance_id="not-real"))
    assert intruder["ignored"] and stale["ignored"] and missing["ignored"]
    assert session.to_dict() == before


def test_tenpai_after_discard_completes_and_updates_personal_record():
    store = MemoryStore()
    service = MahjongEfficiencyService(store=store, rng=random.Random(1))
    wall_tiles = [tile for tile in range(34) for _ in range(4)]
    for tile in COMPLETE_STANDARD:
        wall_tiles.remove(tile)
    session = MahjongSession(
        "game", "p1", "direct-1", 1, 1,
        [TileInstance(f"h{i}", tile) for i, tile in enumerate(COMPLETE_STANDARD)],
        [TileInstance(f"w{i}", tile) for i, tile in enumerate(wall_tiles)],
        drawn_tile_instance_id="h13",
    )
    service.sessions["p1"] = session
    client = FakeClient()
    best_tile = evaluate_discards(COMPLETE_STANDARD, remaining_counts=counts_from_tiles(wall_tiles)).best_discards[0]
    selected = next(item for item in session.hand if item.tile == best_tile)
    result = service.handle_action(client, action_for(session, selected))
    assert result["completed"] is True
    assert "p1" not in service.sessions
    record = service.records["p1"]
    assert record["completed_games"] == 1
    assert record["total_discards"] == 1
    assert record["correct_discards"] == 1
    assert record["current_streak"] == record["best_streak"] == 1


def test_session_and_records_restore_after_restart():
    store = MemoryStore()
    first = MahjongEfficiencyService(store=store, rng=random.Random(3))
    first.handle_command(FakeClient(), direct_message())
    original = first.sessions["p1"].to_dict()
    second = MahjongEfficiencyService(store=store, rng=random.Random(3))
    assert second.sessions["p1"].to_dict() == original


def test_hand_card_has_two_rows_unique_instances_and_minimal_payload():
    service = MahjongEfficiencyService(store=MemoryStore(), rng=random.Random(2))
    client = FakeClient()
    service.handle_command(client, direct_message())
    session = service.sessions["p1"]
    card = build_hand_card(session)
    rows = [item for item in card["body"] if item.get("type") == "ColumnSet"]
    assert [len(row["columns"]) for row in rows] == [7, 8]
    payloads = []
    for row in rows:
        for column in row["columns"]:
            for item in column.get("items", []):
                if item.get("selectAction"):
                    payloads.append(item["selectAction"]["data"])
    assert len({payload["tile_instance_id"] for payload in payloads}) == 14
    assert all(set(payload) == {"action", "game_id", "round_id", "state_version", "tile_instance_id"} for payload in payloads)
    serialized = str(payloads)
    assert "hand" not in serialized and "ukeire" not in serialized and "person_id" not in serialized


def test_result_card_lists_every_best_discard():
    evaluation = evaluate_discards(COMPLETE_STANDARD)
    selected = evaluation.for_tile(evaluation.best_discards[0])
    card = build_result_card({
        "selected": selected,
        "best_discards": evaluation.best_discards,
        "highest_ukeire_count": evaluation.highest_ukeire_count,
        "round_id": 1,
        "drawn_tile": TileInstance("drawn", 31),
        "discarded_tile": TileInstance("discarded", selected.tile),
        "is_tsumogiri": False,
        "acquired_efficiency": selected.ukeire_count,
        "efficiency_loss": selected.efficiency_loss,
    })
    facts = card["body"][1]["facts"]
    displayed = next(item["value"] for item in facts if item["title"] == "최선 타패")
    assert len(displayed.split(", ")) == len(evaluation.best_discards)


def test_status_record_end_help_and_mention_normalization():
    service = MahjongEfficiencyService(store=MemoryStore(), rng=random.Random(5))
    client = FakeClient()
    assert service.is_command("@FSS   패효율   시작")
    service.handle_command(client, direct_message("@FSS   패효율   시작"))
    service.handle_command(client, direct_message("패효율 상태"))
    service.handle_command(client, direct_message("패효율 기록"))
    service.handle_command(client, direct_message("패효율 도움말"))
    service.handle_command(client, direct_message("패효율 종료"))
    assert "p1" not in service.sessions
    combined = "\n".join(message for _, message in client.messages)
    assert "패효율 진행 중" in combined
    assert "패효율 개인 기록" in combined
    assert "패효율 명령" in combined


def test_encrypted_atomic_store_round_trip(tmp_path):
    store = MahjongEfficiencyStore(tmp_path / "mahjong.json")
    payload = {"sessions": {}, "records": {"p1": {"completed_games": 2}}}
    store.save(payload)
    assert store.file_path.read_text(encoding="utf-8").startswith("FSS2.")
    assert store.load() == payload
    assert not list(tmp_path.glob("mahjong_efficiency_*.tmp"))


def test_webex_handler_routes_direct_command_and_uses_actual_action_person():
    service = MahjongEfficiencyService(store=MemoryStore(), rng=random.Random(11))
    client = FakeClient()

    class Gateway(FakeClient):
        def get_message(self, message_id):
            return {
                "id": message_id, "roomId": "direct-1", "personId": "p1",
                "text": "패효율 시작", "roomType": "direct",
            }

        def is_bot_message(self, message):
            return False

        def get_attachment_action(self, action_id):
            session = service.sessions["p1"]
            return action_for(session, person_id="intruder")

    gateway = Gateway()
    handler = WebexEventHandler.__new__(WebexEventHandler)
    handler.webex_client_factory = lambda: gateway
    handler.mahjong_efficiency_service = service
    handler.is_force_reset = lambda text: False
    handler.is_game_selection = lambda text: False
    handler.is_ranking_reset = lambda text: False

    started = handler.handle_message_locked({"data": {"id": "message-1"}})
    before = service.sessions["p1"].to_dict()
    clicked = handler.handle_attachment_locked({"data": {"id": "action-1"}})
    assert started["mahjong_efficiency"] is True
    assert clicked["ignored"] is True
    assert service.sessions["p1"].to_dict() == before


def test_initial_hand_separates_thirteen_base_tiles_and_one_drawn_tile():
    service = MahjongEfficiencyService(store=MemoryStore(), rng=random.Random(21))
    service.handle_command(FakeClient(), direct_message())
    session = service.sessions["p1"]
    assert len(session.base_hand) == 13
    assert session.drawn_tile is not None
    assert session.drawn_tile_instance_id in {item.instance_id for item in session.hand}
    assert session.drawn_tile not in session.base_hand


def test_discard_from_hand_absorbs_old_drawn_tile_and_tsumogiri_keeps_base_hand():
    service = MahjongEfficiencyService(store=MemoryStore(), rng=random.Random(22))
    client = FakeClient()
    service.handle_command(client, direct_message())
    session = service.sessions["p1"]
    old_drawn_id = session.drawn_tile_instance_id
    base_discard = session.base_hand[0]
    result = service.handle_action(client, action_for(session, base_discard))
    assert result["completed"] is False
    assert result["result"]["is_tsumogiri"] is False
    assert old_drawn_id in {item.instance_id for item in session.base_hand}

    service2 = MahjongEfficiencyService(store=MemoryStore(), rng=random.Random(23))
    client2 = FakeClient()
    service2.handle_command(client2, direct_message())
    session2 = service2.sessions["p1"]
    original_base_ids = {item.instance_id for item in session2.base_hand}
    old_drawn = session2.drawn_tile
    result2 = service2.handle_action(client2, action_for(session2, old_drawn))
    assert result2["completed"] is False
    assert result2["result"]["is_tsumogiri"] is True
    assert {item.instance_id for item in session2.base_hand} == original_base_ids


def test_result_preserves_that_round_draw_and_discard_after_next_draw():
    service = MahjongEfficiencyService(store=MemoryStore(), rng=random.Random(24))
    client = FakeClient()
    service.handle_command(client, direct_message())
    session = service.sessions["p1"]
    old_drawn = session.drawn_tile
    discarded = session.base_hand[0]
    result = service.handle_action(client, action_for(session, discarded))["result"]
    assert result["drawn_tile"].instance_id == old_drawn.instance_id
    assert result["discarded_tile"].instance_id == discarded.instance_id
    assert session.drawn_tile_instance_id != old_drawn.instance_id
    facts = client.cards[-2][2]["body"][1]["facts"]
    values = {item["title"]: item["value"] for item in facts}
    assert values["쯔모"]
    assert values["타패"]
    assert values["타패 방식"] == "손출"


def test_hand_card_separates_drawn_tile_and_shows_ordered_duplicate_discards():
    service = MahjongEfficiencyService(store=MemoryStore(), rng=random.Random(25))
    service.handle_command(FakeClient(), direct_message())
    session = service.sessions["p1"]
    session.discards = [
        {"instance_id": "d1", "tile": 0},
        {"instance_id": "d2", "tile": 0},
        {"instance_id": "d3", "tile": 17},
    ]
    card = build_hand_card(session)
    text = "\n".join(str(item.get("text", "")) for item in card["body"])
    assert "이번 쯔모:" in text
    assert "내 버림패: 1만 · 1만 · 9통" in text
    assert "쯔모" in str(card["body"][3])


def test_status_shows_base_hand_drawn_discard_shanten_and_history():
    service = MahjongEfficiencyService(store=MemoryStore(), rng=random.Random(26))
    client = FakeClient()
    service.handle_command(client, direct_message())
    session = service.sessions["p1"]
    service.handle_action(client, action_for(session, session.drawn_tile))
    service.handle_command(client, direct_message("패효율 상태"))
    status = client.messages[-1][1]
    assert "기본 손패:" in status
    assert "이번 쯔모:" in status
    assert "내 버림패:" in status
    assert "현재 샨텐:" in status
    assert "1순: 쯔모" in status


def test_efficiency_rate_uses_accumulated_tiles_not_accuracy():
    service = MahjongEfficiencyService(store=MemoryStore())
    selected = evaluate_discards(COMPLETE_STANDARD).discards[0]
    service._update_record("p1", selected, acquired=20, possible=25, turn_loss=5)
    service._update_record("p1", selected, acquired=10, possible=15, turn_loss=5)
    record = service.records["p1"]
    assert record["total_acquired_efficiency"] == 30
    assert record["total_possible_efficiency"] == 40
    text = service._record_text("p1")
    assert "효율 획득률: 75.0%" in text
    assert text.index("효율 획득률") < text.index("최선 타패")


def test_multiple_best_has_zero_loss_and_worsened_discard_acquires_zero():
    tied = evaluate_discards(COMPLETE_STANDARD)
    selected = tied.for_tile(tied.best_discards[-1])
    assert selected.is_best and selected.efficiency_loss == 0

    hand = [0, 0, 1, 1, 2, 2, 9, 9, 10, 10, 18, 18, 27, 31]
    wall_tiles = [tile for tile in range(34) for _ in range(4)]
    for tile in hand:
        wall_tiles.remove(tile)
    service = MahjongEfficiencyService(store=MemoryStore(), rng=random.Random(27))
    instances = [TileInstance(f"h{i}", tile) for i, tile in enumerate(hand)]
    session = MahjongSession(
        "game", "p1", "direct-1", 1, 1, instances,
        [TileInstance(f"w{i}", tile) for i, tile in enumerate(wall_tiles)],
        drawn_tile_instance_id=instances[-1].instance_id,
    )
    service.sessions["p1"] = session
    evaluation = evaluate_discards(hand, remaining_counts=counts_from_tiles(wall_tiles))
    worsened = next(item for item in evaluation.discards if item.shanten_loss > 0)
    physical = next(item for item in instances if item.tile == worsened.tile)
    result = service.handle_action(FakeClient(), action_for(session, physical))["result"]
    assert result["acquired_efficiency"] == 0
    assert result["efficiency_loss"] == result["highest_ukeire_count"]


def test_restart_preserves_drawn_tile_discards_history_and_efficiency_totals():
    store = MemoryStore()
    first = MahjongEfficiencyService(store=store, rng=random.Random(28))
    client = FakeClient()
    first.handle_command(client, direct_message())
    session = first.sessions["p1"]
    first.handle_action(client, action_for(session, session.drawn_tile))
    before = first.sessions["p1"].to_dict()
    second = MahjongEfficiencyService(store=store, rng=random.Random(28))
    restored = second.sessions["p1"].to_dict()
    assert restored["drawn_tile_instance_id"] == before["drawn_tile_instance_id"]
    assert restored["discards"] == before["discards"]
    assert restored["history"] == before["history"]
    assert restored["acquired_efficiency"] == before["acquired_efficiency"]
    assert restored["possible_efficiency"] == before["possible_efficiency"]


def test_legacy_session_without_drawn_id_is_safely_invalidated():
    old = MahjongEfficiencyService(store=MemoryStore(), rng=random.Random(29))
    old.handle_command(FakeClient(), direct_message())
    data = old.sessions["p1"].to_dict()
    data.pop("drawn_tile_instance_id")
    store = MemoryStore({"sessions": {"p1": data}, "records": {"p1": {"completed_games": 3}}})
    service = MahjongEfficiencyService(store=store)
    client = FakeClient()
    assert "p1" not in service.sessions
    service.handle_command(client, direct_message("패효율 상태"))
    assert client.messages[-1][1] == "저장 형식이 변경되어 진행 중이던 패효율 게임을 다시 시작해주세요."
    assert service.records["p1"]["completed_games"] == 3
