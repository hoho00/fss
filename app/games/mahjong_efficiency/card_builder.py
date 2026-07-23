from app.games.mahjong_efficiency.engine import tile_label


def build_hand_card(session) -> dict:
    base_tiles = sorted(session.base_hand, key=lambda item: (item.tile, item.instance_id))
    drawn = session.drawn_tile

    def tile_column(tile, drawn_tile=False):
        items = []
        if drawn_tile:
            items.append({
                "type": "TextBlock", "text": "쯔모", "weight": "Bolder",
                "horizontalAlignment": "Center", "color": "Accent", "spacing": "None",
            })
        items.append({
            "type": "Container",
            "style": "accent" if drawn_tile else "emphasis",
            "selectAction": {
                "type": "Action.Submit",
                "data": {
                    "action": "mahjong_discard",
                    "game_id": session.game_id,
                    "round_id": session.round_id,
                    "state_version": session.state_version,
                    "tile_instance_id": tile.instance_id,
                },
            },
            "items": [{
                "type": "TextBlock",
                "text": tile_label(tile.tile),
                "weight": "Bolder",
                "size": "Medium",
                "horizontalAlignment": "Center",
                "wrap": True,
            }],
        })
        return {
                "type": "Column",
                "width": "stretch",
                "items": items,
            }

    first_row = [tile_column(tile) for tile in base_tiles[:7]]
    second_row = [tile_column(tile) for tile in base_tiles[7:]]
    second_row.append({"type": "Column", "width": "12px", "items": []})
    if drawn:
        second_row.append(tile_column(drawn, drawn_tile=True))
    discards = " · ".join(tile_label(item["tile"]) for item in session.discards) or "없음"
    return {
        "$schema": "http://adaptivecards.io/schemas/adaptive-card.json",
        "type": "AdaptiveCard",
        "version": "1.3",
        "body": [
            {"type": "TextBlock", "text": "리치마작 패효율", "weight": "Bolder", "size": "Medium"},
            {"type": "TextBlock", "text": f"{session.round_id}순 · 버릴 패를 선택하세요.", "wrap": True},
            {"type": "ColumnSet", "columns": first_row, "spacing": "Medium"},
            {"type": "ColumnSet", "columns": second_row, "spacing": "Medium"},
            {"type": "TextBlock", "text": f"이번 쯔모: {tile_label(drawn.tile) if drawn else '없음'}", "weight": "Bolder", "wrap": True},
            {"type": "TextBlock", "text": f"내 버림패: {discards}", "wrap": True},
        ],
    }


def build_result_card(result: dict) -> dict:
    selected = result["selected"]
    facts = [
        {"title": "이번 순서", "value": f"{result['round_id']}순"},
        {"title": "쯔모", "value": tile_label(result["drawn_tile"].tile)},
        {"title": "타패", "value": tile_label(result["discarded_tile"].tile)},
        {"title": "타패 방식", "value": "쯔모기리" if result["is_tsumogiri"] else "손출"},
        {"title": "타패 후", "value": f"{selected.shanten}샨텐"},
        {"title": "최선 타패", "value": ", ".join(tile_label(tile) for tile in result["best_discards"])},
        {"title": "선택 유효패", "value": f"{selected.ukeire_count}장"},
        {"title": "획득 효율", "value": f"{result['acquired_efficiency']}장"},
        {"title": "최고 효율", "value": f"{result['highest_ukeire_count']}장"},
        {"title": "효율 손실", "value": f"{result['efficiency_loss']}장"},
    ]
    if selected.shanten_loss:
        facts.append({"title": "샨텐 손실", "value": f"{selected.shanten_loss}단계"})
    ukeire = " · ".join(
        f"{tile_label(tile)} {count}장" for tile, count in selected.ukeire
    ) or "없음"
    return {
        "$schema": "http://adaptivecards.io/schemas/adaptive-card.json",
        "type": "AdaptiveCard",
        "version": "1.3",
        "body": [
            {"type": "TextBlock", "text": f"{result['round_id']}순 패효율 결과", "weight": "Bolder", "size": "Large"},
            {"type": "FactSet", "facts": facts},
            {"type": "TextBlock", "text": f"유효패: {ukeire}", "wrap": True},
        ],
    }
