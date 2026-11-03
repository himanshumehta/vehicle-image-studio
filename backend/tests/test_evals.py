"""The eval metrics (evals/metrics.py) and fixtures, on small synthetic before/after pairs."""
import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from evals.fixtures import build_scene  # noqa: E402
from evals.metrics import PSNR_CAP_DB, edit_preservation, mask_iou, preservation_verdict  # noqa: E402


@pytest.fixture
def pair():
    rng = np.random.default_rng(0)
    before = rng.integers(0, 256, size=(120, 160, 3), dtype=np.uint8)
    mask = np.zeros((120, 160), dtype=bool)
    mask[50:70, 60:100] = True  # the "plate"
    return before, mask


def test_edit_inside_the_mask_passes(pair):
    before, mask = pair
    after = before.copy()
    after[mask] = 255
    score = edit_preservation(before, after, mask)
    assert score.changed_outside_frac == 0 and score.psnr_outside_db == PSNR_CAP_DB
    assert score.changed_inside_frac > 0.9
    assert preservation_verdict(score) == "pass"


def test_bleeding_edit_fails_and_shows_near_the_mask(pair):
    before, mask = pair
    after = before.copy()
    after[40:80, 45:115] = 255  # 10-15 px past the mask
    score = edit_preservation(before, after, mask)
    assert score.changed_near_mask_frac > score.changed_outside_frac > 0
    assert preservation_verdict(score) == "changed_outside_mask"


def test_global_colour_shift_fails(pair):
    before, mask = pair
    after = np.clip(before.astype(int) + 20, 0, 255).astype(np.uint8)
    score = edit_preservation(before, after, mask)
    assert score.changed_outside_frac > 0.8
    assert preservation_verdict(score) == "changed_outside_mask"


def test_no_op_and_resized_outputs_are_flagged(pair):
    before, mask = pair
    assert preservation_verdict(edit_preservation(before, before, mask)) == "no_edit_inside_mask"
    score = edit_preservation(before, before[:100], mask)
    assert not score.size_match and score.changed_outside_frac is None
    assert preservation_verdict(score) == "size_mismatch"


def test_small_noise_stays_under_the_threshold(pair):
    before, mask = pair
    after = before.copy()
    after[mask] = 0
    after[~mask] = np.clip(before[~mask].astype(int) + 3, 0, 255)  # below the 8-level threshold
    assert preservation_verdict(edit_preservation(before, after, mask)) == "pass"


def test_mask_iou():
    a = np.zeros((10, 10), dtype=bool)
    a[:, :5] = True
    b = np.zeros((10, 10), dtype=bool)
    b[:, 2:7] = True
    assert mask_iou(a, a) == 1.0
    assert mask_iou(a, b) == pytest.approx(30 / 70)
    assert mask_iou(a, ~a) == 0.0
    assert mask_iou(a.astype(np.uint8) * 255, a) == 1.0  # uint8 alpha and bool masks mix


def test_synthetic_scene_has_exact_masks():
    scene = build_scene(1)
    assert scene.kind == "bike" and scene.image.size == (960, 640)
    for mask in (scene.subject_mask, scene.plate_mask, scene.watermark_mask):
        assert mask.shape == (640, 960) and 0 < mask.mean() < 0.5
    assert scene.plate_mask[scene.subject_mask].any()  # the plate sits on the vehicle
