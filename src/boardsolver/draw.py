"""Low-level drawing primitives.

Each primitive draws at a given ``origin`` (top-left pixels) using ``scale``
(pixels per inch), draws through the abstract :class:`~boardsolver.canvas.Canvas`,
and returns a :class:`~boardsolver.canvas.BoundingBox` of what it drew. Primitives
never place themselves relative to one another and never read files or compute a
cutting plan — they consume given documents.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from .canvas import BoundingBox, Canvas
from .colors import DEFAULT_COLORS, ColorMap, lighten
from .geometry import (
    Sixteenths,
    measure_to_sixteenths,
    px,
    resolve_slice,
    slice_length,
)
from .format import frac_inches

_OUTLINE = "#333333"
_TITLE_COLOR = "#222222"
_BUY_TITLE_COLOR = "#888888"  # gray title => buy-required (ghost) board
_LOSS_COLOR = "#c96a5a"  # reddish: material turned to sawdust by rip kerf + planing
_KERF_COLOR = "#9a8f76"  # material removed by a crosscut (length axis), per cut
_MARGIN_COLOR = "#e8e4d6"  # leftover width that stays on the source board
_GHOST_COLOR = "#dcd3bf"  # a margin-slab offcut claimed by a sourceRemainder child
_GHOST_LABEL_PX = 11.0
_ALERT_COLOR = "#c0392b"  # negative margin: strips do not fit the real board
_TITLE_PX = 14.0
_ANNOT_PX = 11.0  # panel slice-count annotation text size


# --------------------------------------------------------------------------- #
# draw_slice
# --------------------------------------------------------------------------- #

def draw_slice(
    canvas: Canvas,
    project: Dict[str, Any],
    slice_id: str,
    flip: Optional[str],
    origin,
    scale: float,
    colors: ColorMap = DEFAULT_COLORS,
    outline: Optional[str] = _OUTLINE,
) -> BoundingBox:
    """Draw one slice as a horizontal strip of colored component cells.

    If ``flip == "H"`` the component order is reversed (mirrored half). ``outline``
    is the per-component cell outline; pass ``None`` to draw borderless cells (e.g.
    the finished-board face, where only the whole board is bordered).
    """
    ox, oy = origin
    resolved = resolve_slice(project, slice_id)
    comps = list(resolved.components)
    if flip == "H":
        comps = list(reversed(comps))
    elif flip is not None:
        raise ValueError(f"unsupported flip {flip!r} (only 'H' or None)")

    h_px = px(resolved.height, scale)
    x = ox
    for c in comps:
        w_px = px(c.width, scale)
        canvas.rect(x, oy, w_px, h_px, fill=colors[c.species], outline=outline)
        x += w_px

    total_w = px(slice_length(resolved), scale)
    return BoundingBox(ox, oy, total_w, h_px)


# --------------------------------------------------------------------------- #
# draw_panel
# --------------------------------------------------------------------------- #

def draw_panel(
    canvas: Canvas,
    project: Dict[str, Any],
    panel_id: str,
    origin,
    scale: float,
    colors: ColorMap = DEFAULT_COLORS,
    annotate: bool = True,
) -> BoundingBox:
    """Draw a panel's cross-section: its fullest profile's component cells.

    The fullest profile is the one at index 0 (every component present). Cell
    height is the panel thickness (NOT ``sliceStrips.width`` — this is the glue-up
    view, before any slice ripping).

    When ``annotate`` is true, a line of text beneath the cells reports the
    panel's slice counts: ``"L: 20 · R: 20"`` for a profiled panel, or
    ``"20 slices"`` for a single-profile panel. The returned bbox includes the
    annotation line.
    """
    ox, oy = origin
    panel = _find_panel(project, panel_id)

    # Fullest profile = index 0 => the panel id alone for single-profile panels,
    # else panel-firstProfile.
    if "profiles" in panel:
        fullest_id = f"{panel_id}-{panel['profiles'][0]['id']}"
    else:
        fullest_id = panel_id
    resolved = resolve_slice(project, fullest_id)

    # Glue-up height is always the panel thickness here.
    h_px = px(measure_to_sixteenths(panel["thickness"]), scale)
    x = ox
    for c in resolved.components:
        w_px = px(c.width, scale)
        canvas.rect(x, oy, w_px, h_px, fill=colors[c.species], outline=_OUTLINE)
        x += w_px

    total_w = px(slice_length(resolved), scale)
    total_h = h_px

    if annotate:
        if "profiles" in panel:
            total = sum(p["slices"] for p in panel["profiles"])
            regions = ", ".join(f"{p['id']}={p['slices']}" for p in panel["profiles"])
            label = f"Slice Count: {total} - Regions [{regions}]"
        else:
            label = f"Slice Count: {panel['slices']}"
        canvas.text(ox, oy + h_px + 2, label, _ANNOT_PX, _TITLE_COLOR)
        total_h = h_px + 2 + _ANNOT_PX

    return BoundingBox(ox, oy, total_w, total_h)


# --------------------------------------------------------------------------- #
# draw_cut_strip
# --------------------------------------------------------------------------- #

def draw_cut_strip(
    canvas: Canvas,
    strip: Dict[str, Any],
    source_species: str,
    origin,
    scale: float,
    colors: ColorMap = DEFAULT_COLORS,
    miter_kerf: Sixteenths = 2,
    board_length: Optional[Sixteenths] = None,
) -> BoundingBox:
    """Draw ONE strip: crosscut component cells + per-cut kerf stripes + offcut tail.

    ``strip`` is a cut-spec ``strip`` object ``{width, cuts?, offcutComponent?}``.
    ``miter_kerf`` is in sixteenths (from tool-limits ``miterKerf``). ``board_length``
    (sixteenths) is the drawn length of the board this strip sits on.

    Kerf model (length axis, per strip): every entry in ``cuts`` is one crosscut
    that frees a component and consumes one ``miter_kerf`` of length. So N cuts
    eat ``N * miter_kerf``; each cut cell is followed by a visible kerf stripe
    (the material lost to that crosscut). The horizontal kerf loss therefore
    differs per strip according to how many cuts it has. The leftover,
    ``board_length - sum(cuts) - N*miter_kerf``, is the offcut: lightened (waste)
    unless ``offcutComponent`` is true, in which case it is a normal species cell.

    A strip with no cuts is one full-length species cell (no kerf, no offcut).
    """
    ox, oy = origin
    width_s = measure_to_sixteenths(strip["width"])
    cuts = [measure_to_sixteenths(c) for c in strip.get("cuts", [])]
    offcut_component = bool(strip.get("offcutComponent", False))

    h_px = px(width_s, scale)
    species_color = colors[source_species]

    if not cuts:
        # No crosscuts: the whole strip is one full-length piece (component or
        # offcut), drawn as a single species-colored cell spanning the board.
        if board_length is None:
            board_length = width_s
        full_px = px(board_length, scale)
        canvas.rect(ox, oy, full_px, h_px, fill=species_color, outline=_OUTLINE)
        return BoundingBox(ox, oy, full_px, h_px)

    # A kerf exists only where a cut actually separates material (a following
    # cut or an offcut). A cut that runs to the board's end is not a crosscut.
    # With an offcut after the last cut: N kerfs. Without: N-1 kerfs.
    if board_length is None:
        # No board length given: assume the cuts butt together, last one ends
        # the board => N-1 internal kerfs, no offcut.
        board_length = sum(cuts) + max(len(cuts) - 1, 0) * miter_kerf
    # Does an offcut remain after the cuts + their separating kerfs?
    with_offcut_consumed = sum(cuts) + len(cuts) * miter_kerf
    offcut_len = board_length - with_offcut_consumed
    has_offcut = offcut_len > 0
    if not has_offcut:
        offcut_len = 0

    x = ox
    for i, cut in enumerate(cuts):
        w_px = px(cut, scale)
        canvas.rect(x, oy, w_px, h_px, fill=species_color, outline=_OUTLINE)
        x += w_px
        # Draw a kerf stripe only if material follows this cut: another cut, or
        # an offcut after the final cut.
        follows = (i < len(cuts) - 1) or has_offcut
        if follows:
            kerf_px = px(miter_kerf, scale)
            canvas.rect(x, oy, kerf_px, h_px, fill=_KERF_COLOR, outline=None)
            x += kerf_px

    if has_offcut:
        off_px = px(offcut_len, scale)
        fill = species_color if offcut_component else lighten(species_color)
        canvas.rect(x, oy, off_px, h_px, fill=fill, outline=_OUTLINE)
        x += off_px

    return BoundingBox(ox, oy, x - ox, h_px)


# --------------------------------------------------------------------------- #
# draw_cut_board
# --------------------------------------------------------------------------- #

def draw_cut_board(
    canvas: Canvas,
    cut_spec_board: Dict[str, Any],
    project: Dict[str, Any],
    tool_limits: Dict[str, Any],
    origin,
    scale: float,
    colors: ColorMap = DEFAULT_COLORS,
    cut_spec: Optional[Dict[str, Any]] = None,
) -> BoundingBox:
    """Draw ONE cut-spec board: title, stacked strips, loss band, margin band.

    Derivations (all from the specs):

    * species: ``source``/``sourceRemainder`` trace to the inventory board's
      species; ``buySpecies`` is used directly and marks the board buy-required
      (gray title).
    * drawn board length = ``board.length`` in sixteenths.
    * loss (width axis) = per strip ``(sawKerf + minPlaneLoss)`` summed.
    * margin (width axis) = ``source_width - sum(strip widths) - loss``. This is
      the leftover slab set aside at the same sitting. Negative margin is drawn
      in an alert color (strips do not fit the real board).
    * margin crosscuts (length axis, ordered): the cut-spec ``boards`` are an
      ordered sequence of events. Every later board whose ``sourceRemainder``
      points at THIS board crosscuts one piece off this margin slab, in order:
      the first such child defines the first crosscut (at the child's length),
      the next defines the next off what remains, and so on (each reducing the
      slab by its length plus one miter kerf). Those pieces are drawn in the
      margin band as **ghost rectangles** labelled with the child's board id
      (a pointer to that board's own separate diagram), each followed by a
      crosscut kerf stripe. This board's diagram shows only the crosscuts; it
      never draws the children's own rips.

    ``cut_spec`` (the whole document) is needed to resolve ``sourceRemainder``
    species chains and to find this board's margin-consuming children; pass it
    whenever any board uses ``sourceRemainder``.
    """
    ox, oy = origin
    limits = tool_limits["limits"] if "limits" in tool_limits else tool_limits

    saw_kerf = measure_to_sixteenths(limits["sawKerf"])
    miter_kerf = measure_to_sixteenths(limits["miterKerf"])
    plane_loss = measure_to_sixteenths(limits["minPlaneLoss"])

    species, source_width, buy_required = _resolve_source(
        cut_spec_board, project, cut_spec, limits
    )
    board_len = measure_to_sixteenths(cut_spec_board["length"])

    # Title with starting stock dimensions in parentheses. A bought (ghost)
    # board has no stock on hand, so it reads "(Not Available)".
    title_color = _BUY_TITLE_COLOR if buy_required else _TITLE_COLOR
    dims = _start_dims(cut_spec_board, project, cut_spec, source_width, board_len)
    title = f"{cut_spec_board['id']}  ({dims})"
    canvas.text(ox, oy, title, _TITLE_PX, title_color)
    y = oy + _TITLE_PX + 4

    left = ox
    right = ox
    strips = cut_spec_board["strips"]
    strip_width_total: Sixteenths = 0
    for strip in strips:
        bb = draw_cut_strip(
            canvas,
            strip,
            species,
            (left, y),
            scale,
            colors,
            miter_kerf=miter_kerf,
            board_length=board_len,
        )
        right = max(right, bb.x + bb.w)
        y += bb.h
        strip_width_total += measure_to_sixteenths(strip["width"])

    # Loss band (width axis): one (sawKerf + minPlaneLoss) per strip.
    loss_s = len(strips) * (saw_kerf + plane_loss)
    if loss_s > 0:
        loss_px = px(loss_s, scale)
        canvas.rect(left, y, px(board_len, scale), loss_px, fill=_LOSS_COLOR, outline=_OUTLINE)
        right = max(right, left + px(board_len, scale))
        y += loss_px

    # Margin band (width axis height = leftover slab width; length axis runs
    # along the board). Negative margin => alert band, no children drawn.
    margin_s = source_width - strip_width_total - loss_s
    if margin_s < 0:
        margin_px = px(-margin_s, scale)
        canvas.rect(
            left, y, px(board_len, scale), margin_px, fill=_ALERT_COLOR, outline=_OUTLINE
        )
        right = max(right, left + px(board_len, scale))
        y += margin_px
    elif margin_s > 0:
        margin_px = px(margin_s, scale)
        children = _margin_children(cut_spec, cut_spec_board["id"]) if cut_spec else []
        x = left
        remaining = board_len
        for child in children:
            child_len = measure_to_sixteenths(child["length"])
            drawn = min(child_len, remaining)
            if drawn <= 0:
                break
            piece_px = px(drawn, scale)
            # Ghost rectangle: the offcut handed to the child board.
            canvas.rect(
                x, y, piece_px, margin_px, fill=_GHOST_COLOR, outline=_OUTLINE
            )
            canvas.text(
                x + 3, y + max(margin_px / 2 - _GHOST_LABEL_PX / 2, 1), child["id"], _GHOST_LABEL_PX, _OUTLINE
            )
            x += piece_px
            remaining -= drawn
            # Crosscut kerf stripe that frees this piece off the slab.
            if remaining > 0:
                kerf_px = px(miter_kerf, scale)
                canvas.rect(x, y, kerf_px, margin_px, fill=_KERF_COLOR, outline=None)
                x += kerf_px
                remaining -= miter_kerf
        # Unclaimed tail of the slab (true leftover) drawn plain.
        if remaining > 0:
            tail_px = px(remaining, scale)
            canvas.rect(x, y, tail_px, margin_px, fill=_MARGIN_COLOR, outline=_OUTLINE)
            x += tail_px
        right = max(right, left + px(board_len, scale), x)
        y += margin_px

    return BoundingBox(ox, oy, right - ox, y - oy)


# --------------------------------------------------------------------------- #
# helpers
# --------------------------------------------------------------------------- #

def _root_inventory_board(cut_spec_board, project, cut_spec):
    """Follow source/sourceRemainder to the originating inventory board, or None
    for a bought (ghost) board."""
    if "source" in cut_spec_board:
        return _find_board(project, cut_spec_board["source"])
    if "buySpecies" in cut_spec_board:
        return None
    if "sourceRemainder" in cut_spec_board:
        parent = _find_cut_board(cut_spec, cut_spec_board["sourceRemainder"])
        return _root_inventory_board(parent, project, cut_spec)
    return None


def _start_dims(cut_spec_board, project, cut_spec, source_width, board_len) -> str:
    """Starting-stock dimensions string for the title.

    * source: the inventory board's full length x width x thickness.
    * sourceRemainder: the leftover slab it starts from (board length x slab
      width x inherited thickness).
    * buySpecies: 'Not Available' (no stock on hand).
    """
    if "buySpecies" in cut_spec_board:
        return "Not Available"
    inv = _root_inventory_board(cut_spec_board, project, cut_spec)
    thickness = measure_to_sixteenths(inv["thickness"]) if inv else None
    if "source" in cut_spec_board:
        length = measure_to_sixteenths(inv["length"])
        width = measure_to_sixteenths(inv["width"])
    else:  # sourceRemainder slab
        length = board_len
        width = source_width
    parts = f"{frac_inches(length, ascii=True)} x {frac_inches(width, ascii=True)}"
    if thickness is not None:
        parts += f" x {frac_inches(thickness, ascii=True)}"
    return parts


def _find_panel(project: Dict[str, Any], panel_id: str) -> Dict[str, Any]:
    for p in project["panels"]:
        if p["id"] == panel_id:
            return p
    raise KeyError(f"no panel with id {panel_id!r}")


def _find_board(project: Dict[str, Any], board_id: str) -> Dict[str, Any]:
    for b in project["boards"]:
        if b["id"] == board_id:
            return b
    raise KeyError(f"no inventory board with id {board_id!r}")


def _find_cut_board(cut_spec: Dict[str, Any], board_id: str) -> Dict[str, Any]:
    for b in cut_spec["boards"]:
        if b["id"] == board_id:
            return b
    raise KeyError(f"no cut-spec board with id {board_id!r}")


def _margin_children(cut_spec: Dict[str, Any], board_id: str) -> List[Dict[str, Any]]:
    """Boards that consume ``board_id``'s margin slab, in cut-spec document order.

    Each is a crosscut off the leftover slab, ordered by their position in the
    ``boards`` sequence (the order the cuts happen).
    """
    return [
        b
        for b in cut_spec["boards"]
        if b.get("sourceRemainder") == board_id
    ]


def _resolve_source(cut_spec_board, project, cut_spec, limits=None):
    """Return ``(species, source_width_sixteenths, buy_required)``.

    * ``source`` -> inventory board's species + width.
    * ``buySpecies`` -> that species; source width is the sum of this board's
      strip widths plus its own loss (a bought board is sized to the plan, so
      there is no spare margin). buy_required True.
    * ``sourceRemainder`` -> follow to the referenced parent cut-spec board. The
      source width is the parent's leftover slab width = parent source width
      minus the parent's strip widths minus the parent's loss (one
      ``sawKerf + minPlaneLoss`` per parent strip). Species comes from the
      parent chain. Requires ``limits`` to compute the parent's loss.
    """
    if "source" in cut_spec_board:
        board = _find_board(project, cut_spec_board["source"])
        return board["species"], measure_to_sixteenths(board["width"]), False

    if "buySpecies" in cut_spec_board:
        strips_total = sum(
            measure_to_sixteenths(s["width"]) for s in cut_spec_board["strips"]
        )
        loss = _board_loss(cut_spec_board, limits)
        return cut_spec_board["buySpecies"], strips_total + loss, True

    if "sourceRemainder" in cut_spec_board:
        if cut_spec is None:
            raise ValueError(
                "sourceRemainder board requires the full cut_spec to resolve its chain"
            )
        parent = _find_cut_board(cut_spec, cut_spec_board["sourceRemainder"])
        species, parent_width, buy = _resolve_source(parent, project, cut_spec, limits)
        parent_strips = sum(
            measure_to_sixteenths(s["width"]) for s in parent["strips"]
        )
        parent_loss = _board_loss(parent, limits)
        slab_width = parent_width - parent_strips - parent_loss
        return species, slab_width, buy

    raise ValueError(f"cut-spec board {cut_spec_board.get('id')!r} has no origin")


def _board_loss(cut_spec_board, limits):
    """Width-axis loss for a board: one (sawKerf + minPlaneLoss) per strip.

    Returns 0 when ``limits`` is not supplied (keeps species/width resolution
    usable in contexts without tool-limits, at the cost of ignoring loss).
    """
    if not limits:
        return 0
    saw_kerf = measure_to_sixteenths(limits["sawKerf"])
    plane_loss = measure_to_sixteenths(limits["minPlaneLoss"])
    return len(cut_spec_board["strips"]) * (saw_kerf + plane_loss)
