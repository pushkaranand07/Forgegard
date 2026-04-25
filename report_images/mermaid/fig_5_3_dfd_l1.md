graph TD
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
