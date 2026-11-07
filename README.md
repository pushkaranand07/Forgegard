# ForgeGuard: Deepfake & Image-Forgery Detection Service

ForgeGuard is a production-style serving system built around two detectors:

- a **pretrained face-swap video detector**, the EfficientNet-B7 model from Selim Seferbekov's [DFDC 1st-place solution](https://github.com/selimsef/dfdc_deepfake_challenge), used as-is;
- an **ELA image-splicing classifier** that I trained on CASIA.

Both sit behind a hardened Django API and a React UI. The serving layer, the UI, the deployment setup and the image model's training are my work. The video model's weights and its aggregation logic are third-party; see [CREDITS.md](CREDITS.md). Neither model has been evaluated by a script in this repo yet. An evaluation and calibration harness is in progress, and until it lands this README reports no accuracy figures.

> **Research demo, not proof.** Model output is not evidence about a real person or event. Don't use it to make decisions about people.

## What I built

- **Serving layer:** Django API with per-file, per-request and per-batch size limits; a 50-megapixel decode cap; an inference concurrency guard that queues and then returns `503 BUSY`; per-IP rate limiting; request IDs; a consistent JSON error shape with no stack traces or paths; liveness and readiness probes; model warm-up at startup.
- **Video pipeline port:** adapted the upstream DFDC preprocessing (MTCNN crop, isotropic resize, centre padding, ImageNet normalisation) and `confident_strategy` aggregation to a single-checkpoint, CPU-friendly inference path. Fixed a BGR/RGB colour-order mismatch between frame decoding and the model.
- **Image model:** trained `IMDModel` (a small CNN on ELA maps; architecture adapted from public code, see [CREDITS.md](CREDITS.md)) on CASIA in `training/notebooks/train.ipynb`.
- **Fail-safe model loading:** every weight file is SHA-256-checked against `core/model_manifest.json`, loaded with `weights_only=True` and strict key matching (no unsafe-unpickling fallback). A bad model makes `/api/health/` report unhealthy and requests return `503 MODEL_UNAVAILABLE`. Responses carry the model name, weights hash and pipeline version. Golden-sample tests pin the image pipeline's outputs; video fixtures are pending.
- **Inference engineering:** a thread-safe, device-aware model cache, so concurrent first requests share one checkpoint load and the model stays on its target device. Batched face classification at 8 faces per forward pass instead of 32, which lowered peak RAM in a manual measurement (about 4.1 GB → 1.7 GB on CPU, same outputs). Not yet reproduced by a committed script.
- **Web UI:** single and batch analysis with upload progress, browser-local history, printable reports, and status and API pages.
- **Delivery:** multi-stage Docker image (non-root, health check), docker-compose, and GitHub Actions CI (lint, Django deploy checks, tests, UI build, image build).

## How it works

**Video** (`POST /api/detect-video/`)
1. Sample 32 evenly spaced frames.
2. Detect faces with MTCNN on a half-resolution copy, keep the highest-confidence face per frame, and pad the box by one third on each side.
3. Resize each crop isotropically to 380 px, centre-pad it, and normalise with ImageNet statistics.
4. Run the EfficientNet-B7 classifier. It outputs a logit per face; the sigmoid of that is the per-face fake score.
5. Aggregate the scores with upstream's `confident_strategy`. If no face is found, the result is `UNSURE`.

**Image** (`POST /api/detect-image/`)
1. **Metadata:** report the EXIF/PNG `Software` tag if one is present. This is a weak hint, not a verdict; phone firmware also writes this tag.
2. **ELA:** re-save the image as JPEG at quality 90, take the amplified per-pixel difference, resize it to 128×128, and classify it with `IMDModel` as authentic or tampered.

## Scope & limitations

- **Video detects face-swap manipulation of the kind in DFDC (2019–2020 methods).** It hasn't been tested against, and should be assumed weak on, diffusion-generated or fully synthetic video, lip-sync edits and face reenactment.
- **Only one face per frame is classified** (the most confident detection). A manipulated face that isn't the most prominent can be missed. Upstream classifies all faces.
- **Single checkpoint.** Upstream's competition entry averaged an ensemble, so its published results don't transfer to this single model.
- **The image pipeline detects splicing and retouching in JPEGs.** It does **not** detect AI-generated images.
- **ELA degrades on re-encoded images** (social-media uploads, screenshots, resized files) and isn't meaningful for lossless sources such as PNG.
- **Scores are uncalibrated.** "Confidence" in the current API and UI is `max(p, 1 − p)`, not a probability of being correct.
- **Licences:** the training datasets (DFDC, CASIA) allow non-commercial research only. See [CREDITS.md](CREDITS.md).

## Installation & Setup
Requires [uv](https://docs.astral.sh/uv/getting-started/installation/) and Node 22+. uv installs Python 3.12 (pinned in `.python-version`) if you don't have it.

On Linux/macOS, `make setup` runs steps 1, 2 and 4 below; then `make test`. On Windows, run the commands directly.

1. Install the locked dependencies (exact versions and hashes from `uv.lock`, CPU PyTorch wheels) into `.venv/`.
```bash
uv sync --frozen
```
   For a CUDA build, change the `pytorch-cpu` index in `pyproject.toml` and run `uv lock`. Training-notebook tools are a separate group: `uv sync --frozen --group train`.
2. Download and verify the model weights into `weights/`. Every file is checked against the SHA-256 in `core/model_manifest.json`.
```bash
uv run python scripts/download_weights.py
```
   The video model comes from its upstream release. The image model (`model_c1.pth`) has no public download yet: the script reports it as missing, and you can point it at a copy with `FORGEGUARD_WEIGHTS_URL_MODEL_C1_PTH=<url>`. Without it the image endpoint returns `503` and the image-model tests are skipped.
3. Copy the configuration template (it is loaded automatically and works as-is for local development).
```bash
cp .env.example .env
```
4. Build the web UI. The build is written to `frontend/static/app/` and served by Django at `/`.
```bash
cd web
npm ci
npm run build
```
5. Apply migrations, run the server and open http://127.0.0.1:8000/.
```bash
uv run python manage.py migrate
uv run python manage.py runserver
```

### Web UI development
Run Django on :8000 and the Vite dev server on :5173 (it proxies `/api` to Django):
```bash
uv run python manage.py runserver   # terminal 1
cd web && npm run dev               # terminal 2 → http://localhost:5173
```

Pages: Home, Analyze (single image/video with upload progress), Batch (up to 20 files, CSV/JSON export), History (stored in the browser), Report (printable A4 / Save as PDF), System status, API reference and How it works.

## Production Deployment
ForgeGuard ships as one Docker image: gunicorn serves the API and the pre-built UI, with WhiteNoise for static files.
```bash
cp .env.example .env    # set DJANGO_DEBUG=false and a real DJANGO_SECRET_KEY
docker compose up --build -d
```
What production mode adds:
- **Fails fast on unsafe config**: refuses to start with `DEBUG` off and a placeholder secret key; opt-in HTTPS redirect, HSTS and secure cookies (`DJANGO_HTTPS=true`).
- **Bounded resource use**: per-file, per-request and per-batch size limits; a 50-megapixel cap on images; an inference concurrency guard that queues requests instead of running out of memory (503 `BUSY` when the queue wait expires); per-IP rate limiting (429).
- **Privacy by default**: uploads are analysed from a scratch file and deleted; nothing is kept unless `FORGEGUARD_KEEP_UPLOADS=true`.
- **Operability**: liveness (`/api/health/live`) and readiness (`/api/health/`) probes, models warmed up at startup, an `X-Request-ID` on every response and log line, and no stack traces or internal paths in API responses.

Manual measurement on CPU (not yet scripted): ~0.9 GB RAM with both models loaded, ~1.7 GB peak while analysing a video (~20–25 s for 32 faces). Allow 3 GB. Batch requests run synchronously, so a batch of many videos can exceed the 300 s worker timeout; moving video to background jobs is planned. Serverless hosts such as Vercel cannot run it (bundle size and timeouts). Full guide and every setting: [docs/deployment_guide.md](docs/deployment_guide.md).

## Testing
```bash
uv run pytest              # real-model and golden-sample tests skip automatically when weights are missing
uv run ruff check .
cd web && npm run build    # includes the TypeScript type check
```
CI (`.github/workflows/ci.yml`) runs on every push to `main` and every pull request: ruff and actionlint; a from-scratch `make setup` followed by Django deploy checks and `make test`; a dependency audit; the UI build; and a Docker job that builds the image, runs it, checks liveness and readiness and asserts it runs as non-root. mypy and pip-audit run but don't block yet (see [docs/remediation.md](docs/remediation.md)).

## API Reference
Full reference with response examples and error codes: [docs/api_reference.md](docs/api_reference.md).

| Endpoint | Purpose |
| --- | --- |
| `POST /api/detect-image/` | `image` file → Level-1 metadata forensics + Level-2 ELA/CNN verdict |
| `POST /api/detect-video/` | `video` file → per-face EfficientNet-B7 scores and an aggregated REAL/FAKE/UNSURE verdict |
| `POST /api/detect/` | `file` → routed to the image or video model by extension |
| `POST /api/detect/batch` | repeated `file` fields (up to 20) → one result or error per file |
| `GET /api/health/` | model availability, device and live upload limits (503 if a model is missing) |
| `GET /api/health/live` | liveness probe |

Errors are always `{"error": "...", "status": "<CODE>"}` with a meaningful HTTP status.

## Results

**Not yet evaluated.** No accuracy figure in this repo has been produced by a committed, reproducible evaluation script yet. An earlier version of this README cited ">89% / 90% on out-of-distribution clips". That claim had no supporting evaluation and has been withdrawn.

| Model | Test set | Metrics |
|---|---|---|
| Video: DFDC B7 (single checkpoint) | Celeb-DF v2 official test list (out of distribution) | not yet evaluated |
| Image: ELA + `IMDModel` | CASIA, seeded held-out split | not yet evaluated |

The notebook accuracies printed in `train.ipynb` are not reported here; [docs/training_methodology.md](docs/training_methodology.md) explains why.

## Credits & Licenses

The video model's weights and aggregation logic come from Selim Seferbekov's [DFDC 1st-place solution](https://github.com/selimsef/dfdc_deepfake_challenge) (MIT). Face detection uses [facenet-pytorch](https://github.com/timesler/facenet-pytorch) (MIT), and the backbone definition comes from [timm](https://github.com/huggingface/pytorch-image-models) (Apache-2.0). The training datasets (DFDC, CASIA; Celeb-DF for evaluation) allow **non-commercial research use only**. Full list: [CREDITS.md](CREDITS.md). Model details and limitations: [MODEL_CARD.md](MODEL_CARD.md).
