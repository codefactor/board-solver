# Plaid v1 — Cut Plan

*Two end-grain plaid cutting boards built from cherry, walnut, and brown maple.*

This is a generated plan: the finished design and the cut list that realizes it on the boards in hand. Where the cut list cannot be met from inventory it calls for **bought boards** — buy those and re-run before cutting. The sections follow the build order, from the first crosscut to the final slice-grid assembly.

## 1. Warnings

| # | Lvl | Type | Message |
| --- | --- | --- | --- |
| 1 | ERROR | Planer Gang Too Small | Strip width 3″ is wider than board thickness ¹³⁄₁₆″, and its gang is too small even after crosscutting to component lengths first: 1 strip(s) total ¹³⁄₁₆″, 2 component(s) total 1⅝″, both below 3″ (needs 4 pieces at ¹³⁄₁₆″). Do not plane singly. |
| 2 | WARNING | Ghost Boards | 3 board(s) must be bought (not in inventory): GH-B, GH-C, GH-W. |
| 3 | WARNING | Small Margin | Board BM2A leaves only ⅛″ margin (< ¼″) — too tight; prone to under-supplying strips if the board runs narrow. |
| 4 | WARNING | Small Margin | Board BC1A leaves only 0″ margin (< ¼″) — too tight; prone to under-supplying strips if the board runs narrow. |
| 5 | WARNING | Small Margin | Board BC2A leaves only ¹⁄₁₆″ margin (< ¼″) — too tight; prone to under-supplying strips if the board runs narrow. |

## 2. Finished board pattern

2 finished boards. Final thickness 1¼″.

![Finished board](images/finished-board-2feef37003c4.png)

## 3. Volume Sanity Check

A per-species feasibility check in board feet (1 BF = 144 cubic inches). **Required** is the surfaced volume of every installed slice across all 2 board(s) plus the volume that must be removed to produce them — flattening (sliceDepth − finishedThickness), planing all four edges (minPlaneLoss), and one miter kerf per slice. **Available** is the inventory stock volume. **Volume Offset** = available − required, with available as a percentage of required in parentheses (100% means they are equal); a negative value means the project cannot be built from stock in hand.

| Species | Available | Required | Volume Offset |
| --- | --- | --- | --- |
| maple | 4.7 BF | 1.4 BF + 1.0 BF loss = 2.4 BF | +2.3 BF (196%) |
| cherry | 2.6 BF | 1.6 BF + 1.0 BF loss = 2.6 BF | +0.0 BF (101%) |
| walnut | 2.7 BF | 1.0 BF + 0.7 BF loss = 1.7 BF | +1.0 BF (156%) |

## 4. Crosscut Blanks

The first operation: crosscut each raw inventory board along its length into the labeled board blanks that get ripped later (the Initial board rips section, which follows immediately, ahead of Panels overview). Boards that start from another board's leftover margin are not raw-stock crosscuts — they appear as the labeled offcuts in the Board Rip Diagram and as a crosscut row (↳) after their parent board's row in the rip cut table.

| Raw board | Species | Raw length | Blanks (id = length) | Leftover |
| --- | --- | --- | --- | --- |
| BM1 | maple | 60″ | BM1A = 48″ | 11⅞″ |
| BM2 | maple | 60″ | BM2A = 48″ | 11⅞″ |
| BC1 | cherry | 40″ | BC1A = 40″ (used whole) | 0″ |
| BC2 | cherry | 40″ | BC2A = 40″ (used whole) | 0″ |
| BW1 | walnut | 48″ | BW1A = 48″ (used whole) | 0″ |
| BW2 | walnut | 48″ | BW2A = 48″ (used whole) | 0″ |

### Crosscut Diagram

Each bar is one raw board drawn to scale by length; segments are the blanks (labeled with id and length inside), reddish stripes are crosscut kerfs (sawdust), and the pale tail is leftover length. A red tail means the blanks overflow the raw board. An untouched spare is shown washed-out and uncut; a board used whole goes straight to the rip diagram. The bars below are the individual primitives, left-aligned (not floated side by side); the combined diagram is also saved in images/ as crosscut-blanks-*.png.

![Crosscut — BM1](images/crosscut-BM1-20346df7b7b8.png)
![Crosscut — BM2](images/crosscut-BM2-3b31f16934e3.png)
![Crosscut — BC1](images/crosscut-BC1-8ecf60677df5.png)
![Crosscut — BC2](images/crosscut-BC2-f170092c6201.png)
![Crosscut — BW1](images/crosscut-BW1-2ae78332d31b.png)
![Crosscut — BW2](images/crosscut-BW2-f6e7da1a2e06.png)

## 5. Initial board rips (the cut list)

Each row is one physical board at the saw: rip the strips down its width, then crosscut each strip to the piece lengths. The **Board** column shows `id @ width` — the board's width when ripping begins. **Used** is the summed strip width, **Loss** is rip kerf + planer cleanup per strip, **Margin** is the leftover width (negative = the strips do not fit; large = the board is oversized for what it yields).

A board whose leftover margin is itself the source of other boards gets a crosscut row (↳) immediately after its own row: it lists, in cut-spec document order, the child boards crosscut off that margin slab, the miter kerf between them, and the slab tail left after the last crosscut. For a crosscut row the Used / Loss / Margin figures are length-axis, not width-axis: Used is the total child length, Loss is the miter kerf consumed, Margin is the slab tail.

| Board | Origin | Species | Length | Rips (width × count) | Used | Loss | Margin |
| --- | --- | --- | --- | --- | --- | --- | --- |
| BM1A @ 7″ | BM1 | maple | 48″ | 1½″ ×4 | 6″ | ¾″ | ¼″ |
| BM2A @ 7″ | BM2 | maple | 48″ | ¾″ ×5 · ¼″ ×5 | 5″ | 1⅞″ | ⅛″ |
| GH-B @ ⅞″ | *None* | maple | 48″ | ¼″ ×2 | ½″ | ⅜″ | 0″ |
| BC1A @ 6″ | BC1 | cherry | 40″ | 1½″ ×3 · ¾″ ×1 | 5¼″ | ¾″ | 0″ |
| BC2A @ 5½″ | BC2 | cherry | 40″ | 1½″ ×1 · ¾″ ×4 | 4½″ | ¹⁵⁄₁₆″ | ¹⁄₁₆″ |
| GH-C @ 2¹³⁄₁₆″ | *None* | cherry | 48″ | ¾″ ×3 | 2¼″ | ⁹⁄₁₆″ | 0″ |
| BW1A @ 5″ | BW1 | walnut | 48″ | 3″ ×1 · ¾″ ×1 | 3¾″ | ⅜″ | ⅞″ |
| BW2A @ 5″ | BW2 | walnut | 48″ | ¾″ ×5 | 3¾″ | ¹⁵⁄₁₆″ | ⁵⁄₁₆″ |
| GH-W @ 1⅞″ | *None* | walnut | 48″ | ¾″ ×2 | 1½″ | ⅜″ | 0″ |

### Board Rip Diagram

Each labeled block below is one physical board. Horizontal bands are the strips ripped down the board's width; within a band, the colored cells are the crosscut pieces (with thin kerf gaps between them) and the lightened tail is the offcut. The pale band under the strips is the leftover margin; a gray title marks a board that must be bought. The blocks below are the individual primitives, flowed to fill the page width instead of one tall combined diagram; the combined diagram is also saved as strip-map.png at the plan root and as images/strip-map-*.png, for a single-image copy of the cut diagram.

![Board rip — BM1A](images/strip-BM1A-640525039dc0.png)
![Board rip — BM2A](images/strip-BM2A-c0df0b3cac52.png)
![Board rip — GH-B](images/strip-GH-B-79d415fe8dd8.png)
![Board rip — BC1A](images/strip-BC1A-30f9a7b20530.png)
![Board rip — BC2A](images/strip-BC2A-ab467b96cd71.png)
![Board rip — GH-C](images/strip-GH-C-32228fd41cf5.png)
![Board rip — BW1A](images/strip-BW1A-2859e29d2682.png)
![Board rip — BW2A](images/strip-BW2A-c243c850bbbd.png)
![Board rip — GH-W](images/strip-GH-W-4abf5c9ecf9c.png)

## 6. Panels overview

| Panel | Qty | Length | Slices | Height | Ripped | Sequence (outer → in) |
| --- | --- | --- | --- | --- | --- | --- |
| SL | 2 | 19⅜″ | 11 | ¾″ | — | Me · C2 · M1 · C2 · Md · C2 · M1 · C2 · Md |
| SR | 2 | 19⅜″ | 11 | ¾″ | — | Me · C2 · M1 · C2 · Md · C2 · M1 · C2 |
| ML | 2 | 19⅜″ | 11 | ¾″ | — | Me · W2 · C1 · W2 · Md · W2 · C1 · W2 · Md |
| MR | 2 | 19⅜″ | 11 | ¾″ | — | Me · W2 · C1 · W2 · Md · W2 · C1 · W2 |
| H | 1 | 17¾″ | 10 (L:5 + R:5) | ¼″ | 2× (¼″) | Me · W1 · Md · W1 · Md |

### Panel End Grain Diagram

Each panel's end-grain cross-section (the glue-up of component stripes). The panels below are the individual primitives, centered in the PDF; the combined diagram is also saved in images/ as panels-*.png.

![Panel — SL](images/panel-SL-6f33e30d4623.png)
![Panel — SR](images/panel-SR-d2be9de4dde9.png)
![Panel — ML](images/panel-ML-5687a9fae733.png)
![Panel — MR](images/panel-MR-e0d933a70d2b.png)
![Panel — H](images/panel-H-9b9d306c572a.png)

### Panel Face Diagram

Each panel drawn to scale with its length running left-to-right, wider than tall, centered in the PDF at 75% of its rendered size, with the panel body moved down away from its title. Components are horizontal stripes aligned on the squared edge; profile regions stack left-to-right, so the silhouette steps shorter where trailing components drop out. Dashed lines are the slice crosscuts; the solid red band is total kerf loss, and the cross-hatched ends are the snipe tails (possible loss, depending on the planer). A blue diamond below a solid line marks a crosscut that is also a profile change. The faces below are the individual primitives, on a white background that bleeds into the page; the combined diagram is also saved in images/ as panel-faces-*.png. The legend follows the flow, centered, instead of sitting at the bottom of one tall image.

![Panel face — SL](images/panel-face-SL-7d17ea11fbbf.png)
![Panel face — SR](images/panel-face-SR-72754ada6e00.png)
![Panel face — ML](images/panel-face-ML-444b249ad3f5.png)
![Panel face — MR](images/panel-face-MR-2a273683ab85.png)
![Panel face — H](images/panel-face-H-e2b53ceef436.png)

![Panel faces legend](images/panel-faces-legend-a06bb7156773.png)

### Slice Fulfillment

**Demand** is every slice the grid places across all 2 finished board(s). **Supplied** is the slices the panels above produce — snipe lost, ripped panels multiplied by their strip count. **Supply Offset** = supplied − demand: negative is a shortfall, positive is extra (ideally non-negative everywhere).

| Slice | Demand | Supplied | Supply Offset |
| --- | --- | --- | --- |
| SL | 10 × 2 = 20 | 22 | +2 |
| SR | 10 × 2 = 20 | 22 | +2 |
| ML | 10 × 2 = 20 | 22 | +2 |
| MR | 10 × 2 = 20 | 22 | +2 |
| H-L | 4 × 2 = 8 | 5 × 2 = 10 | +2 |
| H-R | 4 × 2 = 8 | 5 × 2 = 10 | +2 |

_The slice counts supplied are calculated assuming the panels and their quantities are delivered perfectly according to the specs in this section. A panel type may have more than one instance; the ideal panels are always quantity 1._

## 7. Components

**Demand** is what the finished pattern needs (counted from the slice grid; length is the panel the component belongs to). **Fulfilled** is how many the cut list supplies, matched longest-demand-first using exact-length pieces first, then longer pieces cut down (a piece shorter than the demand cannot be used). **Shortfall** is the unmet count. **Total Overcut** is the wasted length trimmed off — the sum of (piece length − demand length) across every longer piece that had to be cut down to fill this row (0 when exact-length pieces covered it).

| Component | Species | Width | Length | Demand | Fulfilled | Shortfall |
| --- | --- | --- | --- | --- | --- | --- |
| C1 | cherry | 1½″ | 19⅜″ | 8 | 8 | 0 |
| C2 | cherry | ¾″ | 19⅜″ | 16 | 16 | 0 |
| M1 | maple | 1½″ | 19⅜″ | 8 | 8 | 0 |
| Md | maple | ¼″ | 19⅜″ | 12 | 12 | 0 |
| Md | maple | ¼″ | 17¾″ | 2 | 2 | 0 |
| Me | maple | ¾″ | 19⅜″ | 8 | 8 | 0 |
| Me | maple | ¾″ | 17¾″ | 1 | 1 | 0 |
| W1 | walnut | 3″ | 17¾″ | 2 | 2 | 0 |
| W2 | walnut | ¾″ | 19⅜″ | 16 | 16 | 0 |

## 8. Panels (profiles and sequence)

The physical panels this plan builds (from the project's panel specs), grouped by identical shape. Qty is how many of each to glue up.

| Panel | Qty | Length | Profiles (slices) | Component sequence |
| --- | --- | --- | --- | --- |
| SL | 2 | 19⅜″ | single: 11 | Me · C2 · M1 · C2 · Md · C2 · M1 · C2 · Md |
| SR | 2 | 19⅜″ | single: 11 | Me · C2 · M1 · C2 · Md · C2 · M1 · C2 |
| ML | 2 | 19⅜″ | single: 11 | Me · W2 · C1 · W2 · Md · W2 · C1 · W2 · Md |
| MR | 2 | 19⅜″ | single: 11 | Me · W2 · C1 · W2 · Md · W2 · C1 · W2 |
| H | 1 | 17¾″ | L: 5, R: 5 | Me · W1 · Md · W1 · Md |

## 9. Slice Grid

The final step: arrange the slices into the finished face. The same grid keyed by slice id — each slice is framed in its legend color so you can see how to arrange the grid cell by cell. A corner triangle marks a slice placed horizontally flipped.

![Slice grid keyed by slice id](images/slice-map-993c11590913.png)
