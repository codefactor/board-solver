"""Abstract Canvas seam + a recording fake + a PIL-backed real canvas.

Primitives draw through the :class:`Canvas` protocol (``rect`` + ``text``) and
never choose their own position beyond the given origin. Each primitive returns
a :class:`BoundingBox` in pixels describing what it drew.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional, Protocol, Tuple


@dataclass(frozen=True)
class BoundingBox:
    x: float
    y: float
    w: float
    h: float


class Canvas(Protocol):
    def rect(
        self,
        x: float,
        y: float,
        w: float,
        h: float,
        fill: Optional[str],
        outline: Optional[str] = None,
    ) -> None: ...

    def hatch_rect(
        self,
        x: float,
        y: float,
        w: float,
        h: float,
        base_fill: str,
        hatch_color: str,
        outline: Optional[str] = None,
        spacing: float = 7,
        width: float = 1,
    ) -> None: ...

    def text(self, x: float, y: float, s: str, size: float, color: str) -> None: ...


# --------------------------------------------------------------------------- #
# Recording fake (for geometry assertions in tests)
# --------------------------------------------------------------------------- #

@dataclass
class RectCall:
    x: float
    y: float
    w: float
    h: float
    fill: Optional[str]
    outline: Optional[str]


@dataclass
class TextCall:
    x: float
    y: float
    s: str
    size: float
    color: str


@dataclass
class HatchCall:
    x: float
    y: float
    w: float
    h: float
    base_fill: str
    hatch_color: str
    outline: Optional[str]


@dataclass
class RecordingCanvas:
    rects: List[RectCall] = field(default_factory=list)
    texts: List[TextCall] = field(default_factory=list)
    hatches: List[HatchCall] = field(default_factory=list)

    def rect(self, x, y, w, h, fill, outline=None):
        self.rects.append(RectCall(x, y, w, h, fill, outline))

    def hatch_rect(self, x, y, w, h, base_fill, hatch_color, outline=None,
                   spacing=7, width=1):
        # Recorded as a rect with the base fill, plus a hatch entry,
        # so geometry tests can assert both the band and its hatch.
        self.rects.append(RectCall(x, y, w, h, base_fill, outline))
        self.hatches.append(HatchCall(x, y, w, h, base_fill, hatch_color, outline))

    def text(self, x, y, s, size, color):
        self.texts.append(TextCall(x, y, s, size, color))


# --------------------------------------------------------------------------- #
# PIL-backed real canvas (for producing actual images)
# --------------------------------------------------------------------------- #

class PILCanvas:
    """A real raster canvas. Call :meth:`save` to write a PNG.

    Coordinates are in pixels with the origin at the top-left, matching the
    primitive contract.
    """

    def __init__(self, width: int, height: int, background: str = "#ffffff"):
        from PIL import Image, ImageDraw

        self._img = Image.new("RGB", (int(width), int(height)), background)
        self._draw = ImageDraw.Draw(self._img)
        self._font_cache = {}

    def _font(self, size: float):
        from PIL import ImageFont

        key = int(round(size))
        if key not in self._font_cache:
            font = None
            for name in (
                "DejaVuSans-Bold.ttf",
                "DejaVuSans.ttf",
                "Arial Bold.ttf",
                "Arial.ttf",
            ):
                try:
                    font = ImageFont.truetype(name, key)
                    break
                except Exception:
                    continue
            if font is None:
                font = ImageFont.load_default()
            self._font_cache[key] = font
        return self._font_cache[key]

    def rect(self, x, y, w, h, fill, outline=None):
        x0, y0 = x, y
        x1, y1 = x + w, y + h
        self._draw.rectangle([x0, y0, x1, y1], fill=fill, outline=outline, width=1)

    def ellipse(self, x, y, w, h, fill, outline=None):
        """Draw an ellipse in the box (x, y, w, h). A circle when w == h."""
        self._draw.ellipse([x, y, x + w, y + h], fill=fill, outline=outline, width=1)

    def polygon(self, points, fill, outline=None):
        """Draw a filled polygon. ``points`` is a list of (x, y) tuples."""
        self._draw.polygon(list(points), fill=fill, outline=outline)

    def line(self, x0, y0, x1, y1, color, width=1):
        self._draw.line([x0, y0, x1, y1], fill=color, width=int(width))

    def dashed_hline(self, x0, x1, y, color, width=1, dash=6, gap=4):
        """Horizontal dashed line from x0 to x1 at height y."""
        x = x0
        while x < x1:
            seg = min(dash, x1 - x)
            self._draw.line([x, y, x + seg, y], fill=color, width=int(width))
            x += dash + gap

    def dashed_vline(self, x, y0, y1, color, width=1, dash=6, gap=4):
        """Vertical dashed line from y0 to y1 at x."""
        y = y0
        while y < y1:
            seg = min(dash, y1 - y)
            self._draw.line([x, y, x, y + seg], fill=color, width=int(width))
            y += dash + gap

    def hatch_rect(self, x, y, w, h, base_fill, hatch_color, outline=None,
                   spacing=7, width=1):
        """Fill a rect with ``base_fill`` then overlay diagonal hatch lines."""
        self._draw.rectangle([x, y, x + w, y + h], fill=base_fill, outline=outline, width=1)
        # Diagonal lines (top-left to bottom-right) clipped to the rect.
        x0, y0, x1, y1 = int(x), int(y), int(x + w), int(y + h)
        # Start offsets so lines sweep across the whole box.
        start = x0 - (y1 - y0)
        c = start
        while c <= x1:
            # line from (c, y0) going down-right; clip to box
            ax, ay = c, y0
            bx, by = c + (y1 - y0), y1
            # Clip endpoints to [x0,x1] horizontally
            if ax < x0:
                ay += (x0 - ax)
                ax = x0
            if bx > x1:
                by -= (bx - x1)
                bx = x1
            if ax <= x1 and bx >= x0:
                self._draw.line([ax, ay, bx, by], fill=hatch_color, width=int(width))
            c += spacing

    def text(self, x, y, s, size, color):
        self._draw.text((x, y), s, fill=color, font=self._font(size))

    def text_centered(self, cx, cy, s, size, color):
        """Draw text centered on (cx, cy). Falls back to measured centering if the
        active font does not support PIL text anchors (bitmap default font)."""
        font = self._font(size)
        try:
            self._draw.text((cx, cy), s, fill=color, font=font, anchor="mm")
        except (ValueError, AttributeError):
            # Bitmap default font: center via the text bounding box.
            try:
                l, t, r, b = self._draw.textbbox((0, 0), s, font=font)
                w, h = r - l, b - t
            except Exception:
                w, h = len(s) * size * 0.5, size
            self._draw.text((cx - w / 2 - l, cy - h / 2 - t), s, fill=color, font=font)

    def save(self, path: str) -> None:
        self._img.save(path)
