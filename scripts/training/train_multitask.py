"""Train the historical multi-task model only on known, event-split labels."""
from __future__ import annotations

import argparse
import csv
import json
import random
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]


def blocked(reason: str, **details) -> None:
    """Emit an explicit blocked report and stop; never fabricate training results."""
    report = {"status": "blocked", "reason": reason, "generated_at": datetime.now(timezone.utc).isoformat(), **details}
    (ROOT / "reports").mkdir(parents=True, exist_ok=True)
    (ROOT / "reports" / "training_blocked.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    raise RuntimeError(f"Training blocked: {reason} (see reports/training_blocked.json)")


def focal_loss(logits, targets, mask, gamma: float = 2.0, pos_weight: float = 1.0):
    """Focal loss on known (finite) targets only; unknown/NaN cells are masked out."""
    import torch
    clean = torch.nan_to_num(targets)
    probabilities = torch.sigmoid(logits)
    bce = torch.nn.functional.binary_cross_entropy_with_logits(logits, clean, reduction="none", pos_weight=torch.tensor(pos_weight, dtype=logits.dtype, device=logits.device))
    pt = probabilities * clean + (1 - probabilities) * (1 - clean)
    weighted = ((1 - pt) ** gamma) * bce * mask
    return weighted.sum() / mask.sum().clamp_min(1.0)


def set_determinism(seed: int) -> None:
    import torch
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    torch.cuda.manual_seed_all(seed)
    torch.backends.cudnn.deterministic = True
    torch.backends.cudnn.benchmark = False
    try:
        torch.use_deterministic_algorithms(True, warn_only=True)
    except (TypeError, AttributeError):
        pass


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--epochs", type=int, default=30)
    parser.add_argument("--seed", type=int, default=20260922)
    parser.add_argument("--patience", type=int, default=5, help="Early-stopping patience on validation loss.")
    parser.add_argument("--amp", action="store_true", help="Optional mixed precision (CUDA only).")
    args = parser.parse_args()

    index_path = ROOT / "data" / "datasets" / "final" / "index.csv"
    if not index_path.exists():
        blocked("data/datasets/final/index.csv does not exist; build known-label event-split sequences first.")
    import torch
    from models.historical_multitask import HistoricalMultiTaskNet
    set_determinism(args.seed)

    with index_path.open(encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    if not rows:
        blocked("final dataset index is empty.")

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    train_rows = [row for row in rows if row["split"] == "train"]
    validation_rows = [row for row in rows if row["split"] == "validation"]
    if not train_rows or not validation_rows:
        blocked("event-based train and validation splits must both contain samples.", train_samples=len(train_rows), validation_samples=len(validation_rows))

    first = np.load(ROOT / train_rows[0]["input_path"], allow_pickle=False)
    channels = int(first["inputs"].shape[1])
    if not np.isfinite(first["inputs"]).all():
        blocked("sequence inputs contain missing values; fit documented training-only imputation before training.")

    # Loss weighting is derived from the actual training-label imbalance (focal loss
    # plus a positive-class weight from observed frequencies).
    positives = 0
    known = 0
    for row in train_rows:
        targets = np.load(ROOT / row["target_path"], allow_pickle=False)["targets"]
        finite = np.isfinite(targets)
        known += int(finite.sum())
        positives += int((targets[finite] > 0.5).sum())
    pos_fraction = positives / known if known else 0.0
    pos_weight = min(20.0, (1.0 - pos_fraction) / max(pos_fraction, 1e-6)) if positives else 1.0

    model = HistoricalMultiTaskNet(channels).to(device)
    optimizer = torch.optim.AdamW(model.parameters(), lr=1e-4, weight_decay=1e-5)
    use_amp = bool(args.amp and device.type == "cuda")
    scaler = torch.cuda.amp.GradScaler(enabled=use_amp)

    best_loss = float("inf")
    epochs_without_improvement = 0
    history: list[dict] = []
    checkpoint_dir = ROOT / "models" / "checkpoints"
    checkpoint_dir.mkdir(parents=True, exist_ok=True)

    def batches(items):
        for start in range(0, len(items), 2):
            group = items[start:start + 2]
            inputs = np.stack([np.load(ROOT / row["input_path"], allow_pickle=False)["inputs"] for row in group])
            targets = np.stack([np.load(ROOT / row["target_path"], allow_pickle=False)["targets"] for row in group])
            yield torch.from_numpy(inputs).to(device), torch.from_numpy(targets).to(device)

    for epoch in range(1, args.epochs + 1):
        model.train()
        epoch_losses = []
        for inputs, targets in batches(train_rows):
            optimizer.zero_grad(set_to_none=True)
            known_mask = torch.isfinite(targets)
            with torch.cuda.amp.autocast(enabled=use_amp):
                loss = focal_loss(model(inputs), targets, known_mask, pos_weight=pos_weight)
            scaler.scale(loss).backward()
            scaler.step(optimizer)
            scaler.update()
            epoch_losses.append(loss.item())
        model.eval()
        with torch.inference_mode():
            val_losses, val_brier = [], []
            for inputs, targets in batches(validation_rows):
                known_mask = torch.isfinite(targets)
                logits = model(inputs)
                val_losses.append(focal_loss(logits, targets, known_mask, pos_weight=pos_weight).item())
                probabilities = torch.nan_to_num(torch.sigmoid(logits))
                clean = torch.nan_to_num(targets)
                val_brier.append((((probabilities - clean) ** 2) * known_mask).sum().item() / known_mask.sum().clamp_min(1.0).item())
        validation_loss = float(np.mean(val_losses))
        validation_brier = float(np.mean(val_brier))
        history.append({"epoch": epoch, "train_loss": float(np.mean(epoch_losses)), "validation_loss": validation_loss, "validation_brier": validation_brier})
        if validation_loss < best_loss:
            best_loss = validation_loss
            epochs_without_improvement = 0
            torch.save({"model": model.state_dict(), "input_channels": channels, "validation_loss": best_loss, "epoch": epoch, "seed": args.seed}, checkpoint_dir / "best.pt")
        else:
            epochs_without_improvement += 1
            if epochs_without_improvement >= args.patience:
                break

    (checkpoint_dir / "training_metadata.json").write_text(json.dumps({"device": str(device), "amp": use_amp, "input_channels": channels, "best_validation_loss": best_loss, "seed": args.seed, "patience": args.patience, "epochs_run": len(history), "early_stopped": len(history) < args.epochs, "label_pos_fraction": pos_fraction, "pos_weight": pos_weight, "history": history}, indent=2), encoding="utf-8")
    print(json.dumps({"status": "trained", "device": str(device), "epochs_run": len(history), "best_validation_loss": best_loss}, indent=2))


if __name__ == "__main__":
    main()