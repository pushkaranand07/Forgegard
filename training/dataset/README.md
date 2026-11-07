# Datasets

No dataset is stored in this repo. All of them are research-only and non-commercial; see [CREDITS.md](../../CREDITS.md). Earlier versions of this file described a `dataset_map.csv` manifest and a directory layout that no code in the project uses. They've been removed.

## Video

**The deployed video model was not trained here.** It's a pretrained DFDC checkpoint from Selim Seferbekov's solution, trained by its author on the DFDC training set.

The local notebooks used DFDC and Celeb-DF v2 for the earlier ResNeXt50+LSTM experiment only:

| Notebook | Data | What it does |
|---|---|---|
| `Create_csv_from_glob.ipynb` | Celeb-DF v2 `YouTube-real/` | Lists video files into a CSV |
| `Remove_audio_altered_files.ipynb`, `copy real and fake .ipynb` | DFDC `dfdc_train_part_8/` | Drops audio-only fakes and splits videos by `metadata.json` label |
| `for_Balancing_data.ipynb` | DFDC `metadata.json` | Balances real and fake counts |
| `preprocessing.ipynb` | DFDC, Celeb-DF | Writes face-only clips |

**Planned evaluation (out of distribution):** Celeb-DF v2 official test list (`List_of_testing_videos.txt`, 518 videos).

**Preprocessing the video model expects** (fixed by the upstream weights, see `core/pipeline/video_processor.py`):
- RGB frames (convert from OpenCV's BGR exactly once);
- MTCNN face crop with one-third padding;
- isotropic resize to 380 px with centre zero-padding;
- ImageNet mean/std normalisation.

## Image

**CASIA** tampering images were used to train `IMDModel` (`train.ipynb`):
- folders `auth_model/` (authentic) and `sp_model/` (spliced), 1,721 images in total;
- labels come from the filename: an `Au_` prefix means authentic;
- the inputs are **ELA images computed beforehand**. The script that produced them isn't in the project, so whether its parameters match inference (JPEG quality 90, ×10 amplification) is unverified.

ELA is specific to the image model. It plays no part in the video pipeline.
