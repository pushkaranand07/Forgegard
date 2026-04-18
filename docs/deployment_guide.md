# ForgeGuard Deployment Guide

## System Requirements
- **OS**: Windows / Linux (Ubuntu 20.04+ recommended)
- **Engine**: CUDA 11.8+ (NVIDIA GPU required for inference < 5 seconds)
- **RAM**: Minimum 16GB (32GB+ recommended)
- **Storage**: ~2GB Disk space minimum for weights

## Environment Setup
1. Instantiate the conda environment natively. Avoid Python version mismatches by locking exactly to Python 3.9+.
```bash
conda env create -f environment.yml
conda activate ForgeGuard
```

## Django WSGI / ASGI Configuration
While local development utilizes `python manage.py runserver`, production environments should immediately transition to WSGI/ASGI handlers (e.g., Gunicorn or Daphne) mapped behind NGINX.

**Example Gunicorn Configuration:**
```bash
gunicorn config.wsgi:application \
    --workers 4 \
    --timeout 120 \
    --bind 127.0.0.1:8000
```
*Note on Workers*: Each Django worker instantiated via Gunicorn will instantiate a separate instance of the PyTorch DeepfakeClassifier if memory is not managed. It is highly recommended to offload inference logic to a secondary background queue (Celery/Redis) rather than tying it to the Django synchronous request thread, though `ForgeGuard` uses Thread Pooling Singletons for VRAM mitigation on local instances.

## NGINX Reverse Proxy
Ensure that the NGINX configuration allocates massive client buffer sizes, since video payloads frequently exceed traditional web traffic limitations.

```nginx
server {
    listen 80;
    server_name forgeguard.internal;

    # Override 1MB default limits
    client_max_body_size 150M;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    }
}
```

## Health Checks
Ping the models passively using the internal network:
```bash
curl -X POST http://127.0.0.1:8000/api/detect-unified/ -F "video=@test.mp4"
```
Check `logs/deepguard.log` for Stack Traces correlating to Model Thread Locks or OOM exceptions.
