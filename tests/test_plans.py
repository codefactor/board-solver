"""Plan tests: design / inventory / cut-spec split, derived panels,
cut-spec selection by name, plans/<design>/<inventory>/<cut-spec>/
construction, and new-pile flow with no hand tweaking.

DECOUPLING RULE (2026-11-03, Scott): these tests must NOT read the
committed specs/ or plans/ in the repo root. Root specs and plans are
constantly moving — a design change (cells, thickness, batch) must
never break a test. Tests move only when the code moves.

Every design, inventory, and cut-spec used here is synthetic and
defined in this file, written into a tmp_path repo by _temp_root().
The only shared fixture is tool_limits from conftest.py, which is
itself synthetic and does not load any committed file.
"""

from __future__ import annotations

import os

import pytest
import yaml
from PIL import Image

from boardsolver import bundle, deliver
from boardsolver.derive import (
    actual_panels,
    auto_panels,
    board_rips,
    match_supply_to_demand,
    slice_fulfillment,
)
from boardsolver.docwriter import write_document

# --- synthetic bundle ------------------------------------------------------
#
# Design "synth": two panel types, A and B, each 3 in wide (four 3/4 in
# components), 3/4 in thick, 5 declared slices. Grid places A, B, A, B
# (batch 1), so installed demand is 2 slices per type, +1 spare = 3,
# floored at the declared 5 -> 1 panel of each type, 5 slices each.
# Panel length (for sticks) = 5 slices x 1 5/8 in pitch + 1 1/2 in snipe
# = 9 5/8 in. Each panel slice uses 2 walnut + 2 maple components, so
# total component demand is 20 sticks per species.

DESIGN = {
    "name": "Synth",
    "description": "Synthetic test design, defined in test_plans.py only.",
    "batch": 1,
    "finishedThickness": [1, 4],
    "sliceDepth": [1, 8],
    "sliceGrid": [
        [{"sliceId": "A"}],
        [{"sliceId": "B"}],
        [{"sliceId": "A"}],
        [{"sliceId": "B"}],
    ],
    "components": [
        {"id": "W", "species": "Walnut", "width": [0, 12], "thickness": [0, 12]},
        {"id": "M", "species": "Brown Maple", "width": [0, 12], "thickness": [0, 12]},
    ],
    "panels": [
        {
            "id": "A",
            "thickness": [0, 12],
            "slices": 5,
            "components": [
                {"type": "W"}, {"type": "M"}, {"type": "W"}, {"type": "M"},
            ],
        },
        {
            "id": "B",
            "thickness": [0, 12],
            "slices": 5,
            "components": [
                {"type": "M"}, {"type": "W"}, {"type": "M"}, {"type": "W"},
            ],
        },
    ],
}

# Hand cut-spec for synth/main: 5 strips per species, 4 sticks each
# (4 x 9 5/8 in from a 48 in strip), totalling the 20 sticks demanded.
HAND_CUT_SPEC = {
    "design": "synth",
    "inventory": "main",
    "kind": "hand",
    "date": "2026-01-01",
    "boards": [
        {
            "id": "W1A", "source": "W1", "length": [48, 0],
            "strips": [
                {"width": [0, 12], "cuts": [[9, 10]] * 4} for _ in range(5)
            ],
        },
        {
            "id": "M1A", "source": "M1", "length": [48, 0],
            "strips": [
                {"width": [0, 12], "cuts": [[9, 10]] * 4} for _ in range(5)
            ],
        },
    ],
}

INVENTORIES = {
    # 6 in boards: hand cut-spec margins are 1 5/16 in per board.
    "main": [
        {"id": "W1", "species": "Walnut", "length": [48, 0], "width": [6, 0], "thickness": [0, 13]},
        {"id": "M1", "species": "Brown Maple", "length": [48, 0], "width": [6, 0], "thickness": [0, 13]},
    ],
    # Same design, wider boards: margins differ, so cut lists differ.
    "wide": [
        {"id": "W1", "species": "Walnut", "length": [48, 0], "width": [8, 0], "thickness": [0, 13]},
        {"id": "M1", "species": "Brown Maple", "length": [48, 0], "width": [8, 0], "thickness": [0, 13]},
    ],
    # A brand-new pile, different board ids, no hand cut-spec.
    "newpile": [
        {"id": "W9", "species": "Walnut", "length": [48, 0], "width": [8, 0], "thickness": [0, 13]},
        {"id": "M9", "species": "Brown Maple", "length": [48, 0], "width": [8, 0], "thickness": [0, 13]},
    ],
}


def _write_yaml(path, doc):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        yaml.safe_dump(doc, f, sort_keys=False)


def _temp_root(tmp_path, tool_limits, inventories=("main", "wide", "newpile"),
               hand=True):
    """A throwaway repo root carrying only the synthetic bundle."""
    root = tmp_path / "repo"
    _write_yaml(str(root / "specs" / "tool-limits.yaml"), tool_limits)
    _write_yaml(str(root / "specs" / "designs" / "synth.yaml"), DESIGN)
    for name in inventories:
        _write_yaml(
            str(root / "specs" / "inventories" / name / "boards.yaml"),
            {"boards": INVENTORIES[name]})
    if hand:
        _write_yaml(
            str(root / "specs" / "inventories" / "main" / "cut-specs"
                / "synth.hand.yaml"),
            HAND_CUT_SPEC)
    return str(root)


def _project(tool_limits):
    return bundle.resolve_bundle(
        DESIGN, {"boards": INVENTORIES["main"]}, tool_limits)


# --- derived panels --------------------------------------------------------


def test_derived_panel_specs_from_grid(tool_limits):
    """Panel count/length follow grid demand, spare, and declared floor."""
    assert "boards" not in DESIGN
    assert "panelSpecs" not in DESIGN
    assert bundle.derive_panel_specs(DESIGN, tool_limits) == [
        {"panel": "A", "profileLengths": [[8, 2]], "count": 1},
        {"panel": "B", "profileLengths": [[8, 2]], "count": 1},
    ]


def test_design_has_no_boards_and_inventory_has_no_pattern(tmp_path, tool_limits):
    root = _temp_root(tmp_path, tool_limits)
    design = bundle.load_design(bundle.find_design(root, "synth"))
    assert "sliceGrid" in design and "components" in design
    assert "boards" not in design
    inv = bundle.load_inventory(bundle.find_inventory_boards(root, "main"))
    assert "sliceGrid" not in inv and "components" not in inv


# --- bundle resolution / inventory reuse -----------------------------------


def test_same_inventory_usable_by_two_designs_without_copying(tool_limits):
    """One inventory file feeds two designs; neither design copies it."""
    inv = {"boards": INVENTORIES["main"]}
    other = dict(DESIGN)
    other["panels"] = [
        dict(p, components=list(reversed(p["components"])))
        for p in DESIGN["panels"]
    ]
    a = bundle.resolve_bundle(DESIGN, inv, tool_limits)
    b = bundle.resolve_bundle(other, inv, tool_limits)
    assert a["boards"] == inv["boards"] == b["boards"]
    assert a["panelSpecs"] == b["panelSpecs"]  # same demand, same shape
    # A genuinely different grid does change the derived panels.
    bigger = dict(DESIGN)
    bigger["sliceGrid"] = DESIGN["sliceGrid"] * 3
    c = bundle.resolve_bundle(bigger, inv, tool_limits)
    assert c["panelSpecs"] != a["panelSpecs"]


# --- cut-spec selection and nesting ----------------------------------------


def test_cut_spec_selection_by_name(tmp_path, tool_limits):
    """Hand vs solver cut-specs for the same design+inventory are
    selected by name, not by overwriting each other."""
    root = _temp_root(tmp_path, tool_limits)
    hand_proj, hand, hand_variant, hand_path = deliver.resolve_run(
        root, "synth", "main", "hand", tool_limits)
    # A "solver" lookup loads an existing solver file, so solve+save
    # it first (the old test only passed because the root repo
    # happened to carry a solver file — exactly the coupling removed).
    deliver.resolve_run(root, "synth", "main", None, tool_limits)
    solver_proj, solver, solver_variant, _ = deliver.resolve_run(
        root, "synth", "main", "solver", tool_limits, save_cut_spec=False)
    assert hand_variant == "hand" and solver_variant == "solver"
    assert hand["kind"] == "hand" and solver["kind"] == "solver"
    assert hand_proj["panelSpecs"] == solver_proj["panelSpecs"]
    assert hand_path == os.path.join(
        root, "specs", "inventories", "main", "cut-specs", "synth.hand.yaml")


def test_cut_spec_for_wrong_design_is_refused(tmp_path, tool_limits):
    """A cut-spec whose metadata names another design is not rendered."""
    with pytest.raises(ValueError, match="design"):
        bundle.check_cut_spec_matches(
            {"design": "synth", "inventory": "main"}, "other", "main")
    root = _temp_root(tmp_path, tool_limits)
    with pytest.raises((FileNotFoundError, ValueError)):
        deliver.resolve_run(root, "synth", "main",
                            "other.hand", tool_limits)


def test_cut_spec_from_wrong_inventory_is_refused(tmp_path, tool_limits):
    """A cut-spec is only looked up inside its own inventory's folder."""
    root = _temp_root(tmp_path, tool_limits)
    with pytest.raises(FileNotFoundError):
        deliver.resolve_run(root, "synth", "wide", "hand", tool_limits)
    with pytest.raises(ValueError, match="inventory"):
        bundle.check_cut_spec_matches(
            {"design": "synth", "inventory": "main"}, "synth", "wide")


def test_solver_never_overwrites_a_hand_cut_spec_file(tmp_path, tool_limits):
    """A solver run leaves the hand cut-spec file untouched."""
    root = _temp_root(tmp_path, tool_limits)
    path = os.path.join(root, "specs", "inventories", "main",
                        "cut-specs", "synth.hand.yaml")
    before = open(path).read()
    deliver.resolve_run(root, "synth", "main", None, tool_limits,
                        save_cut_spec=False)
    assert open(path).read() == before


def test_deliver_creates_no_old_structure(tmp_path, tool_limits):
    """Deliver creates plans/<design>/<inventory>/<cut-spec>/ only —
    never specs/projects, specs/solutions, specs/runs, or plans/runs."""
    root = _temp_root(tmp_path, tool_limits)
    rc = deliver.main(["synth", "--inventory", "main",
                       "--cut-spec", "hand", "--what", "plan",
                       "--root", root])
    assert rc == 0
    for old in ("specs/projects", "specs/solutions", "specs/runs",
                "plans/runs"):
        assert not os.path.exists(os.path.join(root, old))


# --- determinism (replaces pre-refactor golden fixtures) -------------------
#
# The old tests compared plans/math byte-for-byte against fixtures
# captured from the committed plaid/chess designs. That coupled tests
# to production specs: any design change broke them. These tests check
# the same properties — determinism and sensitivity — on the synthetic
# design, so they move only when the code moves.


def _plan_md_and_math(tool_limits, tmp_path):
    project = _project(tool_limits)
    root = _temp_root(tmp_path, tool_limits)
    _, cut_spec, _, _ = deliver.resolve_run(
        root, "synth", "main", "hand", tool_limits)
    out = tmp_path / "plan"
    res = write_document(project, tool_limits, cut_spec, str(out),
                         folder_name="plan")
    md = open(res.markdown_path).read()
    rips = [dict(r.__dict__) if hasattr(r, "__dict__") else str(r)
            for r in board_rips(project, cut_spec, tool_limits)]
    return md, rips


def test_plan_and_math_are_deterministic(tmp_path, tool_limits):
    """Same synthetic bundle twice -> same plan text, same rip math."""
    md1, rips1 = _plan_md_and_math(tool_limits, tmp_path / "a")
    md2, rips2 = _plan_md_and_math(tool_limits, tmp_path / "b")
    assert md1 == md2
    assert rips1 == rips2


def test_plan_and_math_change_when_the_design_changes(tmp_path, tool_limits):
    """Widening a component changes the rip math — the code is not
    just echoing a fixture."""
    md1, rips1 = _plan_md_and_math(tool_limits, tmp_path / "a")
    wide_design = dict(DESIGN)
    wide_design["components"] = [
        dict(c, width=[1, 0]) if c["id"] == "W" else c
        for c in DESIGN["components"]
    ]
    wide_design["panels"] = [
        dict(p, components=[
            dict(comp, type="W") if comp["type"] == "W" else comp
            for comp in p["components"]
        ]) for p in DESIGN["panels"]
    ]
    # Component widths live in the components list; panels reference
    # them by type, so widening W alone changes the panel widths.
    project = bundle.resolve_bundle(
        wide_design, {"boards": INVENTORIES["main"]}, tool_limits)
    root = _temp_root(tmp_path / "c", tool_limits)
    _, cut_spec, _, _ = deliver.resolve_run(
        root, "synth", "main", "hand", tool_limits)
    out = tmp_path / "wide-plan"
    res = write_document(project, tool_limits, cut_spec, str(out),
                         folder_name="plan")
    md2 = open(res.markdown_path).read()
    assert md2 != md1


# --- plans/ construction ----------------------------------------------------


def test_plan_directory_is_programmatic(tmp_path, tool_limits):
    """With no --out, deliver builds plans/<design>/<inventory>/<cut-spec>/
    from its three arguments alone."""
    root = _temp_root(tmp_path, tool_limits)
    rc = deliver.main(["synth", "--inventory", "main",
                       "--cut-spec", "hand", "--what", "plan",
                       "--root", root])
    assert rc == 0
    plan_dir = os.path.join(root, "plans", "synth", "main", "hand")
    assert os.path.isfile(os.path.join(plan_dir, "README.md"))
    assert os.path.isdir(os.path.join(plan_dir, "images"))
    assert not os.path.exists(os.path.join(plan_dir, "plan"))


def test_plan_folder_shape_all_outputs(tmp_path, tool_limits):
    """--what all puts README, images and the PDF side by side in the
    plan folder, with no nested plan/ folder."""
    root = _temp_root(tmp_path, tool_limits)
    rc = deliver.main(["synth", "--inventory", "main",
                       "--cut-spec", "hand", "--what", "all",
                       "--root", root])
    assert rc == 0
    plan_dir = os.path.join(root, "plans", "synth", "main", "hand")
    assert os.path.isfile(os.path.join(plan_dir, "README.md"))
    assert os.path.isfile(os.path.join(plan_dir, "synth-main-hand-cut-plan.pdf"))
    assert os.path.isdir(os.path.join(plan_dir, "images"))
    assert not os.path.exists(os.path.join(plan_dir, "plan"))


# --- two inventories, two cut lists ----------------------------------------


def test_two_inventories_two_different_cut_lists(tmp_path, tool_limits):
    """Same design, two inventories -> two different, correct cut
    lists, each in its own plan folder."""
    root = _temp_root(tmp_path, tool_limits)
    actual = deliver.resolve_run(root, "synth", "main", "hand", tool_limits)
    hyp_proj, hyp_cut, _hyp_variant, _ = deliver.resolve_run(
        root, "synth", "wide", None, tool_limits, save_cut_spec=False)
    assert hyp_cut["boards"] != actual[1]["boards"]
    rows, _unused, _wasted = match_supply_to_demand(
        hyp_proj, hyp_cut, tool_limits)
    assert all(r.shortfall == 0 for r in rows)
    assert all(r.shortfall == 0
               for r in slice_fulfillment(hyp_proj, hyp_cut, tool_limits))
    out_actual = deliver.deliver(actual[0], actual[1], tool_limits,
                                 str(tmp_path / "actual"), "cut-list",
                                 "synth-main-hand")
    out_hyp = deliver.deliver(hyp_proj, hyp_cut, tool_limits,
                              str(tmp_path / "hyp"), "cut-list",
                              "synth-wide-solver")
    assert open(out_actual["cut-list"]).read() != open(out_hyp["cut-list"]).read()


# --- brand-new pile, no hand editing ---------------------------------------


def test_brand_new_pile_flows_through_solver_untouched(tmp_path, tool_limits):
    """A new pile + the synthetic pattern -> a valid cut list, no hand
    editing, no ghost boards needed, no shortfalls."""
    root = _temp_root(tmp_path, tool_limits)
    project, cut_spec, _variant, _path = deliver.resolve_run(
        root, "synth", "newpile", None, tool_limits, save_cut_spec=False)
    assert not any("buySpecies" in b for b in cut_spec["boards"])
    assert all(b.get("source") in ("W9", "M9") for b in cut_spec["boards"])
    rows, _unused, _wasted = match_supply_to_demand(
        project, cut_spec, tool_limits)
    assert all(r.shortfall == 0 for r in rows)
    assert all(r.shortfall == 0
               for r in slice_fulfillment(project, cut_spec, tool_limits))
    for rip in board_rips(project, cut_spec, tool_limits):
        assert rip.margin >= 0


def test_deliver_single_outputs_are_self_contained(tmp_path, tool_limits):
    """A cut-list file must not reference a diagram it does not ship;
    strip-map and finished outputs are real PNGs."""
    root = _temp_root(tmp_path, tool_limits)
    project, cut_spec, _, _ = deliver.resolve_run(
        root, "synth", "main", "hand", tool_limits)
    out = deliver.deliver(project, cut_spec, tool_limits,
                          str(tmp_path), "cut-list", "synth-main-hand")
    text = open(out["cut-list"]).read()
    assert "![" not in text
    out2 = deliver.deliver(project, cut_spec, tool_limits,
                           str(tmp_path / "diagrams"), "strip-map",
                           "synth-main-hand")
    with Image.open(out2["strip-map"]) as im:
        assert im.size[0] > 0 and im.size[1] > 0


# --- shared rip shape, different thickness ----------------------------------
#
# Two components may share a species and width and differ only by thickness
# (the chess CB/CTH case: a 1 1/8 in cherry strip becomes a 2 1/4 in-tall
# border piece in a full-height row or a 1 1/8 in-tall one in a border row).
# Supply is pooled by rip shape and allocated across both demand rows; the
# old id-keyed matcher assigned every shared-shape piece to one component
# and reported the other short. This test is synthetic — it must not read
# the committed chess design.

DUP_DESIGN = {
    "name": "Dup",
    "description": "Synthetic duplicate-shape design, defined in test_plans.py only.",
    "batch": 1,
    "finishedThickness": [1, 4],
    "sliceDepth": [1, 8],
    "sliceGrid": [
        [{"sliceId": "A"}],
        [{"sliceId": "B"}],
    ],
    "components": [
        {"id": "X", "species": "Cherry", "width": [1, 2], "thickness": [2, 4]},
        {"id": "Y", "species": "Cherry", "width": [1, 2], "thickness": [1, 2]},
        {"id": "W", "species": "Walnut", "width": [2, 4], "thickness": [2, 4]},
    ],
    "panels": [
        {"id": "A", "thickness": [2, 4], "slices": 5,
         "components": [{"type": "X"}, {"type": "W"}]},
        {"id": "B", "thickness": [1, 2], "slices": 5,
         "components": [{"type": "Y"}, {"type": "W"}]},
    ],
}

DUP_CUT_SPEC = {
    "design": "dup",
    "inventory": "dup",
    "kind": "hand",
    "date": "2026-01-01",
    "boards": [
        {"id": "C1A", "source": "C1", "length": [48, 0],
         "strips": [{"width": [1, 2], "cuts": [[9, 10]] * 2}]},
        {"id": "W1A", "source": "W1", "length": [48, 0],
         "strips": [{"width": [2, 4], "cuts": [[9, 10]] * 2}]},
    ],
}

DUP_INVENTORY = [
    {"id": "C1", "species": "Cherry", "length": [48, 0], "width": [6, 0], "thickness": [0, 13]},
    {"id": "W1", "species": "Walnut", "length": [48, 0], "width": [6, 0], "thickness": [0, 13]},
]


def test_shared_shape_supply_splits_across_components(tool_limits):
    """Two cherry 1 1/8 in pieces satisfy one X demand and one Y demand —
    neither is short and none is left unused."""
    project = bundle.resolve_bundle(
        DUP_DESIGN, {"boards": DUP_INVENTORY}, tool_limits)
    rows, unused, wasted = match_supply_to_demand(
        project, DUP_CUT_SPEC, tool_limits)
    by_id = {r.component_id: r for r in rows}
    assert by_id["X"].fulfilled == 1 and by_id["X"].shortfall == 0
    assert by_id["Y"].fulfilled == 1 and by_id["Y"].shortfall == 0
    assert by_id["W"].fulfilled == 2 and by_id["W"].shortfall == 0
    assert unused == [] and wasted == []
    # Auto-panels form both panels from the shared pool, and authored
    # panel codes resolve each piece to the component its position needs.
    codes = auto_panels(project, DUP_CUT_SPEC, tool_limits)
    assert sorted(c.split(":")[0] for c in codes) == ["A", "B"]
    authored = dict(DUP_CUT_SPEC, panels=[
        "A:C1A/0/0;W1A/0/0", "B:C1A/0/1;W1A/0/1"])
    panels = actual_panels(project, authored, tool_limits)
    assert [p.panel_id for p in panels] == ["A", "B"]
    assert all(p.sequence_ok for p in panels)
    assert [p.component_id for p in panels[0].pieces] == ["X", "W"]
    assert [p.component_id for p in panels[1].pieces] == ["Y", "W"]
