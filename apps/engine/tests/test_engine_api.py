"""
Tests for the Internal Python Engine FastAPI wrapper (Phase M1).
"""
import pytest

# Skip module if fastapi is not installed
fastapi = pytest.importorskip("fastapi")

from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock

from engine_app import app
from config import settings

client = TestClient(app)

@pytest.fixture
def auth_headers():
    return {"X-INTERNAL-AUTH": settings.internal_auth_secret}

def test_health_check():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "healthy"

def test_missing_auth_rejected():
    """Endpoints must reject requests without the internal auth header."""
    response = client.post("/internal/pipeline/analyze", json={"query": "test"})
    assert response.status_code == 401

def test_invalid_auth_rejected():
    """Endpoints must reject requests with wrong internal auth header."""
    response = client.post(
        "/internal/pipeline/analyze", 
        json={"query": "test"},
        headers={"X-INTERNAL-AUTH": "wrong_secret"}
    )
    assert response.status_code == 401

@patch("engine_app.OpportunityPipeline")
def test_analyze_pipeline_success(MockPipeline, auth_headers):
    """Valid request calls pipeline and serializes output."""
    mock_instance = MockPipeline.return_value
    mock_result = MagicMock()
    mock_result.to_dict.return_value = {"mock": "data"}
    mock_instance.analyze.return_value = [mock_result]

    payload = {
        "query": "wireless earbuds",
        "marketplace": "US",
        "limit": 5
    }

    response = client.post(
        "/internal/pipeline/analyze", 
        json=payload, 
        headers=auth_headers
    )
    
    assert response.status_code == 200
    data = response.json()
    assert "results" in data
    assert len(data["results"]) == 1
    assert data["results"][0] == {"mock": "data"}

def test_calculate_profit_success(auth_headers):
    """Valid profit request calculates correctly."""
    payload = {
        "marketplace": "US",
        "sold_price": 50.0,
        "item_cost": 15.0,
        "shipping_cost": 5.0,
        "promoted_rate": 5.0
    }

    response = client.post(
        "/internal/profit/calculate", 
        json=payload, 
        headers=auth_headers
    )
    
    assert response.status_code == 200
    data = response.json()
    assert "net_profit_per_item" in data
    assert "profit_margin" in data