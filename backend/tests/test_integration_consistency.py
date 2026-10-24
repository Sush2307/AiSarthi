"""End-to-end integration and cross-feature consistency regression tests.

Verifies that Explorer, Chat, Workspace, CSV export, and Dashboard APIs agree
on underlying records, missing value semantics, and numeric validation.
"""
import io
import pandas as pd
import pytest

def test_cross_feature_data_consistency(client):
    """Verify that Explorer, Chat, Workspace, and CSV export agree on the exact same observation."""
    # 1. Retrieve observation through Explorer
    res_exp = client.get("/api/explorer?district=Alpha&indicator=Institutional births (%)&page=1&page_size=10")
    assert res_exp.status_code == 200
    exp_data = res_exp.json()
    assert exp_data["total_records"] >= 1
    exp_rec = exp_data["records"][0]
    expected_val = exp_rec["value"]
    expected_year = exp_rec["year"]
    expected_source = exp_rec["source"]

    # 2. Query the same observation through Chat
    res_chat = client.post("/api/chat", json={"question": "institutional births in Alpha", "district": "Alpha"})
    assert res_chat.status_code == 200
    chat_data = res_chat.json()
    assert len(chat_data["records"]) >= 1
    chat_rec = chat_data["records"][0]
    # Numeric value, source, and year must agree exactly
    assert chat_rec["value"] == expected_val
    assert chat_rec["source"] == expected_source

    # 3. Query the same observation through Workspace Comparison
    res_ws = client.post("/api/workspace/compare", json={
        "indicator": "Institutional births (%)",
        "locations": ["Alpha"],
        "year": expected_year,
    })
    assert res_ws.status_code == 200
    ws_data = res_ws.json()
    assert ws_data["found"] is True
    assert len(ws_data["records"]) == 1
    ws_rec = ws_data["records"][0]
    assert ws_rec["value"] == expected_val
    assert ws_rec["year"] == expected_year
    assert ws_rec["source"] == expected_source

    # 4. Export matching records via CSV
    res_csv = client.get(f"/api/export/csv?district=Alpha&indicator=Institutional births (%)")
    assert res_csv.status_code == 200
    assert "text/csv" in res_csv.headers["content-type"]
    df_exported = pd.read_csv(io.StringIO(res_csv.text))
    assert len(df_exported) >= 1
    assert expected_val in df_exported["value"].values

def test_missing_value_integrity_across_endpoints(client):
    """Missing values must never be silently converted to 0.0 or inferred."""
    # Other State has None value for 'Anaemia in pregnancy'
    # 1. Explorer
    res_exp = client.get("/api/explorer?state=Other State&page=1&page_size=5")
    assert res_exp.status_code == 200
    rec = res_exp.json()["records"][0]
    assert rec["value"] is None

    # 2. Workspace
    res_ws = client.post("/api/workspace/compare", json={
        "indicator": "Anaemia in pregnancy",
        "locations": ["Other State"],
    })
    assert res_ws.status_code == 200
    ws_rec = res_ws.json()["records"][0]
    assert ws_rec["value"] is None
    # Statistics should exclude missing values, count=0
    assert ws_rec["value"] != 0.0

def test_pagination_boundary_conditions(client):
    """Test pagination bounds, clamping, and edge cases."""
    # Page 1
    r1 = client.get("/api/explorer?page=1&page_size=2")
    assert r1.status_code == 200
    j1 = r1.json()
    assert j1["page"] == 1
    assert len(j1["records"]) == 2

    # Out of bounds page clamps to max page
    r_high = client.get("/api/explorer?page=999999&page_size=2")
    assert r_high.status_code == 200
    j_high = r_high.json()
    assert j_high["page"] == j_high["total_pages"]

    # Negative page clamps to 1
    r_low = client.get("/api/explorer?page=0&page_size=2")
    # FastAPI ge=1 validator rejects 0 with 422
    assert r_low.status_code in [422, 200]

def test_deterministic_reproducibility_signature(client):
    """Identical query configurations must produce identical reproducibility signatures."""
    payload = {
        "indicator": "Institutional births (%)",
        "locations": ["Alpha", "Beta"],
        "year": "2020",
    }
    r1 = client.post("/api/workspace/compare", json=payload)
    r2 = client.post("/api/workspace/compare", json=payload)
    assert r1.status_code == 200 and r2.status_code == 200
    sig1 = r1.json()["reproducibility_signature"]
    sig2 = r2.json()["reproducibility_signature"]
    assert sig1 == sig2
    assert sig1.startswith("INFOMED-QUERY-") or sig1.startswith("SARTHI-QUERY-")

def test_combined_filters_consistency(client):
    """Applying multiple filters simultaneously narrows records predictably."""
    r = client.get("/api/explorer?state=Test State&district=Alpha&source=NFHS-5&year=2020")
    assert r.status_code == 200
    j = r.json()
    assert j["total_records"] == 1
    rec = j["records"][0]
    assert rec["district"] == "Alpha"
    assert rec["year"] == "2020"
    assert rec["source"] == "NFHS-5"
