graph TD
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
