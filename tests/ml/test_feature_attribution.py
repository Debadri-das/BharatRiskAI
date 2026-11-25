import numpy as np
import torch

from ml.nowcasting.inference import NowcastingInferenceEngine
from reports.unified_feature_schema import CHANNEL_ORDER


def test_reduce_channel_attributions_leaves_canonical_channel_axis():
    gradients = torch.zeros((2, 3, 13, 2, 2), dtype=torch.float32)
    for channel in range(13):
        gradients[:, :, channel, :, :] = channel + 1

    scores = NowcastingInferenceEngine._reduce_channel_attributions(gradients, 13)
    expected = np.arange(1, 14, dtype=np.float32)
    expected /= expected.sum()

    np.testing.assert_allclose(scores, expected)


def test_compute_feature_attribution_preserves_order_and_cpu_gradient(monkeypatch):
    class WeightedModel(torch.nn.Module):
        def forward(self, sequence, baseline):
            weights = torch.arange(1, 14, device=sequence.device, dtype=sequence.dtype)
            weighted = sequence * weights.view(1, 1, 13, 1, 1)
            return {"thunderstorms": weighted.sum(dim=2)}

    sequence = np.ones((7, 13, 2, 2), dtype=np.float32)
    baseline = np.zeros((6, 2, 2), dtype=np.float32)
    monkeypatch.setattr(
        "ml.nowcasting.inference.build_spatiotemporal_features",
        lambda observation: (sequence, baseline),
    )

    engine = NowcastingInferenceEngine(device="cpu")
    engine.model = WeightedModel()
    engine._loaded_checkpoint_path = "synthetic-test-checkpoint"
    engine._normalization_stats = {}

    attribution = engine.compute_feature_attribution({})
    expected = np.arange(1, 14, dtype=np.float32)
    expected /= expected.sum()

    assert list(attribution) == CHANNEL_ORDER
    np.testing.assert_allclose(list(attribution.values()), expected, rtol=1e-6, atol=1e-7)
