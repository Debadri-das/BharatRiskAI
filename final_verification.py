
import sys
import os
from pathlib import Path
import json
import numpy as np
import torch

# Ensure the root directory is in sys.path
ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from ml.nowcasting.inference import NowcastingInferenceEngine

def run_verification():
    print("Starting final verification...")
    
    # 1. Initialize engine
    engine = NowcastingInferenceEngine(device="cpu")
    print("Engine initialized.")

    # 2. Setup normalization (create dummy scaler if not exists)
    scaler_path = ROOT / "models" / "preprocessing" / "scaler.json"
    if not scaler_path.exists():
        print("Creating mock scaler.json...")
        scaler_path.parent.mkdir(parents=True, exist_ok=True)
        stats = {
            "method": "training-only per-channel standardization",
            "channels": [{"mean": 0.0, "std": 1.0} for _ in range(19)]
        }
        scaler_path.write_text(json.dumps(stats, indent=2))
    
    engine.load_normalization(str(scaler_path))
    print("Normalization loaded.")

    # 3. Test Determinism
    engine.set_determinism(seed=42)
    observation = {
        "iwv": 45.0, "ctt": -50.0, "cape": 1500.0, "cin": -50.0, 
        "ctt_drop_rate": 5.0, "low_level_convergence": 0.15,
        "elevation_m": 100.0, "slope_degrees": 2.0, "drainage_score": 80.0
    }
    
    res1 = engine.predict_nowcast(observation)
    res2 = engine.predict_nowcast(observation)
    
    deterministic = (res1["alert_level"] == res2["alert_level"]) and \
                   (res1["thunderstorm_prob"] == res2["thunderstorm_prob"])
    
    print(f"Determinism Check: {'PASSED' if deterministic else 'FAILED'}")

    # 4. Check Attribution
    attribution = res1["feature_attribution"]
    has_keys = all(k in attribution for k in ["ctt", "cape", "iwv"])
    print(f"Attribution Keys Check: {'PASSED' if has_keys else 'FAILED'}")
    
    # 5. Check Output structure
    required_keys = ["alert_level", "primary_hazard", "timeline", "hazard_probability_maps", "xai_triggers"]
    structure_ok = all(k in res1 for k in required_keys)
    print(f"Output Structure Check: {'PASSED' if structure_ok else 'FAILED'}")

    if deterministic and has_keys and structure_ok:
        print("\nOVERALL STATUS: ALL CHECKS PASSED")
    else:
        print("\nOVERALL STATUS: SOME CHECKS FAILED")
        sys.exit(1)

if __name__ == "__main__":
    run_verification()
