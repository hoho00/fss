import logging
from collections.abc import Callable

from app.games.mahjong_efficiency.battle_card_builder import build_game_status_selector_card
from app.games.sword_upgrade.domain.game import SwordUpgradeGame

logger = logging.getLogger(__name__)

_SWORD_CHAT_ONLY_COMMANDS = {
    "강화",
    "검생성",
    "검 생성",
    "검만들기",
    "검 만들기",
}


class WebexEventHandler:
    def __init__(
        self,
        webex_client_factory: Callable,
        command_coordinator,
        card_builder,
        get_game: Callable,
        send_result: Callable,
        handle_force_reset: Callable,
        handle_game_selection: Callable,
        handle_ranking_reset: Callable,
        is_force_reset: Callable[[str], bool],
        is_game_selection: Callable[[str], bool],
        is_ranking_reset: Callable[[str], bool],
        is_latest_card: Callable[[str, str | None], bool],
        can_accept_stale_card: Callable[[str, str], bool],
        should_ignore_result: Callable[[str, dict], bool],
        room_lock: Callable[[str], object],
        is_processed: Callable[[str], bool],
        mark_processed: Callable[[str], None],
        save_state: Callable[[], None],
        mahjong_efficiency_service=None,
        mahjong_battle_service=None,
    ):
        self.webex_client_factory = webex_client_factory
        self.command_coordinator = command_coordinator
        self.card_builder = card_builder
        self.get_game = get_game
        self.send_result = send_result
        self.handle_force_reset = handle_force_reset
        self.handle_game_selection = handle_game_selection
        self.handle_ranking_reset = handle_ranking_reset
        self.is_force_reset = is_force_reset
        self.is_game_selection = is_game_selection
        self.is_ranking_reset = is_ranking_reset
        self.is_latest_card = is_latest_card
        self.can_accept_stale_card = can_accept_stale_card
        self.should_ignore_result = should_ignore_result
        self.room_lock = room_lock
        self.is_processed = is_processed
        self.mark_processed = mark_processed
        self.save_state = save_state
        self.mahjong_efficiency_service = mahjong_efficiency_service
        self.mahjong_battle_service = mahjong_battle_service

    def process_event(
        self,
        payload: dict,
        event_kind: str,
        locked_handler: Callable[[dict], dict],
    ) -> dict:
        data = payload.get("data") or {}
        event_id = data.get("id")
        room_key = data.get("roomId") or f"{event_kind}:{event_id or 'unknown'}"
        with self.room_lock(room_key):
            if event_id and self.is_processed(event_id):
                return {"ok": True, "ignored": True, "reason": "duplicate webhook"}
            result = locked_handler(payload)
            if event_id and result.get("ok"):
                self.mark_processed(event_id)
                self.save_state()
            return result

    def handle_message_locked(self, payload: dict) -> dict:
        data = payload.get("data") or {}
        message_id = data.get("id")
        if not message_id:
            return {"ok": False, "message": "webhook payload에 data.id가 없습니다."}

        client = self.webex_client_factory()
        message = client.get_message(message_id)
        if client.is_bot_message(message):
            return {"ok": True, "ignored": True, "reason": "봇 자신의 메시지입니다."}

        room_id = message.get("roomId") or data.get("roomId")
        if not room_id:
            return {"ok": False, "message": "메시지에서 roomId를 찾을 수 없습니다."}
        text = message.get("text", "").strip()
        person_id = message.get("personId")
        person_email = message.get("personEmail")
        display_name = person_email or person_id
        if not text:
            return {"ok": True, "ignored": True, "reason": "텍스트가 없는 메시지입니다."}

        logger.info(
            "WEBEX command room=%s user=%s text=%r",
            room_id,
            display_name,
            text,
        )

        special_service = None
        battle_service = getattr(self, "mahjong_battle_service", None)
        if battle_service and battle_service.normalized_command(text) == "상태":
            client.send_room_card(
                room_id=room_id, markdown="FSS 게임 상태 선택",
                card=build_game_status_selector_card(),
            )
            return {"ok": True, "status_selection": True}
        if battle_service and battle_service.is_command(text):
            special_service = battle_service
        elif self.mahjong_efficiency_service and self.mahjong_efficiency_service.is_command(text):
            special_service = self.mahjong_efficiency_service
        if special_service:
            if not message.get("roomType") and hasattr(client, "get_room"):
                room = client.get_room(room_id)
                message = {**message, "roomType": room.get("type") or room.get("roomType")}
            return special_service.handle_command(client, message)

        if self.is_force_reset(text):
            result = self.handle_force_reset(room_id, person_id)
            self.send_result(client, room_id, person_id, result)
            return {"ok": True}
        if self.is_game_selection(text):
            result = self.handle_game_selection(room_id, text)
            self.send_result(client, room_id, person_id, result)
            return {"ok": True}
        if self.is_ranking_reset(text):
            result = self.handle_ranking_reset(room_id, person_email)
            self.send_result(client, room_id, person_id, result)
            return {"ok": True}

        result = self.command_coordinator.execute(
            gateway=client,
            room_id=room_id,
            person_id=person_id,
            display_name=display_name,
            text=text,
        )
        if self.should_ignore_result(text, result):
            return {"ok": True, "ignored": True, "reason": "out_of_turn_text_action"}
        self.send_result(client, room_id, person_id, result)
        return {"ok": True}

    def handle_attachment_locked(self, payload: dict) -> dict:
        data = payload.get("data") or {}
        action_id = data.get("id")
        if not action_id:
            return {"ok": False, "message": "attachmentActions payload에 data.id가 없습니다."}

        client = self.webex_client_factory()
        action = client.get_attachment_action(action_id)
        room_id = action.get("roomId") or data.get("roomId")
        if not room_id:
            return {"ok": False, "message": "버튼 클릭 정보에서 roomId를 찾을 수 없습니다."}
        person_id = action.get("personId")
        if not person_id:
            return {"ok": False, "message": "attachment action에 personId가 없습니다."}

        inputs = action.get("inputs") or {}
        action_name = inputs.get("action")
        button_command = inputs.get("command")
        if action_name or button_command:
            logger.info(
                "WEBEX button room=%s person=%s action=%s command=%r",
                room_id,
                person_id,
                action_name,
                button_command,
            )
        battle_service = getattr(self, "mahjong_battle_service", None)
        if inputs.get("action") == "game_status_selection":
            command = inputs.get("command")
            if command and getattr(self, "is_game_selection", lambda _text: False)(command):
                result = self.handle_game_selection(room_id, command)
                self.send_result(client, room_id, person_id, result)
                return {"ok": True, "status_selection": True}
            if command == "패효율 상태" and self.mahjong_efficiency_service:
                room = client.get_room(room_id)
                return self.mahjong_efficiency_service.handle_command(client, {
                    "roomId": room_id, "personId": person_id, "text": command,
                    "roomType": room.get("type") or room.get("roomType"),
                })
            if command == "패효율 대결 상태" and battle_service:
                room = client.get_room(room_id); person = client.get_person(person_id)
                return battle_service.handle_command(client, {
                    "roomId": room_id, "personId": person_id, "text": command,
                    "roomType": room.get("type") or room.get("roomType"),
                    "personDisplayName": client.display_name_from_person(person, person_id),
                })
            person = client.get_person(person_id)
            result = self.command_coordinator.execute(
                gateway=client, room_id=room_id, person_id=person_id,
                display_name=client.display_name_from_person(person, person_id), text="도움말",
            )
            self.send_result(client, room_id, person_id, result)
            return {"ok": True, "status_selection": True}
        if inputs.get("action") == "mahjong_battle_discard" and battle_service:
            return battle_service.handle_action(client, action)
        command = inputs.get("command")
        if inputs.get("action") == "mahjong_battle_command" or (
            command and battle_service and battle_service.is_command(command)
        ):
            room = client.get_room(room_id)
            person = client.get_person(person_id)
            message = {
                "roomId": room_id, "personId": person_id, "text": command,
                "roomType": room.get("type") or room.get("roomType"),
                "personDisplayName": client.display_name_from_person(person, person_id),
                "actionContext": inputs,
            }
            return battle_service.handle_command(client, message)
        if command and self.mahjong_efficiency_service and self.mahjong_efficiency_service.is_command(command):
            room = client.get_room(room_id)
            message = {
                "roomId": room_id, "personId": person_id, "text": command,
                "roomType": room.get("type") or room.get("roomType"),
            }
            return self.mahjong_efficiency_service.handle_command(client, message)
        if inputs.get("action") == "mahjong_discard" and self.mahjong_efficiency_service:
            return self.mahjong_efficiency_service.handle_action(client, action)
        if inputs.get("action") == "sword_raid_invite":
            raid_room_id = inputs.get("raid_room_id")
            command = inputs.get("command")
            if not raid_room_id or not command:
                return {
                    "ok": False,
                    "message": "레이드 초대 버튼 정보가 올바르지 않습니다.",
                }
            person = client.get_person(person_id)
            display_name = client.display_name_from_person(person, person_id)
            result = self.command_coordinator.execute(
                gateway=client,
                room_id=raid_room_id,
                person_id=person_id,
                display_name=display_name,
                text=command,
            )
            self.send_result(client, raid_room_id, person_id, result)
            try:
                client.send_direct_message(
                    person_id=person_id,
                    markdown=(
                        result.get("message")
                        if result.get("ok")
                        else f"처리 실패: {result.get('message')}"
                    ),
                )
            except Exception:
                logger.exception("레이드 초대 응답 DM 확인 메시지 전송 실패")
            return {"ok": True, "raid_invite": True}
        command_text = self.card_builder.extract_command(action)
        card_token = self.card_builder.extract_card_token(action)
        if not self.is_latest_card(room_id, card_token) and not self.can_accept_stale_card(
            room_id, command_text
        ):
            result = {
                "ok": False,
                "message": "이전 카드의 버튼입니다. 가장 아래 최신 카드에서 다시 눌러주세요.",
                "status": self.get_game(room_id).status(),
            }
            self.send_result(client, room_id, person_id, result)
            return {"ok": True, "ignored": True, "reason": "stale card action"}

        person = client.get_person(person_id)
        display_name = client.display_name_from_person(person, person_id)
        if self.is_game_selection(command_text):
            result = self.handle_game_selection(room_id, command_text)
        elif (
            isinstance(self.get_game(room_id), SwordUpgradeGame)
            and command_text.strip() in _SWORD_CHAT_ONLY_COMMANDS
        ):
            result = {
                "ok": False,
                "message": "검 강화는 채팅으로만 가능합니다. `@FSS 강화`를 입력해주세요.",
                "status": self.get_game(room_id).status(),
            }
        else:
            result = self.command_coordinator.execute(
                gateway=client,
                room_id=room_id,
                person_id=person_id,
                display_name=display_name,
                text=command_text,
            )
        if self.should_ignore_result(command_text, result):
            return {"ok": True, "ignored": True, "reason": "out_of_turn_button_action"}
        self.send_result(client, room_id, person_id, result)
        return {"ok": True}
