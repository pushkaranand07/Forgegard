# ForgeGuard: Deepfake & Image-Forgery Detection Service

ForgeGuard is a production-style serving system built around two detectors:

- a **pretrained face-swap video detector**, the EfficientNet-B7 model from Selim Seferbekov's [DFDC 1st-place solution](https://github.com/selimsef/dfdc_deepfake_challenge), used as-is;
- an **ELA image-splicing classifier** that I trained, and later retrained on CASIA v2 with a reproducible script.

Both sit behind a hardened Django API and a React UI.
- **My work:** the serving layer, the UI, the deployment setup, the evaluation harness and the image model's training.
- **Third-party:** the video model's weights and its consensus thresholds. See [CREDITS.md](CREDITS.md).

**Honest status:**
- **Image model: not validated.** It fails its own evaluation, so it gives no verdict, only an experimental score.
- **Video model: indicative results only,** on a small local set.

Details are in [Results](#results).

> **Research demo, not proof.** Model output is not evidence about a real person or event. Don't use it to make decisions about people.

## What I built

- **Serving layer.**
  - Django API with per-file, per-request and per-batch size limits, and a 50-megapixel decode cap.
  - Pillow is restricted to the JPEG, PNG and WebP decoders, and a file's real format must match its extension.
  - Analysis runs in a separate background worker (Huey: SQLite locally, Redis in production), so web requests never run a model.
  - When the queue is full, requests get an immediate `503 BUSY`. Images are queued ahead of videos.
  - Per-IP rate limiting, request IDs, liveness and readiness probes (readiness tracks the worker's heartbeat).
  - CORS for an exact-origin allow-list.
- **One error contract.** Every error is `{"error", "status", "code"}`, where `code` comes from one closed set, with no stack traces or paths. The whole API is described by an [OpenAPI 3.1 contract](api/openapi.yaml):
  - tests check every endpoint's real responses against it;
  - the UI's TypeScript types are generated from it.
- **Video pipeline port.**
  - Adapted the upstream DFDC preprocessing (MTCNN crop, isotropic resize, centre padding, ImageNet normalisation) to a single-checkpoint, CPU-friendly path.
  - Frames are streamed, never all held in memory, and capped at 4096×4096.
  - Fixed a BGR/RGB colour-order mismatch between frame decoding and the model.
- **Image pipeline and evaluation.**
  - ELA in one shared module, at native resolution, in strips (bit-identical output, bounded memory).
  - Leakage-aware CASIA preparation and a seeded training script with temperature scaling.
  - An evaluation harness with bootstrap confidence intervals and a pre-registered validation rule.
- **Fail-safe model loading.**
  - Every weight file is SHA-256-checked against `core/model_manifest.json`, then loaded with `weights_only=True` and strict key matching.
  - A model only gives verdicts if its manifest entry is marked `validated`.
  - A bad model makes `/api/health/` report unhealthy, and requests return `503 MODEL_UNAVAILABLE`.
- **Web UI.**
  - Single and batch analysis with upload progress, browser-local history, printable reports, and status and API pages.
  - Automated accessibility checks (axe, WCAG 2.1 A/AA rules) find no serious or critical violations on any page, in either theme, at phone or desktop width. Automated tools cover only part of WCAG; no manual audit has been done.
- **Delivery.**
  - Multi-stage Docker image (non-root, health check).
  - docker-compose (web, worker, redis), plus a single-container mode for hosts such as a Hugging Face Space.
  - GitHub Actions CI (see [Testing](#testing)).

## How it works

**Video** (`POST /api/detect-video/`)
1. Sample 32 evenly spaced frames, streamed from the file (downscaled above 1920 px).
2. Detect faces with MTCNN, keep the highest-confidence face per frame, and pad the box by one third on each side.
3. Resize each crop isotropically to 380 px, centre-pad it, and normalise with ImageNet statistics.
4. Run the EfficientNet-B7 classifier. The sigmoid of its logit is each face's fake score.
5. Give a verdict only on consensus, using upstream's own thresholds:
   - **FAKE:** more than 11 confidently fake faces (score > 0.8), and more than n / 2.5 of them.
   - **REAL:** more than 90% of faces confidently real (score < 0.2).
   - **Otherwise `UNSURE`,** with the reason in `notes`: `NO_CONSENSUS`, `TOO_FEW_FACES` (under 8 faces) or `NO_FACE_DETECTED`.

**Image** (`POST /api/detect-image/`)
1. **Metadata:** report the EXIF/PNG `Software` tag if one is present. This is a weak hint, not a verdict; phone firmware also writes this tag.
2. **ELA (JPEG only):** re-save the image as JPEG at quality 90, take the amplified per-pixel difference, resize it to 128×128, and score it with `IMDModel`.
   - The model is not validated, so the result is labelled `UNVALIDATED`, with an experimental score and no verdict.
   - PNG and WebP get `UNSUPPORTED`: ELA measures JPEG compression, which they don't have.

## Scope & limitations

- **Video detects face-swap manipulation of the kind in DFDC (2019–2020 methods).** It hasn't been tested against, and should be assumed weak on, diffusion-generated or fully synthetic video, lip-sync edits and face reenactment. Beauty filters can trigger confident false positives ([docs/eval.md](docs/eval.md)).
- **Only one face per frame is classified** (the most confident detection). A manipulated face that isn't the most prominent can be missed.
- **Single checkpoint.** Upstream's competition entry averaged an ensemble, so its published results don't transfer to this single model.
- **The image model does not generalise.**
  - Retrained on CASIA v2, it scores AUC 0.962 on CASIA's held-out test images, but 0.576 (chance) on a separate splice set.
  - It does **not** detect AI-generated images, and ELA degrades on re-encoded images (social-media uploads, screenshots, resized files).
- **Video scores are uncalibrated.** `confidence_pct` is `max(p, 1 − p)`, not a probability of being correct, and is only given with a verdict.
- **Licences:** the datasets (DFDC, CASIA) allow non-commercial research only. See [CREDITS.md](CREDITS.md).

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
   - **Video model:** comes from its upstream release.
   - **Image model (`model_c1.pth`):** has no public download, so the script reports it as missing. You can point it at a copy with `FORGEGUARD_WEIGHTS_URL_MODEL_C1_PTH=<url>`.
   - **Without the image model:** the image endpoint returns `503`, and the image-model tests are skipped.
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
5. Apply migrations, then start the analysis worker and the web server (two terminals) and open http://127.0.0.1:8000/.
```bash
uv run python manage.py migrate
uv run python manage.py run_worker   # terminal 1: loads the models, runs analysis jobs
uv run python manage.py runserver    # terminal 2: API + UI
```
   Without a worker, uploads are accepted but stay queued, and `/api/health/` reports `degraded`.

### Web UI development
Run the worker, Django on :8000 and the Vite dev server on :5173 (it proxies `/api` to Django):
```bash
uv run python manage.py run_worker  # terminal 1
uv run python manage.py runserver   # terminal 2
cd web && npm run dev               # terminal 3 → http://localhost:5173
```

Pages: Home, Analyze (single image/video with upload progress), Batch (up to 20 files, CSV/JSON export), History (stored in the browser), Report (printable A4 / Save as PDF), System status, API reference and How it works.

After changing `api/openapi.yaml`, regenerate the UI's API types with `npm run gen:api` in `web/`; CI fails if they are stale.

## Production Deployment
ForgeGuard ships as one Docker image. `docker-compose.yml` runs it as three services:
- **web:** gunicorn serving the API and the pre-built UI, with no models;
- **worker:** `run_worker`, which holds the models;
- **redis:** the queue and shared rate-limit counters.

Uploads pass from web to worker through a shared volume.
```bash
cp .env.example .env    # set DJANGO_DEBUG=false and a real DJANGO_SECRET_KEY
docker compose up --build -d
```
What production mode adds:
- **Fails fast on unsafe config:**
  - refuses to start with `DEBUG` off and a placeholder secret key;
  - opt-in HTTPS redirect, HSTS and secure cookies (`DJANGO_HTTPS=true`).
- **Bounded resource use:**
  - per-file, per-request and per-batch size limits;
  - a 50-megapixel cap on images and a 4096×4096 cap on video;
  - memory per request independent of the upload's size;
  - a bounded job queue (immediate 503 `BUSY` when full);
  - per-IP rate limiting (429), global when Redis is used.
- **Isolation:** analysis runs in the worker container with its own memory limit, so an out-of-memory crash kills a job, never the website, and health checks keep answering under load.
- **Privacy by default:** uploads are analysed from a scratch file and deleted; nothing is kept unless `FORGEGUARD_KEEP_UPLOADS=true`.
- **Operability:**
  - a liveness probe (`/api/health/live`, no I/O);
  - a readiness probe (`/api/health/`: weights verified, queue reachable, worker heartbeat fresh, models loaded);
  - models warmed up when the worker starts;
  - an `X-Request-ID` on every response and log line.

**Single-container hosts.**
- `FORGEGUARD_ROLE=all` runs the web server and the worker in one container.
- `FORGEGUARD_DOWNLOAD_WEIGHTS=true` downloads verified weights at startup.
- CI runs exactly this configuration, as the non-root user a Hugging Face Space uses, and puts a real job through it.

**Frontend on Vercel:** set `VITE_API_BASE` to the backend's URL, and allow the frontend's origin on the backend with `DJANGO_CORS_ALLOWED_ORIGINS`.

Step-by-step guides for both are in [docs/deployment_guide.md](docs/deployment_guide.md).

**Performance**, measured with `scripts/loadtest.py` ([docs/perf.md](docs/perf.md)):
- **Memory:** the web process uses ~75 MB, and the worker ~0.9 GB with both models.
- **Video speed:** ~20–25 s per video on CPU.
- **Under load (6 concurrent videos):** an image still returns in ~9 s (178 s before the worker split), and liveness answers every probe (max 54 ms).

## Testing
```bash
make test                      # pytest with a 90% coverage gate (real-model tests skip without weights)
uv run ruff check . && uv run mypy api core
cd web && npm test             # Vitest unit tests for the UI logic, with a coverage gate
cd web && npm run test:e2e     # Playwright + axe: every page, both themes, phone and desktop widths
```

The backend suite includes:
- **Contract tests** against `api/openapi.yaml`.
- **Error-code tests:** the same problem gives the same `code` on every endpoint.
- **Hypothesis property tests** on upload validation. They found a real 500 (a truncated JPEG), now fixed.
- **Memory-bound tests,** decoder allow-list tests, and golden samples pinned to weight hashes.

CI (`.github/workflows/ci.yml`) runs on every push to `main` and every pull request. Every job blocks:
- **Lint:** ruff, actionlint and vulture.
- **Typecheck:** mypy.
- **Setup and tests:** a from-scratch `make setup`, then Django deploy checks and `make test`.
- **Audit:** pip-audit and npm audit, with no accepted findings.
- **Secret scan:** a full-history gitleaks scan.
- **Web UI:** unit tests, stale-type check, accessibility checks and build.
- **Docker:** builds the image, then runs a real job through the compose stack and through a single container.

## API Reference
- **Human-readable:** [docs/api_reference.md](docs/api_reference.md).
- **Machine-readable:** [api/openapi.yaml](api/openapi.yaml).

| Endpoint | Purpose |
| --- | --- |
| `POST /api/detect-image/` | `image` file → metadata hint, plus an experimental ELA score for JPEGs (`UNVALIDATED`, no verdict) |
| `POST /api/detect-video/` | `video` file → per-face EfficientNet-B7 scores and a REAL / FAKE / UNSURE consensus verdict |
| `POST /api/detect/` | `file` → routed to the image or video model by extension |
| `POST /api/detect/batch` | repeated `file` fields (up to 20) → one result or error per file |
| `POST /api/jobs/`, `GET /api/jobs/<id>/` | submit one file as a background job (202 + job id) / poll it |
| `POST /api/batches/`, `GET /api/batches/<id>/` | submit several files (202 + batch id) / poll progress and results |
| `GET /api/health/` | readiness: weights verified, queue reachable, worker alive with models loaded (503 otherwise) |
| `GET /api/health/live` | liveness probe |

**Waiting and polling.** The four `detect` endpoints wait up to 20 s for their job, which covers images. Slower work, usually video, returns `202` with a job or batch id to poll.

**Errors** are `{"error": "...", "status": "<legacy>", "code": "<CODE>"}`, with a meaningful HTTP status; switch on `code`. A full queue gives `503 BUSY` with `Retry-After`.

## Results

**How these numbers were produced.**
- Every figure comes from a committed script, with its result file in `eval/results/`; methods are in [docs/eval.md](docs/eval.md).
- **The validation rule was fixed before any evaluation:** a model's AUC 95% interval must lie entirely above both 0.5 and a no-model baseline (mean ELA intensity).

| Model | Test set | Result |
|---|---|---|
| Image: `model_c1` (deployed) | Kodak splice set, 96 JPEGs (reproducible) | AUC 0.619 (0.500–0.728), baseline 0.566. **Fails**: no verdict is given |
| Image: retrained on CASIA v2 (`model_c2`, not deployed) | CASIA v2 test split, 1,424 images, split by source image | AUC 0.962 (0.952–0.971), ECE 0.020 |
| Image: same retrained model | Kodak splice set | AUC 0.576 (0.460–0.685). **Fails**: does not generalise beyond CASIA |
| Video: DFDC B7 (single checkpoint) | 17 local clips (crude face swaps), indicative only | Verdict on 10 of 17, accuracy 0.900 when it gives one; AUC 0.889 (0.697–1.000) |
| Video | Celeb-DF v2 / FaceForensics++ | not yet evaluated (access requests pending) |

**What these results mean:**
- **Image model:** retraining with the exact inference preprocessing, a leakage-free split and calibration still fails the out-of-distribution test. So the gap is the training data or the approach, not tuning.
- **Video model:** the set is tiny, and its fakes are easier than real deepfakes, so these numbers are an upper bound, not a benchmark.
- **The earlier claim** of ">89% / 90% on out-of-distribution clips" had no supporting evaluation and is withdrawn.

## Project history

ForgeGuard was audited in November 2026: it scored 5.2/10, with 22 issues ([docs/audit-2026-11.md](docs/audit-2026-11.md)).

[docs/remediation.md](docs/remediation.md) tracks each issue's fix, the test or measurement that proves it, and its status. It also has a log of every measurement.

## Credits & Licenses

- **Video model:** weights and consensus thresholds from Selim Seferbekov's [DFDC 1st-place solution](https://github.com/selimsef/dfdc_deepfake_challenge) (MIT).
- **Face detection:** [facenet-pytorch](https://github.com/timesler/facenet-pytorch) (MIT).
- **Backbone definition:** [timm](https://github.com/huggingface/pytorch-image-models) (Apache-2.0).
- **Datasets:** DFDC and CASIA, plus Celeb-DF for evaluation, allow **non-commercial research use only**.

Full list: [CREDITS.md](CREDITS.md). Model details and limitations: [MODEL_CARD.md](MODEL_CARD.md).
