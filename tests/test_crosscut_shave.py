"""Crosscut shave vs true overflow, synthetic only.

A crosscut resulting in a non-positive offcut whose absolute value
is less than one kerf is a shave, not an overflow: the trim cut
shaves the end of the board and leaves no separate offcut, so
leftover is shown as 0 with a warning, not negative. An over-cut of
at least one kerf is a true overflow and stays negative.
"""

from boardsolver.derive import crosscut_blanks


def _blanks(raw_length, blank_length):
    project = {"boards": [{"id": "B1", "species": "Cherry",
                           "length": raw_length, "width": [7, 0],
                           "thickness": [0, 13]}]}
    cut_spec = {"boards": [{"id": "X", "source": "B1",
                            "length": blank_length, "strips": []}]}
    tool_limits = {"sawKerf": [0, 2], "miterKerf": [0, 2],
                   "maxCutLength": [49, 8], "maxPlaneWidth": [12, 8],
                   "minPlaneLength": [12, 0]}
    return crosscut_blanks(project, cut_spec, tool_limits)


def test_shave_margin_less_than_kerf():
    cb = _blanks([48, 1], [48, 0])[0]
    assert cb.raw_margin == 1
    assert cb.resulting_offcut == -1
    assert cb.shave is True
    assert cb.leftover == 0


def test_shave_kerf_exact_trim():
    # 48 1/8 in board cut to 48 in: trim is exactly one kerf, so the
    # resulting offcut is 0, within one kerf of zero.
    cb = _blanks([48, 2], [48, 0])[0]
    assert cb.raw_margin == 2
    assert cb.resulting_offcut == 0
    assert cb.shave is True
    assert cb.leftover == 0


def test_shave_small_negative_overcut():
    # Blank 1/16 in longer than the board: resulting offcut -1/16 in,
    # non-positive with absolute value less than one kerf.
    cb = _blanks([48, 0], [48, 1])[0]
    assert cb.raw_margin == -1
    assert cb.resulting_offcut == -1
    assert cb.shave is True
    assert cb.leftover == 0


def test_shave_margin_zero_multi_blank():
    project = {"boards": [{"id": "B1", "species": "Cherry",
                           "length": [40, 0], "width": [7, 0],
                           "thickness": [0, 13]}]}
    cut_spec = {"boards": [
        {"id": "X", "source": "B1", "length": [20, 0], "strips": []},
        {"id": "Y", "source": "B1", "length": [19, 14], "strips": []},
    ]}
    tool_limits = {"sawKerf": [0, 2], "miterKerf": [0, 2]}
    cb = crosscut_blanks(project, cut_spec, tool_limits)[0]
    # 20 in + 19 7/8 in + 1/8 in kerf = 40 in exactly.
    assert cb.raw_margin == 0
    assert cb.shave is True
    assert cb.leftover == 0


def test_non_last_crosscut_overflow_is_not_shave():
    # First blank already exceeds the board by 1/16 in, and a second
    # blank still follows: the final over-cut is 1 3/16 in, at least
    # one kerf, so this is an overflow error, not a shave — a small
    # negative on a non-last cut does not become a shave.
    project = {"boards": [{"id": "B1", "species": "Cherry",
                           "length": [40, 0], "width": [7, 0],
                           "thickness": [0, 13]}]}
    cut_spec = {"boards": [
        {"id": "X", "source": "B1", "length": [40, 1], "strips": []},
        {"id": "Y", "source": "B1", "length": [1, 0], "strips": []},
    ]}
    tool_limits = {"sawKerf": [0, 2], "miterKerf": [0, 2]}
    cb = crosscut_blanks(project, cut_spec, tool_limits)[0]
    assert cb.shave is False
    assert cb.leftover < -2


def test_true_overflow_stays_negative():
    cb = _blanks([48, 1], [49, 0])[0]
    assert cb.raw_margin == -15
    assert cb.shave is False
    assert cb.leftover == -15


def test_normal_margin_leaves_offcut():
    cb = _blanks([48, 1], [40, 0])[0]
    assert cb.raw_margin == 129
    assert cb.shave is False
    assert cb.leftover == 127
