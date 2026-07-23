import app.main as main_module


def test_duplicate_message_webhook_is_processed_only_once(monkeypatch):
    calls = []
    main_module.processed_webhook_ids.clear()
    monkeypatch.setattr(main_module, "save_room_games", lambda: None)
    monkeypatch.setattr(
        main_module,
        "_handle_webex_message_created_locked",
        lambda payload: calls.append(payload) or {"ok": True},
    )
    payload = {"data": {"id": "message-1", "roomId": "room-1"}}

    first = main_module._handle_webex_message_created(payload)
    second = main_module._handle_webex_message_created(payload)

    assert first == {"ok": True}
    assert second["ignored"] is True
    assert len(calls) == 1


def test_duplicate_attachment_webhook_is_processed_only_once(monkeypatch):
    calls = []
    main_module.processed_webhook_ids.clear()
    monkeypatch.setattr(main_module, "save_room_games", lambda: None)
    monkeypatch.setattr(
        main_module,
        "_handle_webex_attachment_action_created_locked",
        lambda payload: calls.append(payload) or {"ok": True},
    )
    payload = {"data": {"id": "action-1", "roomId": "room-1"}}

    main_module._handle_webex_attachment_action_created(payload)
    second = main_module._handle_webex_attachment_action_created(payload)

    assert second["ignored"] is True
    assert len(calls) == 1
