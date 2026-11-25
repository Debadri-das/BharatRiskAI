"""Train the production spatiotemporal multi-task model on known labels.

Section 1.4 Production Improvements:
- PyTorch Dataset (SpatiotemporalDataset) for streaming sequence loading.
- PyTorch DataLoader with configurable batch size and num_workers.
- Batch-by-batch GPU transfers (avoiding preloading entire datasets to device memory).
- Pinned CPU memory when using CUDA for accelerated host-to-device streaming.
- Mixed precision (AMP) properly controlled by --amp and enabled strictly when CUDA is available.
- Checkpoint saving (latest.pt & best.pt) and resumption (--resume).
- Masked Binary Cross-Entropy (BCE) with positive-class weighting for confirmed binary labels.
- Per-hazard and per-horizon evaluation reporting BCE loss and Brier score.
"""
from __future__ import annotations

import argparse
import csv
import json
import random
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Sequence

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import numpy as np
import torch
import torch.nn as nn
from torch.utils.data import DataLoader, Dataset

from ml.nowcasting.architecture import SpatiotemporalMTLNet
from reports.unified_feature_schema import BASELINE_ORDER, CHANNEL_ORDER

BASELINE_INDICES = tuple(CHANNEL_ORDER.index(name) for name in BASELINE_ORDER)
HAZARD_NAMES = ("thunderstorms", "cloudbursts", "flash_floods")
HORIZON_NAMES = ("+2h", "+3h", "+4h", "+5h", "+6h")


def blocked(reason: str, **details) -> None:
    """Emit an explicit blocked report and stop; never fabricate training results."""
    report = {"status": "blocked", "reason": reason, "generated_at": datetime.now(timezone.utc).isoformat(), **details}
    (ROOT / "reports").mkdir(parents=True, exist_ok=True)
    (ROOT / "reports" / "training_blocked.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    raise RuntimeError(f"Training blocked: {reason} (see reports/training_blocked.json)")


class SpatiotemporalDataset(Dataset):
    """PyTorch Dataset loading spatiotemporal sequences on-the-fly.
    
    Prevents preloading gigabytes of sequences into memory or GPU VRAM.
    """
    def __init__(
        self,
        rows: list[dict[str, Any]],
        base_root: Path,
        seq_means: np.ndarray,
        seq_stds: np.ndarray,
        base_means: np.ndarray,
        base_stds: np.ndarray,
    ):
        self.rows = rows
        self.base_root = base_root
        self.seq_means = seq_means.reshape(1, 13, 1, 1)
        self.seq_stds = seq_stds.reshape(1, 13, 1, 1)
        self.base_means = base_means.reshape(6, 1, 1)
        self.base_stds = base_stds.reshape(6, 1, 1)

    def __len__(self) -> int:
        return len(self.rows)

    def __getitem__(self, idx: int) -> tuple[torch.Tensor, torch.Tensor, torch.Tensor]:
        row = self.rows[idx]
        in_path = self.base_root / row["input_path"]
        tgt_path = self.base_root / row["target_path"]

        with np.load(in_path, allow_pickle=False) as data:
            raw_in = data["inputs"]  # Expected [7, 13, H, W]

        with np.load(tgt_path, allow_pickle=False) as data:
            raw_tgt = data["targets"]  # Expected [5, 3, H, W]

        # Standardize using training statistics; impute missing values with 0.0 (standardized training mean)
        in_valid = np.isfinite(raw_in)
        norm_in = np.where(in_valid, (raw_in - self.seq_means) / self.seq_stds, 0.0).astype(np.float32)

        raw_base = raw_in[-1, list(BASELINE_INDICES), :, :]
        base_valid = np.isfinite(raw_base)
        norm_base = np.where(base_valid, (raw_base - self.base_means) / self.base_stds, 0.0).astype(np.float32)

        return (
            torch.from_numpy(norm_in).float(),
            torch.from_numpy(norm_base).float(),
            torch.from_numpy(raw_tgt).float(),
        )


def masked_weighted_bce_loss(
    predictions: torch.Tensor,
    targets: torch.Tensor,
    pos_weight: float = 1.0,
    eps: float = 1e-7,
) -> tuple[torch.Tensor, torch.Tensor, int]:
    """Masked Binary Cross-Entropy with positive-class weighting over valid binary targets.
    
    Returns:
        (bce_loss, brier_score, valid_pixel_count)
    """
    valid_mask = torch.isfinite(targets) & ((targets == 0.0) | (targets == 1.0))
    if not valid_mask.any():
        zero = torch.zeros((), device=predictions.device, dtype=predictions.dtype)
        return zero, zero, 0

    clean_targets = torch.nan_to_num(targets, nan=0.0).clamp(0.0, 1.0)
    p = predictions.clamp(eps, 1.0 - eps)

    # Weighted BCE: - [w_pos * y * log(p) + (1 - y) * log(1 - p)]
    bce = -(pos_weight * clean_targets * torch.log(p) + (1.0 - clean_targets) * torch.log(1.0 - p))
    valid_count = valid_mask.sum().clamp_min(1.0)
    bce_loss = (bce * valid_mask.float()).sum() / valid_count

    # Brier score: MSE between predicted probabilities and binary targets over valid pixels
    brier = (((p - clean_targets) ** 2) * valid_mask.float()).sum() / valid_count

    return bce_loss, brier, int(valid_mask.sum().item())


def compute_multitask_loss(
    predictions: torch.Tensor,
    targets: torch.Tensor,
    weights: tuple[float, float, float] = (1.0, 1.0, 1.0),
    pos_weights: tuple[float, float, float] = (1.0, 1.0, 1.0),
) -> tuple[torch.Tensor, dict[str, float], dict[str, float]]:
    """Compute multi-task masked weighted BCE loss and Brier scores across 3 hazards."""
    total_loss = torch.zeros((), device=predictions.device, dtype=predictions.dtype)
    task_losses = {}
    task_briers = {}

    for idx, name in enumerate(HAZARD_NAMES):
        pred_c = predictions[:, :, idx, :, :]
        target_c = targets[:, :, idx, :, :]
        pw = float(pos_weights[idx]) if idx < len(pos_weights) else 1.0
        loss_c, brier_c, _ = masked_weighted_bce_loss(pred_c, target_c, pos_weight=pw)
        weight_c = float(weights[idx]) if idx < len(weights) else 1.0
        total_loss = total_loss + weight_c * loss_c
        task_losses[name] = float(loss_c.detach().cpu().item())
        task_briers[name] = float(brier_c.detach().cpu().item())

    total_loss = total_loss / max(sum(weights), 1e-6)
    return total_loss, task_losses, task_briers


def evaluate_loader(
    model: nn.Module,
    loader: DataLoader,
    device: torch.device,
    weights: tuple[float, float, float],
    pos_weights: tuple[float, float, float],
    pin_memory: bool,
) -> dict[str, Any]:
    """Evaluate DataLoader batch-by-batch across all hazards and forecast horizons."""
    model.eval()
    accum_bce = np.zeros((3, 5), dtype=np.float64)
    accum_brier = np.zeros((3, 5), dtype=np.float64)
    accum_count = np.zeros((3, 5), dtype=np.int64)
    batch_losses = []

    with torch.inference_mode():
        for inputs, baseline, targets in loader:
            inputs = inputs.to(device, non_blocking=pin_memory)
            baseline = baseline.to(device, non_blocking=pin_memory)
            targets = targets.to(device, non_blocking=pin_memory)

            outputs = model(inputs, baseline)
            loss, _, _ = compute_multitask_loss(outputs, targets, weights=weights, pos_weights=pos_weights)
            batch_losses.append(loss.item())

            for h_idx in range(3):
                pw = float(pos_weights[h_idx]) if h_idx < len(pos_weights) else 1.0
                for hz_idx in range(5):
                    p_cell = outputs[:, hz_idx, h_idx, :, :]
                    y_cell = targets[:, hz_idx, h_idx, :, :]
                    bce_val, brier_val, count = masked_weighted_bce_loss(p_cell, y_cell, pos_weight=pw)
                    if count > 0:
                        accum_bce[h_idx, hz_idx] += bce_val.item() * count
                        accum_brier[h_idx, hz_idx] += brier_val.item() * count
                        accum_count[h_idx, hz_idx] += count

    total_val_loss = float(np.mean(batch_losses)) if batch_losses else 0.0

    # Per-hazard aggregation
    per_hazard = {}
    for h_idx, h_name in enumerate(HAZARD_NAMES):
        h_cnt = accum_count[h_idx].sum()
        h_bce = float(accum_bce[h_idx].sum() / max(h_cnt, 1))
        h_brier = float(accum_brier[h_idx].sum() / max(h_cnt, 1))
        per_hazard[h_name] = {"bce": h_bce, "brier": h_brier, "valid_pixels": int(h_cnt)}

    # Per-horizon aggregation
    per_horizon = {}
    for hz_idx, hz_name in enumerate(HORIZON_NAMES):
        hz_cnt = accum_count[:, hz_idx].sum()
        hz_bce = float(accum_bce[:, hz_idx].sum() / max(hz_cnt, 1))
        hz_brier = float(accum_brier[:, hz_idx].sum() / max(hz_cnt, 1))
        per_horizon[hz_name] = {"bce": hz_bce, "brier": hz_brier, "valid_pixels": int(hz_cnt)}

    # Per-hazard and per-horizon matrix
    per_hazard_horizon = {}
    for h_idx, h_name in enumerate(HAZARD_NAMES):
        per_hazard_horizon[h_name] = {}
        for hz_idx, hz_name in enumerate(HORIZON_NAMES):
            cnt = accum_count[h_idx, hz_idx]
            bce_cell = float(accum_bce[h_idx, hz_idx] / max(cnt, 1))
            brier_cell = float(accum_brier[h_idx, hz_idx] / max(cnt, 1))
            per_hazard_horizon[h_name][hz_name] = {"bce": bce_cell, "brier": brier_cell, "valid_pixels": int(cnt)}

    total_cnt = accum_count.sum()
    total_brier = float(accum_brier.sum() / max(total_cnt, 1))

    return {
        "val_loss": total_val_loss,
        "val_brier": total_brier,
        "per_hazard": per_hazard,
        "per_horizon": per_horizon,
        "per_hazard_horizon": per_hazard_horizon,
    }


def set_determinism(seed: int) -> None:
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(seed)
        torch.backends.cudnn.deterministic = True
        torch.backends.cudnn.benchmark = False
    try:
        torch.use_deterministic_algorithms(True, warn_only=True)
    except (TypeError, AttributeError):
        pass


def main() -> None:
    parser = argparse.ArgumentParser(description="Train multi-task spatiotemporal model.")
    parser.add_argument("--epochs", type=int, default=100, help="Number of training epochs.")
    parser.add_argument("--seed", type=int, default=20260922, help="Random seed for determinism.")
    parser.add_argument("--patience", type=int, default=15, help="Early-stopping patience on validation loss.")
    parser.add_argument("--amp", action="store_true", default=True, help="Enable Automatic Mixed Precision (AMP).")
    parser.add_argument("--no-amp", dest="amp", action="store_false", help="Disable Automatic Mixed Precision (AMP).")
    parser.add_argument("--lr", type=float, default=1e-4, help="AdamW learning rate.")
    parser.add_argument("--weight-decay", type=float, default=1e-5, help="AdamW weight decay.")
    parser.add_argument("--batch-size", type=int, default=2, help="Mini-batch size.")
    parser.add_argument("--num-workers", type=int, default=0, help="Number of DataLoader worker processes.")
    parser.add_argument("--resume", type=str, default=None, help="Checkpoint path or 'latest' / 'best' to resume from.")
    parser.add_argument("--pos-weights", nargs=3, type=float, default=None, help="Positive-class weights for 3 hazards.")
    args = parser.parse_args()

    index_path = ROOT / "data" / "datasets" / "final" / "index.csv"
    if not index_path.exists():
        blocked("data/datasets/final/index.csv does not exist; build known-label event-split sequences first.")

    set_determinism(args.seed)

    with index_path.open(encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    if not rows:
        blocked("final dataset index is empty.")

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    train_rows = [row for row in rows if row["split"] == "train"]
    validation_rows = [row for row in rows if row["split"] in ("validation", "val")]
    test_rows = [row for row in rows if row["split"] == "test"]

    if not train_rows or not validation_rows:
        blocked(
            "event-based train and validation splits must both contain samples.",
            train_samples=len(train_rows),
            validation_samples=len(validation_rows),
        )

    first = np.load(ROOT / train_rows[0]["input_path"], allow_pickle=False)
    channels = int(first["inputs"].shape[1])
    if first["inputs"].ndim != 4 or first["inputs"].shape[0] != 7 or channels != 13:
        blocked("training samples must contain inputs shaped [7, 13, H, W].", shape=first["inputs"].shape)
    if not np.isfinite(first["inputs"]).all():
        nan_count = int((~np.isfinite(first["inputs"])).sum())
        print(f"Notice: sequence inputs contain {nan_count} non-finite pixels; standardized training mean imputation applied.")

    # Load normalization statistics strictly fitted on training split
    scaler_path = ROOT / "models" / "preprocessing" / "scaler.json"
    if not scaler_path.exists():
        blocked("training-only normalization statistics are missing; run the normalize stage first.")
    norm_info = json.loads(scaler_path.read_text(encoding="utf-8"))
    if len(norm_info.get("channels", [])) != 19:
        blocked(
            "normalization statistics must contain 19 channels (13 sequence + 6 baseline).",
            channels=len(norm_info.get("channels", [])),
        )

    seq_means = np.array([c["mean"] for c in norm_info["channels"][:13]], dtype=np.float32)
    seq_stds = np.array([max(c["std"], 1e-7) for c in norm_info["channels"][:13]], dtype=np.float32)
    base_means = np.array([c["mean"] for c in norm_info["channels"][13:19]], dtype=np.float32)
    base_stds = np.array([max(c["std"], 1e-7) for c in norm_info["channels"][13:19]], dtype=np.float32)

    # Compute positive-class weights from dataset statistics if not specified
    if args.pos_weights is not None:
        pos_weights = tuple(args.pos_weights)
    else:
        norm_stats_file = ROOT / "data" / "datasets" / "normalization_stats.json"
        pos_weights_list = [4.0, 10.0, 7.0]  # Safe defaults
        if norm_stats_file.exists():
            try:
                stats_meta = json.loads(norm_stats_file.read_text(encoding="utf-8"))
                target_meta = stats_meta.get("target_channels", {})
                pos_weights_list = []
                for h_key in ["thunderstorm", "cloudburst", "flash_flood"]:
                    pr = target_meta.get(h_key, {}).get("positive_rate", 0.1)
                    pw = (1.0 - pr) / max(pr, 1e-4) if pr > 0 else 5.0
                    pos_weights_list.append(float(np.clip(pw, 1.0, 20.0)))
            except Exception:
                pass
        pos_weights = tuple(pos_weights_list)

    print(f"Computed positive-class weights for loss: thunderstorm={pos_weights[0]:.2f}, cloudburst={pos_weights[1]:.2f}, flash_flood={pos_weights[2]:.2f}")

    # Build PyTorch Datasets
    train_dataset = SpatiotemporalDataset(train_rows, ROOT, seq_means, seq_stds, base_means, base_stds)
    val_dataset = SpatiotemporalDataset(validation_rows, ROOT, seq_means, seq_stds, base_means, base_stds)
    test_dataset = SpatiotemporalDataset(test_rows, ROOT, seq_means, seq_stds, base_means, base_stds)

    pin_memory = (device.type == "cuda")
    train_loader = DataLoader(
        train_dataset,
        batch_size=args.batch_size,
        shuffle=True,
        num_workers=args.num_workers,
        pin_memory=pin_memory,
        drop_last=False,
    )
    val_loader = DataLoader(
        val_dataset,
        batch_size=args.batch_size,
        shuffle=False,
        num_workers=args.num_workers,
        pin_memory=pin_memory,
        drop_last=False,
    )
    test_loader = DataLoader(
        test_dataset,
        batch_size=args.batch_size,
        shuffle=False,
        num_workers=args.num_workers,
        pin_memory=pin_memory,
        drop_last=False,
    )

    # Initialize model and optimizer
    model = SpatiotemporalMTLNet(
        input_channels=13,
        baseline_channels=6,
        hidden_channels=32,
        num_heads=4,
        num_layers=2,
    ).to(device)
    optimizer = torch.optim.AdamW(model.parameters(), lr=args.lr, weight_decay=args.weight_decay)

    # AMP Configuration: strictly respect --amp argument and device availability
    use_amp = bool(args.amp and device.type == "cuda")
    scaler = torch.amp.GradScaler("cuda", enabled=use_amp)

    start_epoch = 1
    best_val_loss = float("inf")
    best_epoch = 0
    epochs_without_improvement = 0
    history: list[dict] = []
    checkpoint_dir = ROOT / "models" / "checkpoints"
    checkpoint_dir.mkdir(parents=True, exist_ok=True)

    # Checkpoint Resumption
    if args.resume:
        resume_target = checkpoint_dir / "latest.pt" if args.resume == "latest" else (
            checkpoint_dir / "best.pt" if args.resume == "best" else Path(args.resume)
        )
        if not resume_target.is_absolute():
            resume_target = ROOT / resume_target
        if resume_target.exists():
            print(f"Resuming training checkpoint from {resume_target}...")
            ckpt = torch.load(resume_target, map_location=device, weights_only=False)
            model.load_state_dict(ckpt["model"])
            if "optimizer" in ckpt:
                optimizer.load_state_dict(ckpt["optimizer"])
            if use_amp and "scaler" in ckpt and ckpt["scaler"] is not None:
                scaler.load_state_dict(ckpt["scaler"])
            start_epoch = ckpt.get("epoch", 0) + 1
            best_val_loss = ckpt.get("best_val_loss", ckpt.get("val_loss", float("inf")))
            best_epoch = ckpt.get("epoch", 0)
            history = ckpt.get("history", [])
            print(f"Resumed successfully at epoch {start_epoch} (previous best val_loss: {best_val_loss:.5f})")
        else:
            print(f"Warning: resume checkpoint {resume_target} not found; starting fresh.")

    start_time = time.time()
    print(f"Starting training: {len(train_dataset)} train samples, {len(val_dataset)} validation samples.")
    print(f"Device: {device} | AMP: {use_amp} (arg={args.amp}) | Pinned Memory: {pin_memory} | Batch Size: {args.batch_size} | Max Epochs: {args.epochs}")

    for epoch in range(start_epoch, args.epochs + 1):
        model.train()
        train_batch_losses = []
        train_task_losses_accum = {h: [] for h in HAZARD_NAMES}
        train_brier_accum = {h: [] for h in HAZARD_NAMES}

        for inputs, baseline, targets in train_loader:
            # Batch-by-batch GPU transfers with non_blocking pinned memory
            inputs = inputs.to(device, non_blocking=pin_memory)
            baseline = baseline.to(device, non_blocking=pin_memory)
            targets = targets.to(device, non_blocking=pin_memory)

            optimizer.zero_grad(set_to_none=True)

            with torch.autocast(device_type="cuda", enabled=use_amp):
                outputs = model(inputs, baseline)
                total_loss, task_losses, task_briers = compute_multitask_loss(
                    outputs, targets, weights=(1.0, 1.0, 1.0), pos_weights=pos_weights
                )

            if use_amp:
                scaler.scale(total_loss).backward()
                scaler.step(optimizer)
                scaler.update()
            else:
                total_loss.backward()
                optimizer.step()

            train_batch_losses.append(total_loss.item())
            for h, l in task_losses.items():
                train_task_losses_accum[h].append(l)
            for h, b in task_briers.items():
                train_brier_accum[h].append(b)

        train_loss = float(np.mean(train_batch_losses))
        train_brier = float(np.mean([np.mean(train_brier_accum[h]) for h in HAZARD_NAMES]))

        # Per-hazard and per-horizon validation evaluation
        eval_metrics = evaluate_loader(
            model=model,
            loader=val_loader,
            device=device,
            weights=(1.0, 1.0, 1.0),
            pos_weights=pos_weights,
            pin_memory=pin_memory,
        )

        val_loss = eval_metrics["val_loss"]
        val_brier = eval_metrics["val_brier"]

        record = {
            "epoch": epoch,
            "train_loss": train_loss,
            "train_brier": train_brier,
            "val_loss": val_loss,
            "validation_loss": val_loss,
            "val_brier": val_brier,
            "validation_brier": val_brier,
            "train_task_losses": {h: float(np.mean(train_task_losses_accum[h])) for h in train_task_losses_accum},
            "per_hazard": eval_metrics["per_hazard"],
            "per_horizon": eval_metrics["per_horizon"],
            "per_hazard_horizon": eval_metrics["per_hazard_horizon"],
        }
        history.append(record)

        print(f"Epoch {epoch:03d}/{args.epochs:03d} | Train Loss: {train_loss:.5f} | Val Loss: {val_loss:.5f} | Val Brier: {val_brier:.5f}")
        h_summary = " | ".join(f"{h[:5]}: BCE={eval_metrics['per_hazard'][h]['bce']:.4f}, Br={eval_metrics['per_hazard'][h]['brier']:.4f}" for h in HAZARD_NAMES)
        hz_summary = " | ".join(f"{hz}: BCE={eval_metrics['per_horizon'][hz]['bce']:.4f}" for hz in HORIZON_NAMES)
        print(f"  -> Per-Hazard:  {h_summary}")
        print(f"  -> Per-Horizon: {hz_summary}")

        # Save checkpoint latest.pt at every epoch for resumption
        latest_ckpt = {
            "model": model.state_dict(),
            "optimizer": optimizer.state_dict(),
            "scaler": scaler.state_dict() if use_amp else None,
            "epoch": epoch,
            "best_val_loss": best_val_loss,
            "val_loss": val_loss,
            "history": history,
            "seed": args.seed,
            "normalization": norm_info,
            "pos_weights": list(pos_weights),
            "input_channels": 13,
            "baseline_channels": 6,
            "sequence_length": 7,
            "hidden_channels": 32,
            "num_heads": 4,
            "num_layers": 2,
            "horizons": 5,
        }
        torch.save(latest_ckpt, checkpoint_dir / "latest.pt")

        # Early stopping and saving best.pt
        if val_loss < best_val_loss - 1e-5:
            best_val_loss = val_loss
            best_epoch = epoch
            epochs_without_improvement = 0
            best_ckpt = dict(latest_ckpt)
            best_ckpt.update({
                "validation_loss": best_val_loss,
                "val_loss": best_val_loss,
                "validation_brier": val_brier,
                "per_hazard": eval_metrics["per_hazard"],
                "per_horizon": eval_metrics["per_horizon"],
                "model_class": "SpatiotemporalMTLNet",
            })
            torch.save(best_ckpt, checkpoint_dir / "best.pt")
        else:
            epochs_without_improvement += 1
            if epochs_without_improvement >= args.patience:
                print(f"Early stopping triggered at epoch {epoch}: val_loss did not improve for {args.patience} consecutive epochs.")
                break

    time_elapsed = time.time() - start_time
    early_stopped = epochs_without_improvement >= args.patience

    # Finalize training metadata
    metadata = {
        "status": "completed",
        "epochs_completed": len(history),
        "best_epoch": best_epoch,
        "final_train_loss": history[-1]["train_loss"] if history else None,
        "final_val_loss": history[-1]["val_loss"] if history else None,
        "best_validation_loss": best_val_loss,
        "time_elapsed_seconds": round(time_elapsed, 2),
        "early_stopped": early_stopped,
        "device": str(device),
        "amp_enabled": use_amp,
        "positive_weights": list(pos_weights),
        "hyperparameters": {
            "epochs": args.epochs,
            "patience": args.patience,
            "seed": args.seed,
            "learning_rate": args.lr,
            "weight_decay": args.weight_decay,
            "amp": args.amp,
            "batch_size": args.batch_size,
            "loss_weights": [1.0, 1.0, 1.0],
            "input_channels": 13,
            "baseline_channels": 6,
            "sequence_length": 7,
            "hidden_channels": 32,
            "num_heads": 4,
            "num_layers": 2,
            "horizons": 5,
        },
        "history": history,
    }
    (checkpoint_dir / "training_metadata.json").write_text(json.dumps(metadata, indent=2), encoding="utf-8")

    # Materialize split predictions from best checkpoint for downstream stages
    best = torch.load(checkpoint_dir / "best.pt", map_location=device, weights_only=False)
    model.load_state_dict(best["model"])
    model.eval()

    def write_predictions(loader: DataLoader, output_name: str) -> None:
        if len(loader.dataset) == 0:
            return
        prob_batches = []
        target_batches = []
        with torch.inference_mode():
            for inputs, baseline, targets in loader:
                inputs = inputs.to(device, non_blocking=pin_memory)
                baseline = baseline.to(device, non_blocking=pin_memory)
                outputs = model(inputs, baseline)
                prob_batches.append(outputs.cpu().numpy())
                target_batches.append(targets.numpy())

        probabilities = np.concatenate(prob_batches, axis=0)
        targets = np.concatenate(target_batches, axis=0)
        logits = np.log(np.clip(probabilities, 1e-6, 1.0 - 1e-6) / np.clip(1.0 - probabilities, 1e-6, 1.0))
        out_path = ROOT / "data" / "datasets" / "final" / output_name
        np.savez_compressed(
            out_path,
            probabilities=probabilities,
            targets=targets,
            logits=logits,
        )
        print(f"Materialized {output_name} with shape {probabilities.shape}")

    write_predictions(val_loader, "validation_predictions.npz")
    write_predictions(test_loader, "test_predictions.npz")

    summary = {
        "status": "trained",
        "device": str(device),
        "epochs_completed": len(history),
        "best_epoch": best_epoch,
        "best_validation_loss": best_val_loss,
        "early_stopped": early_stopped,
        "time_elapsed_seconds": round(time_elapsed, 2),
    }
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
