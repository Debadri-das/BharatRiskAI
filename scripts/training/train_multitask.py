"""Train the production spatiotemporal multi-task model on known labels."""
from __future__ import annotations

import argparse
import csv
import json
import random
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import numpy as np
import torch
from ml.nowcasting.architecture import SpatiotemporalMTLNet
from reports.unified_feature_schema import BASELINE_ORDER, CHANNEL_ORDER

BASELINE_INDICES = tuple(CHANNEL_ORDER.index(name) for name in BASELINE_ORDER)


def blocked(reason: str, **details) -> None:
    """Emit an explicit blocked report and stop; never fabricate training results."""
    report = {"status": "blocked", "reason": reason, "generated_at": datetime.now(timezone.utc).isoformat(), **details}
    (ROOT / "reports").mkdir(parents=True, exist_ok=True)
    (ROOT / "reports" / "training_blocked.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    raise RuntimeError(f"Training blocked: {reason} (see reports/training_blocked.json)")


def masked_mse_loss(
    predictions: torch.Tensor,
    targets: torch.Tensor,
    mask: torch.Tensor | None = None,
) -> torch.Tensor:
    """Masked Mean Squared Error loss computed strictly over valid non-NaN spatial pixels."""
    if mask is None:
        mask = torch.isfinite(targets)
    clean_targets = torch.nan_to_num(targets, nan=0.0)
    squared_diff = (predictions - clean_targets) ** 2
    valid_elements = mask.sum().clamp_min(1.0)
    return (squared_diff * mask.float()).sum() / valid_elements


def compute_multitask_loss(
    predictions: torch.Tensor,
    targets: torch.Tensor,
    weights: tuple[float, float, float] = (1.0, 1.0, 1.0),
) -> tuple[torch.Tensor, dict[str, float]]:
    """Compute multi-task masked loss across 3 hazards and 5 lead times."""
    hazard_names = ("thunderstorms", "cloudbursts", "flash_floods")
    total_loss = torch.zeros((), device=predictions.device, dtype=predictions.dtype)
    channel_losses = {}
    for idx, name in enumerate(hazard_names):
        pred_c = predictions[:, :, idx, :, :]
        target_c = targets[:, :, idx, :, :]
        mask_c = torch.isfinite(target_c)
        loss_c = masked_mse_loss(pred_c, target_c, mask=mask_c)
        weight_c = float(weights[idx]) if idx < len(weights) else 1.0
        total_loss = total_loss + weight_c * loss_c
        channel_losses[name] = float(loss_c.detach().cpu().item())
    total_loss = total_loss / max(sum(weights), 1e-6)
    return total_loss, channel_losses


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
    validation_rows = [row for row in rows if row["split"] == "validation"]
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
        blocked("sequence inputs contain missing values; fit documented training-only imputation before training.")

    # Load normalization statistics strictly fitted on training split (Amphan)
    scaler_path = ROOT / "models" / "preprocessing" / "scaler.json"
    if not scaler_path.exists():
        blocked("training-only normalization statistics are missing; run the normalize stage first.")
    norm_info = json.loads(scaler_path.read_text(encoding="utf-8"))
    if len(norm_info.get("channels", [])) != 19:
        blocked(
            "normalization statistics must contain 19 channels (13 sequence + 6 baseline).",
            channels=len(norm_info.get("channels", [])),
        )

    seq_means = np.array([c["mean"] for c in norm_info["channels"][:13]], dtype=np.float32).reshape(1, 13, 1, 1)
    seq_stds = np.array([max(c["std"], 1e-7) for c in norm_info["channels"][:13]], dtype=np.float32).reshape(1, 13, 1, 1)
    base_means = np.array([c["mean"] for c in norm_info["channels"][13:19]], dtype=np.float32).reshape(6, 1, 1)
    base_stds = np.array([max(c["std"], 1e-7) for c in norm_info["channels"][13:19]], dtype=np.float32).reshape(6, 1, 1)

    # Initialize model and optimizer
    model = SpatiotemporalMTLNet(
        input_channels=13,
        baseline_channels=6,
        hidden_channels=32,
        num_heads=4,
        num_layers=2,
    ).to(device)
    optimizer = torch.optim.AdamW(model.parameters(), lr=args.lr, weight_decay=args.weight_decay)

    # AMP Setup: instantiate scaler before training loop
    scaler = torch.cuda.amp.GradScaler()

    best_val_loss = float("inf")
    best_epoch = 0
    epochs_without_improvement = 0
    history: list[dict] = []
    checkpoint_dir = ROOT / "models" / "checkpoints"
    checkpoint_dir.mkdir(parents=True, exist_ok=True)
    start_time = time.time()

    def load_dataset(items):
        input_list, base_list, target_list = [], [], []
        for row in items:
            raw_in = np.load(ROOT / row["input_path"], allow_pickle=False)["inputs"]
            raw_tgt = np.load(ROOT / row["target_path"], allow_pickle=False)["targets"]
            norm_in = (raw_in - seq_means) / seq_stds
            raw_base = raw_in[-1, list(BASELINE_INDICES), :, :]
            norm_base = (raw_base - base_means) / base_stds
            input_list.append(norm_in)
            base_list.append(norm_base)
            target_list.append(raw_tgt)
        inputs_t = torch.from_numpy(np.stack(input_list)).float().to(device)
        baseline_t = torch.from_numpy(np.stack(base_list)).float().to(device)
        targets_t = torch.from_numpy(np.stack(target_list)).float().to(device)
        return inputs_t, baseline_t, targets_t

    print("Pre-loading training and validation splits into memory for accelerated training...")
    train_inputs, train_baseline, train_targets = load_dataset(train_rows)
    val_inputs, val_baseline, val_targets = load_dataset(validation_rows)

    print(f"Starting training: {len(train_rows)} train samples, {len(validation_rows)} validation samples.")
    print(f"Device: {device} | AMP: {args.amp} | Max Epochs: {args.epochs} | Early Stopping Patience: {args.patience}")

    for epoch in range(1, args.epochs + 1):
        model.train()
        train_batch_losses = []
        train_task_losses_accum = {h: [] for h in ("thunderstorms", "cloudbursts", "flash_floods")}

        for start in range(0, len(train_rows), args.batch_size):
            inputs = train_inputs[start:start + args.batch_size]
            baseline = train_baseline[start:start + args.batch_size]
            targets = train_targets[start:start + args.batch_size]

            # 1. Zero gradients
            optimizer.zero_grad(set_to_none=True)

            # 2. Forward pass and loss inside autocast
            with torch.autocast(device_type="cuda" if torch.cuda.is_available() else "cpu"):
                outputs = model(inputs, baseline)
                total_loss, task_losses = compute_multitask_loss(outputs, targets, weights=(1.0, 1.0, 1.0))

            # 3. Scale composite loss and backpropagate
            scaler.scale(total_loss).backward()

            # 4. Update weights
            scaler.step(optimizer)

            # 5. Update scaler factor
            scaler.update()

            train_batch_losses.append(total_loss.item())
            for h, l in task_losses.items():
                train_task_losses_accum[h].append(l)

        train_loss = float(np.mean(train_batch_losses))

        # Validation evaluation
        model.eval()
        val_batch_losses = []
        val_task_losses_accum = {h: [] for h in ("thunderstorms", "cloudbursts", "flash_floods")}
        val_brier_scores = []

        with torch.inference_mode():
            for start in range(0, len(validation_rows), args.batch_size):
                inputs = val_inputs[start:start + args.batch_size]
                baseline = val_baseline[start:start + args.batch_size]
                targets = val_targets[start:start + args.batch_size]

                outputs = model(inputs, baseline)
                loss, task_losses = compute_multitask_loss(outputs, targets, weights=(1.0, 1.0, 1.0))
                val_batch_losses.append(loss.item())
                for h, l in task_losses.items():
                    val_task_losses_accum[h].append(l)

                clean_t = torch.nan_to_num(targets)
                finite_mask = torch.isfinite(targets)
                brier = (((outputs - clean_t) ** 2) * finite_mask).sum().item() / finite_mask.sum().clamp_min(1.0).item()
                val_brier_scores.append(brier)

        val_loss = float(np.mean(val_batch_losses))
        val_brier = float(np.mean(val_brier_scores))

        record = {
            "epoch": epoch,
            "train_loss": train_loss,
            "val_loss": val_loss,
            "validation_loss": val_loss,
            "validation_brier": val_brier,
            "train_task_losses": {h: float(np.mean(train_task_losses_accum[h])) for h in train_task_losses_accum},
            "val_task_losses": {h: float(np.mean(val_task_losses_accum[h])) for h in val_task_losses_accum},
        }
        history.append(record)
        print(f"Epoch {epoch:03d}/{args.epochs:03d} | Train Loss: {train_loss:.5f} | Val Loss: {val_loss:.5f} | Val Brier: {val_brier:.5f}")

        # Early stopping and checkpointing
        if val_loss < best_val_loss - 1e-5:
            best_val_loss = val_loss
            best_epoch = epoch
            epochs_without_improvement = 0
            torch.save(
                {
                    "model": model.state_dict(),
                    "input_channels": 13,
                    "baseline_channels": 6,
                    "sequence_length": 7,
                    "hidden_channels": 32,
                    "num_heads": 4,
                    "num_layers": 2,
                    "horizons": 5,
                    "validation_loss": best_val_loss,
                    "val_loss": best_val_loss,
                    "epoch": epoch,
                    "seed": args.seed,
                    "model_class": "SpatiotemporalMTLNet",
                    "normalization": norm_info,
                },
                checkpoint_dir / "best.pt",
            )
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
        "amp_enabled": bool(args.amp and torch.cuda.is_available()),
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

    def write_predictions(items_tensors: tuple[torch.Tensor, torch.Tensor, torch.Tensor], output_name: str) -> None:
        inputs_all, baseline_all, targets_all = items_tensors
        if inputs_all.shape[0] == 0:
            return
        prob_batches = []
        with torch.inference_mode():
            for start in range(0, inputs_all.shape[0], args.batch_size):
                inputs = inputs_all[start:start + args.batch_size]
                baseline = baseline_all[start:start + args.batch_size]
                outputs = model(inputs, baseline)
                prob_batches.append(outputs.cpu().numpy())
        probabilities = np.concatenate(prob_batches, axis=0)
        targets = targets_all.cpu().numpy()
        logits = np.log(np.clip(probabilities, 1e-6, 1 - 1e-6) / np.clip(1 - probabilities, 1e-6, 1))
        np.savez_compressed(
            ROOT / "data" / "datasets" / "final" / output_name,
            probabilities=probabilities,
            targets=targets,
            logits=logits,
        )

    test_inputs, test_baseline, test_targets = load_dataset(test_rows)
    write_predictions((val_inputs, val_baseline, val_targets), "validation_predictions.npz")
    write_predictions((test_inputs, test_baseline, test_targets), "test_predictions.npz")

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
