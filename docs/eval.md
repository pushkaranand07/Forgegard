# Model evaluation

Every number here comes from a committed script and can be regenerated. A model is
marked `"validated": true` in `core/model_manifest.json`, and gets to return an
AUTHENTIC/TAMPERED verdict, only if it passes the rule below on a held-out set.

**Validation rule:** the model's ROC AUC 95% bootstrap interval must lie entirely above
both 0.5 (chance) and the AUC of the no-model baseline (mean ELA intensity). A higher
point estimate inside the noise does not count.

## Image model (`model_c1.pth`, IMDModel on ELA): not validated

```bash
python scripts/make_splice_set.py --out eval/data/kodak-splice   # downloads Kodak, builds 96 images
python scripts/eval_image.py --data eval/data/kodak-splice
```

Result file: [`eval/results/model_c1-kodak-splice-2026-11-08.json`](../eval/results/model_c1-kodak-splice-2026-11-08.json)

| Scorer | AUC (95% CI) | Balanced accuracy @ 0.5 | Balanced accuracy, best threshold* | ECE |
|---|---|---|---|---|
| `model_c1.pth` | 0.619 (0.500–0.728) | 0.552 | 0.625 | 0.412 |
| Mean-ELA baseline (no model) | 0.566 (0.448–0.686) | n/a | 0.583 | n/a |

\*Threshold chosen on this same set, so optimistic; shown only for comparison.

| AUC by variant | Model | Baseline |
|---|---|---|
| Single compression (q92) | 0.587 | 0.540 |
| Double compression (q75 background, then q92) | 0.689 | 0.648 |

**Verdict: fails the rule.** The model's interval reaches 0.500, so it is not
distinguishable from chance, and it does not clearly beat a heuristic that uses no
model at all. It is also badly calibrated (ECE 0.41: it reports near-certain scores
that are right about half the time). This agrees with the November 2026 audit
(AUC 0.561 on a different 80-image set). The API therefore labels its results
`UNVALIDATED` and gives no verdict.

### The test set

`scripts/make_splice_set.py` builds it from the 24 lossless Kodak test images
(http://r0k.us/graphics/kodak/, described there as released by Eastman Kodak for
unrestricted use; downloaded at run time against pinned SHA-256 hashes, not stored in
git). For each base image it writes four JPEGs: authentic and spliced, each with single
(q92) and double (q75 then q92) compression; the splice is a seeded 180–320 px patch from
the next image. The audit used the same recipe on frames from other videos. The same
seed always produces byte-identical files.

**Limits of this set:** 96 images is small (hence the wide intervals). The splices are
naive copy-paste with no blending or resizing, so real-world manipulations are likely
harder. Results on CASIA v2 (re-encoded to avoid its format shortcut) are pending
phase 3b.

### Why the model may be at chance

The training notebook (`training/notebooks/train.ipynb`) consumes ELA images produced by
a script that is not in the repository, so the training-time ELA parameters (JPEG
quality, scaling, resize order) cannot be checked against inference. The notebook's
train/test split also has no seed. ELA now lives in one module,
[`core/pipeline/ela.py`](../core/pipeline/ela.py), so any retraining uses exactly the
inference code.

## Video model (`deepfake_detector_b7.pth`): not yet evaluated here

Upstream's DFDC results are for an ensemble, not this single checkpoint. Observations so
far: 15/16 correct on the audit's crude face swaps; real people scored FAKE at 0.987
(audit) and 0.534 (Phase 2 test clip). A video harness and a Celeb-DF / FaceForensics++
evaluation are pending phase 3b.
