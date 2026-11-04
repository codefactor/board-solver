"""Synthetic tests for the solver's sourceRemainder child-split pass.

These use only synthetic _Blank objects, never production designs or
inventories, so they stay decoupled from committed project specs.

The pattern mirrors the chess cherry case in miniature form, with
synthetic dimensions that happen to share the same arithmetic:
a parent blank whose strips, top-down, are 100% utilized, then
33% utilized, then 83% utilized, with a later strip narrower than
the underutilized strip, plus a single-piece donor blank.
"""

from boardsolver.solver import (
    _Blank,
    _child_split_score,
    _try_child_split,
)

LOSS = 3  # sawKerf 2 + minPlaneLoss 1, in sixteenths
KERF = 2  # miterKerf, in sixteenths


def _blank(bid, width, length, strips, source="SRC"):
    blank = _Blank(bid, "TestWood", width, length, source=source)
    blank.strips = strips
    return blank


def _cherry_like_blanks():
    # Widths/lengths in sixteenths: 2.25" = 36, 1.125" = 18,
    # 12.875" = 206, 16.125" = 258, 7.25" = 116, 6.9375" = 111.
    parent = _blank("P1A", 116, 768, [
        {"width": 36, "cuts": [206, 206, 206]},
        {"width": 36, "cuts": [206]},
        {"width": 18, "cuts": [258, 258]},
    ])
    donor = _blank("P2A", 111, 768, [
        {"width": 18, "cuts": [206]},
    ])
    return [parent, donor]


def test_child_split_produces_two_children_and_drops_donor():
    blanks = _cherry_like_blanks()
    result = _try_child_split(blanks, LOSS, KERF)
    assert result is not None
    ids = [b.id for b in result]
    assert "P2A" not in ids
    assert "P1A1" in ids and "P1A2" in ids
    parent = next(b for b in result if b.id == "P1A")
    # Only the highly utilized top strip stays on the parent.
    assert parent.strips == [{"width": 36, "cuts": [206, 206, 206]}]
    child1 = next(b for b in result if b.id == "P1A1")
    child2 = next(b for b in result if b.id == "P1A2")
    # Children are in trigger order: bad strip's length group first.
    assert child1.source_remainder == "P1A" and child1.length == 206
    assert child2.source_remainder == "P1A" and child2.length == 258
    # Every original stick is still present, exactly once.
    sticks = []
    for b in result:
        for strip in b.strips:
            for cut in strip["cuts"]:
                sticks.append((strip["width"], cut))
    assert sorted(sticks) == sorted([
        (36, 206), (36, 206), (36, 206), (36, 206),
        (18, 258), (18, 258), (18, 206),
    ])
    # Score improves: raw blank count drops and waste+loss drops.
    assert _child_split_score(result, LOSS, KERF) < \
        _child_split_score(blanks, LOSS, KERF)


def test_child_split_does_not_fire_without_a_trigger():
    # All strips highly utilized: no far underutilized strip, so no split.
    blanks = [_blank("P1A", 116, 768, [
        {"width": 36, "cuts": [206, 206, 206]},
        {"width": 36, "cuts": [206, 206, 206]},
    ])]
    assert _try_child_split(blanks, LOSS, KERF) is None


def test_child_split_rejects_a_single_length_group():
    # Removed pool groups into only one length: one child would be
    # pointless relabelling, so the pass must not fire.
    blanks = [_blank("P1A", 116, 768, [
        {"width": 36, "cuts": [206, 206, 206]},
        {"width": 36, "cuts": [206]},
        {"width": 18, "cuts": [206]},
    ])]
    assert _try_child_split(blanks, LOSS, KERF) is None
