"""Round 2 document-writer process: the runnable output stage.

Reads the three YAML docs, renders the visual sections to content-hashed PNGs,
assembles the Markdown, and writes a self-contained versioned folder. A new run
archives the previous folder instead of overwriting it.

Shared artifact-versioning rules:
  * image filenames carry a content hash (changed bytes => new name; identical
    bytes => reused name),
  * each run writes a fresh versioned folder,
  * the prior folder is archived (moved under an ``archive/`` sibling), never
    clobbered.
"""

from __future__ import annotations

import hashlib
import os
import shutil
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, Optional

import yaml

from .document import build_markdown
from .render import (
    render_crosscut_blanks,
    render_finished_board,
    render_panel_faces,
    render_panels,
    render_slice_map,
    render_strip_map,
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
    archived: Optional[str]


def write_document(
    project: Dict[str, Any],
    tool_limits: Dict[str, Any],
    cut_spec: Dict[str, Any],
    out_root: str,
    folder_name: str = "plan",
    now: Optional[datetime] = None,
    replace: bool = False,
) -> WriteResult:
    """Render + assemble + write a versioned document folder under ``out_root``.

    The active folder is ``out_root/<folder_name>``. If it already exists it is
    moved into ``out_root/archive/<folder_name>-<timestamp>/`` first — unless
    ``replace`` is true, in which case the existing active folder is deleted (a
    one-off overwrite with no archive copy).
    """
    os.makedirs(out_root, exist_ok=True)
    active = os.path.join(out_root, folder_name)

    archived = None
    if os.path.exists(active):
        if replace:
            shutil.rmtree(active)
        else:
            now = now or datetime.now(timezone.utc)
            stamp = now.strftime("%Y%m%dT%H%M%SZ")
            archive_dir = os.path.join(out_root, "archive")
            os.makedirs(archive_dir, exist_ok=True)
            archived = os.path.join(archive_dir, f"{folder_name}-{stamp}")
            # Avoid collision if two runs land in the same second.
            suffix = 0
            base = archived
            while os.path.exists(archived):
                suffix += 1
                archived = f"{base}-{suffix}"
            shutil.move(active, archived)

    os.makedirs(active)
    images_dir = os.path.join(active, "images")
    os.makedirs(images_dir)

    # Render visual sections and write content-hashed images into images/.
    finished = render_finished_board(project)
    slice_map = render_slice_map(project)
    panels = render_panels(project, tool_limits)
    panel_faces = render_panel_faces(project, tool_limits)
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

    md = build_markdown(project, tool_limits, cut_spec, images)
    md_path = os.path.join(active, "README.md")
    with open(md_path, "w") as f:
        f.write(md)

    return WriteResult(folder=active, markdown_path=md_path, images=images, archived=archived)


def run(
    project_path: str,
    tool_limits_path: str,
    cut_spec_path: str,
    out_root: Optional[str] = None,
    folder_name: str = "plan",
    replace: bool = False,
) -> WriteResult:
    """File-path entrypoint: load the three YAML docs and write the document.

    ``out_root`` defaults to the project's own directory, so the generated plan
    lives adjacent to ``project.yaml`` / ``cut-specs.yaml`` (with its ``archive/``
    sibling there too), mirroring the spec's "write in place, archive adjacent"
    rule for the solver's cut-specs output. ``replace`` overwrites the active
    folder without archiving.
    """
    if out_root is None:
        out_root = os.path.dirname(os.path.abspath(project_path))
    return write_document(
        _load(project_path),
        _load(tool_limits_path),
        _load(cut_spec_path),
        out_root,
        folder_name,
        replace=replace,
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
    ap.add_argument("--replace", action="store_true",
                    help="overwrite the active plan folder without archiving")
    args = ap.parse_args(argv)
    res = run(args.project, args.tool_limits, args.cut_spec, args.out, args.name,
              replace=args.replace)
    print(f"wrote {res.markdown_path}")
    if res.archived:
        print(f"archived previous -> {res.archived}")
    return 0


if __name__ == "__main__":
    raise SystemExit(_main())
