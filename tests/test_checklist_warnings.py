"""Checklist warning surfacing: negative offcuts, over-rip diagram hatch.

Synthetic only (tests must stay decoupled from production specs):
a negative offcut is an overflow and must carry a warning glyph,
and an over-rip end-grain diagram must crosshatch in yellow the
portion past the board's edge, so strips running past it are visible.
"""

import io

from PIL import Image

from boardsolver.cutcheck import (
    _margin_fmt,
    _offcut_fmt,
    _render_endgrain_png,
    _rip_margins,
    _running_margin_cell,
)
from boardsolver.derive import BoardRip, rip_margin_class
from boardsolver.pdf import md_inline_to_xml


def test_negative_offcut_gets_warning_glyph():
    assert _offcut_fmt(-1) == "-¹⁄₁₆″ ⚠️"
    assert _offcut_fmt(0) == "0″ ⚠️"
    assert _offcut_fmt(16) == "1″"


def test_running_rip_margin_goes_negative_mid_board():
    # BM1A in the edge-all showcase: 6 in board, strips 1 1/2 in x4,
    # 3/4 in, 1/4 in; plane loss 1/16 in and saw kerf 1/8 in per rip.
    strips = [{"width": [1, 8]} for _ in range(4)] + [{"width": [0, 12]}, {"width": [0, 4]}]
    assert _rip_margins(96, strips, plane_loss=1, saw_kerf=2) == [69, 42, 15, -12, -27, -34]


def test_last_rip_small_negative_is_shave_larger_is_over():
    # Saw kerf is 2 sixteenths (1/8 in).
    assert rip_margin_class(-1, 2) == "shave"
    assert rip_margin_class(-2, 2) == "over"
    assert rip_margin_class(-7, 2) == "over"
    assert rip_margin_class(0, 2) == ""
    assert rip_margin_class(4, 2) == ""


def test_running_margin_clamps_only_on_last_rip():
    # A small negative running margin on an earlier rip stays
    # negative (error: later rips need material that isn't there);
    # the same value on the last rip shows as 0 (shave warning).
    assert _running_margin_cell(-1, 2, is_last=False) == "-¹⁄₁₆″ ⚠️"
    assert _running_margin_cell(-1, 2, is_last=True) == "0″ ⚠️"
    assert _running_margin_cell(-7, 2, is_last=True) == "-⁷⁄₁₆″ ⚠️"


def test_small_negative_margin_displays_as_zero():
    # Kerf is 2 sixteenths (1/8 in): -1/16 in displays as 0, -1/8 in
    # (exactly one kerf) and larger negatives stay negative.
    assert _margin_fmt(-1, 2) == "0″ ⚠️"
    assert _margin_fmt(-2, 2) == "-⅛″ ⚠️"
    assert _margin_fmt(-7, 2) == "-⁷⁄₁₆″ ⚠️"
    assert _margin_fmt(0, 2) == "0″ ⚠️"
    assert _margin_fmt(16, 2) == "1″"


def test_every_warning_glyph_gets_yellow_background():
    xml = md_inline_to_xml("**⚠️ ERROR — test.**")
    assert '<font backColor="#FFFF00"><b>⚠</b></font>' in xml
    assert md_inline_to_xml("plain text, no glyph") == "plain text, no glyph"


def test_over_rip_endgrain_has_yellow_crosshatch_past_board_edge():
    project = {"boards": [{"id": "B1", "species": "Cherry", "thickness": [0, 13]}]}
    cut_spec = {"boards": []}
    board = {"id": "X", "source": "B1", "length": [38, 14],
             "strips": [{"width": [1, 8], "cuts": [[19, 6]]} for _ in range(4)]}
    # Board 6 in wide, strips 4 x 1 9/16 in rip size + kerfs = 6 3/4 in:
    # over-rip by 3/4 in, margin negative.
    rip = BoardRip(id="X", origin="source:B1", species="Cherry",
                   buy_required=False, length=622, source_width=96,
                   used=96, loss=12, margin=-12, strips=board["strips"])
    png = _render_endgrain_png(project, cut_spec, board, rip, saw_kerf=2, plane_loss=1)
    im = Image.open(io.BytesIO(png))
    # total = rip sizes (4 x 25) + kerfs (4 x 2) = 108; board edge at
    # 96/108 of 1200 px = 1067, inside the grain row (y 54..81).
    # Past the edge the grain row is yellow crosshatch (yellow
    # background or dark diagonal); before it, it is still species color.
    _yellow = {(255, 255, 0), (51, 51, 51)}
    assert im.getpixel((1080, 67)) in _yellow
    assert im.getpixel((1080, 90)) in _yellow
    assert im.getpixel((1060, 67)) not in _yellow
