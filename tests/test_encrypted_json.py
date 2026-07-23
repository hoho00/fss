import json

import pytest

from app.domain.game import HoldemGame
from app.services.encrypted_json import (
    EncryptedJsonCodec,
    EncryptedJsonError,
)
from app.services.game_store import JsonGameStore


KEY_A = "a" * 32
KEY_B = "b" * 32


def test_codec_encrypts_with_random_nonce_and_round_trips():
    codec = EncryptedJsonCodec(KEY_A)
    document = {"hole_cards": ["AS", "KH"], "player": "상현"}

    first = codec.dumps(document)
    second = codec.dumps(document)

    assert first.startswith("FSS2.")
    assert first != second
    assert "hole_cards" not in first
    assert "상현" not in first
    assert codec.loads(first) == (document, False)


def test_codec_rejects_wrong_key_and_tampering():
    encrypted = EncryptedJsonCodec(KEY_A).dumps({"secret": "AS KH"})

    with pytest.raises(EncryptedJsonError):
        EncryptedJsonCodec(KEY_B).loads(encrypted)

    replacement = "A" if encrypted[-1] != "A" else "B"
    with pytest.raises(EncryptedJsonError):
        EncryptedJsonCodec(KEY_A).loads(encrypted[:-1] + replacement)


def test_codec_requires_a_secret_of_at_least_32_bytes(monkeypatch):
    monkeypatch.delenv("FSS_DATA_ENCRYPTION_KEY", raising=False)

    with pytest.raises(EncryptedJsonError):
        EncryptedJsonCodec()
    with pytest.raises(EncryptedJsonError):
        EncryptedJsonCodec("too-short")


def test_game_store_encrypts_hole_cards_and_migrates_plaintext(tmp_path):
    file_path = tmp_path / "games.json"
    game = HoldemGame()
    game.join("player-1", "상현")
    game.join("player-2", "철수")
    game.start()
    plaintext = {
        "rooms": {
            "room": {
                "game_type": "HOLDEM",
                "state": game.to_dict(),
            }
        }
    }
    file_path.write_text(json.dumps(plaintext, ensure_ascii=False), encoding="utf-8")

    store = JsonGameStore(str(file_path), encryption_key=KEY_A)
    loaded = store.load_all()["room"]
    encrypted_on_disk = file_path.read_text(encoding="utf-8")

    assert len(loaded.players[0].hole_cards) == 2
    assert encrypted_on_disk.startswith("FSS2.")
    assert "hole_cards" not in encrypted_on_disk
    assert "상현" not in encrypted_on_disk
