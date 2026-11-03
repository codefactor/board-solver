"""Shared pytest fixtures.

These are SELF-CONTAINED synthetic specs defined in code — they do NOT load the
committed project/cut-spec/tool-limits files. The committed plaid-v1 specs are
known to be incorrect and will change over time; tests must not depend on them.

The synthetic fixtures are small but exercise the real shapes: a profiled panel
with a maxProfile drop-out, a single-profile panel, a sliceStrips (ripped) panel,
inventory boards plus source/sourceRemainder/buy cut-spec boards, and a sliceGrid.
"""

from __future__ import annotations

import pathlib

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "tests" / "_artifacts"


# --------------------------------------------------------------------------- #
# synthetic tool-limits
# --------------------------------------------------------------------------- #

@pytest.fixture
def tool_limits():
    return {
        "limits": {
            "maxCutLength": [48, 0],
            "sawKerf": [0, 2],
            "miterKerf": [0, 2],
            "maxPlaneWidth": [12, 8],
            "minPlaneThickness": [0, 2],
            "minPlaneLoss": [0, 1],
            "maxMiterCrosscut": [13, 12],
            "maxCutDepth": [2, 2],
            "snipeTail": [1, 8],
        }
    }


# --------------------------------------------------------------------------- #
# synthetic project
#
# Components (all 3/4" thick):
#   A  cherry   3/4"     B  cherry  1 1/2"
#   X  walnut   3/4"     W  walnut  3"
#   M  maple    3/4"     D  maple   1/4"
#
# Panels:
#   P (profiled): seq [M, A, B, A, D] with trailing D maxProfile 1
#                 profiles L:10, R:10  (D present only in L)
#   Q (single-profile): seq [M, X, X] slices 5
#   R (sliceStrips, profiled): seq [M, W, D] trailing D maxProfile 1,
#                 thickness 13/16, ripped 2 x 1/4, profiles L:4, R:4
#
# sliceGrid places: P-L, P-R(flip), Q, R-L, R-R(flip)  (batch 2)
# --------------------------------------------------------------------------- #

@pytest.fixture
def project():
    return {
        "name": "Synth",
        "description": "Synthetic test project.",
        "batch": 2,
        "finishedThickness": [1, 4],
        "sliceDepth": [1, 8],
        "sliceGrid": [
            [{"sliceId": "P-L"}, {"sliceId": "P-R", "flip": "H"}],
            [{"sliceId": "R-L"}, {"sliceId": "R-R", "flip": "H"}],
            [{"sliceId": "P-L"}, {"sliceId": "P-R", "flip": "H"}],
        ],
        "components": [
            {"id": "A", "species": "Cherry", "width": [0, 12], "thickness": [0, 12]},
            {"id": "B", "species": "Cherry", "width": [1, 8], "thickness": [0, 12]},
            {"id": "X", "species": "Walnut", "width": [0, 12], "thickness": [0, 12]},
            {"id": "W", "species": "Walnut", "width": [3, 0], "thickness": [0, 12]},
            {"id": "M", "species": "Brown Maple", "width": [0, 12], "thickness": [0, 12]},
            {"id": "D", "species": "Brown Maple", "width": [0, 4], "thickness": [0, 12]},
        ],
        "panels": [
            {
                "id": "P",
                "thickness": [0, 12],
                "profiles": [{"id": "L", "slices": 10}, {"id": "R", "slices": 10}],
                "components": [
                    {"type": "M"}, {"type": "A"}, {"type": "B"},
                    {"type": "A"}, {"type": "D", "maxProfile": 1},
                ],
            },
            {
                "id": "Q",
                "thickness": [0, 12],
                "slices": 5,
                "components": [{"type": "M"}, {"type": "X"}, {"type": "X"}],
            },
            {
                "id": "R",
                "thickness": [0, 13],
                "sliceStrips": {"count": 2, "width": [0, 4]},
                "profiles": [{"id": "L", "slices": 4}, {"id": "R", "slices": 4}],
                "components": [
                    {"type": "M"}, {"type": "W"}, {"type": "D", "maxProfile": 1},
                ],
            },
        ],
        "boards": [
            {"id": "IC1", "species": "Cherry", "length": [48, 0], "width": [7, 0], "thickness": [0, 13]},
            {"id": "IW1", "species": "Walnut", "length": [40, 0], "width": [6, 0], "thickness": [0, 13]},
            {"id": "IM1", "species": "Brown Maple", "length": [40, 0], "width": [8, 0], "thickness": [0, 13]},
            # An untouched spare (no cut-spec board sources from it).
            {"id": "IM2", "species": "Brown Maple", "length": [30, 0], "width": [6, 0], "thickness": [0, 13]},
        ],
    }


# --------------------------------------------------------------------------- #
# synthetic cut-spec
#
# IC1A: source IC1, 34", strips: B x1 (1 1/2), A x4 (3/4)  cut to 34"
# IW1A: source IW1, 34", strips: W x2 (3), X x2 (3/4)      cut to 34"
# IM1A: source IM1, 34", strips: M x3 (3/4), D x2 (1/4)    cut to 34"
# GHX : buy Walnut, 34", strips: X x2                       cut to 34"
# (lengths chosen <= 48" so no overflow; one buy board for a ghost warning.)
# --------------------------------------------------------------------------- #

@pytest.fixture
def cut_spec():
    def strip(width, *cuts):
        return {"width": width, "cuts": list(cuts)}
    return {
        "boards": [
            {
                "id": "IC1A", "source": "IC1", "length": [34, 0],
                "strips": [
                    strip([1, 8], [34, 0]),
                    strip([0, 12], [34, 0]), strip([0, 12], [34, 0]),
                    strip([0, 12], [34, 0]), strip([0, 12], [34, 0]),
                ],
            },
            {
                "id": "IW1A", "source": "IW1", "length": [34, 0],
                "strips": [
                    strip([3, 0], [34, 0]), strip([3, 0], [34, 0]),
                    strip([0, 12], [34, 0]), strip([0, 12], [34, 0]),
                ],
            },
            {
                "id": "IM1A", "source": "IM1", "length": [34, 0],
                "strips": [
                    strip([0, 12], [34, 0]), strip([0, 12], [34, 0]), strip([0, 12], [34, 0]),
                    strip([0, 4], [34, 0]), strip([0, 4], [34, 0]),
                ],
            },
            {
                "id": "GHX", "buySpecies": "Walnut", "length": [34, 0],
                "strips": [strip([0, 12], [34, 0]), strip([0, 12], [34, 0])],
            },
        ],
    }


@pytest.fixture
def out_dir():
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    return OUT_DIR
