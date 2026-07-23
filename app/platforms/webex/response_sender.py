from collections.abc import Callable

from app.domain.game import HoldemGame
from app.platforms.base import PlatformGateway


class WebexResponseSender:
    def __init__(
        self,
        get_game: Callable,
        card_builder,
        build_actions: Callable,
        create_card_token: Callable[[str], str],
        rollback_holdem_start: Callable[[str, dict], HoldemGame],
        save_state: Callable[[], None],
    ):
        self.get_game = get_game
        self.card_builder = card_builder
        self.build_actions = build_actions
        self.create_card_token = create_card_token
        self.rollback_holdem_start = rollback_holdem_start
        self.save_state = save_state

    @staticmethod
    def send_private_cards(gateway: PlatformGateway, game) -> list[str]:
        if not isinstance(game, HoldemGame):
            return []
        failures = []
        for player in game.players:
            try:
                gateway.send_direct_message(
                    person_id=player.person_id,
                    markdown=game.private_cards(player.person_id),
                )
            except Exception:
                failures.append(player.person_id)
        return failures

    def send(
        self,
        gateway: PlatformGateway,
        room_id: str,
        person_id: str,
        result: dict,
    ) -> None:
        game = self.get_game(room_id)
        status = result.get("status") or game.status()
        if result["ok"] and result.get("deal_private_cards"):
            failures = self.send_private_cards(gateway, game)
            if failures and result.get("_start_snapshot") is not None:
                failed_names = [
                    game.players[index].display_name
                    for failed_id in failures
                    if (index := game._find_player_index(failed_id)) is not None
                ]
                game = self.rollback_holdem_start(room_id, result["_start_snapshot"])
                result.clear()
                result.update(
                    {
                        "ok": False,
                        "message": (
                            "개인 카드를 전송할 수 없어 게임 시작을 취소했습니다: "
                            + ", ".join(failed_names)
                        ),
                        "status": game.status(),
                    }
                )
                self.save_state()
                status = result["status"]

        if result["ok"]:
            if result.get("private"):
                gateway.send_direct_message(person_id=person_id, markdown=result["message"])
                if result.get("silent_public"):
                    return
                public_reply = result.get("public_message") or ""
                message_type = "success"
                card_message = public_reply or None
            else:
                public_reply = result["message"]
                message_type = "success"
                if public_reply == status:
                    public_reply = "상태를 조회했습니다."
                    card_message = public_reply
                else:
                    card_message = public_reply
        else:
            public_reply = result["message"]
            message_type = "error"
            card_message = public_reply

        card = self.card_builder.build_action_card(
            status=status,
            message=card_message,
            message_type=message_type,
            actions=self.build_actions(game),
            card_token=self.create_card_token(room_id),
        )
        markdown = (
            f"⚠️ 처리 실패\n\n{public_reply}"
            if message_type == "error"
            else public_reply
        )
        gateway.send_room_card(room_id=room_id, markdown=markdown, card=card)
