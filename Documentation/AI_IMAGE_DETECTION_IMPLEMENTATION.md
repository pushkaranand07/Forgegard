# AI-Generated Image Detection Implementation

## 1) What changed in inference

The Django image pipeline now combines:

- Model-based fake probability from the existing ResNeXt+LSTM path
- Artifact-based signals from the input image:
  - FFT high-frequency ratio
  - Denoise residual noise level
  - Checkerboard/upscale inconsistency
  - Block/grid boundary inconsistency
  - Laplacian texture variance
- Per-image dynamic thresholding:
  - Starts from calibrated base threshold
  - Adjusts by uncertainty (entropy) and artifact score

New APIs:

- `POST /api/calibrate-image-threshold/`
- `GET /api/image-calibration-status/`

## 2) Validation data format for calibration

Use this folder structure:

```text
validation_set/
  real/
    *.jpg|*.jpeg|*.png|*.webp
  fake/          # or ai/ or generated/
    *.jpg|*.jpeg|*.png|*.webp
```

## 3) Calibrate threshold (no retraining)

Request:

```bash
curl -X POST http://127.0.0.1:8000/api/calibrate-image-threshold/ \
  -H "Content-Type: application/json" \
  -d "{\"validation_dir\":\"C:/datasets/validation_set\",\"sequence_length\":100,\"metric\":\"f1\",\"save\":true}"
```

Response contains:

- `image_fake_threshold`
- `metric_used`, `metric_value`
- full confusion metrics (`tp`, `fp`, `tn`, `fn`, `f1`, `youden_j`, etc.)
- `config_path` if saved

## 4) Check active calibration

```bash
curl http://127.0.0.1:8000/api/image-calibration-status/
```

The active base threshold is loaded from:

- `calibration/image_threshold_config.json`

## 5) Fine-tuning for real vs AI-generated images

Use script:

- `Model Creation/train_image_artifact_finetune.py`

Expected dataset:

```text
data/ai_image_detection/
  train/real
  train/fake
  val/real
  val/fake
```

Run:

```bash
python "Model Creation/train_image_artifact_finetune.py" \
  --data_dir "data/ai_image_detection" \
  --epochs 10 \
  --batch_size 32 \
  --lr 1e-4
```

This script uses:

- RGB branch + artifact map branch (lightweight)
- BCE + focal-loss blend for imbalance/hard examples
- threshold sweep for best F1 and EER proxy

## 6) Recommended deployment flow

1. Fine-tune detector on mixed-source AI images (SD, DALL-E, Midjourney, GANs).
2. Evaluate on held-out generators and compression levels.
3. Run calibration endpoint on production-like validation data.
4. Save threshold config and deploy.
5. Recalibrate periodically when data distribution changes.

## 7) Optional: download GenImage quickly

Script:

- `Model Creation/download_genimage.py`

Examples:

```bash
# Download only (resumable Google Drive first, fallback HTTP)
python "Model Creation/download_genimage.py" --destination "./GenImage_download"

# Download + extract
python "Model Creation/download_genimage.py" --destination "./GenImage_download" --extract
```
