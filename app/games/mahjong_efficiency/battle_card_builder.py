from app.games.mahjong_efficiency.engine import tile_label


def _text(text, **extra):
    return {"type": "TextBlock", "text": text, "wrap": True, **extra}


def _participants(battle, scores=False):
    if not battle or not battle.players:
        return "참가자: 없음"
    if scores:
        names = " · ".join(f"{p.display_name} {p.score}점" for p in battle.ranked_players())
    else:
        names = " · ".join(p.display_name for p in battle.players)
    return f"참가자: {names}"


def _tile_column(item, battle):
    return {
        "type": "Column", "width": "stretch", "items": [{
            "type": "Container", "style": "emphasis",
            "selectAction": {"type": "Action.Submit", "data": {
                "action": "mahjong_battle_discard",
                "battle_id": battle.battle_id,
                "turn_no": battle.turn_no,
                "state_version": battle.state_version,
                "tile_instance_id": item.instance_id,
            }},
            "items": [_text(
                tile_label(item.tile), weight="Bolder", size="Medium",
                horizontalAlignment="Center",
            )],
        }],
    }


def build_battle_menu_card(battle) -> dict:
    if battle is None or battle.status in {"finished", "ended"}:
        actions = [("다시 하기", "패효율 대결 다시 하기"), ("메인 메뉴", "패효율 대결 메인 메뉴")]
    elif battle.status == "lobby":
        actions = [
            ("참가", "패효율 대결 참가"), ("참가 취소", "패효율 대결 참가 취소"),
            ("시작", "패효율 대결 시작"),
            ("상태", "패효율 대결 상태"), ("대결 종료", "패효율 대결 종료"),
            ("도움말", "패효율 대결 도움말"), ("메인 메뉴", "패효율 대결 메인 메뉴"),
        ]
    else:
        actions = [
            ("상태", "패효율 대결 상태"), ("대결 종료", "패효율 대결 종료"),
            ("도움말", "패효율 대결 도움말"), ("메인 메뉴", "패효율 대결 메인 메뉴"),
        ]
    host = battle.player(battle.host_person_id).display_name if battle else "없음"
    return {
        "$schema": "http://adaptivecards.io/schemas/adaptive-card.json",
        "type": "AdaptiveCard", "version": "1.3",
        "body": [
            _text("패효율 대결", weight="Bolder", size="Medium"),
            _text("하나의 공통 손패와 패산으로 텐파이까지 이어갑니다."),
            _text(f"방장: {host}"), _text(_participants(battle)),
        ],
        "actions": [{
            "type": "Action.Submit", "title": title,
            "data": {"action": "mahjong_battle_command", "command": command},
        } for title, command in actions],
    }


def build_battle_round_card(battle) -> dict:
    state = battle.current_round
    base = sorted(state.base_hand, key=lambda item: (item.tile, item.instance_id))
    drawn = state.drawn_tile
    rows = [
        {"type": "ColumnSet", "columns": [_tile_column(item, battle) for item in base[:7]]},
        {"type": "ColumnSet", "columns": [_tile_column(item, battle) for item in base[7:]]},
    ]
    return {
        "$schema": "http://adaptivecards.io/schemas/adaptive-card.json",
        "type": "AdaptiveCard", "version": "1.3",
        "body": [
            _text(f"패효율 대결 · {battle.turn_no}순", weight="Bolder", size="Medium"),
            _text("제한시간: 10초", weight="Bolder", color="Attention"),
            _text("텐파이가 될 때까지 같은 손패로 이어집니다."),
            _text("기본 손패", weight="Bolder"), *rows,
            _text("이번 쯔모", weight="Bolder"),
            {"type": "ColumnSet", "columns": [_tile_column(drawn, battle)]},
            _text(_participants(battle, scores=True)),
        ],
    }


def build_battle_result_card(battle, result: dict) -> dict:
    winner = ", ".join(result.get("winner_names", [])) or "없음 (전원 오답/미응답)"
    lines = []
    for player in battle.players:
        submission = result["submissions"].get(player.person_id)
        if not submission:
            lines.append(f"{player.display_name}: 미응답 · 0점 · 누적 {player.score}점")
        elif submission["is_best"]:
            lines.append(f"{player.display_name}: {tile_label(submission['tile'])} · 최선 · +10점 · 누적 {player.score}점")
        elif submission["shanten_worsened"]:
            lines.append(f"{player.display_name}: {tile_label(submission['tile'])} · 샨텐 악화 · 손실 {submission['efficiency_loss']}장 + 10점 감점 · 누적 {player.score}점")
        else:
            lines.append(f"{player.display_name}: {tile_label(submission['tile'])} · 손실 {submission['efficiency_loss']}장 · 누적 {player.score}점")
    body = [
        _text(f"{result['turn_no']}순 결과", weight="Bolder", size="Large"),
        _text(f"정답자: {winner}", weight="Bolder"),
        _text(f"공통 타패: {tile_label(result['common_discard'])}", weight="Bolder"),
        _text(f"현재 샨텐: {result['current_shanten']}샨텐"),
    ]
    if result.get("next_draw") is not None:
        body.append(_text(f"다음 쯔모: {tile_label(result['next_draw'])}"))
    body.extend([
        _text("최선 타패: " + ", ".join(tile_label(tile) for tile in result["best_discards"])),
        _text(f"최고 유효패: {result['highest_ukeire_count']}장"),
        _text(_participants(battle, scores=True)),
        _text("\n".join(lines)),
    ])
    return {"$schema": "http://adaptivecards.io/schemas/adaptive-card.json", "type": "AdaptiveCard", "version": "1.3", "body": body}


def build_battle_status_card(battle, now) -> dict:
    if not battle or battle.status in {"finished", "ended"}:
        body = [_text("패효율 대결 상태", weight="Bolder", size="Medium"), _text("진행 중인 패효율 대결이 없습니다."), _text(_participants(battle))]
    elif battle.status == "lobby":
        host = battle.player(battle.host_person_id).display_name
        body = [_text("패효율 대결 로비", weight="Bolder", size="Medium"), _text(f"방장: {host}"), _text(_participants(battle))]
    else:
        value = battle.round_deadline_at if battle.phase == "ANSWERING" else battle.result_deadline_at
        deadline = __import__("datetime").datetime.fromisoformat(value)
        remaining = max(0, int((deadline - now).total_seconds()))
        phase = "응답 중" if battle.phase == "ANSWERING" else "결과 표시 중"
        body = [_text(f"패효율 대결 · {battle.turn_no}순", weight="Bolder", size="Medium"), _text(f"{phase} · 남은 시간: 약 {remaining}초"), _text(_participants(battle, scores=True))]
    return {"$schema": "http://adaptivecards.io/schemas/adaptive-card.json", "type": "AdaptiveCard", "version": "1.3", "body": body}


def build_battle_final_card(battle, result: dict) -> dict:
    ranking = "\n".join(
        f"{rank}. {p.display_name} · {p.score}점 · 승리 {p.wins}순 · 최선 {p.best_discards}/{p.responses} · 누적 손실 {p.efficiency_loss}장 · 샨텐 악화 {p.worsened}회"
        for rank, p in enumerate(battle.ranked_players(), 1)
    )
    final_hand = " · ".join(tile_label(tile) for tile in sorted(result.get("final_hand", [])))
    waits = ", ".join(tile_label(tile) for tile in result.get("waiting_tiles", [])) or "없음"
    return {
        "$schema": "http://adaptivecards.io/schemas/adaptive-card.json", "type": "AdaptiveCard", "version": "1.3",
        "body": [
            _text("패효율 대결 최종 결과", weight="Bolder", size="Large"),
            _text(f"텐파이까지 {battle.turn_no}순"),
            _text(f"최종 13장 손패: {final_hand}"),
            _text(f"마지막 쯔모패: {tile_label(result['last_drawn']) if result.get('last_drawn') is not None else '없음'}"),
            _text(f"마지막 공통 타패: {tile_label(result['common_discard'])}"),
            _text(f"최종 대기패: {waits}"),
            _text(_participants(battle, scores=True)),
            _text("최종 순위\n" + ranking),
        ],
        "actions": [
            {"type": "Action.Submit", "title": "다시 하기", "data": {"action": "mahjong_battle_command", "command": "패효율 대결 다시 하기"}},
            {"type": "Action.Submit", "title": "메인 메뉴", "data": {"action": "mahjong_battle_command", "command": "패효율 대결 메인 메뉴"}},
        ],
    }


def build_game_status_selector_card() -> dict:
    actions = [
        ("홀덤", "상태 홀덤"), ("개인 패효율", "패효율 상태"),
        ("패효율 대결", "패효율 대결 상태"), ("메인 도움말", "도움말"),
    ]
    return {
        "$schema": "http://adaptivecards.io/schemas/adaptive-card.json", "type": "AdaptiveCard", "version": "1.3",
        "body": [_text("FSS 게임 선택", weight="Bolder", size="Large"), _text("확인할 게임을 선택하세요.")],
        "actions": [{"type": "Action.Submit", "title": title, "data": {"action": "game_status_selection", "command": command}} for title, command in actions],
    }
