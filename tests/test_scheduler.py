from datetime import date


def test_parse_slot_range_valid_and_invalid():
    from agents import scheduler

    valid = scheduler._parse_slot_range("2026-03-20", "09:00-10:00")
    assert valid is not None
    assert valid[0].strftime("%H:%M") == "09:00"

    assert scheduler._parse_slot_range("2026-03-20", "10:00-09:00") is None
    assert scheduler._parse_slot_range("2026-03-20", "invalid") is None


def test_detect_schedule_conflicts(mem, monkeypatch):
    from agents import scheduler

    monkeypatch.setattr(scheduler, "memory", mem)

    today = date.today().isoformat()
    mem.create_agenda_block(today, "09:00-10:00", "Tarefa A")
    mem.create_agenda_block(today, "09:00-09:30", "Tarefa B")

    conflicts = scheduler.detect_schedule_conflicts()

    assert conflicts
    assert "09:00" in conflicts[0]
    assert "Tarefa A" in conflicts[0]
    assert "Tarefa B" in conflicts[0]


def test_calculate_schedule_load_uses_minutes():
    from agents import scheduler

    result = scheduler.calculate_schedule_load(
        [
            {"time_slot": "09:00-10:00", "completed": True},
            {"time_slot": "10:00-10:30", "completed": False},
            {"time_slot": "invalid", "completed": True},
        ]
    )

    assert result["total_blocks"] == 3
    assert result["completed_blocks"] == 2
    assert result["total_minutes"] == 90
    assert result["completion_percent"] == 67
