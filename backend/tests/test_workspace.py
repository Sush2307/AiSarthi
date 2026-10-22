"""Automated test suite for AI Sarthi Research Workspace endpoints and logic."""
import pytest

def test_workspace_indicators_metadata(client):
    r = client.get("/api/workspace/indicators")
    assert r.status_code == 200
    indicators = r.json()
    assert isinstance(indicators, list)
    assert len(indicators) >= 2
    top = indicators[0]
    assert "indicator" in top
    assert "label" in top
    assert "indicator_type" in top
    assert "unit" in top
    assert "source" in top
    assert "years" in top

def test_workspace_locations_list(client):
    r = client.get("/api/workspace/locations?scope=district")
    assert r.status_code == 200
    locations = r.json()
    assert isinstance(locations, list)
    assert len(locations) >= 2
    assert "name" in locations[0]
    assert "state" in locations[0]
    assert "label" in locations[0]

def test_workspace_valid_comparison(client):
    r = client.post("/api/workspace/compare", json={
        "indicator": "Institutional births (%)",
        "locations": ["Alpha", "Beta"],
        "year": "2020",
    })
    assert r.status_code == 200
    j = r.json()
    assert j["found"] is True
    assert j["canonical_indicator"] == "Institutional births (%)"
    assert len(j["records"]) == 2
    assert j["statistics"]["count"] == 2
    assert j["statistics"]["min"] == 70.0
    assert j["statistics"]["max"] == 80.0
    assert j["reproducibility_signature"].startswith("SARTHI-QUERY-")

def test_workspace_nonexistent_indicator(client):
    r = client.post("/api/workspace/compare", json={
        "indicator": "SuperFictionalNonExistentMetricXYZ",
        "locations": ["Alpha"],
    })
    assert r.status_code == 200
    j = r.json()
    assert j["found"] is False
    assert len(j["records"]) == 0
    assert j["statistics"] is None
    assert "could not be matched" in j["methodology"]

def test_workspace_partial_location_match(client):
    r = client.post("/api/workspace/compare", json={
        "indicator": "Institutional births (%)",
        "locations": ["Alpha", "AtlantisCity"],
        "year": "2020",
    })
    assert r.status_code == 200
    j = r.json()
    assert j["found"] is True
    assert "Alpha" in j["matched_locations"]
    assert "AtlantisCity" in j["missing_locations"]
    assert len(j["records"]) == 1
    assert j["statistics"]["count"] == 1

def test_workspace_missing_value_handled_as_none_not_zero(client):
    # Anaemia in pregnancy has None value in test fixture
    r = client.post("/api/workspace/compare", json={
        "indicator": "Anaemia in pregnancy",
        "locations": ["Other State"],
    })
    assert r.status_code == 200
    j = r.json()
    assert j["found"] is True
    assert len(j["records"]) == 1
    rec = j["records"][0]
    assert rec["value"] is None  # Never converted to 0.0!
    assert j["statistics"] is None or j["statistics"]["count"] == 0

def test_workspace_year_mismatch_fallback_disclosure(client):
    # Anaemia in pregnancy only exists in 2021 in test fixture; request 2020
    r = client.post("/api/workspace/compare", json={
        "indicator": "Anaemia in pregnancy",
        "locations": ["Other State"],
        "year": "2020",
    })
    assert r.status_code == 200
    j = r.json()
    assert j["found"] is True
    assert j["year"] == "2021"  # Automatically resolved to available year
    assert "indexed under reporting cycle '2021'" in j["methodology"]
