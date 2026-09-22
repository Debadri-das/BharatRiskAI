"""Compact multi-task spatiotemporal network for historical nowcasting."""
from __future__ import annotations

import torch
from torch import nn


class HistoricalMultiTaskNet(nn.Module):
    """Shared 3-D feature extractor with one spatial head per hazard."""

    def __init__(self, input_channels: int, horizons: int = 5, hidden_channels: int = 32) -> None:
        super().__init__()
        self.horizons = horizons
        self.backbone = nn.Sequential(nn.Conv3d(input_channels, hidden_channels, 3, padding=1), nn.BatchNorm3d(hidden_channels), nn.GELU(), nn.Conv3d(hidden_channels, hidden_channels, 3, padding=1), nn.GELU())
        self.heads = nn.ModuleDict({name: nn.Conv2d(hidden_channels, horizons, 1) for name in ("thunderstorm", "cloudburst", "flash_flood")})

    def forward(self, inputs: torch.Tensor) -> torch.Tensor:
        if inputs.ndim != 5:
            raise ValueError("inputs must have shape [batch, time, channels, height, width]")
        shared = self.backbone(inputs.permute(0, 2, 1, 3, 4)).mean(dim=2)
        return torch.stack([head(shared) for head in self.heads.values()], dim=2)
