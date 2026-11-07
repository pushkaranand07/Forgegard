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

None. `pip-audit` runs in CI with no ignored IDs.

Previously accepted (2026-11-08) and since resolved: PYSEC-2026-3447 and
GHSA-xmj3-9gf7-h52w in setuptools 81, which torch 2.11 capped below 82. Upgrading to
torch 2.15 lifted the cap; setuptools 84.2.1 includes both fixes.

## Secrets in git history

CI scans the full history with gitleaks (`.gitleaks.toml`: default rules plus a
rule for literal Django `SECRET_KEY`s, which the defaults miss).

One finding is reviewed and allow-listed by fingerprint in `.gitleaksignore`:

- **Old hard-coded `SECRET_KEY`** in `Django Application/project_settings/settings.py`,
  added in `6983d82fd` (2020) and removed from the code on 2026-04-17. None of the four
  deployments recorded by GitHub (the earliest is 2026-09-28) contained it; each
  deployed commit was checked. Deployments made outside GitHub's integration, if any,
  can't be checked this way. The key signs only Django sessions and CSRF tokens,
  ForgeGuard has no accounts, and current settings refuse to start in production
  without a new key, so it was not rotated.

## Hardening checks in CI

- `manage.py check --deploy --fail-level WARNING`: any deployment warning fails the build.
- The web UI is served with a strict Content-Security-Policy (`api/views.py`): scripts
  only from the site itself plus the exact hash of the inline theme script.

## Reporting a vulnerability

Open a private security advisory on the GitHub repository rather than a public issue.
