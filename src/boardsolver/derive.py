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
    # When panelSpecs are declared, the overview reflects the actual chosen
    # panels: length = sum of region lengths (+ snipe) and per-profile slice
    # counts = region length / pitch, instead of the ideal design values.
    lim = _limits(tool_limits)
    snipe = measure_to_sixteenths(lim.get("snipeTail", [0, 0]))
    pitch = measure_to_sixteenths(project["sliceDepth"]) + measure_to_sixteenths(lim["miterKerf"])
    spec_by_type: Dict[str, Any] = {}
    for entry in project.get("panelSpecs", []) or []:
        # First spec per type drives the overview row (plaid-style uniform specs).
        spec_by_type.setdefault(entry["panel"], entry)

    out = []
    for panel in project["panels"]:
        pid = panel["id"]
        spec = spec_by_type.get(pid)
        if "profiles" in panel:
            prof_ids = [p["id"] for p in panel["profiles"]]
            if spec:
                region_lens = [measure_to_sixteenths(m) for m in spec["profileLengths"]]
                profiles = [(prof_ids[i], region_lens[i] // pitch) for i in range(len(prof_ids))]
            else:
                profiles = [(p["id"], p["slices"]) for p in panel["profiles"]]
            fullest_id = f"{pid}-{panel['profiles'][0]['id']}"
        else:
            if spec:
                region_lens = [measure_to_sixteenths(m) for m in spec["profileLengths"]]
                profiles = [("", region_lens[0] // pitch)]
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
        if spec:
            length = sum(measure_to_sixteenths(m) for m in spec["profileLengths"]) + snipe
        else:
            length = panel_length(panel, project, tool_limits)
        total_slices = sum(n for _, n in profiles)
        out.append(
            PanelSummary(
                id=pid,
                length=length,
                total_slices=total_slices,
                profiles=profiles,
                height=height,
                ripped=ripped,
                fullest_components=comps,
                sequence=" · ".join(c.id for c in resolved.components),
            )
        )
    return out


# --------------------------------------------------------------------------- #
# volume sanity check (per species): finished vs available vs required loss
# --------------------------------------------------------------------------- #

@dataclass(frozen=True)
class VolumeRow:
    species: str
    finished: Sixteenths   # cubic sixteenths of surfaced product
    available: Sixteenths  # cubic sixteenths of inventory stock
    required_loss: Sixteenths  # cubic sixteenths that MUST be lost producing it


def volume_sanity(
    project: Dict[str, Any], tool_limits: Dict[str, Any]
) -> List[VolumeRow]:
    """Per-species volume sanity check, in cubic sixteenths.

    - Finished: every installed component piece (one per component per slice
      placement in the grid, times batch) at width x finishedThickness x row
      height (panel thickness, or sliceStrips width for a ripped panel).
    - Available: sum of inventory board volumes (length x width x thickness).
    - Required loss: volume that MUST be lost to produce each finished piece:
        * flatten/router-sled: width x (sliceDepth - finishedThickness) x height,
        * 4-edge planing: minPlaneLoss x sliceDepth x 2 x (width + height),
        * one miter kerf on the end-grain face: miterKerf x width x height.
    """
    lim = _limits(tool_limits)
    batch = project.get("batch", 1)
    ft = measure_to_sixteenths(project["finishedThickness"])
    sd = measure_to_sixteenths(project["sliceDepth"])
    mpl = measure_to_sixteenths(lim.get("minPlaneLoss", [0, 0]))
    mk = measure_to_sixteenths(lim["miterKerf"])
    flat = sd - ft
    comp = {c["id"]: c for c in project["components"]}
    panels = {p["id"]: p for p in project["panels"]}

    def row_height(pid: str) -> Sixteenths:
        pn = panels[pid]
        if "sliceStrips" in pn:
            return measure_to_sixteenths(pn["sliceStrips"]["width"])
        return measure_to_sixteenths(pn["thickness"])

    fin: "OrderedDict[str, int]" = OrderedDict()
    loss: "OrderedDict[str, int]" = OrderedDict()
    for row in project.get("sliceGrid", []):
        for cell in row:
            pid = cell["sliceId"].split("-")[0]
            rh = row_height(pid)
            for pc in panels[pid]["components"]:
                c = comp[pc["type"]]
                sp = c["species"]
                w = measure_to_sixteenths(c["width"])
                fin[sp] = fin.get(sp, 0) + w * ft * rh
                piece_loss = (
                    w * flat * rh
                    + mpl * sd * 2 * (w + rh)
                    + mk * w * rh
                )
                loss[sp] = loss.get(sp, 0) + piece_loss

    avail: "OrderedDict[str, int]" = OrderedDict()
    for b in project["boards"]:
        v = measure_to_sixteenths(b["length"]) * measure_to_sixteenths(b["width"]) \
            * measure_to_sixteenths(b["thickness"])
        avail[b["species"]] = avail.get(b["species"], 0) + v

    species = sorted(set(list(fin) + list(avail) + list(loss)))
    return [
        VolumeRow(
            species=sp,
            finished=fin.get(sp, 0) * batch,
            available=avail.get(sp, 0),
            required_loss=loss.get(sp, 0) * batch,
        )
        for sp in species
    ]


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
    """Count every component STICK the plan's panels require.

    Stick model: a panel is a glue-up of full-length sticks that is then sliced
    crosswise, so one stick per component position yields all of that panel's
    slices. Demand is therefore one stick per component in each physical panel's
    sequence (panels come from panelSpecs expanded by count; see panel_specs),
    at that panel's physical length. Keyed by (id, species, width, length).

    (It is NOT one piece per installed slice — slicing multiplies a single stick
    into many slices, so counting per slice over-states demand ~slices-fold.)
    """
    panels_by_id = {p["id"]: p for p in project["panels"]}
    comp_by_id = {c["id"]: c for c in project["components"]}
    tally: "OrderedDict[tuple, int]" = OrderedDict()
    for spec in panel_specs(project, {}, tool_limits):
        panel = panels_by_id[spec.panel_id]
        plen = spec.length  # physical panel length (regions + snipe)
        for pc in panel["components"]:
            c = comp_by_id[pc["type"]]
            key = (c["id"], c["species"], measure_to_sixteenths(c["width"]), plen)
            tally[key] = tally.get(key, 0) + 1
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
    slice_oversupply_threshold: int = 5,     # extra slices beyond which panels are too big
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
    # Skip bought (ghost) boards: a ghost board is bought to size, so a tight
    # margin on it is expected, not a risk worth flagging.
    for r in rips:
        if not r.buy_required and 0 <= r.margin < small_margin_threshold:
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

    # --- Slice-layer checks: panel slice output vs. grid x batch demand ---- #
    sf = slice_fulfillment(project, cut_spec, tool_limits)
    slice_short = [r for r in sf if r.supplied < r.demand]
    if slice_short:
        names = ", ".join(
            f"{r.slice_id} (short {r.demand - r.supplied})" for r in slice_short
        )
        out.append(Warning(
            "yellow", "slice_shortfall",
            f"The panels produce fewer slices than the finished boards need: "
            f"{names}. Build more (or larger) panels of these types.",
        ))
    # No spare slices: demand met exactly (offset 0) with no cushion.
    exact = [r for r in sf if r.supplied == r.demand and r.demand > 0]
    if exact and not slice_short:
        names = ", ".join(r.slice_id for r in exact)
        out.append(Warning(
            "gray", "no_spare_slices",
            f"No spare slices for: {names} (supply exactly meets demand). Consider "
            f"slightly larger/more panels so a bad slice does not cause a shortfall.",
        ))
    # Large over-supply: panels produce far more slices than needed (too big).
    oversupply = [r for r in sf if r.supplied - r.demand > slice_oversupply_threshold]
    if oversupply:
        names = ", ".join(
            f"{r.slice_id} (+{r.supplied - r.demand})" for r in oversupply
        )
        out.append(Warning(
            "gray", "slice_oversupply",
            f"The panels produce far more slices than needed (> "
            f"{slice_oversupply_threshold}): {names}. The panels are likely too "
            f"big — shorten them to use less material.",
        ))

    # --- Components cannot fulfill the speced panels ---------------------- #
    # Every component the panel specs require vs. what the cut list supplies.
    panel_need = _panel_component_demand(project, cut_spec, tool_limits)
    supply = component_supply(project, cut_spec, tool_limits)
    from collections import Counter as _C
    have = _C((p.component_id, p.length) for p in supply if p.component_id)
    unmet = {}
    for (cid, length), need in panel_need.items():
        deficit = need - have.get((cid, length), 0)
        if deficit > 0:
            unmet[cid] = unmet.get(cid, 0) + deficit
    if unmet:
        names = ", ".join(f"{cid} (short {n})" for cid, n in unmet.items())
        out.append(Warning(
            "yellow", "panel_components_short",
            f"The cut list cannot supply all components the speced panels need: "
            f"{names}.",
        ))

    return out


def _panel_component_demand(project, cut_spec, tool_limits):
    """Components (id, length) required to build the panel specs, with counts.

    For each panel spec, its recipe components are needed at the panel's length
    (main list) / prescribed smaller-component lengths. Simplified: each spec
    needs one of every component in its matched sequence at the spec length.
    """
    from collections import Counter
    need: "Counter" = Counter()
    for spec in panel_specs(project, cut_spec, tool_limits):
        panel = next(p for p in project["panels"] if p["id"] == spec.panel_id)
        # Use the fullest-profile sequence as the component requirement.
        fid = f"{spec.panel_id}-{panel['profiles'][0]['id']}" if "profiles" in panel else spec.panel_id
        for c in resolve_slice(project, fid).components:
            need[(c.id, spec.length)] += 1
    return need


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
    lim = _limits(tool_limits)
    pitch = measure_to_sixteenths(project["sliceDepth"]) + measure_to_sixteenths(lim["miterKerf"])
    # panelSpecs (when declared) set region slice counts and panel multiplicity.
    spec_regions: Dict[str, List[int]] = {}
    spec_count: Dict[str, int] = {}
    for e in project.get("panelSpecs", []) or []:
        if e["panel"] not in spec_regions:
            spec_regions[e["panel"]] = [measure_to_sixteenths(m) // pitch for m in e["profileLengths"]]
        spec_count[e["panel"]] = spec_count.get(e["panel"], 0) + e.get("count", 1)
    for panel in project["panels"]:
        ss = panel.get("sliceStrips")
        if not ss:
            continue
        thickness = measure_to_sixteenths(panel["thickness"])
        strip_count = ss["count"]
        strip_width = measure_to_sixteenths(ss["width"])
        # Enumerate (profile_id, slice_count) just like panel_summaries. When a
        # panelSpec exists, use its region slice counts x panel multiplicity.
        pid = panel["id"]
        regs = spec_regions.get(pid)
        mult = spec_count.get(pid, 1)
        if "profiles" in panel:
            regions = [
                (p["id"], (regs[i] if regs else p["slices"]) * mult)
                for i, p in enumerate(panel["profiles"])
            ]
        else:
            regions = [(None, (regs[0] if regs else panel["slices"]) * mult)]
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


def _ideal_sequences(project: Dict[str, Any], panel_id: str) -> List[List[str]]:
    """Each ideal-panel profile's component id sequence (fullest first).

    Returns a list of sequences: one per profile for a profiled panel, or a
    single sequence for a single-profile panel. An actual panel is valid if its
    resolved sequence matches ANY of these (it may realize any profile).
    """
    for panel in project["panels"]:
        if panel["id"] == panel_id:
            if "profiles" in panel:
                return [
                    [c.id for c in resolve_slice(project, f"{panel_id}-{p['id']}").components]
                    for p in panel["profiles"]
                ]
            return [[c.id for c in resolve_slice(project, panel_id).components]]
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
    codes = cut_spec.get("panels")
    if not codes:
        # No authored panels: auto-generate from the produced pieces.
        codes = auto_panels(project, cut_spec, tool_limits)
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
        ideal = _ideal_sequences(project, panel_id)
        sequence_ok = got in ideal
        out.append(ActualPanel(panel_id=panel_id, code=code, pieces=pieces,
                               length=length, sequence_ok=sequence_ok))
    return out


# --------------------------------------------------------------------------- #
# panel recipes + auto-generation of panel codes when the cut-spec omits them
# --------------------------------------------------------------------------- #

@dataclass(frozen=True)
class RecipePart:
    position: int        # index in the full (fullest-profile) sequence
    component_id: str
    species: str
    width: Sixteenths
    ratio: float         # fraction of the panel this component spans (1.0 = full)


@dataclass(frozen=True)
class PanelRecipe:
    panel_id: str
    main: List[RecipePart]     # components present in every profile (ratio 1.0)
    smaller: List[RecipePart]  # drop-out components (ratio < 1.0), by minimumRatio


def panel_recipe(project: Dict[str, Any], panel: Dict[str, Any]) -> PanelRecipe:
    """Split a panel's components into the main list (present in every profile,
    full length) and the smaller components (drop-outs, each spanning a fraction
    of the panel = slices-in-profiles-it-appears / total slices).
    """
    comps_by_id = {c["id"]: c for c in project["components"]}
    if "profiles" in panel:
        prof_slices = [p["slices"] for p in panel["profiles"]]
    else:
        prof_slices = [panel["slices"]]
    total = sum(prof_slices)
    nprof = len(prof_slices)

    main: List[RecipePart] = []
    smaller: List[RecipePart] = []
    for pos, pc in enumerate(panel["components"]):
        mp = pc.get("maxProfile")              # appears in profiles [0, mp)
        appears = nprof if mp is None else mp
        covered = sum(prof_slices[:appears])
        ratio = covered / total
        comp = comps_by_id[pc["type"]]
        part = RecipePart(
            position=pos, component_id=comp["id"], species=comp["species"],
            width=measure_to_sixteenths(comp["width"]), ratio=ratio,
        )
        if ratio >= 1.0:
            main.append(part)
        else:
            smaller.append(part)
    return PanelRecipe(panel_id=panel["id"], main=main, smaller=smaller)


def auto_panels(
    project: Dict[str, Any], cut_spec: Dict[str, Any], tool_limits: Dict[str, Any],
    threshold: Sixteenths = 2,   # +/- 1/8" tolerance for smaller-component length
) -> List[str]:
    """Greedily build panel codes from the produced pieces when the cut-spec has
    no authored ``panels``.

    Per panel recipe: find a complete set of MAIN-LIST components all at one
    length (the panel body / full length); usable length = full length - snipe;
    each SMALLER component's prescribed length = ratio * usable length, matched
    against supply within +/- threshold. A panel forms only when the main list
    is complete and every smaller component is satisfied. Pieces are consumed as
    used; panels are attempted in project order, fullest body first.\n    """
    lim = _limits(tool_limits)
    snipe = measure_to_sixteenths(lim.get("snipeTail", [0, 0]))

    # Supply pool: component_id -> length -> list of refs (mutable, consumable).
    pool: Dict[str, Dict[Sixteenths, List[str]]] = {}
    comp_by_sw: Dict[tuple, str] = {
        (c["species"], measure_to_sixteenths(c["width"])): c["id"]
        for c in project["components"]
    }
    for r in board_rips(project, cut_spec, tool_limits):
        for si, strip in enumerate(r.strips):
            width = measure_to_sixteenths(strip["width"])
            cid = comp_by_sw.get((r.species, width))
            if cid is None:
                continue
            for ci, cut in enumerate(strip.get("cuts", [])):
                L = measure_to_sixteenths(cut)
                pool.setdefault(cid, {}).setdefault(L, []).append(f"{r.id}/{si}/{ci}")

    recipes = {p["id"]: panel_recipe(project, p) for p in project["panels"]}
    codes: List[str] = []

    made_one = True
    while made_one:
        made_one = False
        for panel in project["panels"]:
            rec = recipes[panel["id"]]
            # Candidate body lengths: any length that could satisfy the whole main
            # list. Try longest first so bigger panels form first.
            main_ids = [p.component_id for p in rec.main]
            lengths = sorted(
                {L for cid in set(main_ids) for L in pool.get(cid, {})},
                reverse=True,
            )
            for body_len in lengths:
                # Enough main-list pieces at body_len?
                from collections import Counter
                need = Counter(main_ids)
                if any(len(pool.get(cid, {}).get(body_len, [])) < n for cid, n in need.items()):
                    continue
                usable = body_len - snipe
                # Assemble the full sequence in position order, consuming pieces.
                # If any part can't be filled, roll back every pop and move on.
                seq_parts = sorted(rec.main + rec.smaller, key=lambda p: p.position)
                refs_in_order = []
                popped = []  # (cid, length, ref) to restore on failure
                good = True
                for p in seq_parts:
                    if p.ratio >= 1.0:
                        refs = pool.get(p.component_id, {}).get(body_len, [])
                        if not refs:
                            good = False
                            break
                        ref = refs.pop()
                        popped.append((p.component_id, body_len, ref))
                    else:
                        target = round(p.ratio * usable)
                        lengths_map = pool.get(p.component_id, {})
                        cand = sorted(
                            (abs(L - target), L)
                            for L, rs in lengths_map.items()
                            if rs and abs(L - target) <= threshold
                        )
                        if not cand:
                            good = False
                            break
                        L = cand[0][1]
                        ref = pool[p.component_id][L].pop()
                        popped.append((p.component_id, L, ref))
                    refs_in_order.append(ref)
                if not good:
                    for cid, L, ref in popped:
                        pool[cid][L].append(ref)
                    continue
                codes.append(f"{panel['id']}:" + ";".join(refs_in_order))
                made_one = True
                break  # re-loop panels from the top after making one
    return codes


# --------------------------------------------------------------------------- #
# (end auto_panels)
# --------------------------------------------------------------------------- #


# --------------------------------------------------------------------------- #
# two-layer model: panel specs -> slice supply ; grid x batch -> slice demand
# --------------------------------------------------------------------------- #

@dataclass(frozen=True)
class PanelSpec:
    panel_id: str
    source: str                 # "actual" | "ideal"
    length: Sixteenths          # full length (ideal derived, or actual body length)
    usable: Sixteenths          # length - snipe
    profile_slices: List[tuple] # [(profile_id or None, slice_count)]
    code: Optional[str]         # the actual panel code, if source == "actual"


def panel_specs(
    project: Dict[str, Any], cut_spec: Dict[str, Any], tool_limits: Dict[str, Any]
) -> List[PanelSpec]:
    """The fixed physical panels the plan builds, one PanelSpec per panel.

    Source of truth is ``project['panelSpecs']`` when present: each entry names a
    panel type and its per-profile region lengths, and is expanded by ``count``
    into that many identical PanelSpec objects. A profile region's slice count is
    its length divided by the slice pitch (sliceDepth + miterKerf). When no
    panelSpecs are declared, fall back to one ideal panel per type (declared
    profile slice counts).
    """
    lim = _limits(tool_limits)
    snipe = measure_to_sixteenths(lim.get("snipeTail", [0, 0]))
    slice_depth = measure_to_sixteenths(project["sliceDepth"])
    miter_kerf = measure_to_sixteenths(lim["miterKerf"])
    pitch = slice_depth + miter_kerf

    panels_by_id = {p["id"]: p for p in project["panels"]}
    declared = project.get("panelSpecs")
    specs: List[PanelSpec] = []

    if declared:
        for entry in declared:
            pid = entry["panel"]
            panel = panels_by_id.get(pid)
            if panel is None:
                raise ValueError(f"panelSpecs references unknown panel '{pid}'")
            region_lens = [measure_to_sixteenths(m) for m in entry["profileLengths"]]
            if "profiles" in panel:
                prof_ids = [p["id"] for p in panel["profiles"]]
            else:
                prof_ids = [None]
            if len(region_lens) != len(prof_ids):
                raise ValueError(
                    f"panelSpecs for '{pid}' has {len(region_lens)} profileLengths "
                    f"but the panel has {len(prof_ids)} profile(s)"
                )
            prof_slices = [
                (prof_ids[i], region_lens[i] // pitch) for i in range(len(prof_ids))
            ]
            body = sum(region_lens)
            length = body + snipe
            for _ in range(entry.get("count", 1)):
                specs.append(PanelSpec(
                    panel_id=pid, source="spec", length=length, usable=body,
                    profile_slices=prof_slices, code=None,
                ))
        return specs

    # Fallback: no panelSpecs declared -> one ideal panel per type.
    for panel in project["panels"]:
        pid = panel["id"]
        if "profiles" in panel:
            prof_slices = [(p["id"], p["slices"]) for p in panel["profiles"]]
        else:
            prof_slices = [(None, panel["slices"])]
        length = panel_length(panel, project, tool_limits)
        specs.append(PanelSpec(
            panel_id=pid, source="ideal", length=length, usable=length - snipe,
            profile_slices=prof_slices, code=None,
        ))
    return specs


@dataclass(frozen=True)
class SliceDemandRow:
    slice_id: str       # "S-L", "H-R", ...
    per_board: int      # grid placements in one finished board
    batch: int          # number of finished boards
    demand: int         # per_board * batch
    supplied: int       # INSTALLED slices supplied (pre_rip_supplied * rip_mult)
    shortfall: int
    pre_rip_supplied: int = 0   # crosscut slices off the panels, before ripping
    rip_mult: int = 1           # sliceStrips.count for this slice's panel (else 1)


def slice_fulfillment(
    project: Dict[str, Any], cut_spec: Dict[str, Any], tool_limits: Dict[str, Any]
) -> List[SliceDemandRow]:
    """Layer 2: grid x batch slice demand vs. slices produced by the panel specs.

    Demand is the source of truth: every slice placement in the grid, times the
    batch count. Supply is the fixed slices the panel specs produce (snipe lost).
    Whether the panels were fully built from the cut list is IGNORED here.
    """
    batch = project.get("batch", 1)
    # Demand: count slice placements in one board's grid (per-board).
    per_board: "OrderedDict[str, int]" = OrderedDict()
    for row in project.get("sliceGrid", []):
        for cell in row:
            sid = cell["sliceId"]
            per_board[sid] = per_board.get(sid, 0) + 1

    # Supply: crosscut slices produced by panel specs, keyed as panel-profile.
    # A sliceStrips panel rips each crosscut slice into count installed slices,
    # so the INSTALLED supply is the crosscut count times the rip multiplier.
    panels_by_id = {p["id"]: p for p in project["panels"]}
    rip_mult_by_panel: Dict[str, int] = {}
    for p in project["panels"]:
        ss = p.get("sliceStrips")
        rip_mult_by_panel[p["id"]] = ss["count"] if ss else 1
    pre_rip: Dict[str, int] = {}
    for spec in panel_specs(project, cut_spec, tool_limits):
        for prof_id, n in spec.profile_slices:
            sid = f"{spec.panel_id}-{prof_id}" if prof_id else spec.panel_id
            pre_rip[sid] = pre_rip.get(sid, 0) + n

    rows = []
    for sid, pb in per_board.items():
        d = pb * batch
        panel_id = sid.split("-")[0]
        mult = rip_mult_by_panel.get(panel_id, 1)
        pre = pre_rip.get(sid, 0)
        s = pre * mult
        rows.append(SliceDemandRow(
            slice_id=sid, per_board=pb, batch=batch, demand=d, supplied=s,
            shortfall=max(d - s, 0), pre_rip_supplied=pre, rip_mult=mult,
        ))
    return rows
