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
    panel_specs,
    panel_summaries,
    slice_fulfillment,
    validate_components_unique,
    volume_sanity,
    warnings,
)
from .format import frac_inches
from .geometry import measure_to_sixteenths


def _m(s) -> str:
    """Signed measurement string (keeps a negative sign for negative margins)."""
    return ("-" + frac_inches(-s)) if s < 0 else frac_inches(s)


def _margin_str(s: int, kerf: int) -> str:
    """Margin display: a negative margin whose absolute value is less
    than one kerf is presented as 0″ margin. The true value is kept
    for warning amounts; only the display is clamped.
    """
    return "0″" if -kerf < s < 0 else _m(s)


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
    L.append("Cut list for the finished design, in build order.")
    L.append("")

    # Cut list order is always alphabetical by species, then board id,
    # regardless of the order boards appear in the cut-spec file, so
    # the table and the Board Rip Diagram always match.
    rips = sorted(board_rips(project, cut_spec, tool_limits),
                  key=lambda r: (r.species, r.id))
    summaries = panel_summaries(project, tool_limits)

    # --- Section: warnings (omitted entirely when there are none) -------- #
    warns = warnings(project, cut_spec, tool_limits)
    if warns:
        order = {"red": 0, "yellow": 1, "gray": 2}
        # The MD is the visual representation, so levels and types are
        # written as human words here, not as internal codes or colours.
        # derive.py keeps the machine values ("red"/"yellow"/"gray" and
        # snake_case codes); this rendering layer is where they become
        # ERROR/WARNING/NOTE and "Ghost Boards" etc. The PDF then renders
        # the MD faithfully, with no content transformation of its own.
        level_label = {"red": "ERROR", "yellow": "WARNING", "gray": "NOTE"}
        warns_sorted = sorted(warns, key=lambda w: order.get(w.level, 9))
        L.append(sec("Warnings"))
        L.append("")
        L.append("| # | Lvl | Type | Message |")
        L.append("| --- | --- | --- | --- |")
        for i, w in enumerate(warns_sorted, 1):
            type_label = w.code.replace("_", " ").title()
            L.append(f"| {i} | {level_label.get(w.level, w.level)} | {type_label} | {w.message} |")
        L.append("")

    # --- Section: finished board ----------------------------------------- #
    L.append(sec("Finished board pattern"))
    L.append("")
    ft = project.get("finishedThickness")
    fw = project.get("finishedWidth")
    fl = project.get("finishedLength")
    trims = project.get("edgeTrims") or {}
    if batch > 1:
        if fw is not None and fl is not None and ft:
            _edges = ", ".join(
                f"{edge} {frac_inches(measure_to_sixteenths(trims[edge]))}"
                for edge in ("left", "right", "top", "bottom")
                if edge in trims)
            _size = (f" Final size {frac_inches(measure_to_sixteenths(fw))} × "
                     f"{frac_inches(measure_to_sixteenths(fl))} × "
                     f"{frac_inches(measure_to_sixteenths(ft))}.")
            if _edges:
                _size += f" Edge trims: {_edges}."
        elif trims and ft and project.get("sliceGrid"):
            from .geometry import resolve_slice, slice_length
            _grid = project["sliceGrid"]
            _gw = sum(max(slice_length(resolve_slice(project, _grid[r][c]["sliceId"]))
                          for r in range(len(_grid))) for c in range(len(_grid[0])))
            _gh = sum(resolve_slice(project, _grid[r][0]["sliceId"]).height for r in range(len(_grid)))
            _et = lambda e: measure_to_sixteenths(trims[e]) if e in trims else 0
            _fw = _gw - _et("left") - _et("right")
            _fl = _gh - _et("top") - _et("bottom")
            _edges = ", ".join(
                f"{edge} {frac_inches(_et(edge))}"
                for edge in ("left", "right", "top", "bottom"))
            _size = (f" Final size {frac_inches(_fw)} × {frac_inches(_fl)} × "
                     f"{frac_inches(measure_to_sixteenths(ft))}. "
                     f"Edge trims: {_edges}.")
        elif ft:
            _size = f" Final thickness {frac_inches(measure_to_sixteenths(ft))}."
        else:
            _size = ""
        L.append(f"{batch} finished boards." + _size)
        L.append("")
    L.append(f"![Finished board]({images['finished']})")
    L.append("")

    # --- Section: volume sanity check ------------------------------------ #
    L.append(sec("Volume Sanity Check"))
    L.append("")
    L.append("Review the per-species volumes against inventory.")
    L.append("")
    L.append("| Species | Available | Required | Volume Offset |")
    L.append("| --- | --- | --- | --- |")
    def _bf(v):  # cubic sixteenths -> board feet string
        return f"{v / 4096 / 144:.1f}"
    for r in volume_sanity(project, tool_limits):
        need = r.finished + r.required_loss
        off = r.available - need
        off_bf = off / 4096 / 144
        off_s = f"+{off_bf:.1f}" if off_bf >= 0 else f"{off_bf:.1f}"
        pct = (r.available / need * 100) if need else 0
        req = f"{_bf(r.finished)} BF + {_bf(r.required_loss)} BF loss = {_bf(need)} BF"
        L.append(
            f"| {_species_short(r.species)} | {_bf(r.available)} BF | {req} | "
            f"{off_s} BF ({pct:.0f}%) |"
        )
    L.append("")

    # --- Section: crosscut blanks (the first physical step) -------------- #
    L.append(sec("Crosscut Blanks"))
    L.append("")
    L.append(
        "This plan involves cutting blanks from the inventory — review the "
        "inventory and the planned cuts."
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
    if images.get("crosscut_compact"):
        L.append(f"![Crosscut Diagram — raw boards cut into length blanks]({images['crosscut_compact']})")
    elif images.get("crosscut_prims"):
        # Consecutive image lines (no blank lines between them) so a
        # Markdown renderer flows them and the PDF groups them.
        for cb in blanks:
            if cb.source_id in images["crosscut_prims"]:
                L.append(f"![Crosscut — {cb.source_id}]({images['crosscut_prims'][cb.source_id]})")
    else:
        L.append(f"![Crosscut Diagram — raw boards cut into length blanks]({images['crosscut']})")
    L.append("")

    # --- Section: initial board rips (the actual cut list) ------------- #
    # This section follows the Crosscut Blanks section (so it is section 5
    # in a plan that has a Warnings section, as plaid does), ahead of
    # Panels overview. Inside the section the rip cut table comes first,
    # then the Board Rip Diagram that pictures it.
    L.append(sec("Initial board rips (the cut list)"))
    L.append("")
    L.append("Review the rip list.")
    L.append("")
    L.append("| Board | Origin | Species | Length | Rips (width × count) | Used | Loss | Margin |")
    L.append("| --- | --- | --- | --- | --- | --- | --- | --- |")
    # Child boards, in cut-spec document order (the order their crosscuts
    # are taken off the parent's margin slab), grouped by parent board.
    _children: Dict[str, List[str]] = {}
    for _b in cut_spec.get("boards", []):
        _parent = _b.get("sourceRemainder")
        if _parent:
            _children.setdefault(_parent, []).append(_b["id"])
    _rip_by_id = {r.id: r for r in rips}
    _miter_kerf = measure_to_sixteenths(lim["miterKerf"])
    _saw_kerf = measure_to_sixteenths(lim["sawKerf"])
    for r in rips:
        strip_desc = _rip_desc(r.strips)
        board = f"{r.id} @ {frac_inches(r.source_width)}"
        L.append(
            f"| {board} | {_origin_label(r.origin)} | {_species_short(r.species)} | "
            f"{frac_inches(r.length)} | {strip_desc} | "
            f"{frac_inches(r.used)} | {frac_inches(r.loss)} | {_margin_str(r.margin, _saw_kerf)} |"
        )
        if r.id in _children:
            _child_ids = _children[r.id]
            _child_lens = [_rip_by_id[c].length for c in _child_ids
                           if c in _rip_by_id]
            if _child_lens:
                _sum_len = sum(_child_lens)
                # A kerf is consumed between successive children, and one
                # more after the last child when a slab tail remains to be
                # cut free; when the children exactly fill (or overflow)
                # the slab there is no tail kerf.
                if _sum_len + (len(_child_lens) - 1) * _miter_kerf >= r.length:
                    _kerf_total = (len(_child_lens) - 1) * _miter_kerf
                else:
                    _kerf_total = len(_child_lens) * _miter_kerf
                _tail = r.length - _sum_len - _kerf_total
                _child_desc = "; ".join(
                    f"{c} = {frac_inches(_rip_by_id[c].length)}"
                    for c in _child_ids if c in _rip_by_id)
                _tail_s = _m(_tail) + (" (overflow!)" if _tail < 0 else "")
                L.append(
                    f"| ↳ margin crosscuts | remainder of {r.id} | "
                    f"{_species_short(r.species)} | "
                    f"{frac_inches(_sum_len + _kerf_total)} | {_child_desc} | "
                    f"{frac_inches(_sum_len)} | {frac_inches(_kerf_total)} | "
                    f"{_tail_s} |"
                )
    L.append("")
    L.append("### Board Rip Diagram")
    L.append("")
    L.append("Review the board rip diagrams against the rip list.")
    L.append("")
    if images.get("strip_prims"):
        for r in rips:
            if r.id in images["strip_prims"]:
                L.append(f"![Board rip — {r.id}]({images['strip_prims'][r.id]})")
    else:
        L.append(f"![Board Rip Diagram — how the cut list lands on each board]({images['strip_map']})")
    L.append("")

    # --- Section: panels overview (table + two diagram sub-sections) ----- #
    L.append(sec("Panels overview"))
    L.append("")
    # Quantity of each panel type the plan actually builds (from panel specs:
    # actual panels if any, else one ideal-defaulted spec).
    from collections import Counter as _Counter
    _specs = panel_specs(project, cut_spec, tool_limits)
    qty_by_panel = _Counter(s.panel_id for s in _specs)
    L.append("| Panel | Qty | Length | Slices | Height | Ripped | Sequence (outer → in) |")
    L.append("| --- | --- | --- | --- | --- | --- | --- |")
    for s in summaries:
        if len(s.profiles) == 1 and not s.profiles[0][0]:
            slices = str(s.total_slices)          # single-profile: just the count
        else:
            inner = " + ".join(f"{pid}:{n}" for pid, n in s.profiles)
            slices = f"{s.total_slices} ({inner})"
        ripped = f"2× ({frac_inches(s.height)})" if s.ripped else "—"
        qty = qty_by_panel.get(s.id, 0)
        L.append(
            f"| {s.id} | {qty} | {frac_inches(s.length)} | {slices} | "
            f"{frac_inches(s.height)} | {ripped} | {s.sequence} |"
        )
    L.append("")

    L.append("### Panel End Grain Diagram")
    L.append("")
    L.append("Review the panel end-grain diagrams.")
    L.append("")
    if images.get("panels_compact"):
        L.append(f"![Panel end-grain cross-sections]({images['panels_compact']})")
    elif images.get("panel_prims"):
        for _p in project["panels"]:
            if _p["id"] in images["panel_prims"]:
                L.append(f"![Panel — {_p['id']}]({images['panel_prims'][_p['id']]})")
    else:
        L.append(f"![Panel end-grain cross-sections]({images['panels']})")
    L.append("")

    L.append("### Panel Face Diagram")
    L.append("")
    L.append("Review the panel face diagrams.")
    L.append("")
    if images.get("panel_face_prims"):
        for _p in project["panels"]:
            if _p["id"] in images["panel_face_prims"]:
                L.append(f"![Panel face — {_p['id']}]({images['panel_face_prims'][_p['id']]})")
        L.append("")
        if images.get("panel_faces_legend"):
            L.append(f"![Panel faces legend]({images['panel_faces_legend']})")
    else:
        L.append(f"![Panel faces to scale]({images['panel_faces']})")
    L.append("")

    L.append("### Slice Fulfillment")
    L.append("")
    L.append("Review slice demand, supply, and offset.")
    L.append("")
    L.append("| Slice | Demand | Supplied | Supply Offset |")
    L.append("| --- | --- | --- | --- |")
    for r in slice_fulfillment(project, cut_spec, tool_limits):
        offset = r.supplied - r.demand
        off = f"+{offset}" if offset > 0 else str(offset)
        dem = f"{r.per_board} × {r.batch} = {r.demand}"
        if r.rip_mult > 1:
            sup = f"{r.pre_rip_supplied} × {r.rip_mult} = {r.supplied}"
        else:
            sup = str(r.supplied)
        L.append(f"| {r.slice_id} | {dem} | {sup} | {off} |")
    L.append("")

    # --- Section 6: components (demand) ---------------------------------- #
    L.append(sec("Components"))
    L.append("")
    L.append("Review component demand, fulfillment, and shortfall.")
    L.append("")
    rows, unused, wasted = match_supply_to_demand(project, cut_spec, tool_limits)
    show_overcut = any(r.overcut for r in rows)
    cols = ["Component", "Species", "Width", "Length", "Demand", "Fulfilled", "Shortfall"]
    if show_overcut:
        cols.append("Total Overcut")
    L.append("| " + " | ".join(cols) + " |")
    L.append("| " + " | ".join("---" for _ in cols) + " |")
    for r in sorted(rows, key=lambda r: (r.component_id, -r.length)):
        line = (
            f"| {r.component_id} | {_species_short(r.species)} | {frac_inches(r.width)} | "
            f"{frac_inches(r.length)} | {r.demand} | {r.fulfilled} | {r.shortfall} |"
        )
        if show_overcut:
            line += f" {frac_inches(r.overcut) if r.overcut else '0'} |"
        L.append(line)
    L.append("")
    if unused:
        L.append("**Unused pieces:**")
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
        L.append("**Wasted pieces:**")
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
    L.append("Review the panels and their quantities.")
    L.append("")
    L.append("| Panel | Qty | Length | Profiles (slices) | Component sequence |")
    L.append("| --- | --- | --- | --- | --- |")
    seq_by_type = {s.id: s.sequence for s in summaries}
    from collections import OrderedDict as _OD
    grouped: "_OD[tuple, dict]" = _OD()
    for ps in panel_specs(project, cut_spec, tool_limits):
        key = (ps.panel_id, ps.length, tuple(ps.profile_slices))
        g = grouped.get(key)
        if g is None:
            grouped[key] = dict(spec=ps, qty=1)
        else:
            g["qty"] += 1
    for g in grouped.values():
        ps = g["spec"]
        profs = ", ".join(f"{pid or 'single'}: {n}" for pid, n in ps.profile_slices)
        L.append(
            f"| {ps.panel_id} | {g['qty']} | {frac_inches(ps.length)} | {profs} | "
            f"{seq_by_type.get(ps.panel_id, '')} |"
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
