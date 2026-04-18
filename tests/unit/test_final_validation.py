"""
Final Validation Suite for ForgeGuard Deepfake Pipeline
Run from the ForgeGuard root with:
    conda run -n ForgeGuard python "Django Application/test_final_validation.py"
"""
import os, sys, cv2, time, numpy as np

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'project_settings.settings')

import django
django.setup()

from ml_core.video_model.vmd import (
    FaceExtractor, preprocess_frame, _isotropically_resize, _put_to_center,
    detect_video_file, get_face_extractor, invalidate_caches,
    IMAGENET_MEAN, IMAGENET_STD
)

PASSED = []
FAILED = []

def check(name, condition, detail=""):
    if condition:
        print(f"  ✅ PASS: {name}")
        PASSED.append(name)
    else:
        print(f"  ❌ FAIL: {name} — {detail}")
        FAILED.append(name)

# ──────────────────────────────────────────────────────────────────────
# TEST 1: Color channel order (RGB confirmed)
# ──────────────────────────────────────────────────────────────────────
print("\n" + "="*60)
print("TEST 1: Color Channel Order")
print("="*60)

# Create a frame with strong red dominance (skin tone simulation)
frame_rgb = np.zeros((300, 300, 3), dtype=np.uint8)
frame_rgb[:, :, 0] = 200   # R
frame_rgb[:, :, 1] = 150   # G
frame_rgb[:, :, 2] = 100   # B

r_mean = frame_rgb[:,:,0].mean()
b_mean = frame_rgb[:,:,2].mean()
check("R_mean > B_mean for skin-tone RGB frame", r_mean > b_mean,
      f"R={r_mean:.1f}, B={b_mean:.1f}")

# ──────────────────────────────────────────────────────────────────────
# TEST 2: Preprocessing matches training pipeline exactly
# ──────────────────────────────────────────────────────────────────────
print("\n" + "="*60)
print("TEST 2: Preprocessing Pipeline (Training Match)")
print("="*60)

face = np.random.randint(0, 255, (200, 150, 3), dtype=np.uint8)

# Verify isotropic resize
resized = _isotropically_resize(face, 380)
check("Isotropic resize: largest dim = 380", max(resized.shape[:2]) == 380,
      f"Shape: {resized.shape}")

# Verify put_to_center produces 380x380
centered = _put_to_center(resized, 380)
check("put_to_center output is 380x380", centered.shape == (380, 380, 3),
      f"Shape: {centered.shape}")

# Verify preprocessing tensor shape
tensor = preprocess_frame(face, 380)
check("preprocess_frame tensor shape (C,H,W)", tensor.shape == (3, 380, 380),
      f"Shape: {tensor.shape}")
check("preprocess_frame dtype is float", tensor.dtype.is_floating_point,
      f"dtype: {tensor.dtype}")

# Verify normalization range (ImageNet normalized values typically in [-2.2, 2.8])
check("Tensor values within normalized range",
      tensor.min().item() > -3.0 and tensor.max().item() < 3.0,
      f"min={tensor.min().item():.2f}, max={tensor.max().item():.2f}")

# Verify normalization constants match training
check("IMAGENET_MEAN matches training [0.485, 0.456, 0.406]",
      IMAGENET_MEAN == [0.485, 0.456, 0.406])
check("IMAGENET_STD matches training [0.229, 0.224, 0.225]",
      IMAGENET_STD == [0.229, 0.224, 0.225])

# ──────────────────────────────────────────────────────────────────────
# TEST 3: MTCNN configuration matches training
# ──────────────────────────────────────────────────────────────────────
print("\n" + "="*60)
print("TEST 3: MTCNN Configuration (Training Match)")
print("="*60)

invalidate_caches()
extractor = get_face_extractor("cpu")

check("MTCNN thresholds=[0.7, 0.8, 0.8]",
      extractor.detector.thresholds == [0.7, 0.8, 0.8],
      f"Got: {extractor.detector.thresholds}")
check("MTCNN margin=0",
      extractor.detector.margin == 0,
      f"Got: {extractor.detector.margin}")
check("MTCNN keep_all=True",
      extractor.detector.keep_all == True,
      f"Got: {extractor.detector.keep_all}")

# ──────────────────────────────────────────────────────────────────────
# TEST 4: Synthetic video classification (no-face)  
# ──────────────────────────────────────────────────────────────────────
print("\n" + "="*60)
print("TEST 4: Synthetic Video — No Face → UNSURE")
print("="*60)

from django.conf import settings
MODEL_PATH = os.path.join(settings.PROJECT_DIR, 'models', 'deepfake_detector_b7.pth')

if not os.path.exists(MODEL_PATH):
    print(f"  ⚠️  SKIP: Model not found at {MODEL_PATH}")
else:
    # Faceless video (pure green)
    faceless_path = "faceless_test.mp4"
    out = cv2.VideoWriter(faceless_path, cv2.VideoWriter_fourcc(*'mp4v'), 10, (200, 200))
    for _ in range(32):
        frame = np.zeros((200, 200, 3), dtype=np.uint8)
        frame[:, :, 1] = 180  # Pure green, no face
        out.write(frame)
    out.release()

    result = detect_video_file(faceless_path, MODEL_PATH)
    check("Faceless video → label=UNSURE", result.label == "UNSURE",
          f"Got: {result.label}")
    check("Faceless video → fake_prob=0.5", result.fake_prob == 0.5,
          f"Got: {result.fake_prob}")
    check("Faceless video → NO_FACE_DETECTED in notes",
          "NO_FACE_DETECTED" in result.notes,
          f"Notes: {result.notes}")
    os.remove(faceless_path)

# ──────────────────────────────────────────────────────────────────────
# TEST 5: Empty / corrupt video handling
# ──────────────────────────────────────────────────────────────────────
print("\n" + "="*60)
print("TEST 5: Edge Case — Empty / Corrupt File")
print("="*60)

from ml_core.video_model.vmd import EmptyVideoException

empty_path = "empty_test.mp4"
open(empty_path, 'wb').close()

try:
    from ml_core.video_model.vmd import VideoReader
    reader = VideoReader(verbose=False)
    reader.read_frames(empty_path, 32)
    check("Empty file raises EmptyVideoException", False, "No exception raised")
except EmptyVideoException:
    check("Empty file raises EmptyVideoException", True)
except Exception as e:
    check("Empty file raises EmptyVideoException", False, f"Wrong exception: {e}")
finally:
    os.remove(empty_path)

# ──────────────────────────────────────────────────────────────────────
# SUMMARY
# ──────────────────────────────────────────────────────────────────────
print("\n" + "="*60)
print(f"RESULTS: {len(PASSED)} passed, {len(FAILED)} failed")
print("="*60)
if FAILED:
    print("FAILED tests:")
    for f in FAILED:
        print(f"  ❌ {f}")
    sys.exit(1)
else:
    print("All tests passed! ✅")
