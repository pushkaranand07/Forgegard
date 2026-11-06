# Phase 0 — Recon

Date: 2026-11-06. No code was changed in this phase.

## Repo map

| Area | Location | Notes |
|---|---|---|
| Django entry | `manage.py`, `config/settings.py`, `config/urls.py`, `gunicorn.conf.py` | 1 gthread worker × 4 threads, timeout 300 s, `LocMemCache` |
| API | `api/unified_api.py` (`/api/detect/`, `/api/detect/batch`), `api/image_api.py`, `api/video_api.py`, `api/health_api.py`, `api/common.py` (limits, semaphore, rate limit), `api/middleware.py`, `api/warmup.py` | Batch runs files sequentially inside one request |
| Video pipeline | `core/pipeline/video_processor.py` | MTCNN → single B7 → `confident_strategy` |
| Image pipeline | `core/pipeline/image_processor.py` | EXIF `Software` tag + ELA → `IMDModel` (128×128) |
| Tests | `tests/test_api.py`, `tests/test_pipeline.py`, `api/tests.py` | HTTP plumbing and input validation only; no model-output tests |
| CI | `.github/workflows/ci.yml` | ruff, `check --deploy`, pytest, UI build, Docker build |
| UI | `web/` (Vite/React), legacy templates in `frontend/templates/` | API base from `VITE_API_BASE` / `VITE_API_URL`, default same-origin |
| Deploy | `Dockerfile`, `docker-compose.yml`, `web/vercel.json` | Vercel config is an SPA rewrite only; no CORS configured in Django |
| Training | `training/notebooks/*.ipynb` (gitignored, local only), `training/dataset/README.md` | No notebook trains EfficientNet-B7 |
| `calibration/` | does not exist | gitignored; never created |
| `dfdc_model_source/` | **does not exist** in the repo or on this machine | Upstream was checked against the public repo instead (below) |

Environment: torch 2.11.0+cpu, timm 1.0.30, numpy 2.4.3, Django 6.0.4, CPU only. No datasets are on this machine; the notebooks reference `F:/College/BE/Final year project/Dataset/...`, which isn't mounted.

## Upstream check

Source: `github.com/selimsef/dfdc_deepfake_challenge` (MIT license, author Selim Seferbekov), files `kernel_utils.py`, `training/pipelines/train_classifier.py`, `download_weights.sh`. I read the public files because `dfdc_model_source/` isn't available locally.

| # | Question | Upstream | ForgeGuard | Match? |
|---|---|---|---|---|
| a | Multiple faces per frame | `FaceExtractor` keeps **every** detected box (`for bbox, score in zip(batch_boxes, probs): faces.append(crop)`); `predict_on_video` loops `for face in frame_data["faces"]` | `extract_face` keeps only the highest-probability face (`video_processor.py:272-274`) | **No.** The "EXACTLY replicates" comments are wrong on this point. The review's claim [Medium] is confirmed. |
| b | `confident_strategy` thresholds | `t=0.8`; `fakes > sz // 2.5 and fakes > 11` → mean of `> t`; `count(pred < 0.2) > 0.9*sz` → mean of `< 0.2`; else mean | Identical (`video_processor.py:323-353`) | Yes |
| c | Normalisation / colour order | BGR→RGB in `VideoReader`; ImageNet mean/std; isotropic resize (INTER_AREA down / INTER_CUBIC up) + `put_to_center` | BGR→RGB once (`video_processor.py:695`); same mean/std, resize and centring | Yes |
| – | Ensemble | `download_weights.sh` publishes **7** B7 checkpoints (seeds 111/555/777/888/999); README says 5 seeds trained via `train.sh`. Prediction = mean over models of `strategy(per-model preds)` | One checkpoint | No (one model only) |
| – | No faces found | returns 0.5 | returns `UNSURE` with 0.5/0.5 | Equivalent |
| – | Inference precision | `.half()` on CUDA | float32, CPU or CUDA | Differs (harmless) |

### Checkpoint format

`weights/deepfake_detector_b7.pth`: dict `{'epoch': 30, 'state_dict': <1202 tensors, 'module.'-prefixed>, 'bce_best': np.float64(0.16684)}`.

- Upstream `train_classifier.py` saves exactly `{'epoch': current_epoch + 1, 'state_dict': model.state_dict(), 'bce_best': ...}`. The `module.` prefix comes from DataParallel training.
- Size: local file is 266,910,617 bytes. Three of the seven upstream release files (`final_111_…_0_36`, `final_777_…_0_29`, `final_777_…_0_31`) are exactly that size. The others differ by 1–4 bytes. This is consistent with a downloaded upstream checkpoint but doesn't prove it; a SHA-256 comparison would.
- `docs/training_methodology.md`'s "30 epochs" and "0.166 BCE" match this metadata. Its other hyperparameters (AdamW, cosine from 1e-3, batch 32) aren't implemented anywhere in the repo or the local notebooks.

SHA-256 of the local weights:
- `deepfake_detector_b7.pth`: `9fe4311d551a9cbaa1475dbcd6b15fccb31a1e17a8d63069e90a8899aef03b5c`
- `model_c1.pth`: `5839a0d90084a00a5e00680eb801b9b44009e8f3a48b4ba1191388d9bee34fed`

## Review claims: confirmed / corrected

| Review claim | Status |
|---|---|
| Video pipeline is a port of the DFDC 1st-place solution | Confirmed (code comments, identical functions, identical checkpoint format) |
| Upstream classifies all faces; ForgeGuard only the top one | Confirmed |
| Upstream used "a 7-model ensemble" | **Partly corrected:** 7 checkpoints are published; the README describes training 5 seeds. Either way it's an ensemble and ForgeGuard uses one model. |
| No notebook trains B7; a ResNeXt50+LSTM is trained instead | Confirmed (`Model_and_train_csv.ipynb`) |
| Image CNN eval: unseeded `random_split([1000, 500, 221])`, 82.7% → 93.7% after reloading another checkpoint | Confirmed in `train.ipynb` outputs; leakage remains an inference, not proven |
| `strict=False` load, `weights_only=False` fallbacks, `__main__` monkeypatch | Confirmed |
| Batch of 20 videos exceeds the gunicorn timeout | Arithmetic confirmed from code and README timings; not yet reproduced |
| `video_processor.py:107` docstring "Real=1, Fake=0" contradicts the code | Confirmed |

## Blockers / open questions for the owner

1. **Provenance of `deepfake_detector_b7.pth`.** Everything points to an upstream release file. Confirm, and say which file if you know. I can confirm it by downloading the three same-size release files (~800 MB) and comparing SHA-256.
2. **`model_c1.pth`.** Did you train it with `training/notebooks/train.ipynb`? Is `IMDModel` adapted from a specific repo (the code says "faithful reproduction of upstream model.py")? Which one?
3. **ResNeXt50+LSTM.** Any results? The notebook has no saved evaluation output.
4. **Datasets.** Nothing is on this machine. Phase 3 (Celeb-DF v2 test list, CASIA) and Phase 7 (GenImage) can't produce numbers until you give me paths.
5. **Deployment.** Is the Vercel project UI-only? Where's the API hosted, if anywhere? (Django has no CORS setup, so a cross-origin UI can't currently call the API.)
6. **Hardware.** CPU only? Evaluating 518 Celeb-DF videos at ~20–25 s each is about 3–3.5 h on CPU.
