"""Drawing-primitive tests.

Two layers:
  * geometry assertions against a RecordingCanvas (bbox + draw-call math), and
  * real PNGs rendered with PILCanvas into tests/_artifacts/ for visual review.

The PNGs are inspected by a human/agent as part of verifying Round 1; the
assertions here guard the numbers behind the pixels.
"""

from __future__ import annotations

from boardsolver.canvas import PILCanvas, RecordingCanvas
from boardsolver.colors import DEFAULT_COLORS
from boardsolver.draw import (
    draw_cut_board,
    draw_cut_strip,
    draw_panel,
    draw_slice,
)
from boardsolver.geometry import measure_to_sixteenths, px, resolve_slice, slice_length

SCALE = 40.0


# --------------------------------------------------------------------------- #
# draw_slice
# --------------------------------------------------------------------------- #

def test_draw_slice_bbox_matches_slice_length_and_height(project):
    rc = RecordingCanvas()
    r = resolve_slice(project, "R-R")
    bb = draw_slice(rc, project, "R-R", "H", (0, 0), SCALE, DEFAULT_COLORS)
    # R-R = [M, W] reversed; height = sliceStrips width 1/4"
    assert bb.w == px(slice_length(r), SCALE)
    assert bb.h == px(r.height, SCALE)
    assert bb.h == px(measure_to_sixteenths([0, 4]), SCALE)
    # R-R drops trailing D: M(3/4) + W(3) = 3 3/4"
    assert bb.w == px(measure_to_sixteenths([3, 12]), SCALE)


def test_draw_slice_flip_reverses_component_order(project):
    base = RecordingCanvas()
    flip = RecordingCanvas()
    draw_slice(base, project, "R-R", None, (0, 0), SCALE)
    draw_slice(flip, project, "R-R", "H", (0, 0), SCALE)
    base_fills = [r.fill for r in base.rects]
    flip_fills = [r.fill for r in flip.rects]
    assert flip_fills == list(reversed(base_fills))


# --------------------------------------------------------------------------- #
# draw_panel
# --------------------------------------------------------------------------- #

def test_draw_panel_P_bbox(project):
    rc = RecordingCanvas()
    bb = draw_panel(rc, project, "P", (0, 0), SCALE)
    # fullest profile P-L: 5 cells, length 4"; cell height = panel thickness 3/4"
    assert bb.w == px(measure_to_sixteenths([4, 0]), SCALE)
    assert len(rc.rects) == 5
    cell_h = px(measure_to_sixteenths([0, 12]), SCALE)
    assert all(r.h == cell_h for r in rc.rects)
    assert bb.h > cell_h  # annotation line adds height
    assert rc.texts and rc.texts[0].s == "Slice Count: 20 - Regions [L=10, R=10]"


def test_draw_panel_no_annotation_bbox_is_cell_height(project):
    rc = RecordingCanvas()
    bb = draw_panel(rc, project, "P", (0, 0), SCALE, annotate=False)
    assert bb.h == px(measure_to_sixteenths([0, 12]), SCALE)
    assert rc.texts == []


# --------------------------------------------------------------------------- #
# draw_cut_strip: per-cut kerf + offcut tail
# --------------------------------------------------------------------------- #

def test_draw_cut_strip_single_cut_on_longer_board():
    # width 1 1/2", one 34" cut, board drawn at 48 1/8"; miterKerf 1/8".
    rc = RecordingCanvas()
    strip = {"width": [1, 8], "cuts": [[34, 0]]}
    board_len = measure_to_sixteenths([48, 2])
    bb = draw_cut_strip(
        rc, strip, "Walnut", (0, 0), SCALE, DEFAULT_COLORS,
        miter_kerf=2, board_length=board_len,
    )
    # cells drawn: [cut, kerf, offcut] = 3 rects
    assert len(rc.rects) == 3
    cut_px, kerf_px, offcut = rc.rects
    assert cut_px.w == px(measure_to_sixteenths([34, 0]), SCALE)
    assert kerf_px.w == px(2, SCALE)  # one miter kerf
    # offcut = 48 1/8 - 34 - 1/8 = 14
    assert offcut.w == px(measure_to_sixteenths([14, 0]), SCALE)
    assert bb.w == px(board_len, SCALE)


def test_draw_cut_strip_two_cuts_last_reaches_end_has_one_kerf():
    rc = RecordingCanvas()
    # 34 + kerf(1/8) + 13 7/8 = 48"; the second piece runs to the board end, so
    # only the first cut is a crosscut => 1 kerf. [cut, kerf, cut] = 3 rects.
    strip = {"width": [0, 12], "cuts": [[34, 0], [13, 14]]}
    board_len = measure_to_sixteenths([48, 0])
    bb = draw_cut_strip(
        rc, strip, "Cherry", (0, 0), SCALE, DEFAULT_COLORS,
        miter_kerf=2, board_length=board_len,
    )
    assert len(rc.rects) == 3  # cut, kerf, cut (no trailing kerf, no offcut)
    assert rc.rects[1].fill == "#9a8f76"  # the single kerf stripe
    assert bb.w == px(board_len, SCALE)


def test_draw_cut_strip_full_length_cut_has_no_kerf():
    # A single cut equal to the full board length is the whole strip, not a
    # crosscut => no kerf stripe, no offcut, just one cell.
    rc = RecordingCanvas()
    strip = {"width": [3, 0], "cuts": [[27, 8]]}
    board_len = measure_to_sixteenths([27, 8])
    bb = draw_cut_strip(
        rc, strip, "Walnut", (0, 0), SCALE, DEFAULT_COLORS,
        miter_kerf=2, board_length=board_len,
    )
    assert len(rc.rects) == 1  # just the strip cell, no kerf
    assert bb.w == px(board_len, SCALE)


def test_draw_cut_strip_no_cuts_is_single_cell():
    rc = RecordingCanvas()
    strip = {"width": [3, 0]}
    board_len = measure_to_sixteenths([27, 8])
    bb = draw_cut_strip(
        rc, strip, "Walnut", (0, 0), SCALE, miter_kerf=2, board_length=board_len
    )
    assert len(rc.rects) == 1
    assert bb.w == px(board_len, SCALE)


# --------------------------------------------------------------------------- #
# draw_cut_board: species tracing + loss + ordered margin children
# --------------------------------------------------------------------------- #

def test_draw_cut_board_traces_source_species(project, tool_limits, cut_spec):
    rc = RecordingCanvas()
    iw1a = next(b for b in cut_spec["boards"] if b["id"] == "IW1A")
    draw_cut_board(rc, iw1a, project, tool_limits, (0, 0), SCALE, DEFAULT_COLORS, cut_spec)
    # IW1A sources IW1 (Walnut) => strip cells use the walnut color.
    walnut = DEFAULT_COLORS["Walnut"]
    assert any(r.fill == walnut for r in rc.rects)
    assert rc.texts and rc.texts[0].s.startswith("IW1A")
    assert "(" in rc.texts[0].s and ")" in rc.texts[0].s


def test_draw_cut_board_buy_board_has_gray_title(project, tool_limits, cut_spec):
    rc = RecordingCanvas()
    ghx = next(b for b in cut_spec["boards"] if b["id"] == "GHX")
    draw_cut_board(rc, ghx, project, tool_limits, (0, 0), SCALE, DEFAULT_COLORS, cut_spec)
    assert rc.texts[0].s.startswith("GHX")
    assert "(Not Available)" in rc.texts[0].s  # ghost board has no stock
    assert rc.texts[0].color == "#888888"  # buy-required gray title


def test_draw_cut_board_buy_board_no_false_alert(project, tool_limits, cut_spec):
    # A bought board is sized to strips + its own loss => margin is exactly 0,
    # so there must be no alert band.
    rc = RecordingCanvas()
    ghx = next(b for b in cut_spec["boards"] if b["id"] == "GHX")
    draw_cut_board(rc, ghx, project, tool_limits, (0, 0), SCALE, DEFAULT_COLORS, cut_spec)
    from boardsolver.draw import _ALERT_COLOR
    assert not any(r.fill == _ALERT_COLOR for r in rc.rects)


def test_source_remainder_slab_width_is_parent_leftover():
    # Parent BIGA: 10" source, one 2" strip, loss = 1*(1/8+1/16)=3/16.
    # Leftover slab = 10 - 2 - 3/16 = 7 13/16". A child's source width must equal that.
    from boardsolver.draw import _resolve_source
    project = {
        "components": [], "panels": [],
        "boards": [{"id": "BIG", "species": "Walnut", "length": [48, 0],
                    "width": [10, 0], "thickness": [0, 13]}],
    }
    limits = {"sawKerf": [0, 2], "miterKerf": [0, 2], "minPlaneLoss": [0, 1]}
    cut_spec = {
        "boards": [
            {"id": "BIGA", "source": "BIG", "length": [48, 0],
             "strips": [{"width": [2, 0], "cuts": [[48, 0]]}]},
            {"id": "BIGB", "sourceRemainder": "BIGA", "length": [20, 0],
             "strips": [{"width": [7, 0], "cuts": [[20, 0]]}]},
        ],
    }
    child = cut_spec["boards"][1]
    species, width, buy = _resolve_source(child, project, cut_spec, limits)
    assert species == "Walnut"
    assert buy is False
    # 7 13/16" = 7*16 + 13 = 125 sixteenths
    assert width == measure_to_sixteenths([7, 13])


def test_draw_cut_strip_offcut_component_tail_is_species_not_lightened():
    from boardsolver.colors import lighten
    rc = RecordingCanvas()
    strip = {"width": [0, 12], "cuts": [[10, 0]], "offcutComponent": True}
    board_len = measure_to_sixteenths([20, 0])
    draw_cut_strip(rc, strip, "Cherry", (0, 0), SCALE, DEFAULT_COLORS,
                   miter_kerf=2, board_length=board_len)
    species = DEFAULT_COLORS["Cherry"]
    # [cut, kerf, offcut-as-component]
    tail = rc.rects[-1]
    assert tail.fill == species  # used component, not waste
    assert tail.fill != lighten(species)


def test_draw_cut_strip_waste_offcut_is_lightened():
    from boardsolver.colors import lighten
    rc = RecordingCanvas()
    strip = {"width": [0, 12], "cuts": [[10, 0]]}  # no offcutComponent => waste
    board_len = measure_to_sixteenths([20, 0])
    draw_cut_strip(rc, strip, "Cherry", (0, 0), SCALE, DEFAULT_COLORS,
                   miter_kerf=2, board_length=board_len)
    tail = rc.rects[-1]
    assert tail.fill == lighten(DEFAULT_COLORS["Cherry"])


def test_draw_cut_board_ordered_margin_children():
    # Synthetic: a wide source board ripped into one thin strip, leaving a big
    # margin slab consumed by two sourceRemainder children in order.
    project = {
        "components": [],
        "panels": [],
        "boards": [
            {"id": "BIG", "species": "Walnut", "length": [48, 0],
             "width": [10, 0], "thickness": [0, 13]},
        ],
    }
    tool_limits = {"limits": {"sawKerf": [0, 2], "miterKerf": [0, 2], "minPlaneLoss": [0, 1]}}
    cut_spec = {
        "boards": [
            {"id": "BIGA", "source": "BIG", "length": [48, 0],
             "strips": [{"width": [2, 0], "cuts": [[48, 0]]}]},
            {"id": "BIGB", "sourceRemainder": "BIGA", "length": [20, 0],
             "strips": [{"width": [7, 0], "cuts": [[20, 0]]}]},
            {"id": "BIGC", "sourceRemainder": "BIGA", "length": [15, 0],
             "strips": [{"width": [7, 0], "cuts": [[15, 0]]}]},
        ],
    }
    rc = RecordingCanvas()
    biga = cut_spec["boards"][0]
    draw_cut_board(rc, biga, project, tool_limits, (0, 0), SCALE, DEFAULT_COLORS, cut_spec)
    # Two ghost labels, in document order.
    ghost_labels = [t.s for t in rc.texts if t.s in ("BIGB", "BIGC")]
    assert ghost_labels == ["BIGB", "BIGC"]
    # Ghost rects use the ghost color; there are two of them.
    from boardsolver.draw import _GHOST_COLOR
    ghosts = [r for r in rc.rects if r.fill == _GHOST_COLOR]
    assert len(ghosts) == 2
    # First ghost is 20" long, second 15".
    assert ghosts[0].w == px(measure_to_sixteenths([20, 0]), SCALE)
    assert ghosts[1].w == px(measure_to_sixteenths([15, 0]), SCALE)


def test_draw_cut_board_negative_margin_alert():
    # Strips wider than the source => negative margin => alert band.
    project = {
        "components": [], "panels": [],
        "boards": [{"id": "SMALL", "species": "Cherry", "length": [30, 0],
                    "width": [3, 0], "thickness": [0, 13]}],
    }
    tool_limits = {"limits": {"sawKerf": [0, 2], "miterKerf": [0, 2], "minPlaneLoss": [0, 1]}}
    board = {"id": "SMALLA", "source": "SMALL", "length": [30, 0],
             "strips": [{"width": [2, 8], "cuts": [[30, 0]]},
                        {"width": [2, 8], "cuts": [[30, 0]]}]}
    rc = RecordingCanvas()
    draw_cut_board(rc, board, project, tool_limits, (0, 0), SCALE)
    from boardsolver.draw import _ALERT_COLOR
    assert any(r.fill == _ALERT_COLOR for r in rc.rects)


# --------------------------------------------------------------------------- #
# Real-image renderers (visually verified by inspecting the PNGs)
# --------------------------------------------------------------------------- #

def test_render_finished_board_grid_png(project, out_dir):
    """Render the full sliceGrid as a plaid board image for visual review."""
    grid = project["sliceGrid"]
    scale = 26.0
    pad = 20
    # row width = sum of the first row's slice lengths (true grid: all rows equal)
    row_w = sum(
        px(slice_length(resolve_slice(project, cell["sliceId"])), scale)
        for cell in grid[0]
    )
    def row_h(row):
        r0 = resolve_slice(project, row[0]["sliceId"])
        return px(r0.height, scale)
    total_h = sum(row_h(row) for row in grid)
    canvas = PILCanvas(int(row_w + 2 * pad), int(total_h + 2 * pad))
    y = pad
    for row in grid:
        x = pad
        h = 0
        for cell in row:
            bb = draw_slice(canvas, project, cell["sliceId"], cell.get("flip"),
                            (x, y), scale, DEFAULT_COLORS)
            x += bb.w
            h = bb.h
        y += h
    canvas.save(str(out_dir / "finished-board.png"))


def test_render_panels_png(project, out_dir):
    scale = 40.0
    pad = 20
    gap = 24
    panels = project["panels"]
    widths = [px(slice_length(resolve_slice(project, _fullest(p))), scale) for p in panels]
    heights = [px(measure_to_sixteenths(p["thickness"]), scale) for p in panels]
    W = int(max(widths) + 2 * pad)
    H = int(sum(heights) + gap * len(panels) + 2 * pad)
    canvas = PILCanvas(W, H)
    y = pad
    for p in panels:
        bb = draw_panel(canvas, project, p["id"], (pad, y + 14), scale, DEFAULT_COLORS)
        canvas.text(pad, y, f"Panel {p['id']}", 13, "#222222")
        y += bb.h + gap
    canvas.save(str(out_dir / "panels.png"))


def test_render_cut_boards_png(project, tool_limits, cut_spec, out_dir):
    scale = 12.0
    pad = 16
    gap = 30
    canvas = PILCanvas(900, 1700)
    y = pad
    for board in cut_spec["boards"]:
        bb = draw_cut_board(canvas, board, project, tool_limits,
                            (pad, y), scale, DEFAULT_COLORS, cut_spec)
        y += bb.h + gap
    canvas.save(str(out_dir / "cut-boards.png"))


def test_render_margin_children_png(out_dir):
    """Render the synthetic sourceRemainder scenario so the ghost pieces show."""
    project = {
        "components": [], "panels": [],
        "boards": [{"id": "BIG", "species": "Walnut", "length": [48, 0],
                    "width": [10, 0], "thickness": [0, 13]}],
    }
    tool_limits = {"limits": {"sawKerf": [0, 2], "miterKerf": [0, 2], "minPlaneLoss": [0, 1]}}
    cut_spec = {
        "boards": [
            {"id": "BIGA", "source": "BIG", "length": [48, 0],
             "strips": [{"width": [2, 0], "cuts": [[48, 0]]}]},
            {"id": "BIGB", "sourceRemainder": "BIGA", "length": [20, 0],
             "strips": [{"width": [7, 0], "cuts": [[20, 0]]}]},
            {"id": "BIGC", "sourceRemainder": "BIGA", "length": [15, 0],
             "strips": [{"width": [7, 0], "cuts": [[15, 0]]}]},
        ],
    }
    scale = 14.0
    canvas = PILCanvas(int(px(measure_to_sixteenths([48, 0]), scale) + 40),
                       int(px(measure_to_sixteenths([13, 0]), scale) + 60))
    draw_cut_board(canvas, cut_spec["boards"][0], project, tool_limits,
                   (16, 16), scale, DEFAULT_COLORS, cut_spec)
    canvas.save(str(out_dir / "margin-children.png"))


def test_render_single_strip_kerf_png(out_dir):
    """Zoomed single strip so the per-cut kerf stripes + offcut are visible."""
    scale = 12.0
    pad = 10
    strip = {"width": [1, 8], "cuts": [[12, 0], [12, 0], [10, 0]]}
    board_len = measure_to_sixteenths([48, 0])
    W = int(px(board_len, scale) + 2 * pad)
    H = int(px(measure_to_sixteenths([1, 8]), scale) + 2 * pad)
    canvas = PILCanvas(W, H)
    draw_cut_strip(canvas, strip, "Walnut", (pad, pad), scale, DEFAULT_COLORS,
                   miter_kerf=2, board_length=board_len)
    canvas.save(str(out_dir / "single-strip-kerf.png"))


def _fullest(panel):
    if "profiles" in panel:
        return f"{panel['id']}-{panel['profiles'][0]['id']}"
    return panel["id"]
