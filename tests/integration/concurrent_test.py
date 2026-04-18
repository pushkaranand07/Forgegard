import concurrent.futures
import requests
import psutil
import os

def send_request(video_path):
    with open(video_path, 'rb') as f:
        # Assuming server is running localhost 8000
        try:
            response = requests.post(
                'http://127.0.0.1:8000/api/detect-video/',
                files={'video': f},
                timeout=60
            )
            return response.status_code, response.json()
        except Exception as e:
            return 500, {'error': str(e), 'status': 'error'}

def get_memory_mb():
    process = psutil.Process(os.getpid())
    return process.memory_info().rss / (1024 * 1024)

if __name__ == '__main__':
    print(f"Memory Before: {get_memory_mb():.2f} MB")
    
    video_paths = ['real_01.mp4', 'fake_01.mp4', 'faceless_01.mp4',
                   'real_02.mp4', 'empty.mp4', 'audio_only.aac', 'fake_02.mp4']

    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
        results = list(executor.map(send_request, video_paths))

    for path, (status, body) in zip(video_paths, results):
        print(f"[{path}] HTTP {status} | Status: {body.get('status', 'N/A')} | Label: {body.get('label', 'N/A')}")
        
    print(f"Memory After: {get_memory_mb():.2f} MB")
