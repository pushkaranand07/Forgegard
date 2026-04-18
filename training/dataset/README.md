# Dataset Architecture & Preprocessing

## Directory Structure
Training relies heavily on absolute dataset integrity. Ensure the raw metadata files are synced into this module.

```text
dataset/
├── df_raw/                # (Deepfake Raw MP4 extracts)
├── real_raw/              # (Authentic Raw MP4 extracts)
├── face_crops/
│   ├── df/                # Extracted 380x380 synthetics
│   └── real/              # Extracted 380x380 authentic
├── metadata/
│   └── dataset_map.csv    # Binary tag linkage
└── cache/                 # Temporary Pytorch tensor sets
```

## Dataset Manifests
The `dataset_map.csv` is internally used to bridge multi-folder structures into the `__getitem__` index loop. Do not manually mutate this document. The CSV contains exactly two rows: `filename`, `label`. For multi-class tracking, `original_id` is maintained locally but inherently discarded prior to Binary Classification.

## Preprocessing Considerations
Because the CNN Backbone utilizes `tf_efficientnet_b7_ns` pre-trained on ImageNet, we must mimic ImageNet channel formatting. Do not configure your training loaders using `BGR` formatting native to OpenCV. Use `core.pipeline.video_processor` bounds scaling to handle padding thresholds.

## Synthetic Expansion
Data augmentation applied via PyTorch `Transforms` heavily skews toward geometric noise (rotations, cropping, flips) rather than color manipulation. Applying extreme color manipulation mathematically damages the ELA properties required to ascertain real images from generative manipulations. Color threshold jittering is restricted to `< 1.2%`.
