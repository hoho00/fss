from datetime import datetime

from app.games.dice.domain.game import DiceGame


class DiceStatsHandler:
    def record(self, data: dict, game: DiceGame, now: datetime) -> bool:
        if not game.game_over or not game.winner_person_ids:
            return False
        recorded_ids = data.setdefault("recorded_game_ids", {}).setdefault("dice", [])
        if game.game_id and game.game_id in recorded_ids:
            return False
        records = data.setdefault("players", {})
        timestamp = now.isoformat()
        for player in game.players:
            record = records.setdefault(player.person_id, {"display_name": player.display_name})
            stats = record.setdefault(
                "dice", {"games": 0, "wins": 0, "losses": 0, "last_played_at": None}
            )
            record["display_name"] = player.display_name
            stats["games"] = int(stats.get("games", 0)) + 1
            stats["last_played_at"] = timestamp
            field = "wins" if player.person_id in game.winner_person_ids else "losses"
            stats[field] = int(stats.get(field, 0)) + 1
        if game.game_id:
            recorded_ids.append(game.game_id)
        return True
