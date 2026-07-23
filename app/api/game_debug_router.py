from collections.abc import Callable

from fastapi import APIRouter
from pydantic import BaseModel

from app.domain.deck import Deck


class JoinRequest(BaseModel):
    person_id: str
    display_name: str


class ActionRequest(BaseModel):
    person_id: str


class RaiseRequest(BaseModel):
    person_id: str
    amount: int


class DebugCommandRequest(BaseModel):
    person_id: str
    display_name: str
    text: str
    room_id: str | None = None
    person_email: str | None = None


def create_game_debug_router(
    get_debug_game: Callable,
    get_game: Callable,
    get_service: Callable,
    get_admin_service: Callable,
    save_state: Callable[[], None],
    room_games: dict,
    card_tokens: dict,
    debug_room_id: str,
) -> APIRouter:
    router = APIRouter(prefix="/debug", tags=["debug-game"])

    @router.get("/deck")
    def debug_deck():
        deck = Deck()
        deck.shuffle()
        return {
            "drawn_cards": [str(deck.draw()) for _ in range(5)],
            "remaining_count": deck.remaining_count(),
        }

    @router.post("/command")
    def debug_command(body: DebugCommandRequest):
        room_id = body.room_id or debug_room_id
        admin = get_admin_service()
        if admin.is_force_reset(body.text):
            return admin.handle_force_reset(room_id, body.person_email)
        if admin.is_game_selection(body.text):
            return admin.select_game(room_id, body.text)
        if admin.is_ranking_reset(body.text):
            return admin.reset_ranking(room_id, body.person_email)
        result = get_service(room_id).handle_text_command(
            person_id=body.person_id,
            display_name=body.display_name,
            text=body.text,
        )
        if result.get("ok") is False and "status" not in result:
            result["status"] = get_game(room_id).status()
        save_state()
        return result

    def execute(action: Callable) -> dict:
        game = get_debug_game()
        try:
            message = action(game)
            return {"ok": True, "message": message, "status": game.status()}
        except Exception as error:
            return {"ok": False, "message": str(error)}

    @router.post("/join")
    def debug_join(body: JoinRequest):
        return execute(lambda game: game.join(body.person_id, body.display_name))

    @router.post("/start")
    def debug_start():
        return execute(lambda game: game.start())

    @router.post("/call")
    def debug_call(body: ActionRequest):
        return execute(lambda game: game.call(body.person_id))

    @router.post("/check")
    def debug_check(body: ActionRequest):
        return execute(lambda game: game.check(body.person_id))

    @router.post("/raise")
    def debug_raise(body: RaiseRequest):
        return execute(lambda game: game.raise_to(body.person_id, body.amount))

    @router.post("/fold")
    def debug_fold(body: ActionRequest):
        return execute(lambda game: game.fold(body.person_id))

    @router.get("/private-cards/{person_id}")
    def debug_private_cards(person_id: str):
        try:
            return {"ok": True, "message": get_debug_game().private_cards(person_id)}
        except Exception as error:
            return {"ok": False, "message": str(error)}

    @router.get("/status")
    def debug_status():
        return {"ok": True, "status": get_debug_game().status()}

    @router.get("/rooms/status")
    def debug_rooms_status():
        return {
            "ok": True,
            "rooms": {room_id: game.status() for room_id, game in room_games.items()},
            "latest_card_tokens": card_tokens,
        }

    return router
