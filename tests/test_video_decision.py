"""Video verdicts need consensus among the per-face scores (remediation phase 3b).

Upstream's confident_strategy already defines consensus: many confidently fake
faces, or nearly all confidently real. When neither holds it silently averages,
and the average decided the verdict: a real person whose per-face scores
flip-flopped between 0.02 and 0.98 came out FAKE at 0.534. Now that case, and
videos with too few faces to judge, return UNSURE.
"""

from __future__ import annotations

import numpy as np
import pytest
import torch
from torch import nn

from core.pipeline import video_processor as vp

# Per-face scores measured on the two real clips investigated in phase 3b
FLIP_FLOP_REAL_PERSON = [0.0283, 0.9007, 0.8671, 0.7423, 0.0991, 0.1176, 0.0208, 0.0197, 0.2567, 0.9731,
                         0.6601, 0.7604, 0.9573, 0.9823, 0.2773, 0.269, 0.7191, 0.9771, 0.1293, 0.9187,
                         0.0511, 0.9681, 0.8872, 0.3411, 0.8252, 0.1262]
BEAUTY_FILTERED_REAL_PERSON = [0.77] + [0.99] * 25 + [0.5] * 4 + [0.02, 0.022]


def test_flip_flopping_scores_give_unsure_not_fake():
    label, score, note = vp.decide(FLIP_FLOP_REAL_PERSON)
    assert label == "UNSURE" and note == "NO_CONSENSUS"
    assert score == pytest.approx(np.mean(FLIP_FLOP_REAL_PERSON))  # the number is still reported


def test_consistent_fake_scores_give_fake():
    assert vp.decide([0.95] * 20)[0] == "FAKE"


def test_nearly_all_confident_real_scores_give_real():
    assert vp.decide([0.05] * 19 + [0.5])[0] == "REAL"


def test_a_consistently_flagged_real_person_stays_fake():
    """Documented limitation (beauty filter): consistent evidence is not overruled."""
    assert vp.decide(BEAUTY_FILTERED_REAL_PERSON)[0] == "FAKE"


@pytest.mark.parametrize("n", [1, 5, vp.MIN_FACES - 1])
def test_too_few_faces_give_unsure(n):
    label, _, note = vp.decide([0.05] * n)
    assert label == "UNSURE" and note == "TOO_FEW_FACES"


def test_twelve_confident_fakes_are_needed_for_fake():
    # Upstream requires more than 11 confident fakes (and > n // 2.5)
    assert vp.decide([0.95] * 11 + [0.5] * 9)[0] == "UNSURE"
    assert vp.decide([0.95] * 12 + [0.5] * 8)[0] == "FAKE"


@pytest.mark.parametrize("scores", [FLIP_FLOP_REAL_PERSON, BEAUTY_FILTERED_REAL_PERSON,
                                    [0.95] * 20, [0.05] * 20, [0.3, 0.6, 0.4]])
def test_decide_reports_confident_strategys_number_unchanged(scores):
    assert vp.decide(scores)[1] == pytest.approx(vp.confident_strategy(scores))


# ── Through the pipeline ─────────────────────────────────────────────────────

class _FixedScores(nn.Module):
    """Stands in for the B7 classifier: returns preset per-face scores as logits."""

    def __init__(self, scores):
        super().__init__()
        self.scores = list(scores)

    def forward(self, batch):
        out = [self.scores.pop(0) for _ in range(batch.shape[0])]
        p = torch.tensor(out).clamp(1e-6, 1 - 1e-6)
        return torch.log(p / (1 - p)).unsqueeze(1)


def _run(monkeypatch, scores):
    monkeypatch.setattr(vp, "load_model", lambda *a, **k: _FixedScores(scores))
    crops = [np.full((64, 64, 3), 128, np.uint8) for _ in scores]
    return vp.detect_video_frames(crops, "unused.pth", device="cpu", extract_faces=False)


def test_pipeline_returns_unsure_without_a_verdict_or_confidence(monkeypatch):
    result = _run(monkeypatch, FLIP_FLOP_REAL_PERSON)
    assert result.label == "UNSURE"
    assert result.predicted_class == -1
    assert result.confidence_pct is None
    assert result.fake_prob == pytest.approx(np.mean(FLIP_FLOP_REAL_PERSON), abs=1e-4)
    assert "NO_CONSENSUS" in result.notes


def test_pipeline_keeps_verdicts_when_the_faces_agree(monkeypatch):
    result = _run(monkeypatch, [0.97] * 24)
    assert result.label == "FAKE" and result.predicted_class == 0
    assert result.confidence_pct == pytest.approx(97, abs=0.5)
