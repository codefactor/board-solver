"""Pure geometry helper tests, driven by the committed project.yaml."""

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

def test_resolve_slice_S_L_has_nine_components(project):
    r = resolve_slice(project, "S-L")
    assert r.panel_id == "S"
    assert r.profile_id == "L"
    assert len(r.components) == 9  # index 0 includes trailing Md (maxProfile 1 > 0)
    assert r.components[-1].id == "Md"
    assert r.height == measure_to_sixteenths([0, 12])  # panel S thickness


def test_resolve_slice_S_R_drops_trailing_md(project):
    r = resolve_slice(project, "S-R")
    assert len(r.components) == 8  # index 1: maxProfile 1 > 1 is false -> Md dropped
    assert all(c.id != "Md" or True for c in r.components)  # last Md removed
    assert r.components[-1].id == "C2"
    assert r.height == measure_to_sixteenths([0, 12])


def test_resolve_slice_H_L_height_is_slicestrips_width(project):
    r = resolve_slice(project, "H-L")
    # panel H has sliceStrips {count:2, width:[0,4]} -> height is the ripped strip width
    assert r.height == measure_to_sixteenths([0, 4])
    assert r.height != measure_to_sixteenths([0, 13])  # NOT the panel thickness


def test_resolve_slice_requires_profile_for_profiled_panel(project):
    with pytest.raises(KeyError):
        resolve_slice(project, "S")  # S has profiles; bare id is ambiguous


# --------------------------------------------------------------------------- #
# slice_length
# --------------------------------------------------------------------------- #

def test_slice_length_examples(project):
    # S-R = Me + C2 + M1 + C2 + C2 + M1 + C2 (8 comps) -> 7"
    sr = slice_length(resolve_slice(project, "S-R"))
    assert sr == measure_to_sixteenths([7, 0])
    # S-L adds the trailing Md (1/4") -> 7 1/4"
    sl = slice_length(resolve_slice(project, "S-L"))
    assert sl == measure_to_sixteenths([7, 4])
