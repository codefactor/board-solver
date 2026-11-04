"""Finishing face size derivation.

Synthetic only (tests must stay decoupled from production specs):
the finished size is the declared target when present; otherwise
it is derived from per-edge trims, which are independent and may
be unequal — no edge is assumed, and no equal split is assumed.
Without either, the old fallback applies (width trimmed by the
flattening allowance, length untrimmed).
"""
from boardsolver.cutcheck import _edge_trim, _finishing_size


def test_declared_finished_size_is_the_target():
    project = {"finishedWidth": [14, 0], "finishedLength": [16, 0]}
    # Grid 14 1/4 x 16, sliceDepth 1 1/2, finishedThickness 1 1/4.
    assert _finishing_size(project, 228, 256, 24, 20) == (224, 256)


def test_edge_trims_derive_size_and_may_be_unequal():
    project = {"edgeTrims": {"left": [0, 3], "right": [0, 1], "top": [0, 8]}}
    assert _finishing_size(project, 228, 256, 24, 20) == (224, 248)
    assert _edge_trim(project, "left") == 3
    assert _edge_trim(project, "right") == 1
    assert _edge_trim(project, "bottom") == 0


def test_undeclared_falls_back_to_old_derivation():
    project = {}
    assert _finishing_size(project, 228, 256, 24, 20) == (224, 256)
