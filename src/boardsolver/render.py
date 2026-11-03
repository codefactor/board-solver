"""Visual section renderers: compose Round 1 primitives into whole-section images.

Each renderer draws into a fresh :class:`PILCanvas`, returns the raw PNG bytes,
and the caller hashes those bytes for a content-addressed filename. Layout math
(positioning multiple primitives) lives here, not in the primitives.

Includes the Round 2 true-grid validation for the finished-board layout.
"""

from __future__ import annotations

import io
from typing import Any, Dict, List, Optional, Tuple

from .canvas import PILCanvas
from .colors import DEFAULT_COLORS, ColorMap, slice_color_map, text_on, lighten
from .derive import board_rips, crosscut_blanks, panel_summaries, ripped_slice_profiles
from .draw import draw_cut_board, draw_panel, draw_slice, _KERF_COLOR, _LOSS_COLOR, _OUTLINE
from .geometry import measure_to_sixteenths, px, resolve_slice, slice_length
from .format import frac_inches

_BG = "#f7f4e9"


def _to_png_bytes(canvas: PILCanvas) -> bytes:
    buf = io.BytesIO()
    canvas._img.save(buf, format="PNG")
    return buf.getvalue()


# --------------------------------------------------------------------------- #
# true-grid validation
# --------------------------------------------------------------------------- #

def validate_true_grid(project: Dict[str, Any]) -> None:
    """Raise ValueError unless the sliceGrid is a true grid:

    every row has equal height (all its slices share one height), every column
    index has equal width across rows, and all rows have the same column count.
    """
    grid = project.get("sliceGrid", [])
    if not grid:
        return
    ncols = len(grid[0])
    col_widths: List[int] = [None] * ncols
    for r, row in enumerate(grid):
        if len(row) != ncols:
            raise ValueError(
                f"sliceGrid row {r} has {len(row)} cells, expected {ncols}"
            )
        row_height = None
        for c, cell in enumerate(row):
            resolved = resolve_slice(project, cell["sliceId"])
            h = resolved.height
            w = slice_length(resolved)
            if row_height is None:
                row_height = h
            elif h != row_height:
                raise ValueError(
                    f"sliceGrid row {r} has unequal heights "
                    f"({row_height} vs {h} at col {c})"
                )
            if col_widths[c] is None:
                col_widths[c] = w
            elif w != col_widths[c]:
                raise ValueError(
                    f"sliceGrid column {c} has unequal widths "
                    f"({col_widths[c]} vs {w} at row {r})"
                )


# --------------------------------------------------------------------------- #
# section 1: finished board grid
# --------------------------------------------------------------------------- #

def render_finished_board(
    project: Dict[str, Any], scale: float = 26.0, colors: ColorMap = DEFAULT_COLORS
) -> bytes:
    validate_true_grid(project)
    grid = project["sliceGrid"]
    pad = 20

    # Row heights and the single row width (true grid => every row same width).
    row_heights = []
    for row in grid:
        r0 = resolve_slice(project, row[0]["sliceId"])
        row_heights.append(px(r0.height, scale))
    row_w = sum(
        px(slice_length(resolve_slice(project, cell["sliceId"])), scale)
        for cell in grid[0]
    )
    total_h = sum(row_heights)
    canvas = PILCanvas(int(row_w + 2 * pad), int(total_h + 2 * pad), _BG)
    y = pad
    for row, h in zip(grid, row_heights):
        x = pad
        for cell in row:
            # Borderless component cells: the only border is around the whole board.
            bb = draw_slice(
                canvas, project, cell["sliceId"], cell.get("flip"),
                (x, y), scale, colors, outline=None,
            )
            x += bb.w
        y += h
    # Single border around the entire board face.
    canvas.rect(pad, pad, row_w, total_h, fill=None, outline="#222222")
    return _to_png_bytes(canvas)


def render_slice_map(
    project: Dict[str, Any],
    scale: float = 26.0,
    colors: ColorMap = DEFAULT_COLORS,
    border: int = 3,
    flip_tri: int = 10,  # size (px) of the top-left flip-indicator triangle
) -> bytes:
    """Slice-keyed variant of the finished board (its own "Slice Grid" section).

    Each slice cell is the same full-bleed component-colored slice as
    :func:`render_finished_board`, inset inside a ``border``-thick frame colored
    by the slice's id (see :func:`slice_color_map`). The frame is a gutter: the
    board is ``columns * 2*border`` wider and ``rows * 2*border`` taller than the
    borderless finished board. A horizontally-flipped slice is marked with a
    filled triangle in its top-left inner corner (just inside the border). A
    legend under the board maps each border color to its slice id; a footer
    explains the flip triangle.
    """
    validate_true_grid(project)
    grid = project["sliceGrid"]
    pad = 20
    ncols = len(grid[0])
    nrows = len(grid)

    all_ids = [cell["sliceId"] for row in grid for cell in row]
    cmap = slice_color_map(all_ids)

    # Cell inner sizes.
    row_heights = [
        px(resolve_slice(project, row[0]["sliceId"]).height, scale) for row in grid
    ]
    col_widths = [
        px(slice_length(resolve_slice(project, cell["sliceId"])), scale)
        for cell in grid[0]
    ]
    board_w = sum(col_widths) + ncols * 2 * border
    board_h = sum(row_heights) + nrows * 2 * border

    # Legend geometry: distinct slice ids laid out in up to 3 columns.
    legend_sw = 16  # swatch size
    legend_line = 22
    legend_cols = 3
    legend_col_w = 120  # wide enough for a 5-6 char slice id beside its swatch
    import math as _math
    legend_grid_rows = _math.ceil(len(cmap) / legend_cols)
    legend_h = 18 + legend_grid_rows * legend_line + 28  # title + rows + footer

    W = int(max(board_w, legend_cols * legend_col_w) + 2 * pad)
    H = int(board_h + 2 * pad + legend_h)
    canvas = PILCanvas(W, H, _BG)

    y = pad
    for row, ch in zip(grid, row_heights):
        x = pad
        for cell, cw in zip(row, col_widths):
            sid = cell["sliceId"]
            # Colored border frame (gutter) sized cell + 2*border.
            canvas.rect(x, y, cw + 2 * border, ch + 2 * border,
                        fill=cmap[sid], outline=None)
            # Full-bleed component-colored slice inset by the border.
            draw_slice(canvas, project, sid, cell.get("flip"),
                       (x + border, y + border), scale, colors, outline=None)
            if cell.get("flip") == "H":
                # Flip indicator: bright yellow triangle in the top-left corner of
                # the outer colored box, 1px in from its top and left edges, drawn
                # on top of everything.
                tx, ty = x + 1, y + 1
                canvas.polygon(
                    [(tx, ty), (tx + flip_tri, ty), (tx, ty + flip_tri)],
                    fill="#ffe000", outline=None,
                )
            x += cw + 2 * border
        y += ch + 2 * border

    # Legend: slice-id swatches in 3 columns, then a yellow-triangle entry.
    ly = pad + board_h + 14
    canvas.text(pad, ly - 4, "Slice legend", 13, "#222222")
    ly += 14
    row_top = ly
    for i, (sid, color) in enumerate(cmap.items()):
        col = i % legend_cols
        rown = i // legend_cols
        ex = pad + col * legend_col_w
        ey = row_top + rown * legend_line
        canvas.rect(ex, ey, legend_sw, legend_sw, fill=color, outline="#333333")
        canvas.text(ex + legend_sw + 8, ey + 1, sid, 12, "#222222")
    footer_y = row_top + legend_grid_rows * legend_line + 4
    # Yellow-triangle key for the flip indicator.
    canvas.polygon(
        [(pad, footer_y), (pad + legend_sw, footer_y), (pad, footer_y + legend_sw)],
        fill="#ffe000", outline="#333333",
    )
    canvas.text(pad + legend_sw + 8, footer_y + 2,
                "corner triangle = slice placed horizontally flipped",
                11, "#555555")
    return _to_png_bytes(canvas)


# --------------------------------------------------------------------------- #
# panel faces: each panel drawn to-scale with length vertical
# --------------------------------------------------------------------------- #

_SNIPE_BASE = "#d98b7a"   # possible loss (snipe) base
_SNIPE_HATCH = "#7a2d20"  # darker-red hatch over snipe


def render_panel_faces(
    project: Dict[str, Any], tool_limits: Dict[str, Any],
    scale: float = 16.0, colors: ColorMap = DEFAULT_COLORS,
    quantities: Optional[Dict[str, int]] = None,
) -> bytes:
    """Each panel drawn to-scale, length running top-to-bottom.

    Components are glued aligned on one squared edge (the left/width origin) and
    run as vertical columns. Profiles are length regions stacked top-to-bottom:
    the fullest profile (all components) is the top region; later profiles drop
    trailing components, so the panel silhouette steps narrower down its length.
    A dashed crosscut line (overflowing the width) marks each slice boundary; a
    solid reddish band is the total kerf loss above the bottom snipe tail; both
    snipe half-tails (top and bottom) are reddish cross-hatch (possible loss).
    """
    lim = tool_limits["limits"] if "limits" in tool_limits else tool_limits
    slice_depth = measure_to_sixteenths(project["sliceDepth"])
    miter_kerf = measure_to_sixteenths(lim["miterKerf"])
    snipe = measure_to_sixteenths(lim.get("snipeTail", [0, 0]))
    pitch = slice_depth + miter_kerf

    panels = project["panels"]
    pad = 20
    gap = 90
    title_px = 13
    overflow = 10
    label_h = 2 * title_px + 10  # two lines: name, then length

    def profile_regions(panel):
        """[(resolved, slice_count)] per profile, fullest first; one for single."""
        pid = panel["id"]
        if "profiles" in panel:
            return [
                (resolve_slice(project, f"{pid}-{p['id']}"), p["slices"])
                for p in panel["profiles"]
            ]
        return [(resolve_slice(project, pid), panel["slices"])]

    # Pre-measure.
    metas = []
    for panel in panels:
        regions = profile_regions(panel)
        n = sum(c for _, c in regions)
        full_w = slice_length(regions[0][0])  # fullest profile width
        body_len = n * slice_depth
        kerf_len = n * miter_kerf
        total_len = body_len + kerf_len + snipe
        metas.append(dict(panel=panel, regions=regions, n=n, full_w=full_w,
                          body_len=body_len, kerf_len=kerf_len, total_len=total_len))

    # Grid layout: max 3 panels per row; each row's height = its tallest panel
    # (label + snipe + body + kerf). Next row starts below the previous row.
    per_row = 3
    row_gap = 40
    rows = [metas[i:i + per_row] for i in range(0, len(metas), per_row)]

    def cell_w(m):
        return px(m["full_w"], scale) + 2 * overflow

    def cell_h(m):
        return label_h + px(m["total_len"], scale)

    row_widths = [
        sum(cell_w(m) for m in row) + gap * (len(row) - 1) for row in rows
    ]
    row_heights = [max(cell_h(m) for m in row) for row in rows]
    legend_h = 4 * 20 + 16  # four entries + heading padding
    total_w = max(max(row_widths), 360) + 2 * pad
    H = int(sum(row_heights) + row_gap * (len(rows) - 1) + 2 * pad + legend_h)
    canvas = PILCanvas(int(total_w), H, _BG)

    def draw_one(m, cell_x, cell_y):
        """Draw one panel; cell_x is the left of the cell (before overflow),
        cell_y is the top of the cell (label line)."""
        panel = m["panel"]
        x = cell_x + overflow
        full_w_px = px(m["full_w"], scale)
        qty = (quantities or {}).get(panel["id"], 1)
        canvas.text(x, cell_y, f"Panel {panel['id']}  ×{qty}", title_px, "#222222")
        canvas.text(x, cell_y + title_px + 2,
                    f"{frac_inches(m['total_len'], ascii=True)} long", title_px - 1, "#555555")
        y0 = cell_y + label_h
        half_snipe = px(snipe / 2, scale)
        body_y = y0 + half_snipe

        ry = body_y
        region_boundaries = []  # y of each interior profile transition
        for ri, (resolved, count) in enumerate(m["regions"]):
            region_h = px(count * slice_depth, scale)
            cx = x
            for c in resolved.components:
                cwpx = px(c.width, scale)
                canvas.rect(cx, ry, cwpx, region_h, fill=colors[c.species], outline=_OUTLINE)
                cx += cwpx
            ry += region_h
            if ri < len(m["regions"]) - 1:
                region_boundaries.append(ry)  # transition to the next profile

        for i in range(1, m["n"]):
            ly = body_y + px(i * slice_depth, scale)
            canvas.dashed_hline(x - overflow, x + full_w_px + overflow, ly, "#444444", width=1)

        # Profile transitions: solid line across + a blue diamond off the right
        # edge, vertically centered on the transition.
        for by in region_boundaries:
            canvas.line(x, by, x + full_w_px, by, "#222222", width=2)
            d = 6  # diamond half-size
            dx = x + full_w_px + overflow + d + 2  # center, just right of the panel
            canvas.polygon(
                [(dx, by - d), (dx + d, by), (dx, by + d), (dx - d, by)],
                fill="#1f6fe0", outline="#0b3c86",
            )

        kerf_px = px(m["kerf_len"], scale)
        kerf_y = body_y + px(m["body_len"], scale)
        if kerf_px > 0:
            canvas.rect(x, kerf_y, full_w_px, kerf_px, fill=_LOSS_COLOR, outline=None)

        bot_snipe_y = kerf_y + kerf_px
        if half_snipe > 0:
            canvas.hatch_rect(x, y0, full_w_px, half_snipe, _SNIPE_BASE, _SNIPE_HATCH)
            canvas.hatch_rect(x, bot_snipe_y, full_w_px, half_snipe, _SNIPE_BASE, _SNIPE_HATCH)

    y = pad
    for row, rh in zip(rows, row_heights):
        x = pad
        for m in row:
            draw_one(m, x, y)
            x += cell_w(m) + gap
        y += rh + row_gap

    # Legend.
    lx = pad
    ly = y
    sample_w = 34
    tx = lx + sample_w + 10
    line_h = 20
    # dashed line = crosscut
    cy = ly + line_h // 2
    canvas.dashed_hline(lx, lx + sample_w, cy, "#444444", width=1)
    canvas.text(tx, ly + 3, "dashed line = crosscut", 12, "#333333")
    ly += line_h
    # solid line + diamond = crosscut AND profile change
    cy = ly + line_h // 2
    canvas.line(lx, cy, lx + sample_w, cy, "#222222", width=2)
    d = 5
    dcx = lx + sample_w + 2
    canvas.polygon([(dcx, cy - d), (dcx + d, cy), (dcx, cy + d), (dcx - d, cy)],
                   fill="#1f6fe0", outline="#0b3c86")
    canvas.text(tx + 6, ly + 3, "solid line + diamond = crosscut and profile change", 12, "#333333")
    ly += line_h
    # red = kerf loss
    canvas.rect(lx, ly + 3, sample_w, line_h - 8, fill=_LOSS_COLOR, outline=_OUTLINE)
    canvas.text(tx, ly + 3, "red = kerf loss (sawdust)", 12, "#333333")
    ly += line_h
    # cross-hatch = potential snipe loss
    canvas.hatch_rect(lx, ly + 3, sample_w, line_h - 8, _SNIPE_BASE, _SNIPE_HATCH, outline=_OUTLINE)
    canvas.text(tx, ly + 3, "cross-hatch = potential loss from planer snipe", 12, "#333333")

    return _to_png_bytes(canvas)


# --------------------------------------------------------------------------- #
# ripped-slice diagrams: one per distinct ripped slice profile
# --------------------------------------------------------------------------- #

def render_ripped_slices(
    project: Dict[str, Any], tool_limits: Dict[str, Any],
    scale: float = 46.0, colors: ColorMap = DEFAULT_COLORS,
) -> bytes:
    """One zoomed diagram per distinct ripped-slice profile (merged across
    panels). Horizontal axis = the slice's length (end-grain stripes as vertical
    bands); vertical = the panel thickness, divided by dashed rip lines into
    ``strip_count`` strips; a reddish full-width band at the bottom is the rip
    kerf + planing/margin loss. Each diagram is labeled with how many identical
    slices to cut and the contributing slice ids.
    """
    lim = tool_limits["limits"] if "limits" in tool_limits else tool_limits
    miter_kerf = measure_to_sixteenths(lim["miterKerf"])  # (slices already cut)
    profiles = ripped_slice_profiles(project, tool_limits)
    pad = 20
    title_px = 14
    sub_px = 12
    gap = 34
    label_h = title_px + 4 + sub_px + 8
    legend_h = 2 * 18 + 10

    if not profiles:
        canvas = PILCanvas(260, 60, _BG)
        canvas.text(pad, pad, "No ripped slices in this project.", 13, "#555555")
        return _to_png_bytes(canvas)

    # Sizes.
    def dims(rp):
        w = px(rp.length, scale)
        h = px(rp.panel_thickness, scale)
        return w, h

    max_w = max(dims(rp)[0] for rp in profiles)
    total_h = 0
    for rp in profiles:
        total_h += label_h + dims(rp)[1] + gap
    H = int(total_h + legend_h + 2 * pad)
    W = int(max_w + 2 * pad)
    canvas = PILCanvas(W, H, _BG)

    y = pad
    for rp in profiles:
        w_px, h_px = dims(rp)
        ids = ", ".join(rp.slice_ids)
        canvas.text(pad, y, f"Slice {ids}  —  cut {rp.count} identical", title_px, "#222222")
        canvas.text(pad, y + title_px + 4,
                    f"{frac_inches(rp.length, ascii=True)} long, ripped into "
                    f"{rp.strip_count} x {frac_inches(rp.strip_width, ascii=True)} strips",
                    sub_px, "#555555")
        by = y + label_h

        # End-grain stripes: vertical bands across the length, full thickness.
        cx = pad
        for c in rp.components:
            cwpx = px(c.width, scale)
            canvas.rect(cx, by, cwpx, h_px, fill=colors[c.species], outline=_OUTLINE)
            cx += cwpx

        # Rip loss band at the bottom: thickness - strip_count * strip_width.
        strips_h = px(rp.strip_count * rp.strip_width, scale)
        loss_h = h_px - strips_h
        if loss_h > 0:
            canvas.rect(pad, by + strips_h, w_px, loss_h, fill=_LOSS_COLOR, outline=None)

        # Dashed rip lines dividing the strips (strip_count - 1 interior lines),
        # overflowing the width.
        for i in range(1, rp.strip_count):
            ly = by + px(i * rp.strip_width, scale)
            canvas.dashed_hline(pad - 8, pad + w_px + 8, ly, "#444444", width=1)

        # Outline the slice.
        canvas.rect(pad, by, w_px, h_px, fill=None, outline="#222222")
        y = by + h_px + gap

    # Legend.
    lx, ly = pad, y
    sample_w = 34
    tx = lx + sample_w + 10
    cy = ly + 9
    canvas.dashed_hline(lx, lx + sample_w, cy, "#444444", width=1)
    canvas.text(tx, ly + 3, "dashed line = rip cut", 12, "#333333")
    ly += 18
    canvas.rect(lx, ly + 3, sample_w, 11, fill=_LOSS_COLOR, outline=_OUTLINE)
    canvas.text(tx, ly + 3, "red = rip kerf + planing / margin loss", 12, "#333333")

    return _to_png_bytes(canvas)


# --------------------------------------------------------------------------- #
# crosscut blanks diagram (to-scale by length; modest fixed bar height)
# --------------------------------------------------------------------------- #

def render_crosscut_blanks(
    project: Dict[str, Any], cut_spec: Dict[str, Any], tool_limits: Dict[str, Any],
    scale: float = 7.0, colors: ColorMap = DEFAULT_COLORS, bar_h: int = 34,
) -> bytes:
    """One horizontal bar per raw inventory board, to-scale by length. Each bar
    is split into the labeled blank segments (length labeled inside), kerf
    stripes at the crosscuts, and a leftover tail (alert color if the blanks
    overflow the raw board).
    """
    blanks = crosscut_blanks(project, cut_spec, tool_limits)
    pad = 16
    title_px = 13
    gap = 22
    kerf_s = blanks[0].kerf if blanks else 2

    max_len = max((cb.length for cb in blanks), default=0)
    W = int(px(max_len, scale) + 2 * pad)
    H = int(len(blanks) * (title_px + 4 + bar_h + gap) + 2 * pad)
    canvas = PILCanvas(W, H, _BG)

    y = pad
    for cb in blanks:
        # Title: spares and whole-use boards are annotated distinctly.
        if cb.state == "spare":
            title = f"{cb.source_id}  ({frac_inches(cb.length, ascii=True)} long)  — untouched spare"
            title_color = "#888888"
        elif cb.state == "whole":
            title = f"{cb.source_id}  ({frac_inches(cb.length, ascii=True)} long)  — used whole (no crosscut)"
            title_color = "#222222"
        else:
            title = f"{cb.source_id}  ({frac_inches(cb.length, ascii=True)} long)"
            title_color = "#222222"
        canvas.text(pad, y, title, title_px, title_color)
        by = y + title_px + 4
        x = pad
        species_color = colors[cb.species]

        if cb.state == "spare":
            # Untouched spare: hollow/outlined bar in a muted dashed look (no fill
            # treatment available, so draw a pale wash with a dashed-ish double
            # outline) and no blanks.
            full = px(cb.length, scale)
            canvas.rect(x, by, full, bar_h, fill=lighten(species_color, 0.4), outline=_OUTLINE)
            canvas.text(x + 4, by + bar_h / 2 - 6, f"{cb.source_id} spare — not cut",
                        11, text_on(lighten(species_color, 0.4)))
            y = by + bar_h + gap
            continue

        for i, bl in enumerate(cb.blanks):
            seg_w = px(bl.length, scale)
            canvas.rect(x, by, seg_w, bar_h, fill=species_color, outline=_OUTLINE)
            label = f"{bl.blank_id} {frac_inches(bl.length, ascii=True)}"
            if cb.state == "whole":
                label += "  → rip diagram"
            canvas.text(x + 4, by + bar_h / 2 - 6, label, 11, text_on(species_color))
            x += seg_w
            # Reddish crosscut kerf stripe between blanks (sawdust), one per
            # crosscut after the first blank.
            if i != len(cb.blanks) - 1:
                kerf_px = px(kerf_s, scale)
                canvas.rect(x, by, kerf_px, bar_h, fill=_LOSS_COLOR, outline=None)
                x += kerf_px
        # Leftover tail: a trimmed end also pays a crosscut kerf (reddish), then
        # the pale leftover; or a red overflow bar if the blanks don't fit.
        if cb.leftover > 0:
            if cb.state != "whole":
                kerf_px = px(kerf_s, scale)
                canvas.rect(x, by, kerf_px, bar_h, fill=_LOSS_COLOR, outline=None)
                x += kerf_px
            lp = px(cb.leftover, scale)
            canvas.rect(x, by, lp, bar_h, fill="#e8e4d6", outline=_OUTLINE)
            canvas.text(x + 4, by + bar_h / 2 - 6,
                        f"left {frac_inches(cb.leftover, ascii=True)}", 10, "#666666")
        elif cb.leftover < 0:
            # Blanks overflow the raw board: draw a red overflow bar past the end.
            op = px(-cb.leftover, scale)
            canvas.rect(x, by, op, bar_h, fill="#c0392b", outline=_OUTLINE)
            canvas.text(x + 4, by + bar_h / 2 - 6,
                        f"over {frac_inches(-cb.leftover, ascii=True)}", 10, "#ffffff")
        y = by + bar_h + gap
    return _to_png_bytes(canvas)


# --------------------------------------------------------------------------- #
# section 2: panels overview
# --------------------------------------------------------------------------- #

def render_panels(
    project: Dict[str, Any], tool_limits: Dict[str, Any],
    scale: float = 40.0, colors: ColorMap = DEFAULT_COLORS,
) -> bytes:
    pad = 20
    gap = 26
    title_px = 15
    panels = project["panels"]
    widths, heights = [], []
    for p in panels:
        r = resolve_slice(project, _fullest_id(p))
        widths.append(px(slice_length(r), scale))
        # cell + annotation line
        cell_h = px(measure_to_sixteenths(p["thickness"]), scale)
        heights.append(title_px + 4 + cell_h + 2 + 11)
    W = int(max(widths) + 2 * pad)
    H = int(sum(heights) + gap * len(panels) + 2 * pad)
    canvas = PILCanvas(W, H, _BG)
    y = pad
    for p, h in zip(panels, heights):
        canvas.text(pad, y, f"Panel {p['id']}", title_px, "#222222")
        draw_panel(canvas, project, p["id"], (pad, y + title_px + 4), scale, colors)
        y += h + gap
    return _to_png_bytes(canvas)


# --------------------------------------------------------------------------- #
# section 3: strip map (all cut boards)
# --------------------------------------------------------------------------- #

def render_strip_map(
    project: Dict[str, Any], cut_spec: Dict[str, Any], tool_limits: Dict[str, Any],
    scale: float = 12.0, colors: ColorMap = DEFAULT_COLORS,
) -> bytes:
    pad = 16
    gap = 30
    boards = cut_spec["boards"]
    # Pre-measure height by drawing into a scratch canvas is overkill; estimate
    # generously, then crop by drawing into a correctly-sized canvas in one pass.
    # Width: longest board length * scale + source-width overhang margin.
    max_len = max(measure_to_sixteenths(b["length"]) for b in boards)
    # Height per board: title + strips + loss + margin. Use source width as an
    # upper bound on stacked height (strips + loss + margin <= source width).
    rips = {r.id: r for r in board_rips(project, cut_spec, tool_limits)}

    def board_height(b):
        r = rips[b["id"]]
        stacked = max(r.source_width, r.used + r.loss + max(r.margin, 0))
        return 14 + 4 + px(stacked, scale) + 4

    total_h = sum(board_height(b) + gap for b in boards) + 2 * pad
    W = int(px(max_len, scale) + 2 * pad)
    canvas = PILCanvas(W, int(total_h), _BG)
    y = pad
    for b in boards:
        bb = draw_cut_board(canvas, b, project, tool_limits, (pad, y), scale, colors, cut_spec)
        y += bb.h + gap
    return _to_png_bytes(canvas)


# --------------------------------------------------------------------------- #

def _fullest_id(panel: Dict[str, Any]) -> str:
    if "profiles" in panel:
        return f"{panel['id']}-{panel['profiles'][0]['id']}"
    return panel["id"]
