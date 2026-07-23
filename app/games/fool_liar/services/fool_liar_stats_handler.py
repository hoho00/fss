from datetime import datetime

from app.games.fool_liar.domain.game import FoolLiarGame
from app.services.display_name import clean_display_name


class FoolLiarStatsHandler:
    def record(self, data: dict, game: FoolLiarGame, now: datetime) -> bool:
        if not game.normal_finished or not game.game_id or not game.winner_person_ids:
            return False
        recorded_ids = data.setdefault("recorded_game_ids", {}).setdefault("fool_liar", [])
        if game.game_id in recorded_ids:
            game.stats_recorded = True
            return False

        records = data.setdefault("players", {})
        timestamp = now.isoformat()
        for player in game.players:
            player.display_name = clean_display_name(player.display_name)
            record = records.setdefault(player.person_id, {"display_name": player.display_name})
            stats = record.setdefault(
                "fool_liar",
                {
                    "games": 0, "wins": 0, "losses": 0, "last_played_at": None,
                    "fool_games": 0, "fool_wins": 0,
                    "normal_games": 0, "normal_wins": 0,
                    "identified_as_fool": 0, "answer_successes": 0,
                },
            )
            record["display_name"] = player.display_name
            stats["games"] = int(stats.get("games", 0)) + 1
            stats["last_played_at"] = timestamp
            won = player.person_id in game.winner_person_ids
            outcome = "wins" if won else "losses"
            stats[outcome] = int(stats.get(outcome, 0)) + 1
            if player.person_id == game.fool_person_id:
                stats["fool_games"] = int(stats.get("fool_games", 0)) + 1
                if won:
                    stats["fool_wins"] = int(stats.get("fool_wins", 0)) + 1
                if game.final_accused_person_id == game.fool_person_id:
                    stats["identified_as_fool"] = int(stats.get("identified_as_fool", 0)) + 1
                if game.answer_correct:
                    stats["answer_successes"] = int(stats.get("answer_successes", 0)) + 1
            else:
                stats["normal_games"] = int(stats.get("normal_games", 0)) + 1
                if won:
                    stats["normal_wins"] = int(stats.get("normal_wins", 0)) + 1

        recorded_ids.append(game.game_id)
        game.stats_recorded = True
        return True
