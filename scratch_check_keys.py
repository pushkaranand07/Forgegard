import torch
import glob

model_files = glob.glob(r"C:\coding\my work\final year\ForgeGuard\Django Application\models\*.pt")
for p in model_files:
    print(f"\nEvaluating: {p}")
    chk = torch.load(p, map_location="cpu")
    print(f"Is dict? {isinstance(chk, dict)}")
    if isinstance(chk, dict):
        print(f"Keys: {list(chk.keys())}")
        if "model_state_dict" in chk:
            inner = chk["model_state_dict"]
            print(f"Type of inner 'model_state_dict': {type(inner)}")
            if isinstance(inner, dict):
                print(f"Inner keys (first 10): {list(inner.keys())[:10]}")
