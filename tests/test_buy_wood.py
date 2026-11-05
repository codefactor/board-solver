"""Buy Wood phase data: ghost boards only, in cut-spec order.

Synthetic only (tests must stay decoupled from production specs):
a ghost board is a cut-spec board whose rip is buy_required; an
inventory board with buy_required False never appears, and a
project with no ghost boards yields no Buy Wood rows at all, so
the phase is omitted.
"""

from boardsolver.cutcheck import _buy_board_rows
from boardsolver.derive import BoardRip


def _rip(board_id, species, buy_required):
    return BoardRip(
        id=board_id, origin=f"buy:{species}" if buy_required else f"source:{board_id}",
        species=species, buy_required=buy_required, length=622,
        source_width=15, used=12, loss=3, margin=0, strips=[])


def _data():
    ghost = {"id": "GH-C", "buySpecies": "Cherry", "length": [38, 14],
             "strips": [{"width": [0, 12], "cuts": [[19, 6], [19, 6]]}]}
    inv = {"id": "BC1A", "source": "BC1", "length": [38, 14],
           "strips": [{"width": [0, 12], "cuts": [[19, 6]]}]}
    return {
        "boards": [inv, ghost],
        "rips": {"BC1A": _rip("BC1A", "Cherry", False),
                 "GH-C": _rip("GH-C", "Cherry", True)},
    }


def _project():
    return {"boards": [{"id": "BC1", "species": "Cherry", "thickness": [0, 13]}]}


def test_buy_wood_rows_only_ghost_boards():
    rows = _buy_board_rows(_project(), _data())
    assert [r["id"] for r in rows] == ["GH-C"]
    row = rows[0]
    assert row["species"] == "Cherry"
    assert row["length"] == 622
    assert row["width"] == 15
    assert row["thickness"] == 13
    assert row["yields"] == "¾″ → 19⅜″x2"


def test_buy_wood_rows_empty_without_ghosts():
    data = _data()
    data["boards"] = [b for b in data["boards"] if b["id"] != "GH-C"]
    del data["rips"]["GH-C"]
    assert _buy_board_rows(_project(), data) == []
