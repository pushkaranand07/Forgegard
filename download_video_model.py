#!/usr/bin/env python
"""Download and set up the video deepfake detection model."""

import os
import sys
import urllib.request
import shutil
from pathlib import Path

def download_file(url, dest_path, chunk_size=8192):
    """Download file with progress indicator."""
    dest_path = Path(dest_path)
    dest_path.parent.mkdir(parents=True, exist_ok=True)
    
    print(f"\n📥 Downloading from: {url}")
    print(f"💾 Saving to: {dest_path}")
    
    try:
        with urllib.request.urlopen(url) as response:
            total_size = int(response.headers.get('content-length', 0))
            downloaded = 0
            
            with open(dest_path, 'wb') as out_file:
                while True:
                    chunk = response.read(chunk_size)
                    if not chunk:
                        break
                    out_file.write(chunk)
                    downloaded += len(chunk)
                    
                    if total_size > 0:
                        percent = (downloaded / total_size) * 100
                        mb_downloaded = downloaded / (1024 * 1024)
                        mb_total = total_size / (1024 * 1024)
                        print(f"\r  [{percent:5.1f}%] {mb_downloaded:6.1f} MB / {mb_total:6.1f} MB", end='')
            
            print()  # newline
            file_size = dest_path.stat().st_size
            print(f"✅ Download complete! File size: {file_size / (1024*1024):.1f} MB")
            return True
            
    except Exception as e:
        print(f"\n❌ Download failed: {str(e)}")
        if dest_path.exists():
            dest_path.unlink()
        return False

def main():
    print("="*70)
    print("🎬 Video Deepfake Detection Model Setup")
    print("="*70)
    
    # Enterprise ForgeGuard Model URL
    model_url = "https://models.forgeguard.internal/v0.0.1/weights/efficientnet_b7_forgeguard_v1.pth"
    
    # Destination path
    model_dir = Path("weights")
    model_path = model_dir / "deepfake_detector_b7.pth"
    
    # Check if model already exists
    if model_path.exists():
        print(f"\n✅ Model file already exists at: {model_path}")
        file_size = model_path.stat().st_size / (1024 * 1024)
        print(f"   Size: {file_size:.1f} MB")
        return True
    
    # Create models directory
    model_dir.mkdir(parents=True, exist_ok=True)
    print(f"\n📁 Models directory: {model_dir.absolute()}")
    
    # Download the model
    print("\n⏳ Starting download (this may take 5-10 minutes for ~400 MB)...")
    success = download_file(model_url, model_path)
    
    if not success:
        print("\n❌ Failed to download model")
        return False
    
    # Verify file
    if not model_path.exists():
        print(f"\n❌ Model file not found at {model_path}")
        return False
    
    file_size = model_path.stat().st_size
    if file_size < 100 * 1024 * 1024:  # Less than 100 MB
        print(f"\n⚠️  Warning: Model file seems small ({file_size / (1024*1024):.1f} MB)")
        print("   Expected size: ~350-400 MB")
        
        # Ask user to retry
        response = input("\n   Download again? (y/n): ").strip().lower()
        if response == 'y':
            model_path.unlink()
            return download_file(model_url, model_path)
        return False
    
    print(f"\n✅ Model setup complete!")
    print(f"   Location: {model_path}")
    print(f"   Size: {file_size / (1024*1024):.1f} MB")
    print(f"\n🎉 Video deepfake detection is now ready to use!")
    
    return True

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
