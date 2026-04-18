import torch, numpy as np, os, sys, re
sys.path.insert(0, os.path.abspath('..'))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'project_settings.settings')
import django; django.setup()
from django.conf import settings
from ml_core.video_model.vmd import DeepFakeClassifier, normalize_transform

try:
    torch.serialization.add_safe_globals([np.core.multiarray.scalar])
except: pass

MODEL_PATH = os.path.join(settings.PROJECT_DIR, 'models', 'final_777_b7_ns_0_29.pth')
print(f"Testing: {MODEL_PATH}")

try:
    ckpt = torch.load(MODEL_PATH, map_location='cpu', weights_only=True)
except:
    ckpt = torch.load(MODEL_PATH, map_location='cpu', weights_only=False)

if isinstance(ckpt, dict):
    sd = ckpt.get('state_dict', ckpt)
    print(f"epoch={ckpt.get('epoch')}, bce_best={ckpt.get('bce_best')}")
else:
    sd = ckpt

sd = {re.sub(r'^module\.', '', k): v for k, v in sd.items()}

model = DeepFakeClassifier(encoder='tf_efficientnet_b7_ns')
r = model.load_state_dict(sd, strict=False)
print(f"Missing: {len(r.missing_keys)}, Unexpected: {len(r.unexpected_keys)}")
model.eval()

def run(rgb_val, label):
    frame = np.full((380, 380, 3), rgb_val, dtype=np.uint8)
    t = torch.from_numpy(frame).permute(2, 0, 1).float() / 255.0
    t = normalize_transform(t).unsqueeze(0)
    with torch.no_grad():
        logit = model(t)
        p = torch.sigmoid(logit).item()
    verdict = 'FAKE' if p > 0.5 else 'REAL'
    print(f"  {label}: sigmoid={p:.3f} -> {verdict} ({p*100:.1f}% fake prob)")
    return p

p_skin = run([200, 150, 100], "Skin-tone [R>G>B]")
p_inv  = run([100, 150, 200], "Inverted [B>G>R]")
p_grey = run([128, 128, 128], "Neutral grey")

print()
if p_skin < 0.5 and p_grey < 0.5:
    print("✅ Official weights look correctly calibrated (real → low score)")
    print("✅ Replacing old checkpoint with official one...")
    import shutil
    old = os.path.join(settings.PROJECT_DIR, 'models', 'deepfake_detector_b7.pth')
    bak = old + '.bad_backup'
    shutil.copy(old, bak)
    shutil.copy(MODEL_PATH, old)
    print(f"✅ Done. Old checkpoint backed up to: {bak}")
else:
    print("❌ Official weights also miscalibrated — further investigation needed")
