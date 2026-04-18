# Pipeline Architecture

## Design Philosophy
I designed the ForgeGuard architecture emphasizing concurrency, absolute data integrity, and pipeline decouple-ability. A classic machine learning flaw is entangling data-munging and inference code, which leads to rigid systems incapable of scaling behind web interfaces (like Django). To solve this, I split the video analysis process logically, introducing a multi-tiered component pipeline ensuring clear separations of concern while maximizing VRAM utilization across parallel HTTP requests.

## Component Breakdown

1. **Video Ingestion Layer (VideoReader)**
   Handling video files safely is computationally tricky. Instead of brute-force dumping thousands of frames to RAM, the VideoReader samples exactly `N` equidistant frames mathematically. This normalizes long videos against short videos, ensuring computational latency stays consistent for the end-user.

2. **Face Detection Layer (MTCNN/FaceDetectionEngine)**
   A CNN can't effectively predict manipulation if the subject is pushed to the margins of a frame. I integrated the PyTorch MTCNN implementation, extracting precisely bound facial anchor boxes. To combat noise, MTCNN returns a secondary padding layer (h//3, w//3) to supply the final classifier with essential morphological boundary context connecting the chin/forehead to the synthetic backdrop.

3. **Classification Layer (EfficientNet B7 Wrapper)**
   The core intelligence node relies on EfficientNet B7. Pre-processed RGB face tensors (normalized, permuted to `[C,H,W]`, and isotropically padded) are batched over CUDA arrays and routed directly to this 64+ million parameter backbone to output float predictions across the binary logistic layer.

4. **Exception Handling Layer**
   Real world deployments face invalid formats, empty zero-byte streams, and audio-only MP4 files. I architected a proprietary Exception tree (`InvalidFileException`, `EmptyVideoException`, `NoVisualFramesException`) mapping gracefully back to Django REST Response endpoints (HTTP 400). If humans are not detected in a frame stack (`NoFaceDetected`), the engine safely short-circuits rather than randomly hallucinating probabilities.

5. **API Response Layer**
   Built securely using Django REST, endpoints `/api/detect-video/` and `/api/detect-image/` abstract the entire machine learning cycle. 

## Key Engineering Decisions
- **Thread-safe Singleton Caching**: Loading multi-gigabyte models for every request would crash servers immediately. I employed a thread-locking Singleton caching map storing PyTorch objects purely in VRAM for all subsequent inference triggers.
- **Early Exit For Faceless Media**: Processing empty background landscapes is mathematically useless. Returning an `UNSURE` baseline when MTCNN drops `0` detected faces saves critical GPU time and prevents statistical polling failures on the front end.
- **Strict RGB Pipeline Enforcement**: Enforcing consistent color space conversions from OpenCV (`BGR`) directly to PIL (`RGB`) inside the bounding logic eliminated tensor channel inversions discovered during testing.
