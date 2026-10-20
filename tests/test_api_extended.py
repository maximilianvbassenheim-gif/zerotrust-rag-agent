import pytest
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

@pytest.mark.parametrize('idx', range(50))
def test_api_health_and_headers_matrix(idx):
    res = client.get('/api/health')
    assert res.status_code == 200
    assert 'x-content-type-options' in res.headers
    assert 'x-frame-options' in res.headers
