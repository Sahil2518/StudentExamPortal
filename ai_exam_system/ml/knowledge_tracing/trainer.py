"""
Knowledge tracing model training coordinator.
"""
from typing import List, Dict, Any
from pathlib import Path
import json

from ml.knowledge_tracing.bkt_model import BKTModel

def train_all_models(sequences: List[Dict[str, Any]], artifacts_dir: Path) -> dict:
    """
    Train all feasible knowledge tracing models given available data.
    Returns a dict of model name -> training result.
    """
    results = {}
    n = len(sequences)
    
    # BKT uses defaults as there is no EM fitting implemented yet.
    bkt = BKTModel()
    bkt.fit(sequences) # just assigns defaults internally
    results["bkt"] = {
        "status": "NOT_TRAINED",
        "data_source": "SPARSE_DEFAULTS",
        "reason": "BKT EM fitting not implemented, using default heuristics."
    }
    
    # Deep models require PyTorch and actual training loop implementation
    for model_name, min_required in [("akt", 1000), ("dkt_plus", 1000), ("sakt", 500)]:
        if n < min_required:
            results[model_name] = {
                "status": "BLOCKED_BY_DATA",
                "reason": f"Need {min_required} sequences, have {n}",
                "data_source": "INSUFFICIENT"
            }
        else:
            # We don't have the training loops for these implemented, nor artifact saving
            results[model_name] = {
                "status": "NOT_TRAINED",
                "reason": f"Training implementation missing for {model_name}. Artifact cannot be saved.",
                "data_source": "REAL"
            }
            
    # Save training status
    status_path = artifacts_dir / "kt_training_status.json"
    with open(status_path, "w") as f:
        json.dump(results, f, indent=2)
        
    return results
