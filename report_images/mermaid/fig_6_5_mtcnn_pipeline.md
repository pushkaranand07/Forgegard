graph LR
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
