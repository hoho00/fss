from fastapi import APIRouter
from pydantic import BaseModel

from app.services.webex_client import WebexClient


router = APIRouter(prefix="/debug/webex", tags=["debug-webex"])


class WebexSendRequest(BaseModel):
    markdown: str
    room_id: str | None = None


def _error(error: Exception) -> dict:
    return {"ok": False, "message": str(error)}


@router.get("/me")
def debug_webex_me():
    try:
        me = WebexClient().get_me()
        return {
            "ok": True,
            "person_id": me.get("id"),
            "display_name": me.get("displayName"),
            "emails": me.get("emails"),
            "raw": me,
        }
    except Exception as error:
        return _error(error)


@router.get("/rooms")
def debug_webex_rooms():
    try:
        rooms = WebexClient().list_rooms()
        return {
            "ok": True,
            "rooms": [
                {
                    "id": room.get("id"),
                    "title": room.get("title"),
                    "type": room.get("type"),
                    "created": room.get("created"),
                    "lastActivity": room.get("lastActivity"),
                }
                for room in rooms.get("items", [])
            ],
        }
    except Exception as error:
        return _error(error)


@router.post("/send")
def debug_webex_send(body: WebexSendRequest):
    try:
        result = WebexClient().send_room_message(body.markdown, body.room_id)
        return {"ok": True, "message": "Webex 방에 메시지를 보냈습니다.", "webex_result": result}
    except Exception as error:
        return _error(error)


@router.get("/webhooks")
def debug_webex_webhooks():
    try:
        webhooks = WebexClient().list_webhooks()
        return {
            "ok": True,
            "webhooks": [
                {
                    "id": item.get("id"),
                    "name": item.get("name"),
                    "targetUrl": item.get("targetUrl"),
                    "resource": item.get("resource"),
                    "event": item.get("event"),
                    "filter": item.get("filter"),
                    "status": item.get("status"),
                    "created": item.get("created"),
                }
                for item in webhooks.get("items", [])
            ],
        }
    except Exception as error:
        return _error(error)


@router.post("/webhooks")
def debug_create_webex_webhook():
    try:
        webhook = WebexClient().create_messages_created_webhook()
        return {"ok": True, "message": "Webex messages webhook을 생성했습니다.", "webhook": webhook}
    except Exception as error:
        return _error(error)


@router.post("/webhooks/actions")
def debug_create_webex_attachment_actions_webhook():
    try:
        webhook = WebexClient().create_attachment_actions_created_webhook()
        return {"ok": True, "message": "Webex attachmentActions webhook을 생성했습니다.", "webhook": webhook}
    except Exception as error:
        return _error(error)


@router.delete("/webhooks/{webhook_id}")
def debug_delete_webex_webhook(webhook_id: str):
    try:
        WebexClient().delete_webhook(webhook_id)
        return {"ok": True, "message": "Webex webhook을 삭제했습니다.", "webhook_id": webhook_id}
    except Exception as error:
        return _error(error)
