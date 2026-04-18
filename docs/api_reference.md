# ForgeGuard API Reference

ForgeGuard implements a dual-endpoint detection API via standard HTTP POST operations. Both endpoints return JSON responses. A dedicated `/api/detect-unified/` endpoint handles multi-modal inputs dynamically depending on their magic bytes.

## Endpoints

### 1. Video Deepfake Detection (`POST /api/detect-video/`)

Accurately classify deepfakes based on temporal and morphological pixel boundaries.

**Payload Requirements**
- Content-Type: `multipart/form-data`
- Body Parameter: `video` (File representation of the MP4/AVI clip. Maximum threshold dictates 100 MB caps).

**Success Response (200 OK)**
```json
{
    "label": "FAKE",
    "confidence_pct": 98.7,
    "device": "cuda",
    "processing_time_ms": 2154.2,
    "num_frames_processed": 32,
    "frame_predictions": [
        {"frame": 0, "confidence": 98.6},
        {"frame": 1, "confidence": 97.4}
    ]
}
```

### 2. Image Manipulation Detection (`POST /api/detect-image/`)

Classifies manipulated images (photoshops, generative faces) relying heavily on Level-1 Software specific flags and Level-2 Error-Level Analysis (ELA).

**Payload Requirements**
- Content-Type: `multipart/form-data`
- Body Parameter: `image` (JPEG/PNG variants)

**Success Response (200 OK)**
```json
{
    "label": "TAMPERED",
    "confidence_pct": 84.1,
    "device": "cuda",
    "level1": {
        "software_found": true,
        "software_signature": "Adobe Photoshop 2023",
        "notes": ["Software signature found: Adobe Photoshop 2023"]
    },
    "level2": {
        "authentic_prob": 0.158,
        "tampered_prob": 0.841,
        "method": "ELA + CNN"
    }
}
```

## Exceptions & Status Codes

All API endpoints map proprietary logic exceptions correctly to explicit API Status Codes:

| Exception Trigger | Detail | HTTP Status |
| --- | --- | --- |
| `InvalidFileException` | Incorrect Magic Bytes / Compression type | 400 Bad Request |
| `EmptyVideoException` | Missing visual payload but audio stream exists | 400 Bad Request |
| `NoVisualFramesException`| File was corrupted during pipeline iteration | 400 Bad Request |
| Server Side / OOM | Hardware Memory Exhaustion | 500 Internal Error |
