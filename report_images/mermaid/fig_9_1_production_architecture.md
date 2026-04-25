graph TD
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
