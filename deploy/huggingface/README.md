---
title: ForgeGuard API
emoji: 🛡️
colorFrom: blue
colorTo: gray
sdk: docker
app_port: 8000
pinned: false
short_description: Image-tampering and face-swap analysis API (research demo)
---

# ForgeGuard API (backend)

This Space runs the ForgeGuard backend: the Django API, the job worker and both
models in one container (`FORGEGUARD_ROLE=all`). The web UI is hosted
separately and calls this API directly.

**Source, documentation and model cards:** see the GitHub repository. This
Space is a deployment snapshot pushed by `.github/workflows/deploy-space.yml`;
do not edit it here.

**Limitations, in short:**
- The image model is **not validated**. It reports an experimental score and never gives a verdict.
- The video model gives a verdict only when frame-level evidence agrees, and otherwise says it is unsure.
- Results are probabilistic and must not be used for decisions about real people.

Uploads are deleted as soon as each job finishes.
