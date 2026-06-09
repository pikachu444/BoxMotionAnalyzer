import pytest
import pandas as pd
import numpy as np
from src.analysis.compare.data_model import ComparisonModel

@pytest.fixture
def mock_proc_df():
    # Create a MultiIndex DataFrame similar to what DataLoader.load_result_csv returns
    columns = pd.MultiIndex.from_tuples([
        ("Analysis", "DropPostureSummary", "DeltaH_mm"),
        ("Analysis", "DropPostureSummary", "BetaAtT1MinusDeg"),
        ("Analysis", "DropPostureSummary", "ContactState"),
        ("Analysis", "DropPosture", "ThetaLongDeg"),
    ])
    
    # 5 frames of data
    data = [
        [150.5, 12.3, "ImpactEvent", 1.2],
        [150.5, 12.3, "ImpactEvent", 1.5],
        [150.5, 12.3, "ImpactEvent", 1.8],
        [150.5, 12.3, "ImpactEvent", 2.1],
        [150.5, 12.3, "ImpactEvent", 2.4],
    ]
    df = pd.DataFrame(data, columns=columns)
    df.index = [0.0, 0.01, 0.02, 0.03, 0.04]
    df.index.name = "Time"
    return df

def test_same_file_zero_difference(monkeypatch, mock_proc_df):
    model = ComparisonModel()
    
    # Mock load_result_csv to return our fixture
    def mock_load(filepath):
        return mock_proc_df.copy()
        
    monkeypatch.setattr(model.data_loader, "load_result_csv", mock_load)
    
    # Load same logical data twice
    name1 = model.load_file("test_data1.proc.csv")
    name2 = model.load_file("test_data2.proc.csv")
    
    # Should automatically set baseline to the first file
    assert model.baseline_name == name1
    
    diffs = model.get_summary_differences()
    
    # Check baseline diffs
    b_diffs = diffs[name1]["diffs"]
    assert b_diffs["DeltaH_mm"] == 0.0
    assert b_diffs["BetaAtT1MinusDeg"] == 0.0
    assert b_diffs["ContactState"] == "Match"
    
    # Check target diffs
    t_diffs = diffs[name2]["diffs"]
    assert t_diffs["DeltaH_mm"] == 0.0
    assert t_diffs["BetaAtT1MinusDeg"] == 0.0
    assert t_diffs["ContactState"] == "Match"

def test_different_files_compute_difference(monkeypatch, mock_proc_df):
    model = ComparisonModel()
    
    # Second dataset has +10mm height, +5 deg beta, and different contact state
    df2 = mock_proc_df.copy()
    df2.loc[:, ("Analysis", "DropPostureSummary", "DeltaH_mm")] = 160.5
    df2.loc[:, ("Analysis", "DropPostureSummary", "BetaAtT1MinusDeg")] = 17.3
    df2.loc[:, ("Analysis", "DropPostureSummary", "ContactState")] = "NoContact"
    
    def mock_load(filepath):
        if "baseline" in filepath:
            return mock_proc_df.copy()
        return df2.copy()
        
    monkeypatch.setattr(model.data_loader, "load_result_csv", mock_load)
    
    name1 = model.load_file("baseline.proc.csv")
    name2 = model.load_file("compare.proc.csv")
    
    diffs = model.get_summary_differences()
    
    t_diffs = diffs[name2]["diffs"]
    assert np.isclose(t_diffs["DeltaH_mm"], 10.0)
    assert np.isclose(t_diffs["BetaAtT1MinusDeg"], 5.0)
    assert t_diffs["ContactState"] == "NoContact"

def test_get_timeseries_data(monkeypatch, mock_proc_df):
    model = ComparisonModel()
    monkeypatch.setattr(model.data_loader, "load_result_csv", lambda x: mock_proc_df.copy())
    
    model.load_file("f1.proc.csv")
    model.load_file("f2.proc.csv")
    
    series_dict = model.get_timeseries_data("Analysis", "DropPosture", "ThetaLongDeg")
    assert "f1.proc.csv" in series_dict
    assert "f2.proc.csv" in series_dict
    assert len(series_dict["f1.proc.csv"]) == 5
