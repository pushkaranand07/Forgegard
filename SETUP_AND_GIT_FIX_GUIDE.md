# ForgeGuard: Complete Setup & Git Integration Fix

**Date:** April 17, 2026  
**Status:** Comprehensive guide to fix both environment and git integration issues

---

## Table of Contents
1. [Part A: Fix the Environment (Problem 1)](#part-a--fix-the-environment-problem-1)
2. [Part B: Fix Git Integration (Problem 2)](#part-b--fix-git-integration-problem-2)
3. [Part C: Error Handling & Troubleshooting](#part-c--error-handling--troubleshooting)
4. [Part D: Final Task List to Upload](#part-d--final-task-list-to-upload)

---

# PART A – Fix the Environment (Problem 1)

## Overview
Your project currently has **no Python libraries installed**. You need:
- Python 3.10 (alongside your existing 3.13)
- A clean virtual environment
- All dependencies from `requirements.txt`
- A `.env` configuration file

---

## Sub-Task A1: Install Python 3.10 (Without Removing 3.13)

### Why Do This?
Your project was developed for **Python 3.10**, which has better compatibility with PyTorch and face_recognition on Windows. Python 3.13 is too new.

### Step-by-Step Commands

**1. Check if Python 3.10 is already installed:**
```powershell
py -3.10 --version
```

**Expected output if installed:**
```
Python 3.10.x
```

**If command fails:** Python 3.10 is NOT installed. Proceed to step 2.

---

**2. Download and Install Python 3.10:**

Go to: https://www.python.org/downloads/release/python-3109/

**Download:** `Windows installer (64-bit)` 

**During installation:**
- ✅ **CHECK:** "Add Python 3.10 to PATH"
- ✅ **CHECK:** "Install pip"
- ❌ **DO NOT CHECK:** "Install for all users" (unless you're admin)

**Verify installation after completing the installer:**
```powershell
py -3.10 --version
```

Should output:
```
Python 3.10.9
```

---

## Sub-Task A2: Create a Virtual Environment

### Why Do This?
A virtual environment is a **isolated folder** that holds your project's dependencies. This prevents conflicts with other Python projects on your computer.

### Step-by-Step Commands

**1. Navigate to your project root:**
```powershell
cd "c:\coding\my work\final year\ForgeGuard"
```

**2. Create a virtual environment named "venv" using Python 3.10:**
```powershell
py -3.10 -m venv venv
```

**What this does:**
- Creates a folder named `venv/` in your project
- Sets up Python 3.10 as the isolated Python for this project

**Expected output:** (none – it just creates the folder)

**3. Activate the virtual environment:**

On **PowerShell:**
```powershell
.\venv\Scripts\Activate.ps1
```

On **Command Prompt (cmd.exe):**
```cmd
venv\Scripts\activate.bat
```

**Expected output:**
```
(venv) C:\coding\my work\final year\ForgeGuard>
```

The `(venv)` prefix means your virtual environment is **active**.

**4. Verify Python is 3.10 inside the virtual environment:**
```powershell
python --version
```

**Expected output:**
```
Python 3.10.9
```

---

## Sub-Task A3: Install All Required Libraries

### Why Do This?
Your project needs Django, PyTorch, and many other libraries to run. The `requirements.txt` file lists all of them.

### Important Note on PyTorch + Windows
PyTorch (the AI library) requires special handling on Windows:
- **Regular pip install often fails** on Windows for PyTorch
- **Solution:** Install via Conda OR use the prebuilt wheel

We'll use **Conda** (recommended) because it's more reliable on Windows.

### Step-by-Step Commands

**1. Check if Conda is installed:**
```powershell
conda --version
```

**If Conda is installed:**
- You should see output like: `conda 24.1.2`
- Proceed to Step 2

**If Conda is NOT installed:**
- Download from: https://docs.conda.io/projects/miniconda/en/latest/miniconda-install.html
- Install **Miniconda** (lightweight version)
- Restart PowerShell after installation

---

**2. Create a Conda environment for Python 3.10:**

```powershell
conda create -n ForgeGuard python=3.10
```

**Expected output:**
```
... (lots of text)
Proceed ([y]/n)? y
```

Press `y` and Enter.

---

**3. Activate the Conda environment:**

```powershell
conda activate ForgeGuard
```

**Expected output:**
```
(ForgeGuard) C:\coding\my work\final year\ForgeGuard>
```

---

**4. Install PyTorch with CUDA support (GPU) - RECOMMENDED:**

```powershell
conda install pytorch torchvision pytorch-cuda=12.1 -c pytorch -c nvidia
```

**What this does:**
- Installs PyTorch with CUDA 12.1 (GPU acceleration)
- If your GPU driver doesn't support 12.1, see **Error Handling** section below

**Expected output:**
```
... (many lines of installation)
Proceed ([y]/n)? y
```

Press `y` and Enter. **This may take 5-10 minutes.**

---

**5. Install dlib from conda-forge (required for face_recognition on Windows):**

```powershell
conda install -c conda-forge dlib
```

**Expected output:**
```
... (many lines)
Proceed ([y]/n)? y
```

Press `y` and Enter. **This may take 10+ minutes – be patient.**

---

**6. Install remaining dependencies from requirements.txt:**

Navigate to the Django Application folder:
```powershell
cd "Django Application"
```

Install requirements:
```powershell
pip install -r requirements.txt
```

**Expected output:**
```
Successfully installed Django-5.0.6 opencv-python-4.10.0.84 ...
```

**Expected completion time:** 5-10 minutes

---

## Sub-Task A4: Create .env File

### Why Do This?
Django needs configuration values stored in the `.env` file (secret key, debug mode, allowed hosts).

### Step-by-Step Commands

**1. Navigate back to project root:**
```powershell
cd ".."  # Go up one level from "Django Application"
```

**2. Copy the template to create the real .env file:**

On **PowerShell:**
```powershell
Copy-Item ".env.example" ".env"
```

On **Command Prompt:**
```cmd
copy .env.example .env
```

**3. Open the new `.env` file in a text editor:**

Option A (PowerShell):
```powershell
notepad ".env"
```

Option B (VS Code):
```powershell
code ".env"
```

**4. Edit the values if needed** (for local development, the defaults are usually fine):

```
DJANGO_SECRET_KEY=dev-secret-change-me-in-production
DJANGO_DEBUG=true
DJANGO_ALLOWED_HOSTS=127.0.0.1,localhost
DJANGO_LOG_LEVEL=INFO
```

For **local testing**, these values are fine.  
For **production**, change `DJANGO_SECRET_KEY` to something random.

**5. Save the file and close the editor.**

---

## Sub-Task A5: Verify Installation with Test Command

### Why Do This?
Before running the full server, verify that all libraries loaded successfully and there are no import errors.

### Step-by-Step Commands

**1. Make sure you're in the project root and Conda environment is active:**

```powershell
# You should see (ForgeGuard) at the start of your prompt
# If not, run: conda activate ForgeGuard
```

**2. Run the environment health check script:**

```powershell
python check_env.py
```

**Expected output:**
```
============================================================
  ForgeGuard -- Environment Health Check
============================================================

[1] Python version : 3.10.x
     [PASS]  Python 3.10 confirmed

[2] PyTorch / CUDA
     [PASS]  torch version  : 2.0.x
     [PASS]  CUDA available : NVIDIA GeForce RTX ...

[3] torchvision
     [PASS]  torchvision 0.15.x

[4] Core deps
     [PASS]  Pillow 10.3.0
     [PASS]  opencv-python 4.10.0.84
     [PASS]  numpy 1.26.4

[5] Django
     [PASS]  Django 5.0.6

[7] face_recognition (required for video pipeline)
     [PASS]  face_recognition available

[8] Model weight files
     [PASS]  Video model (ResNeXt+LSTM) [REQUIRED] (216.1 MB)
     [PASS]  Image model (IMDModel)     [REQUIRED] (56.6 MB)

[9] ml_core imports
     [PASS]  ml_core.image_model.imd  -- OK
     [PASS]  ImageDetectionResult     -- OK

============================================================
  Health check complete.
```

**If you see all [PASS] marks:** ✅ Environment is ready!

**If you see [FAIL] marks:** See **Part C: Error Handling** below.

---

# PART B – Fix Git Integration (Problem 2)

## Overview
The `external/image_detection/` folder contains the cloned `z1311/Image-Manipulation-Detection` repository. Currently:
- ❌ It's NOT a git submodule
- ❌ It has its own separate `.git` folder
- ❌ It won't be tracked by your main project's git

**Goal:** Convert it to a proper git submodule so when someone clones your repo, they automatically get this folder too.

---

## Sub-Task B1: Remove the Existing Image Detection Folder

### Why Do This?
Git submodules must be added cleanly. We need to remove the existing folder and its separate git history first.

### Step-by-Step Commands

**1. Navigate to your project root:**
```powershell
cd "c:\coding\my work\final year\ForgeGuard"
```

**2. Remove the image_detection folder from git tracking (without deleting the code):**

```powershell
git rm --cached -r external/image_detection
```

**Expected output:**
```
rm 'external/image_detection/...'  (many files listed)
```

**What this does:**
- Removes the folder from git's index
- Does NOT delete the actual folder yet
- Prepares it to be re-added as a submodule

---

**3. Check git status to verify:**

```powershell
git status
```

**Expected output:**
```
On branch main
Changes to be committed:
  (use "git restore --staged <path>..." to unstage)
        deleted:    external/image_detection/...

Untracked files:
  (use "git add <file>..." to include them)
        external/image_detection/
```

This shows the folder is **staged for deletion** but still exists on disk.

---

**4. Commit this removal:**

```powershell
git commit -m "Remove external/image_detection for submodule integration"
```

**Expected output:**
```
 1 file changed, X insertions(-)
 delete mode 100644 external/image_detection/...
```

---

**5. Delete the actual image_detection folder (now safe to delete):**

On **PowerShell:**
```powershell
Remove-Item -Recurse -Force "external/image_detection"
```

On **Command Prompt:**
```cmd
rmdir /s /q external\image_detection
```

**Expected output:** (none – just deletes the folder)

---

**6. Verify it's gone:**

```powershell
git status
```

**Expected output:**
```
On branch main
Your branch is ahead of 'origin/main' by 1 commit.
  (use "git push" to publish your local commits)

nothing to commit, working tree clean
```

✅ The folder is completely removed and committed.

---

## Sub-Task B2: Add as a Git Submodule

### Why Do This?
A git submodule allows your main project to reference another repository as a subfolder. When someone clones your project with `--recursive`, they automatically get this folder.

### Step-by-Step Commands

**1. Verify you're in the project root:**

```powershell
cd "c:\coding\my work\final year\ForgeGuard"
```

**2. Add the z1311 repository as a submodule:**

```powershell
git submodule add https://github.com/z1311/Image-Manipulation-Detection.git external/image_detection
```

**Expected output:**
```
Cloning into 'C:\coding\my work\final year\ForgeGuard\external\image_detection'...
remote: Enumerating objects: XXXX, done.
...
```

**This will take 1-2 minutes** as it clones the entire repository.

---

**3. Verify the submodule was added:**

```powershell
git status
```

**Expected output:**
```
On branch main
Changes to be committed:
  (use "git restore --staged <path>..." to unstage)
        new file:   .gitmodules
        new file:   external/image_detection
```

**Also check that `.gitmodules` file was created:**
```powershell
cat .gitmodules
```

**Expected output:**
```
[submodule "external/image_detection"]
    path = external/image_detection
    url = https://github.com/z1311/Image-Manipulation-Detection.git
```

---

**4. Verify the imports still work (imports don't need adjustment):**

```powershell
cd "Django Application"
python -c "from ml_core.image_model.imd import detect_image_bytes; print('✓ Import successful')"
cd ".."
```

**Expected output:**
```
✓ Import successful
```

If you see this, **no import path changes are needed** – the code continues to work as-is.

---

**5. Commit the submodule reference:**

```powershell
git add .gitmodules external/image_detection
git commit -m "Add Image-Manipulation-Detection as git submodule

- Properly reference z1311/Image-Manipulation-Detection repo
- Ensures clones with --recursive get the image detection code
- Maintains compatibility with ml_core.image_model.imd imports"
```

**Expected output:**
```
 2 files changed, X insertions(+)
 create mode 100644 .gitmodules
 create mode 160000 external/image_detection
```

The `160000` mode indicates it's a submodule reference (not regular files).

---

# PART C – Error Handling & Troubleshooting

## Common Issues & Solutions

### **Error Group 1: Python Installation**

#### ❌ Error: "py -3.10: command not found"
**Why it happens:**
- Python 3.10 is not installed
- OR it's not in your PATH

**Fix:**
1. Download from https://www.python.org/downloads/release/python-3109/
2. During installation, **CHECK "Add Python 3.10 to PATH"**
3. After installation, restart PowerShell/cmd
4. Try: `py -3.10 --version`

---

#### ❌ Error: "The term 'py' is not recognized"
**Why it happens:**
- Python is not in your system PATH
- You're using a terminal that hasn't been refreshed

**Fix:**
Option 1: Restart PowerShell completely (close and reopen)
Option 2: Use the full path:
```powershell
"C:\Python310\python.exe" --version
```

---

### **Error Group 2: Virtual Environment**

#### ❌ Error: ".\venv\Scripts\Activate.ps1 cannot be loaded because running scripts is disabled"
**Why it happens:**
- PowerShell execution policy is too restrictive

**Fix:**
```powershell
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
.\venv\Scripts\Activate.ps1
```

---

#### ❌ Error: "ModuleNotFoundError: No module named 'venv'"
**Why it happens:**
- Python 3.10's venv module is missing

**Fix:**
On Windows, reinstall Python 3.10 and ensure **"pip"** is checked during installation.

---

### **Error Group 3: Conda & PyTorch Installation**

#### ❌ Error: "conda: command not found"
**Why it happens:**
- Miniconda/Anaconda is not installed
- OR it's not in PATH

**Fix:**
1. Install Miniconda: https://docs.conda.io/projects/miniconda/en/latest/
2. Restart PowerShell
3. Try: `conda --version`

---

#### ❌ Error: "Solving environment: failed with initial frozen solve"
**Why it happens:**
- Conda's package cache is corrupted

**Fix:**
```powershell
conda clean --all
conda create -n ForgeGuard python=3.10
conda activate ForgeGuard
```

---

#### ❌ Error: "CUDA is not available" (even though you installed pytorch-cuda=12.1)
**Why it happens:**
- Your GPU driver doesn't support CUDA 12.1
- OR your GPU is too old

**Fix Option 1: Use a different CUDA version:**
```powershell
conda install pytorch torchvision pytorch-cuda=11.8 -c pytorch -c nvidia
```

**Fix Option 2: Use CPU-only PyTorch (slower but works everywhere):**
```powershell
conda install pytorch torchvision cpuonly -c pytorch
```

**Note:** The app will still work with CPU; it'll just be slower.

---

#### ❌ Error: "LINK : fatal error LNK1181: cannot open input file 'dlib.lib'" (during dlib installation)
**Why it happens:**
- dlib requires a C++ compiler, which pip doesn't handle well on Windows

**Fix:**
```powershell
conda install -c conda-forge dlib  # Use conda, not pip
```

---

### **Error Group 4: Dependencies & Requirements**

#### ❌ Error: "ERROR: Could not find a version that satisfies the requirement matplotlib==3.9.0"
**Why it happens:**
- matplotlib 3.9.0 is incompatible with Python 3.13 (your original Python)
- The requirements.txt file has this, but it's commented out for Python 3.13

**Fix:**
This is automatically handled in the requirements.txt (matplotlib is commented out). If pip fails:
```powershell
pip install --upgrade pip
pip install -r requirements.txt
```

---

#### ❌ Error: "pip: command not found"
**Why it happens:**
- Conda environment is not activated

**Fix:**
```powershell
conda activate ForgeGuard
pip --version  # Should now work
```

---

### **Error Group 5: .env Configuration**

#### ❌ Error: "ImproperlyConfigured: The SECRET_KEY setting must not be empty"
**Why it happens:**
- The `.env` file wasn't created or Django can't read it

**Fix:**
1. Verify `.env` file exists in project root:
   ```powershell
   Test-Path ".\.env"  # Should return True
   ```
2. If it returns False:
   ```powershell
   Copy-Item ".env.example" ".env"
   ```
3. Verify it has content:
   ```powershell
   cat ".env"
   ```

---

### **Error Group 6: Git Submodule Issues**

#### ❌ Error: "fatal: pathspec 'external/image_detection' did not match any files"
**Why it happens:**
- The folder doesn't exist at that path
- OR you're not in the project root

**Fix:**
```powershell
cd "c:\coding\my work\final year\ForgeGuard"
ls external/  # Verify folder exists
git submodule add https://github.com/z1311/Image-Manipulation-Detection.git external/image_detection
```

---

#### ❌ Error: "A git directory for 'external/image_detection' is found locally... fatal: unable to add submodule"
**Why it happens:**
- The old `.git` folder from image_detection still exists

**Fix:**
```powershell
Remove-Item -Recurse -Force "external/image_detection\.git"
git submodule add https://github.com/z1311/Image-Manipulation-Detection.git external/image_detection
```

---

#### ❌ Error: "fatal: Pathspec 'external/image_detection' is in submodule 'external/image_detection'"
**Why it happens:**
- You're trying to add a submodule that's already registered

**Fix:**
```powershell
# Remove from git index
git rm --cached external/image_detection
# Remove from .gitmodules
# (Manually edit .gitmodules and delete the [submodule ...] section)
# Then try again
git submodule add https://github.com/z1311/Image-Manipulation-Detection.git external/image_detection
```

---

#### ❌ Error: "ImportError: No module named 'ml_core'" (after submodule setup)
**Why it happens:**
- The PYTHONPATH doesn't include the project root
- OR Django's manage.py isn't adding it

**Fix:**
This shouldn't happen because manage.py already adds the project root. But if it does:

```powershell
cd "Django Application"
$env:PYTHONPATH = ".."  # On PowerShell
set PYTHONPATH=..       # On cmd.exe
python manage.py runserver
```

---

### **Error Group 7: Running the Server**

#### ❌ Error: "Address already in use" (port 8000)
**Why it happens:**
- Another process is already using port 8000
- OR you have an old Django server still running

**Fix:**
```powershell
# Find process using port 8000
netstat -ano | findstr :8000

# Kill the process (replace PID with the number shown)
taskkill /PID <PID> /F

# Try running the server on a different port
cd "Django Application"
python manage.py runserver 127.0.0.1:8001
```

---

#### ❌ Error: "ModuleNotFoundError: No module named 'django'" (when running manage.py)
**Why it happens:**
- Conda environment is not activated

**Fix:**
```powershell
conda activate ForgeGuard
cd "c:\coding\my work\final year\ForgeGuard\Django Application"
python manage.py runserver
```

---

#### ❌ Error: "No trained model files (.pt) found in the models/ directory"
**Why it happens:**
- The model files are missing from `Django Application/models/`

**Fix:**
Models should already exist. Verify:
```powershell
ls "Django Application/models/"
```

Should show:
```
model_97_acc_100_frames_FF_data.pt
model_99_acc_image_artifact_finetuned.pt
```

If missing, ensure they're downloaded/placed in that folder.

---

# PART D – Final Task List to Upload

## Complete Numbered Checklist

### **Phase 1: Setup (Complete Before Testing)**

- [ ] **1. Install Python 3.10**
  - Download from python.org/downloads
  - Run installer with "Add to PATH" checked
  - Verify: `py -3.10 --version`

- [ ] **2. Create Conda environment**
  ```powershell
  conda create -n ForgeGuard python=3.10
  conda activate ForgeGuard
  ```

- [ ] **3. Install PyTorch with CUDA support**
  ```powershell
  conda install pytorch torchvision pytorch-cuda=12.1 -c pytorch -c nvidia
  ```
  - If CUDA fails, use: `pytorch-cuda=11.8` instead
  - If still fails, use: `cpuonly` version

- [ ] **4. Install dlib via conda-forge**
  ```powershell
  conda install -c conda-forge dlib
  ```

- [ ] **5. Install remaining dependencies**
  ```powershell
  cd "Django Application"
  pip install -r requirements.txt
  cd ".."
  ```

- [ ] **6. Create .env file**
  ```powershell
  Copy-Item ".env.example" ".env"
  ```

- [ ] **7. Verify environment**
  ```powershell
  python check_env.py
  ```
  - All [PASS] indicators should be green
  - If any [FAIL], fix using Part C: Error Handling

---

### **Phase 2: Fix Git Integration (Complete After Phase 1)**

- [ ] **8. Remove image_detection from git tracking**
  ```powershell
  git rm --cached -r external/image_detection
  git commit -m "Remove external/image_detection for submodule integration"
  ```

- [ ] **9. Delete the image_detection folder**
  ```powershell
  Remove-Item -Recurse -Force "external/image_detection"
  ```

- [ ] **10. Add as git submodule**
  ```powershell
  git submodule add https://github.com/z1311/Image-Manipulation-Detection.git external/image_detection
  ```

- [ ] **11. Verify import compatibility**
  ```powershell
  cd "Django Application"
  python -c "from ml_core.image_model.imd import detect_image_bytes; print('✓')"
  cd ".."
  ```

- [ ] **12. Commit submodule reference**
  ```powershell
  git add .gitmodules external/image_detection
  git commit -m "Add Image-Manipulation-Detection as git submodule"
  ```

---

### **Phase 3: Test Locally (Before Pushing)**

- [ ] **13. Start Django development server**
  ```powershell
  cd "Django Application"
  python manage.py runserver
  ```
  - Server should start at http://127.0.0.1:8000
  - No errors should appear in console

- [ ] **14. Test home page**
  - Open http://127.0.0.1:8000 in browser
  - Should see video upload form

- [ ] **15. Test image detection API (optional but recommended)**
  ```powershell
  # In another PowerShell window:
  curl -X POST http://127.0.0.1:8000/api/detect-image/ -F "image=@path/to/test/image.jpg"
  ```

- [ ] **16. Test video detection (optional)**
  - Upload a test video through the web UI
  - Should see predictions and confidence score

- [ ] **17. Stop the server** (when testing is complete)
  - Press `Ctrl+C` in the PowerShell running `manage.py runserver`

---

### **Phase 4: Commit & Push to GitHub**

- [ ] **18. Check git status**
  ```powershell
  git status
  ```
  - Should show "Your branch is ahead of 'origin/main' by X commits"
  - No uncommitted changes

- [ ] **19. View commits to be pushed**
  ```powershell
  git log origin/main..HEAD --oneline
  ```

- [ ] **20. Push to GitHub**
  ```powershell
  git push origin main
  ```
  - If you don't have write access, create a fork first
  - Should complete without errors

- [ ] **21. Verify on GitHub**
  - Go to your GitHub repo
  - Verify `.gitmodules` file is present
  - Verify `external/image_detection` shows as a submodule (with @ symbol)

---

### **Phase 5: Test Fresh Clone (On Another Machine or Folder)**

**This is the ultimate test – verify someone else can clone and run your project:**

- [ ] **22. Clone the repo with submodules (in a different folder)**
  ```powershell
  cd "C:\temp"  # Different folder
  git clone --recursive https://github.com/YOUR_USERNAME/ForgeGuard.git ForgeGuard_Test
  cd ForgeGuard_Test
  ```

- [ ] **23. Verify submodule was cloned**
  ```powershell
  ls external/image_detection
  ```
  - Should list the image detection files

- [ ] **24. Repeat Phase 1 setup** (environment, dependencies)
  ```powershell
  conda create -n ForgeGuard_Test python=3.10
  conda activate ForgeGuard_Test
  conda install pytorch torchvision pytorch-cuda=12.1 -c pytorch -c nvidia
  conda install -c conda-forge dlib
  cd "Django Application"
  pip install -r requirements.txt
  cd ".."
  Copy-Item ".env.example" ".env"
  ```

- [ ] **25. Run health check**
  ```powershell
  python check_env.py
  ```
  - All [PASS] should be shown

- [ ] **26. Start server**
  ```powershell
  cd "Django Application"
  python manage.py runserver
  ```
  - Should start without errors

- [ ] **27. Test website loads**
  - Open http://127.0.0.1:8000
  - Upload page should appear

- [ ] **28. FINAL SUCCESS** ✅
  - Your project is now fully setup and shareable!

---

### **Phase 6: Share with Others (Instructions to Give Them)**

Create a `CLONE_AND_RUN.md` file with these instructions for new users:

```markdown
# How to Clone and Run ForgeGuard

## Prerequisites
- Python 3.10 or higher
- Miniconda or Anaconda
- Git

## Setup (5-10 minutes)

1. Clone with submodules:
   ```
   git clone --recursive https://github.com/YOUR_USERNAME/ForgeGuard.git
   cd ForgeGuard
   ```

2. Create Conda environment:
   ```
   conda create -n ForgeGuard python=3.10
   conda activate ForgeGuard
   ```

3. Install PyTorch (GPU):
   ```
   conda install pytorch torchvision pytorch-cuda=12.1 -c pytorch -c nvidia
   ```

4. Install dlib:
   ```
   conda install -c conda-forge dlib
   ```

5. Install dependencies:
   ```
   cd "Django Application"
   pip install -r requirements.txt
   cd ..
   ```

6. Create .env:
   ```
   Copy-Item ".env.example" ".env"
   ```

7. Run the server:
   ```
   cd "Django Application"
   python manage.py runserver
   ```

8. Open http://127.0.0.1:8000

Done! 🎉
```

---

## Summary of What Gets Fixed

| **Problem** | **Before** | **After** |
|---|---|---|
| **Libraries** | ❌ Django, PyTorch, OpenCV missing | ✅ All installed via Conda |
| **Python Version** | ❌ Python 3.13 (incompatible) | ✅ Python 3.10 (correct) |
| **.env Configuration** | ❌ Missing | ✅ Created from template |
| **Image Detection Integration** | ❌ Untracked folder + separate .git | ✅ Proper git submodule |
| **Cloning by Others** | ❌ Submodule missing for cloners | ✅ Automatic with `--recursive` |
| **Server Status** | ❌ Fails immediately | ✅ Runs on http://127.0.0.1:8000 |

---

## Quick Command Reference

**Activate environment:**
```powershell
conda activate ForgeGuard
```

**Run server:**
```powershell
cd "Django Application"
python manage.py runserver
```

**Check environment:**
```powershell
python check_env.py
```

**Push changes:**
```powershell
git push origin main
```

**Clone with submodules (for others):**
```powershell
git clone --recursive https://github.com/YOUR_USERNAME/ForgeGuard.git
```

---

**Last Updated:** April 17, 2026  
**Status:** Ready for implementation
