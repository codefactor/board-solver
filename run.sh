#!/usr/bin/env bash
# board-solver task runner. Single entrypoint for tests and plan generation.
#
# Usage:
#   ./run.sh deliver <design> --inventory <inv> [--cut-spec <variant>]
#                                [--what cut-list|strip-map|finished|plan|pdf|all]
#                                [--out=DIR] [--no-save-cut-spec]
#                                Design + inventory + cut-spec -> exactly the
#                                requested output, under
#                                plans/<design>/<inventory>/<cut-spec>/
#                                by default. --out is only an override for
#                                a shelf copy outside the repo.
#   ./run.sh test [pytest args...]        Run the test suite.
#   ./run.sh help | --help | -h           Show this help.
#
# Examples:
#   ./run.sh deliver plaid-v1 --inventory actual --cut-spec hand --what all
#   ./run.sh deliver chess-v1 --inventory hypothetical --what pdf
#   ./run.sh deliver plaid-v1 --inventory actual --what all
#   ./run.sh test
#   ./run.sh test -k geometry

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PY="$ROOT/.venv/bin/python"

if [[ ! -x "$PY" ]]; then
  PY="$(command -v python3 || true)"
  if [[ -z "$PY" ]]; then
    echo "error: no python found (.venv missing and python3 not on PATH)" >&2
    exit 1
  fi
fi

usage() {
  sed -n '2,20p' "${BASH_SOURCE[0]}" | sed 's/^# \{0,1\}//'
}

action="${1:-help}"
shift || true

case "$action" in
  help|--help|-h)
    usage
    ;;

  test)
    cd "$ROOT"
    exec "$PY" -m pytest "$@"
    ;;

  deliver)
    design="${1:-}"
    if [[ -z "$design" ]]; then
      echo "error: 'deliver' needs a design, e.g. ./run.sh deliver plaid-v1 --inventory actual" >&2
      exit 1
    fi
    shift
    cd "$ROOT"
    exec "$PY" -m boardsolver.deliver "$design" --root "$ROOT" "$@"
    ;;

  *)
    echo "error: unknown action '$action'" >&2
    echo >&2
    usage >&2
    exit 1
    ;;
esac
