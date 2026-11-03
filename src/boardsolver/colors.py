"""Species -> CSS color mapping. Not part of the schema (a drawing concern)."""

from __future__ import annotations

from typing import Dict

ColorMap = Dict[str, str]

# Default palette cited in docs/function-specs.md.
DEFAULT_COLORS: ColorMap = {
    "Cherry": "#b87143",
    "Walnut": "#604331",
    "Brown Maple": "#e5d2a5",
}

# A fixed set of 20 bright, saturated colors for keying slice ids in the
# slice-map diagram. Chosen to stand out over wood tones (cream/orange/brown)
# and over white. Assigned to slice ids in first-appearance order; the order is
# stable so a given project always maps the same ids to the same colors.
SLICE_PALETTE = [
    "#e6194b",  # red
    "#3cb44b",  # green
    "#4363d8",  # blue
    "#f58231",  # orange
    "#911eb4",  # purple
    "#42d4f4",  # cyan
    "#f032e6",  # magenta
    "#bfef45",  # lime
    "#fabed4",  # pink
    "#469990",  # teal
    "#dcbeff",  # lavender
    "#9a6324",  # brown-accent
    "#fffac8",  # pale yellow
    "#800000",  # maroon
    "#aaffc3",  # mint
    "#808000",  # olive
    "#ffd8b1",  # apricot
    "#000075",  # navy
    "#e6beff",  # light purple
    "#ff4500",  # orange-red
]


def slice_color_map(slice_ids) -> ColorMap:
    """Map slice ids to SLICE_PALETTE colors in first-appearance order.

    Raises ValueError if there are more distinct ids than palette colors.
    """
    seen = []
    for sid in slice_ids:
        if sid not in seen:
            seen.append(sid)
    if len(seen) > len(SLICE_PALETTE):
        raise ValueError(
            f"{len(seen)} distinct slice ids exceed the {len(SLICE_PALETTE)}-color palette"
        )
    return {sid: SLICE_PALETTE[i] for i, sid in enumerate(seen)}


def lighten(css_hex: str, amount: float = 0.55) -> str:
    """Lighten a ``#rrggbb`` color toward white by ``amount`` in [0, 1].

    Used to draw an offcut (waste) tail as a washed-out version of the board's
    species color.
    """
    s = css_hex.lstrip("#")
    if len(s) != 6:
        raise ValueError(f"expected #rrggbb, got {css_hex!r}")
    r, g, b = (int(s[i : i + 2], 16) for i in (0, 2, 4))
    r = round(r + (255 - r) * amount)
    g = round(g + (255 - g) * amount)
    b = round(b + (255 - b) * amount)
    return f"#{r:02x}{g:02x}{b:02x}"


def _rgb(css_hex: str):
    s = css_hex.lstrip("#")
    if len(s) != 6:
        raise ValueError(f"expected #rrggbb, got {css_hex!r}")
    return tuple(int(s[i : i + 2], 16) for i in (0, 2, 4))


def relative_luminance(css_hex: str) -> float:
    """Perceived luminance of a ``#rrggbb`` color in [0, 1] (Rec. 709 weights)."""
    r, g, b = _rgb(css_hex)
    return (0.2126 * r + 0.7152 * g + 0.0722 * b) / 255


def text_on(css_hex: str, *, dark: str = "#111111", light: str = "#ffffff",
            threshold: float = 0.6) -> str:
    """Pick a readable text color for text drawn on ``css_hex``.

    Returns ``dark`` over light backgrounds and ``light`` over dark ones, based
    on the background's relative luminance.
    """
    return dark if relative_luminance(css_hex) >= threshold else light
