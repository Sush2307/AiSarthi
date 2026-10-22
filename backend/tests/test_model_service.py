"""Comprehensive tests for ModelService, configuration validation, evidence grounding,

inference lifecycle, and deterministic fallback.
"""
import json
from pathlib import Path
from unittest.mock import MagicMock, patch
import pytest
from fastapi.testclient import TestClient

from app.model import ModelService
from app import config


def test_model_disabled_config(monkeypatch):
    """Test 1: When MODEL_ENABLED=0, model remains unloaded and retrieval-only mode is active."""
    monkeypatch.setenv("MODEL_ENABLED", "0")
    monkeypatch.setenv("LOAD_MODEL", "0")
    service = ModelService()
    service.load()
    assert not service.loaded
    assert not service.available
    assert "retrieval-only" in service.diagnostic.lower()


def test_adapter_directory_missing(monkeypatch, tmp_path):
    """Test 2: Missing adapter directory produces a clear diagnostic and preserves retrieval-only mode."""
    non_existent = tmp_path / "non_existent_adapter_dir"
    monkeypatch.setenv("MODEL_ENABLED", "1")
    monkeypatch.setenv("ADAPTER_PATH", str(non_existent))
    monkeypatch.setenv("STRICT_MODEL_REQUIRED", "0")
    
    service = ModelService()
    service.load()
    assert not service.loaded
    assert not service.available
    assert "Adapter directory not found" in service.error
    assert "retrieval-only mode" in service.diagnostic


def test_strict_model_required_raises(monkeypatch, tmp_path):
    """Test 3: STRICT_MODEL_REQUIRED=1 raises when adapter is missing."""
    non_existent = tmp_path / "non_existent_adapter_dir"
    monkeypatch.setenv("MODEL_ENABLED", "1")
    monkeypatch.setenv("ADAPTER_PATH", str(non_existent))
    monkeypatch.setenv("STRICT_MODEL_REQUIRED", "1")
    
    service = ModelService()
    with pytest.raises(FileNotFoundError):
        service.load()


def test_invalid_adapter_config(monkeypatch, tmp_path):
    """Test 4: Corrupted adapter_config.json is handled gracefully without crashing."""
    ad_dir = tmp_path / "corrupt_adapter"
    ad_dir.mkdir()
    cfg_file = ad_dir / "adapter_config.json"
    cfg_file.write_text("{ this is not valid json", encoding="utf-8")
    
    monkeypatch.setenv("MODEL_ENABLED", "1")
    monkeypatch.setenv("ADAPTER_PATH", str(ad_dir))
    monkeypatch.setenv("STRICT_MODEL_REQUIRED", "0")
    
    service = ModelService()
    # Mock transformers to prevent external network lookups
    with patch("transformers.AutoTokenizer.from_pretrained", side_effect=Exception("Missing tokenizer files")):
        service.load()
        assert not service.loaded
        assert service.error is not None
        assert "Missing tokenizer files" in service.error


def test_model_service_mock_initialization(monkeypatch, tmp_path):
    """Test 5: Successful model and tokenizer loading sets evaluation mode and correct status."""
    ad_dir = tmp_path / "valid_adapter"
    ad_dir.mkdir()
    cfg_file = ad_dir / "adapter_config.json"
    cfg_file.write_text(json.dumps({"base_model_name_or_path": "Qwen/Qwen3-1.7B"}), encoding="utf-8")

    monkeypatch.setenv("MODEL_ENABLED", "1")
    monkeypatch.setenv("ADAPTER_PATH", str(ad_dir))
    monkeypatch.setenv("MODEL_DEVICE", "cpu")

    mock_tokenizer = MagicMock()
    mock_tokenizer.pad_token_id = 0
    mock_tokenizer.eos_token_id = 0
    mock_base = MagicMock()
    mock_peft = MagicMock()
    mock_peft.eval.return_value = mock_peft

    with patch("transformers.AutoTokenizer.from_pretrained", return_value=mock_tokenizer), \
         patch("transformers.AutoModelForCausalLM.from_pretrained", return_value=mock_base), \
         patch("peft.PeftModel.from_pretrained", return_value=mock_peft):
        service = ModelService()
        service.load()
        assert service.loaded
        assert service.available
        assert service.device == "cpu"
        assert service.precision == "float32"
        mock_peft.eval.assert_called_once()


def test_evidence_grounding_validation_success():
    """Test 6: validate_evidence_grounding approves answers whose numbers match verified records."""
    records = [
        {"district": "Pune", "indicator": "institutional_births", "value": 97.97, "year": "2019-2021"},
        {"district": "Mumbai", "indicator": "institutional_births", "value": 99.53, "year": "2019-2021"},
    ]
    answer = "In Pune, institutional births reached 97.97% while Mumbai recorded 99.53% according to official records."
    is_grounded, failure = ModelService.validate_evidence_grounding(answer, records)
    assert is_grounded
    assert failure is None


def test_evidence_grounding_validation_catches_hallucination():
    """Test 7: validate_evidence_grounding rejects answers with unverified invented numbers."""
    records = [
        {"district": "Pune", "indicator": "institutional_births", "value": 80.0, "year": "2019-2021"},
    ]
    # Model hallucinated 99.5% which does not exist in records
    hallucinated_answer = "Institutional births in Pune are exceptionally high at 99.5%."
    is_grounded, failure = ModelService.validate_evidence_grounding(hallucinated_answer, records)
    assert not is_grounded
    assert "unverified numbers" in failure
    assert "99.5" in failure


def test_chat_endpoint_grounded_model_inference(client):
    """Test 8: When model generates verified text, response has mode=live and ai_generated."""
    mock_model_service = MagicMock()
    mock_model_service.loaded = True
    mock_model_service.available = True
    mock_model_service.enabled = True
    mock_model_service.device = "mock-cpu"
    # Return text with real number from test fixture (80.0)
    mock_model_service.generate.return_value = (
        "According to official NFHS-5 data for 2020, institutional births in Test State (Alpha) was 80.0%."
    )
    mock_model_service.validate_evidence_grounding.return_value = (True, None)

    client.app.state.model = mock_model_service

    res = client.post("/api/chat", json={"question": "What is institutional births in Alpha?"})
    assert res.status_code == 200
    data = res.json()
    assert data["mode"] == "live"
    assert data["inference_mode"] == "model-generated"
    assert data["answer_type"] == "ai_generated"
    assert not data["fallback_used"]
    assert "80.0%" in data["answer"]


def test_chat_endpoint_hallucination_triggers_deterministic_fallback(client):
    """Test 9: When model hallucinates a number, chat endpoint falls back to deterministic response."""
    mock_model_service = MagicMock()
    mock_model_service.loaded = True
    mock_model_service.available = True
    mock_model_service.enabled = True
    mock_model_service.device = "mock-cpu"
    # Model returns fabricated number 99.9%
    mock_model_service.generate.return_value = "Institutional births in Alpha was 99.9%."
    # Use real validator
    mock_model_service.validate_evidence_grounding = ModelService.validate_evidence_grounding

    client.app.state.model = mock_model_service

    res = client.post("/api/chat", json={"question": "What is institutional births in Alpha?"})
    assert res.status_code == 200
    data = res.json()
    assert data["fallback_used"] is True
    assert data["inference_mode"] == "retrieval-only-fallback"
    assert "Numerical grounding verification" in data["fallback_reason"]
    # Grounded value (80.0 or 85.0 from CSV) is returned, NOT 99.9%
    assert "99.9" not in data["answer"]
    assert "Based on verified records" in data["answer"]


def test_chat_endpoint_model_exception_triggers_deterministic_fallback(client):
    """Test 10: Model exception triggers graceful fallback without raising 500."""
    mock_model_service = MagicMock()
    mock_model_service.loaded = True
    mock_model_service.available = True
    mock_model_service.enabled = True
    mock_model_service.generate.side_effect = RuntimeError("CUDA Out of Memory")

    client.app.state.model = mock_model_service

    res = client.post("/api/chat", json={"question": "What is institutional births in Alpha?"})
    assert res.status_code == 200
    data = res.json()
    assert data["fallback_used"] is True
    assert data["inference_mode"] == "retrieval-only-fallback"
    assert "CUDA Out of Memory" in data["fallback_reason"]
    assert "Based on verified records" in data["answer"]


def test_scheme_query_distinction(client):
    """Test 11: Questions concerning schemes return verified scheme information."""
    res = client.post("/api/chat", json={"question": "What is the PM-JAY scheme eligibility?"})
    assert res.status_code == 200
    data = res.json()
    assert data["mode"] == "verified-scheme"
    assert data["inference_mode"] == "verified-scheme"
    assert "PM-JAY" in data["answer"] or "Ayushman" in data["answer"]


def test_unsupported_question_insufficient_evidence(client):
    """Test 12: Questions with no matching evidence return insufficient-evidence status."""
    res = client.post("/api/chat", json={"question": "What is the astronaut count in Mars colony?"})
    assert res.status_code == 200
    data = res.json()
    assert data["answer_type"] == "no_data"
    assert data["inference_mode"] == "insufficient-evidence"
    assert len(data["records"]) == 0


def test_missing_values_preserved_in_evidence_context():
    """Test 13: Missing values in records remain None and are not converted to 0.0 in evidence context."""
    service = ModelService()
    records = [{"district": "Alpha", "indicator": "anaemia", "value": None, "year": "2021"}]
    ctx_str = service.build_evidence_context(records)
    ctx = json.loads(ctx_str)
    assert ctx[0]["value"] is None
    assert ctx[0]["value"] != 0.0


def test_health_endpoint_model_diagnostics(client):
    """Test 14: /api/health reports comprehensive model diagnostics."""
    res = client.get("/api/health")
    assert res.status_code == 200
    data = res.json()
    assert "status" in data
    assert "records" in data
    assert "model_loaded" in data
    assert "model_enabled" in data
    assert "model_available" in data
    assert "device" in data
    assert "base_model_id" in data
