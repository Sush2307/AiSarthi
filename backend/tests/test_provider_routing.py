"""Tests for 3-Level Provider Routing, Intelligent Healthcare Retrieval, and Grounding.

Covers:
1. HostedQwenProvider circuit breaker, timeout, and event stream parsing.
2. LocalQwenProvider safe lifecycle and error handling.
3. DeterministicEvidenceProvider verified statistical computations and answers.
4. ProviderRouter automatic fallback: Hosted -> Local -> Deterministic.
5. Indicator discovery queries ("What healthcare indicators are available for Maharashtra?").
6. Indian state & district alias resolution (MH -> Maharashtra, Bombay -> Mumbai).
7. Strict numerical evidence grounding and hallucination prevention.
8. API schema compatibility with frontend expectations.
"""
from __future__ import annotations
import json
import time
from unittest.mock import MagicMock, patch
import pytest
from fastapi.testclient import TestClient

from app.config import master_path
from app.data import Dataset
from app.model import ModelService
from app.providers import (
    HostedQwenProvider,
    LocalQwenProvider,
    DeterministicEvidenceProvider,
)
from app.main import app


@pytest.fixture(scope="module")
def shared_dataset():
    return Dataset(master_path())


@pytest.fixture
def client(shared_dataset):
    app.state.data = shared_dataset
    app.state.model = ModelService()
    return TestClient(app)


# ---------------------------------------------------------------------------
# 1. HostedQwenProvider & Circuit Breaker Tests
# ---------------------------------------------------------------------------

def test_hosted_provider_circuit_breaker():
    """Verify that consecutive failures trip the circuit breaker and avoid repeated timeouts."""
    provider = HostedQwenProvider(
        base_url="https://mock-space.hf.space",
        timeout=1.0,
        cooldown_seconds=10.0,
        failure_threshold=2,
    )
    assert provider.is_available() is True
    assert provider.circuit_open is False

    # Simulate 1st failure
    provider._record_failure("HTTP 504 Gateway Timeout")
    assert provider.consecutive_failures == 1
    assert provider.circuit_open is False
    assert provider.is_available() is True

    # Simulate 2nd failure (threshold reached)
    provider._record_failure("HTTP 504 Gateway Timeout")
    assert provider.consecutive_failures == 2
    assert provider.circuit_open is True
    assert provider.is_available() is False

    # During cooldown, generate raises immediately without making network calls
    with pytest.raises(RuntimeError, match="circuit is cooling down"):
        provider.generate("test question", [])

    st = provider.get_status()
    assert st["circuit_open"] is True
    assert st["consecutive_failures"] == 2
    assert st["cooldown_remaining_seconds"] > 0

    # Simulate cooldown expiry
    provider.last_failure_time = time.time() - 15.0
    assert provider.circuit_open is False

    # Simulate success resetting circuit
    provider._record_success()
    assert provider.consecutive_failures == 0
    assert provider.circuit_open is False
    assert provider.successful_requests == 1


def test_hosted_provider_successful_sse_parsing(monkeypatch):
    """Verify that HostedQwenProvider parses Gradio 5 SSE event stream correctly."""
    provider = HostedQwenProvider(base_url="https://mock-space.hf.space", timeout=5.0)

    class MockStream:
        def __enter__(self): return self
        def __exit__(self, *args): pass
        def iter_lines(self):
            return [
                "event: heartbeat",
                "data: null",
                "event: generating",
                'data: ["Institutional births in Pune is 97.97%."]',
                "event: complete",
            ]

    class MockClient:
        def __init__(self, *args, **kwargs): pass
        def __enter__(self): return self
        def __exit__(self, *args): pass
        def post(self, url, json):
            mock_resp = MagicMock()
            mock_resp.status_code = 200
            mock_resp.json.return_value = {"event_id": "evt_12345"}
            return mock_resp
        def stream(self, method, url, timeout):
            return MockStream()

    monkeypatch.setattr("httpx.Client", MockClient)
    records = [{"indicator": "institutional_births", "value": 97.97, "district": "Pune", "source": "NFHS-5"}]
    answer = provider.generate("Institutional births in Pune?", records)
    assert answer == "Institutional births in Pune is 97.97%."
    assert provider.successful_requests == 1


# ---------------------------------------------------------------------------
# 2. LocalQwenProvider Safe Lifecycle Tests
# ---------------------------------------------------------------------------

def test_local_provider_missing_adapter_graceful():
    """Verify LocalQwenProvider handles missing adapter gracefully without crashing."""
    provider = LocalQwenProvider()
    st = provider.get_status()
    assert st["provider_id"] == "local_qwen"
    assert provider.loaded is False

    with pytest.raises(RuntimeError, match="not available"):
        provider.generate("test question", [])


# ---------------------------------------------------------------------------
# 3. DeterministicEvidenceProvider Verified Calculation Tests
# ---------------------------------------------------------------------------

def test_deterministic_provider_single_record():
    provider = DeterministicEvidenceProvider()
    record = {
        "indicator": "institutional_births_percent",
        "value": 97.97,
        "district": "Pune",
        "year": "2019-20",
        "source": "NFHS-5",
        "unit": "%",
    }
    answer = provider.generate("Institutional births in Pune", [record], intent="exact_statistic")
    assert "NFHS-5" in answer
    assert "97.97%" in answer
    assert "Pune" in answer


def test_deterministic_provider_comparison_computation():
    provider = DeterministicEvidenceProvider()
    records = [
        {"indicator": "institutional_births", "value": 97.5, "district": "Pune", "year": "2020", "source": "NFHS-5", "unit": "%"},
        {"indicator": "institutional_births", "value": 91.2, "district": "Nashik", "year": "2020", "source": "NFHS-5", "unit": "%"},
    ]
    answer = provider.generate("Compare institutional births in Pune vs Nashik", records, intent="comparison")
    assert "**Pune**: 97.5%" in answer
    assert "**Nashik**: 91.2%" in answer
    assert "highest observation" in answer
    assert "6.3%" in answer  # 97.5 - 91.2 = 6.3


def test_deterministic_provider_trend_computation():
    provider = DeterministicEvidenceProvider()
    records = [
        {"indicator": "institutional_births", "value": 85.0, "district": "Pune", "year": "2015", "source": "NFHS-4", "unit": "%"},
        {"indicator": "institutional_births", "value": 92.5, "district": "Pune", "year": "2020", "source": "NFHS-5", "unit": "%"},
    ]
    answer = provider.generate("Trend in institutional births in Pune", records, intent="trend")
    assert "**2015**: 85.0%" in answer
    assert "**2020**: 92.5%" in answer
    assert "increase of 7.5%" in answer


def test_deterministic_provider_indicator_discovery():
    provider = DeterministicEvidenceProvider()
    records = [
        {"indicator": "institutional_births_percent", "state": "Maharashtra", "source": "NFHS-5", "year": "2019-20"},
        {"indicator": "children_fully_vaccinated_percent", "state": "Maharashtra", "source": "NFHS-5", "year": "2019-20"},
        {"indicator": "mothers_who_had_4_anc_visits_percent", "state": "Maharashtra", "source": "NFHS-5", "year": "2019-20"},
    ]
    answer = provider.generate("What healthcare indicators are available for Maharashtra?", records, intent="available_indicators")
    assert "Maharashtra" in answer
    assert "Institutional Births Percent" in answer
    assert "Children Fully Vaccinated Percent" in answer


# ---------------------------------------------------------------------------
# 4. Intelligent Retrieval & Indicator Discovery Tests
# ---------------------------------------------------------------------------

def test_retrieval_indicator_discovery_query(shared_dataset):
    """Test indicator discovery query: 'What healthcare indicators are available for Maharashtra?'."""
    locs = shared_dataset.detect_locations("What healthcare indicators are available for Maharashtra?")
    assert locs["state"] == "Maharashtra"

    intent = shared_dataset.classify_intent("What healthcare indicators are available for Maharashtra?", locs)
    assert intent == "available_indicators"

    recs = shared_dataset.retrieve(
        "What healthcare indicators are available for Maharashtra?",
        state=locs["state"],
        intent=intent,
        limit=10,
    )
    # Must NOT be empty!
    assert not recs.empty
    assert len(recs) >= 5
    distinct_indicators = recs["indicator"].nunique()
    assert distinct_indicators >= 3


def test_location_alias_normalization(shared_dataset):
    """Verify state abbreviations and city aliases normalize to canonical dataset entities."""
    # MH abbreviation
    locs_mh = shared_dataset.detect_locations("Show institutional births in MH")
    assert locs_mh["state"] == "Maharashtra"

    # UP abbreviation
    locs_up = shared_dataset.detect_locations("What is the maternal mortality in UP?")
    assert locs_up["state"] == "Uttar Pradesh"

    # Bombay historical alias
    locs_bombay = shared_dataset.detect_locations("Show immunization in Bombay")
    assert locs_bombay["district"] == "Mumbai"

    # Poona historical alias
    locs_poona = shared_dataset.detect_locations("Data for Poona")
    assert locs_poona["district"] == "Pune"


def test_retrieval_comparison_query_multiple_districts(shared_dataset):
    """Verify comparing Pune vs Nashik returns records for BOTH locations."""
    q = "Compare institutional births in Pune vs Nashik"
    locs = shared_dataset.detect_locations(q)
    assert "Pune" in locs["all_districts"]
    assert "Nashik" in locs["all_districts"]

    intent = shared_dataset.classify_intent(q, locs)
    assert intent == "comparison"

    recs = shared_dataset.retrieve(
        q,
        intent=intent,
        all_locations=locs["all_districts"],
        limit=20,
    )
    assert not recs.empty
    districts_found = set(recs["district_clean"].str.lower().unique())
    assert "pune" in districts_found
    assert "nashik" in districts_found


# ---------------------------------------------------------------------------
# 5. 3-Level Routing & Fallback Integration Tests
# ---------------------------------------------------------------------------

def test_chat_routes_to_hosted_when_healthy(client, monkeypatch):
    """When hosted provider is healthy and grounded, chat uses hosted output."""
    monkeypatch.setenv("PRIMARY_PROVIDER", "hosted")
    mock_service = ModelService()
    mock_service.openrouter_provider.is_available = MagicMock(return_value=False)
    # Mock hosted provider
    mock_hosted = MagicMock()
    mock_hosted.is_available.return_value = True
    mock_hosted.circuit_open = False
    mock_hosted.generate.return_value = "Official NFHS-5 recorded institutional births in Pune as 97.97%."

    mock_service.hosted_provider = mock_hosted
    client.app.state.model = mock_service

    res = client.post("/api/chat", json={"question": "What is institutional births in Pune?"})
    assert res.status_code == 200
    data = res.json()
    assert data["mode"] == "live"
    assert data["inference_mode"] == "hosted-qwen"
    assert data["fallback_used"] is False
    assert "97.97%" in data["answer"]


def test_chat_falls_back_when_hosted_fails(client, monkeypatch):
    """When hosted provider fails, chat automatically falls back to deterministic fallback."""
    monkeypatch.setenv("PRIMARY_PROVIDER", "hosted")
    mock_service = ModelService()
    mock_service.openrouter_provider.is_available = MagicMock(return_value=False)
    # Simulate hosted provider failing with timeout
    mock_hosted = MagicMock()
    mock_hosted.is_available.return_value = True
    mock_hosted.circuit_open = False
    mock_hosted.generate.side_effect = RuntimeError("Connection timed out after 15s")

    mock_service.hosted_provider = mock_hosted
    client.app.state.model = mock_service

    res = client.post("/api/chat", json={"question": "What is institutional births in Pune?"})
    assert res.status_code == 200
    data = res.json()
    assert data["mode"] == "retrieval-only"
    assert data["inference_mode"] == "retrieval-only-fallback"
    assert data["fallback_used"] is True
    assert "Hosted provider" in data["fallback_reason"]
    # Answer is validly derived from evidence
    assert "Pune" in data["answer"]


def test_chat_grounding_catches_hallucination_and_falls_back(client, monkeypatch):
    """When model generates an unverified number, grounding check rejects it and uses deterministic answer."""
    monkeypatch.setenv("PRIMARY_PROVIDER", "hosted")
    mock_service = ModelService()
    mock_service.openrouter_provider.is_available = MagicMock(return_value=False)
    mock_hosted = MagicMock()
    mock_hosted.is_available.return_value = True
    mock_hosted.circuit_open = False
    # Model hallucinated 52.3% (not in Pune records where value is ~97.97%)
    mock_hosted.generate.return_value = "Official data shows institutional births in Pune reached 52.3%."

    mock_service.hosted_provider = mock_hosted
    client.app.state.model = mock_service

    res = client.post("/api/chat", json={"question": "What is institutional births in Pune?"})
    assert res.status_code == 200
    data = res.json()
    assert data["mode"] == "retrieval-only"
    assert data["fallback_used"] is True
    assert "Hosted numerical grounding check failed" in data["fallback_reason"]
    # Hallucinated number 52.3% is NOT presented to the user
    assert "52.3" not in data["answer"]
    # Grounded location is presented
    assert "Pune" in data["answer"]


def test_health_endpoint_backward_compatibility_and_diagnostics(client):
    """Verify /api/health retains exact backward-compatible fields plus new provider diagnostics."""
    res = client.get("/api/health")
    assert res.status_code == 200
    data = res.json()

    # Required baseline fields
    assert data["status"] == "ok"
    assert isinstance(data["records"], int)
    assert "model_loaded" in data
    assert "model_enabled" in data
    assert "model_available" in data
    assert "device" in data
    assert "precision" in data
    assert "base_model_id" in data

    # New provider diagnostics
    assert "primary_provider" in data
    assert "circuit_breaker" in data
    assert "providers" in data
    assert "hosted" in data["providers"]
    assert "local" in data["providers"]
    assert "deterministic" in data["providers"]
