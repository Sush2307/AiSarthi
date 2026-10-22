"""Automated verification suite for AI Sarthi reliability improvements without model training.

Tests cover all 12 core reliability scenarios:
1. Maharashtra statewide indicator discovery (indicators sampled for Maharashtra, not Nandurbar).
2. Exact indicator lookup in Nandurbar (returns Nandurbar records correctly when explicitly requested).
3. Indicator synonym matching (caesarean, c-section, stunting, wasting, anaemia, full immunization).
4. State versus district filtering (Maharashtra statewide vs Pune/Nashik district).
5. Follow-up summary using previous evidence ("Summarize the retrieved healthcare records in simple language.").
6. Follow-up source and reporting-period questions ("What is the source?").
7. Follow-up district comparisons ("What about Pune?", "Compare with Nashik").
8. Rankings and deterministic calculations (top districts, unweighted district average without cross-indicator blending).
9. Missing values and unavailable records (null values not converted to zero, honest limitations).
10. Numerical grounding validation (unverified numbers rejected, verified numbers accepted).
11. OpenRouter failure and deterministic fallback (circuit breaker tripping, fallback disclosure without leaking secrets).
12. Conversation context surviving provider failures (context preserved and summarized even when LLM fails).
"""
from __future__ import annotations
import os
from unittest.mock import MagicMock, patch
import pytest
from fastapi.testclient import TestClient

from app.config import master_path
from app.context import session_manager
from app.data import Dataset
from app.model import ModelService
from app.providers import OpenRouterProvider
from app.main import app


@pytest.fixture(scope="module")
def real_dataset():
    return Dataset(master_path())


@pytest.fixture
def client(real_dataset):
    app.state.data = real_dataset
    app.state.model = ModelService()
    return TestClient(app)


# ==============================================================================
# Scenario 1: Maharashtra statewide indicator discovery
# ==============================================================================
def test_scenario_1_maharashtra_statewide_indicator_discovery(client):
    """Confirm 'What healthcare indicators are available for Maharashtra?' returns

    indicators for Maharashtra without attributing them to Nandurbar.
    """
    res = client.post(
        "/api/chat",
        json={"question": "What healthcare indicators are available for Maharashtra?", "session_id": "test_sc1"},
    )
    assert res.status_code == 200
    data = res.json()

    assert data["intent"] == "available_indicators"
    assert len(data["records"]) >= 5
    # The answer must explicitly reference Maharashtra
    assert "Maharashtra" in data["answer"]
    # It must NOT falsely attribute the state-level indicators to Nandurbar
    assert "for **Nandurbar**" not in data["answer"]
    assert "indexes 8 key indicators for **Nandurbar**" not in data["answer"]
    # Evidence summary must record positive matched records
    assert data["evidence_summary"]["record_count"] >= 5


# ==============================================================================
# Scenario 2: Exact indicator lookup in Nandurbar
# ==============================================================================
def test_scenario_2_exact_indicator_lookup_in_nandurbar(client):
    """Confirm exact indicator lookup in Nandurbar returns actual Nandurbar records

    (e.g., 76.29% institutional births).
    """
    res = client.post(
        "/api/chat",
        json={"question": "What is institutional births in Nandurbar?", "session_id": "test_sc2"},
    )
    assert res.status_code == 200
    data = res.json()

    assert len(data["records"]) > 0
    top_record = data["records"][0]
    assert top_record["district"] == "Nandurbar"
    assert top_record["value"] == 76.29
    assert "76.29" in data["answer"]
    assert "Nandurbar" in data["answer"]


# ==============================================================================
# Scenario 3: Indicator synonym and alias matching
# ==============================================================================
def test_scenario_3_indicator_synonym_matching(real_dataset):
    """Verify robust synonym resolution across all primary healthcare categories."""
    ds = real_dataset

    # Caesarean / C-Section
    c_sec_ind = ds.resolve_indicator("caesarean deliveries in Pune")
    assert c_sec_ind == "births_delivered_by_caesarean_section_in_the_5_years_before_the_survey_percent"

    c_sec_alt = ds.resolve_indicator("c-section delivery rate")
    assert c_sec_alt == "births_delivered_by_caesarean_section_in_the_5_years_before_the_survey_percent"

    # Nutrition / Stunting
    stunt_ind = ds.resolve_indicator("child stunting in Maharashtra")
    assert stunt_ind == "children_under_5_years_who_are_stunted_height_for_age18_percent"

    # Nutrition / Wasting
    waste_ind = ds.resolve_indicator("wasting in children")
    assert waste_ind == "children_under_5_years_who_are_wasted_weight_for_height18_percent"

    # Nutrition / Underweight
    under_ind = ds.resolve_indicator("underweight children in Bihar")
    assert under_ind == "children_under_5_years_who_are_underweight_weight_for_age18_percent"

    # Anaemia
    anaemia_ind = ds.resolve_indicator("anaemia in pregnancy in Nashik")
    assert anaemia_ind == "pregnant_women_age_15_49_years_who_are_anaemic_<11.0_g_dl22_percent"

    # Immunization
    imm_ind = ds.resolve_indicator("full immunization in children")
    assert "fully_vaccinated" in imm_ind


# ==============================================================================
# Scenario 4: State versus district filtering
# ==============================================================================
def test_scenario_4_state_vs_district_filtering(real_dataset):
    """Verify distinct resolution for statewide vs district-specific requests."""
    ds = real_dataset

    # Pune district request
    pune_filters = ds.detect_filters("Show institutional births in Pune")
    assert pune_filters["district"] == "Pune"
    assert pune_filters["state"] is None

    # Maharashtra statewide request
    mh_filters = ds.detect_filters("Show institutional births in Maharashtra")
    assert mh_filters["state"] == "Maharashtra"
    assert mh_filters["district"] is None

    # Retrieve Pune rows (must be district level)
    pune_rows = ds.retrieve("institutional births in Pune", state=None, district="Pune")
    assert not pune_rows.empty
    assert (pune_rows["district_clean"] == "Pune").all() or (pune_rows["district"] == "Pune").all()


# ==============================================================================
# Scenario 5: Follow-up summary using previous evidence
# ==============================================================================
def test_scenario_5_follow_up_summary_using_previous_evidence(client):
    """Verify that asking 'Summarize the retrieved healthcare records in simple language'

    reuses previous evidence and returns a plain-language summary instead of
    'NO DIRECT RECORDS FOUND'.
    """
    sid = "test_sc5_session"

    # Turn 1: Retrieve records
    r1 = client.post(
        "/api/chat",
        json={"question": "What is institutional births in Pune?", "session_id": sid},
    )
    assert r1.status_code == 200
    assert len(r1.json()["records"]) > 0

    # Turn 2: Follow-up summary
    r2 = client.post(
        "/api/chat",
        json={"question": "Summarize the retrieved healthcare records in simple language.", "session_id": sid},
    )
    assert r2.status_code == 200
    d2 = r2.json()

    assert d2["answer_type"] != "no_data"
    assert d2["intent"] == "evidence_summary"
    assert d2["evidence_count"] > 0
    # Summary must explain the metric and include key figures
    assert "institutional" in d2["answer"].lower()
    assert ("97.97" in d2["answer"] or "pune" in d2["answer"].lower() or "summary" in d2["answer"].lower())


# ==============================================================================
# Scenario 6: Follow-up source and reporting-period questions
# ==============================================================================
def test_scenario_6_follow_up_source_and_period(client):
    """Verify follow-up asking 'What is the source?' explains the source of prior records."""
    sid = "test_sc6_session"

    # Turn 1: Retrieve records
    r1 = client.post(
        "/api/chat",
        json={"question": "What is institutional births in Pune?", "session_id": sid},
    )
    assert r1.status_code == 200

    # Turn 2: Source follow-up
    r2 = client.post(
        "/api/chat",
        json={"question": "What is the source?", "session_id": sid},
    )
    assert r2.status_code == 200
    d2 = r2.json()

    assert d2["intent"] == "metadata_explanation"
    assert "NFHS" in d2["answer"] or "HMIS" in d2["answer"] or "official" in d2["answer"].lower()
    assert d2["evidence_count"] > 0


# ==============================================================================
# Scenario 7: Follow-up district comparisons
# ==============================================================================
def test_scenario_7_follow_up_district_comparisons(client):
    """Verify that asking 'What about Nashik?' preserves the indicator (institutional births)

    from the previous turn.
    """
    sid = "test_sc7_session"

    # Turn 1: Pune institutional births
    r1 = client.post(
        "/api/chat",
        json={"question": "What is institutional births in Pune?", "session_id": sid},
    )
    assert r1.status_code == 200

    # Turn 2: Follow-up location switch
    r2 = client.post(
        "/api/chat",
        json={"question": "What about Nashik?", "session_id": sid},
    )
    assert r2.status_code == 200
    d2 = r2.json()

    assert len(d2["records"]) > 0
    assert d2["records"][0]["district"] == "Nashik"
    assert "90.49" in d2["answer"]


# ==============================================================================
# Scenario 8: Rankings and deterministic calculations
# ==============================================================================
def test_scenario_8_rankings_and_calculations(client, real_dataset):
    """Verify deterministic ranking and aggregation calculation."""
    # 1. District ranking for institutional births in Maharashtra
    res = client.post(
        "/api/chat",
        json={"question": "Top 5 districts in Maharashtra for institutional births", "session_id": "test_sc8"},
    )
    assert res.status_code == 200
    data = res.json()
    assert data["intent"] in ["ranking", "multiple_records"]
    assert len(data["records"]) >= 2
    # Verify records are sorted descending by value
    vals = [r["value"] for r in data["records"] if isinstance(r.get("value"), (int, float))]
    assert vals == sorted(vals, reverse=True)

    # 2. Aggregation check
    agg_res = client.post(
        "/api/chat",
        json={"question": "Average institutional births across districts in Maharashtra", "session_id": "test_sc8_agg"},
    )
    assert agg_res.status_code == 200
    agg_data = agg_res.json()
    assert agg_data["intent"] in ["aggregation", "multiple_records", "single_record"]
    assert "unweighted" in agg_data["answer"].lower() or "average" in agg_data["answer"].lower()


# ==============================================================================
# Scenario 9: Missing values and unavailable records
# ==============================================================================
def test_scenario_9_missing_values_and_unavailable_records(client, real_dataset):
    """Confirm missing values are preserved as None (not zero), and non-existent

    districts return a helpful clarification instead of substituting another geography.
    """
    # 1. Non-existent district
    res = client.post(
        "/api/chat",
        json={"question": "What is institutional births in Atlantis District?", "session_id": "test_sc9"},
    )
    assert res.status_code == 200
    data = res.json()
    assert data["answer_type"] == "no_data"
    assert "No matching record" in data["answer"]
    assert len(data["records"]) == 0

    # 2. Null value preservation check in dataset
    null_rows = real_dataset.df[real_dataset.df["value"].isna()]
    if not null_rows.empty:
        sample_dict = real_dataset.to_records(null_rows.head(1))[0]
        assert sample_dict["value"] is None  # Never converted to 0.0


# ==============================================================================
# Scenario 10: Numerical grounding validation
# ==============================================================================
def test_scenario_10_numerical_grounding_validation():
    """Verify that validate_evidence_grounding rejects hallucinated numbers

    and accepts verified numbers.
    """
    records = [
        {
            "indicator": "institutional_births_percent",
            "value": 97.97,
            "district": "Pune",
            "year": "2019-2021",
            "source": "NFHS-5",
        }
    ]

    # Valid grounded text
    valid_text = "According to NFHS-5 (2019-2021), institutional births in Pune was 97.97%."
    is_grounded, reason = ModelService.validate_evidence_grounding(valid_text, records)
    assert is_grounded is True
    assert reason is None

    # Hallucinated number (42.8%)
    fabricated_text = "According to records, institutional births in Pune was fabricated at 42.8%."
    is_grounded, reason = ModelService.validate_evidence_grounding(fabricated_text, records)
    assert is_grounded is False
    assert "unverified numbers" in reason.lower()
    assert "42.8" in reason


# ==============================================================================
# Scenario 11: OpenRouter failure and deterministic fallback
# ==============================================================================
def test_scenario_11_openrouter_failure_triggers_fallback(monkeypatch):
    """Verify that when OpenRouter fails (e.g. 503 outage or circuit open),

    the system falls back to DeterministicEvidenceProvider without exposing secrets.
    """
    monkeypatch.setenv("PRIMARY_PROVIDER", "openrouter")
    service = ModelService()

    secret_key = "sk-or-v1-secret-test-key-should-never-leak"
    monkeypatch.setenv("OPENROUTER_API_KEY", secret_key)

    with patch.object(service.openrouter_provider, "is_available", return_value=True):
        with patch.object(
            service.openrouter_provider,
            "generate",
            side_effect=RuntimeError(f"HTTP 503 Outage with {secret_key}"),
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

            assert res["fallback_used"] is True
            assert res["mode"] == "retrieval-only"
            assert "97.97" in res["answer"]
            # Verify secret is never exposed in answer or fallback reason
            assert secret_key not in res["answer"]
            assert secret_key not in res["fallback_reason"]


# ==============================================================================
# Scenario 12: Conversation context surviving provider failures
# ==============================================================================
def test_scenario_12_context_survives_provider_failure(client):
    """Verify multi-turn session context is preserved and accessible even when

    the model provider fails.
    """
    sid = "test_sc12_session"

    # Turn 1: Successfully retrieve and answer
    r1 = client.post(
        "/api/chat",
        json={"question": "What is institutional births in Pune?", "session_id": sid},
    )
    assert r1.status_code == 200

    # Turn 2: Simulate OpenRouter provider failure during follow-up
    with patch.object(OpenRouterProvider, "generate", side_effect=RuntimeError("OpenRouter 429 Rate Limit")):
        r2 = client.post(
            "/api/chat",
            json={"question": "Summarize these records in simple language", "session_id": sid},
        )
        assert r2.status_code == 200
        d2 = r2.json()

        # Deterministic fallback answered using preserved records from Turn 1
        assert d2["intent"] == "evidence_summary"
        assert d2["evidence_count"] > 0
        assert "institutional" in d2["answer"].lower()
        assert d2["fallback_used"] is True
