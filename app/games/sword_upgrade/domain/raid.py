"""보스 레이드 규칙과 전투 판정."""

from __future__ import annotations

import random
from dataclasses import dataclass, field
from enum import Enum


class RaidPhase(str, Enum):
    IDLE = "idle"
    INVITING = "inviting"
    BATTLING = "battling"


@dataclass
class RaidInvitee:
    person_id: str
    display_name: str
    response: str | None = None  # None | "accepted" | "rejected"


@dataclass
class RaidAttackResult:
    person_id: str
    display_name: str
    dice: list[int]
    first_sum: int
    damage: int
    note: str


@dataclass
class BossRaid:
    starter_id: str
    starter_name: str
    phase: RaidPhase = RaidPhase.INVITING
    invites: dict[str, RaidInvitee] = field(default_factory=dict)
    boss_hp: int | None = None
    boss_max_hp: int | None = None
    attacks: dict[str, RaidAttackResult] = field(default_factory=dict)

    def pending_invitees(self) -> list[RaidInvitee]:
        return [item for item in self.invites.values() if item.response is None]

    def accepted(self) -> list[RaidInvitee]:
        return [item for item in self.invites.values() if item.response == "accepted"]

    def all_invites_answered(self) -> bool:
        return all(item.response is not None for item in self.invites.values())

    def pending_attackers(self) -> list[RaidInvitee]:
        return [
            item
            for item in self.accepted()
            if item.person_id not in self.attacks
        ]

    def to_dict(self) -> dict:
        return {
            "starter_id": self.starter_id,
            "starter_name": self.starter_name,
            "phase": self.phase.value,
            "boss_hp": self.boss_hp,
            "boss_max_hp": self.boss_max_hp,
            "invites": {
                person_id: {
                    "person_id": invitee.person_id,
                    "display_name": invitee.display_name,
                    "response": invitee.response,
                }
                for person_id, invitee in self.invites.items()
            },
            "attacks": {
                person_id: {
                    "person_id": attack.person_id,
                    "display_name": attack.display_name,
                    "dice": list(attack.dice),
                    "first_sum": attack.first_sum,
                    "damage": attack.damage,
                    "note": attack.note,
                }
                for person_id, attack in self.attacks.items()
            },
        }

    @classmethod
    def from_dict(cls, data: dict) -> BossRaid:
        raid = cls(
            starter_id=str(data.get("starter_id", "")),
            starter_name=str(data.get("starter_name", "")),
            phase=RaidPhase(str(data.get("phase", RaidPhase.INVITING.value))),
            boss_hp=data.get("boss_hp"),
            boss_max_hp=data.get("boss_max_hp"),
        )
        for person_id, raw in (data.get("invites") or {}).items():
            raid.invites[person_id] = RaidInvitee(
                person_id=str(raw.get("person_id", person_id)),
                display_name=str(raw.get("display_name", "unknown")),
                response=raw.get("response"),
            )
        for person_id, raw in (data.get("attacks") or {}).items():
            raid.attacks[person_id] = RaidAttackResult(
                person_id=str(raw.get("person_id", person_id)),
                display_name=str(raw.get("display_name", "unknown")),
                dice=[int(value) for value in raw.get("dice", [])],
                first_sum=int(raw.get("first_sum", 0)),
                damage=int(raw.get("damage", 0)),
                note=str(raw.get("note", "")),
            )
        return raid


WEAPON_TIER = 1  # 무기 티어 (아직 미구현, 고정 1)


def roll_die() -> int:
    return random.randint(1, 6)


def resolve_attack_dice(sword_level: int) -> RaidAttackResult:
    """2d6 공격 판정.

    - 합 2~3: 미스 (데미지 0)
    - 합 4~10: 평타
    - 합 11~12: 크리티컬 (평타 데미지 ×2)
    - 평타 데미지 = 무기티어 × 무기등급(검 강화 강수)
    - 같은 눈이면 한 번 더 굴림(연출), 판정은 첫 두 눈의 합 기준
    """
    first = [roll_die(), roll_die()]
    dice = list(first)
    first_sum = first[0] + first[1]
    if first[0] == first[1]:
        dice.extend([roll_die(), roll_die()])

    grade = sword_level
    base = WEAPON_TIER * grade

    if first_sum <= 3:
        damage = 0
        note = "미스"
    elif first_sum >= 11:
        damage = base * 2
        note = "크리티컬"
    else:
        damage = base
        note = "평타"

    if len(dice) > 2 and note != "미스":
        note = f"{note}+더블"
    elif len(dice) > 2:
        note = "미스+더블"

    return RaidAttackResult(
        person_id="",
        display_name="",
        dice=dice,
        first_sum=first_sum,
        damage=damage,
        note=note,
    )


def roll_boss_hp(accepted_levels: list[int]) -> int:
    """한 라운드(전원 1회 공격)로 잡을 수 있을 법한 랜덤 체력.

    기대 데미지 ≈ 티어×등급 기준이므로 강수 합으로 스케일합니다.
    """
    power = sum(max(level, 1) * WEAPON_TIER for level in accepted_levels) or 1
    low = max(1, power)
    high = max(low + 1, int(power * 2.5))
    return random.randint(low, high)


def format_dice(dice: list[int]) -> str:
    return "[" + "][".join(str(value) for value in dice) + "]"
