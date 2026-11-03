"""Design / inventory / cut-spec bundles: the new, split format.

The format splits what used to be packed into one file: the pattern, the
boards in hand, and the chosen physical panels (panelSpecs). A new pile
of boards, or a new cut list, gets its own named file, and the same
pattern can be reused with a different inventory without copying boards
into it.

A bundle splits the three things, and names a run by all three:

* design -- pattern only: name, description, batch, finishedThickness,
  sliceDepth, sliceGrid, components, panels. No boards, no panelSpecs.
* inventory -- a reusable board list, referenced by name. The same
  inventory file is usable by more than one design, with no copying.
* cut-spec -- a cut-spec (boards + strips + cuts) plus metadata naming
  its design, its inventory, its kind (``hand`` or ``solver``) and its
  date. A hand cut-spec and a solver cut-spec for the same design and
  inventory are different files and never overwrite each other.

``resolve_bundle`` turns a design + inventory into the project shape
the rest of the code already understands: it attaches the inventory
boards and a *derived* set of panelSpecs (see :func:`derive_panel_specs`),
so solver, document-writer, PDF and all their math run on a bundle.

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


def cut_spec_metadata(cut_spec: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "design": cut_spec.get("design"),
        "inventory": cut_spec.get("inventory"),
        "kind": cut_spec.get("kind"),
        "date": cut_spec.get("date"),
    }


def check_cut_spec_matches(
    cut_spec: Dict[str, Any], design_name: str, inventory_name: str,
) -> None:
    """Refuse to render a cut-spec against the wrong design/inventory.

    A cut-spec without metadata is accepted as-is: it predates
    metadata and its caller already knows which design and inventory
    it belongs to. A cut-spec whose metadata names another design, or
    another inventory than the folder it was found in, is refused.
    """
    if cut_spec.get("design") is None and cut_spec.get("inventory") is None:
        return
    if cut_spec.get("design") not in (None, design_name):
        raise ValueError(
            f"cut-spec is for design {cut_spec.get('design')!r}, "
            f"not {design_name!r}")
    if cut_spec.get("inventory") not in (None, inventory_name):
        raise ValueError(
            f"cut-spec is for inventory {cut_spec.get('inventory')!r}, "
            f"not {inventory_name!r}")


def cut_spec_stem(design_name: str, variant: str) -> str:
    """File stem of a cut-spec inside an inventory: <design>.<variant>."""
    return f"{design_name}.{variant}"


def find_design(root: str, name: str) -> str:
    """Locate a design file by name, or raise clearly."""
    path = os.path.join(root, "specs", "designs", f"{name}.yaml")
    if os.path.exists(path):
        return path
    raise FileNotFoundError(f"no design named {name!r} under specs/designs/")


def find_inventory_boards(root: str, name: str) -> str:
    """Locate an inventory's boards file by name, or raise clearly."""
    path = os.path.join(root, "specs", "inventories", name, "boards.yaml")
    if os.path.exists(path):
        return path
    raise FileNotFoundError(
        f"no inventory named {name!r} under specs/inventories/")


def find_cut_spec(root: str, inventory_name: str, design_name: str,
                  variant: str) -> str:
    """Locate a cut-spec inside its inventory's folder only.

    A cut-spec is only meaningful in the context of the inventory it
    was cut from, so the lookup never searches another inventory's
    folder: pairing a cut-spec with a different inventory is refused
    here, with a clear file-not-found error, not silently rendered.
    """
    if variant.startswith(f"{design_name}."):
        variant = variant[len(design_name) + 1:]
    path = os.path.join(root, "specs", "inventories", inventory_name,
                        "cut-specs", f"{design_name}.{variant}.yaml")
    if os.path.exists(path):
        return path
    raise FileNotFoundError(
        f"no cut-spec {design_name}.{variant} under "
        f"specs/inventories/{inventory_name}/cut-specs/")
