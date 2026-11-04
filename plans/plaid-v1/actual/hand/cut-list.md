# Plaid v1 — Cut List

## 5. Initial board rips (the cut list)

Each row is one physical board at the saw: rip the strips down its width, then crosscut each strip to the piece lengths. The **Board** column shows `id @ width` — the board's width when ripping begins. **Used** is the summed strip width, **Loss** is rip kerf + planer cleanup per strip, **Margin** is the leftover width (negative = the strips do not fit; large = the board is oversized for what it yields).

A board whose leftover margin is itself the source of other boards gets a crosscut row (↳) immediately after its own row: it lists, in cut-spec document order, the child boards crosscut off that margin slab, the miter kerf between them, and the slab tail left after the last crosscut. For a crosscut row the Used / Loss / Margin figures are length-axis, not width-axis: Used is the total child length, Loss is the miter kerf consumed, Margin is the slab tail.

| Board | Origin | Species | Length | Rips (width × count) | Used | Loss | Margin |
| --- | --- | --- | --- | --- | --- | --- | --- |
| BM1A @ 8⁷⁄₁₆″ | BM1 | maple | 48″ | 1½″ ×4 · ¾″ ×1 · ¼″ ×1 | 7″ | 1⅛″ | ⁵⁄₁₆″ |
| BM1B @ 8⁷⁄₁₆″ | BM1 | maple | 48″ | ¾″ ×4 · ¼″ ×6 | 4½″ | 1⅞″ | 2¹⁄₁₆″ |
| BC1A @ 7³⁄₁₆″ | BC1 | cherry | 48″ | 1½″ ×1 · ¾″ ×6 | 6″ | 1⁵⁄₁₆″ | -⅛″ |
| BC2A @ 6½″ | BC2 | cherry | 48″ | 1½″ ×3 · ¾″ ×2 | 6″ | ¹⁵⁄₁₆″ | -⁷⁄₁₆″ |
| BW1A @ 6¼″ | BW1 | walnut | 48″ | 3″ ×1 · ¾″ ×3 | 5¼″ | ¾″ | ¼″ |
| BW2A @ 6¹⁄₁₆″ | BW2 | walnut | 48″ | ¾″ ×5 | 3¾″ | ¹⁵⁄₁₆″ | 1⅜″ |
