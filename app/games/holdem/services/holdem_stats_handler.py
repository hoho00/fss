from datetime import datetime

from app.domain.game import HoldemGame
from app.domain.player import Player


class HoldemStatsHandler:
    def record(self, data: dict, game: HoldemGame, now: datetime) -> bool:
        if not game.game_over:
            return False
        players = self._collect_players(game)
        winner_ids = self._winner_ids(game, players)
        if not players or not winner_ids:
            return False

        recorded_ids = data.setdefault("recorded_game_ids", {}).setdefault("holdem", [])
        if game.game_id and game.game_id in recorded_ids:
            return False
        records = data.setdefault("players", {})
        timestamp = now.isoformat()
        for player in players:
            record = records.setdefault(
                player.person_id,
                {
                    "display_name": player.display_name,
                    "games": 0,
                    "wins": 0,
                    "eliminations": 0,
                    "last_played_at": None,
                },
            )
            record["display_name"] = player.display_name
            record["games"] = int(record.get("games", 0)) + 1
            record["last_played_at"] = timestamp
            field = "wins" if player.person_id in winner_ids else "eliminations"
            record[field] = int(record.get(field, 0)) + 1
        if game.game_id:
            recorded_ids.append(game.game_id)
        return True

    @staticmethod
    def _collect_players(game: HoldemGame) -> list[Player]:
        players = {}
        for item in [*game.players, *game.eliminated_players]:
            player = item if isinstance(item, Player) else Player(
                person_id=item["person_id"],
                display_name=item.get("display_name", item["person_id"]),
                chips=int(item.get("chips", 0)),
            )
            players[player.person_id] = player
        return list(players.values())

    @staticmethod
    def _winner_ids(game: HoldemGame, players: list[Player]) -> set[str]:
        if game.final_winner_name:
            return {
                player.person_id
                for player in players
                if player.display_name == game.final_winner_name
            }
        active = [player for player in game.players if player.chips > 0]
        return {active[0].person_id} if len(active) == 1 else set()
