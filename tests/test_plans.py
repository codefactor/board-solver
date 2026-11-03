"""Plan tests: design / inventory / cut-spec split, derived panels,
cut-spec selection by name, plans/<design>/<inventory>/<cut-spec>/
construction, and new-pile flow with no hand tweaking.

A cut-spec lives only inside its inventory's cut-specs/ folder: it is
meaningful only in the context of that inventory. Pre-refactor
equivalence is checked against tests/fixtures/, captured from the old
project.yaml plans before the old structure was deleted: plan Markdown
text, image filenames (content hashes), and derived math must match
exactly.
"""

from __future__ import annotations

import json
import os
import shutil

import pytest
import yaml
from PIL import Image

from boardsolver import bundle, deliver
from boardsolver.derive import (
    board_rips,
    match_supply_to_demand,
    slice_fulfillment,
)
from boardsolver.docwriter import write_document

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
FIXTURES = os.path.join(os.path.dirname(__file__), "fixtures")

TUPLES = [
    ("plaid-v1", "actual", "hand"),
    ("plaid-v1", "actual", "solver"),
    ("chess-v1", "actual", "solver"),
    ("plaid-v1", "hypothetical", "solver"),
    ("chess-v1", "hypothetical", "solver"),
]


def _load(path):
    with open(path) as f:
        return yaml.safe_load(f)


@pytest.fixture
def tool_limits():
    return _load(os.path.join(ROOT, "specs", "tool-limits.yaml"))


def _fixture(name):
    with open(os.path.join(FIXTURES, "equivalence.json")) as f:
        return json.load(f)[name]


def _ser(obj):
    if hasattr(obj, "_asdict"):
        return obj._asdict()
    if hasattr(obj, "__dict__"):
        return dict(obj.__dict__)
    return str(obj)


# --- derived panels --------------------------------------------------------


@pytest.mark.parametrize("name", ["plaid-v1", "chess-v1"])
def test_derived_panel_specs_match_fixture(name, tool_limits):
    """Derived panels equal the pre-refactor panelSpecs, exactly."""
    design = bundle.load_design(bundle.find_design(ROOT, name))
    assert "boards" not in design
    assert "panelSpecs" not in design
    assert bundle.derive_panel_specs(design, tool_limits) == \
        _fixture(name)["panelSpecs"]


# --- bundle resolution / inventory reuse -----------------------------------


def test_same_inventory_usable_by_both_designs_without_copying(tool_limits):
    """One inventory file feeds plaid and chess; neither design copies it."""
    inv = bundle.load_inventory(bundle.find_inventory_boards(ROOT, "actual"))
    projects = {}
    for name in ("plaid-v1", "chess-v1"):
        design = bundle.load_design(bundle.find_design(ROOT, name))
        project = bundle.resolve_bundle(design, inv, tool_limits)
        assert project["boards"] == inv["boards"]
        projects[name] = project
    assert projects["plaid-v1"]["panelSpecs"] != projects["chess-v1"]["panelSpecs"]


def test_design_has_no_boards_and_inventory_has_no_pattern(tool_limits):
    design = bundle.load_design(bundle.find_design(ROOT, "plaid-v1"))
    assert "sliceGrid" in design and "components" in design
    inv = bundle.load_inventory(bundle.find_inventory_boards(ROOT, "actual"))
    assert "sliceGrid" not in inv and "components" not in inv


# --- cut-spec selection and nesting ----------------------------------------


def test_cut_spec_selection_by_name(tool_limits):
    """Hand vs solver cut-specs for the same design+inventory differ
    and are selected by name, not by overwriting each other."""
    hand_proj, hand, hand_variant, hand_path = deliver.resolve_run(
        ROOT, "plaid-v1", "actual", "hand", tool_limits)
    solver_proj, solver, solver_variant, _ = deliver.resolve_run(
        ROOT, "plaid-v1", "actual", "solver", tool_limits,
        save_cut_spec=False)
    assert hand_variant == "hand" and solver_variant == "solver"
    assert hand["kind"] == "hand" and solver["kind"] == "solver"
    assert hand["boards"] != solver["boards"]
    assert hand_proj["panelSpecs"] == solver_proj["panelSpecs"]
    assert hand_path == os.path.join(
        ROOT, "specs", "inventories", "actual", "cut-specs",
        "plaid-v1.hand.yaml")


def test_cut_spec_for_wrong_design_is_refused(tool_limits):
    """A cut-spec whose metadata names another design is not rendered."""
    with pytest.raises(ValueError, match="design"):
        bundle.check_cut_spec_matches(
            {"design": "plaid-v1", "inventory": "actual"},
            "chess-v1", "actual")
    # And a cut-spec looked up under the wrong design is not found there.
    with pytest.raises((FileNotFoundError, ValueError)):
        deliver.resolve_run(ROOT, "chess-v1", "actual",
                            "plaid-v1.hand", tool_limits)


def test_cut_spec_from_wrong_inventory_is_refused(tool_limits):
    """A cut-spec is only looked up inside its own inventory's folder."""
    with pytest.raises(FileNotFoundError):
        deliver.resolve_run(ROOT, "plaid-v1", "hypothetical",
                            "hand", tool_limits)
    with pytest.raises(ValueError, match="inventory"):
        bundle.check_cut_spec_matches(
            {"design": "plaid-v1", "inventory": "actual"},
            "plaid-v1", "hypothetical")


def test_solver_never_overwrites_a_hand_cut_spec_file(tool_limits):
    """A solver run leaves the committed hand cut-spec untouched."""
    path = os.path.join(ROOT, "specs", "inventories", "actual",
                        "cut-specs", "plaid-v1.hand.yaml")
    before = open(path).read()
    deliver.resolve_run(ROOT, "plaid-v1", "actual", None, tool_limits,
                        save_cut_spec=False)
    assert open(path).read() == before


# --- no duplicates, no old structure ---------------------------------------


def test_no_duplicate_yaml_and_no_old_structure():
    """Each design, inventory board list, and cut-spec exists once;
    the old project and run structure is gone."""
    assert not os.path.exists(os.path.join(ROOT, "specs", "projects"))
    assert not os.path.exists(os.path.join(ROOT, "specs", "solutions"))
    assert not os.path.exists(os.path.join(ROOT, "specs", "runs"))
    assert not os.path.exists(os.path.join(ROOT, "plans", "runs"))
    designs = sorted(os.listdir(os.path.join(ROOT, "specs", "designs")))
    assert designs == ["chess-v1.yaml", "plaid-v1.yaml"]
    for inv in ("actual", "hypothetical"):
        inv_dir = os.path.join(ROOT, "specs", "inventories", inv)
        assert os.path.isfile(os.path.join(inv_dir, "boards.yaml"))
        assert not os.path.isfile(os.path.join(
            ROOT, "specs", "inventories", f"{inv}.yaml"))
    # Every cut-spec exists in exactly one place: its inventory's
    # cut-specs/ folder. The same stem in a different inventory is a
    # different cut-spec, so identity is (inventory, stem), not stem.
    pairs = []
    for inv in ("actual", "hypothetical"):
        cut_dir = os.path.join(ROOT, "specs", "inventories", inv, "cut-specs")
        for f in sorted(os.listdir(cut_dir)):
            pairs.append((inv, f))
    assert len(pairs) == len(set(pairs))
    assert sorted(pairs) == [
        ("actual", "chess-v1.solver.yaml"),
        ("actual", "plaid-v1.hand.yaml"),
        ("actual", "plaid-v1.solver.yaml"),
        ("hypothetical", "chess-v1.solver.yaml"),
        ("hypothetical", "plaid-v1.solver.yaml"),
    ]


# --- pre-refactor equivalence ----------------------------------------------


def _plan_md_and_images(project, cut_spec, tool_limits, tmp_path):
    res = write_document(project, tool_limits, cut_spec, str(tmp_path),
                         folder_name="plan")
    md = open(res.markdown_path).read()
    images = {}
    for fname in sorted(os.listdir(os.path.join(res.folder, "images"))):
        with Image.open(os.path.join(res.folder, "images", fname)) as im:
            images[fname.split("-")[0]] = (im.size, im.tobytes())
    return md, images


@pytest.mark.parametrize("name", ["plaid-v1", "chess-v1"])
def test_new_plan_matches_pre_refactor_plan(name, tool_limits, tmp_path):
    """Plan Markdown and diagram filenames match the pre-refactor
    fixture exactly (filenames are content hashes, so equal names
    mean equal diagrams)."""
    fixture_md = open(os.path.join(FIXTURES, f"{name}-plan.md")).read()
    design = bundle.load_design(bundle.find_design(ROOT, name))
    inv = bundle.load_inventory(bundle.find_inventory_boards(ROOT, "actual"))
    project = bundle.resolve_bundle(design, inv, tool_limits)
    kind = "hand" if name == "plaid-v1" else "solver"
    _, cut_spec, _, _ = deliver.resolve_run(
        ROOT, name, "actual", kind, tool_limits)
    md, _images = _plan_md_and_images(project, cut_spec, tool_limits, tmp_path)
    assert md == fixture_md


@pytest.mark.parametrize("name", ["plaid-v1", "chess-v1"])
def test_new_math_matches_pre_refactor_math(name, tool_limits):
    """Margins, slice fulfilment and component fulfilment are unchanged
    from the pre-refactor fixture (same numbers, not just pictures)."""
    fixture = _fixture(name)
    design = bundle.load_design(bundle.find_design(ROOT, name))
    inv = bundle.load_inventory(bundle.find_inventory_boards(ROOT, "actual"))
    project = bundle.resolve_bundle(design, inv, tool_limits)
    kind = "hand" if name == "plaid-v1" else "solver"
    _, cut_spec, _, _ = deliver.resolve_run(
        ROOT, name, "actual", kind, tool_limits)
    assert [_ser(r) for r in board_rips(project, cut_spec, tool_limits)] == \
        fixture["board_rips"]
    assert [_ser(r) for r in slice_fulfillment(project, cut_spec, tool_limits)] == \
        fixture["slice_fulfillment"]
    rows, _unused, _wasted = match_supply_to_demand(
        project, cut_spec, tool_limits)
    assert [_ser(r) for r in rows] == fixture["supply"]


# --- plans/ construction ----------------------------------------------------


def _temp_root(tmp_path):
    root = tmp_path / "repo"
    root.mkdir()
    shutil.copytree(os.path.join(ROOT, "specs"), root / "specs")
    return str(root)


def test_plan_directory_is_programmatic(tmp_path):
    """With no --out, deliver builds plans/<design>/<inventory>/<cut-spec>/
    from its three arguments alone."""
    root = _temp_root(tmp_path)
    rc = deliver.main(["plaid-v1", "--inventory", "actual",
                       "--cut-spec", "hand", "--what", "plan",
                       "--root", root])
    assert rc == 0
    plan_dir = os.path.join(root, "plans", "plaid-v1", "actual", "hand")
    assert os.path.isfile(os.path.join(plan_dir, "README.md"))
    assert os.path.isdir(os.path.join(plan_dir, "images"))
    assert not os.path.exists(os.path.join(plan_dir, "plan"))


def test_plan_folder_shape_all_outputs(tmp_path):
    """--what all puts README, images and the PDF side by side in the
    plan folder, with no nested plan/ folder."""
    root = _temp_root(tmp_path)
    rc = deliver.main(["chess-v1", "--inventory", "actual",
                       "--cut-spec", "solver", "--what", "all",
                       "--root", root])
    assert rc == 0
    plan_dir = os.path.join(root, "plans", "chess-v1", "actual", "solver")
    assert os.path.isfile(os.path.join(plan_dir, "README.md"))
    assert os.path.isfile(os.path.join(
        plan_dir, "chess-v1-actual-solver-cut-plan.pdf"))
    assert os.path.isdir(os.path.join(plan_dir, "images"))
    assert not os.path.exists(os.path.join(plan_dir, "plan"))


@pytest.mark.parametrize("design,inventory,variant", TUPLES)
def test_committed_plans_exist(design, inventory, variant):
    """Every tuple in the approved set has a committed plan folder."""
    plan_dir = os.path.join(ROOT, "plans", design, inventory, variant)
    assert os.path.isfile(os.path.join(plan_dir, "README.md"))
    assert os.path.isdir(os.path.join(plan_dir, "images"))


# --- two inventories, two cut lists ----------------------------------------


def test_two_inventories_two_different_cut_lists(tool_limits, tmp_path):
    """Same design, two inventories -> two different, correct cut
    lists, each in its own plan folder."""
    actual = deliver.resolve_run(ROOT, "plaid-v1", "actual", "hand", tool_limits)
    hyp_proj, hyp_cut, hyp_variant, _ = deliver.resolve_run(
        ROOT, "plaid-v1", "hypothetical", None, tool_limits,
        save_cut_spec=False)
    assert hyp_cut["boards"] != actual[1]["boards"]
    rows, _unused, _wasted = match_supply_to_demand(hyp_proj, hyp_cut, tool_limits)
    assert all(r.shortfall == 0 for r in rows)
    assert all(r.shortfall == 0 for r in slice_fulfillment(hyp_proj, hyp_cut, tool_limits))
    out_actual = deliver.deliver(actual[0], actual[1], tool_limits,
                                 str(tmp_path / "actual"), "cut-list",
                                 "plaid-v1-actual-hand")
    out_hyp = deliver.deliver(hyp_proj, hyp_cut, tool_limits,
                              str(tmp_path / "hyp"), "cut-list",
                              "plaid-v1-hypothetical-solver")
    assert open(out_actual["cut-list"]).read() != open(out_hyp["cut-list"]).read()


# --- brand-new pile, no hand editing ---------------------------------------


def test_brand_new_pile_flows_through_solver_untouched(tool_limits):
    """A hypothetical pile + the chess pattern -> a valid cut list,
    no hand editing, no ghost boards needed, no shortfalls."""
    project, cut_spec, _variant, _path = deliver.resolve_run(
        ROOT, "chess-v1", "hypothetical", None, tool_limits,
        save_cut_spec=False)
    assert not any("buySpecies" in b for b in cut_spec["boards"])
    assert all(b.get("source") in ("BC1", "BC2", "BW1", "BW2", "BM1", "BM2")
               for b in cut_spec["boards"])
    rows, _unused, _wasted = match_supply_to_demand(project, cut_spec, tool_limits)
    assert all(r.shortfall == 0 for r in rows)
    assert all(r.shortfall == 0
               for r in slice_fulfillment(project, cut_spec, tool_limits))
    for rip in board_rips(project, cut_spec, tool_limits):
        assert rip.margin >= 0


def test_deliver_single_outputs_are_self_contained(tool_limits, tmp_path):
    """A cut-list file must not reference a diagram it does not ship;
    strip-map and finished outputs are real PNGs."""
    project, cut_spec, _, _ = deliver.resolve_run(
        ROOT, "plaid-v1", "actual", "hand", tool_limits)
    out = deliver.deliver(project, cut_spec, tool_limits,
                          str(tmp_path), "cut-list", "plaid-v1-actual-hand")
    text = open(out["cut-list"]).read()
    assert "![" not in text
    out2 = deliver.deliver(project, cut_spec, tool_limits,
                           str(tmp_path / "diagrams"), "strip-map",
                           "plaid-v1-actual-hand")
    with Image.open(out2["strip-map"]) as im:
        assert im.size[0] > 0 and im.size[1] > 0
