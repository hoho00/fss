from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class PlatformUser:
    user_id: str
    display_name: str
    email: str | None = None


@dataclass(frozen=True)
class IncomingCommand:
    event_id: str
    room_id: str
    user: PlatformUser
    text: str


class PlatformGateway(Protocol):
    def send_direct_message(
        self,
        person_id: str,
        markdown: str,
        card: dict | None = None,
    ) -> dict: ...

    def send_room_card(
        self,
        markdown: str,
        card: dict,
        room_id: str | None = None,
    ) -> dict: ...
