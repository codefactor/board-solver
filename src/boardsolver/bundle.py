"""Design / inventory / solution bundles: the new, split format.

The old format packs everything into one project.yaml: the pattern, the
boards in hand, and the chosen physical panels (panelSpecs). That single
slot means a new pile of boards, or a new cut list, overwrites the old
one, and the same pattern cannot be reused with a different inventory
without copying boards into it.

A bundle splits the three things, and names a run by all three:

* design -- pattern only: name, description, batch, finishedThickness,
  sliceDepth, sliceGrid, components, panels. No boards, no panelSpecs.
* inventory -- a reusable board list, referenced by name. The same
  inventory file is usable by more than one design, with no copying.
* solution -- a cut-spec (boards + strips + cuts) plus metadata naming
  its design, its inventory, its kind (``hand`` or ``solver``) and its
  date. A hand solution and a solver solution for the same design and
  inventory are different files and never overwrite each other.

``resolve_bundle`` turns a design + inventory back into the old
project shape the rest of the code already understands: it attaches
the inventory boards and a *derived* set of panelSpecs (see
:func:`derive_panel_specs`), so solver, document-writer, PDF and all
their math run unchanged on a bundle. The old project.yaml path is
untouched: a project that already carries its own panelSpecs keeps
using them.

Derived panel specs
-------------------
Panel count and length are computed, not hand-written, from the grid
demand, the slice pitch, the snipe tail, and the batch, with one spare
slice per profile:

* installed demand per slice id = grid placements per board x batch;
* pre-rip demand per profile = installed demand / rip multiplier
  (sliceStrips count, else 1), rounded up;
* needed per profile = pre-rip demand + 1 spare, floored at the
  panel's declared slice count for that profile (a design may
  deliberately over-produce a panel type, as chess-v1's border
  panel C does: demand 4 + spare = 5, declared 9, built at 9);
* a panel must let at least two sticks fit in one crosscut blank
  (maxCutLength): its total slice count is capped at the largest
  count whose length (slices x pitch + snipe) still leaves room for
  two sticks in a blank, i.e. 2 x length + miterKerf <= maxCutLength;
* panel count = ceil(total needed slices / cap), and each profile's
  slices per panel = ceil(needed per profile / count).

That rule reproduces the existing panelSpecs exactly for both
committed designs: plaid-v1 (S/M: 2 panels x 11 slices; H: 1 panel
x 5 + 5) and chess-v1 (1 panel x 9 slices each), and it needs no
hand tweaking for a new pile of boards -- the panel plan follows
the demand, not the inventory.
"""

from __future__ import annotations

import math
import os
from collections import Counter
from typing import Any, Dict, List, Optional, Tuple

import yaml

from .geometry import measure_to_sixteenths, sixteenths_to_measure


def _lim(tool_limits: Dict[str, Any]) -> Dict[str, Any]:
    return tool_limits["limits"] if "limits" in tool_limits else tool_limits


def _load(path: str) -> Dict[str, Any]:
    with open(path) as f:
        return yaml.safe_load(f)


def load_design(path: str) -> Dict[str, Any]:
    design = _load(path)
    if "boards" in design:
        raise ValueError(f"design {path} must not carry boards (use an inventory)")
    if "panelSpecs" in design:
        raise ValueError(
            f"design {path} must not carry panelSpecs (panels are derived)")
    return design


def load_inventory(path: str) -> Dict[str, Any]:
    inv = _load(path)
    if "boards" not in inv:
        raise ValueError(f"inventory {path} has no boards list")
    return inv


def derive_panel_specs(
    design: Dict[str, Any], tool_limits: Dict[str, Any], spare: int = 1,
) -> List[Dict[str, Any]]:
    """Compute panelSpecs for a design, in the old panelSpecs shape.

    Returns one entry per panel type, in the design's panel order, each
    with ``panel``, ``profileLengths`` (measurement pairs) and ``count``.
    Panel types that appear nowhere in the sliceGrid are skipped: they
    demand nothing, so building them would only waste wood.
    """
    lim = _lim(tool_limits)
    pitch = measure_to_sixteenths(design["sliceDepth"]) + measure_to_sixteenths(
        lim["miterKerf"])
    snipe = measure_to_sixteenths(lim.get("snipeTail", [0, 0]))
    miter_kerf = measure_to_sixteenths(lim["miterKerf"])
    batch = design.get("batch", 1)

    # Installed demand per slice id, from the grid.
    per_board: Counter = Counter()
    for row in design.get("sliceGrid", []):
        for cell in row:
            per_board[cell["sliceId"]] += 1

    panels_by_id = {p["id"]: p for p in design["panels"]}
    # Largest total slice count whose panel still fits two sticks in a
    # maxCutLength blank: 2 * (n * pitch + snipe) + miterKerf <= maxCut.
    max_cut = measure_to_sixteenths(lim["maxCutLength"]) if lim.get("maxCutLength") else None
    if max_cut:
        cap = max(1, (max_cut - miter_kerf - 2 * snipe) // (2 * pitch))
    else:
        cap = 1 << 30

    specs: List[Dict[str, Any]] = []
    for panel in design["panels"]:
        pid = panel["id"]
        rip = panel.get("sliceStrips", {}).get("count", 1) if panel.get("sliceStrips") else 1
        if "profiles" in panel:
            prof_ids = [p["id"] for p in panel["profiles"]]
            ideal = [p["slices"] for p in panel["profiles"]]
        else:
            prof_ids = [None]
            ideal = [panel["slices"]]
        needed = []
        for prof_id, ideal_n in zip(prof_ids, ideal):
            sid = f"{pid}-{prof_id}" if prof_id else pid
            installed = per_board.get(sid, 0) * batch
            if installed == 0:
                needed.append(0)
                continue
            pre_rip = -(-installed // rip)  # ceil division
            needed.append(max(ideal_n, pre_rip + spare))
        if all(n == 0 for n in needed):
            continue
        total_needed = sum(needed)
        count = max(1, -(-total_needed // cap))
        per_panel = [-(-n // count) if n else 0 for n in needed]
        profile_lengths = [
            list(sixteenths_to_measure(n * pitch)) for n in per_panel
        ]
        specs.append({
            "panel": pid,
            "profileLengths": profile_lengths,
            "count": count,
        })
    return specs


def resolve_bundle(
    design: Dict[str, Any], inventory: Dict[str, Any],
    tool_limits: Dict[str, Any],
) -> Dict[str, Any]:
    """Design + inventory -> the project dict the solver/docwriter expect.

    The returned dict is a fresh copy: design fields, the inventory's
    boards, and derived panelSpecs. It validates as a project (boards
    present, panelSpecs in the old shape) even though neither input
    file carries the other's data.
    """
    project = {k: v for k, v in design.items()}
    project["boards"] = inventory["boards"]
    project["panelSpecs"] = derive_panel_specs(design, tool_limits)
    return project


def solution_metadata(solution: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "design": solution.get("design"),
        "inventory": solution.get("inventory"),
        "kind": solution.get("kind"),
        "date": solution.get("date"),
    }


def check_solution_matches(
    solution: Dict[str, Any], design_name: str, inventory_name: str,
) -> None:
    """Refuse to render a solution against the wrong design/inventory.

    A solution without metadata (the old hand/solved cut-spec shape)
    is accepted as-is: it predates metadata and its caller already
    knows which project it belongs to.
    """
    if solution.get("design") is None and solution.get("inventory") is None:
        return
    if solution.get("design") not in (None, design_name):
        raise ValueError(
            f"solution is for design {solution.get('design')!r}, "
            f"not {design_name!r}")
    if solution.get("inventory") not in (None, inventory_name):
        raise ValueError(
            f"solution is for inventory {solution.get('inventory')!r}, "
            f"not {inventory_name!r}")


def bundle_name(design_name: str, inventory_name: str, solution_name: str) -> str:
    return f"{design_name}.{inventory_name}.{solution_name}"


def find_file(root: str, kind: str, name: str) -> str:
    """Locate a design/inventory/solution file by name, or raise clearly."""
    candidates = [
        os.path.join(root, "specs", kind, f"{name}.yaml"),
        os.path.join(root, "specs", kind, name),
    ]
    for path in candidates:
        if os.path.exists(path):
            return path
    raise FileNotFoundError(
        f"no {kind} named {name!r} under specs/{kind}/")
