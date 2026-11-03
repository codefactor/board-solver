"""Markdown document assembly for the Round 2 document-writer.

Builds the six-section human-readable plan as a Markdown string, embedding the
(content-hashed) image filenames the caller has written, and the derived tables.
Pure string building; the caller owns file I/O and image hashing.
"""

from __future__ import annotations

from typing import Any, Dict, List

from .derive import (
    board_rips,
    crosscut_blanks,
    match_supply_to_demand,
    panel_summaries,
    validate_components_unique,
    warnings,
)
from .format import frac_inches
from .geometry import measure_to_sixteenths


def _m(s) -> str:
    """Signed measurement string (keeps a negative sign for negative margins)."""
    return ("-" + frac_inches(-s)) if s < 0 else frac_inches(s)


def _species_short(name: str) -> str:
    return {"Brown Maple": "maple", "Walnut": "walnut", "Cherry": "cherry"}.get(name, name)


def _origin_label(origin: str) -> str:
    kind, _, ref = origin.partition(":")
    return {
        "source": ref,
        "remainder": f"remainder of {ref}",
        "buy": "*None*",
    }.get(kind, origin)


def build_markdown(
    project: Dict[str, Any],
    tool_limits: Dict[str, Any],
    cut_spec: Dict[str, Any],
    images: Dict[str, str],
) -> str:
    """Assemble the plan document. ``images`` maps section keys
    (``finished``, ``panels``, ``strip_map``) to hashed image filenames.
    """
    validate_components_unique(project)
    lim = tool_limits["limits"] if "limits" in tool_limits else tool_limits
    name = project.get("name", "Project")
    batch = project.get("batch", 1)
    L: List[str] = []
    _sec = [0]
    def sec(title: str) -> str:
        _sec[0] += 1
        return f"## {_sec[0]}. {title}"

    L.append(f"# {name} — Cut Plan")
    L.append("")
    if project.get("description"):
        L.append(f"*{project['description']}*")
        L.append("")
    L.append(
        "This is a generated plan: the finished design (sections 1, 2, 4, 5) and the "
        "cut list that realizes it on the boards in hand (the Initial board rips "
        "section). Where the cut "
        "list cannot be met from inventory it calls for **bought boards** — buy those "
        "and re-run before cutting."
    )
    L.append("")

    rips = board_rips(project, cut_spec, tool_limits)
    summaries = panel_summaries(project, tool_limits)

    # --- Section: warnings (omitted entirely when there are none) -------- #
    warns = warnings(project, cut_spec, tool_limits)
    if warns:
        order = {"red": 0, "yellow": 1, "gray": 2}
        emoji = {"red": "\U0001F534", "yellow": "\U0001F7E1", "gray": "\u26AA"}
        warns_sorted = sorted(warns, key=lambda w: order.get(w.level, 9))
        L.append(sec("Warnings"))
        L.append("")
        L.append("| # | Lvl | Type | Message |")
        L.append("| --- | --- | --- | --- |")
        for i, w in enumerate(warns_sorted, 1):
            L.append(f"| {i} | {emoji.get(w.level, '')} | {w.code} | {w.message} |")
        L.append("")
        L.append("Legend:")
        L.append("")
        L.append("- \U0001F534 invalid / impossible as written")
        L.append("- \U0001F7E1 at risk or needs more material")
        L.append("- \u26AA produces unusable output")
        L.append("")

    # --- Section: finished board ----------------------------------------- #
    L.append(sec("Finished board pattern"))
    L.append("")
    ft = project.get("finishedThickness")
    if batch > 1:
        L.append(f"{batch} finished boards." + (f" Final thickness {frac_inches(measure_to_sixteenths(ft))}." if ft else ""))
        L.append("")
    L.append("The finished plaid face.")
    L.append("")
    L.append(f"![Finished plaid face]({images['finished']})")
    L.append("")

    # --- Section 2: slice grid ------------------------------------------- #
    L.append(sec("Slice Grid"))
    L.append("")
    L.append(
        "The same grid keyed by slice id: each slice is framed in its legend color "
        "so you can see how to arrange the grid cell by cell. A corner triangle "
        "marks a slice placed horizontally flipped."
    )
    L.append("")
    L.append(f"![Slice grid keyed by slice id]({images['slice_map']})")
    L.append("")

    # --- Section 3: panels overview -------------------------------------- #
    L.append(sec("Panels overview"))
    L.append("")
    L.append(f"![Panel cross-sections]({images['panels']})")
    L.append("")
    L.append("| Panel | Length | Slices | Height | Ripped | Sequence (outer → in) |")
    L.append("| --- | --- | --- | --- | --- | --- |")
    for s in summaries:
        slices = " + ".join(f"{pid or '—'}:{n}" for pid, n in s.profiles)
        ripped = f"2× ({frac_inches(s.height)})" if s.ripped else "—"
        L.append(
            f"| {s.id} | {frac_inches(s.length)} | {s.total_slices} ({slices}) | "
            f"{frac_inches(s.height)} | {ripped} | {s.sequence} |"
        )
    L.append("")

    # --- Section 4: crosscut blanks -------------------------------------- #
    L.append(sec("Crosscut Blanks"))
    L.append("")
    L.append(
        "The first operation: crosscut each raw inventory board along its length "
        "into the labeled board blanks that get ripped later (the Initial board rips "
        "section). Boards "
        "that start from another board's leftover margin are not raw-stock "
        "crosscuts — they appear as the labeled offcuts in the Board Rip Diagram."
    )
    L.append("")
    blanks = crosscut_blanks(project, cut_spec, tool_limits)
    L.append("| Raw board | Species | Raw length | Blanks (id = length) | Leftover |")
    L.append("| --- | --- | --- | --- | --- |")
    for cb in blanks:
        if cb.state == "spare":
            blist = "— (untouched spare)"
            leftover = "—"
        elif cb.state == "whole":
            blist = "; ".join(f"{b.blank_id} = {frac_inches(b.length)} (used whole)" for b in cb.blanks)
            leftover = _m(cb.leftover)
        else:
            blist = "; ".join(f"{b.blank_id} = {frac_inches(b.length)}" for b in cb.blanks)
            leftover = _m(cb.leftover) + (" (overflow!)" if cb.leftover < 0 else "")
        L.append(
            f"| {cb.source_id} | {_species_short(cb.species)} | "
            f"{frac_inches(cb.length)} | {blist} | {leftover} |"
        )
    L.append("")
    L.append("### Crosscut Diagram")
    L.append("")
    L.append(
        "Each bar is one raw board drawn to scale by length; segments are the "
        "blanks (labeled with id and length inside), reddish stripes are crosscut "
        "kerfs (sawdust), and the pale tail is leftover length. A red tail means "
        "the blanks overflow the raw board. An untouched spare is shown washed-out "
        "and uncut; a board used whole goes straight to the rip diagram."
    )
    L.append("")
    L.append(f"![Crosscut Diagram — raw boards cut into length blanks]({images['crosscut']})")
    L.append("")

    # --- Section 5: initial board rips (the actual cut list) ------------- #
    L.append(sec("Initial board rips (the cut list)"))
    L.append("")
    L.append(
        "Each row is one physical board at the saw: rip the strips down its width, "
        "then crosscut each strip to the piece lengths. The **Board** column shows "
        "`id @ width` — the board's width when ripping begins. **Used** is the summed "
        "strip width, **Loss** is rip kerf + planer cleanup per strip, **Margin** is "
        "the leftover width (negative = the strips do not fit; large = the board is "
        "oversized for what it yields)."
    )
    L.append("")
    L.append("| Board | Origin | Species | Length | Rips (width × count) | Used | Loss | Margin |")
    L.append("| --- | --- | --- | --- | --- | --- | --- | --- |")
    for r in rips:
        strip_desc = _rip_desc(r.strips)
        board = f"{r.id} @ {frac_inches(r.source_width)}"
        L.append(
            f"| {board} | {_origin_label(r.origin)} | {_species_short(r.species)} | "
            f"{frac_inches(r.length)} | {strip_desc} | "
            f"{frac_inches(r.used)} | {frac_inches(r.loss)} | {_m(r.margin)} |"
        )
    L.append("")
    L.append("### Board Rip Diagram")
    L.append("")
    L.append(
        "Each labeled block below is one physical board. Horizontal bands are the "
        "strips ripped down the board's width; within a band, the colored cells are "
        "the crosscut pieces (with thin kerf gaps between them) and the lightened "
        "tail is the offcut. The pale band under the strips is the leftover margin; "
        "a gray title marks a board that must be bought."
    )
    L.append("")
    L.append(f"![Board Rip Diagram — how the cut list lands on each board]({images['strip_map']})")
    L.append("")

    # --- Section 6: components (demand) ---------------------------------- #
    L.append(sec("Components"))
    L.append("")
    L.append(
        "**Demand** is what the finished pattern needs (counted from the slice "
        "grid; length is the panel the component belongs to). **Fulfilled** is how "
        "many the cut list supplies, matched longest-demand-first using exact-length "
        "pieces first, then longer pieces cut down (a piece shorter than the demand "
        "cannot be used). **Shortfall** is the unmet count."
    )
    L.append("")
    rows, unused, wasted = match_supply_to_demand(project, cut_spec, tool_limits)
    show_overcut = any(r.overcut for r in rows)
    cols = ["Component", "Species", "Width", "Length", "Demand", "Fulfilled", "Shortfall"]
    if show_overcut:
        cols.append("Total Overcut")
    L.append("| " + " | ".join(cols) + " |")
    L.append("| " + " | ".join("---" for _ in cols) + " |")
    for r in rows:
        line = (
            f"| {r.component_id} | {_species_short(r.species)} | {frac_inches(r.width)} | "
            f"{frac_inches(r.length)} | {r.demand} | {r.fulfilled} | {r.shortfall} |"
        )
        if show_overcut:
            line += f" {frac_inches(r.overcut) if r.overcut else '0'} |"
        L.append(line)
    L.append("")
    if unused:
        L.append(
            "**Unused pieces** — produced by the cut list but not attributable to any "
            "demand (wrong length for every demand row that needed this component):"
        )
        L.append("")
        L.append("| Component | Species | Width | Length | Count |")
        L.append("| --- | --- | --- | --- | --- |")
        for u in unused:
            L.append(
                f"| {u.component_id} | {_species_short(u.species)} | "
                f"{frac_inches(u.width)} | {frac_inches(u.length)} | {u.count} |"
            )
        L.append("")
    if wasted:
        L.append(
            "**Wasted pieces** — produced by the cut list but matching no component "
            "shape in this project (end-grain width the pattern never uses); these "
            "are cut but unusable here:"
        )
        L.append("")
        L.append("| From board | Species | Width | Length | Count |")
        L.append("| --- | --- | --- | --- | --- |")
        for w in wasted:
            L.append(
                f"| {w.board_id} | {_species_short(w.species)} | "
                f"{frac_inches(w.width)} | {frac_inches(w.length)} | {w.count} |"
            )
        L.append("")

    # --- Section 7: panels (merged / sequence) --------------------------- #
    L.append(sec("Panels (profiles and sequence)"))
    L.append("")
    L.append("| Panel | Length | Profiles (slices) | Component sequence |")
    L.append("| --- | --- | --- | --- |")
    for s in summaries:
        profs = ", ".join(f"{pid or 'single'}: {n}" for pid, n in s.profiles)
        L.append(f"| {s.id} | {frac_inches(s.length)} | {profs} | {s.sequence} |")
    L.append("")

    # --- Section 8: plane, slice, flatten -------------------------------- #
    L.append(sec("Plane, slice, and flatten"))
    L.append("")
    sd = measure_to_sixteenths(project["sliceDepth"])
    ftn = measure_to_sixteenths(ft) if ft else None
    L.append(
        f"Glue up each panel, plane to its thickness, then slice crosswise at the "
        f"slice depth ({frac_inches(sd)}) with the miter kerf "
        f"({frac_inches(measure_to_sixteenths(lim['miterKerf']))}) between slices."
    )
    ripped_panels = [s for s in summaries if s.ripped]
    for s in ripped_panels:
        L.append("")
        L.append(
            f"**Panel {s.id} is ripped, not planed thin:** each sliced piece is ripped "
            f"into {s.ripped} strips of {frac_inches(s.height)} (the installed row "
            f"height), so {s.total_slices} sliced pieces yield "
            f"{s.total_slices * s.ripped} installed slices — saving the costlier wood "
            f"from being planed to dust."
        )
    if ftn:
        L.append("")
        L.append(
            f"Finally flatten the end-grain faces to the finished thickness "
            f"({frac_inches(ftn)}); the difference from the slice depth is the whole "
            f"budget for flattening and misalignment."
        )
    L.append("")
    return "\n".join(L)


def _rip_desc(strips) -> str:
    """Rip list for a board: strip widths aggregated by count, ignoring the
    per-cut lengths (how each strip is crosscut to length is handled elsewhere).

    e.g. four 3/4" strips + two 1 1/2" strips -> "1½″ ×2 · ¾″ ×4".
    """
    from collections import Counter
    counts = Counter(measure_to_sixteenths(s["width"]) for s in strips)
    # Widest first for readability.
    parts = [f"{frac_inches(w)} ×{n}" for w, n in sorted(counts.items(), reverse=True)]
    return " · ".join(parts)
