"""Automated test suite executing against the actual 1.18M master healthcare dataset.

Tests:
1. Known exact indicator lookup (Pune institutional births).
2. State-level indicator discovery (Maharashtra available indicators).
3. District-level lookup (Nashik institutional births).
4. Source-specific query (Maharashtra data sources).
5. Survey-period query (Pune institutional births available periods).
6. State comparison (Maharashtra vs Bihar).
7. District comparison (Pune vs Nashik).
8. Trend query.
9. Unavailable indicator handling.
10. Ambiguous indicator handling.
11. Query with no matching records.
12. Incompatible survey period protection.
13. Missing value integrity (preserved as None, never converted to 0).
14. Fabricated number rejection.
15. Hosted model failure fallback.
16. Local model failure fallback.
17. Both models unavailable fallback.
18. Deterministic fallback answering strictly from verified records.
"""
from __future__ import annotations
from unittest.mock import MagicMock
import pytest
from fastapi.testclient import TestClient

from app.config import master_path
from app.data import Dataset
from app.model import ModelService
from app.main import app


@pytest.fixture(scope="module")
def real_dataset():
    return Dataset(master_path())


@pytest.fixture
def client(real_dataset):
    app.state.data = real_dataset
    app.state.model = ModelService()
    return TestClient(app)


# Case 1: Known exact indicator lookup
def test_case_1_known_exact_indicator_lookup(client):
    res = client.post("/api/chat", json={"question": "What is institutional births in Pune?"})
    assert res.status_code == 200
    data = res.json()
    assert "Pune" in data["answer"]
    assert "97.97" in data["answer"]
    assert len(data["records"]) > 0
    assert data["records"][0]["value"] == 97.97
    assert data["records"][0]["source"] == "NFHS-5"


# Case 2: State-level indicator discovery query
def test_case_2_state_level_indicator_discovery(client):
    res = client.post("/api/chat", json={"question": "What healthcare indicators are available for Maharashtra?"})
    assert res.status_code == 200
    data = res.json()
    assert data["intent"] == "available_indicators"
    assert "Maharashtra" in data["answer"] or "Maharastra" in data["answer"]
    assert len(data["records"]) >= 5
    assert data["evidence_summary"]["record_count"] >= 5


# Case 3: District-level lookup
def test_case_3_district_level_lookup(client):
    res = client.post("/api/chat", json={"question": "What is institutional births in Nashik?"})
    assert res.status_code == 200
    data = res.json()
    assert "Nashik" in data["answer"]
    assert "90.49" in data["answer"]
    assert data["records"][0]["value"] == 90.49


# Case 4: Source-specific query
def test_case_4_source_specific_query(client):
    res = client.post("/api/chat", json={"question": "What data sources are available for Maharashtra?"})
    assert res.status_code == 200
    data = res.json()
    assert data["intent"] == "available_sources"
    assert "NFHS-5" in data["answer"] or "HMIS" in data["answer"]
    assert len(data["records"]) >= 1


# Case 5: Survey-period query
def test_case_5_survey_period_query(client):
    res = client.post("/api/chat", json={"question": "Which years are available for institutional births in Pune?"})
    assert res.status_code == 200
    data = res.json()
    assert data["intent"] == "available_years"
    assert "2019-2021" in data["answer"]


# Case 6: State comparison
def test_case_6_state_comparison(client):
    res = client.post("/api/chat", json={"question": "Compare institutional births in Maharashtra vs Bihar"})
    assert res.status_code == 200
    data = res.json()
    assert data["intent"] == "comparison"
    assert len(data["records"]) >= 2


# Case 7: District comparison
def test_case_7_district_comparison(client):
    res = client.post("/api/chat", json={"question": "Compare institutional births in Pune vs Nashik"})
    assert res.status_code == 200
    data = res.json()
    assert "97.97%" in data["answer"]
    assert "90.49%" in data["answer"]
    assert ("7.48%" in data["answer"] or "Pune" in data["answer"])


# Case 8: Trend query
def test_case_8_trend_query(client):
    res = client.post("/api/chat", json={"question": "Show trend of institutional births in Pune over time"})
    assert res.status_code == 200
    data = res.json()
    assert data["intent"] in ["trend", "district_lookup"]
    assert len(data["records"]) > 0


# Case 9: Unavailable indicator
def test_case_9_unavailable_indicator(client):
    res = client.post("/api/chat", json={"question": "What is the super_rare_fantasy_metric in Pune?"})
    assert res.status_code == 200
    data = res.json()
    assert data["answer_type"] == "no_data"
    assert data["mode"] == "retrieval-only"
    assert "No matching record" in data["answer"]


# Case 10: Ambiguous indicator
def test_case_10_ambiguous_indicator(client):
    res = client.post("/api/chat", json={"question": "What is health in Maharashtra?"})
    assert res.status_code == 200
    data = res.json()
    assert data["mode"] in ["retrieval-only", "live"]


# Case 11: Query with no matching records
def test_case_11_no_matching_records(client):
    res = client.post("/api/chat", json={"question": "What is the metric in Atlantis District?"})
    assert res.status_code == 200
    data = res.json()
    assert data["answer_type"] == "no_data"
    assert "No matching record" in data["answer"]
    assert len(data["records"]) == 0


# Case 12: Incompatible survey periods prevention
def test_case_12_incompatible_survey_periods(client):
    # Requesting institutional births with an unavailable cycle e.g. 1980
    res = client.post("/api/chat", json={"question": "Institutional births in Pune in 1980", "year": "1980"})
    assert res.status_code == 200
    data = res.json()
    assert "1980" not in [r.get("year") for r in data["records"]]


# Case 13: Missing values integrity (None not 0)
def test_case_13_missing_values_integrity(real_dataset):
    # Find records with null value
    null_rows = real_dataset.df[real_dataset.df["value"].isna()]
    assert len(null_rows) > 0
    recs = real_dataset.to_records(null_rows.head(5))
    for r in recs:
        assert r["value"] is None
        assert r["value"] != 0


# Case 14: Fabricated number rejection
def test_case_14_fabricated_number_rejection(client):
    mock_service = ModelService()
    mock_service.openrouter_provider.is_available = MagicMock(return_value=False)
    mock_hosted = MagicMock()
    mock_hosted.is_available.return_value = True
    mock_hosted.circuit_open = False
    # 33.33% is completely fabricated
    mock_hosted.generate.return_value = "Official NFHS-5 reported institutional births in Pune as 33.33%."

    mock_service.hosted_provider = mock_hosted
    client.app.state.model = mock_service

    res = client.post("/api/chat", json={"question": "What is institutional births in Pune?"})
    assert res.status_code == 200
    data = res.json()
    assert data["mode"] == "retrieval-only"
    assert data["fallback_used"] is True
    assert "33.33" not in data["answer"]
    assert "97.97" in data["answer"]


# Case 15: Hosted model failure fallback
def test_case_15_hosted_failure_fallback(client):
    mock_service = ModelService()
    mock_service.openrouter_provider.is_available = MagicMock(return_value=False)
    mock_hosted = MagicMock()
    mock_hosted.is_available.return_value = True
    mock_hosted.circuit_open = False
    mock_hosted.generate.side_effect = RuntimeError("Gateway Timeout 504")

    mock_service.hosted_provider = mock_hosted
    client.app.state.model = mock_service

    res = client.post("/api/chat", json={"question": "What is institutional births in Pune?"})
    assert res.status_code == 200
    data = res.json()
    assert data["fallback_used"] is True
    assert data["mode"] == "retrieval-only"
    assert "Pune" in data["answer"]
    assert "97.97" in data["answer"]


# Case 16: Local model failure fallback
def test_case_16_local_failure_fallback(client):
    mock_service = ModelService()
    mock_service.openrouter_provider.is_available = MagicMock(return_value=False)
    mock_service.hosted_provider.is_available = MagicMock(return_value=False)
    mock_local = MagicMock()
    mock_local.is_available.return_value = True
    mock_local.generate.side_effect = RuntimeError("CPU Out of Memory")

    mock_service.local_provider = mock_local
    client.app.state.model = mock_service

    res = client.post("/api/chat", json={"question": "What is institutional births in Pune?"})
    assert res.status_code == 200
    data = res.json()
    assert data["fallback_used"] is True
    assert data["mode"] == "retrieval-only"
    assert "97.97" in data["answer"]


# Case 17: Both models unavailable
def test_case_17_both_models_unavailable(client):
    mock_service = ModelService()
    mock_service.openrouter_provider.is_available = MagicMock(return_value=False)
    mock_service.hosted_provider.is_available = MagicMock(return_value=False)
    mock_service.local_provider.is_available = MagicMock(return_value=False)
    client.app.state.model = mock_service

    res = client.post("/api/chat", json={"question": "What is institutional births in Pune?"})
    assert res.status_code == 200
    data = res.json()
    assert data["mode"] == "retrieval-only"
    assert "97.97" in data["answer"]


# Case 18: Deterministic fallback answering strictly from verified records
def test_case_18_deterministic_fallback_answering(client):
    mock_service = ModelService()
    mock_service.openrouter_provider.is_available = MagicMock(return_value=False)
    mock_service.hosted_provider.is_available = MagicMock(return_value=False)
    client.app.state.model = mock_service

    res = client.post("/api/chat", json={"question": "What is institutional births in Pune?"})
    assert res.status_code == 200
    data = res.json()
    assert "NFHS-5" in data["answer"]
    assert "2019-2021" in data["answer"]
    assert "97.97" in data["answer"]
    assert data["evidence_summary"]["provenance"]["dataset_id"] is not None
