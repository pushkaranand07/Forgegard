import sys
import os

sys.path.append(r"C:\coding\my work\final year\ForgeGuard\Django Application")
sys.path.append(r"C:\coding\my work\final year\ForgeGuard")

import django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'project_settings.settings')
django.setup()

from ml_app.views import load_model_cached

print("Calling load_model_cached(60)...")
try:
    model, name = load_model_cached(60)
    print(f"Success! Model loaded: {name}")
except Exception as e:
    print(f"EXCEPTION: {e}")
