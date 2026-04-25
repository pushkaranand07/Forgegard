# ForgeGuard Report — Image Generation Strategy

## Overview
This document provides a systematic approach to generate all 31 figures for your project report. Images are categorized by type, with recommended tools and workflows for each category.

---

## Category 1: Technical Diagrams (Using draw.io)
**Tool**: [draw.io (diagrams.net)](https://app.diagrams.net/) — FREE, no signup required

### How to Use draw.io:
1. Go to https://app.diagrams.net/
2. Click "Create New Diagram"
3. Select template (blank or relevant type: UML, Network, Flowchart)
4. Use the drag-and-drop shapes library on the left
5. Export as PNG (File → Export As → PNG)

### Diagrams to Create:

| Fig # | Name | Type | Key Elements | Draw.io Template |
|-------|------|------|--------------|------------------|
| **5.1** | 4-Layer Architecture | System Diagram | Presentation Layer, Business Logic, Data Layer, Database | Blank + shapes |
| **5.2** | Level 0 DFD | Data Flow | User → System → External Storage | DFD template |
| **5.3** | Level 1 DFD | Data Flow | API Gateway, Image Pipeline, Video Pipeline, ML Models | DFD template |
| **5.4** | Level 2 DFD (Image) | Data Flow | Preprocessing, ELA, Model, Classification | DFD template |
| **5.5** | Use Case Diagram | UML | User, Analyst, Admin; Use cases (Upload, Detect, View Report) | UML template |
| **5.6** | Class Diagram | UML | DeepFakeClassifier, IMDModel, VideoDetectionResult, ImageDetectionResult | UML template |
| **5.7** | Sequence Diagram | UML | User → View → API → Model → Database | UML Sequence |
| **5.8** | ER Diagram | Database | Tables: User, Session, DetectionLog (if any) | ER template |
| **5.9** | API Response Tree | Tree Structure | Response → metadata → predictions → confidence/label | Tree template |
| **6.4** | EfficientNet B7 Scaling | Comparison | Show baseline model vs. compound scaling (depth, width, resolution) | Blank + shapes |
| **6.5** | MTCNN 3-Stage Pipeline | Process Flow | P-Net → R-Net → O-Net with bounding boxes | Blank + flowchart |
| **9.1** | Production Architecture | System Diagram | Client → Nginx → Gunicorn (workers) → Django → PostgreSQL | System template |
| **9.2** | Security Flow | Flowchart | Request → HTTPS/SSL → Validation → Model → Response | Flowchart template |

---

## Category 2: Charts & Graphs (Using Python + matplotlib/seaborn)
**Tool**: Python scripts (run locally, export as PNG)

### Script Location: `scripts/generate_charts.py` (provided below)

| Fig # | Name | Type | Data Source |
|-------|------|------|-------------|
| **3.1** | Papers Published 2017-2024 | Bar Chart | Custom data (from literature review) |
| **3.2** | Tool Feature Comparison | Bar/Radar Chart | Custom comparison table |
| **4.1** | Feasibility Pie Chart | Pie Chart | 3 segments (Technical, Operational, Economic) |
| **7.2** | Accuracy Comparison | Bar Chart | Results from project report |
| **7.3** | Processing Time vs. File Size | Line/Scatter | Benchmark results |
| **7.4** | Confusion Matrix | Heatmap | TP/TN/FP/FN values |

---

## Category 3: Architecture Diagrams (Using Mermaid or draw.io)
**Alternative to draw.io**: Mermaid.js diagrams (can be embedded in HTML)

### Recommended Mermaid Diagrams:
```
graph TD
    A[Client] --> B[Nginx Reverse Proxy]
    B --> C[Gunicorn Workers]
    C --> D[Django Application]
    D --> E[PyTorch Models]
    E --> F[GPU/CPU Inference]
```

---

## Category 4: Screenshots (Manual Collection)
**Tool**: VS Code built-in screenshot + Snipping Tool

| Fig # | Name | Source | How to Capture |
|-------|------|--------|-----------------|
| **1.1** | College Logo | College website / provided by you | Take screenshot or save logo image |
| **1.3** | CSE Lab Photo | Your college campus | Take real photo with phone/camera |
| **6.1** | Project Directory Tree | VS Code | File Explorer → Right-click → Screenshot |
| **6.6-6.12** | 7 App Screenshots | Running ForgeGuard app | Chrome DevTools → Run locally → Screenshot each page |
| **7.5** | NO_FACE_DETECTED API | Postman or cURL | POST request → screenshot JSON response |

---

## Category 5: Technical Visualizations (Using Python)
**Tool**: Python + PIL/OpenCV/matplotlib

| Fig # | Name | Type | How to Generate |
|-------|------|------|-----------------|
| **6.2** | IMDModel CNN Architecture | Neural Network Diagram | Use NN-SVG tool online |
| **6.3** | ELA Comparison | Image Processing | Python script: original → compressed → ELA diff |

---

## Generation Workflow (Step-by-Step)

### Phase 1: Automatic Generation (Today) ✓
1. Generate all Python chart scripts
2. Create Mermaid diagrams for quick reference
3. Output PNG files to `report_images/`

### Phase 2: Semi-Automated (This week)
1. Use draw.io templates (copy-paste provided templates)
2. Export as PNG to `report_images/`

### Phase 3: Manual Collection (As needed)
1. Screenshots from running application
2. College logo/photos

### Phase 4: Integration
1. Insert all PNG files into HTML report
2. Update figure captions and references

---

## Recommended Directory Structure
```
ForgeGuard/
├── report_images/                 # All generated images go here
│   ├── diagrams/                  # draw.io exports
│   │   ├── 5.1_architecture.png
│   │   ├── 5.2_dfd_l0.png
│   │   ├── 5.3_dfd_l1.png
│   │   └── ...
│   ├── charts/                    # Python-generated charts
│   │   ├── 3.1_papers_timeline.png
│   │   ├── 7.2_accuracy_comparison.png
│   │   └── ...
│   ├── screenshots/               # Application UI screenshots
│   │   ├── 6.6_home_page.png
│   │   ├── 6.7_video_upload.png
│   │   └── ...
│   └── manual/                    # User-provided images
│       ├── 1.1_college_logo.png
│       ├── 1.3_lab_photo.jpg
│       └── ...
└── scripts/
    ├── generate_charts.py         # Python chart generator
    ├── generate_diagrams.py       # Mermaid diagram generator
    └── draw_io_templates/         # draw.io XML templates
```

---

## Tools Summary

| Category | Tool | Cost | Setup |
|----------|------|------|-------|
| Diagrams | draw.io | FREE | No signup, just open in browser |
| Charts | Python (matplotlib, seaborn) | FREE | Already installed |
| Mermaid | Mermaid.js | FREE | Embedded in HTML/Markdown |
| Screenshots | VS Code / Snipping Tool | FREE | Built-in Windows tool |
| CNN Viz | NN-SVG | FREE | Web-based tool |
| ELA Viz | Python + PIL/OpenCV | FREE | Script provided below |

---

## Next Steps

1. **Today**: Generate Python charts + Mermaid diagrams
2. **This week**: Create draw.io diagrams (use templates)
3. **By end of week**: Collect screenshots from running app
4. **Final**: Insert all images into HTML report

---

*This strategy allows you to generate ~60% of images automatically, 30% with draw.io templates, and 10% manual collection.*
