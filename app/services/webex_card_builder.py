import re


class WebexCardBuilder:
    CARD_PATTERN = re.compile(r"\[(10|[2-9JQKA])\s*([♠♥♦♣]|🍀)️?\]")
    SUIT_COLORS = {
        "♣": "good",
        "🍀": "good",
        "♠": "light",
        "♥": "attention",
        "♦": "attention",
    }

    def build_action_card(
        self,
        status: str,
        message: str | None = None,
        message_type: str | None = None,
        actions: list[tuple[str, str]] | None = None,
        card_token: str | None = None,
    ) -> dict:
        body = [
            {
                "type": "TextBlock",
                "text": "FSS 홀덤",
                "weight": "Bolder",
                "size": "Medium",
                "wrap": True,
            },
        ]

        if message:
            if message_type == "error":
                body.extend(
                    [
                        {
                            "type": "TextBlock",
                            "text": "⚠️ 처리 실패",
                            "wrap": True,
                            "spacing": "Medium",
                            "weight": "Bolder",
                            "size": "Medium",
                            "color": "Attention",
                        },
                        {
                            **self._text_or_rich_text_block(
                                {
                                    "type": "TextBlock",
                                    "text": message,
                                    "wrap": True,
                                    "spacing": "Small",
                                    "weight": "Bolder",
                                    "color": "Attention",
                                }
                            )
                        },
                    ]
                )
            elif message_type == "success":
                body.append(
                    self._text_or_rich_text_block(
                        {
                            "type": "TextBlock",
                            "text": message,
                            "wrap": True,
                            "spacing": "Medium",
                            "weight": "Bolder",
                            "color": "Good",
                        }
                    )
                )
            else:
                body.append(
                    self._text_or_rich_text_block(
                        {
                            "type": "TextBlock",
                            "text": message,
                            "wrap": True,
                            "spacing": "Medium",
                            "weight": "Bolder",
                        }
                    )
                )

        body.append(
            self._text_or_rich_text_block(
                {
                    "type": "TextBlock",
                    "text": status,
                    "wrap": True,
                    "spacing": "Medium",
                }
            )
        )

        if actions is None:
            actions = [
                ("참가", "참가"),
                ("시작", "시작"),
                ("상태", "상태"),
                ("내카드", "내카드"),
                ("체크", "체크"),
                ("콜", "콜"),
                ("폴드", "폴드"),
                ("올인", "올인"),
                ("레이즈 600", "레이즈 600"),
                ("랭킹", "랭킹"),
                ("전적", "전적"),
                ("개인 패효율", "패효율 시작"),
                ("패효율 대결", "패효율 대결"),
                ("도움말", "도움말"),
                ("리셋", "리셋"),
            ]

        return {
            "$schema": "http://adaptivecards.io/schemas/adaptive-card.json",
            "type": "AdaptiveCard",
            "version": "1.3",
            "body": body,
            "actions": [
                self._button(
                    title=title,
                    command=command,
                    card_token=card_token,
                )
                for title, command in actions
            ],
        }

    def extract_command(self, attachment_action: dict) -> str:
        inputs = attachment_action.get("inputs") or {}
        command = inputs.get("command")

        if not command:
            raise ValueError("버튼 명령어를 찾을 수 없습니다.")

        return command

    def extract_card_token(self, attachment_action: dict) -> str | None:
        inputs = attachment_action.get("inputs") or {}
        return inputs.get("card_token")

    def _button(
        self,
        title: str,
        command: str,
        card_token: str | None,
    ) -> dict:
        data = {
            "command": command,
        }

        if card_token:
            data["card_token"] = card_token

        return {
            "type": "Action.Submit",
            "title": title,
            "data": data,
        }

    def _text_or_rich_text_block(self, block: dict) -> dict:
        text = block.get("text")

        if not isinstance(text, str):
            return block

        if not self.CARD_PATTERN.search(text):
            return block

        rich_block = {
            "type": "RichTextBlock",
            "inlines": self._card_text_runs(text),
        }

        for key in [
            "horizontalAlignment",
            "spacing",
            "separator",
            "height",
        ]:
            if key in block:
                rich_block[key] = block[key]

        return rich_block

    def _card_text_runs(self, text: str) -> list[dict]:
        runs = []
        cursor = 0

        for match in self.CARD_PATTERN.finditer(text):
            if match.start() > cursor:
                runs.append(
                    {
                        "type": "TextRun",
                        "text": text[cursor:match.start()],
                    }
                )

            rank = match.group(1)
            suit = match.group(2)

            runs.extend(
                [
                    {
                        "type": "TextRun",
                        "text": f"[{rank} ",
                    },
                    {
                        "type": "TextRun",
                        "text": suit,
                        "color": self.SUIT_COLORS[suit],
                        "weight": "bolder",
                    },
                    {
                        "type": "TextRun",
                        "text": "]",
                    },
                ]
            )

            cursor = match.end()

        if cursor < len(text):
            runs.append(
                {
                    "type": "TextRun",
                    "text": text[cursor:],
                }
            )

        return runs
