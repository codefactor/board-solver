"""Synthetic tests for crosscut leftover: actual free piece, not plan figure.

The plan was wrong: it counted kerfs only between blanks, so its
leftover was 1/8 in too long and its crosscut diagram summed to raw
length + 1 kerf. The checklist was already right: it subtracted the
final kerf that separates the leftover from the last blank. This
test pins the plan calculation to the checklist calculation.

Only synthetic boards defined here, never production specs.
"""

from boardsolver.derive import crosscut_blanks


def _run(raw, blank_lengths):
    project = {"boards": [{
        "id": "S1", "species": "TestWood",
        "length": [raw // 16, raw % 16],
        "width": [8, 0], "thickness": [0, 13],
    }]}
    cut_spec = {"boards": [{
        "id": f"B{i + 1}", "source": "S1",
        "length": [bl // 16, bl % 16], "strips": [],
    } for i, bl in enumerate(blank_lengths)]}
    tools = {"limits": {"miterKerf": [0, 2]}}
    out = crosscut_blanks(project, cut_spec, tools)
    assert len(out) == 1
    return out[0]


def test_two_blanks_leftover_counts_final_kerf():
    # Raw 98 1/16 in, blanks 47 7/8 in + 35 5/8 in.
    # Old plan figure: 14 7/16 in. Actual free piece: 14 5/16 in.
    cb = _run(98 * 16 + 1, [47 * 16 + 14, 35 * 16 + 10])
    assert cb.leftover == 14 * 16 + 5


def test_single_trimmed_blank_leftover_counts_final_kerf():
    # Raw 48 1/16 in, blank 47 7/8 in. Old: 3/16 in. Actual: 1/16 in.
    cb = _run(48 * 16 + 1, [47 * 16 + 14])
    assert cb.leftover == 1


def test_exact_fit_leftover_stays_zero():
    cb = _run(48 * 16, [48 * 16])
    assert cb.leftover == 0
    assert cb.state == "whole"


def test_overflow_leftover_not_made_larger():
    # Blanks already exceed raw: negative leftover is the overflow
    # amount, not overflow plus a final kerf for a piece that isn't there.
    cb = _run(48 * 16, [30 * 16, 30 * 16])
    assert cb.leftover == 48 * 16 - 60 * 16 - 2
