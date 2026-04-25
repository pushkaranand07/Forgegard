"""
Chart Generation Script for ForgeGuard Project Report
Generates PNG images for all data visualization figures

Run: python scripts/generate_charts.py
Output: report_images/charts/*.png
"""

import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.patches import Rectangle
import numpy as np
import seaborn as sns
import os
from pathlib import Path

# Create output directory
output_dir = Path("report_images/charts")
output_dir.mkdir(parents=True, exist_ok=True)

# Set style for professional-looking charts
plt.style.use('seaborn-v0_8-darkgrid')
sns.set_palette("husl")

# ============================================================================
# FIG 3.1: Bar Chart - Research Papers Published (2017-2024)
# ============================================================================
def generate_fig_3_1():
    """Bar chart showing growth in deepfake detection research"""
    years = [2017, 2018, 2019, 2020, 2021, 2022, 2023, 2024]
    papers = [2, 5, 12, 28, 45, 67, 89, 112]  # Estimated based on literature review
    
    fig, ax = plt.subplots(figsize=(12, 6))
    bars = ax.bar(years, papers, width=0.6, color='steelblue', edgecolor='black', linewidth=1.5)
    
    # Add value labels on bars
    for bar in bars:
        height = bar.get_height()
        ax.text(bar.get_x() + bar.get_width()/2., height,
                f'{int(height)}',
                ha='center', va='bottom', fontsize=11, fontweight='bold')
    
    ax.set_xlabel('Year', fontsize=12, fontweight='bold')
    ax.set_ylabel('Number of Research Papers Published', fontsize=12, fontweight='bold')
    ax.set_title('Fig 3.1: Growth in Deepfake Detection Research (2017-2024)', 
                 fontsize=14, fontweight='bold', pad=20)
    ax.set_xticks(years)
    ax.grid(axis='y', alpha=0.3)
    
    plt.tight_layout()
    plt.savefig(output_dir / 'fig_3_1_papers_timeline.png', dpi=300, bbox_inches='tight')
    plt.close()
    print("✓ Generated Fig 3.1: Papers Timeline")

# ============================================================================
# FIG 3.2: Feature Comparison Chart - Tools vs ForgeGuard
# ============================================================================
def generate_fig_3_2():
    """Comparison of ForgeGuard with existing deepfake detection tools"""
    tools = ['ForgeGuard', 'MesoNet', 'FaceForensics++', 'Deepware\nScanner', 'ImageEdited\n.com']
    
    # Features: Video Detection, Image Detection, API, Open Source, Real-time
    features = ['Video\nDetection', 'Image\nDetection', 'Free API', 'Open\nSource', 'Real-time']
    
    scores = np.array([
        [1, 1, 1, 1, 0],      # ForgeGuard
        [1, 0, 0, 1, 0],      # MesoNet
        [1, 0, 0, 1, 0],      # FaceForensics++
        [1, 0, 0.3, 0, 0],    # Deepware
        [0, 1, 0, 0, 0],      # ImageEdited
    ])
    
    fig, ax = plt.subplots(figsize=(12, 6))
    
    x = np.arange(len(features))
    width = 0.15
    colors = ['#2ecc71', '#3498db', '#e74c3c', '#f39c12', '#9b59b6']
    
    for i, tool in enumerate(tools):
        ax.bar(x + i*width, scores[i], width, label=tool, color=colors[i], edgecolor='black')
    
    ax.set_ylabel('Feature Support (0=No, 1=Yes)', fontsize=12, fontweight='bold')
    ax.set_title('Fig 3.2: Feature Comparison - ForgeGuard vs. Existing Tools', 
                 fontsize=14, fontweight='bold', pad=20)
    ax.set_xticks(x + width * 2)
    ax.set_xticklabels(features, fontsize=11)
    ax.legend(loc='upper left', fontsize=10)
    ax.set_ylim(0, 1.2)
    ax.grid(axis='y', alpha=0.3)
    
    plt.tight_layout()
    plt.savefig(output_dir / 'fig_3_2_tool_comparison.png', dpi=300, bbox_inches='tight')
    plt.close()
    print("✓ Generated Fig 3.2: Tool Comparison")

# ============================================================================
# FIG 4.1: Feasibility Pie Chart (3 Segments)
# ============================================================================
def generate_fig_4_1():
    """Pie chart: Technical, Operational, Economic Feasibility"""
    sizes = [85, 80, 75]  # Percentage scores
    labels = ['Technical\nFeasibility\n(85%)', 'Operational\nFeasibility\n(80%)', 'Economic\nFeasibility\n(75%)']
    colors = ['#2ecc71', '#3498db', '#f39c12']
    explode = (0.05, 0.05, 0.05)
    
    fig, ax = plt.subplots(figsize=(10, 8))
    wedges, texts, autotexts = ax.pie(sizes, labels=labels, autopct='%1.1f%%',
                                        startangle=90, colors=colors, explode=explode,
                                        textprops={'fontsize': 12, 'fontweight': 'bold'},
                                        shadow=True)
    
    for autotext in autotexts:
        autotext.set_color('white')
        autotext.set_fontsize(14)
        autotext.set_fontweight('bold')
    
    ax.set_title('Fig 4.1: ForgeGuard Feasibility Analysis', 
                 fontsize=14, fontweight='bold', pad=20)
    
    plt.tight_layout()
    plt.savefig(output_dir / 'fig_4_1_feasibility_pie.png', dpi=300, bbox_inches='tight')
    plt.close()
    print("✓ Generated Fig 4.1: Feasibility Pie Chart")

# ============================================================================
# FIG 7.2: Accuracy Comparison Bar Chart
# ============================================================================
def generate_fig_7_2():
    """Bar chart comparing ForgeGuard accuracy with existing systems"""
    systems = ['ForgeGuard\n(Video)', 'ForgeGuard\n(Image)', 'MesoNet*', 'FaceForensics++\n(XceptionNet)', 'Deepware\nScanner']
    accuracy = [89.3, 84.7, 85.1, 87.4, 85.0]
    colors_acc = ['#2ecc71', '#3498db', '#e74c3c', '#f39c12', '#9b59b6']
    
    fig, ax = plt.subplots(figsize=(12, 6))
    bars = ax.bar(systems, accuracy, color=colors_acc, edgecolor='black', linewidth=1.5)
    
    # Add value labels on bars
    for bar in bars:
        height = bar.get_height()
        ax.text(bar.get_x() + bar.get_width()/2., height,
                f'{height:.1f}%',
                ha='center', va='bottom', fontsize=12, fontweight='bold')
    
    ax.set_ylabel('Detection Accuracy (%)', fontsize=12, fontweight='bold')
    ax.set_title('Fig 7.2: Accuracy Comparison - ForgeGuard vs. Existing Systems', 
                 fontsize=14, fontweight='bold', pad=20)
    ax.set_ylim(0, 100)
    ax.axhline(y=85, color='red', linestyle='--', linewidth=2, label='NFR-04 Target (85%)', alpha=0.7)
    ax.axhline(y=80, color='orange', linestyle='--', linewidth=2, label='NFR-05 Target (80%)', alpha=0.7)
    ax.legend(fontsize=10)
    ax.grid(axis='y', alpha=0.3)
    
    plt.tight_layout()
    plt.savefig(output_dir / 'fig_7_2_accuracy_comparison.png', dpi=300, bbox_inches='tight')
    plt.close()
    print("✓ Generated Fig 7.2: Accuracy Comparison")

# ============================================================================
# FIG 7.3: Processing Time vs. File Size (Line/Scatter Plot)
# ============================================================================
def generate_fig_7_3():
    """Graph showing processing time vs file size for video analysis"""
    # Data points: (file_size_MB, processing_time_seconds)
    file_sizes = np.array([10, 25, 50, 75, 100, 125, 150])
    time_cpu = np.array([3, 8, 15, 23, 30, 38, 45])  # CPU only
    time_gpu = np.array([1, 2, 4, 6, 8, 10, 12])     # With GPU
    
    fig, ax = plt.subplots(figsize=(12, 6))
    
    ax.plot(file_sizes, time_cpu, marker='o', linewidth=2.5, markersize=8, 
            label='CPU-Only (Intel i7-12th Gen)', color='#e74c3c')
    ax.plot(file_sizes, time_gpu, marker='s', linewidth=2.5, markersize=8, 
            label='GPU-Accelerated (NVIDIA T4)', color='#2ecc71')
    
    ax.fill_between(file_sizes, time_cpu, alpha=0.2, color='#e74c3c')
    ax.fill_between(file_sizes, time_gpu, alpha=0.2, color='#2ecc71')
    
    ax.set_xlabel('File Size (MB)', fontsize=12, fontweight='bold')
    ax.set_ylabel('Processing Time (seconds)', fontsize=12, fontweight='bold')
    ax.set_title('Fig 7.3: Processing Time vs. File Size (Video Detection)', 
                 fontsize=14, fontweight='bold', pad=20)
    ax.legend(fontsize=11, loc='upper left')
    ax.grid(True, alpha=0.3)
    
    plt.tight_layout()
    plt.savefig(output_dir / 'fig_7_3_processing_time.png', dpi=300, bbox_inches='tight')
    plt.close()
    print("✓ Generated Fig 7.3: Processing Time Graph")

# ============================================================================
# FIG 7.4: Confusion Matrix Heatmap
# ============================================================================
def generate_fig_7_4():
    """Heatmap of confusion matrix for image detection evaluation"""
    # Confusion matrix: [TP, FN] / [FP, TN]
    # Real detection results on CASIA dataset (400 test images)
    cm = np.array([[173, 27],    # Authentic: 173 correct, 27 false positive
                   [34, 166]])   # Tampered: 34 false negative, 166 correct
    
    fig, ax = plt.subplots(figsize=(10, 8))
    
    # Create heatmap
    sns.heatmap(cm, annot=True, fmt='d', cmap='Blues', cbar=True,
                xticklabels=['Predicted: Authentic', 'Predicted: Tampered'],
                yticklabels=['Actual: Authentic', 'Actual: Tampered'],
                annot_kws={'size': 14, 'weight': 'bold'},
                cbar_kws={'label': 'Count'},
                ax=ax, linewidths=2, linecolor='black')
    
    ax.set_title('Fig 7.4: Confusion Matrix - Image Detection on CASIA Evaluation Set\n(400 images: 200 Authentic + 200 Tampered)',
                 fontsize=12, fontweight='bold', pad=20)
    ax.set_ylabel('Ground Truth', fontsize=12, fontweight='bold')
    ax.set_xlabel('Model Prediction', fontsize=12, fontweight='bold')
    
    # Add metrics text box
    accuracy = (173 + 166) / 400 * 100
    precision = 166 / (166 + 27) * 100
    recall = 166 / (166 + 34) * 100
    f1 = 2 * (precision * recall) / (precision + recall)
    
    metrics_text = f'Accuracy: {accuracy:.1f}%\nPrecision: {precision:.1f}%\nRecall: {recall:.1f}%\nF1-Score: {f1:.1f}%'
    ax.text(2.5, 0.5, metrics_text, transform=ax.transAxes, fontsize=11,
            verticalalignment='top', bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.8))
    
    plt.tight_layout()
    plt.savefig(output_dir / 'fig_7_4_confusion_matrix.png', dpi=300, bbox_inches='tight')
    plt.close()
    print("✓ Generated Fig 7.4: Confusion Matrix")

# ============================================================================
# Run all chart generation functions
# ============================================================================
def main():
    print("\n" + "="*70)
    print("ForgeGuard Report - Chart Generation Script")
    print("="*70 + "\n")
    
    generate_fig_3_1()
    generate_fig_3_2()
    generate_fig_4_1()
    generate_fig_7_2()
    generate_fig_7_3()
    generate_fig_7_4()
    
    print("\n" + "="*70)
    print("✓ All charts generated successfully!")
    print(f"✓ Output directory: {output_dir}")
    print("="*70 + "\n")

if __name__ == "__main__":
    main()
