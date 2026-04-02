def test_normalize_date_range_swaps():
    from agents import calendar_sync

    start, end = calendar_sync._normalize_date_range("2026-03-22", "2026-03-20")

    assert start.isoformat() == "2026-03-20"
    assert end.isoformat() == "2026-03-22"


def test_fetch_events_range_parses_items(monkeypatch):
    from agents import calendar_sync

    class FakeEvents:
        def __init__(self, items):
            self.items = items

        def list(self, **kwargs):
            self.kwargs = kwargs
            return self

        def execute(self):
            return {"items": self.items}

    class FakeService:
        def __init__(self, items):
            self._events = FakeEvents(items)

        def events(self):
            return self._events

    items = [
        {
            "id": "evt-1",
            "summary": "Standup",
            "start": {"dateTime": "2026-03-20T09:00:00"},
            "end": {"dateTime": "2026-03-20T09:30:00"},
            "location": "Sala 1",
            "description": "Daily",
        },
        {
            "id": "evt-2",
            "summary": "Feriado",
            "start": {"date": "2026-03-21"},
            "end": {"date": "2026-03-22"},
        },
    ]

    monkeypatch.setattr(calendar_sync, "_get_service", lambda: FakeService(items))
    monkeypatch.setattr(calendar_sync.notifier, "info", lambda *args, **kwargs: None)
    monkeypatch.setattr(calendar_sync.notifier, "warning", lambda *args, **kwargs: None)
    monkeypatch.setattr(calendar_sync.notifier, "error", lambda *args, **kwargs: None)

    events = calendar_sync.fetch_events_range("2026-03-20", "2026-03-21")

    assert len(events) == 2
    assert events[0]["time_slot"] == "09:00-09:30"
    assert events[0]["all_day"] is False
    assert events[1]["all_day"] is True
    assert events[1]["time_slot"] == "00:00"
    assert events[1]["date"] == "2026-03-21"


def test_import_events_range_as_blocks_skips_duplicates(mem, monkeypatch):
    from agents import calendar_sync

    monkeypatch.setattr(calendar_sync, "memory", mem)
    monkeypatch.setattr(calendar_sync.notifier, "info", lambda *args, **kwargs: None)
    monkeypatch.setattr(calendar_sync.notifier, "success", lambda *args, **kwargs: None)

    mem.create_agenda_block("2026-03-20", "09:00-10:00", "Review")

    events = [
        {
            "date": "2026-03-20",
            "time_slot": "09:00-10:00",
            "title": "Review",
            "all_day": False,
        },
        {
            "date": "2026-03-20",
            "time_slot": "10:00-10:30",
            "title": "Planejamento",
            "all_day": False,
        },
        {
            "date": "2026-03-20",
            "time_slot": "00:00",
            "title": "Feriado",
            "all_day": True,
        },
    ]

    monkeypatch.setattr(calendar_sync, "fetch_events_range", lambda *args, **kwargs: events)

    created = calendar_sync.import_events_range_as_blocks(
        "2026-03-20", "2026-03-20", skip_all_day=True
    )

    assert created == 1
    blocks = mem.get_agenda_for_date("2026-03-20")
    titles = {b["task_title"] for b in blocks}
    assert titles == {"Review", "Planejamento"}
