"""Compact crosscut diagram: one fixed-height bar per raw board, common scale."""

import io

from PIL import Image

from boardsolver.render import render_crosscut_blanks, render_crosscut_compact


def test_compact_diagram_is_much_shorter_and_common_scale(project, cut_spec, tool_limits):
    compact = render_crosscut_compact(project, cut_spec, tool_limits)
    combined = render_crosscut_blanks(project, cut_spec, tool_limits)
    im_c = Image.open(io.BytesIO(compact))
    im_o = Image.open(io.BytesIO(combined))
    # 4 raw boards + 1 ghost buy board in the fixture: compact height
    # is one thin bar + gap per row, less than half the old combined height.
    assert im_c.height < im_o.height / 2
    # Common scale + annotation column: pads + label + longest board
    # at 7 px/in + annotation column.
    assert im_c.width == int(10 * 2 + 118 + (48 * 7) + 110)
    # Fixed bar height: total height is pads + 5 * (18 + 6) - 6.
    assert im_c.height == int(10 * 2 + 5 * (18 + 6) - 6)


def test_compact_diagram_negative_offcut_is_red_split_not_extra_piece(project, cut_spec, tool_limits):
    # Make IC1A demand 50" from a 48" raw board: a 2" negative offcut.
    import copy
    cs = copy.deepcopy(cut_spec)
    cs["boards"][0]["length"] = [50, 0]
    data = render_crosscut_compact(project, cs, tool_limits)
    im = Image.open(io.BytesIO(data)).convert("RGB")
    px = list(im.getdata())
    # Red pixels for the 2" shortfall portion, not a separate red tail
    # on top of a full 50" blank (which would double-count it).
    red = sum(1 for r, g, b in px if r > 180 and g < 80 and b < 80)
    assert red > 0
    # Width covers the 50" demand + label + annotation, not demand + overflow.
    assert im.width == int(10 * 2 + 118 + (50 * 7) + 110)
