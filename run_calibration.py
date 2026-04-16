import requests, json, sys, time

# Wait for server to be ready
time.sleep(5)

try:
    r = requests.post(
        'http://127.0.0.1:8000/api/calibrate-image-threshold/',
        json={'validation_dir': 'C:/coding/my work/final year/ForgeGuard/data/ai_image_detection/val', 'metric': 'f1', 'save': True},
        timeout=900
    )
    print(f'Status: {r.status_code}')
    print(json.dumps(r.json(), indent=2))
    sys.exit(0 if r.status_code == 200 else 1)
except Exception as e:
    print(f'Error: {e}', file=sys.stderr)
    sys.exit(1)
