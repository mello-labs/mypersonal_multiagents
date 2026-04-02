def test_persona_manager_loads_and_sets_active(monkeypatch):
    from agents import persona_manager

    monkeypatch.setattr(
        persona_manager,
        "_active_persona_id",
        persona_manager._DEFAULT_PERSONA_ID,
        raising=False,
    )

    persona_manager.reload_personas()
    personas = persona_manager.list_personas()

    assert personas
    assert any(p["id"] == persona_manager._DEFAULT_PERSONA_ID for p in personas)

    first_id = personas[0]["id"]
    assert persona_manager.set_active_persona(first_id) is True
    assert persona_manager.get_active_persona_id() == first_id

    assert persona_manager.set_active_persona("missing-persona") is False
    assert persona_manager.get_active_persona_id() == first_id

    fallback = persona_manager.get_persona("missing-persona")
    assert fallback.get("id") == persona_manager._DEFAULT_PERSONA_ID


def test_persona_manager_temperature_defaults():
    from agents import persona_manager

    persona_manager.reload_personas()
    temperature = persona_manager.get_temperature("coordinator", "direct")

    assert isinstance(temperature, float)
