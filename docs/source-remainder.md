# sourceRemainder and child boards

Read this before using `sourceRemainder` in a cut-spec, or before
"fixing" a plan by moving strips around. This models a real shop operation,
not a bookkeeping trick, and most of the failures below come from treating
it as bookkeeping.

## The shop operation, in order

1. **Rip a board.** A cut-spec board is ripped into strips across its
   width. Loss per strip is `sawKerf + minPlaneLoss` (1/8″ + 1/16″ = 3/16″).
2. **A margin slab is left over.** If the strips do not use the full
   source width, the leftover is a slab, not waste:
   ```
   slab width = source width − sum(strip widths) − loss
   slab length = parent board length
   ```
   Its dimensions are fully predictable once the parent's strips are
   fixed. That is the only reason a child board can be planned at all.
3. **Crosscut the slab.** A later cut-spec board with
   `sourceRemainder: <parent id>` is one crosscut piece off that slab.
   Children of the same parent are taken **in cut-spec document order**,
   each consuming its length plus one `miterKerf` (1/8″) off what remains
   of the slab. They are drawn as ghost rectangles in the parent's margin
   band, in that order, followed by any unclaimed slab tail.
4. **Rip the child.** A child board is a new stripping source in its own
   right: it is ripped into its own strips, with its own loss, and it has
   its own margin slab, which can itself feed a nested child
   (`sourceRemainder: <child id>`).

Child boards are **not** raw-stock crosscuts. They do not appear in
`crosscut_blanks` (that table covers only boards with a `source` into
raw inventory). They appear only as ghost rectangles in the parent's
margin band and as their own boards in the rip diagram and cut list.

## Why child boards exist at all

Strips in a single board all share that board's length. If one strip
carries a 12⅞″ piece and another strip on the same board carries a
45″ run of pieces, the short strip wastes a ~32″ offcut tail. Splitting
the margin slab into **length-matched segments**, each ripped
differently, removes that waste: each segment's board length equals
its pieces' length, so every strip fills its board exactly.

That is why **one child board is pointless**. A single child carrying
all the remaining pieces is just the parent's strips relabelled onto
another board — same widths, same length problem, no new capability.
The benefit starts at **two children** with different lengths and
different rip layouts, one segment per piece-length group.

## Rules — check all of these before calling a plan valid

- **Two children minimum for any benefit.** One child = relabelling.
  Two children, length-matched to their pieces, = the point of the
  feature.
- **Child lengths must fit the slab they come from.**
  For children of one parent, in document order:
  ```
  sum(child lengths) + (number of children − 1) × miterKerf ≤ parent length
  ```
  A nested child must also fit its immediate parent child:
  its length ≤ that child's board length. A child longer than its
  source is physically impossible, even if the planner accepts it.
- **The planner does NOT warn on sourceRemainder length overflow.**
  `warnings()` checks over-rip, rip-too-long, crosscut overflow of raw
  boards, and component shortfall — it does not check a child's length
  against its parent's remaining slab length. When it overflows, the
  parent's ghost rectangle is silently truncated to the remaining slab
  while the child's own diagram still draws its full (impossible)
  length. Check the lengths by hand; do not trust "no warnings" here.
- **Do not increase a blank's length to make a layout fit.**
  A blank's length in the cut-spec is the length you will actually
  crosscut. If a layout needs a longer blank than the blank you have,
  the layout is invalid — raising the blank is reward hacking, not a
  fix. Raw stock length is an upper bound, not a licence: a trimmed
  blank (solver trim = longest strip total, including inter-cut kerfs)
  stays at that length unless you are explicitly re-planning the
  raw-stock crosscut, with the raw leftover to prove it.
- **A slab tail left unused is fine.** Children do not have to consume
  the whole slab. An unclaimed tail is drawn plain in the parent's
  margin band and is just leftover material.
- **Strip-map titles show the blank's length, not the source's length.**
  A source board's title is
  `id (blank length × source width × thickness)`.
  A sourceRemainder board's title is
  `id (board length × slab width × thickness)`.
  Two blanks from the same inventory board therefore have different
  titles even though they share a source — if two titles look identical
  while the boards are different lengths, the title code is wrong, not
  the boards. (Fixed in `draw.py` `_start_dims`: it used to use the
  inventory board's full length for source boards.)

## Worked example — chess-v1 cherry, actual inventory

Demand left after the parent, all cherry: CT ×4 (2¼″ × 12⅞″),
CB ×2 (1⅛″ × 16⅛″), CTH ×1 (1⅛″ × 12⅞″).

Parent:
- **BC1A**, source BC1, length **38⅞″** (the trimmed solver blank —
  not raised to 48″), strips: CT 2¼″, cuts 12⅞″ ×3.
  Used 2¼″, loss 3/16″, margin slab **4¹³⁄₁₆″ wide × 38⅞″ long**.

Two children, both `sourceRemainder: BC1A`, in document order:
- **BC1A1, 16⅛″:** 2 thinner, longer strips — CB 1⅛″ ×2, each cut
  16⅛″. Used 2¼″, loss 3/8″, margin 2³⁄₁₆″.
- **BC1A2, 12⅞″:** 1 larger strip (CT 2¼″, cut 12⅞″) + 1 thinner,
  shorter strip (CTH 1⅛″, cut 12⅞″). Used 3⅜″, loss 3/8″,
  margin 1¹⁄₁₆″.

Length check: 16⅛″ + ⅛″ kerf + 12⅞″ = 29⅛″ ≤ 38⅞″, leaving a
9¾″ slab tail. Every strip fills its board exactly — no offcut tails.
Result: CT 4/4, CB 2/2, CTH 1/1, 0 shortfall, no warnings, finished
board byte-identical to the solver anchor. BC2 stays an untouched spare.

## How the solver finds this itself (hill climber)

`boardsolver.solver._try_child_split`, run as the fourth improvement
attempt per species, after the ghost passes (which do nothing when
there are no ghost strips — the chess case). It formalizes the
intuitive scan above, so no human has to point at a gap in a diagram:

1. **Scan top-down, per blank.** Utilization per strip =
   (sum of cuts + inter-cut kerfs) / trimmed blank length.
   Trigger on the first strip with utilization < 50%, a preceding
   strip at ≥ 80%, and a later strip at least 30 points more utilized
   and narrower than the trigger strip. A bad strip at the end of a
   board, or a uniformly underutilized board, does not trigger.
2. **Split point and crosscut point.** Keep strips before the trigger
   strip on the parent; the margin slab grows by the removed strips'
   widths + loss. Crosscut that slab at the trigger strip's
   utilization edge — that length is determined, not chosen.
3. **Group the remaining pieces by length into exactly two children.**
   Remaining pieces = removed strips' sticks, plus sticks from other
   blanks of the same species, but only if *all* of a donor blank's
   sticks land in the children, so the donor drops entirely. One
   length group is rejected (pointless relabelling); three or more
   are rejected for now. Each group becomes one child, one strip per
   stick, child length = group length, so no child strip has a tail.
4. **Hard constraints, then net score.** Child widths + loss must fit
   the slab width; sum of child lengths + kerfs must fit the parent's
   trimmed length (never increase a blank's length; never let a child
   exceed its slab). Then accept only if the area-based score
   `(ghost volume, raw blank count, waste area + loss area)` is
   strictly lower. Waste is terminal waste only (strip tails, child
   margins, unclaimed slab tails — a parent slab feeding children is
   not itself waste). Loss is per-strip loss × board length.
5. **Smaller blanks are rewarded by the area score.** Waste and loss
   scale with board length, so shortening a blank, or dropping one,
   reduces them — and the length saved stays on the raw board as a
   full-width leftover (see `crosscut_blanks`), usable for a future
   build, whereas a strip tail of the same length is narrow-width
   waste. The old ghost-pass score, `(ghost volume, -margin width)`,
   does not reward smaller blanks at all, because margin width is
   length-independent. That is why the child split has its own score.

Worked numbers for chess cherry: before, ghost 0, raw blanks 2,
waste + loss ≈ 204 (sixteenths-squared units, waste ≈ 180 + loss
≈ 24); after, ghost 0, raw blanks 1, waste + loss ≈ 114
(waste ≈ 96 + loss ≈ 18), despite one extra strip lane, because
the new lanes run on shorter boards. The extra lane costs
~3.0 sq in of loss and the inter-child kerf ~0.6 sq in, against
~84 sq in of waste eliminated and a whole raw blank dropped.

The solver now produces this solution directly: running the solver
on chess-v1 actual yields BC1A (38⅞″, CT ×3) plus BC1A1 (12⅞″,
CT + CTH) and BC1A2 (16⅛″, CB ×2), BC2 untouched, all components
fulfilled, finished board byte-identical to the hand anchor.
(The child order follows the trigger: the bad strip's length group
first, so solver BC1A1 is the 12⅞″ group, where the hand version
listed CB first — same pieces, different child numbering.)

## Counterexamples — do not repeat these

- **Single-blank lift/shift (reward hack).** Moving BC1A2's strips
  onto BC1A as extra strips "worked" only because BC1A's length was
  quietly raised from 38⅞″ to 48″. The narrow strip alone needs
  45⅜″, which cannot fit a 38⅞″ blank. Same label (source length
  48⅛″) on both blanks hid the change. This is exactly the
  blank-increase rule above.
- **Three children, one nested too long.** BC1A1 (12⅞″, CT),
  BC1A2 (16⅛″, CB ×2), and BC1A3 (16⅛″, CTH) with
  `sourceRemainder: BC1A1` was accepted by the planner (all components
  fulfilled, no warnings) even though BC1A3 at 16⅛″ is longer than
  its source BC1A1 at 12⅞″. The giveaway was the diagram: BC1A1's
  ghost for BC1A3 was truncated to 12⅞″ while BC1A3's own board drew
  16⅛″. Collapsing the two 12⅞″ pieces (CT + CTH) into one child is
  what makes the two-child version above work.
- **Merged-image comparison trap.** Two strip-map PNGs have different
  canvas widths (their longest board length × 12 px/in + padding).
  Resizing both to the same display width changes their effective
  scale differently, so equal-length pieces render at different pixel
  widths and do not line up. Compare strip maps at native pixel size,
  pasted unscaled and left-aligned, or compare the cut-list numbers,
  not a resized composite.
