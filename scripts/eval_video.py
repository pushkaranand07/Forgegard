"""
Evaluate the video model on a labelled set of clips.

    python scripts/eval_video.py --data eval/data/faceswap
    python scripts/eval_video.py --rescore eval/results/<file>.json   # new rule, saved scores

The data directory holds clips plus labels.csv (file, label) with 1 = fake,
0 = real; scripts/make_faceswap_set.py builds one from your own videos.

Each clip runs through exactly what the service runs
(core.pipeline.video_processor.detect_video_file). Every per-face score is saved,
so changes to the aggregation rule can be re-scored without re-running the model.

Reported for both the current rule (verdict only on consensus, else UNSURE) and
the old rule (verdict = aggregated score >= 0.5): accuracy among decided clips,
how many real and fake clips were wrongly decided, how many came back UNSURE, and
ROC AUC of the aggregated score with a bootstrap 95% interval.
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

from scripts.eval_image import bootstrap_auc_ci, roc_auc  # noqa: E402


def score_rules(clips: list[dict]) -> dict:
    from core.pipeline import video_processor as vp

    def rule_report(decision):
        decided = [(c["label"], decision(c)) for c in clips if c["faces"]]
        verdicts = [(y, d) for y, d in decided if d != "UNSURE"]
        wrong_real = sum(1 for y, d in verdicts if y == 0 and d == "FAKE")
        wrong_fake = sum(1 for y, d in verdicts if y == 1 and d == "REAL")
        correct = sum(1 for y, d in verdicts if (d == "FAKE") == (y == 1))
        return {
            "decided": len(verdicts),
            "unsure": sum(1 for _, d in decided if d == "UNSURE"),
            "no_face": sum(1 for c in clips if not c["faces"]),
            "accuracy_when_decided": correct / len(verdicts) if verdicts else None,
            "real_clips_called_fake": wrong_real,
            "fake_clips_called_real": wrong_fake,
        }

    def new_rule(c):
        return vp.decide(c["face_scores"])[0]

    def old_rule(c):
        return "FAKE" if vp.confident_strategy(c["face_scores"]) >= 0.5 else "REAL"

    with_scores = [c for c in clips if c["faces"]]
    s = np.array([vp.confident_strategy(c["face_scores"]) for c in with_scores])
    y = np.array([c["label"] for c in with_scores])
    auc = roc_auc(s, y) if len(set(y)) == 2 else None
    return {
        "consensus_rule": rule_report(new_rule),
        "old_threshold_rule": rule_report(old_rule),
        "auc_aggregated_score": auc,
        "auc_95ci": bootstrap_auc_ci(s, y) if auc is not None else None,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.strip().splitlines()[0])
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--data", type=Path)
    group.add_argument("--rescore", type=Path, help="re-score a saved results file with the current rule")
    parser.add_argument("--weights", type=Path, default=ROOT / "weights" / "deepfake_detector_b7.pth")
    parser.add_argument("--out", type=Path, default=ROOT / "eval" / "results")
    args = parser.parse_args()

    import django

    django.setup()

    if args.rescore:
        results = json.loads(args.rescore.read_text(encoding="utf-8"))
        results.update(score_rules(results["clips"]))
        out_file = args.rescore
    else:
        from core.pipeline import video_processor as vp

        with (args.data / "labels.csv").open(encoding="utf-8") as f:
            rows = list(csv.DictReader(f))
        clips = []
        for row in rows:
            r = vp.detect_video_file(str(args.data / row["file"]), str(args.weights), device="cpu")
            clips.append({"file": row["file"], "label": int(row["label"]), "service_label": r.label,
                          "faces": len(r.frame_predictions), "face_scores": [round(float(x), 5) for x in
                                                                             r.frame_predictions],
                          "notes": list(r.notes)})
            print(f"{row['file']}: label {row['label']} -> {r.label} ({len(r.frame_predictions)} faces)", flush=True)
        h = hashlib.sha256(args.weights.read_bytes()).hexdigest()
        results = {"dataset": args.data.name, "n_clips": len(clips), "n_fake": sum(c["label"] for c in clips),
                   "weights": args.weights.name, "weights_sha256": h, "date": dt.date.today().isoformat(),
                   "clips": clips}
        results.update(score_rules(clips))
        args.out.mkdir(parents=True, exist_ok=True)
        out_file = args.out / f"{args.weights.stem}-{args.data.name}-{results['date']}.json"

    out_file.write_text(json.dumps(results, indent=2) + "\n", encoding="utf-8")

    print(f"\n## {results['weights']} on {results['dataset']} ({results['n_clips']} clips, {results['n_fake']} fake)\n")
    print("| Rule | Decided | UNSURE | No face | Accuracy when decided | Real called fake | Fake called real |")
    print("|---|---|---|---|---|---|---|")
    for name, key in (("Consensus (current)", "consensus_rule"), ("Score >= 0.5 (old)", "old_threshold_rule")):
        r = results[key]
        acc = f"{r['accuracy_when_decided']:.3f}" if r["accuracy_when_decided"] is not None else "n/a"
        print(f"| {name} | {r['decided']} | {r['unsure']} | {r['no_face']} | {acc} | "
              f"{r['real_clips_called_fake']} | {r['fake_clips_called_real']} |")
    if results["auc_aggregated_score"] is not None:
        lo, hi = results["auc_95ci"]
        print(f"\nAUC of the aggregated score: {results['auc_aggregated_score']:.3f} ({lo:.3f}-{hi:.3f})")
    print(f"Written to {out_file.relative_to(ROOT) if out_file.is_relative_to(ROOT) else out_file}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
