import sys
from pathlib import Path
import pandas as pd, pytest
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

# TEST FIXTURE ONLY: invented rows used to test code, not real statistics.
ROWS = [
 ("Test State", "Test State", "Alpha", "Alpha", "2020", "NFHS-5", "Institutional births (%)", 80.0, "district"),
 ("Test State", "Test State", "Beta", "Beta", "2020", "NFHS-5", "Institutional births (%)", 70.0, "district"),
 ("Test State", "Test State", "Alpha", "Alpha", "2021", "NFHS-5", "Institutional births (%)", 85.0, "district"),
 ("Other State", "Other State", "", "", "2021", "HMIS", "Anaemia in pregnancy", None, "state"),
]

@pytest.fixture(scope="session")
def csv_path(tmp_path_factory):
    p = tmp_path_factory.mktemp("d") / "master.csv"
    cols = ["state", "state_standard", "district", "district_clean", "year", "source", "indicator", "value", "geographic_level"]
    pd.DataFrame(ROWS, columns=cols).to_csv(p, index=False)
    return p

@pytest.fixture()
def client(csv_path, monkeypatch):
    monkeypatch.setenv("MASTER_PATH", str(csv_path))
    monkeypatch.setenv("LOAD_MODEL", "0")
    monkeypatch.setenv("MODEL_ENABLED", "0")
    from fastapi.testclient import TestClient
    from app.main import app
    with TestClient(app) as c:
        yield c
