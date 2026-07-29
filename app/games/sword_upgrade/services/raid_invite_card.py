def build_raid_invite_card(room_id: str, starter_name: str) -> dict:
    """DM용 보스 레이드 수락/거부 카드."""
    return {
        "$schema": "http://adaptivecards.io/schemas/adaptive-card.json",
        "type": "AdaptiveCard",
        "version": "1.3",
        "body": [
            {
                "type": "TextBlock",
                "text": "보스 레이드 초대",
                "weight": "Bolder",
                "size": "Medium",
                "wrap": True,
            },
            {
                "type": "TextBlock",
                "text": f"{starter_name}님이 보스 레이드를 시작했습니다. 참여하시겠습니까?",
                "wrap": True,
            },
        ],
        "actions": [
            {
                "type": "Action.Submit",
                "title": "수락",
                "data": {
                    "action": "sword_raid_invite",
                    "command": "레이드수락",
                    "raid_room_id": room_id,
                },
            },
            {
                "type": "Action.Submit",
                "title": "거부",
                "data": {
                    "action": "sword_raid_invite",
                    "command": "레이드거부",
                    "raid_room_id": room_id,
                },
            },
        ],
    }
