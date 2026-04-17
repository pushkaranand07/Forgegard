"""
Contains the ResNeXt-50 + LSTM model definition, dataset helper, utility
functions, and all Django view functions that serve both the web UI pages
and the JSON API endpoints.
"""

from django.shortcuts import render, redirect
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.views.decorators.csrf import csrf_exempt
import torch
import torchvision
from torchvision import transforms, models
from torch.utils.data import DataLoader
from torch.utils.data.dataset import Dataset
import os
import numpy as np
import cv2
import threading

try:
    import matplotlib.pyplot as plt
except ImportError:
    plt = None

try:
    import face_recognition
except ImportError:
    face_recognition = None

from torch.autograd import Variable
import time
from torch import nn
import json
import glob
import copy
import shutil
import re
import uuid
from PIL import Image as pImage
from django.conf import settings
from .forms import VideoUploadForm

# ─────────────────────────────────────────────
# Template names
# ─────────────────────────────────────────────
HOME_TEMPLATE          = 'index.html'
VIDEO_RESULT_TEMPLATE  = 'predict.html'
ABOUT_TEMPLATE         = 'about.html'

# Legacy aliases kept for any external references
index_template_name        = HOME_TEMPLATE
predict_template_name      = VIDEO_RESULT_TEMPLATE
about_template_name        = ABOUT_TEMPLATE

# ─────────────────────────────────────────────
# Allowed file extensions
# ─────────────────────────────────────────────
ALLOWED_VIDEO_EXTENSIONS = {'mp4', 'gif', 'webm', 'avi', '3gp', 'wmv', 'flv', 'mkv'}

# ─────────────────────────────────────────────
# Pre-processing constants
# ─────────────────────────────────────────────
FRAME_SIZE = 224  # Height and width each frame is resized to before being fed into the model

IMAGENET_MEAN = [0.485, 0.456, 0.406]
IMAGENET_STD  = [0.229, 0.224, 0.225]

# Inverse-normalise a tensor back to [0, 1] pixel range for visualisation
denormalize = transforms.Normalize(
    mean=[-m / s for m, s in zip(IMAGENET_MEAN, IMAGENET_STD)],
    std=[1.0 / s for s in IMAGENET_STD],
)

softmax_fn = nn.Softmax(dim=1)

# Device selection: use GPU when available, otherwise fall back to CPU
device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')

# The same spatial transforms applied to every frame during inference
frame_transforms = transforms.Compose([
    transforms.ToPILImage(),
    transforms.Resize((FRAME_SIZE, FRAME_SIZE)),
    transforms.ToTensor(),
    transforms.Normalize(IMAGENET_MEAN, IMAGENET_STD),
])

# Ensure required upload/output folders exist at startup
_required_dirs = [
    os.path.join(settings.PROJECT_DIR, 'models'),
    os.path.join(settings.PROJECT_DIR, 'uploaded_images'),
    os.path.join(settings.PROJECT_DIR, 'uploaded_videos'),
]
for _d in _required_dirs:
    os.makedirs(_d, exist_ok=True)


# ─────────────────────────────────────────────
# Model Architecture
# ─────────────────────────────────────────────

class DeepfakeDetectorModel(nn.Module):
    """
    Two-stage deep neural network for deepfake detection.

    Stage 1 – Spatial feature extraction: a pretrained ResNeXt-50 CNN trunk
    processes each video frame independently and outputs a feature map.

    Stage 2 – Temporal modelling: an LSTM ingests the per-frame features in
    sequence order and captures temporal inconsistencies that are characteristic
    of deepfake videos. The final hidden state is classified as REAL or FAKE.
    """

    def __init__(
        self,
        num_classes: int,
        latent_dim: int = 2048,
        lstm_layers: int = 1,
        hidden_dim: int = 2048,
        bidirectional: bool = False,
    ):
        super().__init__()

        # Load a pretrained ResNeXt-50; strip the final FC + avg-pool layers so
        # we get raw spatial feature maps (shape: batch, channels, H, W).
        backbone = models.resnext50_32x4d(
            weights=models.ResNeXt50_32X4D_Weights.DEFAULT
        )
        self.model = nn.Sequential(*list(backbone.children())[:-2])

        # The original code contained a bug: `bidirectional` was passed as the 4th
        # positional argument to nn.LSTM. In PyTorch, the 4th argument is `bias`,
        # not `bidirectional`. To successfully load the pre-trained weights, we MUST
        # reproduce this exact behaviour: bias=bidirectional, bidirectional=False.
        self.lstm = nn.LSTM(latent_dim, hidden_dim, lstm_layers, bias=bidirectional)
        self.relu = nn.LeakyReLU()
        self.dp = nn.Dropout(0.4)

        self.linear1 = nn.Linear(hidden_dim, num_classes)

        # Collapse spatial H×W into a single vector per frame
        self.avgpool = nn.AdaptiveAvgPool2d(1)

    def forward(self, x: torch.Tensor):
        """
        Args:
            x: Tensor of shape (batch, seq_length, C, H, W)
        Returns:
            feature_maps: Raw CNN spatial maps – used for Class Activation Maps
            logits:       Classification scores of shape (batch, num_classes)
        """
        batch_size, seq_length, C, H, W = x.shape

        # Merge batch and sequence dimensions so every frame is processed in
        # one CNN forward pass: (batch * seq, C, H, W)
        x = x.view(batch_size * seq_length, C, H, W)

        # Extract spatial feature maps: (batch * seq, channels, h, w)
        feature_maps = self.model(x)

        # Pool each feature map down to a vector: (batch * seq, channels, 1, 1)
        pooled = self.avgpool(feature_maps)
        num_channels = pooled.shape[1]

        # Restore the sequence dimension: (batch, seq, channels)
        pooled = pooled.view(batch_size, seq_length, num_channels)

        # Run LSTM over the frame sequence; take the final hidden state
        lstm_out, _ = self.lstm(pooled, None)

        # Classify using the last time step's output
        logits = self.dp(self.linear1(lstm_out[:, -1, :]))

        return feature_maps, logits


# ─────────────────────────────────────────────
# Dataset Helper
# ─────────────────────────────────────────────

class VideoFrameDataset(Dataset):
    """
    Loads frames from a list of video file paths.

    For each video, extracts up to `sequence_length` frames, applies face
    detection and cropping (when face_recognition is available), and returns a
    stacked tensor suitable for the DeepfakeDetectorModel.

    If the video contains fewer frames than `sequence_length`, the last frame
    is repeated to fill the sequence – ensuring a stable input shape for the
    model at all times.
    """

    def __init__(self, video_paths: list, sequence_length: int = 60, transform=None):
        self.video_paths   = video_paths
        self.sequence_length = sequence_length
        self.transform     = transform

    def __len__(self):
        return len(self.video_paths)

    def __getitem__(self, idx: int):
        if face_recognition is None:
            raise RuntimeError(
                "face_recognition library is not installed. "
                "Install project dependencies to enable face detection and cropping."
            )

        video_path = self.video_paths[idx]
        frames = []

        for frame_idx, raw_frame in enumerate(self._extract_frames(video_path)):
            # OpenCV yields BGR; face_recognition expects RGB
            rgb_frame = cv2.cvtColor(raw_frame, cv2.COLOR_BGR2RGB)

            # Detect faces and crop to the first found face, if any
            detected_faces = face_recognition.face_locations(rgb_frame)
            if detected_faces:
                top, right, bottom, left = detected_faces[0]
                cropped_bgr = raw_frame[top:bottom, left:right, :]
                rgb_frame   = cv2.cvtColor(cropped_bgr, cv2.COLOR_BGR2RGB)

            frames.append(self.transform(rgb_frame))

            if len(frames) == self.sequence_length:
                break

        if len(frames) == 0:
            raise ValueError(f"No frames could be extracted from: {video_path}")

        # Pad short videos by repeating the last frame
        if len(frames) < self.sequence_length:
            last_frame = frames[-1]
            while len(frames) < self.sequence_length:
                frames.append(last_frame.clone())

        # Stack and add a batch dimension: (1, seq, C, H, W)
        stacked = torch.stack(frames[:self.sequence_length])
        return stacked.unsqueeze(0)

    def _extract_frames(self, video_path: str):
        """Generator that yields individual BGR frames from a video file."""
        cap = cv2.VideoCapture(video_path)
        success = True
        while success:
            success, frame = cap.read()
            if success:
                yield frame
        cap.release()


# ─────────────────────────────────────────────
# Utility Functions
# ─────────────────────────────────────────────

def make_artifact_map(img_bgr: np.ndarray) -> np.ndarray:
    """
    Generate a single-channel 'artifact map' emphasizing high-frequency
    and residual noise patterns typical of AI generation/GANs.
    """
    gray = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2GRAY).astype(np.float32)
    # Edge-preserving denoising to isolate residuals
    denoised = cv2.bilateralFilter(gray, d=7, sigmaColor=30, sigmaSpace=30)
    residual = np.abs(gray - denoised)

    # Frequency-domain magnitude proxy
    fft = np.fft.fftshift(np.fft.fft2(gray))
    mag = np.log1p(np.abs(fft))
    mag = (mag - mag.min()) / (mag.max() - mag.min() + 1e-8)

    # Blend residual and magnitude into final map
    residual = (residual - residual.min()) / (residual.max() - residual.min() + 1e-8)
    artifact = 0.6 * residual + 0.4 * mag
    return artifact.astype(np.float32)


def tensor_to_numpy_image(tensor: torch.Tensor, video_stem: str = "") -> np.ndarray:
    """
    Convert a CxHxW tensor (normalised to ImageNet stats) back into a NumPy
    image array in [0, 1] range, ready for matplotlib or cv2 operations.
    """
    image = tensor.to("cpu").clone().detach()
    image = image.squeeze()
    image = denormalize(image)
    image = image.numpy().transpose(1, 2, 0)
    image = image.clip(0, 1)
    return image


def visualise_frame(tensor: torch.Tensor) -> None:
    """Display a frame tensor using matplotlib (development / debug helper)."""
    if plt is None:
        return
    image = tensor.cpu().numpy().transpose(1, 2, 0)
    b, g, r = cv2.split(image)
    image = cv2.merge((r, g, b))
    image = image * [0.22803, 0.22145, 0.216989] + [0.43216, 0.394666, 0.37645]
    image = image * 255.0
    plt.imshow(image.astype('uint8'))
    plt.show()


def run_inference(model: DeepfakeDetectorModel, img_tensor: torch.Tensor,
                  save_dir: str = './', video_stem: str = "") -> list:
    """
    Run a single forward pass through the model and return the prediction.

    Args:
        model:      Trained DeepfakeDetectorModel (in eval mode).
        img_tensor: Tensor of shape (1, seq, C, H, W).
        save_dir:   Directory path (unused here; kept for API consistency).
        video_stem: Base filename without extension (unused here).

    Returns:
        [predicted_class (int), confidence_percent (float)]
        Predicted class: 1 = REAL, 0 = FAKE.
    """
    with torch.no_grad():
        # MARK: Model used here (forward pass)
        _, logits = model(img_tensor.to(device))

    probabilities = softmax_fn(logits)
    _, predicted_class = torch.max(probabilities, 1)
    confidence_pct = probabilities[:, int(predicted_class.item())].item() * 100

    print(f"[Inference] Class: {predicted_class.item()}  Confidence: {confidence_pct:.2f}%")
    return [int(predicted_class.item()), confidence_pct]


def run_inference_with_probs(model: nn.Module, img_tensor: torch.Tensor,
                             art_tensor: torch.Tensor = None) -> dict:
    """
    Run a forward pass through the DeepfakeDetectorModel and return
    calibrated per-class probabilities.

    Args:
        model:      Loaded DeepfakeDetectorModel in eval mode.
        img_tensor: RGB video sequence tensor of shape (1, seq, C, H, W).
        art_tensor: Unused — kept for API compatibility only.

    Returns:
        {
            "predicted_class": int   (1 = REAL, 0 = FAKE),
            "confidence_pct":  float,
            "real_prob":       float in [0, 1],
            "fake_prob":       float in [0, 1],
        }
    """
    model.eval()
    with torch.no_grad():
        _, logits = model(img_tensor.to(device))
        probabilities = softmax_fn(logits).squeeze(0).detach().cpu()
        real_idx = int(getattr(settings, 'REAL_CLASS_INDEX', 1))
        fake_idx = int(getattr(settings, 'FAKE_CLASS_INDEX', 0))
        real_prob = float(probabilities[real_idx].item())
        fake_prob = float(probabilities[fake_idx].item())

    predicted_class = 1 if real_prob >= 0.5 else 0
    confidence_pct = max(real_prob, fake_prob) * 100.0

    return {
        "predicted_class": predicted_class,
        "confidence_pct": confidence_pct,
        "real_prob": real_prob,
        "fake_prob": fake_prob,
    }


def generate_class_activation_map(
    frame_index: int,
    model: DeepfakeDetectorModel,
    img_tensor: torch.Tensor,
    save_dir: str = './',
    video_stem: str = '',
) -> str:
    """
    Generate a Class Activation Map (CAM) heatmap for a single frame and
    overlay it on the corresponding video frame.

    The heatmap highlights the spatial regions that most influenced the
    model's prediction – useful for interpretability.

    Args:
        frame_index: Which frame in the sequence to generate the map for.
        model:       Trained model (must be in eval mode).
        img_tensor:  Input tensor of shape (1, seq, C, H, W).
        save_dir:    Directory where the heatmap PNG will be saved.
        video_stem:  Filename stem used for naming the output file.

    Returns:
        Absolute path to the saved heatmap image.
    """
    # MARK: Model used here (feature extraction for CAM)
    feature_maps, logits = model(img_tensor.to(device))
    classifier_weights    = model.linear1.weight.detach().cpu().numpy()
    probabilities         = softmax_fn(logits)
    _, predicted_class    = torch.max(probabilities, 1)
    class_idx             = np.argmax(probabilities.detach().cpu().numpy())

    bz, num_channels, fmap_h, fmap_w = feature_maps.shape

    # Dot product of flattened feature map with the classifier weights
    activation = np.dot(
        feature_maps[frame_index].detach().cpu().numpy().reshape((num_channels, fmap_h * fmap_w)).T,
        classifier_weights[class_idx, :].T,
    )
    activation_map = activation.reshape(fmap_h, fmap_w)

    # Normalise to [0, 255] for colour mapping
    activation_map -= activation_map.min()
    if activation_map.max() > 0:
        activation_map /= activation_map.max()
    activation_uint8 = np.uint8(255 * activation_map)

    resized_map = cv2.resize(activation_uint8, (FRAME_SIZE, FRAME_SIZE))
    heatmap     = cv2.applyColorMap(resized_map, cv2.COLORMAP_JET)

    original_frame = tensor_to_numpy_image(img_tensor[:, -1, :, :, :], video_stem)
    blended        = heatmap * 0.5 + original_frame * 0.8 * 255

    heatmap_filename = f"{video_stem}_cam_{frame_index}.png"
    output_path      = os.path.join(settings.PROJECT_DIR, 'uploaded_images', heatmap_filename)
    cv2.imwrite(output_path, blended)

    return output_path


# ─────────────────────────────────────────────
# Model Selection & Caching
# ─────────────────────────────────────────────

def select_best_model_file(sequence_length: int) -> str:
    """
    Search the `models/` directory for a .pt file that matches the requested
    sequence length.

    Expected filename format: ``<name>_<accuracy>_acc_<seq>_<rest>.pt``
    e.g. ``model_84_acc_100_frames_final.pt``

    If several models match the same sequence length, the one with the highest
    accuracy value (parsed from the filename) is returned.  If no match is
    found, the first available model is returned as a fallback.

    Returns:
        The filename (not the full path) of the selected model, or ``""`` if
        the models directory is empty.
    """
    candidates = get_model_candidates()
    if not candidates:
        return ""

    matching_models = [c for c in candidates if c['sequence_length'] == sequence_length]
    if matching_models:
        return matching_models[0]['filename']

    # No exact sequence-length match; use globally best-scored model.
    return candidates[0]['filename']


def _parse_model_filename(filename: str) -> dict:
    """
    Parse model metadata from weight filename.

    Expected examples:
      model_84_acc_100_frames_final.pt
      anything_91.2_acc_60_foo.pt
    """
    base = os.path.basename(filename)
    name_no_ext = os.path.splitext(base)[0]
    parts = name_no_ext.split('_')

    seq = None
    acc = 0.0
    for idx, token in enumerate(parts):
        if token.lower() == 'acc':
            if idx > 0:
                try:
                    acc = float(parts[idx - 1])
                except ValueError:
                    pass
            if idx + 1 < len(parts):
                try:
                    seq = int(parts[idx + 1])
                except ValueError:
                    seq = None
            break

    if seq is None:
        # Fallback: use last integer found in the filename as sequence hint.
        ints = re.findall(r'(\d+)', name_no_ext)
        if ints:
            seq = int(ints[-1])

    return {'filename': base, 'sequence_length': seq, 'accuracy': acc}


def get_model_candidates() -> list:
    """
    Return available model files sorted by highest accuracy then filename.
    """
    all_model_paths = glob.glob(os.path.join(settings.PROJECT_DIR, 'models', '*.pt'))
    parsed = []
    for path in all_model_paths:
        meta = _parse_model_filename(os.path.basename(path))
        parsed.append(meta)

    # Prefer model files that expose sequence metadata, then best accuracy.
    parsed.sort(
        key=lambda m: (
            0 if m['sequence_length'] is not None else 1,
            -float(m['accuracy']),
            m['filename'].lower(),
        )
    )
    return parsed


def get_default_sequence_length(default: int = 100) -> int:
    """
    Pick a sequence length dynamically from available model files.
    """
    candidates = get_model_candidates()
    for candidate in candidates:
        if candidate['sequence_length'] is not None:
            return int(candidate['sequence_length'])
    return default


# Thread-safe in-memory cache so we don't reload weights on every request
_MODEL_CACHE: dict = {}
_MODEL_CACHE_LOCK = threading.Lock()


def load_model_cached(sequence_length: int):
    """
    Return a loaded and cached DeepfakeDetectorModel for video inference.
    """
    selected_weights_file = select_best_model_file(sequence_length)
    if not selected_weights_file:
        return None, ""

    weights_path = os.path.join(settings.PROJECT_DIR, 'models', selected_weights_file)
    if not os.path.isfile(weights_path):
        return None, selected_weights_file

    cache_key = (selected_weights_file, device.type)
    with _MODEL_CACHE_LOCK:
        if cache_key in _MODEL_CACHE:
            return _MODEL_CACHE[cache_key], selected_weights_file

        checkpoint = torch.load(weights_path, map_location=device)

        model = DeepfakeDetectorModel(num_classes=2).to(device)
        if isinstance(checkpoint, dict) and 'model_state_dict' in checkpoint:
            model.load_state_dict(checkpoint['model_state_dict'])
        else:
            model.load_state_dict(checkpoint)

        model.eval()
        _MODEL_CACHE[cache_key] = model
        return model, selected_weights_file


# ─────────────────────────────────────────────
# File Validation Helpers
# ─────────────────────────────────────────────

def allowed_video_file(filename: str) -> bool:
    """Return True when the file's extension is a supported video format."""
    if '.' not in filename:
        return False
    ext = filename.rsplit('.', 1)[-1].lower()
    return ext in ALLOWED_VIDEO_EXTENSIONS


def _persist_uploaded_video(video_file) -> tuple:
    """
    Write the uploaded video file to disk under ``uploaded_videos/`` and
    return its absolute path and its basename.

    A timestamp suffix in the filename prevents collisions between concurrent
    uploads.

    Returns:
        (absolute_path, basename)
    """
    ext         = video_file.name.rsplit('.', 1)[-1].lower() if '.' in video_file.name else 'mp4'
    saved_name  = f"uploaded_video_{int(time.time())}.{ext}"

    if settings.DEBUG:
        target_dir = os.path.join(settings.PROJECT_DIR, 'uploaded_videos')
    else:
        target_dir = os.path.join(settings.PROJECT_DIR, 'uploaded_videos', 'app', 'uploaded_videos')

    os.makedirs(target_dir, exist_ok=True)
    saved_path = os.path.join(target_dir, saved_name)

    with open(saved_path, 'wb') as out_file:
        shutil.copyfileobj(video_file, out_file)

    return saved_path, saved_name


# ─────────────────────────────────────────────
# View Functions
# ─────────────────────────────────────────────

def index(request):
    """
    Home page – video upload form.

    GET:  Render the upload form and clear any stale session data from a
          previous detection run.
    POST: Validate the uploaded video, save it to disk, store the path in the
          session, and redirect to the results page.
    """
    if request.method == 'GET':
        form = VideoUploadForm()
        # Clear any leftover session data from a prior run
        for key in ('file_name', 'preprocessed_images', 'faces_cropped_images'):
            request.session.pop(key, None)
        return render(request, HOME_TEMPLATE, {'form': form})

    # POST – process the uploaded video
    form = VideoUploadForm(request.POST, request.FILES)
    if not form.is_valid():
        return render(request, HOME_TEMPLATE, {'form': form})

    video_file      = form.cleaned_data['upload_video_file']
    video_ext       = video_file.name.rsplit('.', 1)[-1].lower() if '.' in video_file.name else ''
    sequence_length = form.cleaned_data['sequence_length']
    content_type    = video_file.content_type.split('/')[0]

    # Enforce max file size
    if content_type in settings.CONTENT_TYPES and video_file.size > int(settings.MAX_UPLOAD_SIZE):
        form.add_error('upload_video_file', 'Maximum allowed file size is 100 MB.')
        return render(request, HOME_TEMPLATE, {'form': form})

    # sequence_length > 0 is also enforced by the form's min_value validator,
    # but we keep this guard in case the form is submitted without JS.
    if sequence_length <= 0:
        form.add_error('sequence_length', 'Sequence length must be at least 1.')
        return render(request, HOME_TEMPLATE, {'form': form})

    if not allowed_video_file(video_file.name):
        form.add_error('upload_video_file', 'Only video files are accepted.')
        return render(request, HOME_TEMPLATE, {'form': form})

    # Persist the file and store its path for the results view
    saved_name = f"uploaded_video_{int(time.time())}.{video_ext}"
    # Always store uploads under MEDIA_ROOT so Django can serve them consistently.
    # (The UI playback uses `MEDIA_URL` + the uploaded filename.)
    save_dir = os.path.join(settings.PROJECT_DIR, 'uploaded_videos')

    os.makedirs(save_dir, exist_ok=True)
    saved_path = os.path.join(save_dir, saved_name)
    with open(saved_path, 'wb') as out_file:
        shutil.copyfileobj(video_file, out_file)

    request.session['file_name']       = saved_path
    request.session['sequence_length'] = sequence_length
    return redirect('ml_app:predict')


def predict_page(request):
    """
    Video analysis results page.

    Loads the uploaded video from the session, extracts frames, detects faces,
    runs the deepfake detection model, and renders the results along with
    preprocessed frame previews and cropped face thumbnails.

    Requires the ``face_recognition`` library to be installed.
    """
    if request.method != 'GET':
        return redirect('ml_app:home')

    if 'file_name' not in request.session:
        return redirect('ml_app:home')

    video_path      = request.session['file_name']
    sequence_length = request.session.get('sequence_length', 10)
    video_basename  = os.path.basename(video_path)
    video_stem      = os.path.splitext(video_basename)[0]

    # The browser uses MEDIA_URL to retrieve the uploaded file.
    # The value passed here should be the uploaded filename/basename.
    display_video_name = video_basename

    if face_recognition is None:
        return render(request, VIDEO_RESULT_TEMPLATE, {
            'error': (
                'Missing dependency: face_recognition. '
                'Install the project requirements to enable face detection and cropping.'
            ),
        })

    # Verify at least one model file is present before we start processing
    model_files = glob.glob(os.path.join(settings.PROJECT_DIR, 'models', '*.pt'))
    if not model_files:
        return render(request, VIDEO_RESULT_TEMPLATE, {
            'error': (
                'No trained model files (.pt) found in the models/ directory. '
                'Please download the weights and place them there.'
            ),
            'available_models': [],
        })

    # Load the model that best matches the requested sequence length
    selected_model_name = select_best_model_file(sequence_length)
    weights_path        = os.path.join(settings.PROJECT_DIR, 'models', selected_model_name)
    if not os.path.isfile(weights_path):
        return render(request, VIDEO_RESULT_TEMPLATE, {
            'error': f'Model file "{selected_model_name}" not found. Available: {model_files}',
            'available_models': model_files,
        })

    # MARK: Model instantiated and loaded here
    model = DeepfakeDetectorModel(num_classes=2).to(device)
    checkpoint = torch.load(weights_path, map_location=device)
    if isinstance(checkpoint, dict) and 'model_state_dict' in checkpoint:
        model.load_state_dict(checkpoint['model_state_dict'])
    else:
        model.load_state_dict(checkpoint)
    model.eval()

    # ── Frame extraction and face detection ──────────────────────────────────
    print("<=== | Started: Frame Extraction & Face Detection | ===>")
    start_time = time.time()

    preprocessed_frames  = []   # Filenames of raw extracted frames
    face_crop_frames     = []   # Filenames of cropped face images
    face_padding_px      = 40
    total_faces_found    = 0
    total_frames_read    = 0

    cap = cv2.VideoCapture(video_path)
    for frame_number in range(sequence_length):
        grabbed, frame_bgr = cap.read()
        if not grabbed:
            break
        total_frames_read += 1

        # Save the raw frame (converted to RGB) as a preview image
        frame_rgb      = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
        preview_name   = f"{video_stem}_frame_{frame_number + 1}.png"
        preview_path   = os.path.join(settings.PROJECT_DIR, 'uploaded_images', preview_name)
        pImage.fromarray(frame_rgb, 'RGB').save(preview_path)
        preprocessed_frames.append(preview_name)

        # Detect faces and crop with padding
        face_locations = face_recognition.face_locations(frame_rgb)
        if not face_locations:
            continue

        top, right, bottom, left = face_locations[0]
        fr_h, fr_w = frame_bgr.shape[:2]
        y1 = max(0, top    - face_padding_px)
        y2 = min(fr_h, bottom + face_padding_px)
        x1 = max(0, left   - face_padding_px)
        x2 = min(fr_w, right  + face_padding_px)
        if y2 <= y1 or x2 <= x1:
            continue

        face_bgr  = frame_bgr[y1:y2, x1:x2]
        face_rgb  = cv2.cvtColor(face_bgr, cv2.COLOR_BGR2RGB)
        crop_name = f"{video_stem}_face_{frame_number + 1}.png"
        crop_path = os.path.join(settings.PROJECT_DIR, 'uploaded_images', crop_name)
        pImage.fromarray(face_rgb, 'RGB').save(crop_path)
        face_crop_frames.append(crop_name)
        total_faces_found += 1

    cap.release()
    print(f"Frames read: {total_frames_read}  |  Faces found: {total_faces_found}")
    print(f"<=== | Done: Frame Extraction ({time.time() - start_time:.1f}s) | ===>")

    if total_faces_found == 0:
        return render(request, VIDEO_RESULT_TEMPLATE, {'no_faces': True})

    # ── Model Inference ──────────────────────────────────────────────────────
    try:
        video_dataset = VideoFrameDataset(
            [video_path], sequence_length=sequence_length, transform=frame_transforms
        )
        heatmap_images = []
        output_label   = ""
        confidence_pct = 0.0

        print("<=== | Started: Model Inference | ===>")
        # MARK: Model inference used here
        raw_prediction = run_inference(model, video_dataset[0], './', video_stem)
        confidence_pct = round(raw_prediction[1], 1)
        output_label   = "REAL" if raw_prediction[0] == 1 else "FAKE"
        print(f"Result: {output_label}  Confidence: {confidence_pct}%")
        print(f"<=== | Done: Inference ({time.time() - start_time:.1f}s) | ===>")

        context = {
            'preprocessed_images': preprocessed_frames,
            'faces_cropped_images': face_crop_frames,
            'heatmap_images': heatmap_images,
            'original_video': display_video_name,
            'models_location': os.path.join(settings.PROJECT_DIR, 'models'),
            'output': output_label,
            'confidence': confidence_pct,
        }
        return render(request, VIDEO_RESULT_TEMPLATE, context)

    except Exception as exc:
        print(f"Inference error: {exc}")
        return render(request, 'cuda_full.html')


@csrf_exempt
@require_POST
def api_predict(request):
    """
    JSON API endpoint for video deepfake detection.

    Accepts a multipart POST with the same fields as the web form
    (``upload_video_file``, ``sequence_length``) and returns a JSON response
    with the prediction result, confidence score, uploaded video basename, and
    the name of the model used.

    Does not generate preview images – suitable for programmatic clients or
    future AJAX integration.
    """
    form = VideoUploadForm(request.POST, request.FILES)
    if not form.is_valid():
        return JsonResponse({'error': 'Invalid form data.', 'details': form.errors}, status=400)

    video_file      = form.cleaned_data['upload_video_file']
    sequence_length = int(form.cleaned_data['sequence_length'])

    if sequence_length <= 0:
        return JsonResponse({'error': 'Sequence length must be at least 1.'}, status=400)

    if not allowed_video_file(video_file.name):
        return JsonResponse({'error': 'Only video files are accepted.'}, status=400)

    if video_file.size > int(settings.MAX_UPLOAD_SIZE):
        return JsonResponse({'error': 'Maximum allowed file size is 100 MB.'}, status=400)

    saved_path, saved_basename = _persist_uploaded_video(video_file)
    video_stem                 = os.path.splitext(saved_basename)[0]

    try:
        if face_recognition is None:
            return JsonResponse(
                {'error': 'face_recognition library is not installed. Install project dependencies.'},
                status=500,
            )

        video_dataset = VideoFrameDataset(
            [saved_path], sequence_length=sequence_length, transform=frame_transforms
        )
        # MARK: Model loaded from cache here
        model, selected_model_name = load_model_cached(sequence_length)
        if model is None:
            return JsonResponse(
                {'error': f'No model found for sequence length {sequence_length}.'},
                status=500,
            )

        # MARK: Model inference used here
        raw_prediction = run_inference(model, video_dataset[0], './', video_stem)
        confidence_pct = round(raw_prediction[1], 1)
        output_label   = "REAL" if raw_prediction[0] == 1 else "FAKE"

        return JsonResponse({
            'output':         output_label,
            'confidence':     confidence_pct,
            'original_video': saved_basename,
            'model_used':     selected_model_name,
        })

    except Exception as exc:
        return JsonResponse({'error': f'Prediction failed: {exc}'}, status=500)


def about(request):
    """Render the About page describing the project and model architecture."""
    return render(request, ABOUT_TEMPLATE)


def handler404(request, exception):
    """Custom 404 error page."""
    return render(request, '404.html', status=404)


def cuda_full(request):
    """Error page shown when inference fails (e.g. out of CUDA memory)."""
    return render(request, 'cuda_full.html')
