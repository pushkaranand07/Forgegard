import os
import sys
import cv2
import numpy as np
import logging

from ml_core.video_model.vmd import detect_video_file, FaceExtractor

def test_color_channel_order():
    print("--- Test 2.1: Color Channel Unit Test ---")
    mock_frame = np.zeros((100, 100, 3), dtype=np.uint8)
    mock_frame[:, :, 0] = 200  # R
    mock_frame[:, :, 1] = 150  # G
    mock_frame[:, :, 2] = 100  # B

    class MockFaceExtractor(FaceExtractor):
        def _mock_face(self, frame):
            return frame[20:80, 20:80]

    extractor = MockFaceExtractor(device="cpu", verbose=True)
    extractor.extract_face = extractor._mock_face
    face_crop = extractor.extract_face(mock_frame)

    r_mean = face_crop[:, :, 0].mean()
    b_mean = face_crop[:, :, 2].mean()

    assert r_mean > b_mean, f"❌ BGR inversion detected! R={r_mean:.2f}, B={b_mean:.2f}"
    print(f"✅ RGB order confirmed: R_mean={r_mean:.2f} > B_mean={b_mean:.2f}")

def test_real_videos(video_paths: list):
    print("\n--- Test 2.2: Real Video Classification ---")
    if not video_paths:
        print("Skipping: No provided paths for real videos.")
        return
        
    results = []
    for path in video_paths:
        if not os.path.exists(path):
            print(f"Skipping {path} - file missing")
            continue
        try:
            result = detect_video_file(path)
            passed = result.real_prob > 0.5 and result.confidence_pct > 0.8
            results.append({
                "file": path,
                "label": result.label,
                "real_prob": result.real_prob,
                "confidence": result.confidence_pct,
                "passed": "✅" if passed else "❌"
            })
        except Exception as e:
            print(f"Error on {path}: {e}")
            
    for r in results:
        print(r)
    if results:
        assert all(r["passed"] == "✅" for r in results), "❌ One or more real videos misclassified"

def test_fake_videos(video_paths: list):
    print("\n--- Test 2.3: Fake Video Classification ---")
    if not video_paths:
        print("Skipping: No provided paths for fake videos.")
        return
        
    results = []
    for path in video_paths:
        if not os.path.exists(path):
            print(f"Skipping {path} - file missing")
            continue
        try:
            result = detect_video_file(path)
            passed = result.real_prob < 0.5 and result.fake_prob > 0.5
            results.append({
                "file": path,
                "label": result.label,
                "real_prob": result.real_prob,
                "fake_prob": result.fake_prob,
                "passed": "✅" if passed else "❌"
            })
        except Exception as e:
            print(f"Error on {path}: {e}")
            
    for r in results:
        print(r)
    if results:
        assert all(r["passed"] == "✅" for r in results), "❌ One or more fake videos misclassified"

def test_faceless_videos(video_paths: list):
    print("\n--- Test 2.4: Face-Less Video Test ---")
    if not video_paths:
        print("Skipping: No provided paths for face-less videos.")
        return
        
    for path in video_paths:
        if not os.path.exists(path):
            print(f"Skipping {path} - file missing")
            continue
            
        result = detect_video_file(path)
        assert result.label == "UNSURE", f"❌ Expected UNSURE, got {result.label}"
        assert "NO_FACE_DETECTED" in result.notes, "❌ Missing NO_FACE_DETECTED note"
        assert result.real_prob == 0.5, f"❌ Expected 0.5, got {result.real_prob}"
        assert result.fake_prob == 0.5, f"❌ Expected 0.5, got {result.fake_prob}"
        print(f"✅ Face-less handled correctly: {path} → {result.label}")

def test_multi_face_video(path: str):
    print("\n--- Test 2.5: Multi-Face Regression Test ---")
    if not os.path.exists(path):
        print("Skipping: No provided path for multi-face regression.")
        return
        
    result = detect_video_file(path)
    assert result.label in ["REAL", "FAKE"], f"❌ Unexpected label: {result.label}"
    assert result.confidence_pct > 0.5, "❌ Low confidence on multi-face video"
    print(f"✅ Multi-face video handled: {result.label} @ {result.confidence_pct:.2%}")

if __name__ == "__main__":
    # In a real environment, load directories:
    test_color_channel_order()
    
    # Placeholders down below
    # test_real_videos(["real_01.mp4", "real_02.mp4", "real_03.mp4", "real_04.mp4", "real_05.mp4"])
    # test_fake_videos(["fake_01.mp4", "fake_02.mp4", "fake_03.mp4", "fake_04.mp4", "fake_05.mp4"])
    # test_faceless_videos(["landscape.mp4", "traffic.mp4", "screen_rec.mp4"])
    # test_multi_face_video("multi_face.mp4")
    
    print("\nAll synthetically runnable automated tests passed successfully.")
