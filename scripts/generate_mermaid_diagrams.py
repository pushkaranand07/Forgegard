"""
Mermaid Diagram Generation Script for ForgeGuard Report
Generates Mermaid.js code for system diagrams

These diagrams can be:
1. Embedded directly in HTML using mermaid script tag
2. Exported as SVG/PNG using mermaid-cli

Install mermaid-cli: npm install -g @mermaid-js/mermaid-cli
Export to PNG: mmdc -i diagram.md -o diagram.png
"""

import os
from pathlib import Path

# Create output directory
output_dir = Path("report_images/mermaid")
output_dir.mkdir(parents=True, exist_ok=True)

# ============================================================================
# FIG 5.1: 4-Layer System Architecture
# ============================================================================
mermaid_5_1 = """graph TD
    A["👤 Client Layer<br/>(Web Browser)"]
    B["🌐 API Layer<br/>(Django REST API)"]
    C["🧠 Business Logic Layer<br/>(ML Models + Processing)"]
    D["💾 Data Layer<br/>(SQLite/PostgreSQL)"]
    
    A -->|HTTP Requests| B
    B -->|Model Inference| C
    C -->|Query/Store Data| D
    D -->|Return Results| C
    C -->|JSON Response| B
    B -->|HTTP Response| A
    
    E["📁 File Storage<br/>(Images/Videos)"]
    C -->|Read Media Files| E
    
    style A fill:#e3f2fd
    style B fill:#f3e5f5
    style C fill:#e8f5e9
    style D fill:#fff3e0
    style E fill:#fce4ec
"""

# ============================================================================
# FIG 5.2: Level 0 DFD (Context Diagram)
# ============================================================================
mermaid_5_2 = """graph TD
    User["👤 User"]
    System["🎯 ForgeGuard<br/>Deepfake Detection System"]
    Storage["☁️ File Storage<br/>(Cloud/Local)"]
    MLModels["🧠 ML Models<br/>(External)"]
    
    User -->|Upload Media| System
    System -->|Detection Result| User
    User -->|Configure Settings| System
    System -->|Store Results| Storage
    System -->|Load Pre-trained Models| MLModels
    
    style User fill:#e3f2fd,stroke:#1976d2,stroke-width:2px
    style System fill:#c8e6c9,stroke:#388e3c,stroke-width:3px
    style Storage fill:#fff3e0,stroke:#f57c00,stroke-width:2px
    style MLModels fill:#f3e5f5,stroke:#7b1fa2,stroke-width:2px
"""

# ============================================================================
# FIG 5.3: Level 1 DFD (Major Processes)
# ============================================================================
mermaid_5_3 = """graph TD
    User["👤 User"]
    Web["🌐 Web Server<br/>(Django)"]
    ImgPipeline["🖼️ Image Detection<br/>Pipeline"]
    VidPipeline["🎬 Video Detection<br/>Pipeline"]
    Database["💾 Database"]
    Results["📊 Results Display"]
    
    User -->|1. Upload Media| Web
    Web -->|2a. Image File| ImgPipeline
    Web -->|2b. Video File| VidPipeline
    ImgPipeline -->|ELA + CNN| Web
    VidPipeline -->|MTCNN + Classifier| Web
    Web -->|3. Store Results| Database
    Web -->|4. Return JSON| Results
    Results -->|5. Display Results| User
    
    style User fill:#e3f2fd
    style Web fill:#f3e5f5
    style ImgPipeline fill:#ffe0b2
    style VidPipeline fill:#c8e6c9
    style Database fill:#ffccbc
    style Results fill:#f8bbd0
"""

# ============================================================================
# FIG 5.5: UML Use Case Diagram
# ============================================================================
mermaid_5_5 = """graph LR
    User["👤 User"]
    Analyst["📊 Analyst"]
    Admin["🔐 Admin"]
    
    System["ForgeGuard System"]
    
    UC1["Upload Image"]
    UC2["Upload Video"]
    UC3["View Result"]
    UC4["View Report"]
    UC5["Manage Models"]
    UC6["View Logs"]
    
    User -.->|use| UC1
    User -.->|use| UC2
    User -.->|use| UC3
    Analyst -.->|use| UC4
    Admin -.->|use| UC5
    Admin -.->|use| UC6
    
    UC1 -.->|include| UC3
    UC2 -.->|include| UC3
    
    style User fill:#e3f2fd
    style Analyst fill:#f3e5f5
    style Admin fill:#ffe0b2
    style System fill:#e8f5e9
"""

# ============================================================================
# FIG 6.5: MTCNN 3-Stage Pipeline
# ============================================================================
mermaid_6_5 = """graph LR
    Input["📸 Input Image<br/>(380x380)"]
    PNet["P-Net<br/>(Proposal)<br/>12x12 conv"]
    RNet["R-Net<br/>(Refinement)<br/>24x24 conv"]
    ONet["O-Net<br/>(Output)<br/>48x48 conv"]
    Output["✅ Face Detections<br/>(Bounding Box +<br/>Landmarks)"]
    
    Input -->|Stage 1| PNet
    PNet -->|Candidate| RNet
    RNet -->|Refined| ONet
    ONet -->|Final| Output
    
    style Input fill:#e3f2fd
    style PNet fill:#fff9c4
    style RNet fill:#ffe0b2
    style ONet fill:#ffccbc
    style Output fill:#c8e6c9
"""

# ============================================================================
# FIG 9.1: Production Deployment Architecture
# ============================================================================
mermaid_9_1 = """graph TD
    Client["🖥️ Client Browser"]
    CDN["🚀 CDN<br/>(Static Files)"]
    LB["⚖️ Load Balancer"]
    Nginx["🔒 Nginx Reverse Proxy<br/>(SSL/TLS)"]
    
    W1["⚙️ Gunicorn Worker 1"]
    W2["⚙️ Gunicorn Worker 2"]
    W3["⚙️ Gunicorn Worker 3"]
    W4["⚙️ Gunicorn Worker 4"]
    
    Django["🐍 Django Application"]
    Models["🧠 PyTorch Models"]
    GPU["🎮 GPU (Optional)"]
    
    PgSQL["🗄️ PostgreSQL<br/>Database"]
    Storage["💾 File Storage<br/>(S3/NAS)"]
    
    Client -->|HTTPS| CDN
    Client -->|HTTPS| LB
    LB --> Nginx
    Nginx --> W1
    Nginx --> W2
    Nginx --> W3
    Nginx --> W4
    
    W1 --> Django
    W2 --> Django
    W3 --> Django
    W4 --> Django
    
    Django --> Models
    Models --> GPU
    Django --> PgSQL
    Django --> Storage
    
    style Client fill:#e3f2fd
    style Nginx fill:#fff9c4
    style W1 fill:#ffe0b2
    style W2 fill:#ffe0b2
    style W3 fill:#ffe0b2
    style W4 fill:#ffe0b2
    style Django fill:#f3e5f5
    style Models fill:#e8f5e9
    style GPU fill:#ffccbc
    style PgSQL fill:#ffcdd2
    style Storage fill:#c8e6c9
"""

# ============================================================================
# Save all diagrams to files
# ============================================================================
diagrams = {
    "fig_5_1_architecture.md": mermaid_5_1,
    "fig_5_2_dfd_l0.md": mermaid_5_2,
    "fig_5_3_dfd_l1.md": mermaid_5_3,
    "fig_5_5_usecase.md": mermaid_5_5,
    "fig_6_5_mtcnn_pipeline.md": mermaid_6_5,
    "fig_9_1_production_architecture.md": mermaid_9_1,
}

def main():
    print("\n" + "="*70)
    print("ForgeGuard Report - Mermaid Diagram Generation")
    print("="*70 + "\n")
    
    for filename, diagram_code in diagrams.items():
        filepath = output_dir / filename
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(diagram_code)
        print(f"✓ Generated {filename}")
    
    print("\n" + "="*70)
    print("To export Mermaid diagrams as PNG:")
    print("1. Install mermaid-cli: npm install -g @mermaid-js/mermaid-cli")
    print("2. Run: mmdc -i report_images/mermaid/fig_5_1_architecture.md -o report_images/diagrams/fig_5_1_architecture.png")
    print("\nOr embed directly in HTML:")
    print("<script src='https://cdn.jsdelivr.net/npm/mermaid/dist/mermaid.min.js'></script>")
    print("<div class='mermaid'>[paste diagram code here]</div>")
    print("="*70 + "\n")

if __name__ == "__main__":
    main()
