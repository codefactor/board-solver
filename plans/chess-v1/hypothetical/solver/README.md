# Chess v1 — Cut Plan

*One end-grain chess-pattern board, walnut and brown maple 2.25 in cells, cherry border 1.125 in all sides, finished 20.25 in square, 0.5 in thick. Each row is built as two half-width panels split at the centre line (left half mirrors right half), so no panel is wider than 10.125 in and every panel fits the 12.5 in planer. Only three panel patterns are built, A, B and C, and both A and B start with a cherry component. Their mirrors are the same slices placed flipped (flip H), A flipped covers the old BR half, B flipped covers the old AR half, C flipped covers the old CR half.*

Cut list for the finished design, in build order.

## 1. Warnings

| # | Lvl | Type | Message |
| --- | --- | --- | --- |
| 1 | WARNING | Small Margin | Board BW1A leaves only ⅛″ margin (< ¼″) — too tight; prone to under-supplying strips if the board runs narrow. |
| 2 | WARNING | Zero Offcut | 6 strip(s) crosscut to an exact fit with 0″ offcut — no margin for cutting error in the crosscut phase: BM1A ×2, BC1A ×1, BC2A ×1, BW1A ×2. A cut even slightly long, or kerf drift, will make the last piece short. Consider longer blanks or fewer pieces per strip. |

## 2. Finished board pattern

![Finished board](images/finished-board-a428586cb1f2.png)

## 3. Volume Sanity Check

Review the per-species volumes against inventory.

| Species | Available | Required | Volume Offset |
| --- | --- | --- | --- |
| maple | 4.7 BF | 0.6 BF + 1.5 BF loss = 2.0 BF | +2.7 BF (235%) |
| cherry | 2.6 BF | 0.3 BF + 0.8 BF loss = 1.1 BF | +1.5 BF (231%) |
| walnut | 2.7 BF | 0.6 BF + 1.5 BF loss = 2.0 BF | +0.7 BF (134%) |

## 4. Crosscut Blanks

This plan involves cutting blanks from the inventory — review the inventory and the planned cuts.

| Raw board | Species | Raw length | Blanks (id = length) | Leftover |
| --- | --- | --- | --- | --- |
| BM1 | maple | 60″ | BM1A = 32⅜″ | 27½″ |
| BC1 | cherry | 40″ | BC1A = 38⅞″ | 1″ |
| BC2 | cherry | 40″ | BC2A = 32⅜″ | 7½″ |
| BW1 | walnut | 48″ | BW1A = 32⅜″ | 15½″ |
| BW2 | walnut | 48″ | — (untouched spare) | — |
| BM2 | maple | 60″ | — (untouched spare) | — |

### Crosscut Diagram

![Crosscut Diagram — raw boards cut into length blanks](images/crosscut-compact-27b4cac8f3a3.png)

## 5. Initial board rips (the cut list)

Review the rip list.

| Board | Origin | Species | Length | Rips (width × count) | Used | Loss | Margin |
| --- | --- | --- | --- | --- | --- | --- | --- |
| BM1A @ 7″ | BM1 | maple | 32⅜″ | 2¼″ ×2 | 4½″ | ⅜″ | 2⅛″ |
| BC1A @ 6″ | BC1 | cherry | 38⅞″ | 2¼″ ×2 | 4½″ | ⅜″ | 1⅛″ |
| BC2A @ 5½″ | BC2 | cherry | 32⅜″ | 1⅛″ ×2 | 2¼″ | ⅜″ | 2⅞″ |
| BW1A @ 5″ | BW1 | walnut | 32⅜″ | 2¼″ ×2 | 4½″ | ⅜″ | ⅛″ |

### Board Rip Diagram

Review the board rip diagrams against the rip list.

![Board rip — BM1A](images/strip-BM1A-1d5288a8b066.png)
![Board rip — BC1A](images/strip-BC1A-db501f3fd579.png)
![Board rip — BC2A](images/strip-BC2A-f1a71d2d8e9e.png)
![Board rip — BW1A](images/strip-BW1A-d401a8b72525.png)

## 6. Panels overview

| Panel | Qty | Length | Slices | Height | Ripped | Sequence (outer → in) |
| --- | --- | --- | --- | --- | --- | --- |
| A | 1 | 16⅛″ | 9 | 2¼″ | — | CB · W · M · W · M |
| B | 1 | 16⅛″ | 9 | 2¼″ | — | CB · M · W · M · W |
| C | 1 | 12⅞″ | 7 | 1⅛″ | — | CT · CT · CT · CT · CTH |

### Panel End Grain Diagram

Review the panel end-grain diagrams.

![Panel end-grain cross-sections](images/panels-compact-0f4ca4b49bd2.png)

### Panel Face Diagram

Review the panel face diagrams.

![Panel face — A](images/panel-face-A-7733e77c974e.png)
![Panel face — B](images/panel-face-B-0a9b038139e6.png)
![Panel face — C](images/panel-face-C-29ac5cee8284.png)

![Panel faces legend](images/panel-faces-legend-a06bb7156773.png)

### Slice Fulfillment

Review slice demand, supply, and offset.

| Slice | Demand | Supplied | Supply Offset |
| --- | --- | --- | --- |
| C | 4 × 1 = 4 | 7 | +3 |
| A | 8 × 1 = 8 | 9 | +1 |
| B | 8 × 1 = 8 | 9 | +1 |

## 7. Components

Review component demand, fulfillment, and shortfall.

| Component | Species | Width | Length | Demand | Fulfilled | Shortfall |
| --- | --- | --- | --- | --- | --- | --- |
| CB | cherry | 1⅛″ | 16⅛″ | 2 | 2 | 0 |
| CT | cherry | 2¼″ | 12⅞″ | 4 | 4 | 0 |
| CTH | cherry | 1⅛″ | 12⅞″ | 1 | 1 | 0 |
| M | maple | 2¼″ | 16⅛″ | 4 | 4 | 0 |
| W | walnut | 2¼″ | 16⅛″ | 4 | 4 | 0 |

## 8. Panels (profiles and sequence)

Review the panels and their quantities.

| Panel | Qty | Length | Profiles (slices) | Component sequence |
| --- | --- | --- | --- | --- |
| A | 1 | 16⅛″ | single: 9 | CB · W · M · W · M |
| B | 1 | 16⅛″ | single: 9 | CB · M · W · M · W |
| C | 1 | 12⅞″ | single: 7 | CT · CT · CT · CT · CTH |
