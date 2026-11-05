"""Human-facing formatting: integer sixteenths -> unicode inch strings.

Kept separate from geometry so the domain stays in integer sixteenths and only
the presentation edge produces strings like ``7¼″`` or ``16⅛″``.
"""

from __future__ import annotations

from .geometry import Sixteenths, measure_to_sixteenths

# Exact unicode vulgar fractions for the sixteenth values that reduce to them.
_VULGAR = {
    (1, 16): "¹⁄₁₆",
    (1, 8): "⅛",
    (3, 16): "³⁄₁₆",
    (1, 4): "¼",
    (5, 16): "⁵⁄₁₆",
    (3, 8): "⅜",
    (7, 16): "⁷⁄₁₆",
    (1, 2): "½",
    (9, 16): "⁹⁄₁₆",
    (5, 8): "⅝",
    (11, 16): "¹¹⁄₁₆",
    (3, 4): "¾",
    (13, 16): "¹³⁄₁₆",
    (7, 8): "⅞",
    (15, 16): "¹⁵⁄₁₆",
}


def _reduce(sixteenths_part: int):
    """Reduce a 0..15 sixteenths remainder to a (num, den) in lowest terms."""
    num, den = sixteenths_part, 16
    while num % 2 == 0 and den % 2 == 0:
        num //= 2
        den //= 2
    return num, den


def frac_inches(s: Sixteenths, *, quote: bool = True, ascii: bool = False) -> str:
    """Format integer sixteenths as an inch string.

    ``118 -> '7⅜"'`` style. ``quote`` appends the inch mark. Unicode by default
    (vulgar/superscript fractions + ″). Diagram labels use this default too:
    this project's rendering fonts are DejaVu (PNG diagrams via PIL, PDF via
    reportlab), and DejaVu covers every glyph used here, so the old
    ``ascii=True`` diagram workaround (slash fractions, plain quote) was
    unnecessary and inconsistent with the Markdown tables. ``ascii=True``
    remains only as a fallback for a surface whose font lacks those glyphs.
    """
    # Negatives format by sign + magnitude: divmod(-1, 16) is (-1, 15),
    # which would otherwise render -1/16 as "-1¹⁵⁄₁₆", read as -1 15/16.
    sign = "-" if s < 0 else ""
    whole, part = divmod(abs(s), 16)
    if part == 0:
        body = f"{sign}{whole}"
    elif ascii:
        num, den = _reduce(part)
        body = f"{sign}{num}/{den}" if whole == 0 else f"{sign}{whole} {num}/{den}"
    else:
        vulgar = _VULGAR[_reduce(part)]
        body = f"{sign}{vulgar}" if whole == 0 else f"{sign}{whole}{vulgar}"
    if not quote:
        return body
    return f'{body}"' if ascii else f"{body}\u2033"


def frac_measure(m, *, quote: bool = True, ascii: bool = False) -> str:
    """Format a ``[whole, sixteenths]`` measurement tuple as an inch string."""
    return frac_inches(measure_to_sixteenths(m), quote=quote, ascii=ascii)
