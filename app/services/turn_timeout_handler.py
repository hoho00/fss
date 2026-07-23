from collections.abc import Callable
import logging

from app.domain.game import HoldemGame
from app.games.fool_liar.domain.game import FoolLiarGame
from app.games.fool_liar.services.fool_liar_bot_service import FoolLiarBotService


logger = logging.getLogger(__name__)


class TurnTimeoutHandler:
    def __init__(
        self,
        is_current_timer: Callable[[str, int, str], bool],
        cancel_timer: Callable[[str], None],
        get_game: Callable,
        get_service: Callable,
        save_state: Callable[[], None],
        webex_client_factory: Callable,
        dispatch_direct_messages: Callable,
        send_result: Callable,
        refresh_timer: Callable[[str], None],
    ):
        self.is_current_timer = is_current_timer
        self.cancel_timer = cancel_timer
        self.get_game = get_game
        self.get_service = get_service
        self.save_state = save_state
        self.webex_client_factory = webex_client_factory
        self.dispatch_direct_messages = dispatch_direct_messages
        self.send_result = send_result
        self.refresh_timer = refresh_timer

    def handle(self, room_id: str, generation: int, person_id: str) -> None:
        if not self.is_current_timer(room_id, generation, person_id):
            return
        self.cancel_timer(room_id)
        game = self.get_game(room_id)
        if isinstance(game, FoolLiarGame):
            service = self.get_service(room_id)
            if not isinstance(service, FoolLiarBotService):
                raise TypeError("바보 라이어게임 서비스가 필요합니다.")
            result = service.timeout_result()
            self.save_state()
            try:
                client = self.webex_client_factory()
                self.dispatch_direct_messages(client, result, game)
                self.send_result(client, room_id, person_id, result)
            except Exception as error:
                self._log_delivery_failure(room_id, error)
            finally:
                self.refresh_timer(room_id)
            return

        if not isinstance(game, HoldemGame):
            return
        player_index = game._find_player_index(person_id)
        if player_index is None:
            return
        player_name = game.players[player_index].display_name
        timeout_count = game.record_turn_timeout(person_id)
        fold_message = game.fold(person_id)
        result = {
            "ok": True,
            "message": (
                f"{player_name}님이 시간 초과로 자동 폴드되었습니다. "
                f"({min(timeout_count, 3)}/3) - 3번 초과 시 게임 강퇴\n{fold_message}"
            ),
            "status": game.status(),
        }
        self.save_state()
        try:
            client = self.webex_client_factory()
            self.send_result(client, room_id, person_id, result)
        except Exception as error:
            self._log_delivery_failure(room_id, error)
        finally:
            self.refresh_timer(room_id)

    @staticmethod
    def _log_delivery_failure(room_id: str, error: Exception) -> None:
        logger.warning(
            "턴 타임아웃 결과를 Webex 방 %s에 전송하지 못했습니다: %s: %s",
            room_id,
            type(error).__name__,
            error,
        )
