"""
Evaluate the image model against the mean-ELA baseline on a labelled set.

    python scripts/eval_image.py --data eval/data/kodak-splice [--weights weights/model_c1.pth]

The data directory holds JPEGs plus labels.csv (file, label[, variant]) with
label 1 = tampered, 0 = authentic; scripts/make_splice_set.py builds one.

Each image is scored by exactly what the service computes
(core.pipeline.image_processor.tampering_score) and by the no-model baseline
(core.pipeline.ela.mean_ela). Reported per scorer: ROC AUC with a bootstrap 95%
interval, balanced accuracy, and for the model, expected calibration error
(ECE). Results are written to eval/results/<model>-<dataset>-<date>.json and
printed as Markdown.

Validation rule (conservative, used by "model_clearly_beats_baseline"): the
model's AUC 95% interval must lie entirely above both 0.5 and the baseline's
AUC. A point estimate that is higher but inside the noise does not count. Only
a model that passes on a held-out set may be marked "validated" in
core/model_manifest.json.
"""

from __future__ import annotations

import argparse
import csv
import datetime as dt
import hashlib
import json
import os
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")


def roc_auc(scores: np.ndarray, labels: np.ndarray) -> float:
    """Probability that a random tampered image outscores a random authentic one (ties count half)."""
    pos, neg = scores[labels == 1], scores[labels == 0]
    if len(pos) == 0 or len(neg) == 0:
        return float("nan")
    greater = (pos[:, None] > neg[None, :]).sum()
    ties = (pos[:, None] == neg[None, :]).sum()
    return float((greater + 0.5 * ties) / (len(pos) * len(neg)))


def bootstrap_auc_ci(scores, labels, n=2000, seed=0) -> tuple[float, float]:
    rng = np.random.default_rng(seed)
    values = []
    for _ in range(n):
        idx = rng.integers(0, len(scores), len(scores))
        if labels[idx].min() == labels[idx].max():
            continue
        values.append(roc_auc(scores[idx], labels[idx]))
    lo, hi = np.percentile(values, [2.5, 97.5])
    return float(lo), float(hi)


def balanced_accuracy(pred: np.ndarray, labels: np.ndarray) -> float:
    tpr = (pred[labels == 1] == 1).mean()
    tnr = (pred[labels == 0] == 0).mean()
    return float((tpr + tnr) / 2)


def best_threshold(scores, labels) -> tuple[float, float]:
    """Threshold maximising balanced accuracy ON THIS SET (optimistic: for comparison only)."""
    best = (0.0, float(np.median(scores)))
    for t in np.unique(scores):
        acc = balanced_accuracy((scores >= t).astype(int), labels)
        if acc > best[0]:
            best = (acc, float(t))
    return best


def ece(probs: np.ndarray, labels: np.ndarray, bins: int = 10) -> float:
    """Expected calibration error of P(tampered), with the predicted class's confidence."""
    pred = (probs >= 0.5).astype(int)
    conf = np.where(pred == 1, probs, 1 - probs)
    correct = (pred == labels).astype(float)
    edges = np.linspace(0.5, 1.0, bins + 1)
    total = 0.0
    for lo, hi in zip(edges[:-1], edges[1:]):
        mask = (conf >= lo) & ((conf < hi) if hi < 1.0 else (conf <= hi))
        if mask.any():
            total += mask.mean() * abs(conf[mask].mean() - correct[mask].mean())
    return float(total)


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.strip().splitlines()[0])
    parser.add_argument("--data", type=Path, required=True)
    parser.add_argument("--weights", type=Path, default=ROOT / "weights" / "model_c1.pth")
    parser.add_argument("--out", type=Path, default=ROOT / "eval" / "results")
    args = parser.parse_args()

    import django

    django.setup()
    import torch

    from core.pipeline import ela, image_processor
    from core.pipeline.safe_image import open_untrusted

    with (args.data / "labels.csv").open(encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    device = torch.device("cpu")

    model_scores, baseline_scores, labels, variants = [], [], [], []
    for row in rows:
        img = open_untrusted(args.data / row["file"], "jpg").convert("RGB")
        model_scores.append(image_processor.tampering_score(img, str(args.weights), device))
        baseline_scores.append(ela.mean_ela(img))
        labels.append(int(row["label"]))
        variants.append(row.get("variant", "all").rsplit("_", 1)[-1] if row.get("variant") else "all")
    m, b, y = np.array(model_scores), np.array(baseline_scores), np.array(labels)
    v = np.array(variants)

    def summary(scores, threshold=None):
        out = {"auc": roc_auc(scores, y), "auc_95ci": bootstrap_auc_ci(scores, y)}
        if threshold is not None:
            out["balanced_accuracy_at_0.5"] = balanced_accuracy((scores >= threshold).astype(int), y)
        acc, t = best_threshold(scores, y)
        out["balanced_accuracy_best_threshold_optimistic"] = acc
        out["best_threshold"] = t
        out["by_variant_auc"] = {k: roc_auc(scores[v == k], y[v == k]) for k in sorted(set(variants))}
        return out

    results = {
        "dataset": args.data.name,
        "n_images": int(len(y)),
        "n_tampered": int(y.sum()),
        "weights": args.weights.name,
        "weights_sha256": sha256_file(args.weights),
        "date": dt.date.today().isoformat(),
        "model": {**summary(m, threshold=0.5), "ece": ece(m, y),
                  "mean_score_authentic": float(m[y == 0].mean()), "mean_score_tampered": float(m[y == 1].mean())},
        "baseline_mean_ela": summary(b),
    }
    lower = results["model"]["auc_95ci"][0]
    results["validation_rule"] = "model AUC 95% CI lower bound > max(0.5, baseline AUC)"
    results["model_clearly_beats_baseline"] = lower > max(0.5, results["baseline_mean_ela"]["auc"])

    args.out.mkdir(parents=True, exist_ok=True)
    out_file = args.out / f"{args.weights.stem}-{args.data.name}-{results['date']}.json"
    out_file.write_text(json.dumps(results, indent=2) + "\n", encoding="utf-8")

    mm, bb = results["model"], results["baseline_mean_ela"]
    print(f"## {results['weights']} on {results['dataset']} ({results['n_images']} images, "
          f"{results['n_tampered']} tampered)\n")
    print("| Scorer | AUC (95% CI) | Balanced acc. @0.5 | Balanced acc., best threshold (optimistic) | ECE |")
    print("|---|---|---|---|---|")
    print(f"| Model | {mm['auc']:.3f} ({mm['auc_95ci'][0]:.3f}-{mm['auc_95ci'][1]:.3f}) | "
          f"{mm['balanced_accuracy_at_0.5']:.3f} | {mm['balanced_accuracy_best_threshold_optimistic']:.3f} | {mm['ece']:.3f} |")
    print(f"| Mean-ELA baseline | {bb['auc']:.3f} ({bb['auc_95ci'][0]:.3f}-{bb['auc_95ci'][1]:.3f}) | n/a | "
          f"{bb['balanced_accuracy_best_threshold_optimistic']:.3f} | n/a |")
    print(f"\nAUC by variant, model: {', '.join(f'{k} {x:.3f}' for k, x in mm['by_variant_auc'].items())}; "
          f"baseline: {', '.join(f'{k} {x:.3f}' for k, x in bb['by_variant_auc'].items())}")
    print(f"Model clearly beats baseline ({results['validation_rule']}): {results['model_clearly_beats_baseline']}. "
          f"Written to {out_file.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
