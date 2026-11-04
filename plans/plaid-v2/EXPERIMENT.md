# Plaid v2 experiment — 2026-11-03, Scott

Experiment only. NOT adopted. plaid-v1 is untouched (its PDF is still
2026-11-03 18:46; the v2 PDF below is 19:30).

## What was tried

- Cherry panel length: (48 1/16 in - 3 x 1/8 in kerf) / 3 = 15 43/48 in,
  rounded down to the nearest 1/16 in = **15 7/8 in**.
- Cherry panel count: 2 -> **3 per type** (+50% in practice; 2 x 1.33 = 2.66,
  so 3 is the closest integer count).
- Panels affected: SL, SR, ML, MR only. H has no cherry, unchanged
  (1 panel, 17 3/4 in, L:5 + R:5).
- How it was built: design `specs/designs/plaid-v2.yaml` is a copy of
  plaid-v1 (same finished pattern). The solver's derived panelSpecs
  would still give 2 panels x 11 slices, so the v2 run used manual
  panelSpecs: cherry panels count 3, region 14 3/8 in, panel length
  15 7/8 in; H as in v1. Cut-spec: `specs/inventories/actual/cut-specs/plaid-v2.solver.yaml`.
  Plan: `plans/plaid-v2/actual/solver/`.

## Caveat: 15 7/8 in is not a clean panel length

15 7/8 in - 1 1/2 in snipe = 14 3/8 in region.
14 3/8 in / 1 5/8 in pitch = 8 full slices + 1 3/8 in remainder per panel.
So each cherry panel yields 8 slices, not 8.86, and wastes 1 3/8 in of
panel length. The clean panel lengths nearest to 15 7/8 in are 14 1/2 in
(8 slices, exact) and 16 1/8 in (9 slices, exact) — 16 1/8 in cannot fit
3 per strip (3 x 16 1/8 in + kerfs = 48 5/8 in, over the raw board).

## Result

- Cherry blanks: BC1A and BC2A both **47 7/8 in** (3 x 15 7/8 in + 2 kerfs).
  Leftover per cherry board: **3/16 in**, down from ~9 3/16 in in v1.
  That part of the theory works: 3 components per strip, almost no board offcut.
- Ghost: **still GH-C, 1 strip** (3 x 15 7/8 in, 3/4 in wide). Ghost is
  width-driven, not length-driven: BC1A holds 3 x 1 1/2 in + 2 x 3/4 in,
  BC2A holds 1 x 1 1/2 in + 5 x 3/4 in, total 11 cherry strips, need 12.
  Shortening panels does not fix it. BC2A margin is still 1/8 in
  (small-margin warning, same as v1).
- Slices: SL/SR/ML/MR each **24 supplied vs 20 demanded (+4)**, vs +2 in v1.
  Panel count per type is odd (3), but slice count per type is even
  (3 x 8 = 24), and L/R counts match (SL = SR = 24, ML = MR = 24).
  No combined 2-profile panel type is needed for this variant.
- Panels: 12 cherry panels + 1 H = 13, vs 9 in v1. More glue-ups.
- Other boards use up their leftovers too: BM1 leftover 2 3/16 in,
  BW1/BW2 leftover 6 7/16 in each (vs ~22 in in v1). Those leftovers were
  usable full-width pieces, not waste — v2 trades them for panel
  remainder waste (1 3/8 in x 12 panels) and extra spare slices.
- No child split in v2 (all strips are 3-piece, 100% utilized, so the
  hill climber does not trigger). Board count drops from 9 to 7.
- Finished board is unchanged (same pattern, same slice grid).
- Tests after v2: 150 passed.

## Update — 2026-11-03 19:46: 12 panels, S pair -> 2-profile S panel

Scott: reduce total panels by 1, convert one other panel to a 2-profile
version like H.

What was actually built (solver-clean version): the whole SL/SR pair was
replaced by a single 2-profile panel type **S**, like H. Grid sliceIds
changed SL/SR -> S-L/S-R; S components = SL sequence, last Md
maxProfile:1, so S-R drops that Md, exactly like H-R. Mixing single
SL/SR panels with one combined S panel does NOT work in the solver's
sliceId system (single panels produce "SL"/"SR", combined produces
"S-L"/"S-R", and slice fulfillment would show a phantom shortfall even
though the sequences are identical), so the full pair replacement is
the version that runs clean.

Manual panelSpecs for this run: S count 5, regions 7 3/16 in + 7 3/16 in
(panel length 15 7/8 in, 4 + 4 slices); ML count 3, MR count 3, each
15 7/8 in, 8 slices; H count 1, unchanged.

- Total panels: **12** (S 5 + ML 3 + MR 3 + H 1), down from 13.
- Slices: **S-L 20/20, S-R 20/20 exactly**, ML 24/20, MR 24/20, H-L/H-R
  10/8. L/R counts are even and balanced for every pair.
- Ghost: **GONE**. Cherry strips needed drop from 12 to 11 (C2 sticks
  24 -> 20, C1 sticks 12, total 11 strips), and the solver packs them as
  BC1A: 3 x 1 1/2 in + 2 x 3/4 in, BC2A: 1 x 1 1/2 in + 5 x 3/4 in.
  Board count drops from 7 to 6 (no GH-C).
- New warning: **no_spare_slices for S-L/S-R** — supply exactly meets
  demand, so one bad S slice is a shortfall, unlike the +4 spare in
  the previous v2.
- Cherry blanks/leftovers unchanged: BC1A/BC2A 47 7/8 in, leftover
  3/16 in each. BC2A still 1/8 in margin (small-margin warning).
- Finished board: **byte-identical to v1** (md5 214106e6059ae18d11bf25a76a8431b1).
  Pattern is unchanged; only slice labels changed.
- Quirk, same as H: component demand counts the maxProfile Md stick
  at full panel length, so Md sticks go 20 -> 21 total (19 at 15 7/8 in
  + 2 at 17 3/4 in for H), even though one panel was removed.
- v2 PDF now 8 pages (was 9). plaid-v1 PDF still 2026-11-03 18:46, untouched.
- Tests: 150 passed.

## Update — 2026-11-03 20:03: hand maple, tweaked v2

Scott: maple rip diagram was messy, gaps too obvious. Design a better
hand cut spec, move components from second blank to first blank with a
clever cross cut after rips.

Hand cut spec: `specs/inventories/actual/cut-specs/plaid-v2.hand.yaml`,
plan: `plans/plaid-v2/actual/hand/` (solver v2 plan untouched, 19:46).

Maple only changed; cherry/walnut boards are the solver versions.

- BM1A: 47 7/8 in, 7 strips, ALL 3 pieces, tail 0 in.
  M1 x3 strips (9 pieces), Me x2 strips (6), Md x2 strips (6).
  Width 6 1/2 in + loss 1 5/16 in = 7 13/16 in, margin 5/8 in.
- BM1B: 35 5/8 in, 12 strips, ALL 2 pieces, tail 1 7/8 in (mixed H
  strips) or 3 3/4 in (regular strips). No 32 in tails.
  M1 x1 strip (2 pieces, 1 demand + 1 spare), Me x3 strips (5 at
  15 7/8 in + 1 at 17 3/4 in H), Md x8 strips (14 at 15 7/8 in, 1 spare,
  + 2 at 17 3/4 in H). Width 5 3/4 in + loss 2 1/4 in = 8 in,
  margin 7/16 in.
- Swap that makes it work: the odd single M1 piece that made solver
  BM1A partial moves to BM1B as half of a 2-piece strip (with a spare
  partner); Me/Md full 3-piece strips that were on solver BM1B move to
  BM1A. BM1A pieces 16 -> 21, BM1B pieces 27 -> 24.
- Clever cross cut after rips, BM1B: every strip gets exactly one
  crosscut, at 15 7/8 in from the start. First piece is always
  15 7/8 in; second piece is 15 7/8 in, or 17 3/4 in for the H strips.
  No second crosscut per strip on BM1B.
- Validation (manual v2 panelSpecs, as in solver v2): no red warnings,
  no ghost, no shortfall, overcut 0, wasted 0. Warnings only the two
  pre-existing yellows/grays: BC2A 1/8 in margin (cherry, unchanged)
  and no spare S slices. Component supply: M1 11/10, Me 11/11 + 1/1 H,
  Md 20/19 + 2/2 H — spare pieces are 1 M1 + 1 Md, kept as spares.
- BM1 crosscut leftover grows to 14 7/16 in (47 7/8 + 35 5/8
  + kerf = 83 5/8 in, raw 98 1/16 in). That is one full-width piece,
  not per-strip gaps, and it is shorter than a component, so it cannot
  yield another 15 7/8 in piece in this plan. Correction 2026-11-03:
  this is not a tradeoff in material terms — the leftover is a usable
  full-width piece, versus narrow per-strip tails that are mostly scrap,
  and total margin + tail area drops, so the hand version is purely
  better, not a tradeoff.
- Hand PDF 9 pages. Tests: 150 passed.

## Update — 2026-11-03 21:43: planer gang warning

Scott: a strip wider than its thickness (13/16 in) must be ganged,
total gang thickness >= strip width; if the strip gang is too small,
crosscut first, then gang components; if that gang is still too small,
warn in the plan and above the gang in the checklist. A gang is all
strips/components of one finished width.

- Implemented in derive.gang_groups + warnings (code
  planer_gang_too_small, red), and in cutcheck.py Phase 3 gangs.
  Tests: tests/test_gang.py, synthetic only. Tests: 156 passed.
- Plaid-v2 hand: 3 in width needs 4 pieces at 13/16 in, only 1 strip
  (13/16 in) and 2 components (1 5/8 in) exist, so ERROR in plan
  (now warning 1, ahead of Small Margin and No Spare Slices) and
  above the 3 in gang in the checklist. This supersedes the earlier
  "no red warnings" line for the hand plan, which predated the gang
  rule; other warnings are unchanged.
- 1 1/2 in width requires a gang, 8 strips total 6 1/2 in, enough.
  3/4 in and 1/4 in widths do not require a gang (width < thickness).
- Checklist change: Phase 3 gangs are crosscut first when the strip
  gang is too small (3 in gang: 2 components at 17 3/4 in, off cut
  12 1/8 in, then plane as gang), and those crosscuts are not
  repeated in Phase 4. Phase 4 BW1A lists strips 2-4 only, with a
  note that strip 1 was already crosscut in Phase 3. Totals stay
  39 strips, 103 pieces. Complete plan PDF still 9 pages, checklist
  PDF still 4 pages.

## Update — 2026-11-03 21:57: plan crosscut leftover fixed to match checklist

Scott: either the plan or the checklist is wrong — fix the wrong one,
do not warn about the inconsistency.

The plan was wrong, the checklist was right. derive.crosscut_blanks
counted kerfs only between blanks, so its leftover was 1/8 in too
long and its crosscut diagram summed to raw length + 1 kerf. Fixed:
leftover = raw - blanks - (blanks-1) kerfs - final kerf, if a
leftover remains; exact fit stays 0, overflow stays negative.
Strip diagrams already used this model, so they were already right.

- Plan leftovers now match the checklist off cuts: BM1 14 5/16 in
  (was 14 7/16 in), BC1/BC2 1/16 in (was 3/16 in), BW1/BW2 6 5/16 in
  (was 6 7/16 in). No other plan section changed.
- Checklist off-cut note removed; checklist numbers unchanged.
  Complete plan PDF still 9 pages, checklist PDF still 4 pages.
- Tests: tests/test_crosscut_leftover.py, synthetic only. Tests:
  160 passed.
