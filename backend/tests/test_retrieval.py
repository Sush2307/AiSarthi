from app.data import Dataset

def test_retrieve_limits(csv_path):
    assert len(Dataset(csv_path).retrieve("institutional births", limit=2)) == 2

def test_missing_value_is_none_not_zero(csv_path):
    ds = Dataset(csv_path)
    assert ds.to_records(ds.filter(source="HMIS"))[0]["value"] is None

def test_detect_locations(csv_path):
    assert Dataset(csv_path).detect_locations("births in alpha, test state")["district"] == "Alpha"
