#!/usr/bin/env python
"""Test video API error handling."""

import os
import sys
import requests
from io import BytesIO

# Create a minimal video-like file for testing
print("\n" + "="*60)
print("Testing Video API Error Handling")
print("="*60)

print("\n1. Creating test video file...")
# Create a minimal MP4-like binary (not a real video)
video_bytes = b'ftypisom\x00\x00\x02\x00isomiso2mp41' + b'\x00' * 100
video_bio = BytesIO(video_bytes)
print("   ✓ Created test video file")

print("\n2. POSTing to /api/detect-video/ endpoint...")
try:
    files = {'video': ('test.mp4', video_bio, 'video/mp4')}
    data = {'num_frames': 32}
    response = requests.post('http://localhost:8000/api/detect-video/', 
                            files=files, data=data)
    print(f"   Status Code: {response.status_code}")
    json_data = response.json()
    print(f"   ✓ API Response:")
    for key, value in json_data.items():
        if isinstance(value, dict):
            print(f"      {key}:")
            for k, v in value.items():
                print(f"         {k}: {v}")
        else:
            print(f"      {key}: {value}")
    
    # Verify error message is user-friendly
    if response.status_code == 503 and json_data.get('status') == 'model_not_found':
        print("\n   ✓ Error message handling is correct:")
        print(f"      - Status: 503 Service Unavailable")
        print(f"      - Status field: 'model_not_found'")
        print(f"      - Error message is user-friendly: {'SETUP_VIDEO_MODEL' in json_data.get('error', '')}")
    
except Exception as e:
    print(f"   ✗ API test failed: {str(e)}")
    import traceback
    traceback.print_exc()

print("\n" + "="*60 + "\n")
