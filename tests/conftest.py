import os

import pytest


# Stores can be constructed while test modules are imported.
os.environ.setdefault("FSS_DATA_ENCRYPTION_KEY", "test-only-encryption-key-32-bytes-long")
os.environ.setdefault("FSS_GAME_STORE_PATH", ".pytest-tmp/global-games.json")
os.environ.setdefault("FSS_STATS_STORE_PATH", ".pytest-tmp/global-stats.json")
os.environ.setdefault(
    "FSS_MAHJONG_EFFICIENCY_STORE_PATH",
    ".pytest-tmp/global-mahjong-efficiency.json",
)
os.environ.setdefault(
    "FSS_MAHJONG_BATTLE_STORE_PATH",
    ".pytest-tmp/global-mahjong-battles.json",
)


@pytest.fixture(autouse=True)
def enable_debug_api_for_tests(monkeypatch):
    monkeypatch.setenv("FSS_DEBUG_API_ENABLED", "true")
