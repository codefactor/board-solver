"""Board-solver Round 1 library: pure geometry helpers + drawing primitives.

Internal measurement representation is an integer count of sixteenths of an inch
(``Sixteenths``). Serialized form is the schema ``measurement`` tuple
``[whole_inches, sixteenths]``. Conversions live in :mod:`boardsolver.geometry`.

No file I/O, no versioning, no solver, no Markdown document assembly — those are
later rounds. Drawing primitives render onto an abstract Canvas (see
:mod:`boardsolver.canvas`); a PIL-backed canvas is provided for producing real
images.
"""

from .geometry import (
    Sixteenths,
    Measurement,
    ResolvedComponent,
    ResolvedSlice,
    measure_to_inches,
    inches_to_measure,
    measure_to_sixteenths,
    sixteenths_to_measure,
    resolve_slice,
    slice_length,
)
from .colors import ColorMap, DEFAULT_COLORS
from .canvas import Canvas, BoundingBox, RecordingCanvas
from .draw import draw_slice, draw_panel, draw_cut_strip, draw_cut_board
from .format import frac_inches, frac_measure

__all__ = [
    "Sixteenths",
    "Measurement",
    "ResolvedComponent",
    "ResolvedSlice",
    "measure_to_inches",
    "inches_to_measure",
    "measure_to_sixteenths",
    "sixteenths_to_measure",
    "resolve_slice",
    "slice_length",
    "ColorMap",
    "DEFAULT_COLORS",
    "Canvas",
    "BoundingBox",
    "RecordingCanvas",
    "draw_slice",
    "draw_panel",
    "draw_cut_strip",
    "draw_cut_board",
    "frac_inches",
    "frac_measure",
]
