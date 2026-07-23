import uuid

from app.domain.card import Card, Rank, Suit
from app.domain.deck import Deck
from app.domain.player import Player


def card_to_dict(card: Card) -> dict:
    return {"suit": card.suit.value, "rank": card.rank.value}


def card_from_dict(data: dict) -> Card:
    return Card(suit=Suit(data["suit"]), rank=Rank(data["rank"]))


def player_to_dict(player: Player) -> dict:
    return {
        "person_id": player.person_id,
        "display_name": player.display_name,
        "chips": player.chips,
        "hole_cards": [card_to_dict(card) for card in player.hole_cards],
        "folded": player.folded,
        "all_in": player.all_in,
        "acted": player.acted,
        "current_bet": player.current_bet,
        "total_bet": player.total_bet,
    }


def player_from_dict(data: dict) -> Player:
    player = Player(
        person_id=data["person_id"],
        display_name=data["display_name"],
        chips=data.get("chips", 10000),
    )
    player.hole_cards = [card_from_dict(item) for item in data.get("hole_cards", [])]
    player.folded = data.get("folded", False)
    player.all_in = data.get("all_in", False)
    player.acted = data.get("acted", False)
    player.current_bet = data.get("current_bet", 0)
    player.total_bet = data.get("total_bet", 0)
    return player


def serialize_holdem_game(game) -> dict:
    return {
        "players": [player_to_dict(player) for player in game.players],
        "deck_cards": [card_to_dict(card) for card in game.deck.cards],
        "community_cards": [card_to_dict(card) for card in game.community_cards],
        "phase": game.phase.value,
        "pot": game.pot,
        "dealer_index": game.dealer_index,
        "current_turn_index": game.current_turn_index,
        "small_blind": game.small_blind,
        "big_blind": game.big_blind,
        "current_highest_bet": game.current_highest_bet,
        "min_raise": game.min_raise,
        "eliminated_players": game.eliminated_players,
        "turn_timeout_counts": game.turn_timeout_counts,
        "timeout_excluded_player_ids": game.timeout_excluded_player_ids,
        "pending_timeout_exclusion_ids": game.pending_timeout_exclusion_ids,
        "game_over": game.game_over,
        "final_winner_name": game.final_winner_name,
        "game_id": game.game_id,
    }


def restore_holdem_game(game, data: dict, phase_enum) -> None:
    game.players = [player_from_dict(item) for item in data.get("players", [])]
    game.deck = Deck()
    game.deck.cards = [card_from_dict(item) for item in data.get("deck_cards", [])]
    game.community_cards = [card_from_dict(item) for item in data.get("community_cards", [])]
    game.phase = phase_enum(data.get("phase", phase_enum.WAITING.value))
    game.pot = data.get("pot", 0)
    game.dealer_index = data.get("dealer_index")
    game.current_turn_index = data.get("current_turn_index")
    game.small_blind = data.get("small_blind", 100)
    game.big_blind = data.get("big_blind", 200)
    game.current_highest_bet = data.get("current_highest_bet", 0)
    game.min_raise = data.get("min_raise", game.big_blind)
    game.eliminated_players = data.get("eliminated_players", [])
    game.turn_timeout_counts = data.get("turn_timeout_counts", {})
    game.timeout_excluded_player_ids = data.get("timeout_excluded_player_ids", [])
    game.pending_timeout_exclusion_ids = data.get("pending_timeout_exclusion_ids", [])
    game.game_over = data.get("game_over", False)
    game.final_winner_name = data.get("final_winner_name")
    game.game_id = data.get("game_id")
    if game.game_id is None and (game.players or game.phase != phase_enum.WAITING):
        game.game_id = str(uuid.uuid4())
    if game.dealer_index is not None and game.players:
        game.dealer_index %= len(game.players)
    if game.current_turn_index is not None:
        game.current_turn_index = (
            game.current_turn_index % len(game.players) if game.players else None
        )
