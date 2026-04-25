graph LR
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
