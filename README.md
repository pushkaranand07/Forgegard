# ForgeGuard

ForgeGuard is a web-based deepfake/AI-image detection project. It provides:
- A Django backend with a UI for uploads.
- JSON API endpoints for programmatic inference.
- A calibration step that selects the best decision threshold using a labeled validation set.

## Features

- Upload a video or image and get a prediction (`REAL` vs `FAKE`) with confidence.
- Image detection API:
  - Multi-view inference (face-cropped + full-frame) with horizontal flip aggregation.
  - Artifact-aware adjustment using lightweight generation artifact heuristics.
- Threshold calibration API:
  - Sweeps candidate base thresholds over a labeled `real/` + `fake/` validation folder.
  - Persists the best threshold as `calibration/image_threshold_config.json`.
- Works with PyTorch models and loads trained weights from the local `models/` directory.

## Tech Stack

- Backend: Django (Python)
- ML: PyTorch, TorchVision
- CV/Artifacts: OpenCV, NumPy, (optional) `face_recognition`
- Dev tooling: pip/venv/conda
- Deployment assets (optional): Dockerfile + Nginx config under `Django Application/`

## Folder Structure (High Level)

- `Django Application/`
  - `ml_app/`: model/inference logic + Django views + REST-ish API endpoints
  - `project_settings/`: Django settings/URL configuration
  - `templates/`, `static/`: frontend UI assets
  - `Dockerfile`, `nginx/`: optional containerization assets
- `Model Creation/`
  - Training scripts and supporting preprocessing code (not required for running the web app)
- Local runtime only (ignored by Git):
  - `data/`, `GenImage_download/`: datasets
  - `artifacts/`, `checkpoints/`: training outputs
  - `uploaded_images/`, `uploaded_videos/`: user uploads and generated previews
  - `calibration/`: persisted threshold config produced by calibration
  - `models/`: trained `.pt` weights required for inference

## Setup

### 1) Python environment

Use your preferred approach (conda/venv). The project expects the dependencies listed in:
`Django Application/requirements.txt`.

### 2) Configure environment variables

Create `.env` from `.env.example`:
- `DJANGO_SECRET_KEY`
- `DJANGO_DEBUG`
- `DJANGO_ALLOWED_HOSTS`

### 3) Install dependencies

From the repo root:

```bash
pip install -r "Django Application/requirements.txt"
```

### 4) Run the Django server

```bash
python "Django Application/manage.py" runserver 127.0.0.1:8000
```

## Usage Guide

### A) Place trained weights

The current Django inference code looks for model weights here:
`models/*.pt` (relative to the repo root).

If you trained a checkpoint with a different extension, either:
- rename/copy it to `.pt`, or
- update the model-loading logic in `Django Application/ml_app/views.py`.

### B) Calibrate the image threshold (recommended)

Prepare a labeled validation directory with this structure:

```text
data/ai_image_detection/val/
  real/
  fake/   (or ai/, generated/)
```

Call the calibration endpoint:

```bash
curl -X POST http://127.0.0.1:8000/api/calibrate-image-threshold/ ^
  -H "Content-Type: application/json" ^
  -d "{\"validation_dir\":\"data/ai_image_detection/val\",\"metric\":\"f1\",\"save\":true}"
```

Expected response includes:
- `image_fake_threshold` (the best base threshold)
- `metric_value` and other metrics
- `saved: true` and the config path when `save=true`

### C) Detect a single image

Use the image prediction API (multipart form upload):

```python
import requests

files = {"upload_image_file": open("path/to/known_ai_image.jpg", "rb")}
data = {"sequence_length": 100}

r = requests.post(
    "http://127.0.0.1:8000/api/predict-image/",
    files=files,
    data=data,
)
print(r.json())
```

Typical response keys:
- `output` (`REAL` or `FAKE`)
- `confidence`
- `dynamic_threshold`, `base_threshold`, `artifact_features`

## Notes for Release / GitHub

- Large datasets, model weights, uploads, and training checkpoints are intentionally ignored by `.gitignore`.
- Do not commit secrets. Configure via environment variables (`.env`).
- If you want to publish large model weights, consider Git LFS (or host them externally and download at startup).

# ForgeGuard

ForgeGuard is a web-based deepfake/AI-image detection project. It provides:
- A Django backend with a UI for uploads.
- JSON API endpoints for programmatic inference.
- A calibration step that selects the best decision threshold using a labeled validation set.

## Features

- Upload a video or image and get a prediction (`REAL` vs `FAKE`) with confidence.
- Image detection API:
  - Multi-view inference (face-cropped + full-frame) with horizontal flip aggregation.
  - Artifact-aware adjustment using lightweight generation artifact heuristics.
- Threshold calibration API:
  - Sweeps candidate base thresholds over a labeled `real/` + `fake/` validation folder.
  - Persists the best threshold as `calibration/image_threshold_config.json`.
- Works with PyTorch models and loads trained weights from the local `models/` directory.

## Tech Stack

- Backend: Django (Python)
- ML: PyTorch, TorchVision
- CV/Artifacts: OpenCV, NumPy, (optional) `face_recognition`
- Dev tooling: pip/venv/conda
- Deployment assets (optional): Dockerfile + Nginx config under `Django Application/`

## Folder Structure (High Level)

- `Django Application/`
  - `ml_app/`: model/inference logic + Django views + REST-ish API endpoints
  - `project_settings/`: Django settings/URL configuration
  - `templates/`, `static/`: frontend UI assets
  - `Dockerfile`, `nginx/`: optional containerization assets
- `Model Creation/`
  - Training scripts and supporting preprocessing code (not required for running the web app)
- Local runtime only (ignored by Git):
  - `data/`, `GenImage_download/`: datasets
  - `artifacts/`, `checkpoints/`: training outputs
  - `uploaded_images/`, `uploaded_videos/`: user uploads and generated previews
  - `calibration/`: persisted threshold config produced by calibration
  - `models/`: trained `.pt` weights required for inference

## Setup

### 1) Python environment

Use your preferred approach (conda/venv). The project expects the dependencies listed in:
`Django Application/requirements.txt`.

### 2) Configure environment variables

Create `.env` from `.env.example`:
- `DJANGO_SECRET_KEY`
- `DJANGO_DEBUG`
- `DJANGO_ALLOWED_HOSTS`

### 3) Install dependencies

From the repo root:

```bash
pip install -r "Django Application/requirements.txt"
```

### 4) Run the Django server

```bash
python "Django Application/manage.py" runserver 127.0.0.1:8000
```

## Usage Guide

### A) Place trained weights

The current Django inference code looks for model weights here:
`models/*.pt` (relative to the repo root).

If you trained a checkpoint with a different extension, either:
- rename/copy it to `.pt`, or
- update the model-loading logic in `Django Application/ml_app/views.py`.

### B) Calibrate the image threshold (recommended)

Prepare a labeled validation directory with this structure:

```text
data/ai_image_detection/val/
  real/
  fake/   (or ai/, generated/)
```

Call the calibration endpoint:

```bash
curl -X POST http://127.0.0.1:8000/api/calibrate-image-threshold/ ^
  -H "Content-Type: application/json" ^
  -d "{\"validation_dir\":\"data/ai_image_detection/val\",\"metric\":\"f1\",\"save\":true}"
```

Expected response includes:
- `image_fake_threshold` (the best base threshold)
- `metric_value` and other metrics
- `saved: true` and the config path when `save=true`

### C) Detect a single image

Use the image prediction API (multipart form upload):

```python
import requests

files = {"upload_image_file": open("path/to/known_ai_image.jpg", "rb")}
data = {"sequence_length": 100}

r = requests.post(
    "http://127.0.0.1:8000/api/predict-image/",
    files=files,
    data=data,
)
print(r.json())
```

Typical response keys:
- `output` (`REAL` or `FAKE`)
- `confidence`
- `dynamic_threshold`, `base_threshold`, `artifact_features`

## Notes for Release / GitHub

- Large datasets, model weights, uploads, and training checkpoints are intentionally ignored by `.gitignore`.
- Do not commit secrets. Configure via environment variables (`.env`).
- If you want to publish large model weights, consider Git LFS (or host them externally and download at startup).

