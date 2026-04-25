"""
ELA (Error Level Analysis) Visualization Script
Generates a side-by-side comparison showing:
1. Original Image
2. JPEG Compressed Version
3. ELA Difference Map

Usage: python scripts/generate_ela_visualization.py
"""

import cv2
import numpy as np
from PIL import Image as PILImage
import matplotlib.pyplot as plt
from pathlib import Path
import os

output_dir = Path("report_images/technical")
output_dir.mkdir(parents=True, exist_ok=True)

def generate_ela_visualization():
    """
    Create a synthetic test image and show ELA comparison.
    For real usage, provide an actual image file.
    """
    
    # Create a synthetic test image (gradient with embedded text)
    width, height = 400, 300
    
    # Create base image
    img = np.ones((height, width, 3), dtype=np.uint8) * 200  # Gray background
    
    # Add some content
    # Create a simple scene: vertical gradient
    for y in range(height):
        img[y, :] = [int(100 + y * 155 / height), 150, int(200 - y * 155 / height)]
    
    # Add a white rectangle (simulating manipulation)
    img[50:100, 50:150] = [255, 255, 255]
    
    # Add text using cv2
    cv2.putText(img, 'Original Image', (10, 280), cv2.FONT_HERSHEY_SIMPLEX, 
                0.7, (0, 0, 0), 2)
    
    original = img.copy()
    
    # Step 1: Save as JPEG with quality 95
    jpeg_path = "temp_compressed.jpg"
    cv2.imwrite(jpeg_path, original, [cv2.IMWRITE_JPEG_QUALITY, 95])
    
    # Step 2: Load the compressed JPEG
    compressed = cv2.imread(jpeg_path)
    
    # Step 3: Calculate ELA (Error Level Analysis)
    # Convert to float for precision
    original_float = original.astype(np.float32)
    compressed_float = compressed.astype(np.float32)
    
    # Calculate difference
    ela_diff = np.abs(original_float - compressed_float)
    
    # Amplify the difference for visibility (multiply by 20)
    ela_amplified = (ela_diff * 20).clip(0, 255).astype(np.uint8)
    
    # Convert BGR to RGB for matplotlib
    original_rgb = cv2.cvtColor(original, cv2.COLOR_BGR2RGB)
    compressed_rgb = cv2.cvtColor(compressed, cv2.COLOR_BGR2RGB)
    ela_rgb = cv2.cvtColor(ela_amplified, cv2.COLOR_BGR2RGB)
    
    # Create visualization
    fig, axes = plt.subplots(1, 3, figsize=(15, 4))
    
    # Original
    axes[0].imshow(original_rgb)
    axes[0].set_title('Original Image', fontsize=12, fontweight='bold')
    axes[0].axis('off')
    
    # Compressed (JPEG 95%)
    axes[1].imshow(compressed_rgb)
    axes[1].set_title('JPEG Compressed (Quality 95%)', fontsize=12, fontweight='bold')
    axes[1].axis('off')
    
    # ELA Difference
    axes[2].imshow(ela_rgb)
    axes[2].set_title('ELA Difference Map\n(Amplified 20x)', fontsize=12, fontweight='bold')
    axes[2].axis('off')
    
    fig.suptitle('Fig 6.3: Error Level Analysis (ELA) — Demonstrating Compression Artifacts', 
                 fontsize=14, fontweight='bold', y=0.98)
    
    plt.tight_layout()
    output_path = output_dir / 'fig_6_3_ela_comparison.png'
    plt.savefig(output_path, dpi=300, bbox_inches='tight')
    plt.close()
    
    # Clean up temp file
    if os.path.exists(jpeg_path):
        os.remove(jpeg_path)
    
    print(f"✓ Generated Fig 6.3: ELA Visualization at {output_path}")
    
    # Return paths for reference
    return str(output_path)

if __name__ == "__main__":
    print("\n" + "="*70)
    print("ForgeGuard Report - ELA Visualization Generation")
    print("="*70 + "\n")
    
    output_path = generate_ela_visualization()
    
    print("\n" + "="*70)
    print(f"✓ ELA visualization saved to: {output_path}")
    print("="*70 + "\n")
