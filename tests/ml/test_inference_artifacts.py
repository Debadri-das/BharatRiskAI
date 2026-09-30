import json

import pytest
import torch

from ml.nowcasting.architecture import SpatiotemporalMTLNet
from ml.nowcasting.inference import NowcastingInferenceEngine


def _normalization():
    return {
        "method": "training-only per-channel standardization",
        "channels": [{"mean": 0.0, "std": 1.0} for _ in range(19)],
    }


def _checkpoint(model, normalization=None):
    artifact = {
        "model": model.state_dict(),
        "input_channels": 13,
        "baseline_channels": 6,
        "sequence_length": 7,
        "hidden_channels": 32,
        "num_heads": 4,
        "num_layers": 2,
        "horizons": 5,
        "model_class": "SpatiotemporalMTLNet",
    }
    if normalization is not None:
        artifact["normalization"] = normalization
    return artifact


def test_invalid_checkpoint_is_not_marked_loaded(tmp_path):
    path = tmp_path / "invalid.pt"
    torch.save({"model": {}}, path)
    engine = NowcastingInferenceEngine()

    with pytest.raises(ValueError):
        engine.load_artifact(str(path))

    assert not engine.is_loaded
    assert engine.checkpoint_path is None


def test_embedded_normalization_is_used(tmp_path):
    model = SpatiotemporalMTLNet()
    path = tmp_path / "embedded.pt"
    torch.save(_checkpoint(model, _normalization()), path)
    engine = NowcastingInferenceEngine()

    engine.load_artifact(str(path))

    assert engine.is_loaded
    assert engine.normalization_stats["method"] == "training-only per-channel standardization"


def test_sidecar_normalization_is_supported_and_required_for_prediction(tmp_path):
    model = SpatiotemporalMTLNet()
    path = tmp_path / "weights-only.pt"
    scaler = tmp_path / "scaler.json"
    torch.save(_checkpoint(model), path)
    scaler.write_text(json.dumps(_normalization()), encoding="utf-8")

    engine = NowcastingInferenceEngine()
    engine.load_artifact(str(path))
    assert engine.is_loaded
    with pytest.raises(RuntimeError, match="normalization"):
        engine.predict_grid({})

    engine.load_normalization(str(scaler))
    assert engine.normalization_stats is not None
