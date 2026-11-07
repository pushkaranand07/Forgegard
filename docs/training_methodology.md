# Training & Model Provenance

This document records how each model in ForgeGuard was obtained. It covers only what the notebooks in `training/notebooks/` (kept locally, gitignored) and the checkpoint files actually show. Hyperparameters that nothing in the project implements have been removed from earlier versions of this document.

## Summary

| Model | Deployed file | Who trained it | Status |
|---|---|---|---|
| Video: EfficientNet-B7 `DeepFakeClassifier` | `weights/deepfake_detector_b7.pth` | **Selim Seferbekov** (DFDC 1st-place solution), downloaded pretrained | Deployed |
| Image: ELA + `IMDModel` | `weights/model_c1.pth` | Me, in `train.ipynb` (architecture adapted from public code) | Deployed |
| Video: ResNeXt50 + LSTM | none | Me, in `Model_and_train_csv.ipynb` | Experiment only, not deployed, no saved evaluation |

## 1. Video model (deployed): pretrained DFDC B7

- **Source:** <https://github.com/selimsef/dfdc_deepfake_challenge> (MIT). It's one of the seven B7 checkpoints in the `0.0.1` release. I didn't train or fine-tune it.
- **Checkpoint contents:** `{'epoch': 30, 'state_dict': <1202 tensors, 'module.' prefix from DataParallel>, 'bce_best': 0.1668}`.
  - `bce_best` is the upstream author's best validation BCE on their own DFDC split. It isn't a ForgeGuard measurement.
- **Training data (upstream):** the DFDC training set. For the upstream training recipe (augmentations, optimiser, schedule), see that repo's `configs/` and `training/`. ForgeGuard doesn't reproduce it.

**What I did with it:** ported the inference path into `core/pipeline/video_processor.py` and checked it against upstream `kernel_utils.py`:

| Step | Matches upstream? |
|---|---|
| BGR→RGB conversion once after decoding | Yes |
| MTCNN `thresholds=[0.7, 0.8, 0.8]`, detection on a half-resolution copy, boxes scaled ×2, one-third padding | Yes |
| Isotropic resize to 380 px (INTER_AREA down / INTER_CUBIC up), zero-padded centring | Yes |
| ImageNet mean/std normalisation | Yes |
| `confident_strategy` (t = 0.8; > 11 and > n/2.5 confident fakes; > 90 % below 0.2) | Yes |
| Faces per frame | **No.** Upstream classifies every detected face; ForgeGuard keeps only the highest-confidence one |
| Number of models | **No.** Upstream averages an ensemble; ForgeGuard uses one checkpoint |

**Why EfficientNet-B7 at 380 px:** that's what upstream trained, so the input size and backbone are fixed by the weights rather than chosen here.
- EfficientNet uses *compound scaling*: depth, width and input resolution grow together by fixed coefficients.
- The network outputs a single **logit** per face. ForgeGuard applies the sigmoid afterwards, giving P(fake) for that face.

**Bug found during integration:** an earlier version of the pipeline gave unstable scores biased towards FAKE on real videos. The fix was to make frame colour order and MTCNN crop settings match upstream exactly (one BGR→RGB conversion, the same thresholds and padding). There's no committed before/after measurement of this. The planned golden-sample tests will guard against the bug coming back.

## 2. Image model (deployed): ELA + `IMDModel`

**Notebook:** `training/notebooks/train.ipynb`.

**Data:**
- 1,721 images from CASIA, read from precomputed folders `auth_model/` and `sp_model/`.
- The label comes from the filename: an `Au_` prefix means authentic (1), otherwise tampered (0).
- 1,721 matches CASIA v1.0's size (800 authentic + 921 spliced).
- The notebook loads ELA images that were already computed. The script that generated them isn't in the project, so it's **unverified** whether its JPEG quality and scaling match inference (quality 90, ×10 in `core/pipeline/image_processor.py`).

**Model:** `IMDModel`, two conv+BN+maxpool blocks (64 and 16 channels), then a three-layer MLP to 2 classes, on a 128×128 input normalised to [0, 1]. Architecture adapted from public code (source URL pending, see [CREDITS.md](../CREDITS.md)).

**The deployed checkpoint has a different architecture from the notebook's current code.** The `IMDModel` cell in `train.ipynb` has `BatchNorm1d` after each hidden linear layer and a final `Softmax`. The deployed `model_c1.pth` (the reloaded `model_c1_e100_v2` checkpoint) has **neither**: its MLP is `Linear(14400,1024) → ReLU → Linear(1024,64) → ReLU → Linear(64,2)` and it outputs logits. So the deployed model came from an earlier version of the notebook, not from the 100-epoch run whose outputs are printed. The serving code didn't notice: the checkpoint was a pickled module that carried its own layers, and inference applied softmax whenever outputs didn't sum to 1. Phase 2 fixed `IMDModel` in `core/pipeline/image_processor.py` to match the deployed weights, and the model now loads strictly.

**Training setup, as in the notebook:**
- Adam, lr 1e-4, batch size 128, 100 epochs.
- `CrossEntropyLoss`, with validation every 10 epochs.
- Split: `random_split(dataset, [1000, 500, 221])` (train / validation / test).

**Problems found in this setup** (they're why no notebook number is reported as a result):

1. **Unseeded split.** `random_split` is called without a generator or seed, so every run of the notebook produces a different train/test partition.
2. **Likely test leakage.** The notebook's own outputs show:
   - after the 100-epoch run: test accuracy **0.827**, test loss 0.709, final train loss 0.0009 (heavy overfitting);
   - then a *different* checkpoint, `model_c1_e100_v2.pth` from an earlier run, is loaded and scored on the *current* test split: accuracy **0.937**, F1 0.934, confusion matrix `[[108, 8], [6, 99]]`;
   - that checkpoint was saved as the deployed `model_c1.pth`.

   Because the earlier run used a different random split, many of these 221 test images were probably in that checkpoint's training set. The 0.937 is therefore likely inflated and **isn't a valid held-out result**.
3. **Small test set.** Even without leakage, 221 images give a 95 % confidence interval of roughly ±3 percentage points, and it's in-distribution CASIA only.
4. **Double softmax in the notebook's current code.** That version of the model ends in `nn.Softmax`, and `CrossEntropyLoss` applies log-softmax again, which weakens gradients. The deployed checkpoint doesn't have this layer (see above), so this affects the notebook's 0.827 run, not the served model.
5. **Saved as a pickled module.** `torch.save(model, ...)` stored the whole object, which needed unsafe unpickling to load. **Fixed:** `scripts/convert_imd_to_state_dict.py` re-saved it as a `state_dict`, after checking the outputs are bit-identical on random inputs. It now loads with `weights_only=True`.

**Planned:** re-evaluate on a seeded, committed split with bootstrap confidence intervals and a recompression stress test.

## 3. Earlier experiment (not deployed): ResNeXt50 + LSTM

- **Notebooks:**
  - `Model_and_train_csv.ipynb`: model and training;
  - `preprocessing.ipynb`: face-only clip extraction;
  - `Create_csv_from_glob.ipynb`, `copy real and fake .ipynb`, `Remove_audio_altered_files.ipynb`, `for_Balancing_data.ipynb`: dataset assembly from Celeb-DF v2 and DFDC part 8;
  - `deepfake-starter-kit.ipynb`: DFDC exploration.
- **Model:** torchvision `resnext50_32x4d` (ImageNet-pretrained) per frame at 112×112, followed by an LSTM over the frame sequence and a 2-way classifier. Settings in the notebook: 20 epochs, lr 1e-5, batch size 4.
- **Data:** face-only clips from Celeb-DF v2 (real and fake) and DFDC (real and fake).
- **Result:** the notebook has no saved outputs, so no result exists. This model was replaced by the pretrained DFDC B7 in the deployed system and isn't used anywhere in the code.
