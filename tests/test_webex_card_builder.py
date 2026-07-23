import pytest

from app.services.webex_card_builder import WebexCardBuilder


def test_action_card_contains_holdem_buttons():
    builder = WebexCardBuilder()

    card = builder.build_action_card("현재 상태: WAITING")

    assert card["type"] == "AdaptiveCard"
    assert card["version"] == "1.3"

    titles = [
        action["title"]
        for action in card["actions"]
    ]

    commands = [
        action["data"]["command"]
        for action in card["actions"]
    ]

    assert "참가" in titles
    assert "시작" in titles
    assert "상태" in titles
    assert "내카드" in titles
    assert "체크" in titles
    assert "콜" in titles
    assert "폴드" in titles
    assert "올인" in titles
    assert "레이즈 600" in titles
    assert "도움말" in titles
    assert "리셋" in titles
    assert "랭킹" in titles
    assert "전적" in titles

    assert "참가" in commands
    assert "시작" in commands
    assert "내카드" in commands
    assert "올인" in commands
    assert "레이즈 600" in commands
    assert "도움말" in commands
    assert "리셋" in commands
    assert "랭킹" in commands
    assert "전적" in commands


def test_extract_command_from_attachment_action():
    builder = WebexCardBuilder()

    attachment_action = {
        "inputs": {
            "command": "콜",
        }
    }

    command = builder.extract_command(attachment_action)

    assert command == "콜"


def test_extract_command_without_command_fails():
    builder = WebexCardBuilder()

    attachment_action = {
        "inputs": {}
    }

    with pytest.raises(ValueError) as error:
        builder.extract_command(attachment_action)

    assert "버튼 명령어를 찾을 수 없습니다" in str(error.value)


def test_action_card_contains_result_message():
    builder = WebexCardBuilder()

    card = builder.build_action_card(
        status="현재 상태: WAITING",
        message="처리 실패: 현재 액션할 수 없는 상태입니다.",
    )

    body_texts = [
        item["text"]
        for item in card["body"]
        if item.get("type") == "TextBlock"
    ]

    assert "처리 실패: 현재 액션할 수 없는 상태입니다." in body_texts
    assert "현재 상태: WAITING" in body_texts


def test_action_card_contains_emphasized_error_message():
    builder = WebexCardBuilder()

    card = builder.build_action_card(
        status="현재 상태: WAITING",
        message="현재 액션할 수 없는 상태입니다.",
        message_type="error",
    )

    body = card["body"]

    assert body[1]["text"] == "⚠️ 처리 실패"
    assert body[1]["color"] == "Attention"
    assert body[2]["text"] == "현재 액션할 수 없는 상태입니다."
    assert body[2]["color"] == "Attention"


def test_action_card_can_use_custom_actions():
    builder = WebexCardBuilder()

    card = builder.build_action_card(
        status="현재 상태: WAITING",
        actions=[
            ("참가", "참가"),
            ("시작", "시작"),
            ("상태", "상태"),
        ],
    )

    titles = [
        action["title"]
        for action in card["actions"]
    ]

    commands = [
        action["data"]["command"]
        for action in card["actions"]
    ]

    assert titles == ["참가", "시작", "상태"]
    assert commands == ["참가", "시작", "상태"]

def test_action_card_contains_card_token_in_buttons():
    builder = WebexCardBuilder()

    card = builder.build_action_card(
        status="현재 상태: WAITING",
        card_token="token-123",
    )

    for action in card["actions"]:
        assert action["data"]["card_token"] == "token-123"


def test_extract_card_token_from_attachment_action():
    builder = WebexCardBuilder()

    attachment_action = {
        "inputs": {
            "command": "리셋",
            "card_token": "token-123",
        }
    }

    card_token = builder.extract_card_token(attachment_action)

    assert card_token == "token-123"


def test_action_card_renders_card_suits_with_readable_rich_text_colors():
    builder = WebexCardBuilder()

    card = builder.build_action_card(
        status="보드: [K♠️] [7🍀] [10♥️] [A♦️]",
        message="쇼다운: [10♠️] [Q🍀] [J♥️] [2♦️]",
    )

    rich_blocks = [
        item
        for item in card["body"]
        if item.get("type") == "RichTextBlock"
    ]
    runs = [
        run
        for block in rich_blocks
        for run in block["inlines"]
    ]

    assert any(run["text"] == "[K " for run in runs)
    assert any(run["text"] == "[10 " for run in runs)
    assert "[K♠️]" not in str(runs)

    suit_runs = [
        run
        for run in runs
        if run.get("text") in {"🍀", "♠", "♥", "♦"}
    ]

    assert {
        run["text"]: (run["color"], run["weight"])
        for run in suit_runs
    } == {
        "🍀": ("good", "bolder"),
        "♠": ("light", "bolder"),
        "♥": ("attention", "bolder"),
        "♦": ("attention", "bolder"),
    }
