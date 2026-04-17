# -*- coding: utf-8 -*-
"""
check_env.py -- ForgeGuard Environment Health Check
====================================================
Run this script to verify the environment before starting the server.

Usage (from project root):
    conda run -n ForgeGuard python check_env.py

Or with the environment already active:
    python check_env.py
"""

import sys
import os

# Force UTF-8 stdout so symbols don't crash Windows cp1252 encoding
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = os.path.dirname(os.path.abspath(__file__))
DJANGO_APP = os.path.join(ROOT, "Django Application")

PASS = "[PASS]"
WARN = "[WARN]"
FAIL = "[FAIL]"
INFO = "[INFO]"

print("=" * 60)
print("  ForgeGuard -- Environment Health Check")
print("=" * 60)

# ── 1. Python version ────────────────────────────────────────────────────────
py_ver = sys.version_info
print(f"\n[1] Python version : {sys.version.split()[0]}")
if py_ver.major == 3 and py_ver.minor == 10:
    print(f"     {PASS}  Python 3.10 confirmed")
else:
    print(f"     {WARN}  Expected Python 3.10, got {py_ver.major}.{py_ver.minor}")

# ── 2. PyTorch + CUDA ────────────────────────────────────────────────────────
print("\n[2] PyTorch / CUDA")
try:
    import torch
    print(f"     {INFO}  torch version  : {torch.__version__}")
    if torch.cuda.is_available():
        print(f"     {PASS}  CUDA available : {torch.cuda.get_device_name(0)}")
        print(f"     {INFO}  CUDA version   : {torch.version.cuda}")
    else:
        print(f"     {WARN}  CUDA not available -- CPU will be used (OK for inference)")
except ImportError:
    print(f"     {FAIL}  torch is NOT installed")

# ── 3. torchvision ───────────────────────────────────────────────────────────
print("\n[3] torchvision")
try:
    import torchvision
    print(f"     {PASS}  torchvision {torchvision.__version__}")
except ImportError:
    print(f"     {FAIL}  torchvision is NOT installed")

# ── 4. Core image/video dependencies ─────────────────────────────────────────
print("\n[4] Core deps")
for pkg_name, import_name in [("Pillow", "PIL"), ("opencv-python", "cv2"), ("numpy", "numpy")]:
    try:
        mod = __import__(import_name)
        ver = getattr(mod, "__version__", "?")
        print(f"     {PASS}  {pkg_name} {ver}")
    except ImportError:
        print(f"     {FAIL}  {pkg_name} NOT installed")

# ── 5. Django ────────────────────────────────────────────────────────────────
print("\n[5] Django")
try:
    import django
    print(f"     {PASS}  Django {django.__version__}")
except ImportError:
    print(f"     {FAIL}  Django NOT installed")

# ── 6. HuggingFace / data pipeline ───────────────────────────────────────────
print("\n[6] HuggingFace / data pipeline")
for pkg in ("huggingface_hub", "datasets", "tqdm", "pyarrow"):
    try:
        mod = __import__(pkg)
        ver = getattr(mod, "__version__", "?")
        print(f"     {PASS}  {pkg} {ver}")
    except ImportError:
        print(f"     {WARN}  {pkg} not installed  (run: pip install {pkg})")

# ── 7. Optional: face_recognition ────────────────────────────────────────────
print("\n[7] face_recognition (required for video pipeline)")
try:
    import face_recognition  # noqa: F401
    print(f"     {PASS}  face_recognition available")
except ImportError:
    print(f"     {WARN}  face_recognition NOT installed")
    print("          Fix: conda install -c conda-forge dlib")
    print("               pip install face-recognition")

# ── 8. Model weight files ─────────────────────────────────────────────────────
print("\n[8] Model weight files")
models = {
    "Video model (ResNeXt+LSTM) [REQUIRED]": os.path.join(
        DJANGO_APP, "models", "model_97_acc_100_frames_FF_data.pt"
    ),
    "Image model (IMDModel)     [REQUIRED]": os.path.join(
        ROOT, "external", "image_detection", "model", "model_c1.pth"
    ),
    "Image artifact fine-tuned  [optional]": os.path.join(
        DJANGO_APP, "models", "model_99_acc_image_artifact_finetuned.pt"
    ),
}
for name, path in models.items():
    if os.path.isfile(path):
        size_mb = os.path.getsize(path) / (1024 * 1024)
        print(f"     {PASS}  {name} ({size_mb:.1f} MB)")
    else:
        tag = FAIL if "REQUIRED" in name else WARN
        print(f"     {tag}  {name}")
        print(f"            NOT FOUND: {path}")

# ── 9. ml_core imports ────────────────────────────────────────────────────────
print("\n[9] ml_core imports")
sys.path.insert(0, DJANGO_APP)
try:
    from ml_core.image_model.imd import IMDModel, detect_image_file, detect_image_bytes  # noqa: F401
    print(f"     {PASS}  ml_core.image_model.imd  -- OK")
except Exception as exc:
    print(f"     {FAIL}  ml_core.image_model.imd  import failed: {exc}")

try:
    from ml_core.image_model.imd import ImageDetectionResult  # noqa: F401
    print(f"     {PASS}  ImageDetectionResult     -- OK")
except Exception as exc:
    print(f"     {FAIL}  ImageDetectionResult     import failed: {exc}")

# ── 10. Summary ───────────────────────────────────────────────────────────────
print("\n" + "=" * 60)
print("  Health check complete.")
print()
print("  To start the server:")
print("    conda activate ForgeGuard")
print(f'    cd "Django Application"')
print("    python manage.py runserver")
print()
print("  To install CUDA PyTorch (GPU support):")
print("    Run: conda_install.bat")
print("=" * 60)
