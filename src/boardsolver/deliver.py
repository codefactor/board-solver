"""Deliver one plan: design + inventory (+ cut-spec) -> the thing asked for.

Usage (via ./run.sh deliver, see that script for the full form)::

    ./run.sh deliver chess-v1 --inventory actual --what pdf
    ./run.sh deliver plaid-v1 --inventory hypothetical --what cut-list
    ./run.sh deliver plaid-v1 --inventory actual --cut-spec hand --what all

A plan is named by its three-part tuple, and its outputs live under
``plans/<design>/<inventory>/<cut-spec>/`` by default, so one
combination never overwrites another's plan. With ``--out`` the
outputs go to the given directory instead (a shelf copy outside the
repo); that is an override, not the normal path.

* ``--cut-spec`` selects an existing cut-spec by variant (``hand`` /
  ``solver``) or by full stem (``plaid-v1.hand``). A cut-spec is only
  ever looked up inside the named inventory's ``cut-specs/`` folder:
  pairing it with a different inventory is refused, not silently
  rendered against the wrong pile. A cut-spec whose metadata names a
  different design or inventory is likewise refused.
* With no ``--cut-spec``, the solver runs and writes a new cut-spec
  into that inventory's ``cut-specs/`` folder. It never overwrites a
  hand cut-spec: the new file is ``<design>.solver.yaml``, distinct
  from ``<design>.hand.yaml``.
  ``--no-save-cut-spec`` keeps the solved cut-spec in memory only
  (useful for tests and throwaway runs).
* ``--what`` picks exactly one output: ``cut-list``, ``strip-map``,
  ``finished``, ``plan``, ``pdf``, or ``all`` (plan + pdf + the
  three single outputs). No packing or panel decisions are made by
  hand here: panels are derived by bundle.derive_panel_specs and
  the cut list comes from the solver or the named cut-spec.

A cut-spec is a recipe for turning that inventory's boards into a
fixed set of panel components. It prescribes no glue-up.
"""

from __future__ import annotations

import argparse
import os
import re
import shutil
import tempfile
from datetime import date
from typing import Any, Dict, Optional, Tuple

import yaml

from . import bundle
from .docwriter import write_document
from .geometry import sixteenths_to_measure
from .pdf import build_pdf
from .render import render_finished_board, render_strip_map
from .solver import solve


def _pair(n: int):
    return list(sixteenths_to_measure(n))


def dump_cut_spec(cut_spec: Dict[str, Any]) -> str:
    """Cut-spec dict -> YAML text, measurement pairs on one line."""
    lines = [
        f"# Cut-spec for design {cut_spec.get('design')}, "
        f"inventory {cut_spec.get('inventory')}.",
        f"# Kind: {cut_spec.get('kind')}, date: {cut_spec.get('date')}.",
    ]
    for key in ("design", "inventory", "kind", "date"):
        if cut_spec.get(key) is not None:
            value = cut_spec[key]
            # Quote the date so YAML loads it as a string, matching the
            # schema's string type (an unquoted 2026-11-03 parses as a date).
            if key == "date":
                value = f"'{value}'"
            lines.append(f"{key}: {value}")
    lines.append("boards:")
    for board in cut_spec["boards"]:
        lines.append(f"- id: {board['id']}")
        if "source" in board:
            lines.append(f"  source: {board['source']}")
        elif "sourceRemainder" in board:
            lines.append(f"  sourceRemainder: {board['sourceRemainder']}")
        else:
            lines.append(f"  buySpecies: {board['buySpecies']}")
        length = board["length"]
        lines.append(f"  length: {_pair(length) if isinstance(length, int) else length}")
        lines.append("  strips:")
        for strip in board["strips"]:
            width = strip["width"]
            lines.append(f"  - width: {_pair(width) if isinstance(width, int) else width}")
            lines.append("    cuts:")
            for cut in strip["cuts"]:
                lines.append(f"    - {_pair(cut) if isinstance(cut, int) else cut}")
    if cut_spec.get("panels"):
        lines.append("panels:")
        for code in cut_spec["panels"]:
            lines.append(f"- {code}")
    return "\n".join(lines) + "\n"


def _load(path: str) -> Dict[str, Any]:
    with open(path) as f:
        return yaml.safe_load(f)


def _normalize_cut_spec(cut_spec: Dict[str, Any]) -> Dict[str, Any]:
    """Solver output uses raw sixteenths ints; renderers expect [w, s] pairs.

    Loaded YAML cut-specs already carry pairs, so this is a no-op for
    them; it converts in-memory solver output to the same shape.
    """
    boards = []
    for board in cut_spec["boards"]:
        length = board["length"]
        strips = []
        for strip in board["strips"]:
            width = strip["width"]
            strips.append({
                "width": _pair(width) if isinstance(width, int) else width,
                "cuts": [_pair(c) if isinstance(c, int) else c
                         for c in strip["cuts"]],
            })
        entry = dict(board)
        entry["length"] = _pair(length) if isinstance(length, int) else length
        entry["strips"] = strips
        boards.append(entry)
    out = dict(cut_spec)
    out["boards"] = boards
    return out


def resolve_run(
    root: str, design_name: str, inventory_name: str,
    cut_spec_arg: Optional[str] = None,
    tool_limits: Optional[Dict[str, Any]] = None,
    save_cut_spec: bool = True,
) -> Tuple[Dict[str, Any], Dict[str, Any], str, Optional[str]]:
    """Load design + inventory, resolve the project, pick/solve a cut-spec.

    Returns (project, cut_spec, variant, cut_spec_path_or_None).
    ``cut_spec_path_or_None`` is the repo cut-spec file written (or
    reused), or None when the cut-spec was solved in-memory only.
    """
    if tool_limits is None:
        tool_limits = _load(os.path.join(root, "specs", "tool-limits.yaml"))
    design = bundle.load_design(bundle.find_design(root, design_name))
    inventory = bundle.load_inventory(
        bundle.find_inventory_boards(root, inventory_name))
    project = bundle.resolve_bundle(design, inventory, tool_limits)

    if cut_spec_arg:
        path = bundle.find_cut_spec(
            root, inventory_name, design_name, cut_spec_arg)
        cut_spec = _load(path)
        bundle.check_cut_spec_matches(cut_spec, design_name, inventory_name)
        variant = os.path.basename(path)[:-5].split(".", 1)[1]
        return project, cut_spec, variant, path

    # Solve a new one. The repo file for a solver cut-spec is
    # <inventory>/cut-specs/<design>.solver.yaml; never overwrite a
    # hand cut-spec (it lives in a different file, but guard anyway).
    variant = "solver"
    repo_path = os.path.join(root, "specs", "inventories", inventory_name,
                             "cut-specs", f"{design_name}.solver.yaml")
    if os.path.exists(repo_path):
        existing = _load(repo_path)
        if existing.get("kind") == "hand":
            raise ValueError(
                f"refusing to overwrite hand cut-spec at {repo_path}")
    solved = _normalize_cut_spec(solve(project, tool_limits))
    cut_spec = {
        "design": design_name,
        "inventory": inventory_name,
        "kind": "solver",
        "date": date.today().isoformat(),
        "boards": solved["boards"],
    }
    if save_cut_spec:
        os.makedirs(os.path.dirname(repo_path), exist_ok=True)
        with open(repo_path, "w") as f:
            f.write(dump_cut_spec(cut_spec))
        return project, cut_spec, variant, repo_path
    return project, cut_spec, variant, None


def _extract_cut_list(md_text: str) -> str:
    """The 'Initial board rips (the cut list)' section of a plan MD."""
    m = re.search(
        r"(## \d+\. Initial board rips \(the cut list\)\n.*?)(?=\n## \d+\. |\Z)",
        md_text, flags=re.S)
    if not m:
        raise ValueError("plan MD has no Initial board rips section")
    text = m.group(1)
    # The cut-list section ends with its diagram subsection, which is
    # a separate --what (strip-map); a standalone cut-list file must
    # not reference an image it does not ship.
    text = text.split("\n### Board Rip Diagram")[0]
    text = "\n".join(line for line in text.splitlines()
                     if not line.startswith("!["))
    return text.rstrip() + "\n"


def deliver(
    project: Dict[str, Any], cut_spec: Dict[str, Any],
    tool_limits: Dict[str, Any], out_dir: str, what: str,
    run_name: str,
) -> Dict[str, str]:
    """Write exactly the requested output(s) into out_dir. Returns paths."""
    if what not in ("cut-list", "strip-map", "finished", "plan", "pdf", "all"):
        raise ValueError(f"unknown --what {what!r}")
    os.makedirs(out_dir, exist_ok=True)
    outputs: Dict[str, str] = {}
    # Every output derives from the same full plan, generated once
    # into a temp dir so single-output runs leave no plan folder behind.
    with tempfile.TemporaryDirectory(prefix="board-solver-plan-") as tmp:
        res = write_document(project, tool_limits, cut_spec, tmp,
                             folder_name="plan")
        md_text = open(res.markdown_path).read()
        if what in ("plan", "pdf", "all"):
            # The plan lives directly in out_dir: README.md + images/
            # alongside the PDF, per plans/<design>/<inventory>/<cut-spec>/.
            for item in os.listdir(res.folder):
                src = os.path.join(res.folder, item)
                dst = os.path.join(out_dir, item)
                if os.path.isdir(src):
                    if os.path.exists(dst):
                        shutil.rmtree(dst)
                    shutil.copytree(src, dst)
                else:
                    shutil.copy2(src, dst)
            outputs["plan"] = os.path.join(out_dir, "README.md")
        if what in ("pdf", "all"):
            pdf_path = os.path.join(out_dir, f"{run_name}-cut-plan.pdf")
            build_pdf(res.markdown_path, pdf_path)
            outputs["pdf"] = pdf_path
        if what in ("cut-list", "all"):
            cut_path = os.path.join(out_dir, "cut-list.md")
            with open(cut_path, "w") as f:
                f.write(f"# {project.get('name', run_name)} — Cut List\n\n")
                f.write(_extract_cut_list(md_text))
            outputs["cut-list"] = cut_path
        if what in ("strip-map", "all"):
            strip_path = os.path.join(out_dir, "strip-map.png")
            with open(strip_path, "wb") as f:
                f.write(render_strip_map(project, cut_spec, tool_limits))
            outputs["strip-map"] = strip_path
        if what in ("finished", "all"):
            fin_path = os.path.join(out_dir, "finished-board.png")
            with open(fin_path, "wb") as f:
                f.write(render_finished_board(project))
            outputs["finished"] = fin_path
    return outputs


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="board-solver deliver (bundle runs)")
    ap.add_argument("design", help="design name, e.g. plaid-v1")
    ap.add_argument("--inventory", required=True, help="inventory name, e.g. actual")
    ap.add_argument("--cut-spec", default=None,
                    help="cut-spec variant (hand/solver) or full stem")
    ap.add_argument("--what", default="plan",
                    choices=["cut-list", "strip-map", "finished", "plan", "pdf", "all"])
    ap.add_argument("--out", default=None, help="output directory")
    ap.add_argument("--root", default=None, help="repo root (default: cwd's repo)")
    ap.add_argument("--no-save-cut-spec", action="store_true")
    args = ap.parse_args(argv)
    root = args.root or os.getcwd()
    tool_limits = _load(os.path.join(root, "specs", "tool-limits.yaml"))
    try:
        project, cut_spec, variant, _path = resolve_run(
            root, args.design, args.inventory, args.cut_spec, tool_limits,
            save_cut_spec=not args.no_save_cut_spec)
    except (FileNotFoundError, ValueError) as exc:
        print(f"error: {exc}")
        return 2
    # The output directory is built from the three arguments alone:
    # plans/<design>/<inventory>/<cut-spec>/, no hand-typed path needed.
    run_name = f"{args.design}-{args.inventory}-{variant}"
    out_dir = args.out or os.path.join(
        root, "plans", args.design, args.inventory, variant)
    outputs = deliver(project, cut_spec, tool_limits, out_dir, args.what, run_name)
    for key, path in outputs.items():
        print(f"wrote {key}: {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
