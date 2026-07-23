from contextlib import asynccontextmanager
from datetime import datetime, timezone
import logging
import os
import secrets
import threading
from uuid import uuid4

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from starlette.concurrency import run_in_threadpool

from app.core.game_registry import GameType, create_game, plugin_for_type
from app.core.application_container import ApplicationContainer
from app.domain.game import GamePhase, HoldemGame
from app.games.dice.domain.game import DiceGame
from app.games.dice.services.dice_bot_service import DiceBotService
from app.games.fool_liar.domain.game import FoolLiarGame
from app.games.fool_liar.services.fool_liar_bot_service import FoolLiarBotService
from app.games.mahjong_efficiency.service import MahjongEfficiencyService
from app.games.mahjong_efficiency.battle_service import MahjongBattleService
from app.services.game_command_coordinator import (
    GameCommandCoordinator,
    should_refresh_timer_after_command,
)
from app.services.admin_command_service import AdminCommandService
from app.services.turn_timeout_handler import TurnTimeoutHandler
from app.services.turn_timer_service import TurnTimerService
from app.services.holdem_bot_service import HoldemBotService
from app.services.webex_client import WebexClient
from app.platforms.base import PlatformGateway
from app.platforms.webex.webhook_router import route_webex_event
from app.platforms.webex.debug_router import router as webex_debug_router
from app.platforms.webex.event_handler import WebexEventHandler
from app.platforms.webex.response_sender import WebexResponseSender
from app.platforms.webex.action_policy import (
    can_accept_stale_action,
    is_out_of_turn_result,
    is_turn_action,
    should_silently_ignore,
)
from app.api.game_debug_router import create_game_debug_router


def _configure_app_logging() -> None:
    app_logger = logging.getLogger("app")
    app_logger.setLevel(logging.INFO)
    if app_logger.handlers:
        return

    handler = logging.StreamHandler()
    handler.setFormatter(
        logging.Formatter("%(levelname)s: %(name)s: %(message)s")
    )
    app_logger.addHandler(handler)


_configure_app_logging()


DEBUG_ROOM_ID = "debug-room"
FORCE_RESET_ADMIN_EMAIL = os.getenv("FSS_ADMIN_EMAIL", "sh_lee@lotte.net")
ADDITIONAL_FORCE_RESET_ADMIN_EMAILS = ("ms-kim1@lotte.net",)
RANKING_RESET_ADMIN_EMAIL = FORCE_RESET_ADMIN_EMAIL

game = HoldemGame()
PROCESSED_WEBHOOK_ID_LIMIT = 5000
container = ApplicationContainer.create(PROCESSED_WEBHOOK_ID_LIMIT)
room_manager = container.room_manager
# Backward-compatible views while endpoints and tests migrate to RoomManager.
room_games = room_manager.games
room_game_types = room_manager.game_types
latest_card_tokens = room_manager.card_tokens
processed_webhook_ids = room_manager.processed_webhook_ids
room_locks = room_manager.room_locks
TURN_TIMEOUT_SECONDS = 60
turn_timer_factory = threading.Timer
turn_timer_manager = container.turn_timer_manager
# Backward-compatible views while timer callers migrate.
turn_timers = turn_timer_manager.timers
turn_timer_generations = turn_timer_manager.generations
turn_timer_lock = turn_timer_manager.lock

game_store = container.game_store
stats_store = container.stats_store
command_parser = container.command_parser
webex_card_builder = container.webex_card_builder
mahjong_efficiency_service = MahjongEfficiencyService(command_parser=command_parser)
mahjong_battle_service = MahjongBattleService(
    webex_client_factory=WebexClient,
    command_parser=command_parser,
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    try:
        loaded_games = game_store.load_all()
        loaded_game_types = game_store.load_game_types()
        loaded_card_tokens = game_store.load_card_tokens()
        loaded_processed_ids = game_store.load_processed_webhook_ids()

        room_manager.restore(
            loaded_games,
            loaded_game_types,
            loaded_card_tokens,
            loaded_processed_ids,
        )

        print(f"GAME STORE LOADED: {len(loaded_games)} room(s)")
        print(f"CARD TOKENS LOADED: {len(loaded_card_tokens)} room(s)")
        _refresh_all_turn_timers()

    except Exception as e:
        print("GAME STORE LOAD SKIPPED:", str(e))

    try:
        webex_client = WebexClient()
        result = webex_client.ensure_required_webhooks()

        print("WEBEX WEBHOOK AUTO SETUP:", result)

    except Exception as e:
        print("WEBEX WEBHOOK AUTO SETUP SKIPPED:", str(e))

    mahjong_battle_service.restore_timers()

    yield

    mahjong_battle_service.stop()

    try:
        game_store.save_all(
            room_games, latest_card_tokens, room_game_types, processed_webhook_ids
        )

        print(f"GAME STORE SAVED: {len(room_games)} room(s)")
        print(f"CARD TOKENS SAVED: {len(latest_card_tokens)} room(s)")

    except Exception as e:
        print("GAME STORE SAVE SKIPPED:", str(e))


app = FastAPI(
    title="FSS Holdem Bot",
    lifespan=lifespan,
)


@app.middleware("http")
async def protect_debug_api(request: Request, call_next):
    if not request.url.path.startswith("/debug"):
        return await call_next(request)

    enabled = os.getenv("FSS_DEBUG_API_ENABLED", "false").strip().lower()
    if enabled not in {"1", "true", "yes", "on"}:
        return JSONResponse(status_code=404, content={"detail": "Not Found"})

    expected_token = os.getenv("FSS_DEBUG_API_TOKEN", "").strip()
    supplied_token = request.headers.get("X-FSS-Debug-Token", "")
    if expected_token and not secrets.compare_digest(supplied_token, expected_token):
        return JSONResponse(status_code=403, content={"detail": "Forbidden"})

    return await call_next(request)


app.include_router(webex_debug_router)


def get_game_for_room(room_id: str | None = None) -> HoldemGame | DiceGame | FoolLiarGame:
    if room_id is None or room_id == DEBUG_ROOM_ID:
        return game

    if room_id not in room_games:
        current_game, created = room_manager.get_or_create_game(room_id)
        if created:
            save_room_games()
        return current_game

    return room_games[room_id]


def get_game_type_for_room(room_id: str | None = None) -> GameType:
    if room_id is None or room_id == DEBUG_ROOM_ID:
        if isinstance(game, DiceGame):
            return GameType.DICE
        if isinstance(game, FoolLiarGame):
            return GameType.FOOL_LIAR
        return GameType.HOLDEM

    return room_manager.game_type(room_id)


def save_room_games() -> None:
    game_store.save_all(
        room_games, latest_card_tokens, room_game_types, processed_webhook_ids
    )


def _get_room_lock(room_id: str) -> threading.RLock:
    return room_manager.room_lock(room_id)


def _is_webhook_processed(event_id: str) -> bool:
    return room_manager.is_webhook_processed(event_id)


def _mark_webhook_processed(event_id: str) -> None:
    room_manager.mark_webhook_processed(event_id)


def _command_coordinator() -> GameCommandCoordinator:
    return GameCommandCoordinator(
        command_parser=command_parser,
        stats_store=stats_store,
        get_game=get_game_for_room,
        get_game_type=get_game_type_for_room,
        save_state=save_room_games,
        refresh_timer=_refresh_turn_timer,
        should_refresh_timer=_should_refresh_timer_after_command,
        debug_room_id=DEBUG_ROOM_ID,
    )


def get_bot_service(room_id: str | None = None) -> HoldemBotService | DiceBotService | FoolLiarBotService:
    return _command_coordinator().service_for_room(room_id or DEBUG_ROOM_ID)


def _create_latest_card_token(room_id: str) -> str:
    card_token = str(uuid4())
    latest_card_tokens[room_id] = card_token
    save_room_games()
    return card_token


def _is_latest_card_action(room_id: str, card_token: str | None) -> bool:
    latest_card_token = latest_card_tokens.get(room_id)

    if not latest_card_token:
        return False

    if not card_token:
        return False

    return latest_card_token == card_token


def _active_turn_player_id(current_game: HoldemGame | DiceGame | FoolLiarGame) -> str | None:
    return _timer_service().active_actor(current_game)


def _should_schedule_turn_timer(current_game: HoldemGame | DiceGame | FoolLiarGame) -> bool:
    return _timer_service().should_schedule(current_game)


def _game_type_for_instance(current_game) -> GameType:
    if isinstance(current_game, DiceGame):
        return GameType.DICE
    if isinstance(current_game, FoolLiarGame):
        return GameType.FOOL_LIAR
    return GameType.HOLDEM


def _next_turn_timer_generation_locked(room_id: str) -> int:
    return turn_timer_manager.next_generation(room_id)


def _timer_service() -> TurnTimerService:
    return TurnTimerService(
        manager=turn_timer_manager,
        timer_factory=turn_timer_factory,
        default_timeout_seconds=TURN_TIMEOUT_SECONDS,
        get_game=get_game_for_room,
        room_ids=lambda: list(room_games),
        timeout_callback=_handle_turn_timeout,
    )


def _cancel_turn_timer(room_id: str) -> None:
    _timer_service().cancel(room_id)


def _refresh_turn_timer(room_id: str) -> None:
    _timer_service().refresh(room_id)


def _refresh_all_turn_timers() -> None:
    _timer_service().refresh_all()


def _is_current_turn_timer(
    room_id: str,
    generation: int,
    person_id: str,
) -> bool:
    return _timer_service().is_current(room_id, generation, person_id)


def _handle_turn_timeout(
    room_id: str,
    generation: int,
    person_id: str,
) -> None:
    with _get_room_lock(room_id):
        _handle_turn_timeout_locked(room_id, generation, person_id)


def _handle_turn_timeout_locked(
    room_id: str,
    generation: int,
    person_id: str,
) -> None:
    TurnTimeoutHandler(
        is_current_timer=_is_current_turn_timer,
        cancel_timer=_cancel_turn_timer,
        get_game=get_game_for_room,
        get_service=get_bot_service,
        save_state=save_room_games,
        webex_client_factory=WebexClient,
        dispatch_direct_messages=_dispatch_direct_messages,
        send_result=_send_webex_result,
        refresh_timer=_refresh_turn_timer,
    ).handle(room_id, generation, person_id)


def _should_refresh_timer_after_command(
    command_text: str,
    result: dict,
) -> bool:
    return should_refresh_timer_after_command(command_parser, command_text, result)


def _replace_game_for_admin(room_id: str, game_type: GameType):
    global game
    if room_id == DEBUG_ROOM_ID:
        game = create_game(game_type)
        return game
    return room_manager.replace_game(room_id, game_type)


def _admin_service() -> AdminCommandService:
    return AdminCommandService(
        command_parser=command_parser,
        admin_email=FORCE_RESET_ADMIN_EMAIL,
        stats_store=stats_store,
        get_game=get_game_for_room,
        get_game_type=get_game_type_for_room,
        replace_game=_replace_game_for_admin,
        cancel_timer=_cancel_turn_timer,
        clear_card_token=lambda room_id: latest_card_tokens.pop(room_id, None),
        save_state=save_room_games,
        additional_force_reset_emails=ADDITIONAL_FORCE_RESET_ADMIN_EMAILS,
    )


def _is_force_reset_command(command_text: str) -> bool:
    return _admin_service().is_force_reset(command_text)


def _is_ranking_reset_command(command_text: str) -> bool:
    return _admin_service().is_ranking_reset(command_text)


def _is_force_reset_admin(person_email: str | None) -> bool:
    return _admin_service().is_force_reset_admin(person_email)


def _is_ranking_reset_admin(person_email: str | None) -> bool:
    return _admin_service().is_admin(person_email)


def _force_reset_room(room_id: str) -> dict:
    return _admin_service().force_reset(room_id)


def _handle_force_reset_command(
    room_id: str,
    person_email: str | None,
) -> dict:
    return _admin_service().handle_force_reset(room_id, person_email)


def _game_selection_from_command(command_text: str) -> GameType | None:
    return _admin_service().selection_from_command(command_text)


def _is_game_selection_command(command_text: str) -> bool:
    return _admin_service().is_game_selection(command_text)


def _can_select_game(current_game: HoldemGame | DiceGame | FoolLiarGame) -> bool:
    return plugin_for_type(_game_type_for_instance(current_game)).can_change(current_game)


def _handle_game_selection_command(room_id: str, command_text: str) -> dict:
    return _admin_service().select_game(room_id, command_text)


def _handle_ranking_reset_command(
    room_id: str,
    person_email: str | None,
) -> dict:
    return _admin_service().reset_ranking(room_id, person_email)


@app.get("/")
def root():
    return {
        "message": "FSS Holdem Bot server is running"
    }


@app.get("/health")
def health():
    return {
        "status": "ok"
    }


@app.post("/webex/webhook")
async def webex_webhook(request: Request):
    payload = await request.json()

    try:
        return await run_in_threadpool(
            route_webex_event,
            payload,
            _handle_webex_message_created,
            _handle_webex_attachment_action_created,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


def _handle_webex_message_created(payload: dict) -> dict:
    return _webex_event_handler().process_event(
        payload, "message", _handle_webex_message_created_locked
    )


def _webex_event_handler() -> WebexEventHandler:
    return WebexEventHandler(
        webex_client_factory=WebexClient,
        command_coordinator=_command_coordinator(),
        card_builder=webex_card_builder,
        get_game=get_game_for_room,
        send_result=_send_webex_result,
        handle_force_reset=_handle_force_reset_command,
        handle_game_selection=_handle_game_selection_command,
        handle_ranking_reset=_handle_ranking_reset_command,
        is_force_reset=_is_force_reset_command,
        is_game_selection=_is_game_selection_command,
        is_ranking_reset=_is_ranking_reset_command,
        is_latest_card=_is_latest_card_action,
        can_accept_stale_card=lambda room_id, command: _can_accept_stale_card_action(
            room_id=room_id, command_text=command
        ),
        should_ignore_result=lambda command, result: _should_silently_ignore_result(
            command_text=command, result=result
        ),
        room_lock=_get_room_lock,
        is_processed=_is_webhook_processed,
        mark_processed=_mark_webhook_processed,
        save_state=save_room_games,
        mahjong_efficiency_service=mahjong_efficiency_service,
        mahjong_battle_service=mahjong_battle_service,
    )


def _handle_webex_message_created_locked(payload: dict) -> dict:
    return _webex_event_handler().handle_message_locked(payload)

def _is_turn_action_command(command_text: str) -> bool:
    return is_turn_action(command_text)


def _is_out_of_turn_result(result: dict) -> bool:
    return is_out_of_turn_result(result)


def _should_silently_ignore_result(
    command_text: str,
    result: dict,
) -> bool:
    return should_silently_ignore(command_text, result)

def _can_accept_stale_card_action(
    room_id: str,
    command_text: str,
) -> bool:
    return can_accept_stale_action(get_game_for_room(room_id), command_text)

def _handle_webex_attachment_action_created(payload: dict) -> dict:
    return _webex_event_handler().process_event(
        payload, "action", _handle_webex_attachment_action_created_locked
    )


def _handle_webex_attachment_action_created_locked(payload: dict) -> dict:
    return _webex_event_handler().handle_attachment_locked(payload)

def _build_available_card_actions(
    current_game: HoldemGame | DiceGame | FoolLiarGame,
) -> list[tuple[str, str]]:
    actions = plugin_for_type(_game_type_for_instance(current_game)).build_actions(current_game)
    existing = {command for _, command in actions}
    for action in [("개인 패효율", "패효율 시작"), ("패효율 대결", "패효율 대결")]:
        if action[1] not in existing:
            actions.append(action)
    return actions


def _response_sender() -> WebexResponseSender:
    return WebexResponseSender(
        get_game=get_game_for_room,
        card_builder=webex_card_builder,
        build_actions=_build_available_card_actions,
        create_card_token=_create_latest_card_token,
        rollback_holdem_start=_rollback_holdem_start,
        save_state=save_room_games,
    )


def _send_private_cards_to_all(
    webex_client: PlatformGateway,
    current_game: HoldemGame | DiceGame | FoolLiarGame,
) -> list[str]:
    return _response_sender().send_private_cards(webex_client, current_game)


def _rollback_holdem_start(room_id: str, snapshot: dict) -> HoldemGame:
    global game
    restored = HoldemGame.from_dict(snapshot)
    if room_id == DEBUG_ROOM_ID:
        game = restored
    else:
        room_manager.set_game(room_id, restored, GameType.HOLDEM)
    return restored


def _preflight_start_direct_messages(
    webex_client: PlatformGateway,
    current_game: HoldemGame | DiceGame | FoolLiarGame,
    command_text: str,
) -> dict | None:
    return _command_coordinator().preflight_start(
        webex_client, current_game, command_text
    )


def _dispatch_direct_messages(
    webex_client: PlatformGateway,
    result: dict,
    current_game: HoldemGame | DiceGame | FoolLiarGame | None = None,
) -> None:
    _command_coordinator().dispatch_direct_messages(
        webex_client, result, current_game
    )
def _send_webex_result(
    webex_client: PlatformGateway,
    room_id: str,
    person_id: str,
    result: dict,
) -> None:
    _response_sender().send(webex_client, room_id, person_id, result)


app.include_router(
    create_game_debug_router(
        get_debug_game=lambda: game,
        get_game=get_game_for_room,
        get_service=get_bot_service,
        get_admin_service=_admin_service,
        save_state=save_room_games,
        room_games=room_games,
        card_tokens=latest_card_tokens,
        debug_room_id=DEBUG_ROOM_ID,
    )
)
