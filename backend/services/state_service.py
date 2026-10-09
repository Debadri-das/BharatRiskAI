"""
System State Machine & Production Artifact Validation Service.
Manages the operational readiness state (READY vs BLOCKED) for the BharatRiskAI nowcasting platform.
"""
from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

import numpy as np
import torch

logger = logging.getLogger("bharatrisk.state")

REPO_ROOT = Path(__file__).resolve().parents[2]

# Module-level state store
_system_state: Dict[str, Any] = {
    "status": "INITIALIZING",
    "model_state": "INITIALIZING",
    "blocked_reason": None,
    "checkpoint_path": None,
    "normalization_path": None,
    "validated_at": None,
    "details": {},
}


def resolve_artifact_paths() -> Tuple[str, str]:
    """Dynamically resolve absolute paths for checkpoint and normalization artifacts."""
    ckpt_env = os.getenv("NOWCAST_CHECKPOINT", "models/checkpoints/best.pt")
    norm_env = os.getenv("NOWCAST_NORMALIZATION", "models/preprocessing/scaler.json")

    ckpt_path = Path(ckpt_env)
    if not ckpt_path.is_absolute():
        ckpt_path = (REPO_ROOT / ckpt_path).resolve()

    norm_path = Path(norm_env)
    if not norm_path.is_absolute():
        norm_path = (REPO_ROOT / norm_path).resolve()

    # Export fully resolved paths to environment
    os.environ["NOWCAST_CHECKPOINT"] = str(ckpt_path)
    os.environ["NOWCAST_NORMALIZATION"] = str(norm_path)

    return str(ckpt_path), str(norm_path)


def validate_artifacts(
    checkpoint_path: str,
    normalization_path: str,
) -> Tuple[bool, Optional[str], Dict[str, Any]]:
    """Validate existence, readability, schema, and dimensional contracts for model artifacts.
    
    Returns:
        (is_valid, blocked_reason, details)
    """
    details: Dict[str, Any] = {
        "checkpoint": {"path": checkpoint_path, "status": "UNKNOWN"},
        "normalization": {"path": normalization_path, "status": "UNKNOWN"},
    }

    # 1. Validate Checkpoint File Existence & Readability
    if not os.path.exists(checkpoint_path):
        err = f"Checkpoint file missing: '{checkpoint_path}'"
        details["checkpoint"]["status"] = "MISSING"
        details["checkpoint"]["error"] = err
        return False, err, details

    if not os.path.isfile(checkpoint_path) or os.path.getsize(checkpoint_path) == 0:
        err = f"Checkpoint file empty or invalid file: '{checkpoint_path}'"
        details["checkpoint"]["status"] = "CORRUPTED"
        details["checkpoint"]["error"] = err
        return False, err, details

    # 2. Validate Checkpoint PyTorch Structure and Model Weights
    try:
        ckpt_data = torch.load(checkpoint_path, map_location="cpu", weights_only=False)
        details["checkpoint"]["file_size_bytes"] = os.path.getsize(checkpoint_path)
    except Exception as exc:
        err = f"Failed to load checkpoint file: {exc}"
        details["checkpoint"]["status"] = "LOAD_ERROR"
        details["checkpoint"]["error"] = err
        return False, err, details

    if not isinstance(ckpt_data, dict):
        err = f"Checkpoint payload must be a dictionary, got {type(ckpt_data).__name__}"
        details["checkpoint"]["status"] = "SCHEMA_ERROR"
        details["checkpoint"]["error"] = err
        return False, err, details

    if "model" not in ckpt_data:
        err = "Checkpoint dictionary missing required 'model' state_dict key"
        details["checkpoint"]["status"] = "SCHEMA_ERROR"
        details["checkpoint"]["error"] = err
        return False, err, details

    # Validate hyperparameter contract & dimensions
    expected_contracts = {
        "input_channels": 13,
        "baseline_channels": 6,
        "sequence_length": 7,
        "hidden_channels": 32,
        "num_heads": 4,
        "num_layers": 2,
        "horizons": 5,
    }
    for key, expected_val in expected_contracts.items():
        actual_val = ckpt_data.get(key)
        if actual_val != expected_val:
            err = (
                f"Checkpoint dimensional mismatch for '{key}': "
                f"expected {expected_val}, got {actual_val!r}"
            )
            details["checkpoint"]["status"] = "DIMENSIONAL_MISMATCH"
            details["checkpoint"]["error"] = err
            return False, err, details

    # Verify model instantiation with weights
    try:
        from ml.nowcasting.architecture import SpatiotemporalMTLNet
        test_net = SpatiotemporalMTLNet(
            input_channels=13,
            baseline_channels=6,
            hidden_channels=32,
            num_heads=4,
            num_layers=2,
        )
        test_net.load_state_dict(ckpt_data["model"])
        test_net.eval()
        details["checkpoint"]["status"] = "VALID"
        details["checkpoint"]["val_loss"] = ckpt_data.get("val_loss")
        details["checkpoint"]["epoch"] = ckpt_data.get("epoch")
    except Exception as exc:
        err = f"Failed to instantiate model architecture from checkpoint state_dict: {exc}"
        details["checkpoint"]["status"] = "INSTANTIATION_ERROR"
        details["checkpoint"]["error"] = err
        return False, err, details

    # 3. Validate Normalization File Existence & Readability
    if not os.path.exists(normalization_path):
        err = f"Normalization statistics file missing: '{normalization_path}'"
        details["normalization"]["status"] = "MISSING"
        details["normalization"]["error"] = err
        return False, err, details

    if not os.path.isfile(normalization_path) or os.path.getsize(normalization_path) == 0:
        err = f"Normalization file empty or invalid file: '{normalization_path}'"
        details["normalization"]["status"] = "CORRUPTED"
        details["normalization"]["error"] = err
        return False, err, details

    try:
        with open(normalization_path, "r", encoding="utf-8") as f:
            norm_stats = json.load(f)
    except Exception as exc:
        err = f"Failed to parse normalization JSON: {exc}"
        details["normalization"]["status"] = "JSON_PARSE_ERROR"
        details["normalization"]["error"] = err
        return False, err, details

    if not isinstance(norm_stats, dict):
        err = f"Normalization root must be a JSON object, got {type(norm_stats).__name__}"
        details["normalization"]["status"] = "SCHEMA_ERROR"
        details["normalization"]["error"] = err
        return False, err, details

    if norm_stats.get("method") != "training-only per-channel standardization":
        err = (
            f"Normalization method mismatch: expected 'training-only per-channel standardization', "
            f"got {norm_stats.get('method')!r}"
        )
        details["normalization"]["status"] = "METHOD_MISMATCH"
        details["normalization"]["error"] = err
        return False, err, details

    channels = norm_stats.get("channels")
    if not isinstance(channels, list) or len(channels) != 19:
        count = len(channels) if isinstance(channels, list) else 0
        err = f"Normalization channel count mismatch: expected 19 channels (13 dynamic + 6 baseline), got {count}"
        details["normalization"]["status"] = "DIMENSIONAL_MISMATCH"
        details["normalization"]["error"] = err
        return False, err, details

    # Validate channel parameters are finite and non-degenerate
    for idx, channel_info in enumerate(channels):
        if not isinstance(channel_info, dict):
            err = f"Normalization channel {idx} must be an object"
            details["normalization"]["status"] = "SCHEMA_ERROR"
            details["normalization"]["error"] = err
            return False, err, details

        mean_val = channel_info.get("mean")
        std_val = channel_info.get("std")
        try:
            m = float(mean_val)
            s = float(std_val)
            if not np.isfinite(m) or not np.isfinite(s) or s <= 0:
                raise ValueError("Non-finite or non-positive value")
        except (TypeError, ValueError) as exc:
            err = f"Invalid statistics for channel {idx} ({channel_info.get('name', 'unnamed')}): mean={mean_val}, std={std_val} ({exc})"
            details["normalization"]["status"] = "STATISTICS_ERROR"
            details["normalization"]["error"] = err
            return False, err, details

    details["normalization"]["status"] = "VALID"
    details["normalization"]["channel_count"] = len(channels)

    return True, None, details


def get_system_state() -> Dict[str, Any]:
    """Retrieve current system operational readiness state."""
    return dict(_system_state)


def set_system_state(
    status: str,
    blocked_reason: Optional[str] = None,
    checkpoint_path: Optional[str] = None,
    normalization_path: Optional[str] = None,
    details: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Update global system readiness state."""
    global _system_state
    _system_state["status"] = status
    _system_state["model_state"] = status
    _system_state["blocked_reason"] = blocked_reason
    if checkpoint_path is not None:
        _system_state["checkpoint_path"] = checkpoint_path
    if normalization_path is not None:
        _system_state["normalization_path"] = normalization_path
    if details is not None:
        _system_state["details"] = details
    _system_state["validated_at"] = datetime.now(timezone.utc).isoformat()
    return dict(_system_state)


def init_and_validate_system() -> Dict[str, Any]:
    """Initialize environment, validate artifacts, and set operational readiness state."""
    ckpt_path, norm_path = resolve_artifact_paths()
    is_valid, blocked_reason, details = validate_artifacts(ckpt_path, norm_path)

    if is_valid:
        set_system_state(
            status="READY",
            blocked_reason=None,
            checkpoint_path=ckpt_path,
            normalization_path=norm_path,
            details=details,
        )
        logger.info(f"System State: READY (Model: {ckpt_path}, Scaler: {norm_path})")

        # Reload/sync the nowcast inference engine
        try:
            from backend.services.nowcast_service import reload_nowcast_engine
            reload_nowcast_engine(ckpt_path, norm_path)
        except Exception as exc:
            logger.warning(f"Engine reload notice: {exc}")
    else:
        set_system_state(
            status="BLOCKED",
            blocked_reason=blocked_reason,
            checkpoint_path=ckpt_path,
            normalization_path=norm_path,
            details=details,
        )
        logger.error(f"System State: BLOCKED - Reason: {blocked_reason}")

    return get_system_state()
