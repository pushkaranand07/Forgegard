# Security

## Threat model

ForgeGuard accepts **untrusted media from anonymous clients** and returns an analysis.
It has no user accounts, stores no records, and by default keeps no uploads.

| Asset | Threat | Control |
|---|---|---|
| Server process | Malicious file exploits a decoder (memory corruption) | Only JPEG, PNG and WebP reach Pillow, checked from the file's bytes, not its name; Pillow kept free of known CVEs |
| Server memory | Small file that decodes to a huge image or video | Pixel caps checked before decoding; ELA and video frames processed with bounded memory |
| Server disk | Uploads written without limit | Scratch files deleted after every request; nothing kept unless `FORGEGUARD_KEEP_UPLOADS=true` |
| Availability | Request floods | Per-IP rate limit on detection endpoints; bounded inference concurrency |
| Response contents | Leaking paths, stack traces or internals | Fixed JSON error shape; details only in server logs |

## Accepted findings

Known vulnerabilities that `pip-audit` reports but that are not reachable in ForgeGuard.
CI ignores exactly these IDs (`.github/workflows/ci.yml`, `Makefile`). Review each one
whenever the dependency that pins it is upgraded.

| ID | Package | Why it is accepted | Pinned by | Review when |
|---|---|---|---|---|
| PYSEC-2026-3447 | setuptools 81 | Affects building source distributions from `MANIFEST.in`. ForgeGuard never builds sdists at runtime or in its image. | `torch 2.11` requires `setuptools<82` | torch is upgraded |
| GHSA-xmj3-9gf7-h52w | setuptools 81 | Affects setuptools' legacy wheel installation on Windows. The service never installs packages at runtime; images are built on Linux with uv. | `torch 2.11` requires `setuptools<82` | torch is upgraded |

## Reporting a vulnerability

Open a private security advisory on the GitHub repository rather than a public issue.
