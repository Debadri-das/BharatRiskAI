import numpy as np
import torch

from ml.nowcasting.architecture import SpatiotemporalMTLNet
from ml.nowcasting.features import build_spatiotemporal_features


def test_mtl_probability_maps_have_expected_shapes():
    sequence, baseline = build_spatiotemporal_features({"iwv": 55.0, "cape_j_kg": 2200.0})
    outputs = SpatiotemporalMTLNet()(
        torch.from_numpy(sequence).unsqueeze(0),
        torch.from_numpy(baseline).unsqueeze(0),
    )

    assert sequence.shape == (4, 13, 16, 16)
    assert baseline.shape == (6, 16, 16)
    assert set(outputs) == {"thunderstorms", "cloudbursts", "flash_floods"}
    assert all(value.shape == (1, 5, 16, 16) for value in outputs.values())
    assert all(np.logical_and(value.detach().numpy() >= 0, value.detach().numpy() <= 1).all() for value in outputs.values())