from fastapi.testclient import TestClient

import app.main as main_module
from app.domain.game import HoldemGame
from app.games.sword_upgrade.domain.game import SwordUpgradeGame
from app.games.sword_upgrade.domain.raid import RaidPhase, resolve_attack_dice
from app.main import app


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


def select_and_seed(room: str, players: list[tuple[str, str, int]], monkeypatch):
    reset_platform(monkeypatch)
    command(room, players[0][0], players[0][1], "게임선택 검키우기")
    game = main_module.get_game_for_room(room)
    assert isinstance(game, SwordUpgradeGame)
    for person_id, name, level in players:
        sword = game.ensure_sword(person_id, name)
        sword.level = level
    return game


def test_resolve_attack_miss_critical_and_doubles(monkeypatch):
    rolls = iter([1, 1, 4, 5])  # doubles 1+1, then bonus 4+5, first_sum=2 miss
    monkeypatch.setattr(
        "app.games.sword_upgrade.domain.raid.random.randint",
        lambda a, b: next(rolls),
    )
    miss = resolve_attack_dice(3)
    assert miss.damage == 0
    assert miss.note == "미스"
    assert miss.dice == [1, 1, 4, 5]

    rolls = iter([6, 5])  # sum 11 crit
    monkeypatch.setattr(
        "app.games.sword_upgrade.domain.raid.random.randint",
        lambda a, b: next(rolls),
    )
    crit = resolve_attack_dice(2)
    assert crit.note == "크리티컬"
    assert crit.damage == (2 + 1) * 11 * 2


def test_raid_invite_dm_and_boss_spawn_after_all_respond(monkeypatch):
    room = "raid-room"
    game = select_and_seed(
        room,
        [("u1", "상현", 2), ("u2", "철수", 1), ("u3", "영희", 3)],
        monkeypatch,
    )
    monkeypatch.setattr(
        "app.games.sword_upgrade.domain.raid.random.randint",
        lambda a, b: 50 if a != 1 or b != 6 else 50,
    )

    started = command(room, "u1", "상현", "보스레이드").json()
    assert started["ok"] is True
    assert "초대 DM" in started["message"]
    assert len(started["direct_messages"]) == 2
    assert all("card" in item for item in started["direct_messages"])
    assert game.raid is not None
    assert game.raid.phase == RaidPhase.INVITING
    assert game.raid.invites["u1"].response == "accepted"

    blocked = command(room, "u1", "상현", "강화").json()
    assert blocked["ok"] is False
    assert "레이드" in blocked["message"]

    change = command(room, "u1", "상현", "게임선택 홀덤").json()
    assert change["ok"] is False

    command(room, "u2", "철수", "레이드수락")
    finished = command(room, "u3", "영희", "레이드거부").json()
    assert finished["ok"] is True
    assert "보스 등장" in finished["message"]
    assert game.raid.phase == RaidPhase.BATTLING
    assert game.raid.boss_hp == 50
    assert len(game.raid.accepted()) == 2


def test_raid_attacks_resolve_clear_or_fail(monkeypatch):
    room = "raid-battle"
    game = select_and_seed(
        room,
        [("u1", "상현", 4), ("u2", "철수", 4), ("u3", "영희", 4)],
        monkeypatch,
    )

    # Force predictable boss hp and dice: always 6,6 then no need more for non-double wait 6+5
    values = iter([40, 6, 5, 6, 5, 6, 5])  # hp then three attacks of 11

    def fake_randint(a, b):
        return next(values)

    monkeypatch.setattr(
        "app.games.sword_upgrade.domain.raid.random.randint",
        fake_randint,
    )

    command(room, "u1", "상현", "보스레이드")
    command(room, "u2", "철수", "레이드수락")
    command(room, "u3", "영희", "레이드수락")
    assert game.raid.boss_hp == 40

    command(room, "u1", "상현", "공격")
    command(room, "u2", "철수", "공격")
    result = command(room, "u3", "영희", "공격").json()
    assert result["ok"] is True
    assert "레이드 결과" in result["message"]
    assert "클리어" in result["message"]
    assert "+1강" in result["message"]
    assert game.raid is None
    assert game.swords["u1"].level == 5
    assert game.swords["u2"].level == 5
    assert game.swords["u3"].level == 5


def test_raid_fail_when_damage_too_low(monkeypatch):
    room = "raid-fail"
    game = select_and_seed(
        room,
        [("u1", "상현", 2), ("u2", "철수", 1), ("u3", "영희", 0)],
        monkeypatch,
    )
    values = iter([200, 2, 1, 2, 1, 2, 1])  # high hp, miss rolls

    monkeypatch.setattr(
        "app.games.sword_upgrade.domain.raid.random.randint",
        lambda a, b: next(values),
    )
    command(room, "u1", "상현", "보스레이드")
    command(room, "u2", "철수", "레이드수락")
    command(room, "u3", "영희", "레이드수락")
    command(room, "u1", "상현", "공격")
    command(room, "u2", "철수", "공격")
    result = command(room, "u3", "영희", "공격").json()
    assert "실패" in result["message"]
    assert "-1강" in result["message"]
    assert game.raid is None
    assert game.swords["u1"].level == 1
    assert game.swords["u2"].level == 0
    assert game.swords["u3"].level == 0  # already 0, stays 0


def test_force_start_raid_keeps_current_sword_levels(monkeypatch):
    room = "raid-force"
    game = select_and_seed(
        room,
        [("u1", "상현", 5), ("u2", "철수", 7), ("u3", "영희", 2)],
        monkeypatch,
    )
    monkeypatch.setattr(
        "app.games.sword_upgrade.domain.raid.random.randint",
        lambda a, b: 77,
    )

    command(room, "u1", "상현", "보스레이드")
    command(room, "u2", "철수", "레이드수락")
    # u3 still pending — starter force-starts with current levels
    assert game.swords["u1"].level == 5
    assert game.swords["u2"].level == 7

    result = command(room, "u1", "상현", "레이드지금시작").json()
    assert result["ok"] is True
    assert "지금" in result["message"] or "응답 대기 없이" in result["message"]
    assert "보스 등장" in result["message"]
    assert "+5강" in result["message"]
    assert "+7강" in result["message"]
    assert game.raid.phase == RaidPhase.BATTLING
    assert len(game.raid.accepted()) == 2
    assert game.raid.invites["u3"].response == "rejected"
    # levels unchanged by starting battle
    assert game.swords["u1"].level == 5
    assert game.swords["u2"].level == 7
    assert game.swords["u3"].level == 2

    denied = command(room, "u2", "철수", "레이드지금시작").json()
    assert denied["ok"] is False


def test_help_includes_raid_rules(monkeypatch):
    reset_platform(monkeypatch)
    command("help-room", "u1", "상현", "게임선택 검키우기")
    result = command("help-room", "u1", "상현", "도움말").json()
    assert "보스 레이드" in result["message"]
    assert "크리티컬" in result["message"]
    assert "레이드 중에는 강화" in result["message"]
    assert "지금 시작" in result["message"]


def test_raid_card_actions_change_by_phase(monkeypatch):
    room = "raid-actions"
    game = select_and_seed(room, [("u1", "상현", 1), ("u2", "철수", 1)], monkeypatch)
    idle = [cmd for _, cmd in main_module._build_available_card_actions(game)]
    assert "보스레이드" in idle
    assert "공격" not in idle

    command(room, "u1", "상현", "보스레이드")
    inviting = [cmd for _, cmd in main_module._build_available_card_actions(game)]
    assert "레이드수락" in inviting
    assert "레이드지금시작" in inviting
    assert "게임선택 홀덤" not in inviting

    command(room, "u2", "철수", "레이드수락")
    battling = [cmd for _, cmd in main_module._build_available_card_actions(game)]
    assert "공격" in battling
    assert "레이드지금시작" not in battling
