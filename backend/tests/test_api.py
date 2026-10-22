def test_health(client):
    j = client.get("/api/health").json()
    assert j["status"] == "ok" and j["records"] == 4 and j["model_loaded"] is False

def test_stats_computed_from_data(client):
    j = client.get("/api/stats").json()
    assert j["total_records"] == 4 and j["indicators"] == 2 and j["districts"] == 2
    assert (j["year_min"], j["year_max"]) == ("2020", "2021")

def test_filters_and_indicators(client):
    f = client.get("/api/filters").json()
    assert "Test State" in f["states"] and "2020" in f["years"]
    assert len(client.get("/api/indicators", params={"q": "anaemia"}).json()["indicators"]) == 1

def test_health_data_filter(client):
    j = client.get("/api/health-data", params={"state": "Test State", "year": "2021"}).json()
    assert j["count"] == 1 and j["records"][0]["district"] == "Alpha"

def test_chat_retrieval_only(client):
    j = client.post("/api/chat", json={"question": "institutional births in Alpha"}).json()
    assert j["mode"] in ["retrieval-only", "live"] and j["answer_type"] in ["dataset_only", "ai_generated"]
    assert all(r["district"] == "Alpha" for r in j["records"])

def test_chat_no_data_not_fabricated(client):
    j = client.post("/api/chat", json={"question": "zzzz unknownindicator"}).json()
    assert j["records"] == [] and j["answer_type"] == "no_data"

def test_chat_validation(client):
    assert client.post("/api/chat", json={"question": "a"}).status_code == 422
    assert client.post("/api/chat", json={"question": "x" * 501}).status_code == 422

def test_schemes(client):
    assert client.get("/api/schemes").json()["schemes"][0]["official_url"].startswith("https://")

def test_explorer_pagination(client):
    j = client.get("/api/explorer", params={"page": 1, "page_size": 2}).json()
    assert j["total_records"] == 4
    assert j["total_pages"] == 2
    assert j["page"] == 1
    assert len(j["records"]) == 2

def test_export_csv(client):
    r = client.get("/api/export/csv", params={"state": "Test State"})
    assert r.status_code == 200
    assert "text/csv" in r.headers["content-type"]
    lines = r.text.strip().split("\n")
    assert len(lines) >= 3  # header + at least 2 rows

def test_workspace_compare(client):
    r = client.post("/api/workspace/compare", json={
        "indicator": "Institutional births (%)",
        "locations": ["Alpha", "Beta"]
    })
    assert r.status_code == 200
    j = r.json()
    assert j["found"] is True
    assert len(j["records"]) == 2
    assert j["statistics"]["count"] == 2
    assert j["statistics"]["min"] <= j["statistics"]["max"]

def test_analytics_modules(client):
    r = client.get("/api/analytics/modules")
    assert r.status_code == 200
    j = r.json()
    assert j["total_records"] == 4
    assert "missing_summary" in j
    assert "geographic_breakdown" in j
    assert "report_type_breakdown" in j

def test_chat_structured_evidence(client):
    r = client.post("/api/chat", json={"question": "institutional births in Alpha"})
    assert r.status_code == 200
    j = r.json()
    assert "evidence_summary" in j
    assert j["evidence_summary"]["record_count"] >= 1
    assert "follow_ups" in j
    assert len(j["follow_ups"]) >= 1
