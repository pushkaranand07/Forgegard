"""
warmup.py — load the models before the first job
=================================================
Called by `manage.py run_worker` at startup so the first job does not pay the
multi-second checkpoint load. The web process never loads models.
"""

from __future__ import annotations

import logging
import os

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
