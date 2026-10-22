"""Tests for OpenRouter Inference Provider, Error Handling, Grounding, and Routing Fallback."""
from __future__ import annotations
import json
import os
import pytest
from unittest.mock import MagicMock, patch
import httpx
from starlette.testclient import TestClient

from app.config import (
    openrouter_enabled,
    openrouter_api_key,
    openrouter_model,
    openrouter_timeout,
    primary_provider,
)
from app.providers import OpenRouterProvider, DeterministicEvidenceProvider
from app.model import ModelService
from app.main import app


# 1. Disabled by default without key
def test_openrouter_disabled_without_key(monkeypatch):
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    monkeypatch.delenv("OPENROUTER_ENABLED", raising=False)
    provider = OpenRouterProvider(api_key=None)
    assert not provider.enabled
    assert not provider.is_available()
    st = provider.get_status()
    assert st["configured"] is False
    assert st["available"] is False


# 2. Successful OpenRouter response
def test_openrouter_successful_generation(monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-secret-key-12345")
    monkeypatch.setenv("OPENROUTER_ENABLED", "1")
    monkeypatch.setenv("OPENROUTER_MODEL", "google/gemini-2.0-flash-001")

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "choices": [
            {
                "message": {
                    "role": "assistant",
                    "content": "According to NFHS-5 (2019-2021), institutional births in Pune was 97.97%.",
                }
            }
        ]
    }

    provider = OpenRouterProvider()
    assert provider.enabled
    assert provider.is_available()

    records = [
        {
            "indicator": "institutional births in the 5 years before the survey percent",
            "value": 97.97,
            "state": "Maharashtra",
            "district": "Pune",
            "year": "2019-2021",
            "source": "NFHS-5",
            "geographic_level": "district",
        }
    ]

    with patch.object(httpx.Client, "post", return_value=mock_resp) as mock_post:
        res = provider.generate("Institutional births in Pune", records)
        assert "97.97%" in res
        assert mock_post.called
        headers = mock_post.call_args.kwargs["headers"]
        # Authorization header formatted correctly
        assert headers["Authorization"] == "Bearer test-secret-key-12345"
        assert "HTTP-Referer" in headers
        assert "X-Title" in headers
        # Payload verification
        payload = mock_post.call_args.kwargs["json"]
        assert payload["model"] == "google/gemini-2.0-flash-001"
        assert len(payload["messages"]) == 2
        assert "Pune" in payload["messages"][1]["content"]


# 3. Invalid API key (HTTP 401)
def test_openrouter_invalid_api_key(monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "invalid-key")
    monkeypatch.setenv("OPENROUTER_ENABLED", "1")

    mock_resp = MagicMock()
    mock_resp.status_code = 401
    mock_resp.text = "Unauthorized"

    provider = OpenRouterProvider()
    with patch.object(httpx.Client, "post", return_value=mock_resp):
        with pytest.raises(RuntimeError) as exc_info:
            provider.generate("Test question", [{"indicator": "test", "value": 10}])
        assert "Invalid or missing API key" in str(exc_info.value)
        # Ensure secret API key is never leaked in exception
        assert "invalid-key" not in str(exc_info.value)


# 4. Rate limiting (HTTP 429) and bounded retries
def test_openrouter_rate_limiting_retries_and_failure(monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")
    monkeypatch.setenv("OPENROUTER_ENABLED", "1")

    mock_resp = MagicMock()
    mock_resp.status_code = 429
    mock_resp.text = "Rate limit exceeded"

    provider = OpenRouterProvider(max_retries=1)
    with patch.object(httpx.Client, "post", return_value=mock_resp) as mock_post:
        with patch("time.sleep"):
            with pytest.raises(RuntimeError) as exc_info:
                provider.generate("Test question", [{"indicator": "test", "value": 10}])
            assert "rate limit" in str(exc_info.value).lower()
            # Retried exactly max_retries + 1 times
            assert mock_post.call_count == 2


# 5. Timeout handling
def test_openrouter_timeout_handling(monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")
    monkeypatch.setenv("OPENROUTER_ENABLED", "1")

    provider = OpenRouterProvider(timeout=1.0, max_retries=0)
    with patch.object(httpx.Client, "post", side_effect=httpx.TimeoutException("Read timed out")):
        with pytest.raises(RuntimeError) as exc_info:
            provider.generate("Test question", [{"indicator": "test", "value": 10}])
        assert "timed out" in str(exc_info.value).lower()


# 6. Malformed response handling
def test_openrouter_malformed_response(monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")
    monkeypatch.setenv("OPENROUTER_ENABLED", "1")

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {"error": "unexpected format"}

    provider = OpenRouterProvider()
    with patch.object(httpx.Client, "post", return_value=mock_resp):
        with pytest.raises(RuntimeError) as exc_info:
            provider.generate("Test question", [{"indicator": "test", "value": 10}])
        assert "malformed" in str(exc_info.value).lower()


# 7. Real evidence included in prompt
def test_openrouter_real_evidence_in_prompt(monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")
    provider = OpenRouterProvider()

    records = [
        {
            "indicator": "institutional_births_percent",
            "value": 94.2,
            "state": "Maharashtra",
            "district": "Pune",
            "year": "2020",
            "source": "HMIS",
            "geographic_level": "district",
        }
    ]

    headers, payload = provider._build_payload("Institutional births in Pune", records, "exact_statistic")
    user_msg = payload["messages"][1]["content"]
    assert "institutional_births_percent" in user_msg
    assert "94.2" in user_msg
    assert "Pune" in user_msg
    assert "HMIS" in user_msg
    assert "2020" in user_msg


# 8. Unsupported generated number rejected by ModelService
def test_openrouter_unsupported_generated_number_rejected(monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")
    monkeypatch.setenv("PRIMARY_PROVIDER", "openrouter")

    service = ModelService()
    # Mock OpenRouter returning a fabricated number (42.5%) not in retrieved records
    with patch.object(service.openrouter_provider, "is_available", return_value=True):
        with patch.object(
            service.openrouter_provider,
            "generate",
            return_value="The institutional births in Pune was fabricated at 42.5%.",
        ):
            records = [
                {
                    "indicator": "institutional births in the 5 years before the survey percent",
                    "value": 97.97,
                    "district": "Pune",
                    "state": "Maharashtra",
                    "year": "2019-2021",
                    "source": "NFHS-5",
                    "unit": "%",
                }
            ]
            res = service.generate_routed("Institutional births in Pune", records)
            # Rejected candidate and used deterministic fallback
            assert res["mode"] == "retrieval-only"
            assert res["fallback_used"] is True
            assert "grounding check failed" in res["fallback_reason"].lower()
            assert "97.97" in res["answer"]
            assert "42.5" not in res["answer"]


# 9. Fallback when OpenRouter fails
def test_openrouter_failure_triggers_fallback(monkeypatch):
    monkeypatch.setenv("PRIMARY_PROVIDER", "openrouter")
    service = ModelService()

    with patch.object(service.openrouter_provider, "is_available", return_value=True):
        with patch.object(service.openrouter_provider, "generate", side_effect=RuntimeError("OpenRouter 503 Outage")):
            records = [
                {
                    "indicator": "institutional births in the 5 years before the survey percent",
                    "value": 97.97,
                    "district": "Pune",
                    "state": "Maharashtra",
                    "year": "2019-2021",
                    "source": "NFHS-5",
                    "unit": "%",
                }
            ]
            res = service.generate_routed("Institutional births in Pune", records)
            assert res["fallback_used"] is True
            assert "503 Outage" in res["fallback_reason"]
            assert "97.97" in res["answer"]


# 10. Empty retrieval results returns no_data without LLM call
def test_openrouter_empty_retrieval_does_not_call_llm(client: TestClient):
    with patch.object(OpenRouterProvider, "generate") as mock_gen:
        res = client.post("/api/chat", json={"question": "What is the metric in Atlantis District?"})
        assert res.status_code == 200
        data = res.json()
        assert data["answer_type"] == "no_data"
        assert not mock_gen.called


# 11. Existing API compatibility and health status
def test_openrouter_health_endpoint_schema(client: TestClient):
    res = client.get("/api/health")
    assert res.status_code == 200
    data = res.json()
    assert "status" in data
    assert "providers" in data
    providers = data["providers"]
    assert "openrouter" in providers
    assert "hosted" in providers
    assert "local" in providers
    assert "deterministic" in providers
    op_status = providers["openrouter"]
    assert "enabled" in op_status
    assert "configured" in op_status
    assert "available" in op_status
    # Ensure no API key secret is leaked in health status
    assert "api_key" not in op_status


# 12. Maharashtra indicator discovery with actual records
def test_openrouter_maharashtra_discovery_integration(client: TestClient):
    res = client.post("/api/chat", json={"question": "What healthcare indicators are available for Maharashtra?"})
    assert res.status_code == 200
    data = res.json()
    assert data["answer_type"] in ["dataset_only", "ai_generated", "multiple_records"]
    assert "Maharashtra" in data["answer"]
    assert len(data["records"]) > 0
    prov = data.get("evidence_summary", {}).get("provenance", {})
    assert prov.get("records_matched", 0) > 0


# 13. Optional Live Integration Test (only executes if real key is present)
def test_openrouter_live_integration_if_key_present():
    real_key = os.getenv("OPENROUTER_API_KEY")
    if not real_key or not real_key.strip() or real_key.startswith("test-"):
        pytest.skip("Skipping live OpenRouter API call: OPENROUTER_API_KEY not configured with real credential.")

    provider = OpenRouterProvider(api_key=real_key)
    records = [
        {
            "indicator": "institutional births in the 5 years before the survey percent",
            "value": 97.97,
            "district": "Pune",
            "state": "Maharashtra",
            "year": "2019-2021",
            "source": "NFHS-5",
            "unit": "%",
        }
    ]
    try:
        answer = provider.generate("What is institutional births in Pune?", records)
        assert isinstance(answer, str)
        assert len(answer) > 10
        assert "Pune" in answer or "97.97" in answer
    except RuntimeError as e:
        if "rate limit" in str(e).lower() or "insufficient" in str(e).lower() or "credits" in str(e).lower():
            pytest.skip(f"OpenRouter upstream quota/credit temporarily exhausted: {e}")
        raise
