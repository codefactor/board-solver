# Board-Solver — Low-Level Drawing Function Specs

Scope of THIS round: the small, low-level drawing primitives only, each with concrete
input/output examples. The next round implements these functions and their tests. Two
things are explicitly **out of scope** here and will be separate later rounds:

- the `solve(project, tool_limits) -> cut_spec` function (its own spec round), and
- the outer program that assembles a full Markdown document with embedded images.

These specs are written to be machine-readable: fixed function names, typed inputs, typed
outputs, and worked examples drawn from the committed YAML (`project.yaml`,
`tool-limits.yaml`, `cut-specs.yaml`) and `schema.json`.

## Conventions

- **Measurement** `= [whole_inches, sixteenths]`. Provide one helper to convert a
  measurement to a rational/float inches value and back; all primitives take measurements
  and convert internally.
- **Scale** `= pixels per inch` (float). A primitive draws geometry at `origin=(x,y)` top-left
  in canvas pixels, using `scale` to size everything.
- **ColorMap** `= { species_name: css_color }`. Not in the schema. Default:
  `{"Cherry": "#b87143", "Walnut": "#604331", "Brown Maple": "#e5d2a5"}`.
- Every primitive returns a **BoundingBox** `{x, y, w, h}` in pixels of what it drew, so a
  higher-level layout can place primitives without overlap. Primitives never decide their
  own position beyond the given origin.
- Primitives draw onto an abstract **Canvas** handle (rectangle + text). The concrete
  surface (PIL image, SVG, etc.) is chosen in the implementation round; specs assume only
  `rect(x,y,w,h,fill,outline?)` and `text(x,y,s,size,color)`.

---

## Geometry helpers (pure, no drawing)

### `measure_to_inches(m: Measurement) -> Rational`
- Example: `measure_to_inches([47, 12]) -> 47 + 12/16 = 47.75`
- Example: `measure_to_inches([0, 2]) -> 0.125`

### `inches_to_measure(x: Rational) -> Measurement`
- Rounds to nearest sixteenth. Example: `inches_to_measure(47.75) -> [47, 12]`.

### `resolve_slice(project, slice_id: str) -> ResolvedSlice`
Resolves a `sliceId` (e.g. `"S-L"`, `"H-R"`, or single-profile `"X"`) against the project.
- **Output `ResolvedSlice`:**
  ```
  {
    panelId: "S",
    profileId: "L" | null,
    components: [ {id:"Me", species:"Brown Maple", width:[0,12]},
                  {id:"C2", species:"Cherry",     width:[0,12]}, ... ],  # ordered, after maxProfile filtering
    height: [0,12]       # panel thickness, OR sliceStrips.width if the panel rips
  }
  ```
- **maxProfile rule:** for a panel with `profiles`, the profile at index `k` (0-based)
  includes a component iff the component has no `maxProfile` OR `maxProfile > k`. Index 0
  (the first profile) always includes every component.
- **Example** (`project.yaml`, `resolve_slice(project,"S-L")`): profile L is index 0, so all
  9 components including the trailing `Md` (maxProfile 1 > 0). `height = [0,12]` (panel S
  thickness).
- **Example** (`resolve_slice(project,"S-R")`): profile R is index 1; the trailing `Md`
  has `maxProfile:1`, and `1 > 1` is false, so it is dropped → 8 components. `height=[0,12]`.
- **Example** (`resolve_slice(project,"H-L")`): panel H has `sliceStrips {count:2,width:[0,4]}`,
  so `height = [0,4]` (the ripped strip width), NOT the panel thickness `[0,13]`.

### `slice_length(resolved: ResolvedSlice) -> Rational`
Sum of component widths. Example: `S-R` = Me¾ + C2¾ + M1·1½ + C2¾ + Md¼ + C2¾ + M1·1½ +
C2¾ = `7` inches. (The L profile adds a trailing Md¼ → `7¼`.)

---

## Drawing primitives

### `draw_slice(canvas, project, slice_id, flip, origin, scale, colors) -> BoundingBox`
Draws one slice as a horizontal strip of colored component cells.
- **Inputs:** `slice_id` (str), `flip` (`"H"` or none), `origin` (px), `scale`, `colors`.
- **Behavior:** `resolve_slice`, then draw each component as a filled rect of width
  `component.width * scale` and height `resolved.height * scale`, left to right; if
  `flip=="H"`, reverse the component order. Outline each cell.
- **Output bbox:** `w = slice_length * scale`, `h = resolved.height * scale`.
- **Example:** `draw_slice(c, project, "H-R", "H", (0,0), 40, default)` draws, right-to-left,
  the reversed H-R profile `[Me, W1, Md, W1]` → walnut/maple cells; bbox height = `0.25*40 = 10px`,
  width = `(¾+3+¼+3)*40 = 7*40 = 280px`.

### `draw_panel(canvas, project, panel_id, origin, scale, colors) -> BoundingBox`
Draws a panel's cross-section (its fullest profile's component cells) — the "what to glue
up" view. Optionally annotate profile slice counts as text beneath.
- **Example:** `draw_panel(c, project, "S", (0,0), 40, default)` draws the 9-cell S-L
  profile; bbox width = `7¼*40 = 290px`, height = panel thickness `¾*40 = 30px`.

### `draw_cut_strip(canvas, strip, source_species, origin, scale, colors, miter_kerf) -> BoundingBox`
Draws ONE strip from a cut-spec board: a horizontal band split into crosscut component
cells, with a visible kerf stripe removed by each crosscut, then an offcut tail.
- **Inputs:** a `strip` object `{width, cuts?, offcutComponent?}`, the `source_species`
  (for color), `miter_kerf` (Measurement, from tool-limits), and the board's drawn length.
- **Behavior:** band height = `strip.width * scale`. Each entry in `cuts` is one crosscut
  that frees a component and **consumes one `miter_kerf` of length**. So for each cut draw a
  species cell of length `cut * scale`, then draw a visible kerf stripe of `miter_kerf * scale`
  (material lost to that crosscut, in a distinct crosscut-loss color). N cuts therefore eat
  `N * miter_kerf`; the horizontal kerf loss differs per strip by how many cuts it has. The
  leftover, `board_length - sum(cuts) - N*miter_kerf`, is the **offcut**: lightened species
  color (waste), unless `offcutComponent` is true (drawn as a normal component cell). A strip
  with empty/absent `cuts` is one full-length species cell (no crosscut, no kerf, no offcut).
- **Example** (`{width:[1,8], cuts:[[34,0]]}` on a board drawn at the source 48⅛″ length):
  one 1½″-tall cell 34″ long + a 1/8″ kerf stripe + a ~14″ lightened offcut tail
  (offcut = 48⅛ − 34 − ⅛ = 14).
- **Example** (`{width:[0,12], cuts:[[34,0],[13,12]]}` on a 48″ board): two cells (34″ and
  13¾″), each followed by a 1/8″ kerf stripe, consuming 34 + 13¾ + 2×⅛ = 48″ — no offcut.

### `draw_cut_board(canvas, cut_spec_board, project, tool_limits, origin, scale, colors) -> BoundingBox`
Draws ONE cut-spec board: a title, then its strips stacked across the board width via
`draw_cut_strip`, then a derived **loss** band and **margin** band.
- **Inputs:** one `board-cut-spec`, the project (to resolve source species + source width),
  the tool-limits (`sawKerf`, planing allowance, `miterKerf`).
- **Derivation (all from specs):**
  - species: `source`/`sourceRemainder` → trace to the project inventory board's species;
    or `buySpecies` directly (and mark the board as buy-required, e.g. gray title).
  - drawn board length = `measure_to_inches(board.length) * scale`.
  - loss (width axis) = per strip `(sawKerf + planing)` summed; planing allowance is a
    tool-limit the implementation round will read (documented as the per-strip face cleanup).
  - margin = `source_width - sum(strip widths) - loss`. Negative margin → draw in an alert
    color; it signals the strips do not fit the real board.
- **Output bbox:** spans the title + all strips + loss + margin bands.
- **Example:** `draw_cut_board(c, BW1A, project, limits, (0,0), s, default)` where `BW1A`
  is `{source:"BW1", length:[27,8], strips:[{width:[3,0],cuts:[[27,8]]} x2]}` → two 3″-tall
  walnut cells 27½″ long, no offcut, then loss/margin bands; title "BW1A".

---

## What each primitive must NOT do

- Must not place itself relative to other primitives (only draws at `origin`, returns bbox).
- Must not read files or know about Markdown/sections/pages — those are the later outer program.
- Must not compute the cutting plan — they consume a given `cut-specs` doc.

---

## Known sections the Round 2 document-writer will need

(Recorded here so the Round 1 primitive set can be checked as sufficient to feed them. NOT
part of Round 1.) From the hand-built example cut list, the human-readable document the
Round 2 process emits has these sections, each buildable from the primitives plus simple
tables:

1. Finished board pattern — a grid of `draw_slice` calls (from `sliceGrid`).
2. Panels overview — `draw_panel` per panel, with profile slice counts.
3. Initial board rips — a table (board, length, cuts, derived used/loss/margin) + optionally
   the composite strip map (many `draw_cut_board`).
4. Components — a table of component id/species/width/length/count (derivable).
5. Panels (merged L+R) — a table of panel/length/slices/component sequence.
6. Plane, slice, flatten — prose + the H `sliceStrips` ripping note.

The primitives Round 1 defines (`draw_slice`, `draw_panel`, `draw_cut_strip`,
`draw_cut_board`) plus the geometry helpers are sufficient to render the visual parts of
sections 1–3; the tables in 3–5 are plain data derivations the Round 2 process computes.

---

## Processes vs. primitives

The system is **two runnable processes** plus a shared library of primitives:

- **Primitives (library):** the pure helpers and drawing primitives from Round 1. No file
  I/O, no versioning — just geometry and drawing onto an abstract Canvas. Both processes
  depend on these.
- **Document-writer process:** reads the YAML specs, renders sections into images, and
  writes a self-contained versioned document folder (Markdown + images).
- **Solver process:** reads a design + inventory (+ `tool-limits.yaml`) and writes a new
  cut-spec into that inventory's `cut-specs/` folder.

### Shared artifact rules (both processes)

A rerun overwrites the current output in place. The project lives in git, so an
old plan is recovered by checking out an old commit, using the
design + inventory + cut-spec tuple as its identity. No side copy is kept.

- **Solver output (a cut-spec):** writing a new cut-spec overwrites the
  file of the same name in that inventory's `cut-specs/` folder. A hand
  cut-spec and a solver cut-spec are different files and never overwrite
  each other.
- **Document output:** each run writes a **self-contained folder** containing the
  `.md` and all its image files together, under
  `plans/<design>/<inventory>/<cut-spec>/`.
- **Image filenames carry a content hash** (hash of the image bytes), so a filename changes
  whenever its content changes (cache-busting), and identical content can reuse a name. The
  Markdown references images by these hashed filenames (relative paths within the folder).

## Development phases

Ordered rounds. A fresh agent can start Round 1 from this document plus `schema.json` and the
three committed YAML files.

### Round 1 — geometry helpers + drawing primitives (library)
**Goal:** implement the pure helpers and the four low-level drawing primitives, with tests.
No file I/O, no versioning — this is the shared library both processes use.
- Implement `measure_to_inches`, `inches_to_measure`, `resolve_slice`, `slice_length`.
- Implement `draw_slice`, `draw_panel`, `draw_cut_strip`, `draw_cut_board` against an
  abstract Canvas (`rect`, `text`) returning a `BoundingBox`.
- **Tests (required):**
  - Round-trip `measure_to_inches` / `inches_to_measure` on sixteenth values.
  - `resolve_slice` maxProfile filtering: `S-L` -> 9 components, `S-R` -> 8; `H-L` height
    is the `sliceStrips.width` `[0,4]`, not panel thickness `[0,13]`.
  - `slice_length`: `S-R` -> 7", `S-L` -> 7¼".
  - Primitive bounding boxes match computed width/height for the worked examples here
    (use a fake Canvas that records draw calls; assert geometry, not pixels).
  - `draw_cut_strip` per-cut kerf stripes and offcut tail length for a strip with one
    cut on a longer board (offcut = board_length - sum(cuts) - N*miter_kerf).
- **Done when:** all helpers/primitives pass tests driven by the committed `project.yaml`
  and `cut-specs.yaml`.

### Round 2 — document-writer process
**Goal:** a runnable process that reads the YAML specs, renders the document's sections to
images using Round 1 primitives, and writes a self-contained versioned document folder
(Markdown + images). This round produces the human-readable output.
- **Section data derivations** (from `project.yaml` + `tool-limits.yaml` + `cut-specs.yaml`):
  - finished-board grid layout (positions for every `sliceGrid` cell),
  - per-panel profile/slice summary,
  - per-board rip rows with used/loss/margin,
  - component demand table (id, species, width, length, count),
  - panel table (id, length, slices, component sequence).
- **Visual section renderers** compose Round 1 primitives into images (finished board,
  panels overview, strip map). Each rendered image is written to a file whose name carries
  a content hash.
- **Document assembly:** emit a Markdown document with the six known sections (see below),
  embedding the hashed image references and the derived tables, for a human to decorate.
  A rerun overwrites the plan folder in place, per the shared artifact rules above.
- **Tests (required):** grid layout satisfies the true-grid assumption (equal row heights
  per row, equal column widths per column; raise on violation); derived tables match the
  committed specs; image filenames change when content changes and are stable when it does
  not; a fresh run overwrites the plan folder in place.

### Round 3 (LATER, separate) — solver process
A runnable process: `solve(project, tool_limits) -> cut_spec`, reading a design +
inventory (+ `tool-limits.yaml`) and writing a new cut-spec into that inventory's
`cut-specs/` folder. Contract and hard constraints are specified in their own round.
Out of scope until Rounds 1–2 are done.

## Starting Round 1

A fresh agent should: read `schema.json`, the three YAML files, and this document; pick the
implementation stack (Python with a simple drawing surface is expected); implement the
Round 1 helpers and primitives with tests; and verify against the worked examples above.
Implement the library only — do not build the Round 2 document-writer or the Round 3 solver.
