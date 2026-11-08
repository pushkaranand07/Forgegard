"""
Retrain the image model (IMDModel, ELA + CNN) on the CASIA v2 train split.

    python scripts/train_image.py --data eval/data/casia2 --out weights/model_c2.pth

Data: scripts/prepare_casia.py (JPEG-origin images only, split by source image).
Inputs are computed by core.pipeline.ela exactly as the service computes them
(ela_image + to_model_input), so training and serving cannot drift apart.

Protocol, fixed before any result was seen:
  * train on "train"; pick the epoch with the best AUC on "val" (early stopping);
  * calibrate on "val" with temperature scaling, folded into the last layer, so
    the checkpoint keeps the exact IMDModel state_dict and the service code is
    unchanged;
  * "test" is never read here. Evaluate once with scripts/eval_image.py
    --split test, and on the Kodak splice set. The model may be marked
    validated only if it passes the validation rule on both.

Class order matches the deployed model: index 0 = tampered, 1 = authentic.
Writes the weights and eval/results/<stem>-train-<date>.json (settings, data hash,
per-epoch metrics, temperature). Seeded; CPU results are reproducible on the same machine.
"""

from __future__ import annotations

import argparse
import csv
import datetime as dt
import hashlib
import json
import os
import sys
import time
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

SEED = 20261108


def model_input_uint8(path: str) -> np.ndarray:
    """The service's model input for one image, stored as uint8 (exact: values are k/255)."""
    from core.pipeline import ela
    from core.pipeline.safe_image import open_untrusted

    p = Path(path)
    img = open_untrusted(p, p.suffix.lstrip(".")).convert("RGB")
    x = ela.to_model_input(ela.ela_image(img))[0].numpy()
    return np.rint(x * 255.0).astype(np.uint8)


def load_split(data: Path, rows: list[dict], name: str, workers: int) -> tuple[np.ndarray, np.ndarray]:
    sel = [r for r in rows if r["split"] == name]
    with ProcessPoolExecutor(workers) as pool:
        xs = list(pool.map(model_input_uint8, [str(data / r["file"]) for r in sel], chunksize=32))
    return np.stack(xs), np.array([int(r["label"]) for r in sel], dtype=np.int64)


def auc(scores: np.ndarray, labels: np.ndarray) -> float:
    pos, neg = scores[labels == 1], scores[labels == 0]
    order = np.argsort(np.concatenate([pos, neg]), kind="mergesort")
    ranks = np.empty(len(order))
    allv = np.concatenate([pos, neg])[order]
    # average ranks for ties
    i = 0
    while i < len(allv):
        j = i
        while j + 1 < len(allv) and allv[j + 1] == allv[i]:
            j += 1
        ranks[order[i:j + 1]] = (i + j) / 2 + 1
        i = j + 1
    return float((ranks[: len(pos)].sum() - len(pos) * (len(pos) + 1) / 2) / (len(pos) * len(neg)))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.strip().splitlines()[0])
    parser.add_argument("--data", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--epochs", type=int, default=40)
    parser.add_argument("--patience", type=int, default=8)
    parser.add_argument("--batch-size", type=int, default=64)
    parser.add_argument("--lr", type=float, default=1e-4)
    parser.add_argument("--weight-decay", type=float, default=1e-4)
    parser.add_argument("--seed", type=int, default=SEED)
    parser.add_argument("--workers", type=int, default=os.cpu_count() or 4)
    args = parser.parse_args()

    import django

    django.setup()
    import torch
    from torch import nn

    from core.pipeline.image_processor import IMDModel

    torch.manual_seed(args.seed)
    rng = np.random.default_rng(args.seed)
    torch.set_num_threads(args.workers)

    labels_csv = args.data / "labels.csv"
    with labels_csv.open(encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    t0 = time.time()
    x_train, y_train = load_split(args.data, rows, "train", args.workers)
    x_val, y_val = load_split(args.data, rows, "val", args.workers)
    print(f"inputs computed in {time.time() - t0:.0f}s: train {len(y_train)} ({y_train.sum()} tampered), "
          f"val {len(y_val)} ({y_val.sum()} tampered)", flush=True)

    def tensor(x: np.ndarray) -> torch.Tensor:
        # to_model_input's numpy transpose leaves channels-last strides, which the cached
        # arrays keep; IMDModel.forward uses .view(), so batches must be NCHW-contiguous.
        return torch.from_numpy(np.ascontiguousarray(x)).float().div_(255.0)

    # target index: 0 = tampered, 1 = authentic
    t_train = torch.from_numpy(1 - y_train)
    counts = np.bincount(1 - y_train, minlength=2)
    class_weight = torch.tensor(len(y_train) / (2.0 * counts), dtype=torch.float32)
    loss_fn = nn.CrossEntropyLoss(weight=class_weight)

    model = IMDModel()
    opt = torch.optim.Adam(model.parameters(), lr=args.lr, weight_decay=args.weight_decay)

    def val_logits(m: nn.Module) -> torch.Tensor:
        m.eval()
        with torch.no_grad():
            return torch.cat([m(tensor(x_val[i:i + 256])) for i in range(0, len(x_val), 256)])

    history, best = [], {"auc": -1.0, "epoch": 0, "state": None}
    for epoch in range(1, args.epochs + 1):
        model.train()
        perm = rng.permutation(len(y_train))
        losses = []
        for i in range(0, len(perm), args.batch_size):
            idx = perm[i:i + args.batch_size]
            xb = tensor(x_train[idx])
            # augmentation: random horizontal / vertical flips (ELA has no orientation)
            flip_h = torch.from_numpy(rng.random(len(idx)) < 0.5)
            flip_v = torch.from_numpy(rng.random(len(idx)) < 0.5)
            xb[flip_h] = xb[flip_h].flip(-1)
            xb[flip_v] = xb[flip_v].flip(-2)
            opt.zero_grad()
            loss = loss_fn(model(xb), t_train[idx])
            loss.backward()
            opt.step()
            losses.append(loss.item())
        p_tampered = torch.softmax(val_logits(model), 1)[:, 0].numpy()
        val_auc = auc(p_tampered, y_val)
        history.append({"epoch": epoch, "train_loss": float(np.mean(losses)), "val_auc": val_auc})
        print(f"epoch {epoch:2d}  loss {np.mean(losses):.4f}  val AUC {val_auc:.4f}", flush=True)
        if val_auc > best["auc"]:
            best = {"auc": val_auc, "epoch": epoch,
                    "state": {k: v.detach().clone() for k, v in model.state_dict().items()}}
        elif epoch - best["epoch"] >= args.patience:
            print(f"early stop: no val improvement for {args.patience} epochs", flush=True)
            break

    model.load_state_dict(best["state"])

    # Temperature scaling on val (minimise NLL over a fine grid; one parameter, no overfitting risk)
    logits = val_logits(model)
    targets = torch.from_numpy(1 - y_val)
    nll = nn.CrossEntropyLoss()
    temps = np.exp(np.linspace(np.log(0.05), np.log(20.0), 600))
    losses_t = [nll(logits / t, targets).item() for t in temps]
    temperature = float(temps[int(np.argmin(losses_t))])
    with torch.no_grad():
        last = model.linear[-1]
        last.weight.div_(temperature)
        last.bias.div_(temperature)
    check = val_logits(model)
    assert torch.allclose(check, logits / temperature, atol=1e-4), "temperature fold-in changed the logits"

    args.out.parent.mkdir(parents=True, exist_ok=True)
    torch.save(model.state_dict(), args.out)
    weights_sha = hashlib.sha256(args.out.read_bytes()).hexdigest()
    report = {
        "date": dt.date.today().isoformat(),
        "weights": args.out.name,
        "weights_sha256": weights_sha,
        "data": str(args.data.as_posix()),
        "labels_csv_sha256": hashlib.sha256(labels_csv.read_bytes()).hexdigest(),
        "settings": {k: v for k, v in vars(args).items() if k not in ("data", "out", "workers")},
        "n_train": len(y_train), "n_train_tampered": int(y_train.sum()),
        "n_val": len(y_val), "n_val_tampered": int(y_val.sum()),
        "best_epoch": best["epoch"], "best_val_auc": best["auc"],
        "temperature": temperature,
        "val_nll_before_after": [nll(logits, targets).item(), min(losses_t)],
        "history": history,
        "note": "Selection and calibration used val only; the test split was not read.",
    }
    report_path = ROOT / "eval" / "results" / f"{args.out.stem}-train-{report['date']}.json"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(f"best epoch {best['epoch']} (val AUC {best['auc']:.4f}); temperature {temperature:.3f}; "
          f"wrote {args.out} (sha256 {weights_sha[:12]}…) and {report_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
