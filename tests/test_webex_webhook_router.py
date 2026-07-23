from app.platforms.webex.webhook_router import route_webex_event


def test_webex_router_dispatches_supported_resources():
    message_payload = {"event": "created", "resource": "messages"}
    action_payload = {"event": "created", "resource": "attachmentActions"}

    assert route_webex_event(message_payload, lambda payload: {"kind": "message"}, lambda payload: {}) == {"kind": "message"}
    assert route_webex_event(action_payload, lambda payload: {}, lambda payload: {"kind": "action"}) == {"kind": "action"}


def test_webex_router_ignores_unknown_or_non_created_events():
    ignored_event = route_webex_event(
        {"event": "updated", "resource": "messages"}, lambda payload: {}, lambda payload: {}
    )
    ignored_resource = route_webex_event(
        {"event": "created", "resource": "rooms"}, lambda payload: {}, lambda payload: {}
    )

    assert ignored_event["ignored"] is True
    assert ignored_resource["ignored"] is True
