from app.security import redact_secrets


def test_redacts_google_key():
    fake_key = "AIzaSy" + "DUMMY" * 7  # nur ein Muster-Dummy, kein echter Key
    out = redact_secrets(f"key={fake_key} done")
    assert "AIza" not in out
    assert "[REDACTED:google-key]" in out


def test_redacts_anthropic_key():
    out = redact_secrets("sk-ant-api03-abcdefgh12345678")
    assert out == "[REDACTED:anthropic-key]"


def test_redacts_github_token():
    out = redact_secrets("token ghp_abcdefghijklmnopqrst123456")
    assert "ghp_" not in out


def test_redacts_private_key_header():
    out = redact_secrets("-----BEGIN RSA PRIVATE KEY-----\nMIIE...")
    assert "PRIVATE KEY" not in out.split("\n")[0] or "REDACTED" in out


def test_plain_text_untouched():
    text = "Ganz normaler Satz ohne Geheimnisse, skifahren macht Spaß."
    assert redact_secrets(text) == text
