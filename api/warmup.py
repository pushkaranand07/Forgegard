"""
warmup.py — Load the models before the first request
====================================================
Started from config/wsgi.py when FORGEGUARD_WARMUP_MODELS is on. Runs in a
daemon thread so the worker accepts requests (and answers health checks)
while the checkpoints load; a request arriving mid-load simply waits on the
model cache lock.
"""

from __future__ import annotations

import logging
import os
import threading

from .common import image_model_path, video_model_path

logger = logging.getLogger("forgeguard.warmup")


def warmup() -> None:
    import torch

    from core.pipeline import image_processor, video_processor

    device = "cuda" if torch.cuda.is_available() else "cpu"
    jobs = [
        ("image", image_model_path(), lambda p: image_processor.load_model(p, torch.device(device))),
        ("video", video_model_path(), lambda p: video_processor.load_model(p, device=device)),
    ]
    for name, path, load in jobs:
        if not os.path.isfile(path):
            logger.warning("Skipping %s model warm-up: weights not found at %s", name, path)
            continue
        try:
            load(path)
        except Exception:
            logger.exception("Warm-up of the %s model failed", name)

    try:
        video_processor.get_face_extractor(device)
    except Exception:
        logger.exception("Warm-up of the MTCNN face detector failed")
    logger.info("Model warm-up finished on %s", device)


def start_warmup() -> threading.Thread:
    thread = threading.Thread(target=warmup, name="forgeguard-warmup", daemon=True)
    thread.start()
    return thread
