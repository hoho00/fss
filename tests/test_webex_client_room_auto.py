import httpx

from app.services.webex_client import WebexClient


class FakeResponse:
    def raise_for_status(self):
        return None

    def json(self):
        return {
            "ok": True,
        }


def test_send_room_message_uses_given_room_id_when_env_room_id_is_missing(monkeypatch):
    sent = {}

    monkeypatch.setenv("WEBEX_BOT_TOKEN", "test-token")
    monkeypatch.delenv("WEBEX_ROOM_ID", raising=False)

    def fake_post(url, headers, json, timeout):
        sent["url"] = url
        sent["headers"] = headers
        sent["json"] = json
        sent["timeout"] = timeout
        return FakeResponse()

    monkeypatch.setattr(httpx, "post", fake_post)

    client = WebexClient()
    client.send_room_message(
        room_id="room-123",
        markdown="hello",
    )

    assert sent["json"]["roomId"] == "room-123"
    assert sent["json"]["markdown"] == "hello"


def test_send_room_card_uses_given_room_id_when_env_room_id_is_missing(monkeypatch):
    sent = {}

    monkeypatch.setenv("WEBEX_BOT_TOKEN", "test-token")
    monkeypatch.delenv("WEBEX_ROOM_ID", raising=False)

    def fake_post(url, headers, json, timeout):
        sent["json"] = json
        return FakeResponse()

    monkeypatch.setattr(httpx, "post", fake_post)

    client = WebexClient()
    client.send_room_card(
        room_id="room-456",
        markdown="card message",
        card={
            "type": "AdaptiveCard",
            "version": "1.3",
            "body": [],
        },
    )

    assert sent["json"]["roomId"] == "room-456"
    assert sent["json"]["markdown"] == "card message"
    assert sent["json"]["attachments"][0]["contentType"] == "application/vnd.microsoft.card.adaptive"


def test_create_messages_webhook_without_room_id_has_no_room_filter(monkeypatch):
    sent = {}

    monkeypatch.setenv("WEBEX_BOT_TOKEN", "test-token")
    monkeypatch.setenv("WEBEX_WEBHOOK_TARGET_URL", "https://example.ngrok-free.app/webex/webhook")
    monkeypatch.setenv("WEBEX_WEBHOOK_NAME", "FSS Webhook")
    monkeypatch.delenv("WEBEX_ROOM_ID", raising=False)

    def fake_post(url, headers, json, timeout):
        sent["json"] = json
        return FakeResponse()

    monkeypatch.setattr(httpx, "post", fake_post)

    client = WebexClient()
    client.create_messages_created_webhook()

    assert sent["json"]["name"] == "FSS Webhook"
    assert sent["json"]["resource"] == "messages"
    assert sent["json"]["event"] == "created"
    assert "filter" not in sent["json"]


def test_create_messages_webhook_with_room_id_keeps_room_filter(monkeypatch):
    sent = {}

    monkeypatch.setenv("WEBEX_BOT_TOKEN", "test-token")
    monkeypatch.setenv("WEBEX_ROOM_ID", "room-789")
    monkeypatch.setenv("WEBEX_WEBHOOK_TARGET_URL", "https://example.ngrok-free.app/webex/webhook")
    monkeypatch.setenv("WEBEX_WEBHOOK_NAME", "FSS Webhook")

    def fake_post(url, headers, json, timeout):
        sent["json"] = json
        return FakeResponse()

    monkeypatch.setattr(httpx, "post", fake_post)

    client = WebexClient()
    client.create_messages_created_webhook()

    assert sent["json"]["filter"] == "roomId=room-789"

def test_ensure_required_webhooks_creates_missing_webhooks(monkeypatch):
    calls = []

    monkeypatch.setenv("WEBEX_BOT_TOKEN", "test-token")
    monkeypatch.setenv("WEBEX_WEBHOOK_TARGET_URL", "https://example.ngrok-free.app/webex/webhook")
    monkeypatch.setenv("WEBEX_WEBHOOK_NAME", "FSS Webhook")
    monkeypatch.delenv("WEBEX_ROOM_ID", raising=False)

    def fake_get(url, headers, timeout):
        calls.append(("GET", url, None))

        class Response:
            def raise_for_status(self):
                return None

            def json(self):
                return {
                    "items": [],
                }

        return Response()

    def fake_post(url, headers, json, timeout):
        calls.append(("POST", url, json))

        class Response:
            def raise_for_status(self):
                return None

            def json(self):
                return {
                    "id": f"created-{json['resource']}",
                    **json,
                }

        return Response()

    def fake_delete(url, headers, timeout):
        calls.append(("DELETE", url, None))

        class Response:
            def raise_for_status(self):
                return None

        return Response()

    monkeypatch.setattr(httpx, "get", fake_get)
    monkeypatch.setattr(httpx, "post", fake_post)
    monkeypatch.setattr(httpx, "delete", fake_delete)

    client = WebexClient()
    result = client.ensure_required_webhooks()

    assert result["messages"]["status"] == "created"
    assert result["attachmentActions"]["status"] == "created"

    posted_resources = [
        payload["resource"]
        for method, url, payload in calls
        if method == "POST"
    ]

    assert "messages" in posted_resources
    assert "attachmentActions" in posted_resources


def test_ensure_required_webhooks_keeps_existing_correct_webhooks(monkeypatch):
    calls = []

    monkeypatch.setenv("WEBEX_BOT_TOKEN", "test-token")
    monkeypatch.setenv("WEBEX_WEBHOOK_TARGET_URL", "https://example.ngrok-free.app/webex/webhook")
    monkeypatch.setenv("WEBEX_WEBHOOK_NAME", "FSS Webhook")
    monkeypatch.delenv("WEBEX_ROOM_ID", raising=False)

    def fake_get(url, headers, timeout):
        calls.append(("GET", url, None))

        class Response:
            def raise_for_status(self):
                return None

            def json(self):
                return {
                    "items": [
                        {
                            "id": "hook-messages",
                            "name": "FSS Webhook",
                            "targetUrl": "https://example.ngrok-free.app/webex/webhook",
                            "resource": "messages",
                            "event": "created",
                            "filter": None,
                        },
                        {
                            "id": "hook-actions",
                            "name": "FSS Webhook Actions",
                            "targetUrl": "https://example.ngrok-free.app/webex/webhook",
                            "resource": "attachmentActions",
                            "event": "created",
                            "filter": None,
                        },
                    ],
                }

        return Response()

    def fake_post(url, headers, json, timeout):
        calls.append(("POST", url, json))
        raise AssertionError("정상 webhook이 있으면 새로 생성하면 안 됩니다.")

    def fake_delete(url, headers, timeout):
        calls.append(("DELETE", url, None))
        raise AssertionError("정상 webhook이 있으면 삭제하면 안 됩니다.")

    monkeypatch.setattr(httpx, "get", fake_get)
    monkeypatch.setattr(httpx, "post", fake_post)
    monkeypatch.setattr(httpx, "delete", fake_delete)

    client = WebexClient()
    result = client.ensure_required_webhooks()

    assert result["messages"]["status"] == "kept"
    assert result["attachmentActions"]["status"] == "kept"

    methods = [method for method, url, payload in calls]

    assert methods == ["GET"]


def test_ensure_required_webhooks_replaces_old_ngrok_url(monkeypatch):
    calls = []

    monkeypatch.setenv("WEBEX_BOT_TOKEN", "test-token")
    monkeypatch.setenv("WEBEX_WEBHOOK_TARGET_URL", "https://new.ngrok-free.app/webex/webhook")
    monkeypatch.setenv("WEBEX_WEBHOOK_NAME", "FSS Webhook")
    monkeypatch.delenv("WEBEX_ROOM_ID", raising=False)

    def fake_get(url, headers, timeout):
        calls.append(("GET", url, None))

        class Response:
            def raise_for_status(self):
                return None

            def json(self):
                return {
                    "items": [
                        {
                            "id": "old-messages",
                            "name": "FSS Webhook",
                            "targetUrl": "https://old.ngrok-free.app/webex/webhook",
                            "resource": "messages",
                            "event": "created",
                            "filter": None,
                        },
                        {
                            "id": "old-actions",
                            "name": "FSS Webhook Actions",
                            "targetUrl": "https://old.ngrok-free.app/webex/webhook",
                            "resource": "attachmentActions",
                            "event": "created",
                            "filter": None,
                        },
                    ],
                }

        return Response()

    def fake_post(url, headers, json, timeout):
        calls.append(("POST", url, json))

        class Response:
            def raise_for_status(self):
                return None

            def json(self):
                return {
                    "id": f"new-{json['resource']}",
                    **json,
                }

        return Response()

    def fake_delete(url, headers, timeout):
        calls.append(("DELETE", url, None))

        class Response:
            def raise_for_status(self):
                return None

        return Response()

    monkeypatch.setattr(httpx, "get", fake_get)
    monkeypatch.setattr(httpx, "post", fake_post)
    monkeypatch.setattr(httpx, "delete", fake_delete)

    client = WebexClient()
    result = client.ensure_required_webhooks()

    assert result["messages"]["status"] == "created"
    assert result["attachmentActions"]["status"] == "created"

    deleted_urls = [
        url
        for method, url, payload in calls
        if method == "DELETE"
    ]

    posted_payloads = [
        payload
        for method, url, payload in calls
        if method == "POST"
    ]

    assert any("old-messages" in url for url in deleted_urls)
    assert any("old-actions" in url for url in deleted_urls)

    assert any(payload["resource"] == "messages" for payload in posted_payloads)
    assert any(payload["resource"] == "attachmentActions" for payload in posted_payloads)