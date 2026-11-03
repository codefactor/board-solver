# CLAUDE.md

Agent working agreements for this repo live in **[AGENTS.md](./AGENTS.md)** — read that first,
then **[docs/function-specs.md](./docs/function-specs.md)** for the implementation spec and
**[README.md](./README.md)** for the layout.

Quick reminders (full rules in AGENTS.md):

- `schema.json` (JSON Schema Draft-07) is the source of truth; keep every YAML in `specs/`
  validating against it after any change.
- Measurements are `[whole_inches, sixteenths]` integer tuples — never floats in YAML.
- Atomic ids are strictly alphanumeric; references join them with hyphens (`S-L`).
- Implement only the development round you were asked to (see docs/function-specs.md).
- Generated artifacts are versioned/archived, never silently overwritten; images use
  content-hash filenames.
- The axis/term vocabulary (length, width, thickness, height, sliceDepth, profile, slice,
  strip, component, panel, offcut, loss, margin) has fixed meanings — use them exactly.
