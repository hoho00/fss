from app.games.fool_liar.domain.game import FoolLiarGame, FoolLiarPhase


def build_fool_liar_card_actions(game: FoolLiarGame) -> list[tuple[str, str]]:
    common = [("상태", "상태"), ("제시어", "제시어")]
    if game.phase == FoolLiarPhase.WAITING:
        return [
            ("참가", "참가"), ("참가취소", "참가취소"), ("시작", "시작"),
            ("상태", "상태"), ("랭킹", "랭킹"), ("전적", "전적"),
            ("도움말", "도움말"), ("종료", "종료"),
            ("♠️ 홀덤", "게임선택 홀덤"),
            ("🎲 주사위", "게임선택 주사위"),
            ("⚔️ 검키우기", "게임선택 검키우기"),
        ]
    if game.phase in {FoolLiarPhase.VOTING, FoolLiarPhase.REVOTING}:
        candidates = game.revote_candidates if game.phase == FoolLiarPhase.REVOTING else [p.person_id for p in game.players]
        return common + [
            (f"투표 {game._player_name(person_id)}", f"투표 {person_id}")
            for person_id in candidates
        ] + [("종료", "종료")]
    if game.phase == FoolLiarPhase.FINISHED:
        return [("새게임", "새게임"), ("상태", "상태"), ("랭킹", "랭킹"), ("전적", "전적"), ("종료", "종료")]
    return common + [("종료", "종료")]
