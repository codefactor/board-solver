"""Synthetic tests for the zero-offcut warning.

Only synthetic projects / cut-specs defined here, never production
specs, so they stay decoupled from committed project specs.

A strip whose pieces plus kerfs exactly fill its board leaves a
0 in offcut: no margin for cutting error in the crosscut phase.
"""

from boardsolver.derive import zero_offcut_boards


def _project():
    return {
        "boards": [
            {"id": "S1", "species": "TestWood", "length": [48, 0],
             "width": [8, 0], "thickness": [0, 13]},
        ],
    }


def _cut_spec(board_length, strips):
    return {
        "boards": [{
            "id": "B1", "source": "S1", "length": board_length,
            "strips": [{"width": w, "cuts": cuts} for w, cuts in strips],
        }],
    }


def _limits():
    return {"limits": {
        "sawKerf": [0, 2], "miterKerf": [0, 2], "minPlaneLoss": [0, 1],
    }}


def test_exact_fit_strip_is_flagged():
    # 47 7/8 in board, 3 pieces at 15 7/8 in + 2 kerfs = exactly 47 7/8 in.
    cut = _cut_spec([47, 14], [([1, 8], [[15, 14]] * 3)])
    assert zero_offcut_boards(_project(), cut, _limits()) == [("B1", 1)]


def test_strip_with_tail_is_not_flagged():
    # Same board, 2 pieces: 16 in of tail remains.
    cut = _cut_spec([47, 14], [([1, 8], [[15, 14]] * 2)])
    assert zero_offcut_boards(_project(), cut, _limits()) == []


def test_counts_are_per_board():
    # One exact-fit strip, one with tail: only the exact one counts.
    cut = _cut_spec([47, 14], [
        ([1, 8], [[15, 14]] * 3),
        ([0, 12], [[15, 14]] * 2),
    ])
    assert zero_offcut_boards(_project(), cut, _limits()) == [("B1", 1)]
