"""Visual section renderers: compose Round 1 primitives into whole-section images.

Each renderer draws into a fresh :class:`PILCanvas`, returns the raw PNG bytes,
and the caller hashes those bytes for a content-addressed filename. Layout math
(positioning multiple primitives) lives here, not in the primitives.

Includes the Round 2 true-grid validation for the finished-board layout.
"""

from __future__ import annotations

import io
from typing import Any, Dict, List, Tuple

from .canvas import PILCanvas
from .colors import DEFAULT_COLORS, ColorMap, slice_color_map, text_on, lighten
from .derive import board_rips, crosscut_blanks, panel_summaries
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
