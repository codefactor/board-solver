#!/usr/bin/env bash
# board-solver task runner. Single entrypoint for tests and plan generation.
#
# Usage:
#   ./run.sh <action> [args...]
#
# Actions:
#   plan <project> [--replace]   Generate the plan document for a project under
#                                specs/projects/<project>/. Writes a versioned
#                                plan/ folder (README.md + images/) and archives
#                                the previous one. With --replace, overwrite the
#                                active plan/ in place WITHOUT archiving.
#   solve <project> [--out=PATH] Run the greedy solver (Round 3): writes
#                                cut-specs.yaml (default: the project's own,
#                                or --out=PATH for a test copy).
#   test [pytest args...]        Run the test suite.
#   help | --help | -h           Show this help.
#
# Examples:
#   ./run.sh plan plaid-v1
#   ./run.sh plan plaid-v1 --replace
#   ./run.sh solve plaid-v1
#   ./run.sh test
#   ./run.sh test -k geometry

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PY="$ROOT/.venv/bin/python"
SPECS="$ROOT/specs"
TOOL_LIMITS="$SPECS/tool-limits.yaml"

if [[ ! -x "$PY" ]]; then
  PY="$(command -v python3 || true)"
  if [[ -z "$PY" ]]; then
    echo "error: no python found (.venv missing and python3 not on PATH)" >&2
    exit 1
  fi
fi

usage() {
  sed -n '2,23p' "${BASH_SOURCE[0]}" | sed 's/^# \{0,1\}//'
}

project_dir() {
  local proj="$1"
  local dir="$SPECS/projects/$proj"
  if [[ ! -d "$dir" ]]; then
    echo "error: no project '$proj' at $dir" >&2
    echo "available projects:" >&2
    ls -1 "$SPECS/projects" 2>/dev/null | sed 's/^/  /' >&2
    exit 1
  fi
  echo "$dir"
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

  plan)
    proj="${1:-}"
    if [[ -z "$proj" ]]; then
      echo "error: 'plan' needs a project, e.g. ./run.sh plan plaid-v1" >&2
      exit 1
    fi
    shift
    replace=""
    for arg in "$@"; do
      case "$arg" in
        --replace) replace="--replace" ;;
        *) echo "error: unknown option for plan: $arg" >&2; exit 1 ;;
      esac
    done
    dir="$(project_dir "$proj")"
    cd "$ROOT"
    exec "$PY" -m boardsolver.docwriter \
      --project "$dir/project.yaml" \
      --tool-limits "$TOOL_LIMITS" \
      --cut-spec "$dir/cut-specs.yaml" \
      $replace
    ;;

  solve)
    proj="${1:-}"
    if [[ -z "$proj" ]]; then
      echo "error: 'solve' needs a project, e.g. ./run.sh solve plaid-v1" >&2
      exit 1
    fi
    shift
    out=""
    for arg in "$@"; do
      case "$arg" in
        --out=*) out="${arg#--out=}" ;;
        *) echo "error: unknown option for solve: $arg" >&2; exit 1 ;;
      esac
    done
    dir="$(project_dir "$proj")"
    if [[ -z "$out" ]]; then
      out="$dir/cut-specs.yaml"
    fi
    cd "$ROOT"
    exec "$PY" -m boardsolver.solver \
      --project "$dir/project.yaml" \
      --tool-limits "$TOOL_LIMITS" \
      --out "$out"
    ;;

  *)
    echo "error: unknown action '$action'" >&2
    echo >&2
    usage >&2
    exit 1
    ;;
esac
