"""Spatiotemporal multi-task network for severe-weather nowcasting."""

from typing import Dict
import torch
from torch import nn


class SpatiotemporalMTLNet(nn.Module):
    """
    Advanced Spatiotemporal Multi-Task Transformer Network.
    
    This architecture integrates:
    1. A 3D CNN spatiotemporal backbone for feature extraction.
    2. Learned 3D spatiotemporal positional embeddings.
    3. A Multi-Head Self-Attention Transformer encoder for storm tracking.
    4. A Spatiotemporal Cross-Attention layer matching real-time satellite
       observation grids to IMDAA thermodynamic baseline grids.
    5. Independent, hazard-specific heads generating probability maps across
       the five forecast horizons (2h, 3h, 4h, 5h, 6h).
    """

    def __init__(self, input_channels: int = 13, baseline_channels: int = 6, hidden_channels: int = 32, num_heads: int = 4, num_layers: int = 2) -> None:
        super().__init__()
        self.input_channels = input_channels
        self.baseline_channels = baseline_channels
        self.hidden_channels = hidden_channels
        self.num_heads = num_heads
        
        self.backbone = nn.Sequential(
            nn.Conv3d(input_channels, hidden_channels, kernel_size=3, padding=1),
            nn.BatchNorm3d(hidden_channels),
            nn.GELU(),
            nn.Conv3d(hidden_channels, hidden_channels, kernel_size=3, padding=1),
            nn.BatchNorm3d(hidden_channels),
            nn.GELU(),
        )
        
        self.baseline_projection = nn.Sequential(
            nn.Conv2d(baseline_channels, hidden_channels, kernel_size=3, padding=1),
            nn.BatchNorm2d(hidden_channels),
            nn.GELU()
        )
        
        encoder_layer = nn.TransformerEncoderLayer(
            d_model=hidden_channels,
            nhead=num_heads,
            dim_feedforward=hidden_channels * 4,
            dropout=0.1,
            activation="gelu",
            batch_first=True
        )
        self.transformer_encoder = nn.TransformerEncoder(encoder_layer, num_layers=num_layers)
        
        self.cross_attention = nn.MultiheadAttention(
            embed_dim=hidden_channels,
            num_heads=num_heads,
            dropout=0.1,
            batch_first=True
        )
        self.cross_norm = nn.LayerNorm(hidden_channels)
        
        self.pos_emb = nn.Parameter(torch.randn(1, 7 * 16 * 16, hidden_channels) * 0.02)
        self.baseline_pos_emb = nn.Parameter(torch.randn(1, 16 * 16, hidden_channels) * 0.02)
        
        self.heads = nn.ModuleDict({
            "thunderstorms": self._head(hidden_channels),
            "cloudbursts": self._head(hidden_channels),
            "flash_floods": self._head(hidden_channels),
        })

    @staticmethod
    def _head(channels: int) -> nn.Sequential:
        return nn.Sequential(
            nn.Conv2d(channels, channels // 2, kernel_size=3, padding=1),
            nn.BatchNorm2d(channels // 2),
            nn.GELU(),
            nn.Conv2d(channels // 2, 5, kernel_size=1)
        )

    def forward(self, sequence: torch.Tensor, baseline: torch.Tensor) -> Dict[str, torch.Tensor]:
        # Validate input shapes
        if sequence.ndim != 5:
            raise ValueError(f"sequence must have shape [batch, time, channels, height, width], got {sequence.shape}")
        if baseline.ndim != 4:
            raise ValueError(f"baseline must have shape [batch, channels, height, width], got {baseline.shape}")
        
        batch, time, channels, height, width = sequence.shape
        
        # Validate channel counts
        if channels != self.input_channels:
            raise ValueError(f"Expected {self.input_channels} input channels, got {channels}")
        if baseline.shape[1] != self.baseline_channels:
            raise ValueError(f"Expected {self.baseline_channels} baseline channels, got {baseline.shape[1]}")
        
        # Validate sequence length (should be 7 for canonical training)
        if time != 7:
            raise ValueError(f"Expected sequence length 7, got {time}. Training and inference must use the same sequence length.")
        
        # Validate spatial dimensions
        if height != 16 or width != 16:
            raise ValueError(f"Expected spatial dimensions 16x16, got {height}x{width}. All features must be on the same grid.")
        
        seq_features = self.backbone(sequence.permute(0, 2, 1, 3, 4))
        seq_flat = seq_features.permute(0, 2, 3, 4, 1).reshape(batch, time * height * width, self.hidden_channels)
        
        if seq_flat.shape[1] != self.pos_emb.shape[1]:
            pos_emb = nn.functional.interpolate(
                self.pos_emb.transpose(1, 2),
                size=seq_flat.shape[1],
                mode="linear",
                align_corners=False
            ).transpose(1, 2)
        else:
            pos_emb = self.pos_emb
            
        seq_flat = seq_flat + pos_emb
        seq_encoded = self.transformer_encoder(seq_flat)
        
        baseline_proj = self.baseline_projection(baseline)
        baseline_flat = baseline_proj.permute(0, 2, 3, 1).reshape(batch, height * width, self.hidden_channels)
        
        if baseline_flat.shape[1] != self.baseline_pos_emb.shape[1]:
            baseline_pos_emb = nn.functional.interpolate(
                self.baseline_pos_emb.transpose(1, 2),
                size=baseline_flat.shape[1],
                mode="linear",
                align_corners=False
            ).transpose(1, 2)
        else:
            baseline_pos_emb = self.baseline_pos_emb
            
        baseline_flat = baseline_flat + baseline_pos_emb
        
        attended, _ = self.cross_attention(
            query=seq_encoded,
            key=baseline_flat,
            value=baseline_flat,
            need_weights=False
        )
        fused = self.cross_norm(seq_encoded + attended)
        
        fused_grid = fused.reshape(batch, time, height, width, self.hidden_channels).permute(0, 4, 1, 2, 3)
        pooled_spatial = fused_grid.mean(dim=2)
        
        return {name: torch.sigmoid(head(pooled_spatial)) for name, head in self.heads.items()}
