# ForgeGuard Project Analysis

## 1. Project Overview

**Purpose and Problem Statement:**
ForgeGuard is a comprehensive, multi-modal, AI-powered forgery detection system. As generative media ("deepfakes") and sophisticated photo manipulation become increasingly difficult to distinguish from authentic content, there is a critical need for systems capable of identifying forgeries. ForgeGuard addresses this threat by detecting both image manipulation (tampered or photoshopped images) and video deepfakes.

**Type of Project:**
ForgeGuard is an end-to-end Machine Learning web application deployed using the Django framework. It provides a RESTful API backend and an interactive web frontend for users to upload media and view forensic analysis results.

---

## 2. Directory Structure Breakdown

```text
ForgeGuard/
│
├── api/                    # Django application for API endpoints and routing
├── calibration/            # (Empty) Intended for model probability calibration scripts
├── config/                 # Django project-level settings and WSGI/ASGI entrypoints
├── core/                   # Core machine learning pipelines and models
│   ├── exceptions/         # Custom exceptions for pipeline errors
│   ├── models/             # PyTorch model architecture definitions
│   └── pipeline/           # Data preprocessing, model inference, and heuristics
├── frontend/               # User interface assets
│   ├── static/             # CSS, JS, and vendor libraries (Bootstrap)
│   └── templates/          # HTML templates for the web views
├── logs/                   # Application logs (e.g., deepguard.log)
├── models/                 # (Empty) Alternate directory for models
├── report_images/          # Images utilized for documentation or the project report
├── scripts/                # Utility scripts (e.g., diagram generation)
├── tests/                  # Unit and integration tests
├── training/               # Code for dataset preparation and model training
│   ├── configs/            # Training configurations
│   ├── dataset/            # Dataset parsing utilities
│   └── notebooks/          # Jupyter Notebooks for data balancing, model training
├── uploaded_images/        # Storage for user-uploaded images (served as media)
├── uploaded_videos/        # Temporary storage for user-uploaded videos
├── weights/                # Saved PyTorch model checkpoint files (.pth)
│
├── .env & .env.example     # Environment variables for Django secrets
├── .gitignore              # Git ignore configuration
├── db.sqlite3              # Local SQLite database used by Django
├── manage.py               # Django CLI management script
├── requirements.txt        # Python dependencies list
├── IMAGE_GENERATION_STATUS.md
├── IMAGE_GENERATION_STRATEGY.md
├── project_report.html
└── project_report_part2.html
```

**Explanation:**
The architecture cleanly separates the web server routing (`api`, `config`) from the machine learning inference logic (`core`). Training data preparation is separated from production inference, ensuring the core web application remains lightweight.

---

## 3. File-by-File Analysis

### `api/` (Django App)
* **`urls.py`**: Defines all API routes. Maps URLs to their respective views (e.g., `/api/detect/` to `unified_api.api_detect`, `/photo/` to `image_api.predict_image`).
* **`image_api.py`**: Handles POST requests to `/api/detect-image/`. Validates file size (<100MB) and type. Saves the file temporarily to `uploaded_images/` and invokes `detect_image_bytes()` from the core pipeline. Formats results into JSON. Also contains `predict_image()` which renders the frontend view.
* **`video_api.py`**: Handles POST requests to `/api/detect-video/`. Validates video files, writes them to `uploaded_videos/`, and invokes `detect_video_file()`. Formats frame-by-frame deepfake probabilities and returns JSON. Contains specific error handling for `EmptyVideoException` and `NoVisualFramesException`.
* **`unified_api.py`**: A unified endpoint (`/api/detect/`) that automatically differentiates between images and videos based on file extensions. Also provides `/api/detect/batch` for handling multiple files in a single request.
* **`unified_detection.py`**: Backend helper that routes bytes to either the image or video processor based on the automatically detected MIME type.
* **`views.py`**: Contains standard web views like the homepage (`video_home`), the about page (`about`), and custom 404 handlers.

### `core/pipeline/` (ML Inference Logic)
* **`image_processor.py`**: The image forgery detection pipeline.
  * **Level-1 Analysis**: `_analyse_metadata()` parses EXIF tags to identify software signatures (e.g., Adobe Photoshop).
  * **Level-2 Analysis**: `_ela_image()` performs Error Level Analysis (ELA) by recompressing the image to 90% JPEG quality and calculating pixel differences.
  * **Model Interface**: Implements `IMDModel` (a custom CNN architecture) and thread-safe caching `load_model()`. Outputs a class distribution between "AUTHENTIC" and "TAMPERED".
* **`video_processor.py`**: The video deepfake detection pipeline.
  * **Face Extraction**: Uses `FaceDetectionEngine` (wrapping MTCNN from `facenet-pytorch`) to crop the most prominent face from video frames. It meticulously replicates training-time extraction logic (scaling, bounding box thresholds).
  * **Preprocessing**: `preprocess_frame()` reshapes extracted faces using isotropic resizing, pads them to 380x380, and applies ImageNet normalization.
  * **Model Architecture**: Rebuilds the `DeepFakeClassifier` utilizing `timm`'s `tf_efficientnet_b7.ns_jft_in1k` backbone.
  * **Heuristics**: Includes `confident_strategy()` which aggregates per-frame probabilities into a final video verdict. A video is flagged if enough frames surpass a high-confidence fake threshold.

### `config/` (Django Configuration)
* **`settings.py`**: Contains project settings. SQLite3 is configured as the default DB. Media files are stored in `uploaded_images/`. Static files are tracked in `frontend/static/`. Sets up a robust logging configuration targeting `logs/deepguard.log`.

### `training/notebooks/` (Data & Training Scripts)
* **`preprocessing.ipynb`, `copy real and fake .ipynb`**: Utility scripts to organize, balance, and clean training videos.
* **`Create_csv_from_glob.ipynb`**: Traverses video folders to create manifest files indicating real vs fake labels for the dataloader.
* **`train.ipynb`, `Model_and_train_csv.ipynb`**: Defines PyTorch DataLoaders, optimizer, and training loops used to fine-tune the EfficientNet B7 model on the deepfake dataset.

### Root Files
* **`manage.py`**: The standard Django entry script for running the server, migrations, etc.
* **`requirements.txt`**: Specifies exact versions. Critical note: PyTorch must be installed via Conda to ensure CUDA availability, while other libraries (Django, numpy, pandas, opencv-python) are installed via pip.

---

## 4. Data & Dataset Details

While the datasets themselves are not present in the repository due to size, explicit evidence in the code and notebook names indicates the use of:
* **CASIA Tampered Image Detection Dataset**: The `IMDModel` in `image_processor.py` was trained on CASIA (explicitly mentioned in the docstrings). It relies on ELA inputs to learn artifacts.
* **Deepfake Detection Challenge (DFDC) Dataset**: The video deepfake model explicitly cites the "DFDC challenge solution". Notebooks like `Model_and_train_csv.ipynb` handle balanced CSV loading of `REAL` and `FAKE` videos spanning thousands of clips. The system is calibrated on over 100,000 clips (referenced in report texts).

---

## 5. Workflow / Data Flow

### Image Detection Workflow:
1. **Upload**: User uploads an image via the web UI (`/photo/`) or API (`/api/detect-image/`).
2. **Validation**: `image_api.py` checks size (<100MB) and format (e.g., .jpg, .png).
3. **Level-1 (Metadata)**: `image_processor.py` scans EXIF headers. If editing software is found, it is logged.
4. **Level-2 (ELA Transformation)**: The image is converted into an Error Level Analysis matrix to highlight recompression anomalies.
5. **Level-2 (CNN Classification)**: The ELA image is resized to 128x128, normalized, and passed into `IMDModel`.
6. **Response**: Softmax probabilities determine the label (AUTHENTIC vs. TAMPERED). The result, alongside Level-1 notes, is serialized and returned.

### Video Detection Workflow:
1. **Upload**: User uploads a video (`/api/detect-video/`).
2. **Frame Extraction**: `VideoReader` extracts 32 evenly spaced frames using OpenCV (`cv2.VideoCapture`).
3. **Face Extraction**: MTCNN scans each frame. The highest-probability face is extracted, expanded with 33% padding, and cropped.
4. **Preprocessing**: The face is isotropically resized to 380x380 and ImageNet-normalized.
5. **Inference**: A pre-loaded EfficientNet B7 backbone (`DeepFakeClassifier`) processes batches of faces, returning a deepfake probability per frame.
6. **Aggregation**: `confident_strategy()` aggregates frame predictions. If over ~40% of frames are confidently fake (>0.8 probability), the video is labeled FAKE; otherwise, an average is taken.
7. **Response**: System returns the final classification, individual frame probabilities, and processing time.

---

## 6. Models / Algorithms

### Model 1: Image Manipulation Detector (`IMDModel`)
* **Architecture**: A lightweight Custom CNN.
  * Two Convolutional + MaxPooling layers with Batch Normalization.
  * Flattening into Dense layers (1024 -> 64 -> 2).
  * Output is Softmax across 2 classes.
* **Input**: 128x128x3 Error Level Analysis images.
* **Weights File**: `weights/model_c1.pth`.

### Model 2: Video Deepfake Detector (`DeepFakeClassifier`)
* **Architecture**: `tf_efficientnet_b7.ns_jft_in1k` (EfficientNet B7 Noisy Student).
  * Standard EfficientNet encoder loaded via the `timm` library.
  * Adaptive Average Pooling followed by a Linear layer projecting 2560 features to a 1-dimensional logit.
* **Face Extractor**: MTCNN (`facenet-pytorch`). Thresholds `[0.7, 0.8, 0.8]`.
* **Input**: 380x380x3 padded face crops normalized with ImageNet stats.
* **Weights File**: `weights/deepfake_detector_b7.pth`.

---

## 7. Technologies & Dependencies

* **Web Framework**: Django 5.0.6 (provides the REST API and template engine).
* **Deep Learning Framework**: PyTorch 2.3.1 (with CUDA 12.1 for GPU acceleration).
* **Computer Vision**: OpenCV (`opencv-python`), Pillow.
* **Pre-trained Models**: `timm` (PyTorch Image Models) for EfficientNet, `facenet-pytorch` for MTCNN face extraction.
* **Data Handling**: NumPy, Pandas.
* **Database**: SQLite3 (Local file-based tracking native to Django).

---

## 8. Configuration & Execution

**Environment Setup:**
The project relies heavily on CUDA availability for timely video processing. A Conda environment is mandatory to ensure appropriate PyTorch/CUDA bindings.
1. `conda create -n ForgeGuard python=3.13`
2. `conda activate ForgeGuard`
3. `conda install pytorch torchvision pytorch-cuda=12.1 -c pytorch -c nvidia`
4. `pip install -r requirements.txt`

**Execution:**
Start the development server using Django's management script:
`python manage.py runserver`

**Key Configurations:**
* In `config/settings.py`, `MAX_UPLOAD_SIZE` is capped at 100 MB.
* Device selection is auto-managed (`_select_device()` defaults to `cuda` if available).
* Thread-safe caching mechanisms (`_MODEL_LOCK`) are employed in both pipelines to load PyTorch checkpoints once in memory across API requests.

---

## 9. Observations & Issues

1. **Missing Test Data Coverage**: `tests/` contains structural folders (`fixtures`, `unit`, `integration`) but no active test files were found. Automated testing is effectively zero.
2. **Weight Files Missing From Analysis**: The `.pth` weight files exist in `weights/`, but some aliases or legacy files are present (`final_777_b7_ns_0_29.pth`, `model_97_acc_100_frames_FF_data.pt`). Ensure production uses only the intended configurations.
3. **Memory Safety on High Concurrency**: Deep learning models are cached effectively via singletons (`_MODEL_LOCK`), avoiding OOM (Out-of-Memory) errors on model loading, but highly concurrent video frame batching (`batch_size=32`) could potentially exhaust VRAM.
4. **Empty Directories**: Several directories (`models`, `calibration`, `core/exceptions`) exist but contain no files. They appear to be scaffolding for unimplemented features.
5. **No Database Models**: `api/models.py` is empty (aside from boilerplate). While `db.sqlite3` exists, the system operates statelessly. Uploads are written to disk temporarily for inference but aren't actively indexed or tracked via Django ORM.
