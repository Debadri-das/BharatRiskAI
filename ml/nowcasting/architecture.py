"""Spatiotemporal multi-task network for severe-weather nowcasting."""

from typing import Dict

import torch
from torch import nn


class SpatiotemporalMTLNet(nn.Module):
    """Shared 3D backbone with hazard-specific spatial probability heads."""

    def __init__(self, input_channels: int = 13, baseline_channels: int = 6, hidden_channels: int = 32) -> None:
        super().__init__()
        self.backbone = nn.Sequential(
            nn.Conv3d(input_channels, hidden_channels, kernel_size=3, padding=1),
            nn.BatchNorm3d(hidden_channels),
            nn.GELU(),
            nn.Conv3d(hidden_channels, hidden_channels, kernel_size=3, padding=1),
            nn.GELU(),
        )
        self.baseline_projection = nn.Conv2d(baseline_channels, hidden_channels, kernel_size=1)
        self.cross_attention = nn.MultiheadAttention(hidden_channels, num_heads=4, batch_first=True)
        self.heads = nn.ModuleDict({
            "thunderstorms": self._head(hidden_channels),
            "cloudbursts": self._head(hidden_channels),
            "flash_floods": self._head(hidden_channels),
        })

    @staticmethod
    def _head(channels: int) -> nn.Sequential:
        return nn.Sequential(nn.Conv2d(channels, channels // 2, 3, padding=1), nn.GELU(), nn.Conv2d(channels // 2, 5, 1))

    def forward(self, sequence: torch.Tensor, baseline: torch.Tensor) -> Dict[str, torch.Tensor]:
        if sequence.ndim != 5:
            raise ValueError("sequence must have shape [batch, time, channels, height, width]")
        if baseline.ndim != 4 or baseline.shape[1] != 6:
            raise ValueError("baseline must have shape [batch, 6, height, width]")
        features = self.backbone(sequence.permute(0, 2, 1, 3, 4)).mean(dim=2)
        baseline_context = self.baseline_projection(baseline)
        batch, channels, height, width = features.shape
        query = features.flatten(2).transpose(1, 2)
        context = baseline_context.flatten(2).transpose(1, 2)
        attended, _ = self.cross_attention(query, context, context, need_weights=False)
        fused = (query + attended).transpose(1, 2).reshape(batch, channels, height, width)
        return {name: torch.sigmoid(head(fused)) for name, head in self.heads.items()}