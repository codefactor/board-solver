# Chess v1 — Cut List

## 5. Initial board rips (the cut list)

Each row is one physical board at the saw: rip the strips down its width, then crosscut each strip to the piece lengths. The **Board** column shows `id @ width` — the board's width when ripping begins. **Used** is the summed strip width, **Loss** is rip kerf + planer cleanup per strip, **Margin** is the leftover width (negative = the strips do not fit; large = the board is oversized for what it yields).

A board whose leftover margin is itself the source of other boards gets a crosscut row (↳) immediately after its own row: it lists, in cut-spec document order, the child boards crosscut off that margin slab, the miter kerf between them, and the slab tail left after the last crosscut. For a crosscut row the Used / Loss / Margin figures are length-axis, not width-axis: Used is the total child length, Loss is the miter kerf consumed, Margin is the slab tail.

| Board | Origin | Species | Length | Rips (width × count) | Used | Loss | Margin |
| --- | --- | --- | --- | --- | --- | --- | --- |
| BM1A @ 7″ | BM1 | maple | 32⅜″ | 2¼″ ×2 | 4½″ | ⅜″ | 2⅛″ |
| BC1A @ 6″ | BC1 | cherry | 38⅞″ | 2¼″ ×2 | 4½″ | ⅜″ | 1⅛″ |
| BC2A @ 5½″ | BC2 | cherry | 32⅜″ | 1⅛″ ×2 | 2¼″ | ⅜″ | 2⅞″ |
| BW1A @ 5″ | BW1 | walnut | 32⅜″ | 2¼″ ×2 | 4½″ | ⅜″ | ⅛″ |
