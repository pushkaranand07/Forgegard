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
harder. For CASIA v2 results see [Retraining on CASIA v2](#retraining-on-casia-v2-phase-3c-still-not-validated).

### Why the model may be at chance

The training notebook (`training/notebooks/train.ipynb`) consumes ELA images produced by
a script that is not in the repository, so the training-time ELA parameters (JPEG
quality, scaling, resize order) cannot be checked against inference. The notebook's
train/test split also has no seed. ELA now lives in one module,
[`core/pipeline/ela.py`](../core/pipeline/ela.py), so any retraining uses exactly the
inference code.

The retraining below rules this out as the main cause: a model trained on exactly
the inference ELA also fails on Kodak.

### Retraining on CASIA v2 (phase 3c): still not validated

```bash
# CASIA2.0-*.tar shards from huggingface.co/datasets/ductai199x/image-manipulation-dataset-compilation,
# checked against their LFS SHA-256 (the data is not redistributed here)
python scripts/prepare_casia.py --src eval/data/casia2-src --out eval/data/casia2
python scripts/train_image.py --data eval/data/casia2 --out weights/model_c2.pth
python scripts/eval_image.py --data eval/data/casia2 --split test --weights weights/model_c2.pth
python scripts/eval_image.py --data eval/data/kodak-splice --weights weights/model_c2.pth
```

**Data.**
- **JPEG-origin images only, in both classes.** CASIA v2 has a format shortcut: 99.3% of authentic images are JPEG, but 60% of tampered ones are TIFF. That leaves 7,437 authentic and 2,064 tampered images.
- **Split by source image.** Each tampered image names the one or two authentic images it was built from. Tampered images and their sources are grouped by connected components, and whole groups go to train, val or test. No source picture appears in two splits.
- **One large chain.** Shared sources chain 1,340 of the tampered images into one component, and it goes to train. The remaining groups are dealt out so val and test each get about 15% of each class.
- **Split sizes:**
  - train: 5,206 authentic / 1,445 tampered
  - val: 1,116 / 310
  - test: 1,115 / 309
- **Format of this mirror.** It stores every image re-saved losslessly as PNG, so the model sees the original JPEG's decoded pixels, but not the original JPEG files.

**Protocol (fixed before any result was seen).**
- Train on train.
- Pick the epoch by val AUC (early stopping).
- Calibrate on val by temperature scaling, folded into the last layer so the checkpoint is a plain IMDModel `state_dict`.
- Evaluate on test once.
- Pass criterion: the validation rule on both the CASIA test split and the Kodak set.

**Training run.**
- Best epoch 17 of 25 (early stop), val AUC 0.970, temperature 1.41.
- Report: [`eval/results/model_c2-train-2026-11-08.json`](../eval/results/model_c2-train-2026-11-08.json)

| Model | CASIA v2 test (1,424; 309 tampered) | Kodak splice set (96; 48 tampered) |
|---|---|---|
| `model_c2.pth` (retrained) | AUC **0.962** (0.952–0.971), ECE 0.020 | AUC **0.576** (0.460–0.685), ECE 0.213 |
| `model_c1.pth` (deployed) | AUC 0.780 (0.750–0.809)† | AUC 0.619 (0.500–0.728) |
| Mean-ELA baseline | AUC 0.714 (0.685–0.742) | AUC 0.566 (0.448–0.686) |

†`model_c1` was trained on an unrecorded CASIA-style subset with an unseeded split, so
some of these test images may have been in its training data. Its CASIA number is an
upper bound, not a held-out result.

Result files: `eval/results/model_c2-casia2-test-2026-11-08.json`,
`model_c2-kodak-splice-2026-11-08.json`, `model_c1-casia2-test-2026-11-08.json`.

**Verdict: fails the criterion.**
- On CASIA's own test split it is strong and well calibrated.
- On Kodak splices it is indistinguishable from chance: its interval includes 0.5, and calibration does not transfer (ECE 0.21).
- So it learned cues specific to CASIA, not splicing in general.

The likeliest cue is JPEG history. CASIA's tampered images were saved with different
compression from the camera originals, and even mean ELA, a heuristic with no learning,
reaches 0.714 on CASIA. Other differences also exist: image size, for example, with
portrait 256×384 at 25% of authentic images vs 10% of tampered ones. This was not
isolated further.

Kodak is small (96 images), so its intervals are wide. A passing model would need an
interval clearly above 0.566, and this one is centred at 0.576.

`model_c2.pth` is not deployed. Its hash is in the manifest so these results can be
reproduced, with `validated: false` and no download URL. The service still uses
`model_c1.pth` and gives no image verdict.

**What would be needed:**
- Training data whose two classes share the same compression history: for example, splices generated from the same camera JPEGs and re-saved identically, as in the Kodak recipe but at scale and with realistic blending.
- Or a detector designed for this task rather than a 2-layer CNN on 128×128 ELA, which discards most of the spatial detail at that resize.

## Video model (`deepfake_detector_b7.pth`): indicative results only

```bash
python scripts/make_faceswap_set.py --videos <folder of real videos> --out eval/data/faceswap
python scripts/eval_video.py --data eval/data/faceswap
python scripts/eval_video.py --rescore eval/results/<file>.json   # re-score saved per-face scores
```

Result file: [`eval/results/deepfake_detector_b7-faceswap-2026-11-08.json`](../eval/results/deepfake_detector_b7-faceswap-2026-11-08.json)
(per-face scores for every clip; no imagery).

**Verdict rule (since phase 3b).** A video gets REAL or FAKE only when its per-face scores
agree, using the same consensus upstream's `confident_strategy` uses to pick its branch:
FAKE needs more than 11 confidently fake faces (score > 0.8) and more than n / 2.5 of
them; REAL needs more than 90% of faces confidently real (< 0.2). Otherwise the result is
`UNSURE` (`NO_CONSENSUS`); fewer than 8 faces gives `UNSURE` (`TOO_FEW_FACES`). These
thresholds are upstream's own, and the 8-face minimum was fixed before this evaluation;
nothing was tuned on this set.

**Set:** 17 clips from 4 real talking-head videos available locally to the developer (not shipped): 8
real 4 s segments, the same 8 segments with the face swapped (MTCNN + seamless clone, the
audit's recipe), and one full-length real video.

| Rule | Verdicts | UNSURE | Accuracy when a verdict is given | Real called fake | Fake called real |
|---|---|---|---|---|---|
| Consensus (current) | 10 | 7 | 0.900 | 1 | 0 |
| Aggregated score ≥ 0.5 (before) | 17 | 0 | 0.765 | 2 | 2 |

AUC of the aggregated score: 0.889 (95% CI 0.697–1.000).

**What this does and does not show.** Requiring consensus turned 3 of the 4 wrong verdicts
into UNSURE, at the price of no verdict for 7 of 17 clips. The set is tiny and the swaps
are crude (visible blending, unlike DFDC or Celeb-DF fakes), so these numbers are an upper
bound and not a benchmark; Celeb-DF v2 / FaceForensics++ results are still pending (they
require access requests).

### Known failure mode: face filters

The remaining false accusation is a real person whose face has strong skin smoothing (a
beauty filter): 26 of 32 faces scored above 0.8. A face-manipulation detector reacting to
face processing is arguably not wrong, but it is not a face swap. Treat FAKE on footage
that may have been beautified or heavily edited with particular caution.

### Investigation notes

On the real clip that previously scored FAKE at 0.534, face detection was clean (detector
confidence ≈ 1.0, one 265–325 px face per frame), but per-face scores swung between 0.02
and 0.98 on near-identical consecutive frames, with no visible cause in the crops. The
model sits on its decision boundary for that footage; the honest output is UNSURE.
