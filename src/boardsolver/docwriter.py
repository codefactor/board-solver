"""Round 2 document-writer process: the runnable output stage.

Reads the three YAML docs, renders the visual sections to content-hashed PNGs,
assembles the Markdown, and writes a self-contained folder. A rerun
overwrites the folder in place: the project lives in git, so recovering
an old plan is done by checking out an old commit, not by keeping a
copy beside the current one.

Shared artifact rules:
  * image filenames carry a content hash (changed bytes => new name; identical
    bytes => reused name),
  * each run writes the folder named by the caller.
"""

from __future__ import annotations

import hashlib
import os
import shutil
from dataclasses import dataclass
from typing import Any, Dict, Optional

import yaml

from .document import build_markdown
from .render import (
    render_crosscut_blanks,
    render_crosscut_blanks_primitives,
    render_finished_board,
    render_panel_faces,
    render_panel_faces_legend,
    render_panel_faces_primitives,
    render_panels,
    render_panels_primitives,
    render_slice_map,
    render_strip_map,
    render_strip_map_primitives,
)


def _hashed_name(prefix: str, data: bytes, ext: str = "png") -> str:
    h = hashlib.sha256(data).hexdigest()[:12]
    return f"{prefix}-{h}.{ext}"


def _load(path: str) -> Dict[str, Any]:
    with open(path) as f:
        return yaml.safe_load(f)


@dataclass(frozen=True)
class WriteResult:
    folder: str
    markdown_path: str
    images: Dict[str, str]


def write_document(
    project: Dict[str, Any],
    tool_limits: Dict[str, Any],
    cut_spec: Dict[str, Any],
    out_root: str,
    folder_name: str = "plan",
) -> WriteResult:
    """Render + assemble + write a document folder under ``out_root``.

    The folder is ``out_root/<folder_name>``. If it already exists it
    is overwritten in place: git history, not a side copy, is how an
    old plan is recovered.
    """
    os.makedirs(out_root, exist_ok=True)
    active = os.path.join(out_root, folder_name)

    if os.path.exists(active):
        shutil.rmtree(active)

    os.makedirs(active)
    images_dir = os.path.join(active, "images")
    os.makedirs(images_dir)

    # Render visual sections and write content-hashed images into images/.
    finished = render_finished_board(project)
    slice_map = render_slice_map(project)
    panels = render_panels(project, tool_limits)
    from .derive import panel_specs as _panel_specs
    from collections import Counter as _Counter
    _qty = _Counter(s.panel_id for s in _panel_specs(project, cut_spec, tool_limits))
    panel_faces = render_panel_faces(project, tool_limits, quantities=dict(_qty))
    crosscut = render_crosscut_blanks(project, cut_spec, tool_limits)
    strip_map = render_strip_map(project, cut_spec, tool_limits)

    images = {}
    for key, prefix, data in (
        ("finished", "finished-board", finished),
        ("slice_map", "slice-map", slice_map),
        ("panels", "panels", panels),
        ("panel_faces", "panel-faces", panel_faces),
        ("crosscut", "crosscut-blanks", crosscut),
        ("strip_map", "strip-map", strip_map),
    ):
        fname = _hashed_name(prefix, data)
        with open(os.path.join(images_dir, fname), "wb") as f:
            f.write(data)
        # Markdown references images by their relative path within the folder.
        images[key] = f"images/{fname}"

    # Individual primitives, tracked the same way (content-hashed names
    # in images/). The combined diagrams above are kept as well, so a
    # single-image copy of e.g. the cut diagram can still be requested;
    # the document itself flows the primitives, not the tall combos.
    def _write_prims(prefix, prims):
        out = {}
        for _id, _data in prims.items():
            fname = _hashed_name(f"{prefix}-{_id}", _data)
            with open(os.path.join(images_dir, fname), "wb") as f:
                f.write(_data)
            out[_id] = f"images/{fname}"
        return out

    images["crosscut_prims"] = _write_prims(
        "crosscut", render_crosscut_blanks_primitives(project, cut_spec, tool_limits))
    images["strip_prims"] = _write_prims(
        "strip", render_strip_map_primitives(project, cut_spec, tool_limits))
    images["panel_prims"] = _write_prims(
        "panel", render_panels_primitives(project, tool_limits))
    images["panel_face_prims"] = _write_prims(
        "panel-face", render_panel_faces_primitives(
            project, tool_limits, quantities=dict(_qty)))
    _leg = render_panel_faces_legend(project, tool_limits)
    _leg_name = _hashed_name("panel-faces-legend", _leg)
    with open(os.path.join(images_dir, _leg_name), "wb") as f:
        f.write(_leg)
    images["panel_faces_legend"] = f"images/{_leg_name}"

    md = build_markdown(project, tool_limits, cut_spec, images)
    md_path = os.path.join(active, "README.md")
    with open(md_path, "w") as f:
        f.write(md)

    return WriteResult(folder=active, markdown_path=md_path, images=images)


def run(
    project_path: str,
    tool_limits_path: str,
    cut_spec_path: str,
    out_root: Optional[str] = None,
    folder_name: str = "plan",
) -> WriteResult:
    """File-path entrypoint: load the three YAML docs and write the document.

    ``out_root`` defaults to the directory of the project file given.
    A rerun overwrites the folder in place; git history is the
    recovery path for an old plan.
    """
    if out_root is None:
        out_root = os.path.dirname(os.path.abspath(project_path))
    return write_document(
        _load(project_path),
        _load(tool_limits_path),
        _load(cut_spec_path),
        out_root,
        folder_name,
    )


def _main(argv=None):
    import argparse

    ap = argparse.ArgumentParser(description="board-solver document-writer (Round 2)")
    ap.add_argument("--project", required=True)
    ap.add_argument("--tool-limits", required=True)
    ap.add_argument("--cut-spec", required=True)
    ap.add_argument(
        "--out",
        default=None,
        help="output root directory (default: the project's own directory)",
    )
    ap.add_argument("--name", default="plan", help="active folder name")
    args = ap.parse_args(argv)
    res = run(args.project, args.tool_limits, args.cut_spec, args.out, args.name)
    print(f"wrote {res.markdown_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(_main())
