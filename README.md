# board-solver

A spec-driven tool for planning how to break down lumber boards into strips and crosscut
pieces, glue them into panels, slice those panels into end-grain pieces, and assemble them
into "plaid" end-grain cutting boards — then render human-readable cut plans and diagrams.

This repository is currently **specs-first**: the data shapes and function specs are
defined and validated; the code is implemented in ordered rounds (see below).

## Layout

```
schema.json                      JSON Schema (Draft-07) for every document shape.
specs/
  tool-limits.yaml               Static limits of the physical toolset (one doc).
  projects/plaid-v1/
    project.yaml                 A project: inventory boards + pattern (components,
                                 panels, sliceGrid) + finished-board info.
    cut-specs.yaml               A cutting plan (normally a solver OUTPUT; the committed
                                 one is a hand-built, schema-valid example).
docs/
  function-specs.md              THE spec for the code: primitives, processes, and the
                                 phased development plan. Read this before coding.
  reference-images/              Example diagrams from an earlier ad-hoc build, cited by
                                 the specs as illustrations of target output.
src/                             Implementation (empty until Round 1 begins).
```

## The four document types (all defined in `schema.json`)

- **tool-limits** — saw/planer/miter capacities, kerfs, angle ranges, snipe allowance.
- **project** — the inventory in hand plus the design: `components` (stripe vocabulary),
  `panels` (glue-ups, with profiles and optional slice-ripping), and `sliceGrid` (how one
  finished board face is reconstructed from slices).
- **cut-spec** — a minimal, non-redundant plan of how each board is cut (strips + crosscuts),
  with boards sourced from inventory, from another board's width-remainder, or bought
  ("ghost" boards). Normally produced by the solver.

All measurements are integer tuples `[whole_inches, sixteenths]`.

## Bundles: design + inventory + solution (the new path)

The old format packs pattern, boards and panel choices into one
`project.yaml`. The bundle format splits them, so one combination
never overwrites another:

- `specs/designs/<name>.yaml` — pattern only (grid, components,
  panels, batch, thickness, slice depth). No boards, no panel specs.
- `specs/inventories/<name>.yaml` — a reusable pile of boards. The
  same inventory feeds any design, with no copying.
- `specs/solutions/<design>.<inventory>.<kind>.yaml` — a cut list
  plus metadata naming its design, inventory, kind (`hand` or
  `solver`) and date. A solver run writes a new solver solution; it
  never overwrites a hand solution.

Panels are derived, not hand-written, on this path: panel count and
length come from grid demand, slice pitch, snipe, batch and a
one-spare-slice-per-profile policy, capped so a panel still lets two
sticks fit in one crosscut blank. The derived panels match the
committed plaid-v1 and chess-v1 panel specs exactly.

Deliver one run, exactly the output asked for:

```
./run.sh deliver plaid-v1 --inventory actual --solution hand --what cut-list
./run.sh deliver chess-v1 --inventory hypothetical --what pdf
./run.sh deliver plaid-v1 --inventory actual --what all
```

Outputs live under `specs/runs/<design>.<inventory>.<solution>/`
by default (or `--out=DIR`), so a new pile or a new cut list gets
its own folder. With no `--solution`, the solver runs and saves a
new `<design>.<inventory>.solver.yaml` (unless `--no-save-solution`).

The old path is unchanged: `./run.sh plan / solve / pdf <project>`
still work on `specs/projects/<project>/` exactly as before.

## How the system is meant to run

Two runnable processes share one library of drawing/geometry primitives:

- **Document-writer** — reads the YAML, renders sections to images (content-hash filenames),
  and writes a self-contained **versioned folder** (Markdown + images) for a human to decorate.
- **Solver** — reads `project.yaml` (+ `tool-limits.yaml`) and writes a new `cut-specs.yaml`,
  **archiving** the previous one.

Generated artifacts are never silently overwritten — the old version is archived first.

## Development phases (see `docs/function-specs.md` for detail)

1. **Round 1** — geometry helpers + drawing primitives (pure library, no I/O, with tests).
2. **Round 2** — the document-writer process (section derivations, renderers, MD + images,
   versioning).
3. **Round 3** — the solver process.

## Validating the specs

The schema is JSON Schema Draft-07; the YAML files must validate against it. Any Draft-07
validator works. Example (Python, in a venv with `pyyaml` + `jsonschema`):

```python
import json, yaml, jsonschema
schema = json.load(open("schema.json"))
jsonschema.Draft7Validator.check_schema(schema)
for f in ["specs/tool-limits.yaml",
          "specs/projects/plaid-v1/project.yaml",
          "specs/projects/plaid-v1/cut-specs.yaml"]:
    jsonschema.Draft7Validator(schema).validate(yaml.safe_load(open(f)))
```

## See also

- `docs/function-specs.md` — the authoritative spec for implementation.
- `AGENTS.md` — working agreements for agents/humans editing this repo.
