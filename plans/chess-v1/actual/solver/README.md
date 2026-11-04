# Chess v1 — Cut Plan

*One end-grain chess-pattern board, walnut and brown maple 2.25 in cells, cherry border 1.125 in all sides, finished 20.25 in square, 0.5 in thick. Each row is built as two half-width panels split at the centre line (left half mirrors right half), so no panel is wider than 10.125 in and every panel fits the 12.5 in planer. Only three panel patterns are built, A, B and C, and both A and B start with a cherry component. Their mirrors are the same slices placed flipped (flip H), A flipped covers the old BR half, B flipped covers the old AR half, C flipped covers the old CR half.*

This is a generated plan: the finished design and the cut list that realizes it on the boards in hand. Where the cut list cannot be met from inventory it calls for **bought boards** — buy those and re-run before cutting. The sections follow the build order, from the first crosscut to the final slice-grid assembly.

## 1. Warnings

| # | Lvl | Type | Message |
| --- | --- | --- | --- |
| 1 | WARNING | Zero Offcut | 9 strip(s) crosscut to an exact fit with 0″ offcut — no margin for cutting error in the crosscut phase: BM1A ×2, BC1A ×1, BC1A1 ×2, BC1A2 ×2, BW1A ×2. A cut even slightly long, or kerf drift, will make the last piece short. Consider longer blanks or fewer pieces per strip. |

## 2. Finished board pattern

![Finished board](images/finished-board-a428586cb1f2.png)

## 3. Volume Sanity Check

A per-species feasibility check in board feet (1 BF = 144 cubic inches). **Required** is the surfaced volume of every installed slice across all 1 board(s) plus the volume that must be removed to produce them — flattening (sliceDepth − finishedThickness), planing all four edges (minPlaneLoss), and one miter kerf per slice. **Available** is the inventory stock volume. **Volume Offset** = available − required, with available as a percentage of required in parentheses (100% means they are equal); a negative value means the project cannot be built from stock in hand.

| Species | Available | Required | Volume Offset |
| --- | --- | --- | --- |
| maple | 6.9 BF | 0.6 BF + 1.5 BF loss = 2.0 BF | +4.9 BF (342%) |
| cherry | 3.7 BF | 0.3 BF + 0.8 BF loss = 1.1 BF | +2.6 BF (330%) |
| walnut | 3.8 BF | 0.6 BF + 1.5 BF loss = 2.0 BF | +1.8 BF (187%) |

## 4. Crosscut Blanks

The first operation: crosscut each raw inventory board along its length into the labeled board blanks that get ripped later (the Initial board rips section, which follows immediately, ahead of Panels overview). Boards that start from another board's leftover margin are not raw-stock crosscuts — they appear as the labeled offcuts in the Board Rip Diagram and as a crosscut row (↳) after their parent board's row in the rip cut table.

| Raw board | Species | Raw length | Blanks (id = length) | Leftover |
| --- | --- | --- | --- | --- |
| BM1 | maple | 98¹⁄₁₆″ | BM1A = 32⅜″ | 65⁹⁄₁₆″ |
| BC1 | cherry | 48¹⁄₁₆″ | BC1A = 38⅞″ | 9¹⁄₁₆″ |
| BW1 | walnut | 54⁵⁄₁₆″ | BW1A = 32⅜″ | 21¹³⁄₁₆″ |
| BC2 | cherry | 48¹⁄₁₆″ | — (untouched spare) | — |
| BW2 | walnut | 54⁵⁄₁₆″ | — (untouched spare) | — |
| BM2 | maple | 47¹⁵⁄₁₆″ | — (untouched spare) | — |

### Crosscut Diagram

Each bar is one raw board drawn to scale by length; segments are the blanks (labeled with id and length inside), reddish stripes are crosscut kerfs (sawdust), and the pale tail is leftover length. A red tail means the blanks overflow the raw board. An untouched spare is shown washed-out and uncut; a board used whole goes straight to the rip diagram. The bars below are the individual primitives, left-aligned (not floated side by side); the combined diagram is also saved in images/ as crosscut-blanks-*.png.

![Crosscut — BM1](images/crosscut-BM1-c932f022b685.png)
![Crosscut — BC1](images/crosscut-BC1-f40e37b551d1.png)
![Crosscut — BW1](images/crosscut-BW1-e5dd3a05119c.png)
![Crosscut — BC2](images/crosscut-BC2-e528a860fdf1.png)
![Crosscut — BW2](images/crosscut-BW2-6ee662eb4739.png)
![Crosscut — BM2](images/crosscut-BM2-d33eb323c7e5.png)

## 5. Initial board rips (the cut list)

Each row is one physical board at the saw: rip the strips down its width, then crosscut each strip to the piece lengths. The **Board** column shows `id @ width` — the board's width when ripping begins. **Used** is the summed strip width, **Loss** is rip kerf + planer cleanup per strip, **Margin** is the leftover width (negative = the strips do not fit; large = the board is oversized for what it yields).

A board whose leftover margin is itself the source of other boards gets a crosscut row (↳) immediately after its own row: it lists, in cut-spec document order, the child boards crosscut off that margin slab, the miter kerf between them, and the slab tail left after the last crosscut. For a crosscut row the Used / Loss / Margin figures are length-axis, not width-axis: Used is the total child length, Loss is the miter kerf consumed, Margin is the slab tail.

| Board | Origin | Species | Length | Rips (width × count) | Used | Loss | Margin |
| --- | --- | --- | --- | --- | --- | --- | --- |
| BM1A @ 8⁷⁄₁₆″ | BM1 | maple | 32⅜″ | 2¼″ ×2 | 4½″ | ⅜″ | 3⁹⁄₁₆″ |
| BC1A @ 7³⁄₁₆″ | BC1 | cherry | 38⅞″ | 2¼″ ×1 | 2¼″ | ³⁄₁₆″ | 4¾″ |
| ↳ margin crosscuts | remainder of BC1A | cherry | 29¼″ | BC1A1 = 12⅞″; BC1A2 = 16⅛″ | 29″ | ¼″ | 9⅝″ |
| BC1A1 @ 4¾″ | remainder of BC1A | cherry | 12⅞″ | 2¼″ ×1 · 1⅛″ ×1 | 3⅜″ | ⅜″ | 1″ |
| BC1A2 @ 4¾″ | remainder of BC1A | cherry | 16⅛″ | 1⅛″ ×2 | 2¼″ | ⅜″ | 2⅛″ |
| BW1A @ 6¼″ | BW1 | walnut | 32⅜″ | 2¼″ ×2 | 4½″ | ⅜″ | 1⅜″ |

### Board Rip Diagram

Each labeled block below is one physical board. Horizontal bands are the strips ripped down the board's width; within a band, the colored cells are the crosscut pieces (with thin kerf gaps between them) and the lightened tail is the offcut. The pale band under the strips is the leftover margin; a gray title marks a board that must be bought. The blocks below are the individual primitives, flowed to fill the page width instead of one tall combined diagram; the combined diagram is also saved as strip-map.png at the plan root and as images/strip-map-*.png, for a single-image copy of the cut diagram.

![Board rip — BM1A](images/strip-BM1A-351526096717.png)
![Board rip — BC1A](images/strip-BC1A-d26483378bdb.png)
![Board rip — BC1A1](images/strip-BC1A1-8e18e97cd7de.png)
![Board rip — BC1A2](images/strip-BC1A2-f87ded08bdf1.png)
![Board rip — BW1A](images/strip-BW1A-d2eff8b95012.png)

## 6. Panels overview

| Panel | Qty | Length | Slices | Height | Ripped | Sequence (outer → in) |
| --- | --- | --- | --- | --- | --- | --- |
| A | 1 | 16⅛″ | 9 | 2¼″ | — | CB · W · M · W · M |
| B | 1 | 16⅛″ | 9 | 2¼″ | — | CB · M · W · M · W |
| C | 1 | 12⅞″ | 7 | 1⅛″ | — | CT · CT · CT · CT · CTH |

### Panel End Grain Diagram

Each panel's end-grain cross-section (the glue-up of component stripes). The panels below are the individual primitives, centered in the PDF; the combined diagram is also saved in images/ as panels-*.png.

![Panel — A](images/panel-A-dcc7ec6e99ab.png)
![Panel — B](images/panel-B-af7227458579.png)
![Panel — C](images/panel-C-3cca7a135733.png)

### Panel Face Diagram

Each panel drawn to scale with its length running left-to-right, wider than tall, centered in the PDF at 75% of its rendered size, with the panel body moved down away from its title. Components are horizontal stripes aligned on the squared edge; profile regions stack left-to-right, so the silhouette steps shorter where trailing components drop out. Dashed lines are the slice crosscuts; the solid red band is total kerf loss, and the cross-hatched ends are the snipe tails (possible loss, depending on the planer). A blue diamond below a solid line marks a crosscut that is also a profile change. The faces below are the individual primitives, on a white background that bleeds into the page; the combined diagram is also saved in images/ as panel-faces-*.png. The legend follows the flow, centered, instead of sitting at the bottom of one tall image.

![Panel face — A](images/panel-face-A-7733e77c974e.png)
![Panel face — B](images/panel-face-B-0a9b038139e6.png)
![Panel face — C](images/panel-face-C-29ac5cee8284.png)

![Panel faces legend](images/panel-faces-legend-a06bb7156773.png)

### Slice Fulfillment

**Demand** is every slice the grid places across all 1 finished board(s). **Supplied** is the slices the panels above produce — snipe lost, ripped panels multiplied by their strip count. **Supply Offset** = supplied − demand: negative is a shortfall, positive is extra (ideally non-negative everywhere).

| Slice | Demand | Supplied | Supply Offset |
| --- | --- | --- | --- |
| C | 4 × 1 = 4 | 7 | +3 |
| A | 8 × 1 = 8 | 9 | +1 |
| B | 8 × 1 = 8 | 9 | +1 |

_The slice counts supplied are calculated assuming the panels and their quantities are delivered perfectly according to the specs in this section. A panel type may have more than one instance; the ideal panels are always quantity 1._

## 7. Components

**Demand** is what the finished pattern needs (counted from the slice grid; length is the panel the component belongs to). **Fulfilled** is how many the cut list supplies, matched longest-demand-first using exact-length pieces first, then longer pieces cut down (a piece shorter than the demand cannot be used). **Shortfall** is the unmet count. **Total Overcut** is the wasted length trimmed off — the sum of (piece length − demand length) across every longer piece that had to be cut down to fill this row (0 when exact-length pieces covered it).

| Component | Species | Width | Length | Demand | Fulfilled | Shortfall |
| --- | --- | --- | --- | --- | --- | --- |
| CB | cherry | 1⅛″ | 16⅛″ | 2 | 2 | 0 |
| CT | cherry | 2¼″ | 12⅞″ | 4 | 4 | 0 |
| CTH | cherry | 1⅛″ | 12⅞″ | 1 | 1 | 0 |
| M | maple | 2¼″ | 16⅛″ | 4 | 4 | 0 |
| W | walnut | 2¼″ | 16⅛″ | 4 | 4 | 0 |

## 8. Panels (profiles and sequence)

The physical panels this plan builds (from the project's panel specs), grouped by identical shape. Qty is how many of each to glue up.

| Panel | Qty | Length | Profiles (slices) | Component sequence |
| --- | --- | --- | --- | --- |
| A | 1 | 16⅛″ | single: 9 | CB · W · M · W · M |
| B | 1 | 16⅛″ | single: 9 | CB · M · W · M · W |
| C | 1 | 12⅞″ | single: 7 | CT · CT · CT · CT · CTH |

## 9. Slice Grid

The final step: arrange the slices into the finished face. The same grid keyed by slice id — each slice is framed in its legend color so you can see how to arrange the grid cell by cell. A corner triangle marks a slice placed horizontally flipped.

![Slice grid keyed by slice id](images/slice-map-15e3f2f0024e.png)
