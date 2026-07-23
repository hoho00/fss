from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from typing import Iterable, Sequence


TILE_LABELS = tuple(
    [f"{number}만" for number in range(1, 10)]
    + [f"{number}통" for number in range(1, 10)]
    + [f"{number}삭" for number in range(1, 10)]
    + ["동", "남", "서", "북", "백", "발", "중"]
)
TERMINAL_HONOR_INDICES = (0, 8, 9, 17, 18, 26, 27, 28, 29, 30, 31, 32, 33)


@dataclass(frozen=True)
class DiscardEvaluation:
    tile: int
    shanten: int
    ukeire: tuple[tuple[int, int], ...]
    ukeire_count: int
    is_best: bool
    efficiency_loss: int
    shanten_loss: int


@dataclass(frozen=True)
class HandEvaluation:
    discards: tuple[DiscardEvaluation, ...]
    best_shanten: int
    highest_ukeire_count: int
    best_discards: tuple[int, ...]

    def for_tile(self, tile: int) -> DiscardEvaluation:
        return next(item for item in self.discards if item.tile == tile)


def tile_label(tile: int) -> str:
    return TILE_LABELS[tile]


def counts_from_tiles(tiles: Iterable[int]) -> tuple[int, ...]:
    counts = [0] * 34
    for tile in tiles:
        if not 0 <= tile < 34:
            raise ValueError(f"올바르지 않은 마작패 인덱스입니다: {tile}")
        counts[tile] += 1
        if counts[tile] > 4:
            raise ValueError(f"같은 마작패는 4장을 초과할 수 없습니다: {tile_label(tile)}")
    return tuple(counts)


def shanten(tiles_or_counts: Sequence[int]) -> int:
    counts = _as_counts(tiles_or_counts)
    return min(
        standard_shanten(counts),
        seven_pairs_shanten(counts),
        thirteen_orphans_shanten(counts),
    )


def standard_shanten(tiles_or_counts: Sequence[int]) -> int:
    return _standard_shanten(_as_counts(tiles_or_counts))


@lru_cache(maxsize=100_000)
def _standard_shanten(counts: tuple[int, ...]) -> int:
    best = 8

    def search(state: list[int], index: int, melds: int, pairs: int, taatsu: int) -> None:
        nonlocal best
        while index < 34 and state[index] == 0:
            index += 1
        if index == 34:
            usable_taatsu = min(taatsu, 4 - melds)
            best = min(best, 8 - melds * 2 - usable_taatsu - pairs)
            return

        # Treat one copy as isolated. This branch also prevents special-hand
        # shapes from forcing an invalid standard decomposition.
        state[index] -= 1
        search(state, index, melds, pairs, taatsu)
        state[index] += 1

        if state[index] >= 3:
            state[index] -= 3
            search(state, index, melds + 1, pairs, taatsu)
            state[index] += 3

        if index < 27 and index % 9 <= 6 and state[index + 1] and state[index + 2]:
            state[index] -= 1
            state[index + 1] -= 1
            state[index + 2] -= 1
            search(state, index, melds + 1, pairs, taatsu)
            state[index] += 1
            state[index + 1] += 1
            state[index + 2] += 1

        if state[index] >= 2:
            state[index] -= 2
            if pairs == 0:
                search(state, index, melds, 1, taatsu)
            search(state, index, melds, pairs, taatsu + 1)
            state[index] += 2

        if index < 27 and index % 9 <= 7 and state[index + 1]:
            state[index] -= 1
            state[index + 1] -= 1
            search(state, index, melds, pairs, taatsu + 1)
            state[index] += 1
            state[index + 1] += 1

        if index < 27 and index % 9 <= 6 and state[index + 2]:
            state[index] -= 1
            state[index + 2] -= 1
            search(state, index, melds, pairs, taatsu + 1)
            state[index] += 1
            state[index + 2] += 1

    search(list(counts), 0, 0, 0, 0)
    return best


def seven_pairs_shanten(tiles_or_counts: Sequence[int]) -> int:
    counts = _as_counts(tiles_or_counts)
    pairs = sum(value >= 2 for value in counts)
    unique = sum(value > 0 for value in counts)
    return 6 - pairs + max(0, 7 - unique)


def thirteen_orphans_shanten(tiles_or_counts: Sequence[int]) -> int:
    counts = _as_counts(tiles_or_counts)
    unique = sum(counts[index] > 0 for index in TERMINAL_HONOR_INDICES)
    pair = any(counts[index] >= 2 for index in TERMINAL_HONOR_INDICES)
    return 13 - unique - int(pair)


def evaluate_discards(
    hand: Sequence[int],
    *,
    remaining_counts: Sequence[int] | None = None,
    discards: Sequence[int] = (),
) -> HandEvaluation:
    if len(hand) % 3 != 2:
        raise ValueError("타패 평가는 14장 형태의 손패가 필요합니다.")
    hand_counts = list(counts_from_tiles(hand))
    if remaining_counts is None:
        discarded_counts = counts_from_tiles(discards)
        remaining = [
            max(0, 4 - hand_counts[index] - discarded_counts[index])
            for index in range(34)
        ]
    else:
        if len(remaining_counts) != 34:
            raise ValueError("remaining_counts는 34개 패 종류를 포함해야 합니다.")
        remaining = [max(0, int(value)) for value in remaining_counts]

    raw = []
    for tile in sorted(set(hand)):
        after = hand_counts.copy()
        after[tile] -= 1
        base_shanten = shanten(after)
        ukeire = []
        for draw, count in enumerate(remaining):
            if count <= 0:
                continue
            after[draw] += 1
            improved = shanten(after) < base_shanten
            after[draw] -= 1
            if improved:
                ukeire.append((draw, count))
        raw.append((tile, base_shanten, tuple(ukeire), sum(count for _, count in ukeire)))

    best_shanten = min(item[1] for item in raw)
    same_shanten = [item for item in raw if item[1] == best_shanten]
    highest_ukeire = max(item[3] for item in same_shanten)
    evaluations = tuple(
        DiscardEvaluation(
            tile=tile,
            shanten=tile_shanten,
            ukeire=ukeire,
            ukeire_count=ukeire_count,
            is_best=tile_shanten == best_shanten and ukeire_count == highest_ukeire,
            efficiency_loss=(highest_ukeire - ukeire_count) if tile_shanten == best_shanten else 0,
            shanten_loss=max(0, tile_shanten - best_shanten),
        )
        for tile, tile_shanten, ukeire, ukeire_count in raw
    )
    return HandEvaluation(
        discards=evaluations,
        best_shanten=best_shanten,
        highest_ukeire_count=highest_ukeire,
        best_discards=tuple(item.tile for item in evaluations if item.is_best),
    )


def _as_counts(values: Sequence[int]) -> tuple[int, ...]:
    if len(values) == 34 and all(isinstance(value, int) and 0 <= value <= 4 for value in values):
        return tuple(values)
    return counts_from_tiles(values)
