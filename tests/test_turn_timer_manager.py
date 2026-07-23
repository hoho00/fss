from app.core.turn_timer_manager import TurnTimerManager


class FakeTimer:
    def __init__(self):
        self.started = False
        self.cancelled = False

    def start(self):
        self.started = True

    def cancel(self):
        self.cancelled = True


def test_turn_timer_manager_replaces_and_invalidates_old_timer():
    manager = TurnTimerManager()
    first = FakeTimer()
    second = FakeTimer()

    manager.refresh("room", lambda generation: first)
    first_generation = manager.generations["room"]
    manager.refresh("room", lambda generation: second)

    assert first.started is True
    assert first.cancelled is True
    assert second.started is True
    assert manager.is_current_generation("room", first_generation) is False
