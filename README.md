# ForgeGuard — AI-Powered Deepfake Detection System

## Overview
ForgeGuard is an enterprise-grade AI pipeline designed to detect forged, tampered, and deepfake media across both image and video modalities. Built from the ground up for robustness and integration, this system allows production security environments to ingest varying media formats and deploy state-of-the-art Convolutional Neural Networks (CNN) combined with metadata forensics to accurately flag manipulated content.

## Architecture
I designed the ForgeGuard architecture as a highly modular Django-backed inference engine composed of parallel detection graphs:
1. **Video Ingestion Layer**: Frame sampling is evenly distributed across a video. 
2. **Face Detection Layer**: Utilizing a thread-safe Singleton instantiation of MTCNN configured to optimal detection thresholds.
3. **Classification Layer**: The extracted crops are normalized and fed into an EfficientNet B7 architecture yielding a Frame-Level confidence score.
4. **Exception Handling Layer**: A bespoke exception framework safely captures corrupted streams and faceless inputs returning structured contextual alerts (`NO_FACE_DETECTED`).
5. **API Response Layer**: Both Video and Image endpoints return parsed JSON indicating authenticity percentages, hardware devices used, and software signatures.

## Dataset & Training
The classifier engine was adapted leveraging data from extensive datasets spanning over 100,000 video clips representing modern forgery techniques. I chose a dataset primarily composed of diversely lit and varied resolution deepfakes to ensure the model could generalize to edge-cases and anomalous codecs.

## Model Selection
I selected the EfficientNet B7 backbone because of its mathematically proven efficiency scaling. Traditional architectures heavily trade-off computational overhead for detection accuracy; however, EfficientNet scales depth, width, and resolution isotropically. The B7 configuration allows ForgeGuard to process 380x380 resolution face crops—significantly higher than typical networks—to detect sub-pixel manipulation blurring.

## Key Engineering Challenges Solved
- **Double color conversion bug (BGR→RGB)**: Discovered and fixed a critical integration misalignment where inference and training tensors received inverted color channels.
- **Face-less video handling**: Designed early-exit architectures avoiding invalid classifications on landscape or empty videos.
- **Singleton model caching**: Architected a thread-locking mechanism to retain Multi-GB PyTorch models in VRAM preventing out-of-memory crashes on concurrent API requests.
- **Edge case exception framework**: Built from scratch for robust client-facing error structures.
- **Device-safe model cache**: Fixed a cache that moved the B7 model back to the CPU in place after loading, which broke the first GPU request, and made concurrent first requests share a single checkpoint load.
- **Peak-memory reduction**: Measured inference memory and cut the video pipeline's peak from ~4.1 GB to ~1.7 GB by classifying faces in batches of 8 instead of 32, with bit-identical outputs and unchanged speed.

## Installation & Setup
Requires Python 3.11–3.13 and Node 22+.

1. Create a virtual environment and install the dependencies. PyTorch comes first (CPU wheels shown; see https://pytorch.org for a CUDA build), and `facenet-pytorch` is installed without its dependencies because its metadata pins outdated torch/numpy/Pillow versions.
```bash
python -m venv .venv
.venv\Scripts\activate                    # Linux/macOS: source .venv/bin/activate
pip install "torch==2.11.0" "torchvision==0.26.0" --index-url https://download.pytorch.org/whl/cpu
pip install -r requirements.txt
pip install --no-deps "facenet-pytorch==2.6.0"
pip install -r requirements-dev.txt         # tests and lint
```
2. Place the model weights `model_c1.pth` and `deepfake_detector_b7.pth` in `weights/`.
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
python manage.py migrate
python manage.py runserver
```

### Web UI development
Run Django on :8000 and the Vite dev server on :5173 (it proxies `/api` to Django):
```bash
python manage.py runserver      # terminal 1
cd web && npm run dev           # terminal 2 → http://localhost:5173
```

Pages: Home, Analyze (single image/video with upload progress), Batch (up to 20 files, CSV/JSON export), History (stored in the browser), Report (printable A4 / Save as PDF), System status, API reference and How it works. The previous Django-template UI is still available at `/legacy/`.

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

Measured on CPU: ~0.9 GB RAM with both models loaded, ~1.7 GB peak while analysing a video (~20–25 s for 32 faces). Allow 3 GB. Serverless hosts such as Vercel cannot run it (bundle size and timeouts). Full guide and every setting: [docs/deployment_guide.md](docs/deployment_guide.md).

## Testing
```bash
pytest          # 46 tests; the two real-model tests skip automatically when weights/ is empty
ruff check .
cd web && npm run build    # includes the TypeScript type check
```
CI (`.github/workflows/ci.yml`) runs lint, Django deploy checks, the test suite, the UI build and a Docker image build on every push and pull request.

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
The system holds >89% confidence thresholds on validation tests effectively trapping 90% of visually imperceptible manipulated frames on out-of-distribution real world clips.
