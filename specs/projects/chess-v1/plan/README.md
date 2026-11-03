# Chess v1 — Cut Plan

*Two end-grain chess-pattern boards, walnut and brown maple 0.5 in cells, cherry border 0.25 in all sides, built from thin strips only (no component wider than 0.5 in).*

This is a generated plan: the finished design and the cut list that realizes it on the boards in hand. Where the cut list cannot be met from inventory it calls for **bought boards** — buy those and re-run before cutting. The sections follow the build order, from the first crosscut to the final slice-grid assembly.

## 1. Finished board pattern

2 finished boards. Final thickness 1¼″.

The finished plaid face.

![Finished plaid face](images/finished-board-8daaa9a0a698.png)

## 2. Volume Sanity Check

A per-species feasibility check in board feet (1 BF = 144 cubic inches). **Required** is the surfaced volume of every installed slice across all 2 board(s) plus the volume that must be removed to produce them — flattening (sliceDepth − finishedThickness), planing all four edges (minPlaneLoss), and one miter kerf per slice. **Available** is the inventory stock volume. **Volume Offset** = available − required, with available as a percentage of required in parentheses (100% means they are equal); a negative value means the project cannot be built from stock in hand.

| Species | Available | Required | Volume Offset |
| --- | --- | --- | --- |
| maple | 6.9 BF | 0.1 BF + 0.1 BF loss = 0.3 BF | +6.6 BF (2615%) |
| cherry | 3.9 BF | 0.1 BF + 0.1 BF loss = 0.2 BF | +3.7 BF (2372%) |
| walnut | 3.8 BF | 0.1 BF + 0.1 BF loss = 0.3 BF | +3.5 BF (1430%) |

## 3. Crosscut Blanks

The first operation: crosscut each raw inventory board along its length into the labeled board blanks that get ripped later (the Initial board rips section). Boards that start from another board's leftover margin are not raw-stock crosscuts — they appear as the labeled offcuts in the Board Rip Diagram.

| Raw board | Species | Raw length | Blanks (id = length) | Leftover |
| --- | --- | --- | --- | --- |
| BM1 | maple | 98¹⁄₁₆″ | BM1A = 48″ | 50¹⁄₁₆″ |
| BC1 | cherry | 48⅛″ | BC1A = 48″ | ⅛″ |
| BW1 | walnut | 54⁵⁄₁₆″ | BW1A = 48″ | 6⁵⁄₁₆″ |
| BC2 | cherry | 48¹⁄₁₆″ | — (untouched spare) | — |
| BW2 | walnut | 54⁵⁄₁₆″ | — (untouched spare) | — |
| BM2 | maple | 47¹⁵⁄₁₆″ | — (untouched spare) | — |

### Crosscut Diagram

Each bar is one raw board drawn to scale by length; segments are the blanks (labeled with id and length inside), reddish stripes are crosscut kerfs (sawdust), and the pale tail is leftover length. A red tail means the blanks overflow the raw board. An untouched spare is shown washed-out and uncut; a board used whole goes straight to the rip diagram.

![Crosscut Diagram — raw boards cut into length blanks](images/crosscut-blanks-d86920307fcf.png)

## 4. Panels overview

| Panel | Qty | Length | Slices | Height | Ripped | Sequence (outer → in) |
| --- | --- | --- | --- | --- | --- | --- |
| A | 1 | 16⅛″ | 9 | ½″ | — | CB · W · M · W · M · W · M · W · M · CB |
| B | 1 | 16⅛″ | 9 | ½″ | — | CB · M · W · M · W · M · W · M · W · CB |
| C | 1 | 16⅛″ | 9 | ¼″ | — | CT · CT · CT · CT · CT · CT · CT · CT · CT |

### Panel End Grain Diagram

Each panel's end-grain cross-section (the glue-up of component stripes).

![Panel end-grain cross-sections](images/panels-91027eeed544.png)

### Panel Face Diagram

Each panel drawn to scale with its length running top-to-bottom. Components are vertical stripes aligned on the squared edge; profile regions stack down the length, so the silhouette steps narrower where trailing components drop out. Dashed lines are the slice crosscuts; the solid red band is total kerf loss, and the cross-hatched ends are the snipe tails (possible loss, depending on the planer).

![Panel faces to scale](images/panel-faces-e382959d79e9.png)

### Slice Fulfillment

**Demand** is every slice the grid places across all 2 finished board(s). **Supplied** is the slices the panels above produce — snipe lost, ripped panels multiplied by their strip count. **Supply Offset** = supplied − demand: negative is a shortfall, positive is extra (ideally non-negative everywhere).

| Slice | Demand | Supplied | Supply Offset |
| --- | --- | --- | --- |
| C | 2 × 2 = 4 | 9 | +5 |
| A | 4 × 2 = 8 | 9 | +1 |
| B | 4 × 2 = 8 | 9 | +1 |

_The slice counts supplied are calculated assuming the panels and their quantities are delivered perfectly according to the specs in this section. A panel type may have more than one instance; the ideal panels are always quantity 1._

### Ripped Slice Diagram

Slices from panels that are ripped (sliceStrips). Identical slices across panels are merged into one diagram, labeled with how many to cut. The horizontal axis is the slice length (end-grain face); dashed lines are the rip cuts; the red band is rip kerf + planing / margin loss.

![Ripped slice diagrams](images/ripped-slices-b17b72658982.png)

## 5. Initial board rips (the cut list)

Each row is one physical board at the saw: rip the strips down its width, then crosscut each strip to the piece lengths. The **Board** column shows `id @ width` — the board's width when ripping begins. **Used** is the summed strip width, **Loss** is rip kerf + planer cleanup per strip, **Margin** is the leftover width (negative = the strips do not fit; large = the board is oversized for what it yields).

| Board | Origin | Species | Length | Rips (width × count) | Used | Loss | Margin |
| --- | --- | --- | --- | --- | --- | --- | --- |
| BM1A @ 8⁷⁄₁₆″ | BM1 | maple | 48″ | ½″ ×4 | 2″ | ¾″ | 5¹¹⁄₁₆″ |
| BC1A @ 7¼″ | BC1 | cherry | 48″ | ½″ ×5 · ¼″ ×2 | 3″ | 1⁵⁄₁₆″ | 2¹⁵⁄₁₆″ |
| BW1A @ 6¼″ | BW1 | walnut | 48″ | ½″ ×4 | 2″ | ¾″ | 3½″ |

### Board Rip Diagram

Each labeled block below is one physical board. Horizontal bands are the strips ripped down the board's width; within a band, the colored cells are the crosscut pieces (with thin kerf gaps between them) and the lightened tail is the offcut. The pale band under the strips is the leftover margin; a gray title marks a board that must be bought.

![Board Rip Diagram — how the cut list lands on each board](images/strip-map-e5c9eacfda45.png)

## 6. Components

**Demand** is what the finished pattern needs (counted from the slice grid; length is the panel the component belongs to). **Fulfilled** is how many the cut list supplies, matched longest-demand-first using exact-length pieces first, then longer pieces cut down (a piece shorter than the demand cannot be used). **Shortfall** is the unmet count. **Total Overcut** is the wasted length trimmed off — the sum of (piece length − demand length) across every longer piece that had to be cut down to fill this row (0 when exact-length pieces covered it).

| Component | Species | Width | Length | Demand | Fulfilled | Shortfall |
| --- | --- | --- | --- | --- | --- | --- |
| CB | cherry | ¼″ | 16⅛″ | 4 | 4 | 0 |
| CT | cherry | ½″ | 16⅛″ | 9 | 9 | 0 |
| M | maple | ½″ | 16⅛″ | 8 | 8 | 0 |
| W | walnut | ½″ | 16⅛″ | 8 | 8 | 0 |

## 7. Panels (profiles and sequence)

The physical panels this plan builds (from the project's panel specs), grouped by identical shape. Qty is how many of each to glue up.

| Panel | Qty | Length | Profiles (slices) | Component sequence |
| --- | --- | --- | --- | --- |
| A | 1 | 16⅛″ | single: 9 | CB · W · M · W · M · W · M · W · M · CB |
| B | 1 | 16⅛″ | single: 9 | CB · M · W · M · W · M · W · M · W · CB |
| C | 1 | 16⅛″ | single: 9 | CT · CT · CT · CT · CT · CT · CT · CT · CT |

## 8. Slice Grid

The final step: arrange the slices into the finished face. The same grid keyed by slice id — each slice is framed in its legend color so you can see how to arrange the grid cell by cell. A corner triangle marks a slice placed horizontally flipped.

![Slice grid keyed by slice id](images/slice-map-d91dfcef0f65.png)
