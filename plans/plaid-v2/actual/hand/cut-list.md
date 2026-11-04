# Plaid v2 — Cut List

## 5. Initial board rips (the cut list)

Each row is one physical board at the saw: rip the strips down its width, then crosscut each strip to the piece lengths. The **Board** column shows `id @ width` — the board's width when ripping begins. **Used** is the summed strip width, **Loss** is rip kerf + planer cleanup per strip, **Margin** is the leftover width (negative = the strips do not fit; large = the board is oversized for what it yields).

A board whose leftover margin is itself the source of other boards gets a crosscut row (↳) immediately after its own row: it lists, in cut-spec document order, the child boards crosscut off that margin slab, the miter kerf between them, and the slab tail left after the last crosscut. For a crosscut row the Used / Loss / Margin figures are length-axis, not width-axis: Used is the total child length, Loss is the miter kerf consumed, Margin is the slab tail.

| Board | Origin | Species | Length | Rips (width × count) | Used | Loss | Margin |
| --- | --- | --- | --- | --- | --- | --- | --- |
| BM1A @ 8⁷⁄₁₆″ | BM1 | maple | 48⅛″ | 1½″ ×3 · ¾″ ×2 · ¼″ ×2 | 6½″ | 1⁵⁄₁₆″ | ⅝″ |
| BM1B @ 8⁷⁄₁₆″ | BM1 | maple | 35⅝″ | 1½″ ×1 · ¾″ ×3 · ¼″ ×8 | 5¾″ | 2¼″ | ⁷⁄₁₆″ |
| BC1A @ 7³⁄₁₆″ | BC1 | cherry | 48¹⁄₁₆″ | 1½″ ×3 · ¾″ ×2 | 6″ | ¹⁵⁄₁₆″ | ¼″ |
| BC2A @ 6½″ | BC2 | cherry | 48¹⁄₁₆″ | 1½″ ×1 · ¾″ ×5 | 5¼″ | 1⅛″ | ⅛″ |
| BW1A @ 6¼″ | BW1 | walnut | 48⅛″ | 3″ ×1 · ¾″ ×3 | 5¼″ | ¾″ | ¼″ |
| BW2A @ 6¹⁄₁₆″ | BW2 | walnut | 48⅛″ | ¾″ ×5 | 3¾″ | ¹⁵⁄₁₆″ | 1⅜″ |
