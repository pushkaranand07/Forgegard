"""
Reproduce the audit's overload scenario against a running ForgeGuard (audit I6).

    python scripts/loadtest.py --base http://127.0.0.1:8000 --video clip.mp4 --image photo.jpg

While N videos are submitted at once to /api/detect-video/, it sends one image
to /api/detect-image/ and probes /api/health/live once a second. It reports:

- how fast each submission got an answer (200, 202 with a job, or 503 BUSY),
- the image request's latency,
- liveness latency under load (the audit saw 3/3 probes time out at 5 s),
- how long the queued videos took to finish, polled through /api/jobs/<id>/.

Prints a Markdown summary (paste it into docs/perf.md). Standard library only.
"""

from __future__ import annotations

import argparse
import json
import mimetypes
import statistics
import threading
import time
import urllib.error
import urllib.request
import uuid
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path


def _post_file(url: str, field: str, path: Path, timeout: float):
    boundary = uuid.uuid4().hex
    ctype = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
    body = (
        f"--{boundary}\r\nContent-Disposition: form-data; name=\"{field}\"; filename=\"{path.name}\"\r\n"
        f"Content-Type: {ctype}\r\n\r\n"
    ).encode() + path.read_bytes() + f"\r\n--{boundary}--\r\n".encode()
    req = urllib.request.Request(url, data=body, method="POST",
                                 headers={"Content-Type": f"multipart/form-data; boundary={boundary}"})
    return _send(req, timeout)


def _get(url: str, timeout: float):
    return _send(urllib.request.Request(url), timeout)


def _send(req, timeout: float):
    started = time.perf_counter()
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            status, raw = resp.status, resp.read()
    except urllib.error.HTTPError as err:
        status, raw = err.code, err.read()
    except Exception as err:  # timeout, connection refused, ...
        return None, {"error": type(err).__name__}, time.perf_counter() - started
    try:
        payload = json.loads(raw)
    except ValueError:
        payload = {}
    return status, payload, time.perf_counter() - started


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--base", default="http://127.0.0.1:8000")
    parser.add_argument("--video", type=Path, required=True)
    parser.add_argument("--image", type=Path, required=True)
    parser.add_argument("--videos", type=int, default=6)
    parser.add_argument("--probe-timeout", type=float, default=5.0, help="Docker HEALTHCHECK uses 5 s")
    args = parser.parse_args()
    base = args.base.rstrip("/")

    probes: list = []
    stop = threading.Event()

    def probe_liveness():
        while not stop.is_set():
            status, _, took = _get(f"{base}/api/health/live", args.probe_timeout)
            probes.append((status, took))
            stop.wait(1.0)

    prober = threading.Thread(target=probe_liveness, daemon=True)
    prober.start()

    t0 = time.perf_counter()
    with ThreadPoolExecutor(args.videos + 1) as pool:
        videos = [pool.submit(_post_file, f"{base}/api/detect-video/", "video", args.video, 600)
                  for _ in range(args.videos)]
        time.sleep(2)  # the image arrives while the videos are being processed
        image = pool.submit(_post_file, f"{base}/api/detect-image/", "image", args.image, 600)
        video_results = [f.result() for f in videos]
        image_result = image.result()

    # Follow queued videos to completion
    finished_at = {}
    pending = {i: r[1]["poll"] for i, r in enumerate(video_results) if r[0] == 202}
    while pending:
        for i, poll in list(pending.items()):
            status, payload, _ = _get(f"{base}{poll}", 30)
            if status == 200 and payload.get("status") in ("done", "failed"):
                finished_at[i] = time.perf_counter() - t0
                del pending[i]
        time.sleep(1)
    total = time.perf_counter() - t0
    stop.set()
    prober.join(timeout=args.probe_timeout + 2)

    codes = [r[0] for r in video_results]
    submit_lat = [r[2] for r in video_results]
    ok_probes = [took for status, took in probes if status == 200]
    failed_probes = sum(1 for status, _ in probes if status != 200)

    print(f"## Load test: {args.videos} concurrent videos + 1 image\n")
    print("| Measurement | Result |\n|---|---|")
    print(f"| Video submissions | {', '.join(f'{c}' for c in codes)} (HTTP status per request) |")
    print(f"| Video submission latency | max {max(submit_lat):.2f} s, median {statistics.median(submit_lat):.2f} s |")
    print(f"| 503 BUSY responses | {codes.count(503)} |")
    print(f"| Image request during load | HTTP {image_result[0]} in {image_result[2]:.2f} s |")
    if ok_probes:
        print(f"| Liveness probes | {len(ok_probes)}/{len(probes)} OK; median {statistics.median(ok_probes) * 1000:.0f} ms, "
              f"max {max(ok_probes) * 1000:.0f} ms; {failed_probes} failed/timed out (> {args.probe_timeout:.0f} s) |")
    else:
        print(f"| Liveness probes | 0/{len(probes)} OK |")
    if finished_at:
        done = sorted(finished_at.values())
        print(f"| Queued videos finished | {len(done)} jobs; first after {done[0]:.0f} s, last after {done[-1]:.0f} s |")
    print(f"| Total wall time | {total:.0f} s |")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
