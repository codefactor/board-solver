"""Shared pytest fixtures: load the committed YAML specs and expose paths."""

from __future__ import annotations

import os
import pathlib

import pytest
import yaml

ROOT = pathlib.Path(__file__).resolve().parents[1]
SPECS = ROOT / "specs"
PROJECT_DIR = SPECS / "projects" / "plaid-v1"

# Where image-producing tests write PNGs for manual/visual verification.
OUT_DIR = ROOT / "tests" / "_artifacts"


def _load(path: pathlib.Path):
    with open(path) as f:
        return yaml.safe_load(f)


@pytest.fixture(scope="session")
def project():
    return _load(PROJECT_DIR / "project.yaml")


@pytest.fixture(scope="session")
def tool_limits():
    return _load(SPECS / "tool-limits.yaml")


@pytest.fixture(scope="session")
def cut_spec():
    return _load(PROJECT_DIR / "cut-specs.yaml")


@pytest.fixture(scope="session")
def out_dir():
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    return OUT_DIR
