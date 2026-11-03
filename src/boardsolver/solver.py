"""Round 3 (greedy) solver: derive a workable cut-specs.yaml from a project.

This is deliberately NOT an optimiser. It guarantees, by construction:

* every component stick demanded by ``panelSpecs`` is produced,
* no inventory board is ever over-ripped (margin >= 0 on every sourced board),
* demand that cannot fit in inventory goes on a bought (ghost) board.

It does not promise a locally optimal packing. A human can tweak the
output afterwards; that is the intended workflow for a project that is
only built every few months.

Method
------
1. Demand comes from ``derive.component_demand`` (one stick per component
   position in each physical panel, at that panel's physical length).
2. Sticks are grouped by (species, width, length) and turned into strips:
   a strip holds as many sticks of one group as fit in one blank, allowing
   one miter kerf between crosscuts.
3. Strips are placed largest-width first (first-fit-decreasing order).
   For each strip, the best fit is the existing blank of the same species
   whose margin after placement is smallest but still >= 0. Margin is
   exactly the docwriter's: ``source_width - used - loss``, with
   ``loss = n_strips * (sawKerf + minPlaneLoss)``.
4. If no existing blank fits, a new blank is opened: first from an
   already-started inventory board that still has length left, then from
   an unused inventory board of that species. A blank is only opened if
   the strip's cuts fit in it lengthwise.
5. If no inventory blank can take the strip, a ghost (bought) board is
   created for that species, capped at the widest inventory width for
   the species so a ghost still looks like a real board.

Blank ids follow the existing convention: source id + a letter
(BC1A, BC1B, ...). Ghost ids are GH-<initial><n> (GH-C, GH-C2, ...).
"""

from __future__ import annotations

import argparse
import math
from collections import defaultdict
from typing import Any, Dict, List, Optional

import yaml

from .derive import component_demand
from .geometry import measure_to_sixteenths


def _lim(tool_limits: Dict[str, Any]) -> Dict[str, Any]:
    return tool_limits["limits"] if "limits" in tool_limits else tool_limits


def _fmt(m: int) -> str:
    """Sixteenths -> YAML measurement pair [whole, remainder]."""
    return f"[{m // 16}, {m % 16}]"


class _Blank:
    def __init__(self, bid: str, species: str, width: int, length: int,
                 source: Optional[str] = None,
                 buy_species: Optional[str] = None):
        self.id = bid
        self.species = species
        self.width = width  # capacity width (source width, or ghost cap)
        self.length = length
        self.source = source
        self.buy_species = buy_species
        self.strips: List[Dict[str, Any]] = []  # {"width": int, "cuts": [int]}

    @property
    def used(self) -> int:
        return sum(s["width"] for s in self.strips)

    def margin_after(self, strip_width: int, loss_per_strip: int) -> int:
        n = len(self.strips) + 1
        return self.width - (self.used + strip_width) - n * loss_per_strip

    def strip_fits_length(self, cuts: List[int], miter_kerf: int) -> bool:
        total = sum(cuts) + max(len(cuts) - 1, 0) * miter_kerf
        return total <= self.length


def solve(project: Dict[str, Any], tool_limits: Dict[str, Any]) -> Dict[str, Any]:
    lim = _lim(tool_limits)
    saw_kerf = measure_to_sixteenths(lim["sawKerf"])
    plane_loss = measure_to_sixteenths(lim["minPlaneLoss"])
    loss_per_strip = saw_kerf + plane_loss
    miter_kerf = measure_to_sixteenths(lim["miterKerf"])
    max_cut = measure_to_sixteenths(lim["maxCutLength"]) if lim.get("maxCutLength") else None

    # --- demand -> strips -------------------------------------------------
    # One strip object per group strip: {species, width, cuts}
    strips: List[Dict[str, Any]] = []
    for d in component_demand(project, tool_limits):
        nominal_blank = max_cut if max_cut else max(
            measure_to_sixteenths(b["length"]) for b in project["boards"]
        )
        per_strip = (nominal_blank + miter_kerf) // (d.length + miter_kerf)
        if per_strip < 1:
            raise ValueError(
                f"component {d.id} stick length {d.length} does not fit "
                f"in a {nominal_blank}-sixteenth blank"
            )
        remaining = d.count
        while remaining > 0:
            n = min(per_strip, remaining)
            strips.append({
                "species": d.species, "width": d.width,
                "cuts": [d.length] * n,
            })
            remaining -= n

    # Largest width first; deterministic tie-breaks.
    strips.sort(key=lambda s: (-s["width"], s["species"], -len(s["cuts"])))

    inv_by_species: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for b in project["boards"]:
        inv_by_species[b["species"]].append(b)
    max_width_by_species = {
        sp: max(measure_to_sixteenths(b["width"]) for b in boards)
        for sp, boards in inv_by_species.items()
    }

    blanks: List[_Blank] = []
    # Per inventory board: blanks opened, and length already consumed
    # (sum of blank lengths + one miter kerf between consecutive blanks).
    consumed: Dict[str, int] = defaultdict(int)
    blank_count: Dict[str, int] = defaultdict(int)
    ghost_count: Dict[str, int] = defaultdict(int)

    def _new_blank_for(source_board: Dict[str, Any], strip: Dict[str, Any]) -> Optional[_Blank]:
        sid = source_board["id"]
        raw_len = measure_to_sixteenths(source_board["length"])
        used_len = consumed[sid]
        kerf = miter_kerf if blank_count[sid] > 0 else 0
        remaining = raw_len - used_len - kerf
        if remaining < sum(strip["cuts"]) + max(len(strip["cuts"]) - 1, 0) * miter_kerf:
            return None
        length = min(max_cut, remaining) if max_cut else remaining
        if length < sum(strip["cuts"]) + max(len(strip["cuts"]) - 1, 0) * miter_kerf:
            return None
        letter = chr(ord("A") + blank_count[sid])
        blank = _Blank(
            bid=f"{sid}{letter}", species=source_board["species"],
            width=measure_to_sixteenths(source_board["width"]),
            length=length, source=sid,
        )
        blank_count[sid] += 1
        consumed[sid] = used_len + kerf + length
        return blank

    def _new_ghost(strip: Dict[str, Any]) -> _Blank:
        sp = strip["species"]
        ghost_count[sp] += 1
        initial = sp[0].upper()
        suffix = "" if ghost_count[sp] == 1 else str(ghost_count[sp])
        length = max_cut if max_cut else max(
            measure_to_sixteenths(b["length"]) for b in project["boards"]
        )
        return _Blank(
            bid=f"GH-{initial}{suffix}", species=sp,
            width=max_width_by_species.get(sp, length),
            length=length, buy_species=sp,
        )

    for strip in strips:
        # Best fit among existing blanks of this species.
        best: Optional[_Blank] = None
        best_margin: Optional[int] = None
        for blank in blanks:
            if blank.species != strip["species"]:
                continue
            if not blank.strip_fits_length(strip["cuts"], miter_kerf):
                continue
            margin = blank.margin_after(strip["width"], loss_per_strip)
            if margin >= 0 and (best_margin is None or margin < best_margin):
                best, best_margin = blank, margin
        if best is not None:
            best.strips.append({"width": strip["width"], "cuts": strip["cuts"]})
            continue

        # Open a new blank: already-started sources first, then unused.
        sources = inv_by_species.get(strip["species"], [])
        ordered = sorted(sources, key=lambda b: (blank_count[b["id"]] == 0, b["id"]))
        placed = False
        for src in ordered:
            blank = _new_blank_for(src, strip)
            if blank is None:
                continue
            # Width must fit on a fresh blank too.
            if blank.margin_after(strip["width"], loss_per_strip) < 0:
                # Undo the length consumption for this unused blank.
                blank_count[src["id"]] -= 1
                consumed[src["id"]] -= (miter_kerf if blank_count[src["id"]] > 0 else 0) + blank.length
                continue
            blank.strips.append({"width": strip["width"], "cuts": strip["cuts"]})
            blanks.append(blank)
            placed = True
            break
        if placed:
            continue

        # Ghost board: same best-fit rule among existing ghosts.
        best = None
        best_margin = None
        for blank in blanks:
            if blank.buy_species is None or blank.species != strip["species"]:
                continue
            if not blank.strip_fits_length(strip["cuts"], miter_kerf):
                continue
            margin = blank.margin_after(strip["width"], loss_per_strip)
            if margin >= 0 and (best_margin is None or margin < best_margin):
                best, best_margin = blank, margin
        if best is not None:
            best.strips.append({"width": strip["width"], "cuts": strip["cuts"]})
            continue
        ghost = _new_ghost(strip)
        ghost.strips.append({"width": strip["width"], "cuts": strip["cuts"]})
        blanks.append(ghost)

    # --- emit YAML in the existing cut-specs style ------------------------
    out_boards = []
    for blank in blanks:
        entry: Dict[str, Any] = {"id": blank.id}
        if blank.source:
            entry["source"] = blank.source
        else:
            entry["buySpecies"] = blank.buy_species
        entry["length"] = blank.length
        entry["strips"] = blank.strips
        out_boards.append(entry)
    return {"boards": out_boards}


def _dump(cut_spec: Dict[str, Any]) -> str:
    lines = [
        "# yaml-language-server: $schema=../../../schema.json",
        "# Generated by the greedy solver (boardsolver.solver).",
        "# Workable, not optimised: tweak by hand afterwards if you like.",
        "boards:",
    ]
    for board in cut_spec["boards"]:
        lines.append(f"- id: {board['id']}")
        if "source" in board:
            lines.append(f"  source: {board['source']}")
        else:
            lines.append(f"  buySpecies: {board['buySpecies']}")
        lines.append(f"  length: {_fmt(board['length'])}")
        lines.append("  strips:")
        for strip in board["strips"]:
            lines.append(f"  - width: {_fmt(strip['width'])}")
            lines.append("    cuts:")
            for cut in strip["cuts"]:
                lines.append(f"    - {_fmt(cut)}")
    return "\n".join(lines) + "\n"


def _main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="board-solver greedy solver (Round 3)")
    ap.add_argument("--project", required=True)
    ap.add_argument("--tool-limits", required=True)
    ap.add_argument("--out", required=True, help="cut-specs.yaml to write")
    args = ap.parse_args(argv)
    with open(args.project) as f:
        project = yaml.safe_load(f)
    with open(args.tool_limits) as f:
        tool_limits = yaml.safe_load(f)
    cut_spec = solve(project, tool_limits)
    with open(args.out, "w") as f:
        f.write(_dump(cut_spec))
    n_boards = len(cut_spec["boards"])
    n_ghosts = sum(1 for b in cut_spec["boards"] if "buySpecies" in b)
    n_strips = sum(len(b["strips"]) for b in cut_spec["boards"])
    print(f"wrote {args.out}: {n_boards} boards ({n_ghosts} ghost), {n_strips} strips")
    return 0


if __name__ == "__main__":
    raise SystemExit(_main())
