from typing import NotRequired, TypedDict


class DirectMessage(TypedDict):
    person_id: str
    message: str


class GameResponse(TypedDict):
    ok: bool
    message: str
    status: NotRequired[str]
    private: NotRequired[bool]
    public_message: NotRequired[str | None]
    silent_public: NotRequired[bool]
    deal_private_cards: NotRequired[bool]
    direct_messages: NotRequired[list[DirectMessage]]
    abort_on_dm_failure: NotRequired[bool]
    _start_snapshot: NotRequired[dict]
