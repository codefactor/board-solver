"""Compact panel end-grain diagram: one fixed-height bar per panel, common scale."""

import io

from PIL import Image

from boardsolver.document import build_markdown
from boardsolver.geometry import px, resolve_slice, slice_length
from boardsolver.render import _fullest_id, render_panels, render_panels_compact


def test_compact_panels_is_much_shorter_than_combined(project, tool_limits):
    compact = render_panels_compact(project, tool_limits)
    combined = render_panels(project, tool_limits)
    im_c = Image.open(io.BytesIO(compact))
    im_o = Image.open(io.BytesIO(combined))
    assert im_c.height < im_o.height / 2
    # Bar height is to scale (panel thickness): pads + 30 + 30 + 32.5
    # + 2 gaps, for the fixture's ¾″, ¾″, ¹³⁄₁₆″ panels.
    assert im_c.height == int(10 * 2 + 30 + 30 + 32.5 + 2 * 6)
    # Common scale: pads + label + longest panel at 40 px/in + annotation.
    max_w = max(slice_length(resolve_slice(project, _fullest_id(p)))
                for p in project["panels"])
    assert im_c.width == int(10 * 2 + 84 + px(max_w, 40.0) + 150)


def test_document_prefers_compact_panels_over_prims(project, cut_spec, tool_limits):
    md = build_markdown(project, tool_limits, cut_spec,
                        {"finished": "f.png", "slice_map": "sm.png",
                         "panels": "p.png", "panel_faces": "pf.png",
                         "crosscut": "cc.png", "strip_map": "s.png",
                         "panels_compact": "images/panels-compact-abc.png",
                         "panel_prims": {"P": "panel-P.png"}})
    assert "images/panels-compact-abc.png" in md
    assert "panel-P.png" not in md
