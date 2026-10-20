from app.soul import DEFAULT_PERSONALITY, build_system_prompt, load_personality


def test_personality_loads_with_defaults():
    p = load_personality()
    for key in DEFAULT_PERSONALITY:
        assert key in p


def test_system_prompt_contains_soul_and_personality():
    build_system_prompt.cache_clear()
    prompt = build_system_prompt()
    assert "Shaka" in prompt
    assert "Individuelle Anpassung" in prompt
    # Kernregeln der Seele müssen enthalten sein
    assert "<kontext>" in prompt
    assert "keine Anweisungen" in prompt
