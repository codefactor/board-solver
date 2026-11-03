# Plaid v1 — Cut Plan

*Two end-grain plaid cutting boards built from cherry, walnut, and brown maple.*

This is a generated plan: the finished design and the cut list that realizes it on the boards in hand. Where the cut list cannot be met from inventory it calls for **bought boards** — buy those and re-run before cutting. The sections follow the build order, from the first crosscut to the final slice-grid assembly.

## 1. Warnings

| # | Lvl | Type | Message |
| --- | --- | --- | --- |
| 1 | 🔴 | crosscut_overflow | Board BW1 is over-cut by 7⁵⁄₁₆″: its blanks demand more length than the raw board has. |
| 2 | 🔴 | crosscut_overflow | Board BW2 is over-cut by 13¹³⁄₁₆″: its blanks demand more length than the raw board has. |
| 3 | 🔴 | over_rip | Cut list for board BC1A over-rips by ¹⁄₁₆″: the strips are wider than the board. |
| 4 | 🔴 | over_rip | Cut list for board BW1A over-rips by ⅛″: the strips are wider than the board. |
| 5 | 🟡 | ghost_boards | 1 board(s) must be bought (not in inventory): GHC. |
| 6 | 🟡 | shortfall | The cut list under-supplies 741 component piece(s) across 9 demand row(s) — see the Components section. |
| 7 | 🟡 | small_margin | Board BC2A leaves only 0″ margin (< ¼″) — too tight; prone to under-supplying strips if the board runs narrow. |
| 8 | 🟡 | small_margin | Board GHC leaves only 0″ margin (< ¼″) — too tight; prone to under-supplying strips if the board runs narrow. |
| 9 | 🟡 | panel_components_short | The cut list cannot supply all components the speced panels need: Me (short 4), C2 (short 8), M1 (short 4), Md (short 9), W2 (short 8), C1 (short 4). |
| 10 | ⚪ | slice_oversupply | The panels produce far more slices than needed (> 5): H-L (+8), H-R (+8). The panels are likely too big — shorten them to use less material. |

## 2. Finished board pattern

2 finished boards. Final thickness 1¼″.

The finished plaid face.

![Finished plaid face](images/finished-board-cadaa3163bff.png)

## 3. Crosscut Blanks

The first operation: crosscut each raw inventory board along its length into the labeled board blanks that get ripped later (the Initial board rips section). Boards that start from another board's leftover margin are not raw-stock crosscuts — they appear as the labeled offcuts in the Board Rip Diagram.

| Raw board | Species | Raw length | Blanks (id = length) | Leftover |
| --- | --- | --- | --- | --- |
| BC1 | cherry | 48⅛″ | BC1A = 47¾″ | ⅜″ |
| BC2 | cherry | 48¹⁄₁₆″ | BC2A = 47¾″ | ⁵⁄₁₆″ |
| BW1 | walnut | 54⁵⁄₁₆″ | BW1A = 27½″; BW1B = 34″ | -7⁵⁄₁₆″ (overflow!) |
| BW2 | walnut | 54⁵⁄₁₆″ | BW2A = 34″; BW2B = 34″ | -13¹³⁄₁₆″ (overflow!) |
| BM1 | maple | 98¹⁄₁₆″ | BM1A = 34″; BM1B = 34″ | 29¹⁵⁄₁₆″ |
| BM2 | maple | 47¹⁵⁄₁₆″ | — (untouched spare) | — |

### Crosscut Diagram

Each bar is one raw board drawn to scale by length; segments are the blanks (labeled with id and length inside), reddish stripes are crosscut kerfs (sawdust), and the pale tail is leftover length. A red tail means the blanks overflow the raw board. An untouched spare is shown washed-out and uncut; a board used whole goes straight to the rip diagram.

![Crosscut Diagram — raw boards cut into length blanks](images/crosscut-blanks-512943d28810.png)

## 4. Panels overview

| Panel | Qty | Length | Slices | Height | Ripped | Sequence (outer → in) |
| --- | --- | --- | --- | --- | --- | --- |
| S | 2 | 37¼″ | 22 (L:11 + R:11) | ¾″ | — | Me · C2 · M1 · C2 · Md · C2 · M1 · C2 · Md |
| M | 2 | 37¼″ | 22 (L:11 + R:11) | ¾″ | — | Me · W2 · C1 · W2 · Md · W2 · C1 · W2 · Md |
| H | 1 | 27½″ | 16 (L:8 + R:8) | ¼″ | 2× (¼″) | Me · W1 · Md · W1 · Md |

### Panel End Grain Diagram

Each panel's end-grain cross-section (the glue-up of component stripes).

![Panel end-grain cross-sections](images/panels-2356d457e5b6.png)

### Panel Face Diagram

Each panel drawn to scale with its length running top-to-bottom. Components are vertical stripes aligned on the squared edge; profile regions stack down the length, so the silhouette steps narrower where trailing components drop out. Dashed lines are the slice crosscuts; the solid red band is total kerf loss, and the cross-hatched ends are the snipe tails (possible loss, depending on the planer).

![Panel faces to scale](images/panel-faces-743b16327ac8.png)

### Slice Fulfillment

**Demand** is every slice the grid places across all 2 finished board(s). **Supplied** is the slices the panels above produce — snipe lost, ripped panels multiplied by their strip count. **Supply Offset** = supplied − demand: negative is a shortfall, positive is extra (ideally non-negative everywhere).

| Slice | Demand | Supplied | Supply Offset |
| --- | --- | --- | --- |
| S-L | 10 × 2 = 20 | 22 | +2 |
| S-R | 10 × 2 = 20 | 22 | +2 |
| M-L | 10 × 2 = 20 | 22 | +2 |
| M-R | 10 × 2 = 20 | 22 | +2 |
| H-L | 4 × 2 = 8 | 8 × 2 = 16 | +8 |
| H-R | 4 × 2 = 8 | 8 × 2 = 16 | +8 |

_The slice counts supplied are calculated assuming the panels and their quantities are delivered perfectly according to the specs in this section. A panel type may have more than one instance; the ideal panels are always quantity 1._

### Ripped Slice Diagram

Slices from panels that are ripped (sliceStrips). Identical slices across panels are merged into one diagram, labeled with how many to cut. The horizontal axis is the slice length (end-grain face); dashed lines are the rip cuts; the red band is rip kerf + planing / margin loss.

![Ripped slice diagrams](images/ripped-slices-17e6d4bbd3c3.png)

## 5. Initial board rips (the cut list)

Each row is one physical board at the saw: rip the strips down its width, then crosscut each strip to the piece lengths. The **Board** column shows `id @ width` — the board's width when ripping begins. **Used** is the summed strip width, **Loss** is rip kerf + planer cleanup per strip, **Margin** is the leftover width (negative = the strips do not fit; large = the board is oversized for what it yields).

| Board | Origin | Species | Length | Rips (width × count) | Used | Loss | Margin |
| --- | --- | --- | --- | --- | --- | --- | --- |
| BC1A @ 7¼″ | BC1 | cherry | 47¾″ | 1½″ ×1 · ¾″ ×6 | 6″ | 1⁵⁄₁₆″ | -¹⁄₁₆″ |
| BC2A @ 6¹⁵⁄₁₆″ | BC2 | cherry | 47¾″ | 1½″ ×3 · ¾″ ×2 | 6″ | ¹⁵⁄₁₆″ | 0″ |
| BW1A @ 6¼″ | BW1 | walnut | 27½″ | 3″ ×2 | 6″ | ⅜″ | -⅛″ |
| BW1B @ 6¼″ | BW1 | walnut | 34″ | ¾″ ×4 | 3″ | ¾″ | 2½″ |
| BW2A @ 6¹⁄₁₆″ | BW2 | walnut | 34″ | ¾″ ×4 | 3″ | ¾″ | 2⁵⁄₁₆″ |
| BW2B @ 6¹⁄₁₆″ | BW2 | walnut | 34″ | ¾″ ×4 | 3″ | ¾″ | 2⁵⁄₁₆″ |
| BM1A @ 8⁷⁄₁₆″ | BM1 | maple | 34″ | 1½″ ×2 · ¾″ ×2 · ¼″ ×3 | 5¼″ | 1⁵⁄₁₆″ | 1⅞″ |
| BM1B @ 8⁷⁄₁₆″ | BM1 | maple | 34″ | 1½″ ×2 · ¾″ ×2 · ¼″ ×2 | 5″ | 1⅛″ | 2⁵⁄₁₆″ |
| GHC @ 7⅛″ | *None* | cherry | 34″ | 1½″ ×2 · ¾″ ×4 | 6″ | 1⅛″ | 0″ |

### Board Rip Diagram

Each labeled block below is one physical board. Horizontal bands are the strips ripped down the board's width; within a band, the colored cells are the crosscut pieces (with thin kerf gaps between them) and the lightened tail is the offcut. The pale band under the strips is the leftover margin; a gray title marks a board that must be bought.

![Board Rip Diagram — how the cut list lands on each board](images/strip-map-0bdef5eca8ff.png)

## 6. Components

**Demand** is what the finished pattern needs (counted from the slice grid; length is the panel the component belongs to). **Fulfilled** is how many the cut list supplies, matched longest-demand-first using exact-length pieces first, then longer pieces cut down (a piece shorter than the demand cannot be used). **Shortfall** is the unmet count. **Total Overcut** is the wasted length trimmed off — the sum of (piece length − demand length) across every longer piece that had to be cut down to fill this row (0 when exact-length pieces covered it).

| Component | Species | Width | Length | Demand | Fulfilled | Shortfall | Total Overcut |
| --- | --- | --- | --- | --- | --- | --- | --- |
| C1 | cherry | 1½″ | 37¼″ | 80 | 0 | 80 | 0 |
| C2 | cherry | ¾″ | 37¼″ | 160 | 0 | 160 | 0 |
| M1 | maple | 1½″ | 37¼″ | 80 | 0 | 80 | 0 |
| Md | maple | ¼″ | 37¼″ | 120 | 0 | 120 | 0 |
| Md | maple | ¼″ | 27½″ | 24 | 5 | 19 | 26″ |
| Me | maple | ¾″ | 37¼″ | 80 | 0 | 80 | 0 |
| Me | maple | ¾″ | 27½″ | 16 | 4 | 12 | 19½″ |
| W1 | walnut | 3″ | 27½″ | 32 | 2 | 30 | 0 |
| W2 | walnut | ¾″ | 37¼″ | 160 | 0 | 160 | 0 |

**Unused pieces** — produced by the cut list but not attributable to any demand (wrong length for every demand row that needed this component):

| Component | Species | Width | Length | Count |
| --- | --- | --- | --- | --- |
| C1 | cherry | 1½″ | 34″ | 6 |
| C2 | cherry | ¾″ | 34″ | 12 |
| W2 | walnut | ¾″ | 34″ | 12 |
| M1 | maple | 1½″ | 34″ | 4 |

## 7. Panels (profiles and sequence)

The physical panels this plan builds (from the project's panel specs), grouped by identical shape. Qty is how many of each to glue up.

| Panel | Qty | Length | Profiles (slices) | Component sequence |
| --- | --- | --- | --- | --- |
| S | 2 | 37¼″ | L: 11, R: 11 | Me · C2 · M1 · C2 · Md · C2 · M1 · C2 · Md |
| M | 2 | 37¼″ | L: 11, R: 11 | Me · W2 · C1 · W2 · Md · W2 · C1 · W2 · Md |
| H | 1 | 27½″ | L: 8, R: 8 | Me · W1 · Md · W1 · Md |

## 8. Slice Grid

The final step: arrange the slices into the finished face. The same grid keyed by slice id — each slice is framed in its legend color so you can see how to arrange the grid cell by cell. A corner triangle marks a slice placed horizontally flipped.

![Slice grid keyed by slice id](images/slice-map-b513ce4c791c.png)
