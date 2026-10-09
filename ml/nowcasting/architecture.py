"""Spatiotemporal multi-task network for severe-weather nowcasting."""

from typing import Dict, Optional, Union, Tuple, List, Any
import torch
from torch import nn


class PredictionTensor(torch.Tensor):
    """
    Multi-task prediction tensor of shape [batch, horizons, hazards, height, width].
    
    Provides dual-interface compatibility:
    - As a canonical torch.Tensor of shape [B, 5, 3, H, W] for losses and tensor operations.
    - As a dictionary-like container mapping hazard names ("thunderstorms", "cloudbursts", "flash_floods")
      to probability maps [B, 5, H, W] for inference and attribution.
    """
    HAZARDS = ("thunderstorms", "cloudbursts", "flash_floods")

    def __getitem__(self, key):
        if isinstance(key, str):
            if key in self.HAZARDS:
                idx = self.HAZARDS.index(key)
                return self[:, :, idx, :, :]
            raise KeyError(f"Unknown hazard key: {key}. Expected one of {self.HAZARDS}")
        return super().__getitem__(key)

    def get(self, key, default=None):
        if isinstance(key, str) and key in self.HAZARDS:
            return self[key]
        return default

    def items(self):
        return [(h, self[:, :, i, :, :]) for i, h in enumerate(self.HAZARDS)]

    def keys(self):
        return self.HAZARDS

    def values(self):
        return [self[:, :, i, :, :] for i in range(len(self.HAZARDS))]

    def __iter__(self):
        return iter(self.HAZARDS)

    def __contains__(self, key):
        return key in self.HAZARDS


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

    def forward(
        self,
        sequence: torch.Tensor,
        baseline: Optional[torch.Tensor] = None,
    ) -> PredictionTensor:
        # Validate input shapes
        if sequence.ndim != 5:
            raise ValueError(f"sequence must have shape [batch, time, channels, height, width], got {sequence.shape}")
        
        batch, time, channels, height, width = sequence.shape
        
        # Validate channel counts
        if channels != self.input_channels:
            raise ValueError(f"Expected {self.input_channels} input channels, got {channels}")
        
        # Validate sequence length (should be 7 for canonical training)
        if time != 7:
            raise ValueError(f"Expected sequence length 7, got {time}. Training and inference must use the same sequence length.")
        
        # Handle baseline (extract from sequence if not supplied)
        if baseline is None:
            baseline = sequence[:, -1, :self.baseline_channels, :, :]
        
        if baseline.ndim != 4:
            raise ValueError(f"baseline must have shape [batch, channels, height, width], got {baseline.shape}")
        if baseline.shape[1] != self.baseline_channels:
            raise ValueError(f"Expected {self.baseline_channels} baseline channels, got {baseline.shape[1]}")
        
        # 1. 3D CNN Spatiotemporal Backbone over full resolution
        seq_features = self.backbone(sequence.permute(0, 2, 1, 3, 4))  # [B, hidden, T, H, W]
        
        # 2. Multi-scale token representation for Transformer
        if height == 16 and width == 16:
            pooled_seq = seq_features
        else:
            pooled_seq = nn.functional.adaptive_avg_pool3d(seq_features, (time, 16, 16))
            
        seq_flat = pooled_seq.permute(0, 2, 3, 4, 1).reshape(batch, time * 16 * 16, self.hidden_channels)
        seq_flat = seq_flat + self.pos_emb
        seq_encoded = self.transformer_encoder(seq_flat)
        
        # 3. IMDAA thermodynamic baseline projection and cross-attention
        baseline_proj = self.baseline_projection(baseline)  # [B, hidden, H, W]
        if height == 16 and width == 16:
            pooled_base = baseline_proj
        else:
            pooled_base = nn.functional.adaptive_avg_pool2d(baseline_proj, (16, 16))
            
        base_flat = pooled_base.permute(0, 2, 3, 1).reshape(batch, 16 * 16, self.hidden_channels)
        base_flat = base_flat + self.baseline_pos_emb
        
        attended, _ = self.cross_attention(
            query=seq_encoded,
            key=base_flat,
            value=base_flat,
            need_weights=False,
        )
        fused = self.cross_norm(seq_encoded + attended)
        
        # 4. Spatiotemporal fusion and multi-scale aggregation
        fused_grid = fused.reshape(batch, time, 16, 16, self.hidden_channels).permute(0, 4, 1, 2, 3)
        fused_temporal = fused_grid.mean(dim=2)  # [B, hidden, 16, 16]
        
        if height == 16 and width == 16:
            combined = fused_temporal
        else:
            # Interpolate global fused features to spatial grid and combine with local 3D CNN features
            fused_spatial = nn.functional.interpolate(
                fused_temporal, size=(height, width), mode="bilinear", align_corners=False
            )
            local_spatial = seq_features.mean(dim=2)  # [B, hidden, H, W]
            combined = fused_spatial + local_spatial
            
        # 5. Multi-task hazard heads generating 5 forecast horizons
        hazard_tensors = [
            torch.sigmoid(self.heads[name](combined))
            for name in ("thunderstorms", "cloudbursts", "flash_floods")
        ]
        # Stack along hazard dimension (dim=2): [B, 5, 3, H, W]
        out_tensor = torch.stack(hazard_tensors, dim=2)
        return out_tensor.as_subclass(PredictionTensor)
