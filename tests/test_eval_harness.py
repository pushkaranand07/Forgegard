"""The evaluation harness that decides whether a model may be marked "validated"."""

from __future__ import annotations

import csv
import hashlib

import numpy as np
import pytest
from PIL import Image

from core.pipeline import ela
from scripts import eval_image as ev
from scripts import make_splice_set as mk


# ── Metrics ──────────────────────────────────────────────────────────────────

def test_auc_is_one_for_perfect_ranking_and_zero_for_inverted():
    y = np.array([0, 0, 1, 1])
    assert ev.roc_auc(np.array([0.1, 0.2, 0.8, 0.9]), y) == 1.0
    assert ev.roc_auc(np.array([0.9, 0.8, 0.2, 0.1]), y) == 0.0


def test_auc_counts_ties_as_half():
    assert ev.roc_auc(np.array([0.5, 0.5, 0.5, 0.5]), np.array([0, 0, 1, 1])) == 0.5


def test_auc_matches_brute_force_on_random_data():
    rng = np.random.default_rng(0)
    s, y = rng.random(60), rng.integers(0, 2, 60)
    pos, neg = s[y == 1], s[y == 0]
    brute = np.mean([1.0 if p > n else 0.5 if p == n else 0.0 for p in pos for n in neg])
    assert ev.roc_auc(s, y) == pytest.approx(brute)


def test_balanced_accuracy_ignores_class_imbalance():
    y = np.array([0] * 9 + [1])
    always_authentic = np.zeros(10, dtype=int)
    assert ev.balanced_accuracy(always_authentic, y) == 0.5  # plain accuracy would say 0.9


def test_ece_is_zero_when_confidence_matches_accuracy():
    # Predicts "tampered" with 0.75 confidence; right 3 times out of 4
    assert ev.ece(np.array([0.75, 0.75, 0.75, 0.75]), np.array([1, 1, 1, 0])) == pytest.approx(0.0)


def test_ece_is_large_for_an_overconfident_coin_flip():
    assert ev.ece(np.array([0.99, 0.99, 0.01, 0.01]), np.array([1, 0, 1, 0])) == pytest.approx(0.49)


def test_bootstrap_interval_contains_the_point_estimate():
    rng = np.random.default_rng(1)
    y = np.repeat([0, 1], 40)
    s = rng.normal(loc=y * 0.8, scale=1.0)
    lo, hi = ev.bootstrap_auc_ci(s, y, n=500)
    assert lo < ev.roc_auc(s, y) < hi


def test_mean_ela_is_zero_for_a_flat_image_and_higher_for_noise():
    flat = Image.new("RGB", (64, 64), (128, 128, 128))
    noise = Image.fromarray(np.random.default_rng(2).integers(0, 255, (64, 64, 3), dtype=np.uint8))
    assert ela.mean_ela(flat) < 0.01 < ela.mean_ela(noise)


# ── Splice-set generator ─────────────────────────────────────────────────────

@pytest.fixture
def tiny_sources(tmp_path):
    rng = np.random.default_rng(3)
    paths = []
    for i in range(3):
        p = tmp_path / f"src{i}.png"
        Image.fromarray(rng.integers(0, 255, (360, 400, 3), dtype=np.uint8)).save(p)
        paths.append(p)
    return paths


def _digest(folder):
    return {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(folder.iterdir())}


def test_generator_is_deterministic_and_balanced(tiny_sources, tmp_path):
    assert mk.build(tiny_sources, tmp_path / "a", seed=7) == 12
    mk.build(tiny_sources, tmp_path / "b", seed=7)
    assert _digest(tmp_path / "a") == _digest(tmp_path / "b")

    with (tmp_path / "a" / "labels.csv").open(encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    assert sum(int(r["label"]) for r in rows) == 6
    assert {r["variant"] for r in rows} == {"auth_single", "splice_single", "auth_double", "splice_double"}
    assert all(bool(r["patch_x_y_size"]) == (r["label"] == "1") for r in rows)


def test_generator_seed_changes_the_set(tiny_sources, tmp_path):
    mk.build(tiny_sources, tmp_path / "a", seed=1)
    mk.build(tiny_sources, tmp_path / "b", seed=2)
    assert _digest(tmp_path / "a") != _digest(tmp_path / "b")


def test_kodak_hashes_are_pinned_for_all_24_images():
    assert len(mk.KODAK_SHA256) == 24
    assert all(len(h) == 64 for h in mk.KODAK_SHA256.values())


# ── Video harness ────────────────────────────────────────────────────────────

def test_video_rule_report_counts_decisions_unsure_and_errors():
    from scripts import eval_video as evv

    clips = [
        {"label": 1, "faces": 20, "face_scores": [0.95] * 20},                      # fake, caught
        {"label": 0, "faces": 20, "face_scores": [0.05] * 20},                      # real, cleared
        {"label": 0, "faces": 20, "face_scores": [0.1, 0.9] * 10},                  # real, faces disagree
        {"label": 0, "faces": 0, "face_scores": []},                                # no face
    ]
    report = evv.score_rules(clips)
    new, old = report["consensus_rule"], report["old_threshold_rule"]
    assert (new["decided"], new["unsure"], new["no_face"]) == (2, 1, 1)
    assert new["real_clips_called_fake"] == 0 and new["accuracy_when_decided"] == 1.0
    # The old rule decides the disagreeing clip by its average (0.5 -> FAKE): a false accusation
    assert old["decided"] == 3 and old["real_clips_called_fake"] == 1
