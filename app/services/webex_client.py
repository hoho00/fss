import os

import httpx
from dotenv import load_dotenv


load_dotenv()


class WebexClient:
    def __init__(self):
        self.bot_token = os.getenv("WEBEX_BOT_TOKEN")
        self.room_id = os.getenv("WEBEX_ROOM_ID")
        self.bot_person_id = os.getenv("WEBEX_BOT_PERSON_ID")
        self.webhook_name = os.getenv("WEBEX_WEBHOOK_NAME", "FSS Webhook")
        self.webhook_target_url = os.getenv("WEBEX_WEBHOOK_TARGET_URL")

        if not self.bot_token:
            raise ValueError("WEBEX_BOT_TOKEN 값이 없습니다.")

        self.base_url = "https://webexapis.com/v1"

    def get_me(self) -> dict:
        response = httpx.get(
            f"{self.base_url}/people/me",
            headers=self._headers(),
            timeout=10,
        )
        response.raise_for_status()
        return response.json()

    def get_person(self, person_id: str) -> dict:
        response = httpx.get(
            f"{self.base_url}/people/{person_id}",
            headers=self._headers(),
            timeout=10,
        )
        response.raise_for_status()
        return response.json()

    def list_rooms(self) -> dict:
        response = httpx.get(
            f"{self.base_url}/rooms",
            headers=self._headers(),
            params={
                "max": 100,
            },
            timeout=10,
        )
        response.raise_for_status()
        return response.json()

    def get_message(self, message_id: str) -> dict:
        response = httpx.get(
            f"{self.base_url}/messages/{message_id}",
            headers=self._headers(),
            timeout=10,
        )
        response.raise_for_status()
        return response.json()

    def get_room(self, room_id: str) -> dict:
        response = httpx.get(
            f"{self.base_url}/rooms/{room_id}",
            headers=self._headers(),
            timeout=10,
        )
        response.raise_for_status()
        return response.json()

    def get_attachment_action(self, action_id: str) -> dict:
        response = httpx.get(
            f"{self.base_url}/attachment/actions/{action_id}",
            headers=self._headers(),
            timeout=10,
        )
        response.raise_for_status()
        return response.json()

    def send_room_message(self, markdown: str, room_id: str | None = None) -> dict:
        target_room_id = room_id or self.room_id

        if not target_room_id:
            raise ValueError("room_id가 없습니다. 메시지가 들어온 roomId를 넘겨야 합니다.")

        response = httpx.post(
            f"{self.base_url}/messages",
            headers=self._headers(),
            json={
                "roomId": target_room_id,
                "markdown": markdown,
            },
            timeout=10,
        )
        response.raise_for_status()
        return response.json()

    def send_room_card(
        self,
        markdown: str,
        card: dict,
        room_id: str | None = None,
    ) -> dict:
        target_room_id = room_id or self.room_id

        if not target_room_id:
            raise ValueError("room_id가 없습니다. 메시지가 들어온 roomId를 넘겨야 합니다.")

        response = httpx.post(
            f"{self.base_url}/messages",
            headers=self._headers(),
            json={
                "roomId": target_room_id,
                "markdown": markdown,
                "attachments": [
                    {
                        "contentType": "application/vnd.microsoft.card.adaptive",
                        "content": card,
                    }
                ],
            },
            timeout=10,
        )
        response.raise_for_status()
        return response.json()

    def send_direct_message(
        self,
        person_id: str,
        markdown: str,
        card: dict | None = None,
    ) -> dict:
        payload: dict = {
            "toPersonId": person_id,
            "markdown": markdown,
        }
        if card is not None:
            payload["attachments"] = [
                {
                    "contentType": "application/vnd.microsoft.card.adaptive",
                    "content": card,
                }
            ]
        response = httpx.post(
            f"{self.base_url}/messages",
            headers=self._headers(),
            json=payload,
            timeout=10,
        )
        response.raise_for_status()
        return response.json()

    def list_webhooks(self) -> dict:
        response = httpx.get(
            f"{self.base_url}/webhooks",
            headers=self._headers(),
            timeout=10,
        )
        response.raise_for_status()
        return response.json()

    def create_messages_created_webhook(self) -> dict:
        if not self.webhook_target_url:
            raise ValueError("WEBEX_WEBHOOK_TARGET_URL 값이 없습니다.")

        payload = {
            "name": self.webhook_name,
            "targetUrl": self.webhook_target_url,
            "resource": "messages",
            "event": "created",
        }

        # WEBEX_ROOM_ID가 있으면 특정 방만 받음.
        # 없으면 봇이 들어간 방의 메시지를 받고, 실제 roomId는 webhook에서 자동 사용.
        if self.room_id:
            payload["filter"] = f"roomId={self.room_id}"

        response = httpx.post(
            f"{self.base_url}/webhooks",
            headers=self._headers(),
            json=payload,
            timeout=10,
        )
        response.raise_for_status()
        return response.json()

    def create_attachment_actions_created_webhook(self) -> dict:
        if not self.webhook_target_url:
            raise ValueError("WEBEX_WEBHOOK_TARGET_URL 값이 없습니다.")

        response = httpx.post(
            f"{self.base_url}/webhooks",
            headers=self._headers(),
            json={
                "name": f"{self.webhook_name} Actions",
                "targetUrl": self.webhook_target_url,
                "resource": "attachmentActions",
                "event": "created",
            },
            timeout=10,
        )
        response.raise_for_status()
        return response.json()

    def ensure_required_webhooks(self) -> dict:
        if not self.webhook_target_url:
            raise ValueError("WEBEX_WEBHOOK_TARGET_URL 값이 없습니다.")

        webhooks = self.list_webhooks()
        items = webhooks.get("items", [])

        messages_result = self._ensure_one_webhook(
            items=items,
            name=self.webhook_name,
            resource="messages",
            event="created",
            target_url=self.webhook_target_url,
            expected_filter=self._expected_messages_filter(),
            create_func=self.create_messages_created_webhook,
        )

        actions_result = self._ensure_one_webhook(
            items=items,
            name=f"{self.webhook_name} Actions",
            resource="attachmentActions",
            event="created",
            target_url=self.webhook_target_url,
            expected_filter=None,
            create_func=self.create_attachment_actions_created_webhook,
        )

        return {
            "messages": messages_result,
            "attachmentActions": actions_result,
        }

    def _ensure_one_webhook(
        self,
        items: list[dict],
        name: str,
        resource: str,
        event: str,
        target_url: str,
        expected_filter: str | None,
        create_func,
    ) -> dict:
        matched_hooks = [
            webhook
            for webhook in items
            if webhook.get("name") == name
            and webhook.get("resource") == resource
            and webhook.get("event") == event
        ]

        kept_webhook = None
        deleted_webhook_ids = []

        for webhook in matched_hooks:
            webhook_id = webhook.get("id")
            actual_target_url = webhook.get("targetUrl")
            actual_filter = self._normalize_filter(webhook.get("filter"))

            is_same_target = actual_target_url == target_url
            is_same_filter = actual_filter == expected_filter

            if kept_webhook is None and is_same_target and is_same_filter:
                kept_webhook = webhook
                continue

            if webhook_id:
                self.delete_webhook(webhook_id)
                deleted_webhook_ids.append(webhook_id)

        if kept_webhook is not None:
            return {
                "status": "kept",
                "webhook_id": kept_webhook.get("id"),
                "deleted_webhook_ids": deleted_webhook_ids,
            }

        created_webhook = create_func()

        return {
            "status": "created",
            "webhook_id": created_webhook.get("id"),
            "deleted_webhook_ids": deleted_webhook_ids,
        }

    def _expected_messages_filter(self) -> str | None:
        if self.room_id:
            return f"roomId={self.room_id}"

        return None

    def _normalize_filter(self, value: str | None) -> str | None:
        if not value:
            return None

        return value

    def delete_webhook(self, webhook_id: str) -> None:
        response = httpx.delete(
            f"{self.base_url}/webhooks/{webhook_id}",
            headers=self._headers(),
            timeout=10,
        )
        response.raise_for_status()

    def is_bot_message(self, message: dict) -> bool:
        if not self.bot_person_id:
            return False

        return message.get("personId") == self.bot_person_id

    def display_name_from_person(self, person: dict, fallback: str) -> str:
        display_name = person.get("displayName")

        if display_name:
            return display_name

        emails = person.get("emails") or []

        if emails:
            return emails[0]

        return fallback

    def _headers(self) -> dict:
        return {
            "Authorization": f"Bearer {self.bot_token}",
            "Content-Type": "application/json",
        }
