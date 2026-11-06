# Golden samples

`expected.json` holds the scores the real models produced for each file in `media/`, recorded on CPU by `scripts/record_golden.py`. `tests/test_golden.py` checks that the live pipeline reproduces them within ±0.02. These are regression checks, **not accuracy measurements**.

## Current fixtures

| File | What it is |
|---|---|
| `synthetic_*.jpg/png` | Deterministic, generated images (gradient plus noise at different JPEG qualities, and one pasted patch). Licence-free. They make the image pipeline produce scores across the whole 0–1 range. |
| *(videos)* | **Pending.** Needs clips the owner can publish: a self-recorded ≤ 3 s face clip (real), and a face-swap clip whose licence allows redistribution (fake). |

## Rules

- **Never commit media from DFDC, Celeb-DF or CASIA.** Their licences forbid redistribution.
- Re-record (`python scripts/record_golden.py`) only after an intentional pipeline change, and explain the change in the commit message.
- A side observation from building this set: the synthetic images show the ELA model's score swinging from about 0.00 to about 1.00 on the *same* content, depending only on added noise and JPEG quality. The lossless PNG scores 1.0 (tampered). This is consistent with the documented limitation that ELA reacts to compression history and noise rather than to manipulation as such. It will be measured properly in the Phase 3 stress test.
