import random
from dataclasses import dataclass


DESTROY_CHANCE = 0.05


@dataclass
class SwordOwner:
    person_id: str
    display_name: str
    level: int = 0


class SwordUpgradeGame:
    """방 안 참가자들이 각자 검을 만들고 강화하는 게임."""

    def __init__(self):
        self.swords: dict[str, SwordOwner] = {}

    @staticmethod
    def success_rate(target_level: int) -> float:
        """N강 도전 성공률. 1강 90%, 2강 80%, ..."""
        if target_level < 1:
            return 1.0
        return max(0.0, (100 - target_level * 10) / 100.0)

    def create_sword(self, person_id: str, display_name: str) -> str:
        existing = self.swords.get(person_id)
        if existing is not None:
            raise ValueError(
                f"이미 검이 있습니다. 현재 {existing.level}강입니다. 강화로 업그레이드하세요."
            )

        self.swords[person_id] = SwordOwner(
            person_id=person_id,
            display_name=display_name,
            level=0,
        )
        return f"{display_name}님이 검을 생성했습니다. (0강)\n강화 버튼으로 강화를 시도하세요."

    def enhance(self, person_id: str, display_name: str) -> str:
        sword = self.swords.get(person_id)
        if sword is None:
            raise ValueError("먼저 검을 생성해주세요.")

        sword.display_name = display_name
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
            del self.swords[person_id]
            return (
                f"강화 실패... 검이 파괴되었습니다.\n"
                f"{display_name}님의 검이 사라졌습니다. 검생성으로 다시 만들 수 있습니다.\n"
                f"(성공률 {rate_percent}%, 파괴 확률 {int(DESTROY_CHANCE * 100)}%)"
            )

        previous = sword.level
        sword.level = max(0, sword.level - 1)
        return (
            f"강화 실패... 검이 {previous}강 → {sword.level}강으로 하락했습니다.\n"
            f"(성공률 {rate_percent}%)"
        )

    def my_sword(self, person_id: str, display_name: str) -> str:
        sword = self.swords.get(person_id)
        if sword is None:
            return f"{display_name}님은 아직 검이 없습니다. 검생성으로 만들어보세요."

        next_rate = int(self.success_rate(sword.level + 1) * 100)
        return (
            f"{display_name}님의 검: +{sword.level}강\n"
            f"다음 강화 성공률: {next_rate}%"
        )

    def ranking(self) -> str:
        if not self.swords:
            return "아직 생성된 검이 없습니다."

        ordered = sorted(
            self.swords.values(),
            key=lambda owner: (-owner.level, owner.display_name),
        )
        lines = ["검키우기 랭킹"]
        for index, owner in enumerate(ordered, start=1):
            lines.append(f"{index}. {owner.display_name} — +{owner.level}강")
        return "\n".join(lines)

    def reset(self) -> str:
        self.swords = {}
        return "검키우기 게임을 리셋했습니다. 모든 검이 초기화되었습니다."

    def status(self) -> str:
        if not self.swords:
            return "검키우기 대기 중. 검생성 후 강화해보세요."

        ordered = sorted(
            self.swords.values(),
            key=lambda owner: (-owner.level, owner.display_name),
        )
        lines = [f"검키우기 현황 ({len(ordered)}명)"]
        for owner in ordered:
            next_rate = int(self.success_rate(owner.level + 1) * 100)
            lines.append(
                f"- {owner.display_name}: +{owner.level}강 (다음 성공률 {next_rate}%)"
            )
        return "\n".join(lines)

    def can_change_game(self) -> bool:
        return True

    def to_dict(self) -> dict:
        return {
            "swords": {
                person_id: {
                    "person_id": owner.person_id,
                    "display_name": owner.display_name,
                    "level": owner.level,
                }
                for person_id, owner in self.swords.items()
            }
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
        return game
