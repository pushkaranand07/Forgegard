# Model Cards

ForgeGuard serves two models, each documented below. Metrics are filled in only from committed evaluation reports under `reports/`. Until those exist, every metric reads "not yet evaluated".

---

## 1. Video face-swap classifier (DFDC EfficientNet-B7)

| | |
|---|---|
| **File** | `weights/deepfake_detector_b7.pth` (SHA-256 `9fe4311d551a…`) |
| **Source** | Selim Seferbekov, [DFDC 1st-place solution](https://github.com/selimsef/dfdc_deepfake_challenge), release `0.0.1`. **Third-party pretrained weights, not trained or fine-tuned in this project.** |
| **License** | Code: MIT. Weights: trained on DFDC, so DFDC's non-commercial research terms apply. |
| **Architecture** | `tf_efficientnet_b7.ns_jft_in1k` encoder (timm) → global average pool → linear layer → 1 logit. sigmoid(logit) = P(fake) for one face crop. |
| **Input** | RGB face crop from MTCNN with one-third padding, isotropically resized to 380 px, centre zero-padded, ImageNet-normalised. |
| **Training data** | DFDC training set (upstream). Checkpoint metadata: epoch 30, upstream best validation BCE 0.1668 on the author's own split. That figure isn't a ForgeGuard measurement. |
| **Video-level output** | Per-face scores from 32 sampled frames, aggregated with upstream `confident_strategy`. No face detected → `UNSURE`. |

**Intended use:** research, education and demonstration of face-swap detection on short videos with clearly visible frontal faces.

**Out of scope:**
- Any decision about a real person: moderation, legal, employment, journalism verdicts.
- Commercial use (dataset terms).
- Audio deepfakes, fully synthetic or diffusion-generated video, lip-sync edits, face reenactment.
- Videos without visible faces.

**Metrics:**

| Evaluation | Result |
|---|---|
| Celeb-DF v2 official test list (out of distribution) | not yet evaluated |
| DFDC held-out subset (in distribution) | not yet evaluated |
| Calibration (ECE) | not yet evaluated |
| Latency, CPU | ~20–25 s per 32-face video (manual measurement, not yet scripted) |

**Known failure modes and limitations:**
- Only the highest-confidence face per frame is classified. Upstream classifies all faces, so a manipulated secondary face can be missed.
- A single checkpoint is used where upstream averaged an ensemble. Upstream's competition results don't transfer.
- Trained on 2019–2020 face-swap methods, so expect lower accuracy on newer generators. DFDC-trained detectors are widely reported to lose accuracy on other datasets.
- 32 frames are sampled regardless of length, so coverage is sparse on long videos.
- Scores are uncalibrated. The UI's "confidence" is `max(p, 1 − p)`.

---

## 2. Image splicing classifier (ELA + `IMDModel`)

| | |
|---|---|
| **File** | `weights/model_c1.pth` (SHA-256 `b6b76a422a82…`, a `state_dict` converted from the original pickled module `5839a0d90084…` with bit-identical outputs) |
| **Source** | Trained by the project author in `training/notebooks/train.ipynb`. Architecture adapted from public code (source URL pending, see [CREDITS.md](CREDITS.md)). |
| **Architecture** | Two conv blocks (3→64→16 channels, 3×3, BN, maxpool, ReLU) → MLP 14400→1024→64→2 (ReLU, no BN) → logits; softmax is applied at inference. Index 0 = tampered, 1 = authentic. This is the architecture stored in the deployed checkpoint, which differs from the notebook's current cell. |
| **Input** | ELA map: the image re-saved as JPEG at quality 90, absolute difference ×10, resized to 128×128, scaled to [0, 1]. |
| **Training data** | 1,721 CASIA images (count consistent with CASIA v1.0), unseeded random split 1000/500/221. ELA maps were precomputed by a script that isn't in the project. |
| **Also reported** | EXIF/PNG `Software` tag as a separate, weak metadata hint. Not used by the CNN. |

**Intended use:** research and education on splicing detection in JPEG photos.

**Out of scope:**
- **AI-generated images (not detected).**
- PNG and other lossless sources (ELA isn't meaningful).
- Social-media or otherwise re-encoded images.
- Any decision about real people or events.
- Commercial use.

**Metrics:**

| Evaluation | Result |
|---|---|
| CASIA, seeded held-out split, with 95 % CI | not yet evaluated |
| Cross-dataset | not yet evaluated |
| Recompression stress test (JPEG q70, 50 % resize) | not yet evaluated |
| Calibration (ECE) | not yet evaluated |

The notebook printed 0.827 and 0.937 test accuracy. Neither is used here: the split was unseeded and the 0.937 checkpoint was likely scored on images it had trained on. See [docs/training_methodology.md](docs/training_methodology.md).

**Known failure modes and limitations:**
- Small, single-source training set; heavy overfitting was visible in training (train loss 0.0009 vs test loss 0.71).
- ELA signal is destroyed by re-encoding and resizing.
- It's unverified whether the training-time ELA parameters match inference.
- Phone firmware writes the EXIF `Software` tag, so the metadata hint produces false positives on unedited phone photos.

---

## Ethical considerations (both models)

- **A wrong FAKE verdict on a real person's video or photo can cause real harm** (reputation, harassment). Results are model outputs, not evidence. The UI and API should present them with uncertainty and a disclaimer.
- Uploads may contain faces, which is personal data. By default ForgeGuard analyses uploads from a scratch file and deletes it afterwards (`FORGEGUARD_KEEP_UPLOADS=false`).
- The datasets' demographic composition hasn't been audited in this project, and performance across demographic groups hasn't been measured.
