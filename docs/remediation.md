# Remediation tracker

Every issue from the [November 2026 audit](audit-2026-11.md), the commit that fixes it,
the test or measurement that proves it, and its status. "Verified" means the proof ran
green in CI.

| ID | Severity | Phase | Fix | Proof | Commit | Status |
|---|---|---|---|---|---|---|
| I1 | High | 3 | No verdict from an unvalidated model (label UNVALIDATED, `validated` flag in the manifest). Retrained on CASIA v2 (JPEG-origin, split by source, calibrated on val): fails on Kodak, so not deployed | Kodak ([eval.md](eval.md)): `model_c1` AUC 0.619 (0.500–0.728); retrained `model_c2` CASIA test 0.962 (0.952–0.971) but Kodak 0.576 (0.460–0.685), baseline 0.566. Both fail the rule | `061fa2729`, phase 3c PR | Interim holds: no image verdict. A model that generalises needs different training data or a different detector (owner decision) |
| I2 | High | 3.1 | PNG/WebP → UNSUPPORTED, no score, model not run | `tests/test_image_verdict.py`; Chrome check | `061fa2729` | Done |
| I3 | High | 1.1 | Pillow `>=13,<14`; pip-audit blocking in CI | pip-audit clean (2 build-time setuptools IDs accepted in SECURITY.md); all goldens unchanged | `8a39349ac` | Done (CI to confirm) |
| I4 | High | 1.2 | `open_untrusted()`: Pillow restricted to JPEG/PNG/WebP decoders, format must match extension; ruff TID251 bans `Image.open` | `tests/test_safe_image.py` (28): disguised BMP/TIFF/GIF/PNG → 415; disallowed parsers never invoked | `d588fa5a7` | Done (CI to confirm) |
| I5 | High | 1.3 | Native-resolution strip ELA in uint8 (bit-identical); streamed video frames, crop-only, 4096² cap | `tests/test_memory_bounds.py`: 49 MP JPEG 2591 → 451 MB; 4096² AVI 2776 → 258 MB | `b4021db7c` | Done (CI to confirm) |
| I6 | High | 2 | Separate worker process (Huey: SQLite / Redis); bounded queue with immediate 503; I/O-free liveness; images prioritised | `tests/test_jobs.py` (25, incl. real worker + web processes); `scripts/loadtest.py` → [perf.md](perf.md): liveness 123/123 OK (max 54 ms), image 200 in 9.1 s, BUSY in ~17 ms | `2cd99f2a6`, `812c704d3`, `a9c5c73d5`, `f1b9d34c3`, `b61dff84a` | Verified: compose stack runs a real job in CI (PR #22) |
| I7 | High | 0 | Manifest download URLs + verified download script; B7 identified upstream; notebook committed | `tests/test_download_weights.py`; fresh clone fetched and verified B7 from upstream | `460feb462`, `6f87cc6c0`, `9ffc94363` | Partial: `model_c1.pth` still has no public URL (owner decision) |
| I8 | Medium | 1.4 | Legacy template UI and upload endpoints deleted (37 files) | `tests/test_legacy_removed.py`: legacy paths 404; no upload kept by any endpoint | `5046f6919` | Done (CI to confirm) |
| I9 | Medium | 4.1 | Detector errors propagate; one helper logs each with its traceback; some frames → FACE_DETECTION_ERRORS note; all frames → FaceDetectionError (500) | `tests/test_face_detection_errors.py` (5) | `449452d2b` | Done |
| I10 | Medium | 1.4 | Resolved by deleting the legacy surface (nothing writes to `MEDIA_ROOT` unless `KEEP_UPLOADS`) | Same tests; Docker CI job | `5046f6919` | Done (CI to confirm) |
| I11 | Medium | 2 | Batches are one background job per file; `/api/detect/batch` returns 202 + batch id instead of running inside the request | Batch 202 → 10 polls → 3 results in Chrome against a real worker; unit tests for batch API and wrapper. A full 20-video batch was not run (~8 min on one worker). No hard per-job timeout (thread workers) | `2cd99f2a6` | Done, with the noted limits |
| I12 | Medium | 0 | Fix the YAML parse error; actionlint in CI; from-scratch setup + Docker run jobs | actionlint clean locally; jobs execute on GitHub | `76b0b1cfb`, `235f332ae`, `b701a9fc5` | Verified: PR #1, all blocking jobs green |
| I13 | Medium | 5 | Hypothesis property tests on upload validation and decoding; direct worker tests; 90% backend coverage gate; Vitest suite for the UI logic with its own gate | Backend 91% line coverage (`api`, `core`), blocking at 90%. Web `src/lib` 97% lines, blocking at 80%. Property tests found a real 500 (see log) | `ca3e8e382`, `2e3773931`, `1d78bd2d1`, `b1fb246ad`, `b30ccb656` | Done (CI to confirm) |
| I14 | Medium | 6.3 | CORS for `/api/`: exact-origin allow-list (`DJANGO_CORS_ALLOWED_ORIGINS`), preflight 204, no credentials, wildcards rejected at startup. The frontend calls the backend directly via `VITE_API_BASE`. A Vercel rewrite was rejected: its body limit for external rewrites is undocumented, and uploads go up to 100 MB | `tests/test_cors.py` (12; 10 fail without the fix). Deployed end to end: pending (backend hosting) | phase6-cors PR | Code done; live check pending |
| I15 | Medium | 0 | Python 3.12 pin, uv lockfile, frozen installs, digest-pinned base images | Fresh clone installed exactly the locked versions | `c4913369d` | Verified: `uv sync --frozen` green on Linux CI and in the Docker build |
| I16 | Low | 3.1 | 'Confidence' wording replaced by 'model score (uncalibrated)'; no confidence figure without a validated verdict | Chrome check: no 'confident' wording on image, PNG or video reports; ECE reported (0.412) | `892cb9568` | Done (calibration itself: phase 3b) |
| I17 | Low | 4.2 | Additive `code` field from one closed ErrorCode set on every error (legacy `status` kept); JSON 405s | `tests/test_error_contract.py` (31): same problem → same code on every endpoint | `5d471bd51` | Done (OpenAPI schema still to do) |
| I18 | Low | 4.3 | `num_frames_sampled` + `num_faces_analyzed`; old field kept, deprecated | `tests/test_video_counts.py` (4) | `6311599e0` | Done |
| I19 | Low | 1.4, 4.3 | Legacy UI and 16 MB of assets (phase 1); remaining dead code removed; vulture in CI | vulture clean in CI | `5046f6919`, `a538f34f1` | Done |
| I20 | Low | 6.1 | Contrast tokens, `/docs` overflow, 404 `<h1>` | Playwright + axe: 0 serious | | Not started |
| I21 | Low | 1.5 | Verified the old key was never in a recorded deployment; gitleaks with a custom Django-key rule in CI | gitleaks full-history scan clean with 1 reviewed fingerprint | see below | Done (CI to confirm) |
| I22 | Low | 0 | Jupyter moved to the `train` dependency group | Fresh-clone setup + tests: 195 s (was 716 s) | `c4913369d` | Done |

## Measurements log

| Date | Measurement | Result |
|---|---|---|
| 2026-11-07 | `deepfake_detector_b7.pth` vs upstream release `0.0.1` | SHA-256 identical to `final_777_DeepFakeClassifier_tf_efficientnet_b7_ns_0_29` |
| 2026-11-07 | Cause of CI failures | `actionlint`: YAML parse error at `ci.yml:34` (unquoted `: ` in a step name) |
| 2026-11-07 | Fresh clone of `phase0-unblock`, `uv sync --frozen` | 103 s; Python 3.12.11, Django 6.0.10, numpy 2.5.4, Pillow 12.3.0, torch 2.11.0+cpu (exactly `uv.lock`) |
| 2026-11-07 | Fresh clone: sync + weights + web build + checks + tests | 195 s total; 77 passed, 10 skipped (all need `model_c1.pth`) |
| 2026-11-07 | `train.ipynb` review (Phase 3 input) | `random_split` has no seed (split not reproducible); the ELA generation step is not in the notebook |
| 2026-11-08 | First GitHub Actions run with jobs (PR #1) | lint, setup + tests, audit, web, docker: pass. mypy: 13 errors (non-blocking). pip-audit: non-blocking |
| 2026-11-08 | Docker image in CI | Builds from `uv.lock`; 384 MB as reported by `docker image inspect`; runs as non-root; `/api/health/live` ok; video model loaded and healthy; readiness `degraded` only because `model_c1.pth` is absent |
| 2026-11-08 | pip-audit after Pillow 13 | 0 unaccepted; setuptools 81 (PYSEC-2026-3447, GHSA-xmj3-9gf7-h52w) accepted: torch 2.11 caps setuptools<82, build-time only |
| 2026-11-08 | Peak RSS growth, 49 MP JPEG | 2591 MB → 451 MB (strip ELA bit-identical to whole-image ELA) |
| 2026-11-08 | Peak RSS growth, 4096² AVI | 2776 MB → 258 MB |
| 2026-11-08 | Video outputs after streaming change | 720p face clip identical (max per-face diff 0.0); 1440p upscale: same label, aggregate 0.031 → 0.023; both paths deviate from native-res scores (mean 0.045 vs 0.056), i.e. B7 is resolution-sensitive above 1080p (phase 3 input) |
| 2026-11-08 | gitleaks, default rules | 0 findings: misses the known historical Django key (false negative) |
| 2026-11-08 | gitleaks, + custom Django-key rule | 1 finding (`6983d82fd`, 2020), reviewed and fingerprinted; 4 / 4 recorded deployments checked: none contained it |
| 2026-11-08 | CSP in Chrome against the built UI | 0 violations across all pages, image analysis, data:/blob: images |
| 2026-11-08 | Peak RSS growth on Linux CI (VmHWM reset before the call) | 49 MP JPEG 477 MB, 4096² AVI 204 MB (budget 600 MB). The first CI run read 649 MB for the JPEG because it used `ru_maxrss`, the process lifetime peak, which includes imports and model loading; the harness now resets the counter first. Correction: commit `2141f73ed` said the harness logs what the unreset counter would read; that logged value was computed differently and was removed in the next commit |
| 2026-11-08 | Phase 2 load test: 6 concurrent videos + 1 image (worker + 16-thread web, SQLite queue) | Liveness 123/123 OK, median 6 ms, max 54 ms (audit: 3/3 timed out). Image 200 in 9.1 s (audit: 178.5 s; before image priority: 202 after 20 s). Videos 202 after the 20 s wait, all done within 123 s |
| 2026-11-08 | Queue full (`FORGEGUARD_MAX_QUEUE=2`), real processes | 2 × 202, then 503 BUSY in ~17 ms each with `Retry-After: 30` (audit: never returned 503) |
| 2026-11-08 | Process memory after Phase 2 | Web 73 MB (audit: 1095 MB, models in the web process); worker 908 MB |
| 2026-11-08 | Real person's video (video4.mp4) through the worker | FAKE at 53.4%: another false-positive data point for phase 3 |
| 2026-11-08 | Docker stack in CI (PR #22): web + worker + redis via docker-compose | Real video job queued → done (`UNSURE`, no face) through the worker; spool empty afterwards; both containers non-root. Memory: web 67 MB, worker 628 MB, redis 4 MB. Image 369 MB |
| 2026-11-08 | Image model on the Kodak splice set (96 JPEGs, reproducible) | AUC 0.619 (95% CI 0.500–0.728), balanced accuracy 0.552, ECE 0.412; mean-ELA baseline AUC 0.566 (0.448–0.686). Fails the validation rule (CI lower bound must exceed max(0.5, baseline)) |
| 2026-11-08 | Splice-set generator determinism | Two runs with the same seed: 97 files byte-identical |
| 2026-11-08 | Video false positives investigated | 0.534 clip: per-face scores flip-flop 0.02–0.98, no consensus, average crossed 0.5. 0.987 clip: consistent scores on a beauty-filtered face (documented limitation) |
| 2026-11-08 | Video model on the local face-swap set (17 clips), consensus rule vs old ≥ 0.5 rule | Consensus: 10 verdicts, accuracy 0.900, 7 UNSURE, 1 real called fake, 0 fakes called real. Old: 17 verdicts, accuracy 0.765, 2 real called fake, 2 fakes called real. AUC 0.889 (0.697–1.000) |
| 2026-11-08 | Static analysis after phase 4 | mypy 39 → 0 errors (now blocking in CI); broad ruff ruleset (E, W, F, I, B, UP, SIM, BLE, C4, RUF) 236 → 0; vulture clean |
| 2026-11-08 | CI secret scan on main failed twice | GitHub release downloads returned 504 (reproduced locally); gitleaks now runs from its pinned Docker Hub image |
| 2026-11-08 | Hypothesis property tests, first run | Found a bug: a JPEG cut off inside its header (6 bytes) made `Image.open` raise `OSError`, so the API returned 500. Now 400 INVALID_MEDIA, with a regression test |
| 2026-11-08 | Flaky test traced | The worker heartbeat thread outlived its test and wrote into the next one; it now takes a stop event |
| 2026-11-08 | Line endings | `.gitattributes` pins LF (CRLF for `.bat`/`.cmd`/`.ps1`); renormalising changed 0 files |
| 2026-11-08 | Coverage | Backend 91% (91% also when the `model_c1.pth` tests skip); web `src/lib` 48 tests, 97% lines, 82% branches |
| 2026-11-08 | CASIA v2 downloaded for phase 3c (not committed) | 28 tar shards from a Hugging Face mirror, each checked against its LFS SHA-256. Counts match the official release: 7,491 authentic, 5,123 tampered. Format bias: 99.3% of authentic images are JPEG, 60% of tampered are TIFF, so a model can learn the file format instead of the tampering. Phase 3c will use only JPEG-origin images in both classes (7,437 vs 2,064). Caveat: the mirror stores every image re-saved losslessly as PNG (`Au_ani_00001.jpg.png`), so the original JPEG files (quantisation tables, metadata) are not available, only their decoded pixels |
| 2026-11-08 | Image model retrained on CASIA v2 (phase 3c) | Best epoch 17/25, val AUC 0.970, temperature 1.41. CASIA test AUC 0.962 (0.952–0.971), ECE 0.020; Kodak AUC 0.576 (0.460–0.685), ECE 0.213, i.e. at chance. Fails the criterion fixed in advance (pass on both). `model_c1` on the same CASIA test: 0.780, possibly contaminated |
