# AGENTS.md — working agreements for the board-solver repo

Read this and `docs/function-specs.md` before changing anything here.

## What this repo is

A spec-driven planner for breaking lumber into end-grain "plaid" cutting boards. It is
**specs-first**: `schema.json` + the YAML in `specs/` define the data; `docs/function-specs.md`
defines the code to be written in ordered rounds. `src/` is empty until Round 1.

## Hard rules

- **The schema is the source of truth.** `schema.json` (JSON Schema Draft-07) defines every
  document shape, field meaning, unit, and id rule. Do not invent fields or meanings that
  aren't in the schema; if something is missing, add it to the schema (with a clear
  `description`) rather than assuming it in code.
- **Every YAML spec must validate against `schema.json`** after any change. Validate before
  considering a change done (see README for a snippet). `additionalProperties: false` is set
  widely — typos will fail validation.
- **Measurements are `[whole_inches, sixteenths]` integer tuples.** Never use floats in the
  YAML. Do exact arithmetic (rationals/sixteenths) in code and convert only at the drawing edge.
- **IDs:** atomic ids are strictly alphanumeric (`^[A-Za-z\d]+$`). References compose them with
  hyphens (`S-L`, at most two segments). Never put a hyphen inside an atomic id.
- **Respect the round boundaries** in `docs/function-specs.md`. Implement the round you were
  asked to; do not build later rounds ahead of time.
- **Generated artifacts are versioned, never clobbered.** The solver archives the previous
  `cut-specs.yaml`; the document-writer writes a new versioned folder and archives the old.
  Images use content-hash filenames for cache-busting.

## Axis / term discipline (these words have fixed meanings — use them exactly)

- **length** — a board's/strip's long dimension (the rip direction).
- **width** — across a board (rips divide width into strips); also a component's stripe width
  across the finished face.
- **thickness** — a board's/panel's dimension into the page (the planed depth).
- **height** — a slice's/row's vertical extent **in a face drawing**. Equals the panel
  thickness, or `sliceStrips.width` when the panel's slices are ripped.
- **sliceDepth** — how thick each slice is cut from a panel (the crosscut pitch); becomes the
  finished board thickness before flattening.
- **profile** — a region of a panel's slices sharing the same component makeup (trailing
  components drop out in later profiles via `maxProfile`).
- **slice / strip / component / panel / offcut / loss / margin** — as defined in the schema
  descriptions and `docs/function-specs.md`. Do not reuse these words with new meanings.

## Known gaps to resolve before/while coding

- The **per-strip planing loss** used in margin math is referenced in the specs but is not yet
  a concrete `tool-limits` field. Pin it to an explicit field before Round 2 relies on it.
- The committed `cut-specs.yaml` is a **hand-built, schema-valid, limit-respecting example**,
  not a solver-optimized plan. It exists to exercise the shape (panel splitting, long-board
  crosscuts, ghost boards). Don't treat its specific packing as optimal.

## Style

- Keep YAML clean and literal: no anchors/aliases; measurement pairs on one line (`[34, 0]`).
- Prefer adding a documented schema field over encoding an assumption in code.
- When a design decision is genuinely open, state it plainly and pick a default; don't pad
  with filler or manufacture false choices.
