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
from .derive import board_rips, crosscut_blanks, panel_summaries
from .draw import draw_cut_board, draw_panel, draw_slice, _KERF_COLOR, _LOSS_COLOR, _OUTLINE
from .geometry import measure_to_sixteenths, px, resolve_slice, slice_length
from .format import frac_inches

_BG = "#ffffff"

# Finished-board image margins: dimension line on the left, outer pad on
# both sides, and the drop-shadow offset on the right. The finished face
# itself is fin.width minus these, which tests use to compare against
# the slice map's board region.
_FINISHED_DIM_LEFT = 68
_FINISHED_OUTER = 12
_FINISHED_SHADOW_DX = 10


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

def _dim_font(size: int):
    from PIL import ImageFont

    for name in ("DejaVuSans-Bold.ttf", "DejaVuSans.ttf", "Arial Bold.ttf"):
        try:
            return ImageFont.truetype(name, size)
        except Exception:
            continue
    return ImageFont.load_default()


def render_finished_board(
    project: Dict[str, Any], scale: float = 26.0, colors: ColorMap = DEFAULT_COLORS
) -> bytes:
    """Finished board face with final dimensions and a drop shadow.

    Typical measurement lines sit above (width) and left (height) of the
    board: an extension line from each corner, a dimension line with
    arrowheads at both ends, and the finished size as its label. A soft
    drop shadow sits under the board, offset down-right.
    """
    from PIL import Image, ImageDraw, ImageFilter

    validate_true_grid(project)
    grid = project["sliceGrid"]

    # Row heights and the single row width (true grid => every row same width),
    # in pixels and in sixteenths (for the dimension labels).
    row_heights = []
    row_heights_16 = []
    for row in grid:
        r0 = resolve_slice(project, row[0]["sliceId"])
        row_heights.append(px(r0.height, scale))
        row_heights_16.append(r0.height)
    row_w = sum(
        px(slice_length(resolve_slice(project, cell["sliceId"])), scale)
        for cell in grid[0]
    )
    row_w_16 = sum(
        slice_length(resolve_slice(project, cell["sliceId"]))
        for cell in grid[0]
    )
    total_h = sum(row_heights)
    total_h_16 = sum(row_heights_16)
    board_w = int(round(row_w))
    board_h = int(round(total_h))

    # Draw the face itself into a tight temporary canvas first, so the
    # shadow and dimension lines can sit outside it.
    face = PILCanvas(board_w, board_h, _BG)
    y = 0
    for row, h in zip(grid, row_heights):
        x = 0
        for cell in row:
            # Borderless component cells: the only border is around the whole board.
            bb = draw_slice(
                face, project, cell["sliceId"], cell.get("flip"),
                (x, y), scale, colors, outline=None,
            )
            x += bb.w
        y += h

    # Crop to final dimensions: the finished board is the grid face
    # after trimming, not the untrimmed glue-up. Finished width/height
    # come from finishedWidth/finishedLength when declared, else from
    # edgeTrims (grid minus edges). The crop per edge follows edgeTrims
    # when declared; otherwise the excess comes off the right and
    # bottom edges, keeping the top-left corner fixed. If no finished
    # size is declared, the grid size stands.
    _fw16, _fl16 = row_w_16, total_h_16
    _fw_decl = project.get("finishedWidth")
    _fl_decl = project.get("finishedLength")
    if _fw_decl is not None and _fl_decl is not None:
        _fw16, _fl16 = measure_to_sixteenths(_fw_decl), measure_to_sixteenths(_fl_decl)
    elif project.get("edgeTrims"):
        _tr = project["edgeTrims"]
        _et = lambda e: measure_to_sixteenths(_tr[e]) if e in _tr else 0
        _fw16 = row_w_16 - _et("left") - _et("right")
        _fl16 = total_h_16 - _et("top") - _et("bottom")
    if _fw16 < row_w_16 or _fl16 < total_h_16:
        _tr = project.get("edgeTrims") or {}
        _et = lambda e: measure_to_sixteenths(_tr[e]) if e in _tr else 0
        _cl, _cr, _ct, _cb = _et("left"), _et("right"), _et("top"), _et("bottom")
        # Declared edges are the distribution; any undeclared remainder
        # of the total trim goes to the right/bottom edges, so the crop
        # always sums to grid minus finished, even when only one edge
        # is declared (e.g. top only).
        _rem_w = (row_w_16 - _fw16) - _cl - _cr
        _rem_h = (total_h_16 - _fl16) - _ct - _cb
        if _rem_w > 0:
            _cr += _rem_w
        if _rem_h > 0:
            _cb += _rem_h
        _crop = face._img.crop((
            int(round(px(_cl, scale))), int(round(px(_ct, scale))),
            board_w - int(round(px(_cr, scale))), board_h - int(round(px(_cb, scale)))))
        face._img = _crop
        board_w, board_h = _crop.size
        row_w_16, total_h_16 = _fw16, _fl16

    # Final canvas: room for the dimension lines, the shadow, and an outer pad.
    dim_top, dim_left, outer = 52, _FINISHED_DIM_LEFT, _FINISHED_OUTER
    sh_dx, sh_dy, sh_blur = _FINISHED_SHADOW_DX, 10, 6
    bx, by = dim_left + outer, dim_top + outer
    W = bx + board_w + sh_dx + outer
    H = by + board_h + sh_dy + outer
    img = Image.new("RGB", (W, H), _BG)

    # Drop shadow: blurred black rectangle offset down-right under the board.
    shadow = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    sd = ImageDraw.Draw(shadow)
    sd.rectangle([bx + sh_dx, by + sh_dy, bx + board_w + sh_dx, by + board_h + sh_dy],
                 fill=(0, 0, 0, 90))
    shadow = shadow.filter(ImageFilter.GaussianBlur(sh_blur))
    img.paste(Image.alpha_composite(img.convert("RGBA"), shadow).convert("RGB"), (0, 0))

    img.paste(face._img, (bx, by))
    d = ImageDraw.Draw(img)
    # Single border around the entire board face.
    d.rectangle([bx, by, bx + board_w, by + board_h], outline="#222222", width=2)

    # Measurement lines.
    dim_color = "#333333"
    ext_gap, dim_off = 6, 28
    font = _dim_font(14)

    def arrow_h(cx, cy, pointing_right):
        s = 6
        if pointing_right:
            d.polygon([(cx, cy), (cx - s, cy - s // 2), (cx - s, cy + s // 2)],
                      fill=dim_color)
        else:
            d.polygon([(cx, cy), (cx + s, cy - s // 2), (cx + s, cy + s // 2)],
                      fill=dim_color)

    def arrow_v(cx, cy, pointing_down):
        s = 6
        if pointing_down:
            d.polygon([(cx, cy), (cx - s // 2, cy - s), (cx + s // 2, cy - s)],
                      fill=dim_color)
        else:
            d.polygon([(cx, cy), (cx - s // 2, cy + s), (cx + s // 2, cy + s)],
                      fill=dim_color)

    # Width, above the board.
    y_dim = by - dim_off
    d.line([bx, by - ext_gap, bx, y_dim - 6], fill=dim_color, width=1)
    d.line([bx + board_w, by - ext_gap, bx + board_w, y_dim - 6], fill=dim_color, width=1)
    d.line([bx, y_dim, bx + board_w, y_dim], fill=dim_color, width=1)
    arrow_h(bx, y_dim, pointing_right=False)
    arrow_h(bx + board_w, y_dim, pointing_right=True)
    w_label = frac_inches(row_w_16)
    tw = d.textlength(w_label, font=font)
    d.rectangle([bx + board_w / 2 - tw / 2 - 4, y_dim - 22,
                 bx + board_w / 2 + tw / 2 + 4, y_dim - 4], fill=_BG)
    d.text((bx + board_w / 2 - tw / 2, y_dim - 21), w_label, fill=dim_color, font=font)

    # Height, left of the board, label rotated.
    x_dim = bx - dim_off
    d.line([bx - ext_gap, by, x_dim - 6, by], fill=dim_color, width=1)
    d.line([bx - ext_gap, by + board_h, x_dim - 6, by + board_h], fill=dim_color, width=1)
    d.line([x_dim, by, x_dim, by + board_h], fill=dim_color, width=1)
    arrow_v(x_dim, by, pointing_down=False)
    arrow_v(x_dim, by + board_h, pointing_down=True)
    h_label = frac_inches(total_h_16)
    label_img = Image.new("RGBA", (200, 40), (0, 0, 0, 0))
    ld = ImageDraw.Draw(label_img)
    ld.text((100, 20), h_label, fill=dim_color, font=font, anchor="mm")
    label_img = label_img.rotate(90, expand=True)
    img.paste(label_img, (int(x_dim - label_img.width / 2 - 6),
                          int(by + board_h / 2 - label_img.height / 2)),
              label_img)

    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


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
    """Each panel drawn to-scale, length running left-to-right (rotated:
    x and y swapped from the old top-to-bottom version, so each panel is
    wider than it is tall, with its titles still horizontal on top).

    Components are glued aligned on one squared edge (the top/width origin) and
    run as horizontal rows. Profiles are length regions stacked left-to-right:
    the fullest profile (all components) is the left region; later profiles drop
    trailing components, so the panel silhouette steps shorter to the right.
    A dashed crosscut line (overflowing the height) marks each slice boundary; a
    solid reddish band is the total kerf loss before the right snipe tail; both
    snipe half-tails (left and right) are reddish cross-hatch (possible loss).
    """
    lim = tool_limits["limits"] if "limits" in tool_limits else tool_limits
    slice_depth = measure_to_sixteenths(project["sliceDepth"])
    miter_kerf = measure_to_sixteenths(lim["miterKerf"])
    snipe = measure_to_sixteenths(lim.get("snipeTail", [0, 0]))
    pitch = slice_depth + miter_kerf

    panels = project["panels"]
    # panelSpecs (when declared) set each type's actual region slice counts.
    _spec_by_type = {}
    for _e in project.get("panelSpecs", []) or []:
        _spec_by_type.setdefault(_e["panel"], _e)
    pad = 20
    gap = 90
    title_px = 13
    overflow = 10
    label_h = 2 * title_px + 10  # two lines: name, then length

    def profile_regions(panel):
        """[(resolved, slice_count)] per profile, fullest first; one for single.
        When a panelSpec exists for this type, its region lengths set the slice
        counts (region length / pitch); otherwise the ideal declared slices."""
        pid = panel["id"]
        spec = _spec_by_type.get(pid)
        spec_slices = None
        if spec:
            spec_slices = [measure_to_sixteenths(m) // pitch for m in spec["profileLengths"]]
        if "profiles" in panel:
            return [
                (resolve_slice(project, f"{pid}-{p['id']}"),
                 spec_slices[i] if spec_slices else p["slices"])
                for i, p in enumerate(panel["profiles"])
            ]
        return [(resolve_slice(project, pid),
                 spec_slices[0] if spec_slices else panel["slices"])]

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

    # Rotated layout: one panel per row, stacked vertically, left-aligned.
    # Each cell is wider than it is tall: body width = total length,
    # body height = fullest profile width. The cell height adds overflow
    # for the crosscut lines and room for the profile-change diamond
    # below the panel (overflow + diamond diameter + margin).
    row_gap = 40

    def cell_w(m):
        return px(m["total_len"], scale) + 2 * overflow

    def cell_h(m):
        # Extra 16 px between the title lines and the panel body, so the
        # body does not sit tight under the title.
        return label_h + 16 + px(m["full_w"], scale) + 2 * overflow + 12

    legend_h = 4 * 20 + 16  # four entries + heading padding
    # Legend text ("solid line + diamond = crosscut and profile change")
    # is wider than a rotated panel cell, so the canvas must be at
    # least wide enough for it, or the legend text clips at the edge.
    total_w = max(max(cell_w(m) for m in metas), 420) + 2 * pad
    H = int(sum(cell_h(m) for m in metas) + row_gap * (len(metas) - 1) + 2 * pad + legend_h)
    canvas = PILCanvas(int(total_w), H, _BG)

    def draw_one(m, cell_x, cell_y):
        """Draw one rotated panel; cell_x is the left of the cell (before
        overflow), cell_y is the top of the cell (label line). Titles stay
        horizontal above the panel; only the panel body has x/y swapped."""
        panel = m["panel"]
        x = cell_x + overflow
        full_w_px = px(m["full_w"], scale)
        qty = (quantities or {}).get(panel["id"], 1)
        per = m["n"]  # slices from one panel = sum of its profile slice counts
        if qty > 1:
            slice_txt = f"({per} x {qty} = {per * qty} slices)"
        else:
            slice_txt = f"({per} slices)"
        canvas.text(x, cell_y, f"Panel {panel['id']}  ×{qty}", title_px, "#222222")
        canvas.text(x, cell_y + title_px + 2,
                    f"{frac_inches(m['total_len'])} long  {slice_txt}",
                    title_px - 1, "#555555")
        y0 = cell_y + label_h + 16  # top of the panel body, moved down from the title
        half_snipe = px(snipe / 2, scale)
        body_x = x + half_snipe  # left snipe band sits left of the body

        rx = body_x
        region_boundaries = []  # x of each interior profile transition
        for ri, (resolved, count) in enumerate(m["regions"]):
            region_w = px(count * slice_depth, scale)
            cy = y0
            for c in resolved.components:
                chpx = px(c.width, scale)
                canvas.rect(rx, cy, region_w, chpx, fill=colors[c.species], outline=_OUTLINE)
                cy += chpx
            rx += region_w
            if ri < len(m["regions"]) - 1:
                region_boundaries.append(rx)  # transition to the next profile

        for i in range(1, m["n"]):
            lx = body_x + px(i * slice_depth, scale)
            canvas.dashed_vline(lx, y0 - overflow, y0 + full_w_px + overflow, "#444444", width=1)

        # Profile transitions: solid line down + a blue diamond below the
        # panel, horizontally centered on the transition.
        for bx in region_boundaries:
            canvas.line(bx, y0, bx, y0 + full_w_px, "#222222", width=2)
            d = 6  # diamond half-size
            dy = y0 + full_w_px + overflow + d + 2  # center, just below the panel
            canvas.polygon(
                [(bx - d, dy), (bx, dy - d), (bx + d, dy), (bx, dy + d)],
                fill="#1f6fe0", outline="#0b3c86",
            )

        kerf_px = px(m["kerf_len"], scale)
        kerf_x = body_x + px(m["body_len"], scale)
        if kerf_px > 0:
            canvas.rect(kerf_x, y0, kerf_px, full_w_px, fill=_LOSS_COLOR, outline=None)

        right_snipe_x = kerf_x + kerf_px
        if half_snipe > 0:
            canvas.hatch_rect(x, y0, half_snipe, full_w_px, _SNIPE_BASE, _SNIPE_HATCH)
            canvas.hatch_rect(right_snipe_x, y0, half_snipe, full_w_px, _SNIPE_BASE, _SNIPE_HATCH)

    y = pad
    for m in metas:
        draw_one(m, pad, y)
        y += cell_h(m) + row_gap

    # Legend, samples rotated to match the rotated panels.
    lx = pad
    ly = y
    sample_w = 34
    tx = lx + sample_w + 10
    line_h = 20
    cx = lx + sample_w // 2  # center of the sample area
    # dashed line = crosscut (vertical, as in the rotated panels)
    canvas.dashed_vline(cx, ly + 3, ly + 17, "#444444", width=1)
    canvas.text(tx, ly + 3, "dashed line = crosscut", 12, "#333333")
    ly += line_h
    # solid line + diamond = crosscut AND profile change
    canvas.line(cx, ly + 2, cx, ly + 10, "#222222", width=2)
    d = 4
    dcy = ly + 14
    canvas.polygon([(cx - d, dcy), (cx, dcy - d), (cx + d, dcy), (cx, dcy + d)],
                   fill="#1f6fe0", outline="#0b3c86")
    canvas.text(tx, ly + 3, "solid line + diamond = crosscut and profile change", 12, "#333333")
    ly += line_h
    # red = kerf loss (vertical band, as in the rotated panels)
    canvas.rect(cx - 6, ly + 3, 12, line_h - 8, fill=_LOSS_COLOR, outline=_OUTLINE)
    canvas.text(tx, ly + 3, "red = kerf loss (sawdust)", 12, "#333333")
    ly += line_h
    # cross-hatch = potential snipe loss (vertical band)
    canvas.hatch_rect(cx - 6, ly + 3, 12, line_h - 8, _SNIPE_BASE, _SNIPE_HATCH, outline=_OUTLINE)
    canvas.text(tx, ly + 3, "cross-hatch = potential loss from planer snipe", 12, "#333333")

    return _to_png_bytes(canvas)


def _panel_face_single_meta(project, tool_limits, panel_id):
    """(cell_w, cell_h) for one rotated panel face, matching render_panel_faces.

    Rotated: cell_w is total length, cell_h is label + fullest width +
    overflow + diamond room; the single-panel combo's top section is
    pad + cell_h, then a row gap, then the legend.
    """
    lim = tool_limits["limits"] if "limits" in tool_limits else tool_limits
    slice_depth = measure_to_sixteenths(project["sliceDepth"])
    miter_kerf = measure_to_sixteenths(lim["miterKerf"])
    snipe = measure_to_sixteenths(lim.get("snipeTail", [0, 0]))
    pitch = slice_depth + miter_kerf
    panel = next(p for p in project["panels"] if p["id"] == panel_id)
    spec = None
    for _e in project.get("panelSpecs", []) or []:
        if _e["panel"] == panel_id:
            spec = _e
            break
    spec_slices = None
    if spec:
        spec_slices = [measure_to_sixteenths(m) // pitch for m in spec["profileLengths"]]
    if "profiles" in panel:
        regions = [(resolve_slice(project, f"{panel_id}-{p['id']}"),
                    spec_slices[i] if spec_slices else p["slices"])
                   for i, p in enumerate(panel["profiles"])]
    else:
        regions = [(resolve_slice(project, panel_id),
                    spec_slices[0] if spec_slices else panel["slices"])]
    n = sum(c for _, c in regions)
    full_w = slice_length(regions[0][0])
    total_len = n * slice_depth + n * miter_kerf + snipe
    label_h = 2 * 13 + 10
    cell_w = px(total_len, 16.0) + 2 * 10
    cell_h = label_h + 16 + px(full_w, 16.0) + 2 * 10 + 12
    return cell_w, cell_h


def render_panel_face_primitive(
    panel_id, project: Dict[str, Any], tool_limits: Dict[str, Any],
    colors: ColorMap = DEFAULT_COLORS,
    quantities: Optional[Dict[str, int]] = None,
) -> bytes:
    """Single-panel-face primitive, rotated wider than tall.

    It is a tight crop of the single-panel panel-faces combo, so it
    matches the combined diagram exactly. Titles stay horizontal; only
    the panel body has x/y swapped. The combined panel-faces diagram
    is kept as well.
    """
    import io as _io
    from PIL import Image as _Image
    single = dict(project)
    single["panels"] = [p for p in project["panels"] if p["id"] == panel_id]
    combo = render_panel_faces(single, tool_limits, colors=colors,
                               quantities=quantities)
    cell_w, cell_h = _panel_face_single_meta(project, tool_limits, panel_id)
    img = _Image.open(_io.BytesIO(combo)).convert("RGB")
    # Top section only: pad + cell height. Tight-crop horizontally to
    # non-background pixels in that section.
    top = img.crop((0, 0, img.size[0], int(20 + cell_h)))
    bg = (255, 255, 255)
    xs = []
    for x in range(top.size[0]):
        for y in range(top.size[1]):
            if top.getpixel((x, y)) != bg:
                xs.append(x)
                break
    left = max(min(xs) - 20, 0) if xs else 0
    right = min(max(xs) + 20, top.size[0]) if xs else top.size[0]
    out = top.crop((left, 0, right, top.size[1]))
    buf = _io.BytesIO()
    out.save(buf, format="PNG")
    return buf.getvalue()


def render_panel_faces_primitives(
    project: Dict[str, Any], tool_limits: Dict[str, Any],
    colors: ColorMap = DEFAULT_COLORS,
    quantities: Optional[Dict[str, int]] = None,
) -> Dict[str, bytes]:
    """{panel_id: single-panel-face PNG} in project panels order."""
    return {p["id"]: render_panel_face_primitive(
        p["id"], project, tool_limits, colors, quantities) for p in project["panels"]}


def render_panel_faces_legend(
    project: Dict[str, Any], tool_limits: Dict[str, Any],
    colors: ColorMap = DEFAULT_COLORS,
) -> bytes:
    """Panel-faces legend alone, as a separate image to sit centered
    below the flowed panel-face primitives (instead of being stuck
    at the bottom of one tall combined image)."""
    import io as _io
    from PIL import Image as _Image
    combo = render_panel_faces(project, tool_limits, colors=colors)
    img = _Image.open(_io.BytesIO(combo)).convert("RGB")
    # Legend is the bottom 4*20+16 px of the combo.
    legend_h = 4 * 20 + 16
    leg = img.crop((0, img.size[1] - legend_h, img.size[0], img.size[1]))
    bg = (255, 255, 255)
    xs = []
    for x in range(leg.size[0]):
        for y in range(leg.size[1]):
            if leg.getpixel((x, y)) != bg:
                xs.append(x)
                break
    left = max(min(xs) - 20, 0) if xs else 0
    right = min(max(xs) + 20, leg.size[0]) if xs else leg.size[0]
    out = leg.crop((left, 0, right, leg.size[1]))
    buf = _io.BytesIO()
    out.save(buf, format="PNG")
    return buf.getvalue()


# --------------------------------------------------------------------------- #
# crosscut blanks diagram (to-scale by length; modest fixed bar height)
# --------------------------------------------------------------------------- #

def _draw_crosscut_bar(canvas, cb, x0, y0, scale, colors, bar_h, kerf_s):
    """Draw one raw board's crosscut bar (title + segments + tail) at (x0, y0).

    Shared by the combined diagram and by the single-bar primitive, so the
    two always match pixel for pixel. Returns the height used
    (title + gap + bar height); the caller advances y by that plus its gap.
    """
    title_px = 13
    if cb.state == "spare":
        title = f"{cb.source_id}  ({frac_inches(cb.length)} long)  — untouched spare"
        title_color = "#888888"
    elif cb.state == "whole":
        title = f"{cb.source_id}  ({frac_inches(cb.length)} long)  — used whole (no crosscut)"
        title_color = "#222222"
    else:
        title = f"{cb.source_id}  ({frac_inches(cb.length)} long)"
        title_color = "#222222"
    canvas.text(x0, y0, title, title_px, title_color)
    by = y0 + title_px + 4
    x = x0
    species_color = colors[cb.species]
    if cb.state == "spare":
        full = px(cb.length, scale)
        canvas.rect(x, by, full, bar_h, fill=lighten(species_color, 0.4), outline=_OUTLINE)
        canvas.text(x + 4, by + bar_h / 2 - 6, f"{cb.source_id} spare — not cut",
                    11, text_on(lighten(species_color, 0.4)))
        return title_px + 4 + bar_h
    for i, bl in enumerate(cb.blanks):
        seg_w = px(bl.length, scale)
        canvas.rect(x, by, seg_w, bar_h, fill=species_color, outline=_OUTLINE)
        label = f"{bl.blank_id} {frac_inches(bl.length)}"
        if cb.state == "whole":
            label += "  → rip diagram"
        canvas.text(x + 4, by + bar_h / 2 - 6, label, 11, text_on(species_color))
        x += seg_w
        if i != len(cb.blanks) - 1:
            kerf_px = px(kerf_s, scale)
            canvas.rect(x, by, kerf_px, bar_h, fill=_LOSS_COLOR, outline=None)
            x += kerf_px
    if cb.leftover > 0:
        if cb.state != "whole":
            kerf_px = px(kerf_s, scale)
            canvas.rect(x, by, kerf_px, bar_h, fill=_LOSS_COLOR, outline=None)
            x += kerf_px
        lp = px(cb.leftover, scale)
        canvas.rect(x, by, lp, bar_h, fill="#e8e4d6", outline=_OUTLINE)
        canvas.text(x + 4, by + bar_h / 2 - 6,
                    f"left {frac_inches(cb.leftover)}", 10, "#666666")
    elif cb.leftover < 0:
        op = px(-cb.leftover, scale)
        canvas.rect(x, by, op, bar_h, fill="#c0392b", outline=_OUTLINE)
        canvas.text(x + 4, by + bar_h / 2 - 6,
                    f"over {frac_inches(-cb.leftover)}", 10, "#ffffff")
    return title_px + 4 + bar_h


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
        y += _draw_crosscut_bar(canvas, cb, pad, y, scale, colors, bar_h, kerf_s) + gap
    return _to_png_bytes(canvas)


def render_crosscut_blank_primitive(
    cb, scale: float = 7.0, colors: ColorMap = DEFAULT_COLORS, bar_h: int = 34,
    kerf_s: int = 2,
) -> bytes:
    """Single-bar primitive: one raw board's crosscut bar, left-aligned.

    The combined diagram is kept as well; this primitive is the version
    the plan document flows, one bar per row, left-aligned, instead of
    stacking all bars into one tall image.
    """
    pad = 16
    W = int(px(cb.length, scale) + 2 * pad)
    H = int(13 + 4 + bar_h + 2 * pad)
    canvas = PILCanvas(W, H, _BG)
    _draw_crosscut_bar(canvas, cb, pad, pad, scale, colors, bar_h, kerf_s)
    return _to_png_bytes(canvas)


def render_crosscut_blanks_primitives(
    project: Dict[str, Any], cut_spec: Dict[str, Any], tool_limits: Dict[str, Any],
    scale: float = 7.0, colors: ColorMap = DEFAULT_COLORS, bar_h: int = 34,
) -> Dict[str, bytes]:
    """{source_id: single-bar PNG} in crosscut_blanks order."""
    blanks = crosscut_blanks(project, cut_spec, tool_limits)
    kerf_s = blanks[0].kerf if blanks else 2
    return {cb.source_id: render_crosscut_blank_primitive(
        cb, scale, colors, bar_h, kerf_s) for cb in blanks}


def _compact_label(seg_w: float, full: str, short: str) -> str:
    """Label for a compact bar segment: full text when it fits,
    short text when only that fits, otherwise nothing. The table
    still carries the exact lengths, so the diagram only needs to
    show where each blank comes from."""
    if seg_w >= 62:
        return full
    if seg_w >= 34:
        return short
    return ""


def render_crosscut_compact(
    project: Dict[str, Any], cut_spec: Dict[str, Any], tool_limits: Dict[str, Any],
    scale: float = 7.0, colors: ColorMap = DEFAULT_COLORS,
    bar_h: int = 18, gap: int = 6, label_w: int = 118, annot_w: int = 110,
) -> bytes:
    """A single compact crosscut diagram for all raw boards.

    The current crosscut diagrams give each board its own tall bar
    (title + 34 px bar + gap, or one primitive per board in the
    plan), and the board's width is drawn as bar height even
    though width carries no crosscut information: a crosscut only
    splits a board along its length. This diagram drops that
    height entirely:

    * one fixed-height bar per raw board, all on a common length
      scale, left-aligned, so bar widths compare directly across
      boards — a 98″ board's bar is twice a 49″ board's bar;
    * bar height is fixed (18 px) and carries no information;
    * the source id and raw length sit in a left label column,
      not a title row above each bar, so the diagram's height is
      just one thin bar + a small gap per board;
    * segments are the blanks in order, species-colored, with
      kerf stripes between them, a pale leftover tail, and a
      washed-out bar for an untouched spare;
    * a tail whose exact amount does not fit inside it is not
      dropped: its amount is written to the right of the bar, in
      the annotation column, on the same row — so a 6″ leftover
      still reads "left 6³⁄₁₆″", and a shave still reads "shave";
    * a negative offcut (overflow) is not an extra red piece
      after a full blank, which would double-count it and make
      the bar longer than both the raw board and the demand.
      Instead the raw board is the background: the portion of a
      blank that fits inside the raw length is species-colored,
      the portion past the raw end is red, and the amount is
      written to the right as "over X". The raw end is therefore
      comparable across boards (same left alignment, same scale),
      and the red part is exactly the shortfall, not an extra;
    * a ghost board (buySpecies, no raw stock) gets its own row
      at the end, gray label, species-colored bar for the bought
      length, annotated "buy" — so a plan that must buy a board
      does not silently drop that board from the crosscut view.

    Returns PNG bytes. Not yet wired into the plan document: this
    is the prototype for review.
    """
    blanks = crosscut_blanks(project, cut_spec, tool_limits)
    buy_boards = [b for b in cut_spec.get("boards", []) if "buySpecies" in b]
    pad = 10
    kerf_s = blanks[0].kerf if blanks else 2

    def _demand_len(cb) -> int:
        return sum(bl.length for bl in cb.blanks) + max(len(cb.blanks) - 1, 0) * kerf_s

    def _drawn_len(cb) -> int:
        # Fit boards: drawn length is the raw length (blanks + kerfs
        # + leftover). Overflow boards: drawn length is the demand,
        # which exceeds the raw length by the shortfall.
        return max(cb.length, _demand_len(cb))

    max_drawn = max(
        [_drawn_len(cb) for cb in blanks]
        + [measure_to_sixteenths(b["length"]) for b in buy_boards],
        default=0)
    n_rows = len(blanks) + len(buy_boards)
    W = int(pad * 2 + label_w + px(max_drawn, scale) + annot_w)
    H = int(pad * 2 + n_rows * (bar_h + gap) - gap) if n_rows else int(pad * 2)
    canvas = PILCanvas(W, H, _BG)
    y = pad
    for cb in blanks:
        label_color = "#888888" if cb.state == "spare" else "#222222"
        canvas.text(pad, y + bar_h / 2 - 6,
                    f"{cb.source_id}  {frac_inches(cb.length)}", 11, label_color)
        bx = pad + label_w
        by = y
        species_color = colors[cb.species]
        raw_end_x = bx + px(cb.length, scale)
        x = bx
        annot = ""
        annot_color = "#666666"
        if cb.state == "spare":
            full = px(cb.length, scale)
            canvas.rect(x, by, full, bar_h, fill=lighten(species_color, 0.4), outline=_OUTLINE)
            lab = _compact_label(full, f"{cb.source_id} spare — not cut", "spare")
            if lab:
                canvas.text(x + 4, by + bar_h / 2 - 5, lab, 10, text_on(lighten(species_color, 0.4)))
            x += full
            y += bar_h + gap
            continue
        # Raw background, so the raw end is visible even when a
        # blank runs past it. Segments drawn on top cover it for
        # fit boards; for overflow boards it ends at raw_end_x.
        canvas.rect(bx, by, px(cb.length, scale), bar_h, fill="#f0f0f0", outline=_OUTLINE)
        for i, bl in enumerate(cb.blanks):
            seg_w = px(bl.length, scale)
            seg_end = x + seg_w
            if x >= raw_end_x:
                # Entirely past the raw end: missing material.
                canvas.rect(x, by, seg_w, bar_h, fill="#c0392b", outline=_OUTLINE)
            elif seg_end > raw_end_x:
                # Split at the raw end: fits in species color, the
                # rest in red, exactly the shortfall.
                canvas.rect(x, by, raw_end_x - x, bar_h, fill=species_color, outline=_OUTLINE)
                canvas.rect(raw_end_x, by, seg_end - raw_end_x, bar_h, fill="#c0392b", outline=_OUTLINE)
            else:
                canvas.rect(x, by, seg_w, bar_h, fill=species_color, outline=_OUTLINE)
            lab = _compact_label(
                seg_w, f"{bl.blank_id} {frac_inches(bl.length)}", bl.blank_id)
            if cb.state == "whole" and lab:
                lab += "  → rip"
                if seg_w < 110:
                    lab = bl.blank_id
            if lab:
                # Label color follows the segment's visible part:
                # white on red for a fully missing blank, otherwise
                # the species text color.
                lab_color = "#ffffff" if x >= raw_end_x else text_on(species_color)
                canvas.text(x + 4, by + bar_h / 2 - 5, lab, 10, lab_color)
            x = seg_end
            if i != len(cb.blanks) - 1:
                kerf_px = px(kerf_s, scale)
                canvas.rect(x, by, kerf_px, bar_h, fill=_LOSS_COLOR, outline=None)
                x += kerf_px
        if cb.leftover > 0:
            kerf_px = px(kerf_s, scale)
            canvas.rect(x, by, kerf_px, bar_h, fill=_LOSS_COLOR, outline=None)
            x += kerf_px
            lp = px(cb.leftover, scale)
            canvas.rect(x, by, lp, bar_h, fill="#e8e4d6", outline=_OUTLINE)
            # A short "left" inside a narrow tail loses the amount,
            # so only a full "left X" goes inside; otherwise the
            # full amount goes in the right annotation column.
            if lp >= 62:
                canvas.text(x + 4, by + bar_h / 2 - 5,
                            f"left {frac_inches(cb.leftover)}", 10, "#666666")
            else:
                annot = f"left {frac_inches(cb.leftover)}"
            x += lp
        elif cb.leftover < 0:
            annot = f"over {frac_inches(-cb.leftover)}"
            annot_color = "#c0392b"
        elif cb.shave:
            # No separate offcut: a thin yellow tick at the end.
            canvas.rect(x, by, 3, bar_h, fill="#ffff00", outline=_OUTLINE)
            x += 3
            annot = "shave"
        if annot:
            canvas.text(x + 8, by + bar_h / 2 - 5, annot, 10, annot_color)
        y += bar_h + gap
    for b in buy_boards:
        blen = measure_to_sixteenths(b["length"])
        canvas.text(pad, y + bar_h / 2 - 6,
                    f"{b['id']}  {frac_inches(blen)}", 11, "#888888")
        bx = pad + label_w
        seg_w = px(blen, scale)
        species_color = colors[b["buySpecies"]]
        canvas.rect(bx, y, seg_w, bar_h, fill=species_color, outline=_OUTLINE)
        lab = _compact_label(seg_w, f"{b['id']} {frac_inches(blen)}", b["id"])
        if lab:
            canvas.text(bx + 4, y + bar_h / 2 - 5, lab, 10, text_on(species_color))
        canvas.text(bx + seg_w + 8, y + bar_h / 2 - 5, "buy", 10, "#666666")
        y += bar_h + gap
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


def render_panel_primitive(
    p, project: Dict[str, Any], tool_limits: Dict[str, Any],
    scale: float = 40.0, colors: ColorMap = DEFAULT_COLORS,
) -> bytes:
    """Single-panel primitive: one panel's end-grain cross-section, drawn
    exactly as in the combined panels diagram, on its own canvas."""
    pad = 20
    title_px = 15
    r = resolve_slice(project, _fullest_id(p))
    cell_h = px(measure_to_sixteenths(p["thickness"]), scale)
    W = int(px(slice_length(r), scale) + 2 * pad)
    H = int(title_px + 4 + cell_h + 2 + 11 + 2 * pad)
    canvas = PILCanvas(W, H, _BG)
    canvas.text(pad, pad, f"Panel {p['id']}", title_px, "#222222")
    draw_panel(canvas, project, p["id"], (pad, pad + title_px + 4), scale, colors)
    return _to_png_bytes(canvas)


def render_panels_primitives(
    project: Dict[str, Any], tool_limits: Dict[str, Any],
    scale: float = 40.0, colors: ColorMap = DEFAULT_COLORS,
) -> Dict[str, bytes]:
    """{panel_id: single-panel PNG} in project panels order."""
    return {p["id"]: render_panel_primitive(
        p, project, tool_limits, scale, colors) for p in project["panels"]}


def render_panels_compact(
    project: Dict[str, Any], tool_limits: Dict[str, Any],
    scale: float = 40.0, colors: ColorMap = DEFAULT_COLORS,
    gap: float = 6, pad: float = 10,
    label_w: float = 84, annot_w: float = 150,
) -> bytes:
    """Compact panel end-grain diagram: one image, all panels.

    Same information as the per-panel primitives, in less than half
    the height — the saving comes from dropping each panel's title
    row, annotation row, and pads, not from distorting the drawing:

    * one bar per panel, all on a common scale, left-aligned, so
      component widths compare directly across panels;
    * bar height is to scale: it is the panel thickness, as in the
      primitives, because this is a projection of the panel's end
      grain — height is not fixed;
    * segments are the fullest profile's components in order,
      species-colored, widths to scale, exactly as in the primitives
      (no internal labels, as in the primitives — the sequence is in
      the Panels overview table);
    * panel thickness is also written in the left label (e.g.
      ``SL ¾″``), and slice count, which the primitives showed as an
      annotation line, is written to the right of the bar (e.g.
      ``20 slices``, ``8 slices (L=4, R=4)`` for a profiled panel).

    Returns PNG bytes.
    """
    panels = project["panels"]
    rows = []
    for p in panels:
        r = resolve_slice(project, _fullest_id(p))
        if "profiles" in p:
            total = sum(pr["slices"] for pr in p["profiles"])
            regions = ", ".join(f"{pr['id']}={pr['slices']}" for pr in p["profiles"])
            annot = f"{total} slices ({regions})"
        else:
            annot = f"{p['slices']} slices"
        rows.append((p, r, annot, px(measure_to_sixteenths(p["thickness"]), scale)))
    max_w = max((slice_length(r) for _, r, _, _ in rows), default=0)
    W = int(pad * 2 + label_w + px(max_w, scale) + annot_w)
    H = int(pad * 2 + sum(bh for _, _, _, bh in rows) + gap * (len(rows) - 1)) if rows else int(pad * 2)
    canvas = PILCanvas(W, H, _BG)
    y = pad
    for p, r, annot, bar_h in rows:
        canvas.text(pad, y + bar_h / 2 - 6,
                    f"{p['id']}  {frac_inches(measure_to_sixteenths(p['thickness']))}",
                    11, "#222222")
        x = pad + label_w
        for c in r.components:
            w_px = px(c.width, scale)
            canvas.rect(x, y, w_px, bar_h, fill=colors[c.species], outline=_OUTLINE)
            x += w_px
        canvas.text(x + 8, y + bar_h / 2 - 5, annot, 10, "#666666")
        y += bar_h + gap
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
    # Board Rip Diagram order always matches the cut list table:
    # alphabetical by species, then board id, regardless of the
    # order boards appear in the cut-spec file.
    _rips = {r.id: r for r in board_rips(project, cut_spec, tool_limits)}
    boards = sorted(cut_spec["boards"],
                    key=lambda b: (_rips[b["id"]].species, b["id"]))
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


def render_cut_board_primitive(
    b, project: Dict[str, Any], cut_spec: Dict[str, Any], tool_limits: Dict[str, Any],
    scale: float = 12.0, colors: ColorMap = DEFAULT_COLORS,
) -> bytes:
    """Single-board primitive: one cut-spec board, drawn exactly as in the
    combined strip map, on its own canvas sized to its own length.

    The combined strip map is kept as well (and as strip-map.png at the
    plan root, for a single-image copy of the cut diagram); this
    primitive is the version the plan document flows, so a tall stack
    of boards does not shrink the whole diagram to fit one page.
    """
    pad = 16
    rips = {r.id: r for r in board_rips(project, cut_spec, tool_limits)}
    r = rips[b["id"]]
    stacked = max(r.source_width, r.used + r.loss + max(r.margin, 0))
    board_len = measure_to_sixteenths(b["length"])
    W = int(px(board_len, scale) + 2 * pad)
    H = int(14 + 4 + px(stacked, scale) + 4 + 2 * pad)
    canvas = PILCanvas(W, H, _BG)
    draw_cut_board(canvas, b, project, tool_limits, (pad, pad), scale, colors, cut_spec)
    return _to_png_bytes(canvas)


def render_strip_map_primitives(
    project: Dict[str, Any], cut_spec: Dict[str, Any], tool_limits: Dict[str, Any],
    scale: float = 12.0, colors: ColorMap = DEFAULT_COLORS,
) -> Dict[str, bytes]:
    """{board_id: single-board PNG} in Board Rip Diagram order
    (alphabetical by species, then board id, matching the cut list table)."""
    _rips = {r.id: r for r in board_rips(project, cut_spec, tool_limits)}
    boards = sorted(cut_spec["boards"],
                    key=lambda b: (_rips[b["id"]].species, b["id"]))
    return {b["id"]: render_cut_board_primitive(
        b, project, cut_spec, tool_limits, scale, colors) for b in boards}


# --------------------------------------------------------------------------- #
# column glue-ups: one column diagram, and the columns side by side
# --------------------------------------------------------------------------- #

def _column_cells(project: Dict[str, Any], col_idx: int):
    """Slice cells of one grid column, top to bottom: [(sliceId, flip)]."""
    grid = project.get("sliceGrid", [])
    if not grid or col_idx >= len(grid[0]):
        raise ValueError(f"no grid column {col_idx + 1}")
    return [(row[col_idx]["sliceId"], row[col_idx].get("flip")) for row in grid]


def _column_size(project: Dict[str, Any], col_idx: int, scale: float):
    """(width_px, height_px) of one column, drawn vertically.

    A column stands vertical, as it is glued up: slices stack top to
    bottom in grid order, each slice a horizontal bar whose width is
    its length and whose height is its height. So the column width is
    the longest slice length, and its height is the sum of the slice
    heights.
    """
    cells = _column_cells(project, col_idx)
    w = max(px(slice_length(resolve_slice(project, sid)), scale) for sid, _ in cells)
    h = sum(px(resolve_slice(project, sid).height, scale) for sid, _ in cells)
    return w, h


def _draw_column_body(canvas, project, col_idx, origin, scale, colors):
    """Draw one column vertically at origin. Returns (w, h).

    Slices bleed full to the column's border: draw_slice with
    outline=None, so there are no borders around slices or
    components. Only the column itself is outlined, by the caller.
    """
    ox, oy = origin
    w, h = _column_size(project, col_idx, scale)
    y = oy
    for sid, flip in _column_cells(project, col_idx):
        bb = draw_slice(canvas, project, sid, flip, (ox, y), scale, colors, outline=None)
        y += bb.h
    return w, h


def render_column_diagram(
    project: Dict[str, Any], col_idx: int,
    scale: float = 12.0, colors: ColorMap = DEFAULT_COLORS,
) -> bytes:
    """One grid column as a diagram, vertically oriented and small.

    Title above a vertical column: the column's slices top to bottom
    in grid order, each slice a horizontal bar. Only text in the image
    is the column title. A thick outline around the column marks
    where it starts and ends, so the diagram replaces a text list of
    the column's slices.
    """
    pad = 16
    title_px = 14
    w, h = _column_size(project, col_idx, scale)
    W = int(w + 2 * pad)
    H = int(pad + title_px + 6 + h + pad)
    canvas = PILCanvas(W, H, _BG)
    canvas.text(pad, pad, f"Column {col_idx + 1}", title_px, "#222222")
    body_y = pad + title_px + 6
    _draw_column_body(canvas, project, col_idx, (pad, body_y), scale, colors)
    canvas._draw.rectangle([pad, body_y, pad + w, body_y + h], outline="#222222", width=3)
    return _to_png_bytes(canvas)


def render_columns_diagram(
    project: Dict[str, Any],
    scale: float = 12.0, colors: ColorMap = DEFAULT_COLORS,
) -> bytes:
    """The final glue-up: vertical columns side by side, not a repeat.

    No titles: the columns stand vertical, as they are glued up,
    side by side and aligned at the top, with only a small margin
    between them. Each column carries its own border; its slices bleed
    full to that border, with no borders around slices or components.
    """
    grid = project.get("sliceGrid", [])
    if not grid:
        raise ValueError("no sliceGrid to render columns from")
    ncols = len(grid[0])
    pad = 16
    gap = 6
    sizes = [_column_size(project, c, scale) for c in range(ncols)]
    col_h = max(h for _, h in sizes)
    W = int(2 * pad + sum(w for w, _ in sizes) + gap * (ncols - 1))
    H = int(2 * pad + col_h)
    canvas = PILCanvas(W, H, _BG)
    x = pad
    for c, (w, h) in enumerate(sizes):
        _draw_column_body(canvas, project, c, (x, pad), scale, colors)
        canvas._draw.rectangle([x, pad, x + w, pad + h], outline="#222222", width=3)
        x += w + gap
    return _to_png_bytes(canvas)

# --------------------------------------------------------------------------- #

def _fullest_id(panel: Dict[str, Any]) -> str:
    if "profiles" in panel:
        return f"{panel['id']}-{panel['profiles'][0]['id']}"
    return panel["id"]
