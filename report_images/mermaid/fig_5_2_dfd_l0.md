graph TD
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
