import random
from dataclasses import dataclass

from app.games.sword_upgrade.domain.raid import (
    BossRaid,
    RaidInvitee,
    RaidPhase,
    format_dice,
    resolve_attack_dice,
    roll_boss_hp,
)


DESTROY_CHANCE = 0.05


@dataclass
class SwordOwner:
    person_id: str
    display_name: str
    level: int = 0


class SwordUpgradeGame:
    """방 안 참가자들이 각자 검을 강화하는 게임.

    검생성 없이, 방에 참여해 명령을 쓰는 순간 0강 검을 자동으로 가집니다.
    파괴 시에도 검은 유지되며 0강으로 돌아갑니다.
    보스 레이드 중에는 강화와 게임 변경이 잠깁니다.
    """

    def __init__(self):
        self.swords: dict[str, SwordOwner] = {}
        self.raid: BossRaid | None = None

    @staticmethod
    def success_rate(target_level: int) -> float:
        """N강 도전 성공률. 1강 90%, 2강 80%, ..."""
        if target_level < 1:
            return 1.0
        return max(0.0, (100 - target_level * 10) / 100.0)

    def ensure_sword(self, person_id: str, display_name: str) -> SwordOwner:
        sword = self.swords.get(person_id)
        if sword is None:
            sword = SwordOwner(
                person_id=person_id,
                display_name=display_name,
                level=0,
            )
            self.swords[person_id] = sword
            return sword

        sword.display_name = display_name
        return sword

    def is_raid_active(self) -> bool:
        return self.raid is not None and self.raid.phase != RaidPhase.IDLE

    def enhance(self, person_id: str, display_name: str) -> str:
        if self.is_raid_active():
            raise ValueError("보스 레이드 중에는 강화할 수 없습니다. 레이드가 끝날 때까지 기다려주세요.")

        sword = self.ensure_sword(person_id, display_name)
        target_level = sword.level + 1
        rate = self.success_rate(target_level)
        rate_percent = int(rate * 100)

        if rate <= 0:
            raise ValueError(f"더 이상 강화할 수 없습니다. 현재 {sword.level}강입니다.")

        roll = random.random()
        if roll < rate:
            sword.level = target_level
            return (
                f"강화 성공! {display_name}님의 검이 +{sword.level}강이 되었습니다.\n"
                f"(성공률 {rate_percent}%)"
            )

        destroyed = random.random() < DESTROY_CHANCE
        if destroyed:
            sword.level = 0
            return (
                f"강화 실패... 검이 파괴되어 0강으로 돌아갔습니다.\n"
                f"{display_name}님의 검: +0강\n"
                f"(성공률 {rate_percent}%, 파괴 확률 {int(DESTROY_CHANCE * 100)}%)"
            )

        previous = sword.level
        sword.level = max(0, sword.level - 1)
        return (
            f"강화 실패... 검이 {previous}강 → {sword.level}강으로 하락했습니다.\n"
            f"(성공률 {rate_percent}%)"
        )

    def my_sword(self, person_id: str, display_name: str) -> str:
        sword = self.ensure_sword(person_id, display_name)
        next_rate = int(self.success_rate(sword.level + 1) * 100)
        return (
            f"{display_name}님의 검: +{sword.level}강\n"
            f"다음 강화 성공률: {next_rate}%"
        )

    def ranking(self) -> str:
        if not self.swords:
            return "아직 강화에 참여한 사람이 없습니다. 채팅으로 `@FSS 강화`를 입력해보세요."

        ordered = sorted(
            self.swords.values(),
            key=lambda owner: (-owner.level, owner.display_name),
        )
        lines = ["검키우기 랭킹"]
        for index, owner in enumerate(ordered, start=1):
            lines.append(f"{index}. {owner.display_name} — +{owner.level}강")
        return "\n".join(lines)

    def reset(self) -> str:
        if self.is_raid_active():
            raise ValueError("보스 레이드 중에는 리셋할 수 없습니다. 먼저 `레이드취소`를 사용하세요.")
        self.swords = {}
        self.raid = None
        return "검키우기 게임을 리셋했습니다. 모든 검이 초기화되었습니다."

    def start_raid(self, person_id: str, display_name: str) -> tuple[str, list[str]]:
        """레이드 시작. 반환: (공개 메시지, 초대 DM 대상 person_id 목록)."""
        if self.is_raid_active():
            raise ValueError("이미 보스 레이드가 진행 중입니다.")

        self.ensure_sword(person_id, display_name)
        if not self.swords:
            raise ValueError("검을 가진 사람이 없습니다. 먼저 `@FSS 강화`로 참여해주세요.")

        invites = {
            owner.person_id: RaidInvitee(
                person_id=owner.person_id,
                display_name=owner.display_name,
                response="accepted" if owner.person_id == person_id else None,
            )
            for owner in self.swords.values()
        }
        self.raid = BossRaid(
            starter_id=person_id,
            starter_name=display_name,
            phase=RaidPhase.INVITING,
            invites=invites,
        )

        invite_targets = [
            invitee.person_id
            for invitee in invites.values()
            if invitee.person_id != person_id
        ]
        if not invite_targets:
            spawn_message = self._spawn_boss_if_ready()
            return (
                f"{display_name}님이 보스 레이드를 시작했습니다.\n"
                f"다른 검 소유자가 없어 즉시 전투를 시작합니다.\n"
                f"{spawn_message}",
                [],
            )

        return (
            f"{display_name}님이 보스 레이드를 시작했습니다.\n"
            f"검을 가진 {len(invites)}명에게 초대 DM을 보냈습니다.\n"
            f"전원 응답을 기다리거나, 시작자가 `지금 시작`으로 바로 전투에 들어갈 수 있습니다.\n"
            f"(시작자는 자동 수락, 현재 검 강화 레벨 그대로 적용)",
            invite_targets,
        )

    def respond_raid(
        self,
        person_id: str,
        display_name: str,
        accepted: bool,
    ) -> str:
        raid = self._require_raid()
        if raid.phase != RaidPhase.INVITING:
            raise ValueError("현재는 레이드 초대 응답 단계가 아닙니다.")

        invitee = raid.invites.get(person_id)
        if invitee is None:
            raise ValueError("이 레이드 초대 대상이 아닙니다.")
        if invitee.response is not None:
            raise ValueError("이미 초대에 응답했습니다.")

        invitee.display_name = display_name
        invitee.response = "accepted" if accepted else "rejected"
        choice = "수락" if accepted else "거부"
        message = f"{display_name}님이 레이드 초대를 {choice}했습니다."

        if not raid.all_invites_answered():
            pending = ", ".join(item.display_name for item in raid.pending_invitees())
            return (
                f"{message}\n응답 대기: {pending}\n"
                f"(시작자는 `지금 시작`으로 대기 없이 전투를 열 수 있습니다.)"
            )

        spawn = self._spawn_boss_if_ready()
        return f"{message}\n전원 응답 완료.\n{spawn}"

    def force_start_raid(self, person_id: str, display_name: str) -> str:
        """응답 대기 없이, 현재 수락 인원과 현재 검 강화로 전투 시작."""
        raid = self._require_raid()
        if raid.phase != RaidPhase.INVITING:
            raise ValueError("초대 단계에서만 지금 시작할 수 있습니다.")
        if person_id != raid.starter_id:
            raise ValueError("레이드 시작자만 지금 시작할 수 있습니다.")

        skipped = []
        for invitee in raid.pending_invitees():
            invitee.response = "rejected"
            skipped.append(invitee.display_name)

        spawn = self._spawn_boss_if_ready()
        if self.raid is None:
            return spawn

        lines = [f"{display_name}님이 응답 대기 없이 레이드 전투를 시작했습니다."]
        if skipped:
            lines.append(f"미응답(불참 처리): {', '.join(skipped)}")
        lines.append("참가자의 현재 검 강화 레벨이 그대로 적용됩니다.")
        lines.append(spawn)
        return "\n".join(lines)

    def attack_boss(self, person_id: str, display_name: str) -> str:
        raid = self._require_raid()
        if raid.phase != RaidPhase.BATTLING:
            raise ValueError("보스가 등장한 뒤에 공격할 수 있습니다.")

        invitee = next((item for item in raid.accepted() if item.person_id == person_id), None)
        if invitee is None:
            raise ValueError("레이드에 수락한 참가자만 공격할 수 있습니다.")
        if person_id in raid.attacks:
            raise ValueError("이미 공격했습니다. 다른 참가자의 공격을 기다려주세요.")

        sword = self.ensure_sword(person_id, display_name)
        result = resolve_attack_dice(sword.level)
        result.person_id = person_id
        result.display_name = display_name
        raid.attacks[person_id] = result
        assert raid.boss_hp is not None
        raid.boss_hp = max(0, raid.boss_hp - result.damage)

        lines = [
            f"{display_name}님의 공격! 주사위 {format_dice(result.dice)} "
            f"(첫합 {result.first_sum}) → {result.note} / 데미지 {result.damage}",
            f"보스 체력: {raid.boss_hp}/{raid.boss_max_hp}",
        ]

        pending = raid.pending_attackers()
        if pending:
            names = ", ".join(item.display_name for item in pending)
            lines.append(f"남은 공격: {names}")
            return "\n".join(lines)

        lines.append(self._finish_raid_round())
        return "\n".join(lines)

    def cancel_raid(self, person_id: str, display_name: str) -> str:
        raid = self._require_raid()
        if person_id != raid.starter_id:
            raise ValueError("레이드 시작자만 취소할 수 있습니다.")
        self.raid = None
        return f"{display_name}님이 보스 레이드를 취소했습니다."

    def _spawn_boss_if_ready(self) -> str:
        raid = self._require_raid()
        accepted = raid.accepted()
        if not accepted:
            self.raid = None
            return "수락한 인원이 없어 레이드가 취소되었습니다."

        levels = []
        for invitee in accepted:
            sword = self.swords.get(invitee.person_id)
            levels.append(sword.level if sword else 0)
        hp = roll_boss_hp(levels)
        raid.boss_hp = hp
        raid.boss_max_hp = hp
        raid.phase = RaidPhase.BATTLING
        raid.attacks = {}
        names = ", ".join(f"{item.display_name}(+{self.swords[item.person_id].level}강)" for item in accepted)
        return (
            f"보스 등장! 체력 {hp}\n"
            f"참가자({len(accepted)}명): {names}\n"
            f"한 라운드(전원 1회 공격)로 처치하는 것이 원칙입니다.\n"
            f"참가자는 `@FSS 공격`으로 공격하세요."
        )

    def _finish_raid_round(self) -> str:
        raid = self._require_raid()
        assert raid.boss_hp is not None and raid.boss_max_hp is not None
        total_damage = sum(attack.damage for attack in raid.attacks.values())
        cleared = raid.boss_hp <= 0
        lines = ["=== 레이드 결과 ==="]
        for attack in raid.attacks.values():
            lines.append(
                f"- {attack.display_name}: {format_dice(attack.dice)} "
                f"{attack.note} → {attack.damage}"
            )
        lines.append(f"총 데미지 {total_damage} / 보스 체력 {raid.boss_max_hp}")
        if cleared:
            lines.append("클리어! 보스를 처치했습니다.")
        else:
            lines.append(
                f"실패... 보스 체력이 {raid.boss_hp} 남았습니다. "
                "한 라운드 공격으로 처치하지 못했습니다."
            )
        self.raid = None
        return "\n".join(lines)

    def _require_raid(self) -> BossRaid:
        if self.raid is None:
            raise ValueError("진행 중인 보스 레이드가 없습니다.")
        return self.raid

    def status(self) -> str:
        lines: list[str] = []
        if self.raid is not None:
            lines.append(self._raid_status())
            lines.append("")

        if not self.swords:
            lines.append(
                "검키우기 진행 중.\n"
                "채팅으로 `@FSS 강화`를 입력하면 0강 검으로 참여합니다."
            )
            return "\n".join(lines).strip()

        ordered = sorted(
            self.swords.values(),
            key=lambda owner: (-owner.level, owner.display_name),
        )
        lines.append(f"검키우기 현황 ({len(ordered)}명)")
        for owner in ordered:
            next_rate = int(self.success_rate(owner.level + 1) * 100)
            lines.append(
                f"- {owner.display_name}: +{owner.level}강 (다음 성공률 {next_rate}%)"
            )
        return "\n".join(lines)

    def _raid_status(self) -> str:
        raid = self._require_raid()
        if raid.phase == RaidPhase.INVITING:
            pending = ", ".join(item.display_name for item in raid.pending_invitees()) or "-"
            accepted = ", ".join(item.display_name for item in raid.accepted()) or "-"
            return (
                f"보스 레이드 초대 중 (시작: {raid.starter_name})\n"
                f"수락: {accepted}\n"
                f"응답 대기: {pending}"
            )
        pending = ", ".join(item.display_name for item in raid.pending_attackers()) or "-"
        return (
            f"보스 레이드 전투 중 (시작: {raid.starter_name})\n"
            f"보스 체력: {raid.boss_hp}/{raid.boss_max_hp}\n"
            f"남은 공격: {pending}"
        )

    def can_change_game(self) -> bool:
        return not self.is_raid_active()

    def to_dict(self) -> dict:
        return {
            "swords": {
                person_id: {
                    "person_id": owner.person_id,
                    "display_name": owner.display_name,
                    "level": owner.level,
                }
                for person_id, owner in self.swords.items()
            },
            "raid": self.raid.to_dict() if self.raid is not None else None,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "SwordUpgradeGame":
        game = cls()
        raw_swords = data.get("swords", {})
        for person_id, owner_data in raw_swords.items():
            game.swords[person_id] = SwordOwner(
                person_id=str(owner_data.get("person_id", person_id)),
                display_name=str(owner_data.get("display_name", "unknown")),
                level=int(owner_data.get("level", 0)),
            )
        raw_raid = data.get("raid")
        if raw_raid:
            game.raid = BossRaid.from_dict(raw_raid)
        return game
