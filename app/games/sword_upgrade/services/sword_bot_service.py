from app.commands.command import CommandType
from app.commands.parser import CommandParser
from app.core.game_response import GameResponse
from app.games.sword_upgrade.domain.game import SwordUpgradeGame
from app.games.sword_upgrade.services.raid_invite_card import build_raid_invite_card
from app.services.display_name import clean_display_name
from app.services.stats_store import JsonStatsStore


class SwordUpgradeBotService:
    def __init__(
        self,
        game: SwordUpgradeGame,
        command_parser: CommandParser,
        stats_store: JsonStatsStore | None = None,
        room_id: str | None = None,
    ):
        self.game = game
        self.command_parser = command_parser
        self.stats_store = stats_store
        self.room_id = room_id or "unknown-room"

    def handle_text_command(
        self,
        person_id: str,
        display_name: str,
        text: str,
    ) -> GameResponse:
        try:
            display_name = clean_display_name(display_name)
            for owner in self.game.swords.values():
                owner.display_name = clean_display_name(owner.display_name)

            normalized = self.command_parser.normalize(text)
            private = False
            silent_public = False
            direct_messages: list[dict] = []

            if normalized in {"검생성", "검 생성", "검만들기", "검 만들기"}:
                self.game.ensure_sword(person_id, display_name)
                message = (
                    f"{display_name}님은 이미 검을 가지고 있습니다. "
                    "별도 생성 없이 채팅으로 `@FSS 강화`를 입력하세요."
                )
            elif normalized == "강화":
                message = self.game.enhance(person_id, display_name)
            elif normalized in {"내검", "내 검"}:
                message = self.game.my_sword(person_id, display_name)
                private = True
                silent_public = True
            elif normalized == "상태":
                message = self.game.status()
            elif normalized in {"랭킹", "순위", "ranking"}:
                message = self.game.ranking()
            elif normalized in {"전체랭킹", "통합랭킹", "overall ranking"}:
                message = (
                    self.stats_store.overall_ranking_text()
                    if self.stats_store
                    else "전적 저장소가 설정되어 있지 않습니다."
                )
            elif normalized in {"전적", "내전적", "기록", "record"}:
                message = self.game.my_sword(person_id, display_name)
                private = True
                silent_public = True
            elif normalized in {"보스레이드", "레이드시작", "레이드", "보스 레이드"}:
                message, invite_ids = self.game.start_raid(person_id, display_name)
                for invite_id in invite_ids:
                    direct_messages.append(
                        {
                            "person_id": invite_id,
                            "message": (
                                f"보스 레이드 초대\n"
                                f"{display_name}님이 레이드를 시작했습니다.\n"
                                f"아래 버튼으로 수락/거부하거나, "
                                f"그룹방에서 `@FSS 레이드수락` / `@FSS 레이드거부`를 입력하세요."
                            ),
                            "card": build_raid_invite_card(self.room_id, display_name),
                        }
                    )
            elif normalized in {"레이드수락", "수락"}:
                message = self.game.respond_raid(person_id, display_name, accepted=True)
            elif normalized in {"레이드거부", "거부"}:
                message = self.game.respond_raid(person_id, display_name, accepted=False)
            elif normalized in {"레이드지금시작", "지금시작", "지금 시작", "초대마감"}:
                message = self.game.force_start_raid(person_id, display_name)
            elif normalized == "공격":
                message = self.game.attack_boss(person_id, display_name)
            elif normalized in {"레이드취소", "보스레이드취소"}:
                message = self.game.cancel_raid(person_id, display_name)
            elif normalized in {"리셋", "초기화", "reset"}:
                self.game.reset()
                message = f"{display_name}님이 검키우기 게임을 리셋했습니다."
            elif normalized in {"도움말", "도움", "명령어", "help"}:
                message = self._help_message()
            else:
                try:
                    command = self.command_parser.parse(text)
                except ValueError as error:
                    raise ValueError("검키우기에서 사용할 수 없는 명령어입니다.") from error
                if command.type == CommandType.FORCE_RESET:
                    raise ValueError("강제리셋은 Webex 텍스트 명령에서만 사용할 수 있습니다.")
                raise ValueError("검키우기에서 사용할 수 없는 명령어입니다.")

            return {
                "ok": True,
                "message": message,
                "status": self.game.status(),
                "private": private,
                "public_message": None,
                "silent_public": silent_public,
                "deal_private_cards": False,
                "direct_messages": direct_messages,
            }
        except Exception as error:
            return {"ok": False, "message": str(error)}

    @staticmethod
    def _help_message() -> str:
        return (
            "검키우기 도움말\n\n"
            "게임 선택: @FSS 게임선택 검키우기\n"
            "진행: 채팅으로 `@FSS 강화`\n\n"
            "규칙\n"
            "- 방에 참여하면 자동으로 0강 검을 가집니다. (검생성 불필요)\n"
            "- 강화는 채팅으로만 가능합니다. (버튼 불가)\n"
            "- 성공률: 1강 90%, 2강 80%, 3강 70% ... (10%씩 감소)\n"
            "- 실패 시 1강 하락, 낮은 확률(5%)로 파괴되어 0강이 됩니다.\n\n"
            "보스 레이드\n"
            "- 시작: `@FSS 보스레이드` (검을 가진 전원에게 DM 초대)\n"
            "- 초대 응답: DM 버튼 또는 `@FSS 레이드수락` / `@FSS 레이드거부`\n"
            "- 전원 응답 전이라도 시작자가 `지금 시작`으로 전투를 열 수 있습니다.\n"
            "- 전투 시 참가자의 현재 검 강화 레벨이 그대로 적용됩니다.\n"
            "- 전원이 응답하거나 지금 시작하면 랜덤 체력 보스가 등장합니다.\n"
            "- 원칙: 한 라운드(참가자 전원 각 1회 공격)로 처치\n"
            "- 공격: `@FSS 공격` → 주사위 2개\n"
            "  · 합 2~3 미스 (데미지 0)\n"
            "  · 합 4~10 평타\n"
            "  · 합 11~12 크리티컬 (평타 ×2)\n"
            "  · 평타 데미지 = 무기티어(현재 1) × 무기등급(검 강수)\n"
            "  · 같은 눈이면 한 번 더 굴림(연출)\n"
            "- 전원 공격 후 클리어/실패를 발표하고 레이드가 종료됩니다.\n"
            "- 클리어 시 참가자 전원 +1강, 실패 시 참가자 전원 -1강\n"
            "- 레이드 중에는 강화·리셋·다른 게임 선택이 불가합니다.\n"
            "- 취소: 시작자만 `@FSS 레이드취소`\n\n"
            "명령어: 강화 / 보스레이드 / 레이드수락 / 레이드거부 / 레이드지금시작 / 공격 / "
            "레이드취소 / 내검 / 상태 / 랭킹 / 리셋\n"
            "다른 게임: @FSS 게임선택 홀덤 / 주사위 / 바보라이어게임"
        )
