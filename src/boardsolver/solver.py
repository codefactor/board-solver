"""Round 3 (greedy) solver: derive a workable cut-specs.yaml from a project.

This is deliberately NOT an optimiser. It guarantees, by construction:

* every component stick demanded by ``panelSpecs`` is produced,
* no inventory board is ever over-ripped (margin >= 0 on every sourced board),
* demand that cannot fit in inventory goes on a bought (ghost) board.

It does not promise a locally optimal packing. A human can tweak the
output afterwards; that is the intended workflow for a project that is
only built every few months.

Second pass (always run)
------------------------
After the greedy pass, ``solve`` always runs an improvement pass, and
repeats it until it stops improving -- a second, third, and further
pass as needed. A trial packing is only ever committed if it is
strictly better than the packing it replaces, under this comparator:

* ghost board volume decreases, OR
* ghost board volume stays the same AND the leftover margins on real
  boards increase.

If both quantities stay the same, the two packings are considered
equal, and the original is kept -- no churn, no sideways moves are
committed on their own. Intermediate steps inside one trial (for
example a swap chain that makes room for a ghost strip) are only
committed as a whole, and only if the final packing is strictly
better, so the output is guaranteed to be the same or better than
the greedy output, never worse.

Ghost volume is the summed strip material on ghost boards
(width x cut length, in sixteenths). Leftover margin is the summed
docwriter margin over real boards of that species. The pass works
per species, in three ways, in order: direct placement of a ghost
strip on a real board; ejection (remove one or two strips from a
real board to make room for a ghost strip, and place the removed
strips elsewhere); and a max-margin swap chain (repeatedly swap
strips between real boards in a way that raises the largest real
margin, until a ghost strip fits). If none of those produces a
strictly better packing, the greedy packing is returned unchanged.

Child-split pass (always run, after the ghost passes)
-----------------------------------------------------
A fourth improvement attempt, ``_try_child_split``, implements the
trigger in ``docs/source-remainder.md``: scan a blank's strips
top-down; if an early strip is far underutilized (utilization < 50%,
with a highly utilized strip before it) and a later strip is more
utilized but narrower than it, keep the strips before the bad strip
on the parent, move the bad strip and later strips (plus, if they
fit, all the sticks of other blanks of the same species that would
drop entirely) into exactly two sourceRemainder children, grouped
by piece length, each child length-matched to its pieces. The
split is committed only if it is strictly better under the
area-based score ``_child_split_score``:
(ghost volume, raw blank count, waste area + loss area), lower is
better. Waste and loss are areas (width x trimmed length), so a
smaller blank is rewarded: shortening a blank, or dropping one,
leaves a full-width raw leftover instead of narrow strip tails,
and that shows up as less waste + loss. The old margin-width score
does not reward smaller blanks at all. Blank lengths are never
increased, and a child never exceeds its parent's remaining slab
length — hard constraints, because ``derive.warnings`` does not
check sourceRemainder length overflow.

Method
------
1. Demand comes from ``derive.component_demand`` (one stick per component
   position in each physical panel, at that panel's physical length).
2. Sticks are grouped by (species, width, length) and turned into strips:
   a strip holds as many sticks of one group as fit in one blank, allowing
   one miter kerf between crosscuts.
3. Strips are placed largest-width first (first-fit-decreasing order).
   For each strip, the best fit is the existing blank of the same species
   whose margin after placement is smallest but still >= 0. Margin is
   exactly the docwriter's: ``source_width - used - loss``, with
   ``loss = n_strips * (sawKerf + minPlaneLoss)``.
4. If no existing blank fits, a new blank is opened: first from an
   already-started inventory board that still has length left, then from
   an unused inventory board of that species. A blank is only opened if
   the strip's cuts fit in it lengthwise.
5. If no inventory blank can take the strip, a ghost (bought) board is
   created for that species, capped at the widest inventory width for
   the species so a ghost still looks like a real board.
6. After packing (and after the improvement passes), each blank is
   trimmed to the longest strip it carries: blank length = max over
   its strips of (sum of cuts + miter kerfs between cuts). This is
   the crosscut-before-rip step. Without it, every blank kept the
   full 48 in nominal length, so the unused length fragmented into
   a narrow tail at the end of every strip. Trimmed, that unused
   length instead stays on the source board as a full-width leftover
   (see crosscut_blanks), usable for later builds. Shorter strips
   on the same blank still have tails — a shared blank is one
   rectangle — but those tails are now bounded by the longest strip,
   not by the full nominal length.

Blank ids follow the existing convention: source id + a letter
(BC1A, BC1B, ...). Ghost ids are GH-<initial><n> (GH-C, GH-C2, ...).
"""

from __future__ import annotations

import argparse
import math
from collections import defaultdict
from typing import Any, Dict, List, Optional

import yaml

from .derive import component_demand
from .geometry import measure_to_sixteenths


def _lim(tool_limits: Dict[str, Any]) -> Dict[str, Any]:
    return tool_limits["limits"] if "limits" in tool_limits else tool_limits


def _fmt(m: int) -> str:
    """Sixteenths -> YAML measurement pair [whole, remainder]."""
    return f"[{m // 16}, {m % 16}]"


class _Blank:
    def __init__(self, bid: str, species: str, width: int, length: int,
                 source: Optional[str] = None,
                 buy_species: Optional[str] = None,
                 source_remainder: Optional[str] = None):
        self.id = bid
        self.species = species
        self.width = width  # capacity width (source width, or ghost cap)
        self.length = length
        self.source = source
        self.buy_species = buy_species
        # For a sourceRemainder child: the parent cut-spec board id whose
        # margin slab this board is crosscut from. Such a board consumes
        # no new raw stock; its width is the parent's margin slab width.
        self.source_remainder = source_remainder
        self.strips: List[Dict[str, Any]] = []  # {"width": int, "cuts": [int]}

    @property
    def used(self) -> int:
        return sum(s["width"] for s in self.strips)

    def margin_after(self, strip_width: int, loss_per_strip: int) -> int:
        n = len(self.strips) + 1
        return self.width - (self.used + strip_width) - n * loss_per_strip

    def strip_fits_length(self, cuts: List[int], miter_kerf: int) -> bool:
        total = sum(cuts) + max(len(cuts) - 1, 0) * miter_kerf
        return total <= self.length


def _margin(blank: "_Blank", loss_per_strip: int) -> int:
    return blank.width - blank.used - len(blank.strips) * loss_per_strip


def _can_place(blank: "_Blank", strip: Dict[str, Any],
               loss_per_strip: int, miter_kerf: int) -> bool:
    if not blank.strip_fits_length(strip["cuts"], miter_kerf):
        return False
    return blank.margin_after(strip["width"], loss_per_strip) >= 0


def _species_score(blanks: List["_Blank"], loss_per_strip: int):
    """(ghost volume, -leftover margin) for one species; lower is better."""
    ghost_volume = 0
    leftover = 0
    for blank in blanks:
        if blank.buy_species is not None:
            for strip in blank.strips:
                ghost_volume += strip["width"] * sum(strip["cuts"])
        else:
            leftover += _margin(blank, loss_per_strip)
    return (ghost_volume, -leftover)


def _is_better(new_blanks, old_blanks, loss_per_strip: int) -> bool:
    new_score = _species_score(new_blanks, loss_per_strip)
    old_score = _species_score(old_blanks, loss_per_strip)
    return new_score < old_score


# ---------------------------------------------------------------------------
# Child-split hill climb (sourceRemainder, see docs/source-remainder.md)
#
# The greedy pass packs strips onto raw blanks, and the ghost passes
# above only move ghost strips. Neither ever asks, for a blank whose
# strips are scanned top-down: "the first few strips fill the blank,
# then one strip is far underutilized, and later strips are more
# utilized but cannot use that strip's tail because that strip is
# wider than they are?" That is the trigger for a child split:
#
#   * keep the highly utilized strips before the bad strip on the
#     parent; the parent's margin slab grows by the removed strips'
#     widths + their loss;
#   * crosscut that slab at the bad strip's utilization edge;
#   * split the remaining pieces (removed strips, plus pieces from
#     other blanks of the same species that would drop entirely)
#     by piece length into exactly two children, each length-matched
#     to its pieces, so no child strip carries an offcut tail.
#
# One child is pointless (just relabelling the parent's strips), so a
# split with one length group is rejected. Three or more length
# groups are also rejected for now: the point is the two-child case.
#
# Scoring is area-based, not margin-width-based, so a smaller blank
# is rewarded: waste and loss areas scale with board length, so a
# shorter blank (or a dropped blank) leaves a full-width raw leftover
# instead of narrow strip tails, and that shows up as less waste +
# loss. The old (_species_score) margin-width score does not reward
# shorter blanks at all. Acceptance is lexicographic:
#   (ghost volume, raw blank count, waste area + loss area)
# lower is better. Blank lengths are never increased, and a child
# never exceeds its parent's remaining slab length — those are hard
# constraints, not score terms, because the planner (derive.warnings)
# does not check sourceRemainder length overflow.
# ---------------------------------------------------------------------------


def _strip_total(strip: Dict[str, Any], miter_kerf: int) -> int:
    return sum(strip["cuts"]) + max(len(strip["cuts"]) - 1, 0) * miter_kerf


def _trimmed_len(blank: "_Blank", miter_kerf: int) -> int:
    if not blank.strips:
        return 0
    return max(_strip_total(s, miter_kerf) for s in blank.strips)


def _expand_sticks(blank: "_Blank") -> List[Dict[str, Any]]:
    """One stick per cut: {"width": strip width, "length": cut length}."""
    sticks = []
    for strip in blank.strips:
        for cut in strip["cuts"]:
            sticks.append({"width": strip["width"], "length": cut})
    return sticks


def _child_split_score(blanks, loss_per_strip: int, miter_kerf: int):
    """(ghost volume, raw blank count, waste area + loss area).

    Waste is terminal waste only: strip tails, child margins, and
    unclaimed parent slab tails. A parent margin slab that feeds
    children is not waste — it is partitioned into child boards
    (their strips, loss and margins) plus the unclaimed tail, and
    only that tail is counted. Loss is per-strip (sawKerf +
    minPlaneLoss) times board length, summed over every board
    including children. Areas are in sixteenths-squared; lengths
    and widths are in sixteenths, so the scale is consistent.
    Ghost volume uses the old definition (width x cut length).
    """
    children_by_parent: Dict[str, List["_Blank"]] = {}
    for blank in blanks:
        if blank.source_remainder is not None:
            children_by_parent.setdefault(blank.source_remainder, []).append(blank)
    ghost_volume = 0
    raw_count = 0
    waste = 0
    loss = 0
    for blank in blanks:
        if blank.buy_species is not None:
            for strip in blank.strips:
                ghost_volume += strip["width"] * sum(strip["cuts"])
            continue
        if blank.source_remainder is None:
            raw_count += 1
        # Trimmed length is the board's real length: for a child it
        # is its declared length (strips fill it by construction, but
        # use the trimmed value so a shorter child is scored shorter).
        blen = _trimmed_len(blank, miter_kerf) if blank.strips else blank.length
        if not blank.strips:
            continue
        loss += len(blank.strips) * loss_per_strip * blen
        for strip in blank.strips:
            waste += (blen - _strip_total(strip, miter_kerf)) * strip["width"]
        margin_w = blank.width - blank.used - len(blank.strips) * loss_per_strip
        children = children_by_parent.get(blank.id, [])
        if children:
            used_len = sum(_trimmed_len(c, miter_kerf) for c in children)
            used_len += max(len(children) - 1, 0) * miter_kerf
            tail_len = blen - used_len
            if tail_len > 0:
                waste += tail_len * margin_w
        else:
            if margin_w > 0:
                waste += margin_w * blen
    return (ghost_volume, raw_count, waste + loss)


def _try_child_split(blanks, loss_per_strip: int, miter_kerf: int):
    """Try one sourceRemainder child split. Returns new blanks or None."""
    import copy
    original_score = _child_split_score(blanks, loss_per_strip, miter_kerf)
    # Real blanks only (source boards, not ghosts, not existing children).
    real = [b for b in blanks
            if b.buy_species is None and b.source_remainder is None and b.strips]
    for parent in real:
        # Diagram order is widest strip first, stable.
        strips = sorted(parent.strips, key=lambda s: -s["width"])
        plen = _trimmed_len(parent, miter_kerf)
        if plen <= 0 or len(strips) < 3:
            continue
        utils = [_strip_total(s, miter_kerf) / plen for s in strips]
        trigger = None
        for i in range(1, len(strips)):
            if utils[i] >= 0.5:
                continue
            if max(utils[:i]) < 0.8:
                continue
            later = [j for j in range(i + 1, len(strips))
                     if utils[j] >= utils[i] + 0.3
                     and strips[j]["width"] < strips[i]["width"]]
            if not later:
                continue
            trigger = i
            break
        if trigger is None:
            continue
        kept = strips[:trigger]
        removed = strips[trigger:]
        kept_used = sum(s["width"] for s in kept)
        slab_w = parent.width - kept_used - len(kept) * loss_per_strip
        if slab_w <= 0:
            continue
        removed_sticks = []
        for strip in removed:
            for cut in strip["cuts"]:
                removed_sticks.append({"width": strip["width"], "length": cut})
        # Donor blanks: other real blanks of this species, fewest
        # strips / largest margin first. A donor only counts if every
        # one of its sticks lands in the children, so the donor drops.
        donors = [b for b in real if b.id != parent.id]
        donors.sort(key=lambda b: (len(b.strips), -_margin(b, loss_per_strip)))
        candidate_pools = []
        # Removed pool alone, then removed + each donor alone, then
        # removed + all donors together. The chess case needs the
        # last one (CTH lives on BC2A); the first two are the
        # no-donor / single-donor fallbacks.
        candidate_pools.append((removed_sticks, []))
        for donor in donors:
            candidate_pools.append((removed_sticks + _expand_sticks(donor), [donor]))
        if len(donors) > 1:
            all_sticks = removed_sticks[:]
            for donor in donors:
                all_sticks.extend(_expand_sticks(donor))
            candidate_pools.append((all_sticks, donors))
        best_trial = None
        best_score = original_score
        for pool, pool_donors in candidate_pools:
            groups: Dict[int, List[Dict[str, Any]]] = {}
            for stick in pool:
                groups.setdefault(stick["length"], []).append(stick)
            if len(groups) != 2:
                continue
            # Children in trigger order: the bad strip's length group
            # first (that is the crosscut at its utilization edge),
            # then the other group.
            bad_len = _strip_total(strips[trigger], miter_kerf)
            ordered_lengths = sorted(
                groups, key=lambda ln: (0 if ln == bad_len else 1, ln))
            children = []
            ok = True
            for idx, ln in enumerate(ordered_lengths):
                sticks = groups[ln]
                child_strips = [{"width": s["width"], "cuts": [s["length"]]}
                                for s in sticks]
                used_w = sum(s["width"] for s in child_strips)
                if used_w + len(child_strips) * loss_per_strip > slab_w:
                    ok = False
                    break
                cid = f"{parent.id}{idx + 1}"
                if any(b.id == cid for b in blanks):
                    ok = False
                    break
                child = _Blank(cid, parent.species, slab_w, ln,
                               source_remainder=parent.id)
                child.strips = child_strips
                children.append(child)
            if not ok:
                continue
            total_child_len = sum(c.length for c in children) + \
                max(len(children) - 1, 0) * miter_kerf
            if total_child_len > plen:
                continue
            trial = copy.deepcopy(blanks)
            t_parent = next(b for b in trial if b.id == parent.id)
            # Remove exactly the removed strips (by width+cuts match).
            for strip in removed:
                match = next(
                    (s for s in t_parent.strips
                     if s["width"] == strip["width"]
                     and s["cuts"] == strip["cuts"]), None)
                if match is not None:
                    t_parent.strips.remove(match)
            donor_ids = {d.id for d in pool_donors}
            trial = [b for b in trial if b.id not in donor_ids]
            # Insert children directly after the parent, in order.
            pos = next(i for i, b in enumerate(trial) if b.id == parent.id)
            for offset, child in enumerate(children):
                trial.insert(pos + 1 + offset, copy.deepcopy(child))
            score = _child_split_score(trial, loss_per_strip, miter_kerf)
            if score < best_score:
                best_score = score
                best_trial = trial
        if best_trial is not None:
            return best_trial
    return None


def _best_fit_board(blanks, strip, loss_per_strip, miter_kerf,
                    exclude_ids=()):
    """Real board with the smallest margin-after still >= 0, or None."""
    best = None
    best_margin = None
    for blank in blanks:
        if blank.buy_species is not None or blank.id in exclude_ids:
            continue
        if not _can_place(blank, strip, loss_per_strip, miter_kerf):
            continue
        margin = blank.margin_after(strip["width"], loss_per_strip)
        if best_margin is None or margin < best_margin:
            best, best_margin = blank, margin
    return best


def _try_direct_ghost(blanks, loss_per_strip, miter_kerf):
    """Move one ghost strip onto a real board. Returns new blanks or None."""
    import copy
    trial = copy.deepcopy(blanks)
    for ghost in trial:
        if ghost.buy_species is None:
            continue
        for strip in list(ghost.strips):
            target = _best_fit_board(trial, strip, loss_per_strip, miter_kerf)
            if target is None:
                continue
            ghost.strips.remove(strip)
            target.strips.append(strip)
            if _is_better(trial, blanks, loss_per_strip):
                return trial
            # This ghost strip did not improve things on its own; undo
            # this one move and keep looking at other ghost strips.
            target.strips.remove(strip)
            ghost.strips.append(strip)
    return None


def _try_ejection(blanks, loss_per_strip, miter_kerf):
    """Make room for a ghost strip by removing 1-2 strips from a real
    board and placing them elsewhere. Returns new blanks or None."""
    import copy
    from itertools import combinations
    trial_base = copy.deepcopy(blanks)
    for ghost in trial_base:
        if ghost.buy_species is None:
            continue
        for ghost_strip in list(ghost.strips):
            for board in trial_base:
                if board.buy_species is not None or board.id == ghost.id:
                    continue
                strips = board.strips
                for size in (1, 2):
                    for subset_idx in combinations(range(len(strips)), size):
                        subset = [strips[i] for i in subset_idx]
                        trial = copy.deepcopy(trial_base)
                        t_ghost = next(b for b in trial if b.id == ghost.id)
                        t_board = next(b for b in trial if b.id == board.id)
                        t_strip = next(s for s in t_ghost.strips
                                       if s["width"] == ghost_strip["width"]
                                       and s["cuts"] == ghost_strip["cuts"])
                        # Remove the subset, then place the ghost strip.
                        for s in subset:
                            t_board.strips.remove(
                                next(x for x in t_board.strips
                                     if x["width"] == s["width"]
                                     and x["cuts"] == s["cuts"]))
                        if not _can_place(t_board, t_strip,
                                          loss_per_strip, miter_kerf):
                            continue
                        t_ghost.strips.remove(t_strip)
                        t_board.strips.append(t_strip)
                        # Place every removed strip elsewhere, best fit.
                        placed = True
                        for s in subset:
                            target = None
                            best_margin = None
                            for cand in trial:
                                if cand.id == t_board.id:
                                    continue
                                if not _can_place(cand, s,
                                                  loss_per_strip, miter_kerf):
                                    continue
                                margin = cand.margin_after(
                                    s["width"], loss_per_strip)
                                if best_margin is None or margin < best_margin:
                                    target, best_margin = cand, margin
                            if target is None:
                                placed = False
                                break
                            target.strips.append(s)
                        if placed and _is_better(trial, blanks, loss_per_strip):
                            return trial
    return None


def _swap_candidates(board_a, board_b, loss_per_strip, miter_kerf):
    """All (a_subset, b_subset) swaps of size (1,1), (1,2) or (2,1)
    that leave both boards fitting, as (a_strips, b_strips) lists."""
    from itertools import combinations
    out = []
    a_strips, b_strips = board_a.strips, board_b.strips
    for a_size, b_size in ((1, 1), (1, 2), (2, 1)):
        for a_idx in combinations(range(len(a_strips)), a_size):
            for b_idx in combinations(range(len(b_strips)), b_size):
                a_sub = [a_strips[i] for i in a_idx]
                b_sub = [b_strips[i] for i in b_idx]
                new_a = [s for i, s in enumerate(a_strips) if i not in a_idx] + b_sub
                new_b = [s for i, s in enumerate(b_strips) if i not in b_idx] + a_sub
                # Margin and length checks on both boards.
                def _ok(strips_list, width, length):
                    used = sum(s["width"] for s in strips_list)
                    if width - used - len(strips_list) * loss_per_strip < 0:
                        return False
                    return all(
                        sum(s["cuts"]) + max(len(s["cuts"]) - 1, 0) * miter_kerf <= length
                        for s in strips_list)
                if _ok(new_a, board_a.width, board_a.length) and \
                        _ok(new_b, board_b.width, board_b.length):
                    out.append((a_sub, b_sub, new_a, new_b))
    return out


def _try_swap_chain(blanks, loss_per_strip, miter_kerf):
    """Repeatedly swap strips to raise the margin on one target
    real board, until a ghost strip fits on it. Only the whole
    chain is committed, and only if it is strictly better.
    Returns new blanks or None.

    The target board's margin is the thing that has to grow: in
    the cherry case the receiving board's margin grows 6 -> 9 ->
    12 -> 15 sixteenths across three 1-big-for-2-small swaps,
    while the other board's margin shrinks, so a largest-margin
    criterion would stop at the first swap (the largest margin
    stays at 9). Targeting one board at a time is what lets the
    chain walk to the fit."""
    import copy
    ghost_strips = [s for b in blanks if b.buy_species is not None
                    for s in b.strips]
    if not ghost_strips:
        return None
    need = max(s["width"] + loss_per_strip for s in ghost_strips)
    real = [b for b in blanks if b.buy_species is None]
    # Try target boards in order of smallest deficit first.
    targets = sorted(real, key=lambda b: need - _margin(b, loss_per_strip))
    for target_id in [b.id for b in targets]:
        trial = copy.deepcopy(blanks)
        t_real = [b for b in trial if b.buy_species is None]
        target = next(b for b in t_real if b.id == target_id)
        for _step in range(10):
            direct = _try_direct_ghost(trial, loss_per_strip, miter_kerf)
            if direct is not None and _is_better(direct, blanks, loss_per_strip):
                return direct
            current = _margin(target, loss_per_strip)
            best_swap = None
            best_target_margin = current
            for other in t_real:
                if other.id == target.id:
                    continue
                for a_sub, b_sub, new_a, new_b in _swap_candidates(
                        target, other, loss_per_strip, miter_kerf):
                    saved_t, saved_o = target.strips, other.strips
                    target.strips, other.strips = new_a, new_b
                    new_margin = _margin(target, loss_per_strip)
                    target.strips, other.strips = saved_t, saved_o
                    if new_margin > best_target_margin:
                        best_target_margin = new_margin
                        best_swap = (other, new_a, new_b)
            if best_swap is None:
                break
            other, new_a, new_b = best_swap
            target.strips, other.strips = new_a, new_b
        direct = _try_direct_ghost(trial, loss_per_strip, miter_kerf)
        if direct is not None and _is_better(direct, blanks, loss_per_strip):
            return direct
    return None


def _improve_species(blanks, loss_per_strip, miter_kerf):
    """Second/third/... passes for one species. Only strictly
    better packings are ever kept, so this cannot make the greedy
    result worse."""
    current = blanks
    for _pass in range(50):
        improved = None
        for attempt in (_try_direct_ghost, _try_ejection, _try_swap_chain,
                        _try_child_split):
            improved = attempt(current, loss_per_strip, miter_kerf)
            if improved is not None:
                break
        if improved is None:
            break
        current = improved
    return current


def solve(project: Dict[str, Any], tool_limits: Dict[str, Any]) -> Dict[str, Any]:
    lim = _lim(tool_limits)
    saw_kerf = measure_to_sixteenths(lim["sawKerf"])
    plane_loss = measure_to_sixteenths(lim["minPlaneLoss"])
    loss_per_strip = saw_kerf + plane_loss
    miter_kerf = measure_to_sixteenths(lim["miterKerf"])
    max_cut = measure_to_sixteenths(lim["maxCutLength"]) if lim.get("maxCutLength") else None

    # --- demand -> strips -------------------------------------------------
    # One strip object per group strip: {species, width, cuts}
    strips: List[Dict[str, Any]] = []
    for d in component_demand(project, tool_limits):
        nominal_blank = max_cut if max_cut else max(
            measure_to_sixteenths(b["length"]) for b in project["boards"]
        )
        per_strip = (nominal_blank + miter_kerf) // (d.length + miter_kerf)
        if per_strip < 1:
            raise ValueError(
                f"component {d.id} stick length {d.length} does not fit "
                f"in a {nominal_blank}-sixteenth blank"
            )
        remaining = d.count
        while remaining > 0:
            n = min(per_strip, remaining)
            strips.append({
                "species": d.species, "width": d.width,
                "cuts": [d.length] * n,
            })
            remaining -= n

    # Largest width first; deterministic tie-breaks.
    strips.sort(key=lambda s: (-s["width"], s["species"], -len(s["cuts"])))

    inv_by_species: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for b in project["boards"]:
        inv_by_species[b["species"]].append(b)
    max_width_by_species = {
        sp: max(measure_to_sixteenths(b["width"]) for b in boards)
        for sp, boards in inv_by_species.items()
    }

    blanks: List[_Blank] = []
    # Per inventory board: blanks opened, and length already consumed
    # (sum of blank lengths + one miter kerf between consecutive blanks).
    consumed: Dict[str, int] = defaultdict(int)
    blank_count: Dict[str, int] = defaultdict(int)
    ghost_count: Dict[str, int] = defaultdict(int)

    def _new_blank_for(source_board: Dict[str, Any], strip: Dict[str, Any]) -> Optional[_Blank]:
        sid = source_board["id"]
        raw_len = measure_to_sixteenths(source_board["length"])
        used_len = consumed[sid]
        kerf = miter_kerf if blank_count[sid] > 0 else 0
        remaining = raw_len - used_len - kerf
        if remaining < sum(strip["cuts"]) + max(len(strip["cuts"]) - 1, 0) * miter_kerf:
            return None
        length = min(max_cut, remaining) if max_cut else remaining
        if length < sum(strip["cuts"]) + max(len(strip["cuts"]) - 1, 0) * miter_kerf:
            return None
        letter = chr(ord("A") + blank_count[sid])
        blank = _Blank(
            bid=f"{sid}{letter}", species=source_board["species"],
            width=measure_to_sixteenths(source_board["width"]),
            length=length, source=sid,
        )
        blank_count[sid] += 1
        consumed[sid] = used_len + kerf + length
        return blank

    def _new_ghost(strip: Dict[str, Any]) -> _Blank:
        sp = strip["species"]
        ghost_count[sp] += 1
        initial = sp[0].upper()
        suffix = "" if ghost_count[sp] == 1 else str(ghost_count[sp])
        length = max_cut if max_cut else max(
            measure_to_sixteenths(b["length"]) for b in project["boards"]
        )
        return _Blank(
            bid=f"GH-{initial}{suffix}", species=sp,
            width=max_width_by_species.get(sp, length),
            length=length, buy_species=sp,
        )

    for strip in strips:
        # Best fit among existing blanks of this species.
        best: Optional[_Blank] = None
        best_margin: Optional[int] = None
        for blank in blanks:
            if blank.species != strip["species"]:
                continue
            if not blank.strip_fits_length(strip["cuts"], miter_kerf):
                continue
            margin = blank.margin_after(strip["width"], loss_per_strip)
            if margin >= 0 and (best_margin is None or margin < best_margin):
                best, best_margin = blank, margin
        if best is not None:
            best.strips.append({"width": strip["width"], "cuts": strip["cuts"]})
            continue

        # Open a new blank: already-started sources first, then unused.
        sources = inv_by_species.get(strip["species"], [])
        ordered = sorted(sources, key=lambda b: (blank_count[b["id"]] == 0, b["id"]))
        placed = False
        for src in ordered:
            blank = _new_blank_for(src, strip)
            if blank is None:
                continue
            # Width must fit on a fresh blank too.
            if blank.margin_after(strip["width"], loss_per_strip) < 0:
                # Undo the length consumption for this unused blank.
                blank_count[src["id"]] -= 1
                consumed[src["id"]] -= (miter_kerf if blank_count[src["id"]] > 0 else 0) + blank.length
                continue
            blank.strips.append({"width": strip["width"], "cuts": strip["cuts"]})
            blanks.append(blank)
            placed = True
            break
        if placed:
            continue

        # Ghost board: same best-fit rule among existing ghosts.
        best = None
        best_margin = None
        for blank in blanks:
            if blank.buy_species is None or blank.species != strip["species"]:
                continue
            if not blank.strip_fits_length(strip["cuts"], miter_kerf):
                continue
            margin = blank.margin_after(strip["width"], loss_per_strip)
            if margin >= 0 and (best_margin is None or margin < best_margin):
                best, best_margin = blank, margin
        if best is not None:
            best.strips.append({"width": strip["width"], "cuts": strip["cuts"]})
            continue
        ghost = _new_ghost(strip)
        ghost.strips.append({"width": strip["width"], "cuts": strip["cuts"]})
        blanks.append(ghost)

    # --- second/third/... passes: always run, only strictly better -----
    # Group by species, improve each species independently, then put
    # the boards back in their original order. Boards left empty by
    # improvement are dropped at emit time.
    species_order = []
    for blank in blanks:
        if blank.species not in species_order:
            species_order.append(blank.species)
    improved_by_species = {}
    for species in species_order:
        species_blanks = [b for b in blanks if b.species == species]
        improved_by_species[species] = _improve_species(
            species_blanks, loss_per_strip, miter_kerf)
    # Rebuild per species, in improved order. Boards left empty by
    # improvement are dropped. New boards created by improvement
    # (sourceRemainder children) must survive this step: they have
    # ids that were not in the original blanks list, so rebuilding
    # from the original list alone would drop them.
    blanks = []
    for species in species_order:
        blanks.extend(b for b in improved_by_species[species] if b.strips)

    # --- trim each blank to its longest strip ----------------------------
    # Crosscut before rip: the blank is only as long as the longest
    # strip it carries, so unused source length remains a full-width
    # leftover instead of fragmenting into a tail on every strip.
    for blank in blanks:
        if blank.strips:
            blank.length = max(
                sum(s["cuts"]) + max(len(s["cuts"]) - 1, 0) * miter_kerf
                for s in blank.strips
            )

    # --- emit YAML in the existing cut-specs style ------------------------
    # Cut list order is always alphabetical by species, then board id,
    # so the table and the Board Rip Diagram read the same way in
    # every plan, generated or hand-crafted.
    blanks = sorted(blanks, key=lambda b: (b.species, b.id))
    out_boards = []
    for blank in blanks:
        entry: Dict[str, Any] = {"id": blank.id}
        if blank.source_remainder is not None:
            entry["sourceRemainder"] = blank.source_remainder
        elif blank.source:
            entry["source"] = blank.source
        else:
            entry["buySpecies"] = blank.buy_species
        entry["length"] = blank.length
        # Strips within a board, widest first (stable, so equal widths
        # keep their original order). This matches how the hand-crafted
        # spec lists strips, so a generated plan and a hand-crafted one
        # with the same counts draw the same diagram.
        entry["strips"] = sorted(
            blank.strips, key=lambda s: -s["width"])
        out_boards.append(entry)
    return {"boards": out_boards}


def _dump(cut_spec: Dict[str, Any]) -> str:
    lines = [
        "# yaml-language-server: $schema=../../../schema.json",
        "# Generated by the greedy solver (boardsolver.solver).",
        "# Workable, not optimised: tweak by hand afterwards if you like.",
        "boards:",
    ]
    for board in cut_spec["boards"]:
        lines.append(f"- id: {board['id']}")
        if "sourceRemainder" in board:
            lines.append(f"  sourceRemainder: {board['sourceRemainder']}")
        elif "source" in board:
            lines.append(f"  source: {board['source']}")
        else:
            lines.append(f"  buySpecies: {board['buySpecies']}")
        lines.append(f"  length: {_fmt(board['length'])}")
        lines.append("  strips:")
        for strip in board["strips"]:
            lines.append(f"  - width: {_fmt(strip['width'])}")
            lines.append("    cuts:")
            for cut in strip["cuts"]:
                lines.append(f"    - {_fmt(cut)}")
    return "\n".join(lines) + "\n"


def _main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="board-solver greedy solver (Round 3)")
    ap.add_argument("--project", required=True)
    ap.add_argument("--tool-limits", required=True)
    ap.add_argument("--out", required=True, help="cut-specs.yaml to write")
    args = ap.parse_args(argv)
    with open(args.project) as f:
        project = yaml.safe_load(f)
    with open(args.tool_limits) as f:
        tool_limits = yaml.safe_load(f)
    cut_spec = solve(project, tool_limits)
    with open(args.out, "w") as f:
        f.write(_dump(cut_spec))
    n_boards = len(cut_spec["boards"])
    n_ghosts = sum(1 for b in cut_spec["boards"] if "buySpecies" in b)
    n_strips = sum(len(b["strips"]) for b in cut_spec["boards"])
    print(f"wrote {args.out}: {n_boards} boards ({n_ghosts} ghost), {n_strips} strips")
    return 0


if __name__ == "__main__":
    raise SystemExit(_main())
