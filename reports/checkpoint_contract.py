"""Validation for the artifact contract used by production nowcast inference."""


def validate_checkpoint(checkpoint) -> None:
    """Reject incomplete or incompatible checkpoints before loading weights."""
    if not isinstance(checkpoint, dict):
        raise ValueError("Nowcast checkpoint must be a metadata dictionary")
    if "model" not in checkpoint:
        raise ValueError("Nowcast checkpoint is missing model weights")
    expected = {
        "input_channels": 13,
        "baseline_channels": 6,
        "sequence_length": 7,
        "hidden_channels": 32,
        "num_heads": 4,
        "num_layers": 2,
        "horizons": 5,
    }
    for key, value in expected.items():
        if checkpoint.get(key) != value:
            raise ValueError(f"Nowcast checkpoint contract mismatch for {key}: expected {value}, got {checkpoint.get(key)!r}")
    if checkpoint.get("model_class") not in (None, "SpatiotemporalMTLNet"):
        raise ValueError(f"Unsupported nowcast model class: {checkpoint.get('model_class')!r}")
    # Normalization may be embedded in the checkpoint or supplied separately
    # via ``NowcastingInferenceEngine.load_normalization``.  The latter is
    # useful for artifacts produced by training jobs that persist the scaler
    # as a sidecar file, so its absence is not a checkpoint violation.
    normalization = checkpoint.get("normalization")
    if normalization is not None and (not isinstance(normalization, dict) or "channels" not in normalization):
        raise ValueError("Nowcast checkpoint contains invalid normalization statistics")
