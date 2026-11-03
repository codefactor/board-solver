"""Section data derivations for the Round 2 document-writer.

Pure functions over the loaded YAML docs (``project``, ``tool_limits``,
``cut_spec``). All arithmetic in integer sixteenths; callers format at the edge.
These feed both the tables and the visual renderers. No file I/O here.
"""

from __future__ import annotations

from collections import OrderedDict
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from .geometry import (
    ResolvedComponent,
    Sixteenths,
    measure_to_sixteenths,
    resolve_slice,
    slice_length,
)


def _limits(tool_limits: Dict[str, Any]) -> Dict[str, Any]:
    return tool_limits["limits"] if "limits" in tool_limits else tool_limits


def validate_components_unique(project: Dict[str, Any]) -> None:
    """A component identifies a unique end-grain shape: (species, width,
    thickness). Two components sharing all three would be the same component,
    so the project is invalid. Raise with the offending ids.
    """
    seen: Dict[tuple, str] = {}
    for c in project["components"]:
        key = (
            c["species"],
            measure_to_sixteenths(c["width"]),
            measure_to_sixteenths(c["thickness"]),
        )
        if key in seen:
            raise ValueError(
                f"invalid project: components {seen[key]!r} and {c['id']!r} have "
                f"identical end-grain shape (species={c['species']}, "
                f"width={c['width']}, thickness={c['thickness']}) — a component "
                f"must identify a unique shape; merge them."
            )
        seen[key] = c["id"]


def component_by_shape(
    project: Dict[str, Any], species: str, width: Sixteenths, thickness: Sixteenths
):
    """Return the single component matching (species, width, thickness), or None.

    Relies on the uniqueness invariant (see validate_components_unique): the
    match is exactly one component or zero, never more.
    """
    for c in project["components"]:
        if (
            c["species"] == species
            and measure_to_sixteenths(c["width"]) == width
            and measure_to_sixteenths(c["thickness"]) == thickness
        ):
            return c
    return None


# --------------------------------------------------------------------------- #
# panel length + slice summary
# --------------------------------------------------------------------------- #

def panel_total_slices(panel: Dict[str, Any]) -> int:
    if "profiles" in panel:
        return sum(p["slices"] for p in panel["profiles"])
    return panel["slices"]


def panel_length(
    panel: Dict[str, Any], project: Dict[str, Any], tool_limits: Dict[str, Any]
) -> Sixteenths:
    """Derived panel length (schema rule):

    ``total_slices * (sliceDepth + miterKerf) + snipeTail``. ``sliceDepth`` is a
    project field; the miter kerf and snipe tail come from tool-limits. Length is
    the crosscut-pitch direction along the panel.
    """
    lim = _limits(tool_limits)
    slice_depth = measure_to_sixteenths(project["sliceDepth"])
    miter_kerf = measure_to_sixteenths(lim["miterKerf"])
    snipe = measure_to_sixteenths(lim.get("snipeTail", [0, 0]))
    pitch = slice_depth + miter_kerf
    return panel_total_slices(panel) * pitch + snipe


@dataclass(frozen=True)
class PanelSummary:
    id: str
    length: Sixteenths
    total_slices: int
    profiles: List[tuple]  # (profile_id, slices) or [("", slices)] for single
    height: Sixteenths  # installed row height (sliceStrips width or thickness)
    ripped: Optional[int]  # sliceStrips count, else None
    fullest_components: List[tuple]  # (id, species, width) outer->in
    sequence: str  # component id sequence of the fullest profile


def panel_summaries(
    project: Dict[str, Any], tool_limits: Dict[str, Any]
) -> List[PanelSummary]:
    out = []
    for panel in project["panels"]:
        pid = panel["id"]
        if "profiles" in panel:
            profiles = [(p["id"], p["slices"]) for p in panel["profiles"]]
            fullest_id = f"{pid}-{panel['profiles'][0]['id']}"
        else:
            profiles = [("", panel["slices"])]
            fullest_id = pid
        resolved = resolve_slice(project, fullest_id)
        if "sliceStrips" in panel:
            ripped = panel["sliceStrips"]["count"]
            height = measure_to_sixteenths(panel["sliceStrips"]["width"])
        else:
            ripped = None
            height = measure_to_sixteenths(panel["thickness"])
        comps = [(c.id, c.species, c.width) for c in resolved.components]
        out.append(
            PanelSummary(
                id=pid,
                length=panel_length(panel, project, tool_limits),
                total_slices=panel_total_slices(panel),
                profiles=profiles,
                height=height,
                ripped=ripped,
                fullest_components=comps,
                sequence=" · ".join(c.id for c in resolved.components),
            )
        )
    return out


# --------------------------------------------------------------------------- #
# component demand (walk the sliceGrid)
# --------------------------------------------------------------------------- #

@dataclass(frozen=True)
class ComponentDemand:
    id: str
    species: str
    width: Sixteenths
    length: Sixteenths
    count: int


def component_demand(
    project: Dict[str, Any], tool_limits: Dict[str, Any]
) -> List[ComponentDemand]:
    """Count every component instance the finished board(s) require.

    Walks ``sliceGrid`` once per finished board (``batch``, default 1). Each
    placed slice resolves to its component list; every component contributes one
    instance at that slice's panel length. Keyed by (id, species, width, length).
    """
    lengths = {s.id: s.length for s in panel_summaries(project, tool_limits)}
    batch = project.get("batch", 1)
    tally: "OrderedDict[tuple, int]" = OrderedDict()
    for row in project.get("sliceGrid", []):
        for cell in row:
            slice_id = cell["sliceId"]
            panel_id = slice_id.split("-")[0]
            plen = lengths[panel_id]
            resolved = resolve_slice(project, slice_id)
            for c in resolved.components:
                key = (c.id, c.species, c.width, plen)
                tally[key] = tally.get(key, 0) + batch
    return [
        ComponentDemand(id=k[0], species=k[1], width=k[2], length=k[3], count=v)
        for k, v in tally.items()
    ]


# --------------------------------------------------------------------------- #
# supply: pieces produced by the cut list (each strip resolves to one component)
# --------------------------------------------------------------------------- #

@dataclass(frozen=True)
class SupplyPiece:
    component_id: Optional[str]  # None => matches no project component (wasted)
    species: str
    width: Sixteenths
    length: Sixteenths   # a single crosscut piece's length
    board_id: str        # which cut-spec board produced it


def component_supply(
    project: Dict[str, Any], cut_spec: Dict[str, Any], tool_limits: Dict[str, Any]
) -> List[SupplyPiece]:
    """Every component piece the cut list produces.

    Each strip's (species, width) is matched to a project component; the species
    comes from the strip's source board. Each crosscut length on the strip is one
    produced piece. A strip whose (species, width) matches NO project component is
    not an error — its pieces carry ``component_id = None`` and are reported as
    wasted (an end-grain shape the project cannot consume). The duplicate-shape
    project invariant is still enforced.
    """
    validate_components_unique(project)
    # Index components by (species, width) -> id. Unique per the project invariant
    # (width alone is enough within a species; thickness is planed later so the
    # rip-time match is species + width).
    by_sw: Dict[tuple, str] = {}
    for c in project["components"]:
        by_sw[(c["species"], measure_to_sixteenths(c["width"]))] = c["id"]

    out: List[SupplyPiece] = []
    for r in board_rips(project, cut_spec, tool_limits):
        for strip in r.strips:
            width = measure_to_sixteenths(strip["width"])
            comp_id = by_sw.get((r.species, width))  # None if unmatched (wasted)
            cuts = strip.get("cuts", [])
            for cut in cuts:
                out.append(SupplyPiece(
                    component_id=comp_id, species=r.species, width=width,
                    length=measure_to_sixteenths(cut), board_id=r.id,
                ))
    return out


# --------------------------------------------------------------------------- #
# matching supply -> demand (greedy, longest demand first)
# --------------------------------------------------------------------------- #

@dataclass(frozen=True)
class MatchRow:
    component_id: str
    species: str
    width: Sixteenths
    length: Sixteenths   # demanded length
    demand: int
    fulfilled: int
    shortfall: int       # demand - fulfilled
    overcut: Sixteenths  # total (piece_len - demand_len) for longer pieces used


@dataclass(frozen=True)
class UnusedPiece:
    component_id: str
    species: str
    width: Sixteenths
    length: Sixteenths
    count: int


@dataclass(frozen=True)
class WastedPiece:
    """A produced piece whose end-grain shape matches no project component."""
    species: str
    width: Sixteenths
    length: Sixteenths
    count: int
    board_id: str


def match_supply_to_demand(
    project: Dict[str, Any], cut_spec: Dict[str, Any], tool_limits: Dict[str, Any]
):
    """Greedy match of produced pieces onto demanded components.

    Per component id: satisfy demand rows longest-first. For each row (length L,
    count N) consume pieces of exactly L first, then any piece longer than L
    (consumed whole; the remainder is waste, not reused). A piece shorter than L
    cannot fulfill it. Overcut accumulates (piece_len - L) for each longer piece
    used.

    Returns (match_rows, unused_pieces, wasted_pieces):
      * match_rows   — one per demand row (fulfilled / shortfall / overcut),
      * unused_pieces— matched-component pieces left over after demand is met,
      * wasted_pieces— produced pieces whose shape matches no component at all.
    """
    demand = component_demand(project, tool_limits)
    supply = component_supply(project, cut_spec, tool_limits)

    # Pieces that match no component are wasted; the rest form the demand pool.
    wasted_tally: "OrderedDict[tuple, int]" = OrderedDict()
    pool: Dict[str, List[Sixteenths]] = {}
    comp_meta: Dict[str, tuple] = {}
    for p in supply:
        if p.component_id is None:
            key = (p.species, p.width, p.length, p.board_id)
            wasted_tally[key] = wasted_tally.get(key, 0) + 1
            continue
        pool.setdefault(p.component_id, []).append(p.length)
        comp_meta[p.component_id] = (p.species, p.width)

    # Demand rows grouped by component id, each row longest-first.
    demand_by_comp: Dict[str, List[ComponentDemand]] = {}
    for d in demand:
        demand_by_comp.setdefault(d.id, []).append(d)

    rows: List[MatchRow] = []

    # Process each component's demand rows longest-first against its pool.
    results: Dict[tuple, MatchRow] = {}
    for comp_id, drows in demand_by_comp.items():
        avail = sorted(pool.get(comp_id, []))  # ascending lengths
        for d in sorted(drows, key=lambda r: r.length, reverse=True):
            need = d.count
            fulfilled = 0
            overcut = 0
            # Exact matches first.
            while need > 0 and avail:
                # find an exact match
                exact_idx = next((k for k, L in enumerate(avail) if L == d.length), None)
                if exact_idx is None:
                    break
                avail.pop(exact_idx)
                fulfilled += 1
                need -= 1
            # Then shortest piece that is longer than L.
            while need > 0:
                longer_idx = next((k for k, L in enumerate(avail) if L > d.length), None)
                if longer_idx is None:
                    break
                piece = avail.pop(longer_idx)
                overcut += piece - d.length
                fulfilled += 1
                need -= 1
            results[(comp_id, d.length)] = MatchRow(
                component_id=comp_id, species=d.species, width=d.width,
                length=d.length, demand=d.count, fulfilled=fulfilled,
                shortfall=d.count - fulfilled, overcut=overcut,
            )
        pool[comp_id] = avail  # remaining unused pieces

    # Emit match rows in the original demand order.
    for d in demand:
        rows.append(results[(d.id, d.length)])

    # Unused pieces: whatever remains in each pool, grouped by (comp, length).
    unused_tally: "OrderedDict[tuple, int]" = OrderedDict()
    for comp_id, lengths in pool.items():
        for L in lengths:
            key = (comp_id, L)
            unused_tally[key] = unused_tally.get(key, 0) + 1
    unused = [
        UnusedPiece(
            component_id=cid, species=comp_meta[cid][0], width=comp_meta[cid][1],
            length=L, count=n,
        )
        for (cid, L), n in unused_tally.items()
    ]
    wasted = [
        WastedPiece(species=sp, width=w, length=L, count=n, board_id=bid)
        for (sp, w, L, bid), n in wasted_tally.items()
    ]
    return rows, unused, wasted


# --------------------------------------------------------------------------- #
# per-board rip rows: used / loss / margin
# --------------------------------------------------------------------------- #

@dataclass(frozen=True)
class BoardRip:
    id: str
    origin: str  # "source:BC1" | "remainder:BW1A" | "buy:Cherry"
    species: str
    buy_required: bool
    length: Sixteenths
    source_width: Sixteenths
    used: Sixteenths
    loss: Sixteenths
    margin: Sixteenths  # may be negative (sizing problem)
    strips: List[Dict[str, Any]]


def _find_board(project, board_id):
    for b in project["boards"]:
        if b["id"] == board_id:
            return b
    raise KeyError(f"no inventory board {board_id!r}")


def _find_cut_board(cut_spec, board_id):
    for b in cut_spec["boards"]:
        if b["id"] == board_id:
            return b
    raise KeyError(f"no cut-spec board {board_id!r}")


def _board_loss(board, lim) -> Sixteenths:
    saw = measure_to_sixteenths(lim["sawKerf"])
    plane = measure_to_sixteenths(lim["minPlaneLoss"])
    return len(board["strips"]) * (saw + plane)


def _source_width(board, project, cut_spec, lim):
    if "source" in board:
        inv = _find_board(project, board["source"])
        return inv["species"], measure_to_sixteenths(inv["width"]), False, f"source:{board['source']}"
    if "buySpecies" in board:
        used = sum(measure_to_sixteenths(s["width"]) for s in board["strips"])
        return board["buySpecies"], used + _board_loss(board, lim), True, f"buy:{board['buySpecies']}"
    if "sourceRemainder" in board:
        parent = _find_cut_board(cut_spec, board["sourceRemainder"])
        species, pw, buy, _ = _source_width(parent, project, cut_spec, lim)
        pused = sum(measure_to_sixteenths(s["width"]) for s in parent["strips"])
        slab = pw - pused - _board_loss(parent, lim)
        return species, slab, buy, f"remainder:{board['sourceRemainder']}"
    raise ValueError(f"board {board.get('id')!r} has no origin")


def board_rips(
    project: Dict[str, Any], cut_spec: Dict[str, Any], tool_limits: Dict[str, Any]
) -> List[BoardRip]:
    lim = _limits(tool_limits)
    out = []
    for board in cut_spec["boards"]:
        species, swidth, buy, origin = _source_width(board, project, cut_spec, lim)
        used = sum(measure_to_sixteenths(s["width"]) for s in board["strips"])
        loss = _board_loss(board, lim)
        out.append(
            BoardRip(
                id=board["id"],
                origin=origin,
                species=species,
                buy_required=buy,
                length=measure_to_sixteenths(board["length"]),
                source_width=swidth,
                used=used,
                loss=loss,
                margin=swidth - used - loss,
                strips=board["strips"],
            )
        )
    return out


# --------------------------------------------------------------------------- #
# crosscut blanks: raw inventory board -> length-crosscut blanks
# --------------------------------------------------------------------------- #

@dataclass(frozen=True)
class BlankCut:
    blank_id: str      # the labeled cut-spec board this length-section becomes
    length: Sixteenths


@dataclass(frozen=True)
class CrosscutBlank:
    source_id: str     # raw inventory board id
    species: str
    length: Sixteenths  # raw board's full length
    width: Sixteenths   # raw board's width (for the to-scale diagram)
    thickness: Sixteenths
    blanks: List[BlankCut]      # labeled blanks crosscut from it, in order
    kerf: Sixteenths            # miter kerf consumed per crosscut
    leftover: Sixteenths        # raw length - sum(blank lengths) - cut kerfs
    state: str                  # 'crosscut' | 'whole' | 'spare'
    # 'crosscut': cut into >=2 blanks, or a single trimmed blank (< raw length).
    # 'whole'   : a single blank equal to the full raw length (used uncut, goes
    #             straight into the rip diagram).
    # 'spare'   : inventory board not referenced by any cut-spec board (untouched).


def crosscut_blanks(
    project: Dict[str, Any], cut_spec: Dict[str, Any], tool_limits: Dict[str, Any]
) -> List[CrosscutBlank]:
    """For each raw inventory board that is crosscut into length blanks, the
    ordered blanks produced (from the cut-spec boards whose ``source`` is that
    inventory board). Only covers raw-stock crosscuts; ``sourceRemainder`` and
    bought boards are not raw-stock crosscuts and are excluded.

    A crosscut is counted for each blank taken off the raw board EXCEPT when the
    blanks exactly use the whole board (a single full-length blank needs no
    crosscut). Modeled simply: one miter kerf per blank after the first, matching
    the schema note that a shorter section is crosscut off, reducing the source
    by that length plus one kerf.
    """
    lim = _limits(tool_limits)
    miter_kerf = measure_to_sixteenths(lim["miterKerf"])

    # Group source boards by their raw inventory id, preserving cut-spec order.
    by_source: "OrderedDict[str, List[Dict[str, Any]]]" = OrderedDict()
    for b in cut_spec["boards"]:
        if "source" in b:
            by_source.setdefault(b["source"], []).append(b)

    out = []
    for source_id, boards in by_source.items():
        inv = _find_board(project, source_id)
        raw_len = measure_to_sixteenths(inv["length"])
        blanks = [
            BlankCut(blank_id=b["id"], length=measure_to_sixteenths(b["length"]))
            for b in boards
        ]
        n_cuts = max(len(blanks) - 1, 0)
        used = sum(bl.length for bl in blanks) + n_cuts * miter_kerf
        # A single blank equal to the full raw length is used whole (no crosscut).
        if len(blanks) == 1 and blanks[0].length == raw_len:
            state = "whole"
        else:
            state = "crosscut"
        out.append(CrosscutBlank(
            source_id=source_id,
            species=inv["species"],
            length=raw_len,
            width=measure_to_sixteenths(inv["width"]),
            thickness=measure_to_sixteenths(inv["thickness"]),
            blanks=blanks,
            kerf=miter_kerf,
            leftover=raw_len - used,
            state=state,
        ))

    # Inventory boards not referenced by any cut-spec board are untouched spares.
    for inv in project["boards"]:
        if inv["id"] in by_source:
            continue
        raw_len = measure_to_sixteenths(inv["length"])
        out.append(CrosscutBlank(
            source_id=inv["id"],
            species=inv["species"],
            length=raw_len,
            width=measure_to_sixteenths(inv["width"]),
            thickness=measure_to_sixteenths(inv["thickness"]),
            blanks=[],
            kerf=miter_kerf,
            leftover=raw_len,
            state="spare",
        ))
    return out


# --------------------------------------------------------------------------- #
# diagnostics: ghost boards + oversized margins
# --------------------------------------------------------------------------- #

@dataclass(frozen=True)
class Diagnostics:
    ghost_boards: List[BoardRip]
    negative_margins: List[BoardRip]
    large_margins: List[BoardRip]  # margin >= threshold (a sizing smell)


def diagnostics(
    rips: List[BoardRip], large_margin_threshold: Sixteenths = 32
) -> Diagnostics:
    """Surface the sizing problems: bought (ghost) boards, negative margins
    (strips do not fit), and large leftover margins (>= threshold, default 2″).
    """
    return Diagnostics(
        ghost_boards=[r for r in rips if r.buy_required],
        negative_margins=[r for r in rips if r.margin < 0],
        large_margins=[r for r in rips if r.margin >= large_margin_threshold],
    )



# --------------------------------------------------------------------------- #
# warnings: categorized, actionable problems for the top-of-document banner
# --------------------------------------------------------------------------- #

@dataclass(frozen=True)
class Warning:
    level: str   # "red" | "yellow" | "gray"
    code: str    # short machine code, e.g. "crosscut_overflow"
    message: str # human-readable, measurements already formatted


def _maybe(v):
    """A tool-limit measurement that may be null/absent -> sixteenths or None."""
    if v is None:
        return None
    return measure_to_sixteenths(v)


def warnings(
    project: Dict[str, Any], cut_spec: Dict[str, Any], tool_limits: Dict[str, Any],
    small_margin_threshold: Sixteenths = 4,  # 1/4" = 4 sixteenths
) -> List["Warning"]:
    """All detected problems, grouped by severity.

    red   = plan is invalid / impossible as written.
    yellow= plan is at risk or needs more material.
    gray  = plan produces unusable output.

    Length checks (rip length, crosscut length) use maxCutLength; when that limit
    is null/absent they are skipped (unbounded capacity, e.g. a table saw).
    """
    from .format import frac_inches  # local import to avoid a cycle at module load

    lim = _limits(tool_limits)
    max_cut = _maybe(lim.get("maxCutLength"))
    max_plane_w = _maybe(lim.get("maxPlaneWidth"))
    max_depth = _maybe(lim.get("maxCutDepth"))

    out: List[Warning] = []

    rips = board_rips(project, cut_spec, tool_limits)
    blanks = crosscut_blanks(project, cut_spec, tool_limits)
    rows, _unused, wasted = match_supply_to_demand(project, cut_spec, tool_limits)

    # --- RED: crosscut overflow (a raw board cut longer than it is) ------- #
    for cb in blanks:
        if cb.leftover < 0:
            out.append(Warning(
                "red", "crosscut_overflow",
                f"Board {cb.source_id} is over-cut by {frac_inches(-cb.leftover)}: "
                f"its blanks demand more length than the raw board has.",
            ))

    # --- RED: over-rip (strips wider than the board) ---------------------- #
    for r in rips:
        if r.margin < 0:
            out.append(Warning(
                "red", "over_rip",
                f"Cut list for board {r.id} over-rips by {frac_inches(-r.margin)}: "
                f"the strips are wider than the board.",
            ))

    # --- RED: board ripped beyond the saw's rip capacity ------------------ #
    if max_cut is not None:
        for r in rips:
            if r.length > max_cut:
                out.append(Warning(
                    "red", "rip_too_long",
                    f"Board {r.id} is {frac_inches(r.length)} long, beyond the saw's "
                    f"{frac_inches(max_cut)} rip capacity.",
                ))

    # --- RED: a crosscut longer than the saw can cut ---------------------- #
    if max_cut is not None:
        for r in rips:
            for strip in r.strips:
                for cut in strip.get("cuts", []):
                    cl = measure_to_sixteenths(cut)
                    if cl > max_cut:
                        out.append(Warning(
                            "red", "crosscut_too_long",
                            f"Board {r.id} has a {frac_inches(cl)} crosscut, beyond the "
                            f"saw's {frac_inches(max_cut)} capacity.",
                        ))

    # --- RED: panel too wide for the planer ------------------------------- #
    if max_plane_w is not None:
        for s in panel_summaries(project, tool_limits):
            glue_w = slice_length_of_fullest(project, s.id)
            if glue_w > max_plane_w:
                out.append(Warning(
                    "red", "panel_too_wide",
                    f"Panel {s.id} glue-up is {frac_inches(glue_w)} wide, beyond the "
                    f"planer's {frac_inches(max_plane_w)} width.",
                ))

    # --- RED: slice-rip depth beyond the saw's cut depth ------------------ #
    if max_depth is not None:
        for panel in project["panels"]:
            if "sliceStrips" in panel:
                depth = measure_to_sixteenths(panel["thickness"])
                if depth > max_depth:
                    out.append(Warning(
                        "red", "slice_rip_too_deep",
                        f"Panel {panel['id']} is ripped at {frac_inches(depth)} deep, "
                        f"beyond the saw's {frac_inches(max_depth)} cut depth.",
                    ))

    # --- YELLOW: bought (ghost) boards needed ----------------------------- #
    ghosts = [r for r in rips if r.buy_required]
    if ghosts:
        ids = ", ".join(r.id for r in ghosts)
        out.append(Warning(
            "yellow", "ghost_boards",
            f"{len(ghosts)} board(s) must be bought (not in inventory): {ids}.",
        ))

    # --- YELLOW: unmet demand (shortfall) --------------------------------- #
    short_rows = [r for r in rows if r.shortfall > 0]
    if short_rows:
        total = sum(r.shortfall for r in short_rows)
        out.append(Warning(
            "yellow", "shortfall",
            f"The cut list under-supplies {total} component piece(s) across "
            f"{len(short_rows)} demand row(s) — see the Components section.",
        ))

    # --- YELLOW: small positive margin (under-supply risk) ---------------- #
    for r in rips:
        if 0 <= r.margin < small_margin_threshold:
            out.append(Warning(
                "yellow", "small_margin",
                f"Board {r.id} leaves only {frac_inches(r.margin)} margin "
                f"(< {frac_inches(small_margin_threshold)}) — too tight; prone to "
                f"under-supplying strips if the board runs narrow.",
            ))

    # --- GRAY: wasted pieces (shape matches no component) ----------------- #
    if wasted:
        total = sum(w.count for w in wasted)
        out.append(Warning(
            "gray", "wasted_pieces",
            f"The cut list produces {total} piece(s) whose end-grain shape matches "
            f"no component in this project — cut but unusable here.",
        ))

    return out


def slice_length_of_fullest(project: Dict[str, Any], panel_id: str) -> Sixteenths:
    """Glue-up width of a panel = sum of its fullest profile's component widths."""
    for panel in project["panels"]:
        if panel["id"] == panel_id:
            fid = f"{panel_id}-{panel['profiles'][0]['id']}" if "profiles" in panel else panel_id
            return slice_length(resolve_slice(project, fid))
    raise KeyError(f"no panel {panel_id!r}")


# --------------------------------------------------------------------------- #
# ripped-slice profiles: distinct ripped slice shapes, merged across panels
# --------------------------------------------------------------------------- #

@dataclass(frozen=True)
class RippedSliceProfile:
    key: tuple                      # dedupe key (sequence + height + rip)
    components: List["ResolvedComponent"]  # ordered, the end-grain stripes
    length: Sixteenths              # slice length = glue-up width (stripe run)
    panel_thickness: Sixteenths     # the height that gets ripped
    strip_count: int                # sliceStrips.count
    strip_width: Sixteenths         # sliceStrips.width (installed row height)
    slice_ids: List[str]            # contributing slice ids (e.g. ["H-L"])
    count: int                      # total identical slices to cut this way


def ripped_slice_profiles(
    project: Dict[str, Any], tool_limits: Dict[str, Any]
) -> List[RippedSliceProfile]:
    """Distinct ripped-slice shapes across all panels, merged by key.

    Only panels with ``sliceStrips`` produce ripped slices. Each (panel, profile)
    yields ``profile.slices`` identical slices; slices from different panels with
    the same end-grain sequence + panel thickness + rip spec are the SAME profile
    and merge into one entry (counts summed, slice ids collected).\n    """
    groups: "OrderedDict[tuple, dict]" = OrderedDict()
    for panel in project["panels"]:
        ss = panel.get("sliceStrips")
        if not ss:
            continue
        thickness = measure_to_sixteenths(panel["thickness"])
        strip_count = ss["count"]
        strip_width = measure_to_sixteenths(ss["width"])
        # Enumerate (profile_id, slice_count) just like panel_summaries.
        if "profiles" in panel:
            regions = [(p["id"], p["slices"]) for p in panel["profiles"]]
        else:
            regions = [(None, panel["slices"])]
        for prof_id, n in regions:
            slice_id = f"{panel['id']}-{prof_id}" if prof_id else panel["id"]
            resolved = resolve_slice(project, slice_id)
            seq = tuple((c.id, c.species, c.width) for c in resolved.components)
            key = (seq, thickness, strip_count, strip_width)
            g = groups.get(key)
            if g is None:
                groups[key] = dict(
                    key=key, components=list(resolved.components),
                    length=slice_length(resolved), panel_thickness=thickness,
                    strip_count=strip_count, strip_width=strip_width,
                    slice_ids=[slice_id], count=n,
                )
            else:
                g["slice_ids"].append(slice_id)
                g["count"] += n
    return [RippedSliceProfile(**g) for g in groups.values()]


# --------------------------------------------------------------------------- #
# actual panels: parse panel codes from the cut-spec into real glue-ups
# --------------------------------------------------------------------------- #

@dataclass(frozen=True)
class ActualPiece:
    ref: str              # "boardId/stripIndex/cutIndex"
    component_id: Optional[str]
    species: str
    width: Sixteenths
    length: Sixteenths


@dataclass(frozen=True)
class ActualPanel:
    panel_id: str                 # ideal panel this realizes
    code: str                     # original panel code
    pieces: List[ActualPiece]     # glued side by side, in order (top-aligned)
    length: Sixteenths            # derived: the longest piece (full panel length)
    sequence_ok: bool             # resolved components match the ideal sequence


def _resolve_piece_ref(ref: str, cut_spec: Dict[str, Any], project: Dict[str, Any],
                       tool_limits: Dict[str, Any], comp_by_sw: Dict[tuple, str]):
    """Resolve 'boardId/stripIndex/cutIndex' to an ActualPiece.

    Raises ValueError (invalid cut-spec panel code) if the reference does not
    point at a real board/strip/cut.
    """
    parts = ref.split("/")
    if len(parts) != 3:
        raise ValueError(f"invalid piece ref {ref!r}: expected boardId/strip/cut")
    board_id, si, ci = parts[0], int(parts[1]), int(parts[2])
    # Find the board and its resolved species via board_rips (handles remainder/buy).
    rips = {r.id: r for r in board_rips(project, cut_spec, tool_limits)}
    if board_id not in rips:
        raise ValueError(f"invalid piece ref {ref!r}: no board {board_id!r} in cut-spec")
    r = rips[board_id]
    if si < 0 or si >= len(r.strips):
        raise ValueError(f"invalid piece ref {ref!r}: strip index {si} out of range")
    strip = r.strips[si]
    cuts = strip.get("cuts", [])
    if ci < 0 or ci >= len(cuts):
        raise ValueError(f"invalid piece ref {ref!r}: cut index {ci} out of range")
    width = measure_to_sixteenths(strip["width"])
    length = measure_to_sixteenths(cuts[ci])
    comp_id = comp_by_sw.get((r.species, width))
    return ActualPiece(ref=ref, component_id=comp_id, species=r.species,
                       width=width, length=length)


def _ideal_sequence(project: Dict[str, Any], panel_id: str) -> List[str]:
    """Ideal panel's fullest-profile component id sequence."""
    for panel in project["panels"]:
        if panel["id"] == panel_id:
            fid = f"{panel_id}-{panel['profiles'][0]['id']}" if "profiles" in panel else panel_id
            return [c.id for c in resolve_slice(project, fid).components]
    raise KeyError(f"no ideal panel {panel_id!r}")


def actual_panels(
    project: Dict[str, Any], cut_spec: Dict[str, Any], tool_limits: Dict[str, Any]
) -> List[ActualPanel]:
    """Parse the cut-spec's ``panels`` codes into ActualPanel records.

    Each code '{panelId}:{ref};{ref};...' builds one physical panel from the
    referenced produced pieces (glued in order, top-aligned). The panel length is
    the longest referenced piece. The resolved component sequence is validated
    against the ideal panel's sequence (sequence_ok flags a mismatch). Empty when
    the cut-spec declares no panels.
    """
    codes = cut_spec.get("panels", [])
    if not codes:
        return []
    comp_by_sw: Dict[tuple, str] = {}
    for c in project["components"]:
        comp_by_sw[(c["species"], measure_to_sixteenths(c["width"]))] = c["id"]

    out: List[ActualPanel] = []
    for code in codes:
        panel_id, _, refs_str = code.partition(":")
        refs = refs_str.split(";") if refs_str else []
        pieces = [
            _resolve_piece_ref(ref, cut_spec, project, tool_limits, comp_by_sw)
            for ref in refs
        ]
        length = max((p.length for p in pieces), default=0)
        got = [p.component_id for p in pieces]
        ideal = _ideal_sequence(project, panel_id)
        sequence_ok = got == ideal
        out.append(ActualPanel(panel_id=panel_id, code=code, pieces=pieces,
                               length=length, sequence_ok=sequence_ok))
    return out
