import pytest
import os
import json
from pathlib import Path
import tempfile
from ml.knowledge_tracing.trainer import train_all_models

def test_untrained_deep_models_not_reported_trained():
    """Verify that deep KT models do not report TRAINED if not actually trained with artifacts."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)
        
        # Test with insufficient data
        sequences_small = [{"sequence": []} for _ in range(10)]
        results_small = train_all_models(sequences_small, tmp_path)
        
        for model in ["akt", "dkt_plus", "sakt"]:
            assert results_small[model]["status"] in ["BLOCKED_BY_DATA", "NOT_TRAINED"]
            assert results_small[model]["status"] != "TRAINED"
            
        # Test with "sufficient" data but no real training logic
        sequences_large = [{"sequence": []} for _ in range(1500)]
        results_large = train_all_models(sequences_large, tmp_path)
        
        for model in ["akt", "dkt_plus", "sakt"]:
            # Even if data is >1000, if it doesn't actually produce artifacts/train, it cannot be TRAINED
            assert results_large[model]["status"] in ["BLOCKED_BY_DATA", "NOT_TRAINED"]
            assert results_large[model]["status"] != "TRAINED"
            assert "missing" in results_large[model]["reason"].lower() or "blocked" in results_large[model]["reason"].lower()

def test_bkt_reports_not_trained_when_using_defaults():
    """Verify that BKT reports NOT_TRAINED when it is just falling back to defaults."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)
        sequences = [{"sequence": []}]
        results = train_all_models(sequences, tmp_path)
        
        assert results["bkt"]["status"] == "NOT_TRAINED"
        assert results["bkt"]["data_source"] == "SPARSE_DEFAULTS"
        assert "default" in results["bkt"]["reason"].lower()

def test_kt_status_file_reflects_reality():
    """Verify that the JSON status output accurately reflects the non-fabricated states."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)
        sequences = [{"sequence": []}]
        train_all_models(sequences, tmp_path)
        
        status_file = tmp_path / "kt_training_status.json"
        assert status_file.exists()
        
        with open(status_file, "r") as f:
            data = json.load(f)
            
        assert data["akt"]["status"] != "TRAINED"
        assert data["dkt_plus"]["status"] != "TRAINED"
        assert data["sakt"]["status"] != "TRAINED"
        assert data["bkt"]["status"] != "TRAINED"
