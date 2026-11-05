"""Checklist Initial crosscuts: compact diagram just before the table."""

import os

from boardsolver.cutcheck import build_md


def test_crosscut_diagram_before_initial_crosscuts_table(project, cut_spec, tool_limits, tmp_path):
    md_path = build_md(project, cut_spec, tool_limits, str(tmp_path),
                       "test", "actual", "solver")
    md = open(md_path).read()
    assert "![Crosscut Diagram](images/crosscut-compact-" in md
    diagram_pos = md.index("![Crosscut Diagram]")
    table_pos = md.index("| [ ] | Raw board | Species | Blank | Length | Off Cut |")
    assert diagram_pos < table_pos
    # The diagram file exists in the checklist images folder.
    name = md[diagram_pos:].split("images/")[1].split(")")[0]
    assert os.path.exists(tmp_path / "images" / name)
