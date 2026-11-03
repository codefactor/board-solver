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
  designs/<name>.yaml            A design: pattern only (components, panels,
                                 sliceGrid) + finished-board info. No boards.
  inventories/<name>/
    boards.yaml                  That inventory's boards, referenced by name.
    cut-specs/<design>.<variant>.yaml
                                 A cut-spec for that design from that inventory:
                                 a recipe for turning those boards into a fixed
                                 set of panel components. No glue-up prescription.
plans/<design>/<inventory>/<cut-spec>/
  README.md                      A generated plan for that exact tuple, with
  images/                        diagrams, and the plan PDF alongside it.
docs/
  function-specs.md              THE spec for the code: primitives, processes, and the
                                 phased development plan. Read this before coding.
  reference-images/              Example diagrams from an earlier ad-hoc build, cited by
                                 the specs as illustrations of target output.
src/                             Implementation.
```

## The document types (all defined in `schema.json`)

- **tool-limits** — saw/planer/miter capacities, kerfs, angle ranges, snipe allowance.
- **design** — the pattern only: `components` (stripe vocabulary),
  `panels` (glue-ups, with profiles and optional slice-ripping), and `sliceGrid` (how one
  finished board face is reconstructed from slices).
- **inventory** — a reusable pile of boards, in `boards.yaml` under
  `specs/inventories/<name>/`.
- **cut-spec** — a minimal, non-redundant plan of how each board is cut (strips + crosscuts),
  with boards sourced from its inventory, from another board's width-remainder, or bought
  ("ghost" boards). Normally produced by the solver. A cut-spec lives only inside its
  inventory's `cut-specs/` folder: it is meaningful only in the context of that inventory.

All measurements are integer tuples `[whole_inches, sixteenths]`.

## Plans: design + inventory + cut-spec

Panels are derived, not hand-written: panel count and length come from grid demand,
slice pitch, snipe, batch and a one-spare-slice-per-profile policy, capped so a panel
still lets two sticks fit in one crosscut blank. The derived panels match the
committed plaid-v1 and chess-v1 panel specs exactly.

Deliver one plan, exactly the output asked for:

```
./run.sh deliver plaid-v1 --inventory actual --cut-spec hand --what cut-list
./run.sh deliver chess-v1 --inventory hypothetical --what pdf
./run.sh deliver plaid-v1 --inventory actual --what all
```

Outputs live under `plans/<design>/<inventory>/<cut-spec>/` by default
(or `--out=DIR` for a shelf copy outside the repo). With no `--cut-spec`, the solver
runs and saves a new `<design>.solver.yaml` into that inventory's `cut-specs/` folder
(unless `--no-save-cut-spec`). A rerun overwrites the plan folder in place: the
project lives in git, so an old plan is recovered by checking out an old commit.

## How the system is meant to run

Two runnable processes share one library of drawing/geometry primitives:

- **Document-writer** — reads the YAML, renders sections to images (content-hash filenames),
  and writes a self-contained folder (Markdown + images) for a human to decorate.
- **Solver** — reads a design + inventory and writes a new cut-spec into that
  inventory's `cut-specs/` folder.

A rerun overwrites the plan folder in place. Git history is the recovery path
for an old plan.

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
          "specs/designs/plaid-v1.yaml",
          "specs/inventories/actual/boards.yaml",
          "specs/inventories/actual/cut-specs/plaid-v1.hand.yaml"]:
    jsonschema.Draft7Validator(schema).validate(yaml.safe_load(open(f)))
```

## See also

- `docs/function-specs.md` — the authoritative spec for implementation.
- `AGENTS.md` — working agreements for agents/humans editing this repo.
