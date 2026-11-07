# Remediation tracker

Every issue from the [November 2026 audit](audit-2026-11.md), the commit that fixes it,
the test or measurement that proves it, and its status. "Verified" means the proof ran
green in CI.

| ID | Severity | Phase | Fix | Proof | Commit | Status |
|---|---|---|---|---|---|---|
| I1 | High | 3 | Fix ELA train/inference mismatch, then retrain or replace the image model; calibrate | Beats mean-ELA baseline on re-encoded CASIA v2 and the audit-recipe set | | Not started |
| I2 | High | 3.1 | Non-JPEG images return `UNSUPPORTED`, never a verdict | Test: PNG/BMP/TIFF/GIF never get a verdict | | Not started |
| I3 | High | 1.1 | Pillow `>=13,<14`; pip-audit blocking in CI | pip-audit 0 in CI | | Not started |
| I4 | High | 1.2 | Single `open_untrusted()` with a format allow-list | Renamed BMP/TIFF/GIF → 415 | | Not started |
| I5 | High | 1.3 | Native-resolution uint8 ELA (strips or lower pixel cap); video resolution cap, crop on decode | Subprocess RSS test on the 49 MP JPEG and 4096² AVI | | Not started |
| I6 | High | 2 | Admission control / job queue; I/O-free liveness | Load test: no long waits, liveness 3 / 3 under load | | Not started |
| I7 | High | 0 | Manifest download URLs + verified download script; B7 identified upstream; notebook committed | `tests/test_download_weights.py`; fresh clone fetched and verified B7 from upstream | `460feb462`, `6f87cc6c0`, `9ffc94363` | Partial: `model_c1.pth` still has no public URL (owner decision) |
| I8 | Medium | 1.4 | Delete the legacy upload surface | Legacy routes 404; upload dir empty | | Not started |
| I9 | Medium | 4.1 | Narrow face-detection exception, log, raise | Detector error → 500 + log line, not UNSURE | | Not started |
| I10 | Medium | 1.4 | Resolved by deleting the legacy surface | Docker CI job | | Not started |
| I11 | Medium | 2 | Per-file jobs with timeouts | 20-video batch completes | | Not started |
| I12 | Medium | 0 | Fix the YAML parse error; actionlint in CI; from-scratch setup + Docker run jobs | actionlint clean locally; jobs execute on GitHub | `76b0b1cfb`, `235f332ae` | Fixed locally; awaiting first GitHub run |
| I13 | Medium | 5 | Tests for classify/aggregate, preprocess goldens, batch | Coverage gate with those lines covered | | Not started |
| I14 | Medium | 6.3 | Vercel rewrite for `/api` | Deployed frontend reaches backend | | Not started |
| I15 | Medium | 0 | Python 3.12 pin, uv lockfile, frozen installs, digest-pinned base images | Fresh clone installed exactly the locked versions | `c4913369d` | Done (CI to confirm on Linux) |
| I16 | Low | 3.1, 3.5 | Remove "confident" wording; calibrate | Vitest on `verdict.ts`; ECE reported | | Not started |
| I17 | Low | 4.2 | `ErrorCode` / `Verdict` enums, one response shape | Cross-endpoint contract test | | Not started |
| I18 | Low | 4.3 | `num_faces_analyzed` + `num_frames_sampled` | Unit test on result fields | | Not started |
| I19 | Low | 1.4, 4.3 | Delete dead code and unused assets | vulture clean | | Not started |
| I20 | Low | 6.1 | Contrast tokens, `/docs` overflow, 404 `<h1>` | Playwright + axe: 0 serious | | Not started |
| I21 | Low | 1.5 | Verify whether the old key was deployed; gitleaks in CI | gitleaks job green | | Not started |
| I22 | Low | 0 | Jupyter moved to the `train` dependency group | Fresh-clone setup + tests: 195 s (was 716 s) | `c4913369d` | Done |

## Measurements log

| Date | Measurement | Result |
|---|---|---|
| 2026-11-07 | `deepfake_detector_b7.pth` vs upstream release `0.0.1` | SHA-256 identical to `final_777_DeepFakeClassifier_tf_efficientnet_b7_ns_0_29` |
| 2026-11-07 | Cause of CI failures | `actionlint`: YAML parse error at `ci.yml:34` (unquoted `: ` in a step name) |
| 2026-11-07 | Fresh clone of `phase0-unblock`, `uv sync --frozen` | 103 s; Python 3.12.11, Django 6.0.10, numpy 2.5.4, Pillow 12.3.0, torch 2.11.0+cpu (exactly `uv.lock`) |
| 2026-11-07 | Fresh clone: sync + weights + web build + checks + tests | 195 s total; 77 passed, 10 skipped (all need `model_c1.pth`) |
| 2026-11-07 | `train.ipynb` review (Phase 3 input) | `random_split` has no seed (split not reproducible); the ELA generation step is not in the notebook |
