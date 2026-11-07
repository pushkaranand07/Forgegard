# Remediation tracker

Every issue from the [November 2026 audit](audit-2026-11.md), the commit that fixes it,
the test or measurement that proves it, and its status. "Verified" means the proof ran
green in CI.

| ID | Severity | Phase | Fix | Proof | Commit | Status |
|---|---|---|---|---|---|---|
| I1 | High | 3 | Fix ELA train/inference mismatch, then retrain or replace the image model; calibrate | Beats mean-ELA baseline on re-encoded CASIA v2 and the audit-recipe set | | Not started |
| I2 | High | 3.1 | Non-JPEG images return `UNSUPPORTED`, never a verdict | Test: PNG/BMP/TIFF/GIF never get a verdict | | Not started |
| I3 | High | 1.1 | Pillow `>=13,<14`; pip-audit blocking in CI | pip-audit clean (2 build-time setuptools IDs accepted in SECURITY.md); all goldens unchanged | `8a39349ac` | Done (CI to confirm) |
| I4 | High | 1.2 | `open_untrusted()`: Pillow restricted to JPEG/PNG/WebP decoders, format must match extension; ruff TID251 bans `Image.open` | `tests/test_safe_image.py` (28): disguised BMP/TIFF/GIF/PNG → 415; disallowed parsers never invoked | `d588fa5a7` | Done (CI to confirm) |
| I5 | High | 1.3 | Native-resolution strip ELA in uint8 (bit-identical); streamed video frames, crop-only, 4096² cap | `tests/test_memory_bounds.py`: 49 MP JPEG 2591 → 451 MB; 4096² AVI 2776 → 258 MB | `b4021db7c` | Done (CI to confirm) |
| I6 | High | 2 | Admission control / job queue; I/O-free liveness | Load test: no long waits, liveness 3 / 3 under load | | Not started |
| I7 | High | 0 | Manifest download URLs + verified download script; B7 identified upstream; notebook committed | `tests/test_download_weights.py`; fresh clone fetched and verified B7 from upstream | `460feb462`, `6f87cc6c0`, `9ffc94363` | Partial: `model_c1.pth` still has no public URL (owner decision) |
| I8 | Medium | 1.4 | Legacy template UI and upload endpoints deleted (37 files) | `tests/test_legacy_removed.py`: legacy paths 404; no upload kept by any endpoint | `5046f6919` | Done (CI to confirm) |
| I9 | Medium | 4.1 | Narrow face-detection exception, log, raise | Detector error → 500 + log line, not UNSURE | | Not started |
| I10 | Medium | 1.4 | Resolved by deleting the legacy surface (nothing writes to `MEDIA_ROOT` unless `KEEP_UPLOADS`) | Same tests; Docker CI job | `5046f6919` | Done (CI to confirm) |
| I11 | Medium | 2 | Per-file jobs with timeouts | 20-video batch completes | | Not started |
| I12 | Medium | 0 | Fix the YAML parse error; actionlint in CI; from-scratch setup + Docker run jobs | actionlint clean locally; jobs execute on GitHub | `76b0b1cfb`, `235f332ae`, `b701a9fc5` | Verified: PR #1, all blocking jobs green |
| I13 | Medium | 5 | Tests for classify/aggregate, preprocess goldens, batch | Coverage gate with those lines covered | | Not started |
| I14 | Medium | 6.3 | Vercel rewrite for `/api` | Deployed frontend reaches backend | | Not started |
| I15 | Medium | 0 | Python 3.12 pin, uv lockfile, frozen installs, digest-pinned base images | Fresh clone installed exactly the locked versions | `c4913369d` | Verified: `uv sync --frozen` green on Linux CI and in the Docker build |
| I16 | Low | 3.1, 3.5 | Remove "confident" wording; calibrate | Vitest on `verdict.ts`; ECE reported | | Not started |
| I17 | Low | 4.2 | `ErrorCode` / `Verdict` enums, one response shape | Cross-endpoint contract test | | Not started |
| I18 | Low | 4.3 | `num_faces_analyzed` + `num_frames_sampled` | Unit test on result fields | | Not started |
| I19 | Low | 1.4, 4.3 | Delete dead code and unused assets | vulture clean | | Not started |
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
