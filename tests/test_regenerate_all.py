"""Synthetic tests for regenerate-all discovery and the v2 override.

These tests use only tmp_path fixtures, never production spec files:
the discovery rule is "a cut-spec file named <design>.<variant>.yaml
under specs/inventories/<inventory>/cut-specs/", and the override
applies to plaid-v2 alone.
"""

from boardsolver.regenerate_all import (
    PLAID_V2_PANEL_SPECS,
    apply_panel_specs_override,
    discover_combos,
)


def _cut_spec(tmp_path, inventory, stem):
    d = tmp_path / "specs" / "inventories" / inventory / "cut-specs"
    d.mkdir(parents=True, exist_ok=True)
    (d / f"{stem}.yaml").write_text("design: x\n")


def test_discover_combos_sorted_and_ignores_non_cut_specs(tmp_path):
    _cut_spec(tmp_path, "actual", "plaid-v1.solver")
    _cut_spec(tmp_path, "actual", "chess-v1.hand")
    _cut_spec(tmp_path, "hypothetical", "plaid-v1.solver")
    (tmp_path / "specs" / "inventories" / "actual" / "cut-specs" / "notes.txt").write_text("x")
    (tmp_path / "specs" / "inventories" / "actual" / "cut-specs" / "no-variant.yaml").write_text("x")
    assert discover_combos(str(tmp_path)) == [
        ("chess-v1", "actual", "hand"),
        ("plaid-v1", "actual", "solver"),
        ("plaid-v1", "hypothetical", "solver"),
    ]


def test_discover_combos_empty_without_inventories(tmp_path):
    assert discover_combos(str(tmp_path)) == []


def test_v2_override_only_for_plaid_v2():
    project = {"panelSpecs": [{"panel": "X", "count": 1}]}
    v2 = apply_panel_specs_override(project, "plaid-v2")
    assert v2["panelSpecs"] == PLAID_V2_PANEL_SPECS
    # The input project is not mutated.
    assert project["panelSpecs"] == [{"panel": "X", "count": 1}]
    assert apply_panel_specs_override(project, "plaid-v1") is project
    assert apply_panel_specs_override(project, "chess-v1") is project
