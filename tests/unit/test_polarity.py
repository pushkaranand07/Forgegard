"""
Test whether the model's high output = FAKE or REAL
by looking at the second available model file and cross-checking.
"""
import torch, numpy as np, os, sys, re
sys.path.insert(0, os.path.abspath('..'))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'project_settings.settings')
import django; django.setup()

from django.conf import settings
from ml_core.video_model.vmd import DeepFakeClassifier, normalize_transform, _put_to_center, _isotropically_resize

try:
    torch.serialization.add_safe_globals([np.core.multiarray.scalar])
except: pass

def load_and_test(model_path, encoder='tf_efficientnet_b7_ns'):
    print(f"\n{'='*60}")
    print(f"Testing: {os.path.basename(model_path)}")
    print(f"{'='*60}")

    try:
        ckpt = torch.load(model_path, map_location='cpu', weights_only=True)
    except:
        ckpt = torch.load(model_path, map_location='cpu', weights_only=False)

    if isinstance(ckpt, dict):
        print(f"epoch={ckpt.get('epoch')}, bce_best={ckpt.get('bce_best')}")
        sd = ckpt.get('state_dict', ckpt)
    else:
        sd = ckpt
    sd = {re.sub(r'^module\.', '', k): v for k, v in sd.items()}

    try:
        model = DeepFakeClassifier(encoder=encoder)
    except Exception as e:
        print(f"  ERROR building model: {e}")
        return

    r = model.load_state_dict(sd, strict=False)
    print(f"Missing: {len(r.missing_keys)}, Unexpected: {len(r.unexpected_keys)}")
    model.eval()

    fc_bias = model.fc.bias.data.item()
    print(f"FC bias: {fc_bias:.4f}")

    def run(rgb_val, label):
        frame = np.full((380, 380, 3), rgb_val, dtype=np.uint8)
        t = torch.from_numpy(frame).permute(2, 0, 1).float() / 255.0
        t = normalize_transform(t).unsqueeze(0)
        with torch.no_grad():
            logit = model(t)
            p = torch.sigmoid(logit).item()
        print(f"  {label}: logit={logit.item():.3f}, sigmoid={p:.3f} → {'FAKE' if p>0.5 else 'REAL'} ({p*100:.1f}%)")
        return p

    run([200, 150, 100], "Skin-tone [R>G>B]")
    run([100, 150, 200], "Inverted skin [B>G>R]")
    run([128, 128, 128], "Neutral grey")

# Test all available models
models_dir = os.path.join(settings.PROJECT_DIR, 'models')
for f in sorted(os.listdir(models_dir)):
    if f.endswith('.pth') or f.endswith('.pt'):
        fpath = os.path.join(models_dir, f)
        # Determine encoder from filename
        if 'b7' in f.lower():
            enc = 'tf_efficientnet_b7_ns'
        elif 'b5' in f.lower():
            enc = 'tf_efficientnet_b5_ns'
        elif 'b4' in f.lower():
            enc = 'tf_efficientnet_b4_ns'
        else:
            enc = 'tf_efficientnet_b7_ns'
        load_and_test(fpath, enc)

print("\n--- CONCLUSION ---")
print("If sigmoid > 0.5 for a skin-tone frame → model treats high output as FAKE")
print("If sigmoid < 0.5 for a skin-tone frame → model treats high output as REAL")
print("Expected for a well-calibrated DFDC model: skin-tone → low score (REAL)")
