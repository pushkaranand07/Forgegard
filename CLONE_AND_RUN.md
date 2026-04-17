# Clone and Run ForgeGuard

This guide is for users who want to clone and run the ForgeGuard project on their machine.

## Prerequisites

Before you start, ensure you have:
- **Python 3.10** or higher
- **Miniconda** or **Anaconda** (for managing Python environments)
- **Git** (version control)

### Install Prerequisites (if needed)

**Miniconda:** https://docs.conda.io/projects/miniconda/en/latest/  
**Git:** https://git-scm.com/download

---

## Quick Start (5 Steps)

### Step 1: Clone the Repository with Submodules

This command clones the main project **and** the Image-Manipulation-Detection submodule:

```powershell
git clone --recursive https://github.com/YOUR_USERNAME/ForgeGuard.git
cd ForgeGuard
```

**Important:** Always use `--recursive` flag so the `external/image_detection/` folder is cloned.

If you already cloned without `--recursive`, run:
```powershell
git submodule update --init --recursive
```

---

### Step 2: Create Conda Environment

```powershell
conda create -n ForgeGuard python=3.10
conda activate ForgeGuard
```

**Expected output:**
```
(ForgeGuard) C:\...\ForgeGuard>
```

The `(ForgeGuard)` prefix means the environment is active.

---

### Step 3: Install PyTorch with GPU Support

```powershell
conda install pytorch torchvision pytorch-cuda=12.1 -c pytorch -c nvidia
```

**If this fails with CUDA errors:**
```powershell
# Try CUDA 11.8 instead
conda install pytorch torchvision pytorch-cuda=11.8 -c pytorch -c nvidia
```

**If that also fails (CPU-only mode):**
```powershell
# Works everywhere but slower
conda install pytorch torchvision cpuonly -c pytorch
```

**This step takes 5-10 minutes.**

---

### Step 4: Install dlib and All Dependencies

```powershell
conda install -c conda-forge dlib
cd "Django Application"
pip install -r requirements.txt
cd ".."
```

**This step takes 10+ minutes.**

---

### Step 5: Create Configuration File and Run

```powershell
# Create .env from template
Copy-Item ".env.example" ".env"

# Verify everything is installed
python check_env.py
```

**Expected output:** All `[PASS]` indicators

**If you see `[FAIL]` items:** See Troubleshooting section below

---

## Running the Server

```powershell
cd "Django Application"
python manage.py runserver
```

**Expected output:**
```
Starting development server at http://127.0.0.1:8000/
```

**Open your browser to:** http://127.0.0.1:8000

You should see the ForgeGuard home page with a video upload form.

---

## Testing the Features

### Test 1: Home Page (Video Upload)
1. Go to http://127.0.0.1:8000
2. Should see a form to upload a video
3. Upload a test video (MP4, AVI, etc.)
4. System should analyze it and show predictions

### Test 2: Image Detection API
```powershell
# In a different PowerShell window:
curl -X POST http://127.0.0.1:8000/api/detect-image/ -F "image=@path/to/test/image.jpg"
```

Should receive JSON response with predictions.

### Test 3: About Page
- Navigate to http://127.0.0.1:8000/about/
- Should display project information

---

## Stop the Server

Press `Ctrl+C` in the PowerShell window running the server.

---

## For Future Sessions

To run the server again later, you only need:

```powershell
cd "c:\path\to\ForgeGuard"
conda activate ForgeGuard
cd "Django Application"
python manage.py runserver
```

---

## Troubleshooting

### Problem: "ModuleNotFoundError: No module named 'torch'"

**Cause:** Conda environment is not active

**Fix:**
```powershell
conda activate ForgeGuard
```

Verify the fix:
```powershell
# Should show (ForgeGuard) at the start
# If not, the environment is not active
```

---

### Problem: "No trained model files (.pt) found"

**Cause:** Model weight files are missing

**Fix:** Models should already exist in `Django Application/models/`

Verify:
```powershell
ls "Django Application/models/"
```

Should show:
```
model_97_acc_100_frames_FF_data.pt
model_99_acc_image_artifact_finetuned.pt
```

If missing, contact the project maintainer.

---

### Problem: "Port 8000 already in use"

**Cause:** Another process is using port 8000

**Fix Option 1:** Use a different port
```powershell
python manage.py runserver 127.0.0.1:8001
```

**Fix Option 2:** Kill the process using port 8000
```powershell
# Find the process
netstat -ano | findstr :8000

# Kill it (replace PID with the number shown)
taskkill /PID <PID> /F
```

---

### Problem: "CUDA out of memory"

**Cause:** Your GPU doesn't have enough VRAM for the models

**Fix Option 1:** Use a smaller video (fewer frames)
- Try sequence_length = 20 instead of 100

**Fix Option 2:** Use CPU instead of GPU
- Slower but will work without GPU memory issues

**Fix Option 3:** Force CPU-only mode:
```powershell
# In Python console:
import os
os.environ['CUDA_VISIBLE_DEVICES'] = '-1'
```

---

### Problem: "face_recognition not found"

**Cause:** dlib or face_recognition package didn't install properly

**Fix:**
```powershell
conda remove face_recognition dlib
conda install -c conda-forge dlib
pip install face-recognition
```

---

### Problem: "ImportError: No module named 'ml_core'"

**Cause:** Python path is not configured correctly

**Fix:** This shouldn't happen with `manage.py`. If it does:

```powershell
cd "Django Application"
$env:PYTHONPATH = ".."  # Add project root to Python path
python manage.py runserver
```

---

## Advanced: Understanding the Project Structure

```
ForgeGuard/
├── Django Application/          # Main web application
│   ├── manage.py               # Django control script
│   ├── requirements.txt         # Python dependencies
│   ├── ml_app/                 # Detection models & views
│   │   ├── views.py            # Video analysis logic
│   │   ├── image_api.py        # Image analysis API
│   │   └── templates/          # HTML pages
│   ├── models/                 # Trained model weights (.pt files)
│   ├── uploaded_images/        # Saved analysis results
│   └── uploaded_videos/        # User uploaded videos
│
├── external/                    # External repositories
│   └── image_detection/        # z1311/Image-Manipulation-Detection (submodule)
│
├── ml_core/                    # Shared ML utilities
│   └── image_model/imd.py      # Image detection wrapper
│
├── .env                        # Configuration (you create this)
├── .env.example                # Configuration template
├── check_env.py                # Environment health check
└── README.md                   # Project documentation
```

---

## Getting Help

If something goes wrong:

1. **Check the comprehensive setup guide:**
   - See `SETUP_AND_GIT_FIX_GUIDE.md` for detailed error handling

2. **Run the health check:**
   ```powershell
   python check_env.py
   ```
   This will tell you exactly what's missing or wrong.

3. **Check Django server output:**
   Look at the terminal where you ran `python manage.py runserver`
   The error message often indicates what's wrong.

---

## Common Commands Reference

| What You Want | Command |
|---|---|
| Activate environment | `conda activate ForgeGuard` |
| Run health check | `python check_env.py` |
| Start server | `cd "Django Application"` then `python manage.py runserver` |
| Stop server | `Ctrl+C` in the terminal running the server |
| Verify submodule cloned | `ls external/image_detection` |
| Update submodule | `git submodule update --init --recursive` |
| Check Python version | `python --version` |
| List Conda environments | `conda env list` |
| Delete environment | `conda env remove -n ForgeGuard` |

---

**Need more help?** See `SETUP_AND_GIT_FIX_GUIDE.md` for comprehensive documentation with error handling for every step.

**Last Updated:** April 17, 2026
