"""Plan checklist: the print-and-execute document, in shop order, for one design + inventory + cut-spec.

Phases 1-4 are the cuts. Phases after that are the glue-ups, slices, and
finishing, in the same order as the sample plan-checklist. The plan document
is the phone-read review document; this checklist is the one to print.
It is a printout to work from at the saw, in the order Scott described:

0. Buy Wood, as Phase 1, only when the cut-spec has ghost boards
   (material to buy, not in inventory): a warning line, then one row
   per board to buy. When present, all later phases shift by one;
   when absent, the phase is omitted and numbering is unchanged.
   Later phases treat a bought board exactly like an inventory board,
   in the desired shape.
1. Initial crosscuts: raw boards -> blanks.
2. Rips: one section per board, end-grain diagram above its rip
   table: species-colored strips at rip size, reddish kerfs between
   strips, gray crosshatched margin last, then a bar 6 px below
   (green total rip-size strip material, red total saw kerf, gray
   crosshatched margin/offcut, aligned with the margin above).
   Top bar 27 px tall (9 px + 200%), bottom bar 9 px tall, gap
   6 px (2 px + 200%), so the diagram still takes little vertical
   space. The only text in that image is the
   board ID and dimension,
   left aligned, above the end-grain row. Rip tables flag
   crosscut-first strips only, with an asterisk, e.g. 3″ (3.00″)*,
   not gangs in general.
   'Pieces planned' is grouped by length, e.g. 15⅞″x3, not repeated
   per piece. Every width in rip tables carries a 2-decimal caliper
   measurement in parentheses, e.g. ¾″ (0.75″), with trailing zeros.
   A board whose margin slab is the source of child boards is followed
   immediately by its margin crosscuts, then its child boards' rip
   sections, before the next parent board. (No child boards in the
   plaid-v2 hand plan; the rule is implemented, not just noted.)
3. Plane by width: one gang per final strip width, across all
   species and boards, so the planer is set once per width, counted
   per species, not listed per strip. A width wider than board
   thickness requires a gang: strips taped together so the gang's
   total thickness reaches the width. If the strip gang is too small,
   crosscut to components first, then gang the components, counted
   as components, not strips; if that gang is still too small, a
   WARNING sits above that gang. A crosscut-first gang's
   crosscuts are in Phase 3 and are not repeated in Phase 4.
4. Crosscut components: strips -> component pieces, after planing,
   except crosscut-first gangs, already crosscut in Phase 3. No
   diagram above the crosscut tables: strip maps are removed from
   this PDF. Final width carries a 2-decimal caliper measurement,
   e.g. 1½″ (1.50″), like the rip tables.
   Crosscut rows do not flag gangs: a gang requirement is for
   planing only, in Phase 3. 'Pieces' is grouped by length,
   e.g. 15⅞″x3, while Cuts checkboxes stay per piece. Piece order
   within a strip does not matter in the shop, even though the plan
   lists them in an order; only the set of lengths per strip matters.
5. Crosscut grouping, at the top of Phase 4: one row per length /
   species / width, with piece counts, then a comma-separated
   totals line for the lengths below the table. No checkboxes.

Rip size = final strip width + minPlaneLoss (1/16 in). Planer setting
= final strip width. Saw kerf 1/8 in between strips; miter kerf 1/8 in
between pieces and between blanks. Off cut = actual remaining material
after the final cut, matching the plan. Phase 1: Length is the blank
length only, plus an Off Cut column for the material remaining after
that cut (final offcut on the last row for a board; 0″ gets a ⚠️).
The PDF also shows the off cut proportion as a 3 pt
progress bar under the Length cell, fixed at Length column width:
green left for cumulative used length, reddish right for the off cut
remaining, for contrast. Species identity is a small colored box
left of the species name in Species columns in the PDF, species
color fill with a dark gray border. A row after the first for a
board uses that board's off cut from the previous row, so it gets a
return icon (↩) and no start length. The PDF draws empty checkbox
squares for printing; the Md keeps "[ ]" for screen.
"""

from __future__ import annotations

import argparse
import hashlib
import os
from collections import OrderedDict
from typing import Any, Dict, List, Tuple

import yaml

from . import bundle, derive
from .colors import DEFAULT_COLORS
from .format import frac_inches
from .geometry import measure_to_sixteenths, sixteenths_to_measure


def _load(path: str):
    with open(path) as f:
        return yaml.safe_load(f)


def _fmt(n: int) -> str:
    return frac_inches(n)


def _fmt_dec(n: int) -> str:
    """Fraction width plus 2-decimal caliper measurement, e.g. ¾″ (0.75″).

    Always 2 decimal places, with trailing zeros, like cents. Sixteenths
    are exact binary fractions, so rounding to 2 places is never a tie.
    Rip sizes in sixteenths therefore round, e.g. 1⁹⁄₁₆″ (1.56″);
    final widths, all quarter-inch increments here, are exact.
    """
    return f"{_fmt(n)} ({n / 16:.2f}″)"


def _offcut_fmt(n: int) -> str:
    """Offcut cell: a 0″ offcut gets a ⚠️, no margin for cutting error.

    A negative offcut (pieces demand more than the strip/board has)
    gets a ⚠️ too: it is an overflow, not just a tight fit.
    """
    return f"{_fmt(n)} ⚠️" if n <= 0 else _fmt(n)


def _margin_fmt(n: int, kerf: int) -> str:
    """Margin cell: a negative margin whose absolute value is less
    than one kerf is presented as 0″ margin, with a ⚠️. The true
    value is kept for warning amounts and for later running-margin
    rows; only the display is clamped. A negative margin of at
    least one kerf stays negative.
    """
    if -kerf < n < 0:
        return "0″ ⚠️"
    return f"{_fmt(n)} ⚠️" if n <= 0 else _fmt(n)


def _running_margin_cell(running: int, kerf: int, is_last: bool) -> str:
    """Running Margin column cell.

    The 0″ clamp applies only on the last rip: a small negative
    margin there is a last-rip shave. A negative running margin on
    an earlier rip is an error, shown as the true negative number,
    because the later rips would be cut from material that isn't
    there — even if the negative value itself is small.
    """
    if is_last:
        return _margin_fmt(running, kerf)
    return f"{_fmt(running)} ⚠️" if running < 0 else _fmt(running)


def _pair(n: int):
    return list(sixteenths_to_measure(n))


def _edge_trim(project, edge):
    """Cut length off one edge in sixteenths; a missing edge is 0."""
    trims = project.get("edgeTrims") or {}
    value = trims.get(edge)
    return measure_to_sixteenths(value) if value is not None else 0


def _finishing_size(project, grid_width, grid_height, slice_depth, finished_th):
    """Finished face size (width, length) in sixteenths.

    The finished size is the declared target when present
    (finishedWidth/finishedLength); edge trims, when declared, are
    the per-edge cuts that reach it and may be unequal — no edge is
    assumed, and no equal split is assumed. Without a declared
    finished size, derive it from edgeTrims (grid minus left minus
    right, grid minus top minus bottom); without either, fall back
    to the old derivation: width trimmed by the flattening
    allowance, length untrimmed.
    """
    fw = project.get("finishedWidth")
    fl = project.get("finishedLength")
    if fw is not None and fl is not None:
        return measure_to_sixteenths(fw), measure_to_sixteenths(fl)
    if project.get("edgeTrims"):
        trim_w = grid_width - _edge_trim(project, "left") - _edge_trim(project, "right")
        trim_h = grid_height - _edge_trim(project, "top") - _edge_trim(project, "bottom")
        return trim_w, trim_h
    return grid_width - (slice_depth - finished_th), grid_height


def _board_thickness(project, cut_spec, board_id):
    """Thickness sixteenths for a cut-spec board, via its source board."""
    by_id = {b["id"]: b for b in project.get("boards", [])}
    cut_by_id = {b["id"]: b for b in cut_spec.get("boards", [])}
    b = cut_by_id.get(board_id, {})
    if "source" in b and b["source"] in by_id:
        th = by_id[b["source"]].get("thickness")
        return measure_to_sixteenths(th) if th is not None else None
    if "sourceRemainder" in b:
        return _board_thickness(project, cut_spec, b["sourceRemainder"])
    return None


def _render_endgrain_png(project, cut_spec, board, rip, saw_kerf, plane_loss) -> bytes:
    """Zoomed-in end-grain rip diagram for one board, as PNG bytes.

    Left to right, to scale: species-colored rectangles for each strip
    at rip size, a reddish kerf between strips (and after the last
    strip, before the margin), then a gray crosshatched margin
    rectangle. Below, 6 px down, a progress bar the full diagram
    width: green left for total rip-size strip material, red middle
    for total saw kerf, gray crosshatched right for the margin/offcut,
    aligned with the margin above. Top bar 27 px tall (9 px + 200%),
    bottom bar 9 px tall, so the diagram still takes little vertical
    space. The only text in the image is the board ID and dimension,
    left aligned, right above the end-grain row.
    """
    from PIL import Image as _Image, ImageDraw as _Draw, ImageFont as _Font
    import io as _io
    W = 1200
    title_h, gap1, grain_h, gap2, bar_h, pad_bottom = 48, 6, 27, 6, 9, 4
    H = title_h + gap1 + grain_h + gap2 + bar_h + pad_bottom
    img = _Image.new("RGB", (W, H), "white")
    draw = _Draw.Draw(img)
    font = None
    for path in ("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
                 "/usr/share/matplotlib/mpl-data/fonts/ttf/DejaVuSans.ttf"):
        try:
            font = _Font.truetype(path, 36)
            break
        except Exception:
            continue
    if font is None:
        font = _Font.load_default()
    length = measure_to_sixteenths(board["length"])
    title = f"{board['id']} ({_fmt(length)} x {_fmt(rip.source_width)}"
    thickness = _board_thickness(project, cut_spec, board["id"])
    if thickness is not None:
        title += f" x {_fmt(thickness)}"
    title += ")"
    draw.text((0, 2), title, fill="black", font=font)
    y0 = title_h + gap1
    y1 = y0 + grain_h
    rip_sizes = [_rip_size(measure_to_sixteenths(s["width"]), plane_loss)
                 for s in board["strips"]]
    total_rip = sum(rip_sizes)
    total_kerf = len(rip_sizes) * saw_kerf
    total = max(rip.source_width, total_rip + total_kerf)
    species_rgb = _rgb_hex(DEFAULT_COLORS.get(rip.species, "#888888"))
    kerf_rgb = _rgb_hex("#c0392b")
    dark = (51, 51, 51)
    # Segments in order: strip, kerf, strip, kerf, ..., margin.
    segments = []
    for rs in rip_sizes:
        segments.append((rs, species_rgb, False))
        segments.append((saw_kerf, kerf_rgb, False))
    if rip.margin > 0:
        segments.append((rip.margin, (208, 208, 208), True))
    def _crosshatch_tile(width_px: int, height_px: int, rgb):
        # Crosshatch on its own tile, so diagonals stay inside the
        # margin rectangle instead of spilling over other segments.
        tile = _Image.new("RGB", (max(1, width_px), max(1, height_px)), rgb)
        tile_draw = _Draw.Draw(tile)
        for d in range(-height_px, tile.width + height_px, 12):
            tile_draw.line([(d, height_px), (d + height_px, 0)], fill=(136, 136, 136), width=1)
        return tile

    px = 0
    six = 0
    for width, rgb, crosshatched in segments:
        six_next = six + width
        px_next = int(round(six_next * W / total)) if total else W
        if crosshatched:
            img.paste(_crosshatch_tile(px_next - px, grain_h, rgb), (px, y0))
            draw.rectangle([px, y0, px_next, y1], outline=dark, width=1)
        else:
            draw.rectangle([px, y0, px_next, y1], fill=rgb, outline=dark, width=1)
        px, six = px_next, six_next
    # Progress bar, full diagram width: green strip material, red kerf,
    # gray crosshatched margin/offcut, aligned with the margin above.
    bar_y0 = y1 + gap2
    bar_y1 = bar_y0 + bar_h
    green_w = int(round(total_rip * W / total)) if total else 0
    kerf_w = int(round((total_rip + total_kerf) * W / total)) if total else 0
    draw.rectangle([0, bar_y0, green_w, bar_y1], fill=_rgb_hex("#28a745"), outline=dark, width=1)
    draw.rectangle([green_w, bar_y0, kerf_w, bar_y1], fill=kerf_rgb, outline=dark, width=1)
    if kerf_w < W:
        img.paste(_crosshatch_tile(W - kerf_w, bar_h, (208, 208, 208)), (kerf_w, bar_y0))
        draw.rectangle([kerf_w, bar_y0, W, bar_y1], outline=dark, width=1)
    draw.rectangle([0, bar_y0, W, bar_y1], outline=dark, width=1)
    if rip.margin < 0:
        # Over-rip: the strips run past the board's edge. Without a
        # marker the diagram scales to the strips and looks complete,
        # so the portion past the board's edge is overlaid with a
        # yellow crosshatch, matching the yellow warning highlight,
        # in the grain row and in the progress bar: that portion is
        # material the board does not have.
        _edge_x = int(round(rip.source_width * W / total)) if total else W
        if _edge_x < W:
            def _yellow_crosshatch_tile(width_px: int, height_px: int):
                tile = _Image.new("RGB", (max(1, width_px), max(1, height_px)), (255, 255, 0))
                tile_draw = _Draw.Draw(tile)
                for d in range(-height_px, tile.width + height_px, 12):
                    tile_draw.line([(d, height_px), (d + height_px, 0)],
                                   fill=(51, 51, 51), width=2)
                return tile
            img.paste(_yellow_crosshatch_tile(W - _edge_x, grain_h), (_edge_x, y0))
            draw.rectangle([_edge_x, y0, W, y1], outline=dark, width=1)
            img.paste(_yellow_crosshatch_tile(W - _edge_x, bar_h), (_edge_x, bar_y0))
            draw.rectangle([_edge_x, bar_y0, W, bar_y1], outline=dark, width=1)
    buf = _io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def _rgb_hex(css_hex: str):
    s = css_hex.lstrip("#")
    return (int(s[0:2], 16), int(s[2:4], 16), int(s[4:6], 16))


def _rip_size(final_width: int, plane_loss: int) -> int:
    return final_width + plane_loss


def _rip_margins(source_width: int, strips, plane_loss: int, saw_kerf: int) -> List[int]:
    """Running margin after each rip, row by row.

    Each rip consumes its rip size (final width + plane loss) plus one
    saw kerf. The last value is the board's total margin.
    """
    out = []
    remaining = source_width
    for strip in strips:
        remaining -= _rip_size(measure_to_sixteenths(strip["width"]), plane_loss) + saw_kerf
        out.append(remaining)
    return out


def _strip_pieces(strip: Dict[str, Any]) -> List[int]:
    return [measure_to_sixteenths(c) for c in strip["cuts"]]


def _grouped_pieces(pieces: List[int]) -> str:
    """Pieces planned, grouped by length, first-occurrence order.

    Same length twice reads as 15⅞″x3, not 15⅞″, 15⅞″, 15⅞″.
    Single pieces carry no multiplier. Used for the Phase 2
    'Pieces planned' column and the Phase 3/4 'Pieces'
    columns. Checkbox columns stay per piece, not grouped.
    Group order is display only: piece order within a strip does
    not matter in the shop, only the set per strip.
    """
    counts: "OrderedDict" = OrderedDict()
    for p in pieces:
        counts[p] = counts.get(p, 0) + 1
    parts = []
    for length, count in counts.items():
        parts.append(f"{_fmt(length)}x{count}" if count > 1 else _fmt(length))
    return ", ".join(parts)


def _tail(strip_len: int, pieces: List[int], kerf: int) -> int:
    if not pieces:
        return strip_len
    return strip_len - sum(pieces) - (len(pieces) - 1) * kerf


# CheckBox is defined inside build_pdf_from_md, where reportlab is
# imported lazily (see pdf.py pattern), so Md generation stays free
# of the reportlab dependency.


def _buy_board_rows(project, data) -> List[Dict[str, Any]]:
    """Ghost boards to buy, in cut-spec order, for the Buy Wood phase.

    A ghost board is a cut-spec board with buy_required set (origin
    buy:<species>): material not in inventory, so the shop must buy
    it before starting. Width is the board width the rip phase starts
    from; thickness is the S3S thickness of that species in inventory,
    or the first inventory board's thickness when the species is not
    in inventory at all. Later phases treat the bought board exactly
    like an inventory board, in the desired shape.
    """
    rows = []
    for b in data["boards"]:
        r = data["rips"][b["id"]]
        if not r.buy_required:
            continue
        thickness = None
        for pb in project.get("boards", []):
            if pb.get("species") == r.species and pb.get("thickness") is not None:
                thickness = measure_to_sixteenths(pb["thickness"])
                break
        if thickness is None and project.get("boards"):
            first_th = project["boards"][0].get("thickness")
            if first_th is not None:
                thickness = measure_to_sixteenths(first_th)
        yields = "; ".join(
            f"{_fmt(measure_to_sixteenths(strip['width']))} → "
            f"{_grouped_pieces(_strip_pieces(strip))}"
            for strip in b["strips"])
        rows.append({
            "id": b["id"], "species": r.species,
            "length": measure_to_sixteenths(b["length"]),
            "width": r.source_width, "thickness": thickness,
            "yields": yields,
        })
    return rows


def _board_order(project, cut_spec, rips) -> List[Dict[str, Any]]:
    """Depth-first board order: parent, margin crosscuts, children, next parent.

    Boards are taken in cut-spec order within each level. Boards with a
    sourceRemainder are children of the named parent; all other boards
    are roots. Any board not reached by the traversal (e.g. a child
    whose parent is missing) is appended in cut-spec order at the end.
    """
    by_id = {b["id"]: b for b in cut_spec["boards"]}
    children: Dict[str, List[Dict[str, Any]]] = {}
    roots: List[Dict[str, Any]] = []
    for b in cut_spec["boards"]:
        if "sourceRemainder" in b:
            children.setdefault(b["sourceRemainder"], []).append(b)
        else:
            roots.append(b)
    out: List[Dict[str, Any]] = []
    seen = set()

    def visit(b):
        if b["id"] in seen:
            return
        seen.add(b["id"])
        out.append(b)
        for child in children.get(b["id"], []):
            visit(child)

    for b in roots:
        visit(b)
    for b in cut_spec["boards"]:
        visit(b)
    return out


def _margin_children(parent_id: str, cut_spec) -> List[Dict[str, Any]]:
    return [b for b in cut_spec["boards"]
            if b.get("sourceRemainder") == parent_id]


def build_data(project, cut_spec, tool_limits):
    """Collect everything the Md and PDF renderers need, from the cut-spec only."""
    lim = tool_limits["limits"] if "limits" in tool_limits else tool_limits
    saw_kerf = measure_to_sixteenths(lim["sawKerf"])
    miter_kerf = measure_to_sixteenths(lim["miterKerf"])
    plane_loss = measure_to_sixteenths(lim["minPlaneLoss"])
    crosscuts = derive.crosscut_blanks(project, cut_spec, tool_limits)
    rips = {r.id: r for r in derive.board_rips(project, cut_spec, tool_limits)}
    boards = _board_order(project, cut_spec, rips)
    # Phase 3: strips grouped by final width, descending, across species/boards.
    # A gang is one such grouping. Gang data comes from derive.gang_groups,
    # so the checklist and the plan warnings use the same calculation.
    gangs = derive.gang_groups(project, cut_spec, tool_limits)
    gangs_by_width = {g.width: g for g in gangs}
    crosscut_first_widths = {g.width for g in gangs if g.crosscut_first}
    by_width: Dict[int, List[Dict[str, Any]]] = OrderedDict()
    for b in boards:
        r = rips[b["id"]]
        for i, strip in enumerate(b["strips"]):
            w = measure_to_sixteenths(strip["width"])
            by_width.setdefault(w, []).append({
                "board": b["id"], "strip_no": i + 1, "species": r.species,
                "final_width": w, "rip_size": _rip_size(w, plane_loss),
                "length": measure_to_sixteenths(b["length"]),
                "pieces": _strip_pieces(strip),
            })
    by_width = OrderedDict(sorted(by_width.items(), reverse=True))
    return {
        "saw_kerf": saw_kerf, "miter_kerf": miter_kerf,
        "plane_loss": plane_loss, "crosscuts": crosscuts,
        "rips": rips, "boards": boards, "by_width": by_width,
        "gangs": gangs, "gangs_by_width": gangs_by_width,
        "crosscut_first_widths": crosscut_first_widths,
        "children": {p: _margin_children(p, cut_spec)
                     for p in by_id_keys(cut_spec)},
    }


def by_id_keys(cut_spec):
    return [b["id"] for b in cut_spec["boards"]]


def _phase1_bars(data):
    """Progress-bar data for Phase 1 rows, in Md row order.

    One entry per Phase 1 table row, skipping spare and whole boards
    (whole boards are not in the table, they get a line under it).
    Each entry is {species, used, offcut} as fractions of the
    original raw board length. Used is cumulative length already
    cut from that board (including kerfs, negligible); offcut is the
    material remaining after that row, which may be used in the next row.
    """
    bars = []
    for cc in data["crosscuts"]:
        if cc.state in ("spare", "whole"):
            continue
        remaining = cc.length
        for idx, bl in enumerate(cc.blanks):
            remaining_after = remaining - bl.length - data["miter_kerf"]
            # Shave board, last row: no separate offcut, so the bar
            # is full green with no red over-cut segment.
            if cc.shave and idx == len(cc.blanks) - 1:
                remaining_after = 0
            used = (cc.length - remaining_after) / cc.length if cc.length else 0
            offcut = remaining_after / cc.length if cc.length else 0
            bars.append({"species": cc.species, "used": used, "offcut": offcut})
            remaining = remaining_after
    return bars


def build_md(project, cut_spec, tool_limits, out_dir: str,
             design_name: str, inventory_name: str, variant: str) -> str:
    """Write plan-checklist.md + images/ into out_dir. Returns the Md path."""
    data = build_data(project, cut_spec, tool_limits)
    images_dir = os.path.join(out_dir, "images")
    os.makedirs(images_dir, exist_ok=True)
    # Clear stale images (e.g. removed crosscut diagrams from an earlier run).
    for _f in os.listdir(images_dir):
        if _f.endswith(".png"):
            os.remove(os.path.join(images_dir, _f))
    # Diagrams: end-grain rip diagrams (Phase 2) only. Strip maps
    # above the Phase 4 crosscut tables are removed from the PDF.
    endgrain_files = {}
    for b in data["boards"]:
        r = data["rips"][b["id"]]
        png = _render_endgrain_png(project, cut_spec, b, r,
                                   data["saw_kerf"], data["plane_loss"])
        name = f"endgrain-{b['id']}-{hashlib.md5(png).hexdigest()[:12]}.png"
        with open(os.path.join(out_dir, "images", name), "wb") as f:
            f.write(png)
        endgrain_files[b["id"]] = name

    lines = []
    lines.append(f"# {project.get('name', design_name)} — Plan Checklist ({variant}, {inventory_name})")
    lines.append("")
    # Finished-board indicator before Phase 1: the same diagram as at
    # the top of the plan, rendered small so it identifies the pattern
    # without taking main focus.
    from .render import render_finished_board
    _fin_png = render_finished_board(project, scale=5.0)
    _fin_name = f"finished-board-{hashlib.md5(_fin_png).hexdigest()[:12]}.png"
    with open(os.path.join(out_dir, "images", _fin_name), "wb") as _f:
        _f.write(_fin_png)
    lines.append(f"![Finished board](images/{_fin_name})")
    lines.append("")
    # Buy Wood is Phase 1 when present; later phases shift by one.
    # When no ghost boards exist, this phase is omitted entirely and
    # the numbering below is unchanged.
    _buy_rows = _buy_board_rows(project, data)
    _has_buy = bool(_buy_rows)
    _p_cross = 2 if _has_buy else 1
    _p_rip = 3 if _has_buy else 2
    _p_plane = 4 if _has_buy else 3
    _p_crosscomp = 5 if _has_buy else 4
    if _has_buy:
        lines.append("## Phase 1 — Buy Wood")
        lines.append("")
        lines.append("**⚠️ Before getting started you should buy wood.**")
        lines.append("")
        lines.append("| [ ] | Board | Species | Length | Width | Thickness | Yields |")
        lines.append("| --- | --- | --- | --- | --- | --- | --- |")
        for _br in _buy_rows:
            _th = _fmt(_br["thickness"]) if _br["thickness"] is not None else "—"
            lines.append(f"| [ ] | {_br['id']} | {_br['species']} | {_fmt(_br['length'])} | {_fmt(_br['width'])} | {_th} | {_br['yields']} |")
        lines.append("")
    # Initial crosscuts — compact crosscut diagram, then the table.
    _cross_overflow = any(cc.leftover < 0 or cc.shave for cc in data["crosscuts"])
    lines.append(f"## Phase {_p_cross} — Initial crosscuts" + (" ⚠️" if _cross_overflow else ""))
    lines.append("")
    from .render import render_crosscut_compact
    _cc_png = render_crosscut_compact(project, cut_spec, tool_limits)
    _cc_name = f"crosscut-compact-{hashlib.md5(_cc_png).hexdigest()[:12]}.png"
    with open(os.path.join(out_dir, "images", _cc_name), "wb") as _f:
        _f.write(_cc_png)
    lines.append(f"![Crosscut Diagram](images/{_cc_name})")
    lines.append("")
    lines.append("| [ ] | Raw board | Species | Blank | Length | Off Cut |")
    lines.append("| --- | --- | --- | --- | --- | --- |")
    for cc in data["crosscuts"]:
        if cc.state in ("spare", "whole"):
            # Whole boards are not crosscut at all: they drop out of
            # this table and get a line under it instead.
            continue
        # Length is the blank length only. Off Cut is the material
        # remaining after that cut — the previous row's off cut is
        # what the next row starts from, so a return row gets a
        # return icon and no start length. On the last row for a
        # board, Off Cut is the final offcut; 0″ there gets a ⚠️,
        # like the Phase 3/4 Off Cut cells.
        used = 0
        for idx, bl in enumerate(cc.blanks):
            used += bl.length
            # Material left after this blank, before any final kerf:
            # blanks so far + kerfs between them. A final kerf is
            # only counted if a leftover piece remains (exact fit
            # is 0″, not −⅛″, matching the plan's leftover rule).
            intermediate = cc.length - used - idx * data["miter_kerf"]
            # Shave board, last row: the raw margin is less than one
            # kerf, so there is no separate offcut piece — show 0″,
            # not a negative number.
            if cc.shave and idx == len(cc.blanks) - 1:
                offcut = 0
            else:
                offcut = (intermediate - data["miter_kerf"]
                          if intermediate > 0 else intermediate)
            raw_cell = (f"{cc.source_id} ({_fmt(cc.length)})" if idx == 0
                        else f"{cc.source_id} ↩")
            lines.append(f"| [ ] | {raw_cell} | {cc.species} | {bl.blank_id} | {_fmt(bl.length)} | {_offcut_fmt(offcut)} |")
    lines.append("")
    wholes = [cc for cc in data["crosscuts"] if cc.state == "whole"]
    if wholes:
        lines.append(f"Boards to be stripped in their entirety, no Phase {_p_cross} crosscut: " + ", ".join(
            f"{cc.source_id} ({cc.species}, {_fmt(cc.length)})" for cc in wholes) + ".")
    spares = [cc for cc in data["crosscuts"] if cc.state == "spare"]
    if spares:
        lines.append("Spare — do not cut: " + ", ".join(
            f"{cc.source_id} ({cc.species}, {_fmt(cc.length)})" for cc in spares) + ".")
    # Crosscut overflow, in this phase, not in a top banner: a board
    # whose blanks demand more length than the raw board has.
    for cc in data["crosscuts"]:
        if cc.leftover < 0:
            lines.append(f"**⚠️ ERROR — Crosscut overflow: Board {cc.source_id} is over-cut by {_fmt(-cc.leftover)}: its blanks demand more length than the raw board has.**")
    # Crosscut shave, in this phase: the crosscut results in a
    # non-positive offcut whose absolute value is less than one kerf,
    # so the trim cut shaves the end of the board and leaves no
    # separate offcut. Shown as 0″ in the table.
    for cc in data["crosscuts"]:
        if cc.shave:
            lines.append(f"**⚠️ WARNING — Board {cc.source_id}'s cut is close to the end of the board, so the saw blade will be shaving off the end with no off cut.**")
    lines.append("")

    # Rips — straight to the first board section, no preamble.
    lines.append(f"## Phase {_p_rip} — Rips")
    lines.append("")
    for p2, b in enumerate(data["boards"], start=1):
        r = data["rips"][b["id"]]
        lines.append(f"### Phase {_p_rip}.{p2} — {b['id']} — {r.species}" + (" ⚠️" if r.margin < 0 else ""))
        lines.append("")
        if b["id"] in endgrain_files:
            lines.append(f"![End grain — {b['id']}](images/{endgrain_files[b['id']]})")
            lines.append("")
        lines.append("| [ ] | Rip | Rip size | Final width | Length | Pieces planned | Margin |")
        lines.append("| --- | --- | --- | --- | --- | --- | --- |")
        # Running margin, row by row (see _rip_margins). The last
        # row's margin is the board's total margin; a row where it
        # first goes negative (and every row after) gets a ⚠️ in
        # this right-side column.
        _margins = _rip_margins(r.source_width, b["strips"],
                                data["plane_loss"], data["saw_kerf"])
        for i, strip in enumerate(b["strips"]):
            w = measure_to_sixteenths(strip["width"])
            pieces = _strip_pieces(strip)
            # Rip tables do not flag gangs in general: gang info is
            # useless at ripping time; it belongs in Phase 3. The one
            # exception is a crosscut-first strip, which must be
            # crosscut before it can be planed, so that row gets an
            # asterisk instead of the old "crosscut first" text.
            # Pieces planned are grouped by length, e.g. 15⅞″x3.
            planned = _grouped_pieces(pieces)
            width_cell = _fmt_dec(w) + ("*" if w in data["crosscut_first_widths"] else "")
            _running = _margins[i]
            _margin_cell = _running_margin_cell(
                _running, data["saw_kerf"], i == len(b["strips"]) - 1)
            lines.append(f"| [ ] | {i + 1} | {_fmt_dec(_rip_size(w, data['plane_loss']))} | {width_cell} | {_fmt(measure_to_sixteenths(b['length']))} | {planned} | {_margin_cell} |")
        lines.append("")
        lines.append(f"Board width {_fmt(r.source_width)} = used {_fmt(r.used)} + "
                     f"loss {_fmt(r.loss)} + margin {_margin_fmt(r.margin, data['saw_kerf'])}.")
        # Over-rip and small margin, in this board's rip section, not
        # in a top banner. Ghost boards are bought to size, so a tight
        # margin on one is expected, not a small-margin warning.
        # A small negative total margin is a last-rip shave warning,
        # not an over-rip error; a larger negative total is an error.
        from .derive import rip_margin_class as _rip_class
        if _rip_class(r.margin, data["saw_kerf"]) == "shave":
            lines.append(f"**⚠️ WARNING — Board {b['id']}'s last rip is close to the edge of the board, so the saw blade will be shaving off the edge with no margin.**")
        elif r.margin < 0:
            lines.append(f"**⚠️ ERROR — Over-rip: Cut list for board {b['id']} over-rips by {_fmt(-r.margin)}: the strips are wider than the board.**")
        elif not r.buy_required and 0 <= r.margin < 4:
            lines.append(f"**⚠️ WARNING — Small margin: Board {b['id']} leaves only {_fmt(r.margin)} margin (< ¼″) — too tight; prone to under-supplying strips if the board runs narrow.**")
        lines.append("")
        kids = data["children"].get(b["id"], [])
        if kids:
            lines.append(f"Margin crosscuts — {b['id']} margin slab, length {_fmt(measure_to_sixteenths(b['length']))}:")
            lines.append("")
            lines.append("| [ ] | Child blank | Length |")
            lines.append("| --- | --- | --- |")
            for k in kids:
                lines.append(f"| [ ] | {k['id']} | {_fmt(measure_to_sixteenths(k['length']))} |")
            lines.append("")
            lines.append("Rip the child boards next, in the order above, before the next parent board.")
            lines.append("")

    # Plane by width — straight to the first gang section, no preamble.
    # A gang is every strip of one finished width. Crosscut-first gangs
    # are crosscut here, before planing, and are not repeated in the
    # crosscut-components phase.
    lines.append(f"## Phase {_p_plane} — Plane by width")
    lines.append("")
    for p3, (w, strips) in enumerate(data["by_width"].items(), start=1):
        gang = data["gangs_by_width"].get(w)
        crosscut_first = bool(gang and gang.crosscut_first)
        # Planing units: strips, except crosscut-first gangs, where each
        # component counts separately because planing is on components.
        # Counted per species, first-appearance order, not listed per strip.
        counts: "OrderedDict" = OrderedDict()
        for s in strips:
            n = len(s["pieces"]) if crosscut_first else 1
            counts[s["species"]] = counts.get(s["species"], 0) + n
        total_units = sum(counts.values())
        unit = "component" if crosscut_first else "strip"
        unit_pl = unit + "s"
        heading = f"### Phase {_p_plane}.{p3} — Gang — Plane to {_fmt(w)} — planer setting {_fmt(w)} ({total_units} {unit_pl})"
        if gang and gang.requires_gang:
            heading += " — requires a gang"
        lines.append(heading)
        lines.append("")
        if gang and gang.insufficient:
            lines.append(f"**WARNING — There aren't enough {_fmt(w)} strips to gang together to safely pass through the planer without tipping over. You might need sacrificial wood to tape onto it in order to prevent movement.**")
            lines.append("")
        elif gang and gang.requires_gang and gang.crosscut_first:
            lines.append(f"Requires a gang — strip gang total {_fmt(gang.strip_total_thickness)} < {_fmt(w)}; crosscut first, then gang components (total {_fmt(gang.component_total_thickness)} ≥ {_fmt(w)}).")
            lines.append("")
        elif gang and gang.requires_gang:
            lines.append(f"Requires a gang — tape strips together; total thickness {_fmt(gang.strip_total_thickness)} ≥ {_fmt(w)}.")
            lines.append("")
        if crosscut_first:
            lines.append("Crosscut first:")
            lines.append("")
            lines.append("| Cuts | Board | Strip | Species | Pieces | Off Cut |")
            lines.append("| --- | --- | --- | --- | --- | --- |")
            for s in strips:
                boxes = " ".join("[ ]" for _ in s["pieces"])
                plist = _grouped_pieces(s["pieces"])
                tail_plan = _tail(s["length"], s["pieces"], data["miter_kerf"])
                off_cut = 0 if tail_plan == 0 else tail_plan - data["miter_kerf"]
                lines.append(f"| {boxes} | {s['board']} | {s['strip_no']} | {s['species']} | {plist} | {_offcut_fmt(off_cut)} |")
            lines.append("")
            lines.append("Plane as gang:")
            lines.append("")
        lines.append("| [ ] | Species | Count |")
        lines.append("| --- | --- | --- |")
        for species, count in counts.items():
            lines.append(f"| [ ] | {species} | {count} {unit_pl} |")
        lines.append("")

    # Crosscut components — grouping first, then board tables.
    # Crosscut-first gangs are not repeated here: they were crosscut
    # in the plane-by-width phase, before planing. A short note names
    # them, not the cuts.
    lines.append(f"## Phase {_p_crosscomp} — Crosscut components")
    lines.append("")
    from collections import Counter as _Counter
    length_counts: "OrderedDict" = OrderedDict()
    length_widths: Dict[int, _Counter] = {}
    for b in data["boards"]:
        r = data["rips"][b["id"]]
        for i, strip in enumerate(b["strips"]):
            w = measure_to_sixteenths(strip["width"])
            if w in data["crosscut_first_widths"]:
                continue
            for p in _strip_pieces(strip):
                length_counts[p] = length_counts.get(p, 0) + 1
                length_widths.setdefault(p, _Counter())[(r.species, w)] += 1
    lines.append(f"### Phase {_p_crosscomp}.1 — Crosscut grouping — by length")
    lines.append("")
    lines.append("| Length | Species | Final width | Pieces |")
    lines.append("| --- | --- | --- | --- |")
    for length in sorted(length_counts):
        for (species, w), n in sorted(
                length_widths[length].items(), key=lambda kv: (kv[0][0], -kv[0][1])):
            lines.append(f"| {_fmt(length)} | {species} | {_fmt_dec(w)} | {n} |")
    lines.append("")
    lines.append("Totals: " + ", ".join(
        f"{_fmt(length)} ×{count}" for length, count in sorted(length_counts.items())) + ".")
    lines.append("")
    total_pieces = 0
    phase3_pieces = 0
    for p4, b in enumerate(data["boards"], start=2):
        r = data["rips"][b["id"]]
        lines.append(f"### Phase {_p_crosscomp}.{p4} — {b['id']} — {r.species}")
        lines.append("")
        shown = []
        already = []
        for i, strip in enumerate(b["strips"]):
            w = measure_to_sixteenths(strip["width"])
            pieces = _strip_pieces(strip)
            if w in data["crosscut_first_widths"]:
                already.append((i + 1, w))
                phase3_pieces += len(pieces)
                continue
            shown.append((i, strip, w, pieces))
        if shown:
            lines.append("| Cuts | Strip | Species | Final width | Pieces | Off Cut |")
            lines.append("| --- | --- | --- | --- | --- | --- |")
            for i, strip, w, pieces in shown:
                total_pieces += len(pieces)
                boxes = " ".join("[ ]" for _ in pieces)
                plist = _grouped_pieces(pieces)
                tail_plan = _tail(measure_to_sixteenths(b["length"]), pieces, data["miter_kerf"])
                off_cut = 0 if tail_plan == 0 else tail_plan - data["miter_kerf"]
                # Crosscut rows do not flag gangs: a gang requirement is
                # for planing only, in Phase 3, not for crosscutting.
                # Final width carries a 2-decimal caliper measurement,
                # e.g. 1½″ (1.50″), like the rip tables.
                lines.append(f"| {boxes} | {i + 1} | {r.species} | {_fmt_dec(w)} | {plist} | {_offcut_fmt(off_cut)} |")
            lines.append("")
        for strip_no, w in already:
            lines.append(f"Strip {strip_no} ({_fmt(w)}) already crosscut in Phase {_p_plane} gang, not repeated here.")
        if already:
            lines.append("")
    overall_pieces = total_pieces + phase3_pieces
    total_line = (f"Total: {sum(len(b['strips']) for b in data['boards'])} strips, "
                  f"{overall_pieces} component pieces.")
    if phase3_pieces:
        total_line += f" ({phase3_pieces} pieces crosscut in Phase {_p_plane} gang, not repeated in Phase {_p_crosscomp}.)"
    lines.append(total_line)
    lines.append("")

    # Phases after the cuts: panel glue-ups, slices, slice rips (skipped
    # when no panel rips slices, with later phases renumbered down),
    # column glue-ups, final glue-up, finishing. No prose in these
    # phases: headings, subtitles, tables, and diagrams only.
    from collections import Counter as _Counter2
    _next = _p_crosscomp + 1
    _summaries = {s.id: s for s in derive.panel_summaries(project, tool_limits)}
    _spec_counts = _Counter2(s.panel_id for s in derive.panel_specs(project, cut_spec, tool_limits))
    # Panel glue-ups.
    _panel_phase = _next; _next += 1
    lines.append(f"## Phase {_panel_phase} — Panel glue-ups")
    lines.append("")
    for _i, _panel in enumerate(project["panels"], start=1):
        _pid = _panel["id"]
        _count = _spec_counts.get(_pid, 1)
        _summ = _summaries[_pid]
        _heading = f"### Phase {_panel_phase}.{_i} — Panel {_pid}"
        if _count > 1:
            _heading += f" x{_count}"
        lines.append(_heading)
        lines.append("")
        _width = sum(c[2] for c in _summ.fullest_components)
        lines.append(f"{_fmt(_summ.length)} x {_fmt(_width)} x {_fmt(_summ.height)} - {len(_summ.fullest_components)} components - x{_count} duplicates")
        lines.append("")
        _boxes = " ".join("[ ]" for _ in range(_count))
        lines.append("| Panels | Order | Species | Width | Component |")
        lines.append("| --- | --- | --- | --- | --- |")
        for _o, (_cid, _species, _w) in enumerate(_summ.fullest_components, start=1):
            lines.append(f"| {_boxes} | {_o} | {_species} | {_fmt_dec(_w)} | {_cid} |")
        lines.append("")
    # Slices.
    _slice_phase = _next; _next += 1
    lines.append(f"## Phase {_slice_phase} — Slices")
    lines.append("")
    _slice_depth = measure_to_sixteenths(project["sliceDepth"])
    _finished_th = measure_to_sixteenths(project["finishedThickness"])
    _initial_th = _slice_depth + (_slice_depth - _finished_th)
    lines.append(f"{_fmt(_initial_th)} thick ({_fmt(_slice_depth)} after flattening)")
    lines.append("")
    _fulfil = derive.slice_fulfillment(project, cut_spec, tool_limits)
    _per_panel = {}
    for _pid, _summ in _summaries.items():
        for _prof, _n in _summ.profiles:
            _sid = f"{_pid}-{_prof}" if _prof else _pid
            _per_panel[_sid] = _n
    lines.append("| [ ] | Slice | From panel | Slice Count |")
    lines.append("| --- | --- | --- | --- |")
    for _row in _fulfil:
        _sid = _row.slice_id
        _from = _sid.split("-")[0]
        _per = _per_panel.get(_sid, '')
        # Multiplier that yields the supplied count: panel count
        # times the slice-rip multiplier (H: 1 panel x 2 rips = 2).
        _mult = (_row.supplied // _per) if _per else _row.supplied
        lines.append(f"| [ ] | {_sid} | {_from} | {_per} x {_mult} = {_row.supplied} |")
    lines.append("")
    # Slice rips: only panels that rip their slices into strips. Skipped
    # entirely when none do, so later phases keep sequential numbers.
    _rip_panels = [pn for pn in project["panels"] if "sliceStrips" in pn]
    if _rip_panels:
        _rip_phase = _next; _next += 1
        lines.append(f"## Phase {_rip_phase} — Slice rips")
        lines.append("")
        lines.append("| [ ] | Slice | Rip to | Count |")
        lines.append("| --- | --- | --- | --- | --- |")
        for _row in _fulfil:
            _from = _row.slice_id.split("-")[0]
            _pn = next((pn for pn in _rip_panels if pn["id"] == _from), None)
            if _pn is None:
                continue
            _rip_to = measure_to_sixteenths(_pn["sliceStrips"]["width"])
            lines.append(f"| [ ] | {_row.slice_id} | {_fmt(_rip_to)} | {_row.supplied} |")
        lines.append("")
    # Column glue-ups: one diagram of all columns together, not a
    # diagram per column. The final columns diagram satisfies both
    # needs at once, so it lives here and is not repeated below.
    # Columns are numbered, not left/right.
    from .render import render_columns_diagram, _column_cells
    _grid = project.get("sliceGrid", [])
    _ncols = len(_grid[0]) if _grid else 0
    _batch = project.get("batch", 1)
    if _ncols:
        _col_phase = _next; _next += 1
        lines.append(f"## Phase {_col_phase} — Column Glue Ups")
        lines.append("")
        _png = render_columns_diagram(project)
        _name = f"columns-{hashlib.md5(_png).hexdigest()[:12]}.png"
        with open(os.path.join(out_dir, "images", _name), "wb") as _f:
            _f.write(_png)
        lines.append(f"![Columns](images/{_name})")
        lines.append("")
        lines.append("| Board | Column | Slices |")
        lines.append("| --- | --- | --- |")
        for _c in range(1, _ncols + 1):
            _boxes = " ".join("[ ]" for _ in range(_batch))
            _slices = " ".join(
                f"{_i:02d} [ ] {_sid}*" if _flip == "H" else f"{_i:02d} [ ] {_sid}"
                for _i, (_sid, _flip) in enumerate(_column_cells(project, _c - 1), start=1))
            lines.append(f"| {_boxes} | Column {_c} | {_slices} |")
        lines.append("")
        # Final glue-up: diagram already shown above, in Column
        # Glue Ups, so it is not repeated here — only its table.
        _final_phase = _next; _next += 1
        lines.append(f"## Phase {_final_phase} — Final Glue Up")
        lines.append("")
        from .geometry import resolve_slice as _resolve_slice, slice_length as _slice_length
        _col_widths = []
        for _c in range(_ncols):
            _col_widths.append(max(_slice_length(_resolve_slice(project, _grid[r][_c]["sliceId"])) for r in range(len(_grid))))
        _grid_width = sum(_col_widths)
        _grid_height = sum(_resolve_slice(project, _grid[r][0]["sliceId"]).height for r in range(len(_grid)))
        lines.append("| Board | Columns | Size |")
        lines.append("| --- | --- | --- |")
        _cols_cell = " + ".join(f"Column {_c}" for _c in range(1, _ncols + 1))
        for _b in range(1, _batch + 1):
            lines.append(f"| [ ] | {_cols_cell} | {_fmt(_grid_width)} × {_fmt(_grid_height)} × {_fmt(_slice_depth)} |")
        lines.append("")
    # Finishing: one row per board.
    _fin_phase = _next; _next += 1
    lines.append(f"## Phase {_fin_phase} — Finishing")
    lines.append("")
    if _ncols:
        _trim_w, _trim_h = _finishing_size(project, _grid_width, _grid_height, _slice_depth, _finished_th)
    else:
        _trim_w = _trim_h = _finished_th
    # Final dimensions once, in the subtitle — not repeated per row,
    # so the Board cell stays a bare checkbox, checked last per board.
    lines.append(f"Final dimensions: {_fmt(_trim_w)} × {_fmt(_trim_h)} × {_fmt(_finished_th)}")
    if project.get("edgeTrims"):
        lines.append(f"Edge trims: left {_fmt(_edge_trim(project, 'left'))}, right {_fmt(_edge_trim(project, 'right'))}, top {_fmt(_edge_trim(project, 'top'))}, bottom {_fmt(_edge_trim(project, 'bottom'))}")
    lines.append("")
    _grits = " ".join(f"[ ] {g}" for g in (80, 120, 220, 320))
    lines.append("| Board | Width trim | Length trim | Flatten | Sanding (grits) | Oil | Wax |")
    lines.append("| --- | --- | --- | --- | --- | --- | --- |")
    for _b in range(1, _batch + 1):
        lines.append(f"| [ ] | {_fmt(_grid_width)} → {_fmt(_trim_w)} | {_fmt(_grid_height)} → {_fmt(_trim_h)} | {_fmt(_slice_depth)} → {_fmt(_finished_th)} | {_grits} | [ ] | [ ] |")
    lines.append("")
    md_path = os.path.join(out_dir, "plan-checklist.md")
    with open(md_path, "w") as f:
        f.write("\n".join(lines))
    return md_path



def _image_display_size(iw: int, ih: int, col_w: float, col_h: float):
    """Display size for a checklist image, in points.

    True size first: 1 pixel = 1 point (72 dpi), so a small diagram
    prints small, not stretched to full column width. Only scale down
    when true size would overflow the column width or the frame height
    (e.g. a 1200 px end-grain diagram, true size 16.7 in wide).
    """
    w, h = float(iw), float(ih)
    if w > col_w:
        h = h * col_w / w
        w = col_w
    if h > col_h:
        w = w * col_h / h
        h = col_h
    return w, h


def build_pdf_from_md(md_path: str, out_path: str, phase1_bars=None) -> str:
    """Render the checklist Md to a portrait, 1-column PDF.

    One column, so Scott can print 2 pages per sheet himself if he
    wants the old 2-column density back. Diagrams render at full
    column width (7.5 in), capped to frame height so a tall strip
    diagram still fits on one page; the tables below each diagram
    carry the exact sizes. Tables may split across pages; headers
    repeat. Each page gets a "Page N" footer, centered below the frame.
    When phase1_bars is given, Phase 1 Length cells also get a 3 pt
    progress bar, fixed at Length-column width: left segment green
    for cumulative used length, right segment reddish for the
    offcut remaining after that row. Species cells in tables get a
    small colored box left of the species name, species color fill
    with a dark gray border.
    """
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import LETTER
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.lib.units import inch
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    from reportlab.platypus import (
        BaseDocTemplate, Flowable, Frame, Image as RLImage, PageTemplate,
        Paragraph, Spacer, Table, TableStyle,
    )

    class CheckBox(Flowable):
        """Drawn empty square for printing, 12 pt, 1.2 pt stroke."""

        def __init__(self, size: int = 12):
            Flowable.__init__(self)
            self.size = size
            self.width = size
            self.height = size

        def wrap(self, aW, aH):
            return (self.size, self.size)

        def draw(self):
            self.canv.setStrokeColorRGB(0, 0, 0)
            self.canv.setLineWidth(1.2)
            self.canv.rect(0, 0, self.size, self.size, stroke=1, fill=0)

    class ProgressBar(Flowable):
        """Thin two-segment bar: green left, gray offcut right.

        Left is always green, for contrast against the offcut,
        regardless of species. Species identity moved to the small
        colored box left of the species name in Species columns.
        A positive offcut is normal leftover, so it is gray, not red.
        For an overflow the caller passes the board-fit fraction as
        used_frac and red as offcut_color, so the red segment is the
        over-cut portion.
        """

        def __init__(self, width: float, used_frac: float,
                     left_color: str = "#28a745", offcut_color: str = "#d0d0d0"):
            Flowable.__init__(self)
            self.bar_width = max(0.0, width)
            self.bar_height = 3
            self.width = self.bar_width
            self.height = self.bar_height
            used = min(1.0, max(0.0, used_frac))
            self.used_w = self.bar_width * used
            self.offcut_w = self.bar_width - self.used_w
            self.left_color = left_color
            self.offcut_color = offcut_color

        def wrap(self, aW, aH):
            return (self.bar_width, self.bar_height)

        def draw(self):
            self.canv.setFillColor(colors.HexColor(self.left_color))
            self.canv.rect(0, 0, self.used_w, self.bar_height, stroke=0, fill=1)
            self.canv.setFillColor(colors.HexColor(self.offcut_color))
            self.canv.rect(self.used_w, 0, self.offcut_w, self.bar_height,
                           stroke=0, fill=1)
            self.canv.setStrokeColorRGB(0.2, 0.2, 0.2)
            self.canv.setLineWidth(0.4)
            self.canv.rect(0, 0, self.bar_width, self.bar_height, stroke=1, fill=0)

    class Swatch(Flowable):
        """Small species-color box with a dark gray border, 10 pt."""

        def __init__(self, color: str, size: int = 10):
            Flowable.__init__(self)
            self.size = size
            self.width = size
            self.height = size
            self.color = color

        def wrap(self, aW, aH):
            return (self.size, self.size)

        def draw(self):
            self.canv.setFillColor(colors.HexColor(self.color))
            self.canv.setStrokeColor(colors.HexColor("#333333"))
            self.canv.setLineWidth(0.8)
            self.canv.rect(0, 0, self.size, self.size, stroke=1, fill=1)
    from reportlab.lib.enums import TA_LEFT
    from PIL import Image as PILImage
    import re

    # Reuse pdf.py's font registration + Md parsing, without importing its
    # single-column builder.
    import sys
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from pdf import _find_font, md_inline_to_xml, parse_md

    for family, fname in (
        ("DejaVuSans", "DejaVuSans.ttf"),
        ("DejaVuSans-Bold", "DejaVuSans-Bold.ttf"),
        ("DejaVuSansMono", "DejaVuSansMono.ttf"),
        ("DejaVuSans-Oblique", "DejaVuSans-Oblique.ttf"),
    ):
        path = _find_font(fname)
        if path:
            pdfmetrics.registerFont(TTFont(family, path))
    if "DejaVuSans-Bold" in pdfmetrics.getRegisteredFontNames():
        italic = ("DejaVuSans-Oblique"
                  if "DejaVuSans-Oblique" in pdfmetrics.getRegisteredFontNames()
                  else "DejaVuSans")
        pdfmetrics.registerFontFamily(
            "DejaVuSans", normal="DejaVuSans", bold="DejaVuSans-Bold",
            italic=italic, boldItalic="DejaVuSans-Bold",
        )
    base_font = "DejaVuSans" if "DejaVuSans" in pdfmetrics.getRegisteredFontNames() else "Helvetica"
    bold_font = base_font + "-Bold" if base_font != "Helvetica" else "Helvetica-Bold"

    page_w, page_h = LETTER
    margin = 0.5 * inch
    col_w = page_w - 2 * margin
    col_h = page_h - 2 * margin

    styles = {
        "h1": ParagraphStyle("h1", fontName=bold_font, fontSize=16, leading=19, spaceAfter=6),
        "h2": ParagraphStyle("h2", fontName=bold_font, fontSize=12, leading=14, spaceBefore=10, spaceAfter=4, keepWithNext=1),
        "h3": ParagraphStyle("h3", fontName=bold_font, fontSize=10, leading=12, spaceBefore=8, spaceAfter=3, keepWithNext=1),
        "p": ParagraphStyle("p", fontName=base_font, fontSize=8.5, leading=11, spaceAfter=4),
        "cell": ParagraphStyle("cell", fontName=base_font, fontSize=12.6, leading=15.96),
        "cellhead": ParagraphStyle("cellhead", fontName=bold_font, fontSize=12.6, leading=15.96),
    }

    md_dir = os.path.dirname(os.path.abspath(md_path))
    story = []
    _parsed = list(parse_md(md_path))
    _i = 0
    while _i < len(_parsed):
        kind, value = _parsed[_i]
        _i += 1
        if kind == "h1":
            story.append(Paragraph(md_inline_to_xml(value), styles["h1"]))
        elif kind == "h2":
            story.append(Paragraph(md_inline_to_xml(value), styles["h2"]))
        elif kind == "h3":
            story.append(Paragraph(md_inline_to_xml(value), styles["h3"]))
        elif kind == "p":
            story.append(Paragraph(md_inline_to_xml(value), styles["p"]))
        elif kind == "image":
            alt, rel = value
            img_path = os.path.join(md_dir, rel)
            if not os.path.exists(img_path):
                story.append(Paragraph(f"[missing image: {alt}]", styles["p"]))
                continue
            with PILImage.open(img_path) as im:
                iw, ih = im.size
            w, h = _image_display_size(iw, ih, col_w, col_h)
            # Float: if the next flowable is also an image and both
            # true-size widths fit side by side in the column, put
            # them in one row instead of stacking them full-width.
            # Each image keeps its true size; only the row is shared.
            _pair = None
            if _i < len(_parsed) and _parsed[_i][0] == "image":
                _alt2, _rel2 = _parsed[_i][1]
                _path2 = os.path.join(md_dir, _rel2)
                if os.path.exists(_path2):
                    with PILImage.open(_path2) as _im2:
                        _iw2, _ih2 = _im2.size
                    _w2, _h2 = _image_display_size(_iw2, _ih2, col_w, col_h)
                    if w + 12 + _w2 <= col_w:
                        _pair = (_path2, _w2, _h2)
                        _i += 1
            if _pair is not None:
                _path2, _w2, _h2 = _pair
                _row = Table(
                    [[RLImage(img_path, width=w, height=h),
                      RLImage(_path2, width=_w2, height=_h2)]],
                    colWidths=[w, _w2])
                _row.setStyle(TableStyle([
                    ("LEFTPADDING", (0, 0), (-1, -1), 0),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 6),
                    ("TOPPADDING", (0, 0), (-1, -1), 0),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ]))
                story.append(_row)
            else:
                story.append(RLImage(img_path, width=w, height=h))
            story.append(Spacer(1, 4))
        elif kind == "table":
            rows = value
            ncols = max(len(r) for r in rows)
            rows = [r + [""] * (ncols - len(r)) for r in rows]
            # Widths: a minimum per column first, so a long cell does not
            # squeeze a short header to wrapping ("Len gth"), then the
            # remaining width distributed by longest cell length.
            maxlen = [max(len(r[c]) + (2 if r[c].strip() in DEFAULT_COLORS else 0)
                          for r in rows) for c in range(ncols)]
            total = sum(maxlen) or 1
            is_checkbox_col0 = bool(rows and rows[0] and rows[0][0].strip() == "[ ]")
            mins = [
                (0.45 * inch if (c == 0 and is_checkbox_col0) else 0.85 * inch)
                for c in range(ncols)
            ]
            if sum(mins) >= col_w:
                widths = [m * col_w / sum(mins) for m in mins]
            else:
                remaining = col_w - sum(mins)
                widths = [mins[c] + remaining * (maxlen[c] / total) for c in range(ncols)]
            is_phase1 = (len(rows[0]) >= 6 and rows[0][1].strip() == "Raw board"
                         and rows[0][4].strip() == "Length"
                         and rows[0][5].strip() == "Off Cut")
            data = []
            for ri, row in enumerate(rows):
                out_row = []
                for ci, c in enumerate(row):
                    cs = c.strip()
                    style = styles["cellhead"] if ri == 0 else styles["cell"]
                    if ri == 0 and cs == "[ ]":
                        # Checkbox column header stays empty, no "Done" label.
                        out_row.append(Paragraph("", styles["cellhead"]))
                    elif cs == "[ ]":
                        out_row.append(CheckBox())
                    elif "[ ]" in cs and cs.strip() != "[ ]":
                        # Mixed cell, e.g. "[ ] 14″ × 16″" or
                        # "[ ] 80 [ ] 120": drawn squares interleaved
                        # with text, not literal "[ ]" text.
                        if re.match(r"^\d+ \[ \]", cs.strip()):
                            # Numbered checkboxes, e.g. "1 [ ] S-L
                            # 2 [ ] ML": number left of its checkbox,
                            # code after it. Parse into items first,
                            # so a wrapped row never splits a number
                            # from its checkbox.
                            _items = re.findall(
                                r"(\d+) \[ \] ([A-Za-z0-9\-*]+)", cs)
                            _rows = []
                            for _k in range(0, len(_items), 6):
                                _chunk = _items[_k:_k + 6]
                                _rc, _rw = [], []
                                for _num, _code in _chunk:
                                    from reportlab.lib.styles import ParagraphStyle as _PS2
                                    _ns = _PS2("numsmall", parent=style, fontSize=10, leading=12)
                                    _cs2 = _PS2("codesmall", parent=style, fontSize=10, leading=12)
                                    _rc.append(Paragraph(_num, _ns))
                                    _rw.append(max(14, len(_num) * 7 + 4))
                                    _rc.append(CheckBox(size=10))
                                    _rw.append(12)
                                    _rc.append(Paragraph(md_inline_to_xml(_code), _cs2))
                                    _rw.append(max(14, len(_code) * 7 + 4))
                                _rows.append((_rc, _rw))
                            _maxlen = max(len(_rc) for _rc, _ in _rows)
                            _inner_data = [_rc + [""] * (_maxlen - len(_rc)) for _rc, _ in _rows]
                            _inner_widths = []
                            for _ci2 in range(_maxlen):
                                _inner_widths.append(max(
                                    _rw[_ci2] if _ci2 < len(_rw) else 0
                                    for _, _rw in _rows))
                            _avail2 = widths[ci] - 6
                            if sum(_inner_widths) > _avail2:
                                _first2 = _rows[0][0]
                                _cb2 = sum(w for _cell2, w in zip(_first2, _inner_widths)
                                           if isinstance(_cell2, CheckBox))
                                _txt2 = sum(_inner_widths) - _cb2
                                if _txt2 > 0 and _avail2 > _cb2:
                                    _scale2 = (_avail2 - _cb2) / _txt2
                                    _inner_widths = [
                                        w if isinstance(_cell2, CheckBox) else w * _scale2
                                        for _cell2, w in zip(_first2, _inner_widths)]
                            inner = Table(_inner_data, colWidths=_inner_widths)
                            inner.setStyle(TableStyle([
                                ("LEFTPADDING", (0, 0), (-1, -1), 1),
                                ("RIGHTPADDING", (0, 0), (-1, -1), 1),
                                ("TOPPADDING", (0, 0), (-1, -1), 0),
                                ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
                                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                                ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                            ]))
                            out_row.append(inner)
                            continue
                        _parts = cs.split("[ ]")
                        _cells = []
                        _widths = []
                        for _j, _seg in enumerate(_parts):
                            if _j > 0:
                                _cells.append(CheckBox(size=10))
                                _widths.append(12)
                            _seg = _seg.strip()
                            if _seg:
                                from reportlab.lib.styles import ParagraphStyle as _PS
                                _small = _PS("mixedsmall", parent=style, fontSize=10, leading=12)
                                _cells.append(Paragraph(md_inline_to_xml(_seg), _small))
                                _widths.append(max(14, len(_seg) * 7 + 4))
                        # Wrap long checkbox runs (e.g. 24 slice
                        # checkboxes) into rows, grouping each
                        # checkbox with its following text as one
                        # item, so a row never splits a checkbox
                        # from its grit/code, and no row exceeds
                        # its outer cell width.
                        _items = []
                        for _cell, _w in zip(_cells, _widths):
                            if isinstance(_cell, CheckBox) or not _items:
                                _items.append([(_cell, _w)])
                            else:
                                _items[-1].append((_cell, _w))
                        _rows = []
                        _row_cells, _row_widths, _row_w = [], [], 0
                        _avail0 = widths[ci] - 6
                        for _item in _items:
                            _iw = sum(w for _, w in _item)
                            if _row_cells and (len([c for c in _row_cells if isinstance(c, CheckBox)]) >= 6
                                               or _row_w + _iw > _avail0):
                                _rows.append((_row_cells, _row_widths))
                                _row_cells, _row_widths, _row_w = [], [], 0
                            for _cell, _w in _item:
                                _row_cells.append(_cell)
                                _row_widths.append(_w)
                            _row_w += _iw
                        if _row_cells:
                            _rows.append((_row_cells, _row_widths))
                        _maxlen = max(len(_rc) for _rc, _ in _rows)
                        _inner_data = []
                        for _rc, _rw in _rows:
                            _inner_data.append(_rc + [""] * (_maxlen - len(_rc)))
                        # Column widths from the widest row per column
                        # position, so no column gets a zero width.
                        _inner_widths = []
                        for _ci in range(_maxlen):
                            _inner_widths.append(max(
                                _rw[_ci] if _ci < len(_rw) else 0
                                for _, _rw in _rows))
                        # Cap the inner table to its outer cell width:
                        # keep checkbox columns at 12 pt, shrink text
                        # columns (they wrap, not clip) so the table
                        # cannot run off the page edge.
                        _avail = widths[ci] - 6
                        if sum(_inner_widths) > _avail:
                            _first = _rows[0][0]
                            _cb = sum(w for _cell, w in zip(_first, _inner_widths)
                                      if isinstance(_cell, CheckBox))
                            _txt = sum(_inner_widths) - _cb
                            if _txt > 0 and _avail > _cb:
                                _scale = (_avail - _cb) / _txt
                                _inner_widths = [
                                    w if isinstance(_cell, CheckBox) else w * _scale
                                    for _cell, w in zip(_first, _inner_widths)]
                        inner = Table(_inner_data, colWidths=_inner_widths)
                        inner.setStyle(TableStyle([
                            ("LEFTPADDING", (0, 0), (-1, -1), 1),
                            ("RIGHTPADDING", (0, 0), (-1, -1), 1),
                            ("TOPPADDING", (0, 0), (-1, -1), 0),
                            ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
                            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                            ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                        ]))
                        out_row.append(inner)
                    else:
                        style = styles["cellhead"] if ri == 0 else styles["cell"]
                        if cs in DEFAULT_COLORS and ri > 0:
                            # Small colored box left of the species name,
                            # species color fill, dark gray border.
                            avail = max(0.0, widths[ci] - 6)
                            swatch_table = Table(
                                [[Swatch(DEFAULT_COLORS[cs]),
                                  Paragraph(md_inline_to_xml(c), style)]],
                                colWidths=[12, max(0.0, avail - 12)])
                            swatch_table.setStyle(TableStyle([
                                ("LEFTPADDING", (0, 0), (0, 0), 0),
                                ("RIGHTPADDING", (0, 0), (0, 0), 4),
                                ("LEFTPADDING", (1, 0), (1, 0), 0),
                                ("RIGHTPADDING", (1, 0), (1, 0), 0),
                                ("TOPPADDING", (0, 0), (-1, -1), 0),
                                ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
                                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                            ]))
                            out_row.append(swatch_table)
                        else:
                            # Warning glyphs already get their yellow
                            # background in md_inline_to_xml, for every
                            # paragraph type, not just table cells.
                            out_row.append(Paragraph(md_inline_to_xml(c), style))
                if is_phase1 and ri > 0 and phase1_bars is not None:
                    bar = phase1_bars[ri - 1] if ri - 1 < len(phase1_bars) else None
                    if bar is not None:
                        # Bar stays under the Length column (index 4),
                        # not under the new Off Cut column (index 5).
                        # Positive offcut is gray leftover. Negative
                        # offcut (overflow) is a red segment at the
                        # right: green is the board-fit fraction
                        # (1 / used), red is the over-cut fraction
                        # (-offcut / used), scaled to the full bar.
                        bar_w = max(0.0, widths[4] - 6)
                        if bar["offcut"] < 0 and bar["used"]:
                            _bar = ProgressBar(bar_w, 1.0 / bar["used"],
                                               offcut_color="#c0392b")
                        else:
                            _bar = ProgressBar(bar_w, bar["used"])
                        out_row[4] = [out_row[4], Spacer(1, 2), _bar]
                data.append(out_row)
            t = Table(data, colWidths=widths, repeatRows=1)
            t.setStyle(TableStyle([
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#e8e8e8")),
                ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#999999")),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("LEFTPADDING", (0, 0), (-1, -1), 3),
                ("RIGHTPADDING", (0, 0), (-1, -1), 3),
                ("TOPPADDING", (0, 0), (-1, -1), 2),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
            ]))
            story.append(t)
            story.append(Spacer(1, 4))

    def footer(canvas, doc):
        canvas.saveState()
        canvas.setFont(base_font, 8)
        canvas.drawCentredString(page_w / 2, 0.3 * inch, f"Page {doc.page}")
        canvas.restoreState()

    doc = BaseDocTemplate(out_path, pagesize=LETTER,
                          leftMargin=margin, rightMargin=margin,
                          topMargin=margin, bottomMargin=margin,
                          title="Plan Checklist")
    # Frame padding must be 0: the default 6 pt padding shrinks
    # paragraphs to col_w - 12 pt while fixed-width tables/images
    # stay col_w wide, so text wrapped 12 pt short of tables/images
    # on the right. With padding 0, tables, images, titles, and body
    # text all share the same 0.5 in left and right margins.
    frame = Frame(margin, margin, col_w, col_h, id="single",
                  leftPadding=0, rightPadding=0, topPadding=0, bottomPadding=0)
    doc.addPageTemplates([PageTemplate(id="onecol", frames=[frame], onPage=footer)])
    doc.build(story)
    return out_path


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Generate a plan checklist (Md + PDF).")
    ap.add_argument("design")
    ap.add_argument("--inventory", required=True)
    ap.add_argument("--cut-spec", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--root", default=None)
    args = ap.parse_args(argv)
    root = args.root or os.getcwd()
    tool_limits = _load(os.path.join(root, "specs", "tool-limits.yaml"))
    from .deliver import resolve_run
    project, cut_spec, variant, _path = resolve_run(
        root, args.design, args.inventory, args.cut_spec, tool_limits,
        save_cut_spec=False)
    os.makedirs(args.out, exist_ok=True)
    md_path = build_md(project, cut_spec, tool_limits, args.out,
                       args.design, args.inventory, variant)
    pdf_path = os.path.join(args.out, "plan-checklist.pdf")
    phase1_data = build_data(project, cut_spec, tool_limits)
    build_pdf_from_md(md_path, pdf_path, phase1_bars=_phase1_bars(phase1_data))
    print(f"wrote {md_path}")
    print(f"wrote {pdf_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
