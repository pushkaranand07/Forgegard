# Credits & Licenses

ForgeGuard serves two models. One is third-party; the other I trained myself on an architecture adapted from public code. This file lists everything the project depends on that I didn't write, and the terms that come with it.

## Models and model code

### Video deepfake classifier: DFDC 1st-place solution

- **Author:** Selim Seferbekov ([@selimsef](https://github.com/selimsef))
- **Source:** <https://github.com/selimsef/dfdc_deepfake_challenge>
- **License:** MIT
- **What ForgeGuard uses:**
  - **Weights.** `weights/deepfake_detector_b7.pth` is one of the seven EfficientNet-B7 checkpoints published in that repo's `0.0.1` release, downloaded as-is and not retrained. The checkpoint stores `{'epoch': 30, 'state_dict', 'bce_best': 0.1668}` in the format written by upstream `training/pipelines/train_classifier.py`. It is byte-identical to the release asset `final_777_DeepFakeClassifier_tf_efficientnet_b7_ns_0_29` (SHA-256 `9fe4311d551a…`, checked on 2026-11-07). `scripts/download_weights.py` fetches it from that release, so ForgeGuard does not re-host it.
  - **Code ported into `core/pipeline/video_processor.py`:** `DeepFakeClassifier` (architecture), `confident_strategy` (aggregation), `isotropically_resize_image` / `put_to_center` (preprocessing), and the MTCNN face-crop settings (thresholds `[0.7, 0.8, 0.8]`, half-resolution detection, one-third padding).
  - **Known deviation:** upstream classifies every detected face in a frame and averages an ensemble of models. ForgeGuard currently classifies only the highest-confidence face per frame with a single checkpoint. See [reports/00_recon.md](reports/00_recon.md).
- The upstream checkpoints were trained on the DFDC dataset (below), so its terms apply to the weights.

### Image manipulation classifier: ELA + small CNN (`IMDModel`)

- **Weights:** `weights/model_c1.pth` were trained by me in `training/notebooks/train.ipynb` (local, not in git) on CASIA images.
- **Architecture and ELA preprocessing:** adapted from a public repository. **The source URL is still to be added** (the code comment in `core/pipeline/image_processor.py` calls it a "faithful reproduction of upstream model.py").

### Libraries the models depend on

| Component | Used for | License |
|---|---|---|
| [timm](https://github.com/huggingface/pytorch-image-models) (Ross Wightman / Hugging Face) | `tf_efficientnet_b7.ns_jft_in1k` architecture definition (ForgeGuard creates it with `pretrained=False`; all weights come from the DFDC checkpoint) | Apache-2.0 |
| EfficientNet (Tan & Le, ICML 2019); Noisy Student (Xie et al., CVPR 2020) | Backbone design and the pretraining the upstream author started from | Paper citations |
| [facenet-pytorch](https://github.com/timesler/facenet-pytorch) (Tim Esler) | MTCNN face detector and its bundled pretrained weights | MIT |
| MTCNN (Zhang et al., IEEE SPL 2016) | Face detection method | Paper citation |
| Error Level Analysis (Neal Krawetz, "A Picture's Worth…", Black Hat 2007) | ELA technique | Technique citation |
| PyTorch, torchvision, OpenCV, Pillow, NumPy | Inference and image/video I/O | BSD-3 / BSD-3 / Apache-2.0 / MIT-CMU / BSD-3 |
| Django, WhiteNoise, gunicorn | Serving | BSD-3 / MIT / MIT |
| React, Vite, Tailwind CSS (see `web/package.json`) | Web UI | MIT |

## Datasets

None of these datasets are redistributed in this repo. Each comes with its own terms, which **restrict use to non-commercial research**. Check the current terms at the source before any use beyond research or education.

| Dataset | Role in ForgeGuard | Terms |
|---|---|---|
| **DFDC** (Deepfake Detection Challenge, Dolhansky et al. 2020; Meta / Kaggle) | Training data of the upstream B7 weights. DFDC parts were also used in my earlier ResNeXt50+LSTM experiment. | DFDC data-use terms: non-commercial research |
| **Celeb-DF v2** (Li et al., CVPR 2020) | Used in the earlier ResNeXt50+LSTM experiment; planned out-of-distribution test set for the video model | Research use only, by request; non-commercial |
| **CASIA Image Tampering Detection Evaluation Database** (Dong, Wang & Tan, ChinaSIP 2013) | Training/validation/test data for `IMDModel` | Research use only |

**Consequence:** because the deployed weights were trained on these datasets, ForgeGuard as it stands is suitable for research, education and demonstration, **not commercial use**.
