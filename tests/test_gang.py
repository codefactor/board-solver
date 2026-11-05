"""Synthetic tests for the planer gang check.

Only synthetic projects / cut-specs defined here (plus the synthetic
conftest fixtures, never production specs), so they stay decoupled
from committed project specs.

Gang rule: a strip wider than its thickness must be ganged, taped
together, so the gang's total thickness reaches the strip width.
Strip gang first; if it is too small, crosscut to components first,
then gang the components; if that gang is still too small, it is a
warning for that width (yellow planer_gang_too_small warning, not
an error — sacrificial wood can make up the gang).
"""

from boardsolver.derive import gang_groups, warnings


def _project(board_defs):
    # board_defs: list of (id, species, thickness_pair)
    return {
        "boards": [
            {"id": bid, "species": sp, "length": [48, 0],
             "width": [8, 0], "thickness": thick}
            for bid, sp, thick in board_defs
        ],
    }


def _cut_spec(board_defs):
    # board_defs: list of (board_id, source_id, [(width_pair, [cut_pairs])])
    boards = []
    for bid, source, strips in board_defs:
        boards.append({
            "id": bid, "source": source, "length": [48, 0],
            "strips": [{"width": w, "cuts": cuts} for w, cuts in strips],
        })
    return {"boards": boards}


def _gang(width, thickness, strip_count, cuts_per_strip):
    proj = _project([("S1", "TestWood", thickness)])
    cut = _cut_spec([("B1", "S1", [
        (width, [[16, 0]] * cuts_per_strip) for _ in range(strip_count)
    ])])
    groups = gang_groups(proj, cut, {"limits": {}})
    assert len(groups) == 1
    return groups[0]


def test_width_at_or_below_thickness_needs_no_gang():
    # 3/4 in wide, 13/16 in thick: width < thickness.
    g = _gang([0, 12], [0, 13], 1, 1)
    assert g.requires_gang is False
    assert g.crosscut_first is False
    assert g.insufficient is False


def test_width_above_thickness_with_enough_strips_needs_no_crosscut_first():
    # 1 1/2 in wide, 13/16 in thick, 2 strips: total 1 5/8 in >= 1 1/2 in.
    g = _gang([1, 8], [0, 13], 2, 1)
    assert g.requires_gang is True
    assert g.strip_sufficient is True
    assert g.crosscut_first is False
    assert g.insufficient is False
    assert g.required_count == 2


def test_crosscut_first_when_strip_gang_too_small_but_component_gang_enough():
    # 3 in wide, 13/16 in thick, 1 strip cut into 4 components:
    # strip total 13/16 in < 3 in, component total 3 1/4 in >= 3 in.
    g = _gang([3, 0], [0, 13], 1, 4)
    assert g.requires_gang is True
    assert g.strip_sufficient is False
    assert g.component_sufficient is True
    assert g.crosscut_first is True
    assert g.insufficient is False
    assert g.required_count == 4


def test_insufficient_even_after_crosscut():
    # 3 in wide, 13/16 in thick, 1 strip cut into 2 components:
    # strip total 13/16 in, component total 1 5/8 in, both < 3 in.
    g = _gang([3, 0], [0, 13], 1, 2)
    assert g.requires_gang is True
    assert g.strip_sufficient is False
    assert g.component_sufficient is False
    assert g.crosscut_first is True
    assert g.insufficient is True
    assert g.strip_count == 1
    assert g.component_count == 2
    assert g.required_count == 4


def test_gang_groups_sorted_widest_first():
    proj = _project([("S1", "TestWood", [0, 13])])
    cut = _cut_spec([("B1", "S1", [
        ([0, 12], [[16, 0]]),
        ([3, 0], [[16, 0]]),
        ([1, 8], [[16, 0]]),
    ])])
    widths = [g.width for g in gang_groups(proj, cut, {"limits": {}})]
    assert widths == sorted(widths, reverse=True)


def test_warnings_include_planer_gang_too_small(project, cut_spec, tool_limits):
    # Conftest synthetic cut-spec has 3 in walnut strips, 2 strips,
    # 2 components, thickness 13/16 in: both gangs below 3 in.
    # (It also has a 1 1/2 in cherry strip, 1 strip / 1 component,
    # which is likewise insufficient, so do not assert a total count.)
    found = [w for w in warnings(project, cut_spec, tool_limits)
             if w.code == "planer_gang_too_small" and "3″" in w.message]
    assert len(found) == 1
    assert found[0].level == "yellow"
    assert "sacrificial wood" in found[0].message
