"""Regenerate every plan in plans/ from the current code.

Usage (via ./run.sh regenerate-all, see that script)::

    ./run.sh regenerate-all

One combination per design + inventory + cut-spec file found under
``specs/inventories/<inventory>/cut-specs/<design>.<variant>.yaml``.
Each combination is regenerated with ``deliver --what all`` into its
normal directory, ``plans/<design>/<inventory>/<variant>/``, so a
stale plan never survives a code change: generated plans are
overwritten on rerun (see repo AGENTS.md), and an old plan is
recovered from git, not kept beside the current one.

Plaid-v2 is the one exception to plain ``deliver``: the design file
carries no panelSpecs, and the derived panelSpecs (S x3, long panels)
do not match the v2 cut-specs, which build S x5, ML x3, MR x3, H x1
at 15 7/8 in (H 17 3/4 in). The override below is the same one the
hand-plan and plan-checklist generators have always used for v2;
without it a plain regenerate would change the v2 layout, not just
its rendering. No other design gets an override.

If a combination already has a ``plan-checklist/`` directory, that
checklist is regenerated too (Md + PDF, via ``cutcheck``), with the
same v2 override where it applies. Combinations without one do not
gain one: a checklist is only regenerated, never invented here.
"""

from __future__ import annotations

import os
from typing import Dict, List, Tuple

import yaml

from . import cutcheck
from .deliver import deliver, resolve_run

# plaid-v2 panels, in the old panelSpecs shape: panel, count,
# profileLengths as [whole_inches, sixteenths] pairs. S is a
# 2-profile panel (L + R), ML/MR are single-profile, H is 2-profile.
PLAID_V2_PANEL_SPECS = [
    {"panel": "S", "count": 5, "profileLengths": [[7, 3], [7, 3]]},
    {"panel": "ML", "count": 3, "profileLengths": [[14, 6]]},
    {"panel": "MR", "count": 3, "profileLengths": [[14, 6]]},
    {"panel": "H", "count": 1, "profileLengths": [[8, 2], [8, 2]]},
]


def discover_combos(root: str) -> List[Tuple[str, str, str]]:
    """All (design, inventory, variant) tuples with a cut-spec file.

    Sorted for a stable, repeatable run order. A cut-spec file is
    named ``<design>.<variant>.yaml``; anything else in the folder
    is ignored.
    """
    combos: List[Tuple[str, str, str]] = []
    inv_root = os.path.join(root, "specs", "inventories")
    if not os.path.isdir(inv_root):
        return combos
    for inventory in sorted(os.listdir(inv_root)):
        cut_dir = os.path.join(inv_root, inventory, "cut-specs")
        if not os.path.isdir(cut_dir):
            continue
        for name in sorted(os.listdir(cut_dir)):
            if not name.endswith(".yaml"):
                continue
            stem = name[:-5]
            if "." not in stem:
                continue
            design, variant = stem.split(".", 1)
            combos.append((design, inventory, variant))
    return sorted(combos)


def apply_panel_specs_override(
    project: Dict, design: str
) -> Dict:
    """Apply the plaid-v2 panelSpecs override, or leave it alone."""
    if design == "plaid-v2":
        project = dict(project)
        project["panelSpecs"] = PLAID_V2_PANEL_SPECS
    return project


def _load_tool_limits(root: str) -> Dict:
    with open(os.path.join(root, "specs", "tool-limits.yaml")) as f:
        return yaml.safe_load(f)


def regenerate_all(root: str) -> List[Tuple[str, str, str]]:
    """Regenerate every discovered plan. Returns the combos done."""
    tool_limits = _load_tool_limits(root)
    done: List[Tuple[str, str, str]] = []
    for design, inventory, variant in discover_combos(root):
        project, cut_spec, _v, _path = resolve_run(
            root, design, inventory, variant, tool_limits)
        project = apply_panel_specs_override(project, design)
        out_dir = os.path.join(root, "plans", design, inventory, variant)
        run_name = f"{design}-{inventory}-{variant}"
        deliver(project, cut_spec, tool_limits, out_dir, "all", run_name)
        print(f"wrote plan: {out_dir}")
        checklist_dir = os.path.join(out_dir, "plan-checklist")
        if os.path.isdir(checklist_dir):
            md_path = cutcheck.build_md(
                project, cut_spec, tool_limits, checklist_dir,
                design, inventory, variant)
            pdf_path = os.path.join(checklist_dir, "plan-checklist.pdf")
            data = cutcheck.build_data(project, cut_spec, tool_limits)
            cutcheck.build_pdf_from_md(
                md_path, pdf_path,
                phase1_bars=cutcheck._phase1_bars(data))
            print(f"wrote checklist: {checklist_dir}")
        done.append((design, inventory, variant))
    return done


def main(argv=None) -> int:
    root = os.getcwd()
    done = regenerate_all(root)
    print(f"regenerated {len(done)} plan(s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
