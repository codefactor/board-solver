"""Pure geometry helpers. No drawing, no file I/O.

All internal measurement arithmetic is done in **integer sixteenths of an inch**
(:data:`Sixteenths`). The schema's serialized form is the ``[whole_inches,
sixteenths]`` tuple (:data:`Measurement`). Convert at the edges only:

* ``measure_to_sixteenths`` / ``sixteenths_to_measure`` — tuple <-> int sixteenths
* ``measure_to_inches`` / ``inches_to_measure`` — tuple <-> float inches
* ``px(sixteenths, scale)`` — int sixteenths -> float pixels (drawing edge)

Keeping the domain in integer sixteenths avoids floating-point precision loss,
since every board mutation on every axis is a whole number of sixteenths.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

Sixteenths = int
Measurement = Tuple[int, int]  # (whole_inches, sixteenths); lists accepted on input


# --------------------------------------------------------------------------- #
# measurement <-> sixteenths <-> inches
# --------------------------------------------------------------------------- #

def measure_to_sixteenths(m: Measurement) -> Sixteenths:
    """``[47, 12] -> 47*16 + 12 = 764`` sixteenths."""
    whole, sixteenths = m
    return whole * 16 + sixteenths


def sixteenths_to_measure(s: Sixteenths) -> Measurement:
    """``764 -> [47, 12]``. Inverse of :func:`measure_to_sixteenths`."""
    if s < 0:
        raise ValueError(f"measurement sixteenths must be non-negative, got {s}")
    return (s // 16, s % 16)


def measure_to_inches(m: Measurement) -> float:
    """``[47, 12] -> 47.75``; ``[0, 2] -> 0.125``."""
    return measure_to_sixteenths(m) / 16


def inches_to_measure(x: float) -> Measurement:
    """Round inches to the nearest sixteenth and return the tuple.

    ``47.75 -> [47, 12]``. Uses round-half-up so e.g. an exact half-sixteenth
    rounds up deterministically rather than banker's-rounding.
    """
    import math

    total_sixteenths = math.floor(x * 16 + 0.5)
    return sixteenths_to_measure(int(total_sixteenths))


def px(s: Sixteenths, scale: float) -> float:
    """Convert integer sixteenths to pixels at ``scale`` pixels-per-inch."""
    return (s / 16) * scale


# --------------------------------------------------------------------------- #
# resolve_slice / slice_length
# --------------------------------------------------------------------------- #

@dataclass(frozen=True)
class ResolvedComponent:
    id: str
    species: str
    width: Sixteenths  # component stripe width, in sixteenths


@dataclass(frozen=True)
class ResolvedSlice:
    panel_id: str
    profile_id: Optional[str]
    components: List[ResolvedComponent]  # ordered, after maxProfile filtering
    height: Sixteenths  # panel thickness, OR sliceStrips.width if the panel rips


def _index_components(project: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    return {c["id"]: c for c in project["components"]}


def _find_panel(project: Dict[str, Any], panel_id: str) -> Dict[str, Any]:
    for p in project["panels"]:
        if p["id"] == panel_id:
            return p
    raise KeyError(f"no panel with id {panel_id!r}")


def _profile_index(panel: Dict[str, Any], profile_id: Optional[str]) -> int:
    """Return the 0-based index of ``profile_id`` within the panel's profiles.

    For a single-profile panel (``slices`` form) the index is 0 and
    ``profile_id`` must be ``None``.
    """
    if "profiles" not in panel:
        if profile_id is not None:
            raise KeyError(
                f"panel {panel['id']!r} has no profiles but slice id "
                f"requested profile {profile_id!r}"
            )
        return 0
    if profile_id is None:
        raise KeyError(
            f"panel {panel['id']!r} has profiles; a profile id is required "
            f"(e.g. {panel['id']}-{panel['profiles'][0]['id']})"
        )
    for i, prof in enumerate(panel["profiles"]):
        if prof["id"] == profile_id:
            return i
    raise KeyError(f"panel {panel['id']!r} has no profile {profile_id!r}")


def _split_slice_id(slice_id: str) -> Tuple[str, Optional[str]]:
    parts = slice_id.split("-")
    if len(parts) == 1:
        return parts[0], None
    if len(parts) == 2:
        return parts[0], parts[1]
    raise ValueError(f"slice id {slice_id!r} has more than two segments")


def resolve_slice(project: Dict[str, Any], slice_id: str) -> ResolvedSlice:
    """Resolve a slice id (``"S-L"``, ``"H-R"``, or single-profile ``"X"``).

    Applies the ``maxProfile`` rule: for a panel with profiles, the profile at
    0-based index ``k`` includes a component iff the component has no
    ``maxProfile`` OR ``maxProfile > k``. Index 0 includes every component.

    ``height`` is the panel thickness, OR ``sliceStrips.width`` when the panel
    rips its slices into strips.
    """
    panel_id, profile_id = _split_slice_id(slice_id)
    panel = _find_panel(project, panel_id)
    k = _profile_index(panel, profile_id)

    comps_by_id = _index_components(project)
    resolved: List[ResolvedComponent] = []
    for pc in panel["components"]:
        max_profile = pc.get("maxProfile")
        included = max_profile is None or max_profile > k
        if not included:
            continue
        comp = comps_by_id[pc["type"]]
        resolved.append(
            ResolvedComponent(
                id=comp["id"],
                species=comp["species"],
                width=measure_to_sixteenths(comp["width"]),
            )
        )

    if "sliceStrips" in panel:
        height = measure_to_sixteenths(panel["sliceStrips"]["width"])
    else:
        height = measure_to_sixteenths(panel["thickness"])

    return ResolvedSlice(
        panel_id=panel_id,
        profile_id=profile_id,
        components=resolved,
        height=height,
    )


def slice_length(resolved: ResolvedSlice) -> Sixteenths:
    """Sum of the resolved slice's component widths, in sixteenths."""
    return sum(c.width for c in resolved.components)
