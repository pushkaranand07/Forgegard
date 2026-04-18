#!/usr/bin/env python
"""Test script to verify image detection is working."""

import os
import sys
import time
from pathlib import Path
from io import BytesIO
from PIL import Image
import requests

# Change to Django Application directory
os.chdir("Django Application")
sys.path.insert(0, ".")

# Set up Django
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "project_settings.settings")

import django
django.setup()

from ml_core.image_model.imd import detect_image_bytes

def test_image_detection():
    """Test the image detection backend."""
    print("\n" + "="*60)
    print("Testing Image Detection Backend")
    print("="*60)
    
    # Create a simple test image
    print("\n1. Creating test image...")
    img = Image.new('RGB', (100, 100), color='red')
    img_bytes = BytesIO()
    img.save(img_bytes, format='PNG')
    img_bytes.seek(0)
    raw_bytes = img_bytes.read()
    print(f"   ✓ Created test image ({len(raw_bytes)} bytes)")
    
    # Test detection
    print("\n2. Running image detection...")
    try:
        result = detect_image_bytes(
            raw_bytes=raw_bytes,
            model_path="models/model_c1.pth"
        )
        print(f"   ✓ Detection completed")
        print(f"      Label: {result.label}")
        print(f"      Authentic Prob: {result.authentic_prob:.2%}")
        print(f"      Tampered Prob: {result.tampered_prob:.2%}")
        print(f"      Device: {result.device}")
        print(f"      Software Found: {result.software_found}")
        
        # Calculate confidence
        confidence = round(max(result.tampered_prob, result.authentic_prob) * 100, 2)
        print(f"      Confidence: {confidence}%")
        return True
    except Exception as e:
        print(f"   ✗ Detection failed: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

def test_api_endpoint():
    """Test the API endpoint."""
    print("\n" + "="*60)
    print("Testing Image Detection API Endpoint")
    print("="*60)
    
    # Create a test image
    print("\n1. Creating test image...")
    img = Image.new('RGB', (100, 100), color='blue')
    img_bytes = BytesIO()
    img.save(img_bytes, format='PNG')
    img_bytes.seek(0)
    print("   ✓ Created test image")
    
    # POST to API
    print("\n2. POSTing to /api/detect-image/ endpoint...")
    try:
        files = {'image': ('test.png', img_bytes, 'image/png')}
        response = requests.post('http://localhost:8000/api/detect-image/', files=files)
        print(f"   Status Code: {response.status_code}")
        data = response.json()
        print(f"   ✓ API Response:")
        for key, value in data.items():
            if isinstance(value, dict):
                print(f"      {key}:")
                for k, v in value.items():
                    print(f"         {k}: {v}")
            else:
                print(f"      {key}: {value}")
        return response.status_code == 200
    except Exception as e:
        print(f"   ✗ API test failed: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    backend_ok = test_image_detection()
    print("\n" + "-"*60)
    print("Waiting 2 seconds before API test...")
    time.sleep(2)
    
    api_ok = test_api_endpoint()
    
    print("\n" + "="*60)
    print("Test Summary")
    print("="*60)
    print(f"Backend Detection: {'✓ PASS' if backend_ok else '✗ FAIL'}")
    print(f"API Endpoint: {'✓ PASS' if api_ok else '✗ FAIL'}")
    print("="*60 + "\n")
    
    sys.exit(0 if (backend_ok and api_ok) else 1)
