from collections.abc import Callable


def route_webex_event(
    payload: dict,
    message_handler: Callable[[dict], dict],
    attachment_handler: Callable[[dict], dict],
) -> dict:
    if payload.get("event") != "created":
        return {
            "ok": True,
            "ignored": True,
            "reason": "created event가 아닙니다.",
        }

    resource = payload.get("resource")
    if resource == "messages":
        return message_handler(payload)
    if resource == "attachmentActions":
        return attachment_handler(payload)
    return {
        "ok": True,
        "ignored": True,
        "reason": "처리 대상 resource가 아닙니다.",
    }
