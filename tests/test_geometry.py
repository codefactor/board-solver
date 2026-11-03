"""Pure geometry helper tests. Driven by the synthetic fixture in conftest.py
(NOT the committed project files, which change over time).

Synthetic panel P: seq [M, A, B, A, D] with trailing D maxProfile 1,
profiles L:10, R:10, thickness 3/4". Panel R: sliceStrips 2 x 1/4".
"""

from __future__ import annotations

import pytest

from boardsolver.geometry import (
    inches_to_measure,
    measure_to_inches,
    measure_to_sixteenths,
    resolve_slice,
    sixteenths_to_measure,
    slice_length,
)


# --------------------------------------------------------------------------- #
# measurement <-> sixteenths <-> inches
# --------------------------------------------------------------------------- #

def test_measure_to_inches_examples():
    assert measure_to_inches([47, 12]) == 47.75
    assert measure_to_inches([0, 2]) == 0.125


def test_inches_to_measure_rounds_to_nearest_sixteenth():
    assert inches_to_measure(47.75) == (47, 12)
    assert inches_to_measure(0.125) == (0, 2)
    # round-half-up at a sixteenth boundary
    assert inches_to_measure(1 / 32) == (0, 1)


@pytest.mark.parametrize("sixteenths", list(range(0, 16 * 4 + 1)))
def test_roundtrip_sixteenths(sixteenths):
    m = sixteenths_to_measure(sixteenths)
    assert measure_to_sixteenths(m) == sixteenths
    # and via inches
    assert inches_to_measure(measure_to_inches(m)) == m


# --------------------------------------------------------------------------- #
# resolve_slice: maxProfile filtering + height rules
# --------------------------------------------------------------------------- #

def test_resolve_slice_P_L_has_all_components(project):
    r = resolve_slice(project, "P-L")
    assert r.panel_id == "P"
    assert r.profile_id == "L"
    assert len(r.components) == 5  # index 0 includes trailing D (maxProfile 1 > 0)
    assert r.components[-1].id == "D"
    assert r.height == measure_to_sixteenths([0, 12])  # panel P thickness


def test_resolve_slice_P_R_drops_trailing_d(project):
    r = resolve_slice(project, "P-R")
    assert len(r.components) == 4  # index 1: maxProfile 1 > 1 is false -> D dropped
    assert r.components[-1].id == "A"
    assert all(c.id != "D" for c in r.components)
    assert r.height == measure_to_sixteenths([0, 12])


def test_resolve_slice_R_L_height_is_slicestrips_width(project):
    r = resolve_slice(project, "R-L")
    # panel R has sliceStrips {count:2, width:[0,4]} -> height is the ripped strip width
    assert r.height == measure_to_sixteenths([0, 4])
    assert r.height != measure_to_sixteenths([0, 13])  # NOT the panel thickness


def test_resolve_slice_single_profile_panel(project):
    r = resolve_slice(project, "Q")  # single-profile: bare id is valid
    assert r.profile_id is None
    assert [c.id for c in r.components] == ["M", "X", "X"]


def test_resolve_slice_requires_profile_for_profiled_panel(project):
    with pytest.raises(KeyError):
        resolve_slice(project, "P")  # P has profiles; bare id is ambiguous


# --------------------------------------------------------------------------- #
# slice_length
# --------------------------------------------------------------------------- #

def test_slice_length_examples(project):
    # P-R = M(3/4) + A(3/4) + B(1 1/2) + A(3/4) = 3 3/4" (D dropped)
    pr = slice_length(resolve_slice(project, "P-R"))
    assert pr == measure_to_sixteenths([3, 12])
    # P-L adds the trailing D (1/4") -> 4"
    pl = slice_length(resolve_slice(project, "P-L"))
    assert pl == measure_to_sixteenths([4, 0])
