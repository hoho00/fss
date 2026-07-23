import json
import random
from dataclasses import dataclass
from itertools import combinations
from pathlib import Path


@dataclass(frozen=True)
class Word:
    text: str
    aliases: tuple[str, ...] = ()

    def to_dict(self) -> dict:
        return {"text": self.text, "aliases": list(self.aliases)}

    @classmethod
    def from_dict(cls, data: dict) -> "Word":
        return cls(text=data["text"], aliases=tuple(data.get("aliases", [])))


@dataclass(frozen=True)
class WordPair:
    category: str
    a: Word
    b: Word

    def to_dict(self) -> dict:
        return {"category": self.category, "a": self.a.to_dict(), "b": self.b.to_dict()}

    @classmethod
    def from_dict(cls, data: dict) -> "WordPair":
        return cls(data["category"], Word.from_dict(data["a"]), Word.from_dict(data["b"]))


class JsonWordPairRepository:
    def __init__(
        self,
        file_path: str | Path | None = None,
        modifier_path: str | Path | None = None,
    ):
        data_dir = Path(__file__).parents[1] / "data"
        self.file_path = Path(file_path) if file_path else data_dir / "word_pairs.json"
        self.modifier_path = Path(modifier_path) if modifier_path else data_dir / "word_modifiers.json"

    def load_all(self) -> list[WordPair]:
        base_pairs = self._load_base_pairs()
        modifiers_by_category = self._load_modifiers()

        expanded_pairs = [
            self._with_modifier(pair, modifier)
            for pair in base_pairs
            for modifier in modifiers_by_category.get(pair.category, [])
        ]
        return base_pairs + expanded_pairs

    def _load_base_pairs(self) -> list[WordPair]:
        with self.file_path.open("r", encoding="utf-8") as file:
            categories = json.load(file)

        return [
            WordPair(category, left, right)
            for category, groups in categories.items()
            for group in groups
            for left, right in combinations(
                [Word.from_dict(item) for item in group["words"]],
                2,
            )
        ]

    def _load_modifiers(self) -> dict[str, list[str]]:
        if not self.modifier_path.exists():
            return {}

        with self.modifier_path.open("r", encoding="utf-8") as file:
            return json.load(file)

    @staticmethod
    def _with_modifier(pair: WordPair, modifier: str) -> WordPair:
        def expand(word: Word) -> Word:
            return Word(
                text=f"{word.text} {modifier}",
                aliases=tuple(f"{alias} {modifier}" for alias in word.aliases),
            )

        return WordPair(pair.category, expand(pair.a), expand(pair.b))

    def choose(self, rng: random.Random | None = None) -> WordPair:
        rng = rng or random
        pairs = self._load_base_pairs()
        if not pairs:
            raise ValueError("바보 라이어 제시어가 없습니다.")
        return rng.choice(pairs)
