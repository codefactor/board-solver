# Plaid v1 — Cut List

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
