import os
import urllib.request
import sys
import torch
import numpy as np
import cv2

sys.path.insert(0, os.path.abspath('..'))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'project_settings.settings')
import django; django.setup()
from django.conf import settings

from ml_core.video_model.vmd import (
    VideoReader, FaceExtractor, preprocess_frame, load_model, 
    _isotropically_resize, _put_to_center
)

def download_sample_video():
    url = "https://github.com/intel-iot-devkit/sample-videos/raw/master/face-demographics-walking.mp4"
    path = "test_walking_face.mp4"
    if not os.path.exists(path):
        print("Downloading sample video with faces...")
        urllib.request.urlretrieve(url, path)
    return path

def test():
    video_path = download_sample_video()
    print(f"Reading: {video_path}")
    reader = VideoReader(verbose=False)
    frames = reader.read_frames(video_path, 8)
    print(f"Read {len(frames)} frames")
    
    extractor = FaceExtractor(device='cpu')
    tensors_rgb = []
    tensors_bgr = []
    
    for i, f_bgr in enumerate(frames):
        f_rgb = cv2.cvtColor(f_bgr, cv2.COLOR_BGR2RGB)
        
        # Test 1: Extract from RGB (what we do now)
        face_rgb = extractor.extract_face(f_rgb)
        if face_rgb is not None:
            tensors_rgb.append(preprocess_frame(face_rgb, 380))
            if i == len(frames)//2:
                cv2.imwrite("debug_face_rgb.jpg", cv2.cvtColor(face_rgb, cv2.COLOR_RGB2BGR))
                
        # Test 2: What if we extracted from BGR? (just in case training data was buggy and trained on BGR)
        face_bgr = extractor.extract_face(f_bgr)
        if face_bgr is not None:
            tensors_bgr.append(preprocess_frame(face_bgr, 380))
            if i == len(frames)//2:
                cv2.imwrite("debug_face_bgr.jpg", face_bgr)

    MODEL_PATH = os.path.join(settings.PROJECT_DIR, 'models', 'deepfake_detector_b7.pth')
    model = load_model(MODEL_PATH, encoder='tf_efficientnet_b7_ns', device='cpu')
    model.eval()

    def predict_group(tensors, title):
        if not tensors:
            print(f"{title}: No faces extracted.")
            return
        
        with torch.no_grad():
            batch = torch.stack(tensors)
            logits = model(batch)
            probs = torch.sigmoid(logits).squeeze().tolist()
            
        if not isinstance(probs, list):
            probs = [probs]
            
        mean_p = np.mean(probs)
        print(f"\n--- {title} ---")
        for i, p in enumerate(probs):
            print(f"  Frame {i:2d}: {p:.4f} -> {'FAKE' if p>0.5 else 'REAL'}")
        print(f"  Mean: {mean_p:.4f} -> {'FAKE' if mean_p>0.5 else 'REAL'}")
        
    predict_group(tensors_rgb, "Trained Pipeline (RGB extraction, RGB tensor)")
    predict_group(tensors_bgr, "Buggy Pipeline? (BGR extraction, BGR tensor)")

if __name__ == "__main__":
    test()
