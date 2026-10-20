import pytest
from app.security import redact_secrets

@pytest.mark.parametrize('idx', range(50))
def test_redact_secrets_fuzzing(idx):
    text = f'System log entry number {idx}: All services operational.'
    assert redact_secrets(text) == text

@pytest.mark.parametrize('secret_pattern,tag', [
    ('AIzaSyD-1234567890abcdefghijklmnopqrst', '[REDACTED:google-key]'),
    ('sk-ant-TEST-DUMMY-not-a-real-key', '[REDACTED:anthropic-key]'),
    ('ghp_1234567890abcdefghijklmnopqrstuvwx', '[REDACTED:github-token]'),
    ('gho_1234567890abcdefghijklmnopqrstuvwx', '[REDACTED:github-token]'),
    ('ghu_1234567890abcdefghijklmnopqrstuvwx', '[REDACTED:github-token]'),
    ('ghs_1234567890abcdefghijklmnopqrstuvwx', '[REDACTED:github-token]'),
    ('ghr_1234567890abcdefghijklmnopqrstuvwx', '[REDACTED:github-token]'),
    ('-----BEGIN RSA PRIVATE KEY-----\nMIIEowIBAAKCAQEA...\n-----END RSA PRIVATE KEY-----', '[REDACTED:private-key]'),
    ('-----BEGIN EC PRIVATE KEY-----\nMHcCAQEEI...\n-----END EC PRIVATE KEY-----', '[REDACTED:private-key]'),
])
def test_secret_redaction_patterns(secret_pattern, tag):
    assert tag in redact_secrets(secret_pattern)
