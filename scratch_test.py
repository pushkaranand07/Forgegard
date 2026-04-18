import sys
import os

sys.path.append(r"C:\coding\my work\final year\ForgeGuard\Django Application")
sys.path.append(r"C:\coding\my work\final year\ForgeGuard")

import django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'project_settings.settings')
django.setup()

from ml_app.views import VideoFrameDataset, frame_transforms

video_path = r"C:\coding\my work\final year\ForgeGuard\Django Application\uploaded_videos\uploaded_file_1773992300.mp4"

try:
    dataset = VideoFrameDataset([video_path], sequence_length=60, transform=frame_transforms)
    tensor = dataset[0]
    print(f"Tensor Shape: {tensor.shape}")
except Exception as e:
    print(f"Error: {e}")
