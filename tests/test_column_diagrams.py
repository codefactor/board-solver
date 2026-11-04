"""Column glue-up diagrams: one column, and all columns side by side.

Synthetic project only (tests must stay decoupled from production specs):
a 2-row x 2-column grid, each slice a single species stripe.
"""
from boardsolver.geometry import measure_to_sixteenths, px
from boardsolver.render import (
    _column_cells,
    _column_size,
    render_column_diagram,
    render_columns_diagram,
)


def _project():
    return {
        "components": [
            {"id": "A", "species": "Cherry", "width": [2, 0], "thickness": [0, 12]},
            {"id": "B", "species": "Walnut", "width": [2, 0], "thickness": [0, 12]},
        ],
        "panels": [
            {"id": "P", "thickness": [0, 12], "profiles": [
                {"id": "L", "slices": 1}, {"id": "R", "slices": 1}],
             "components": [{"type": "A"}, {"type": "B", "maxProfile": 1}]},
        ],
        "sliceGrid": [
            [{"sliceId": "P-L"}, {"sliceId": "P-R"}],
            [{"sliceId": "P-L"}, {"sliceId": "P-R"}],
        ],
        "sliceDepth": [1, 0],
        "finishedThickness": [0, 12],
        "batch": 1,
    }


def test_column_cells_are_numbered_not_left_right():
    proj = _project()
    assert _column_cells(proj, 0) == [("P-L", None), ("P-L", None)]
    assert _column_cells(proj, 1) == [("P-R", None), ("P-R", None)]


def test_column_size():
    proj = _project()
    # Vertically oriented: width = P-L length A 2" + B 2" = 4",
    # height = 2 rows x 3/4" = 1 1/2".
    w, h = _column_size(proj, 0, 16.0)
    assert w == px(measure_to_sixteenths([4, 0]), 16.0)
    assert h == px(measure_to_sixteenths([1, 8]), 16.0)


def test_column_diagrams_render_png():
    proj = _project()
    for png in (render_column_diagram(proj, 0), render_column_diagram(proj, 1),
                render_columns_diagram(proj)):
        assert png[:8] == b"\x89PNG\r\n\x1a\n"
        assert len(png) > 100


def test_image_display_size_true_size_not_stretched():
    from boardsolver.cutcheck import _image_display_size
    # Small diagram: 224x135 px prints at 224x135 pt, not full 540 pt width.
    w, h = _image_display_size(224, 135, 540.0, 720.0)
    assert (w, h) == (224.0, 135.0)
    # Two such diagrams side by side fit in a 540 pt column.
    assert 224 + 12 + 224 <= 540
    # Large diagram: scaled down to column width, not true size.
    w, h = _image_display_size(1200, 100, 540.0, 720.0)
    assert w == 540.0
    assert h == 45.0

def test_final_glue_up_is_titleless_vertical_columns_with_small_margin():
    from PIL import Image
    import io
    proj = _project()
    png = render_columns_diagram(proj, scale=12.0)
    im = Image.open(io.BytesIO(png))
    # No titles, columns side by side, top-aligned: widths 4" x 12
    # = 48 px and 2" x 12 = 24 px, heights both 1 1/2" x 12 = 18 px,
    # so W = 32 + 48 + 6 + 24 = 110, H = 32 + 18 = 50.
    assert im.size == (110, 50)
    # Gap column between columns is background, not a title or border.
    assert im.getpixel((16 + 48 + 3, 25)) == (255, 255, 255)
    # Column border present at the top edge of the first column.
    assert im.getpixel((25, 16)) != (255, 255, 255)
