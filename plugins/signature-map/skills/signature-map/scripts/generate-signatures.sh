#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SRC_DIR="${SCRIPT_DIR}/sigmapgen"
BIN_DIR="${SCRIPT_DIR}/.bin"
BIN_PATH="${BIN_DIR}/sigmapgen"

GO_BIN="${GO_BIN:-$(command -v go || true)}"
SKIP_BUILD="${SIGMAP_SKIP_GO_BUILD:-0}"

cleanup_jobs() {
  local pids
  pids="$(jobs -pr || true)"
  if [[ -n "${pids}" ]]; then
    # Best-effort cleanup for interrupted runs.
    kill ${pids} 2>/dev/null || true
  fi
}
trap cleanup_jobs EXIT INT TERM

fail() {
  echo "ERROR: $*" >&2
  exit 3
}

need_rebuild() {
  if [[ ! -x "${BIN_PATH}" ]]; then
    return 0
  fi
  while IFS= read -r src; do
    if [[ "${src}" -nt "${BIN_PATH}" ]]; then
      return 0
    fi
  done < <(find "${SRC_DIR}" -type f -name '*.go' -print)
  return 1
}

build_generator() {
  [[ -x "${GO_BIN}" ]] || fail "go compiler not found; install Go or set GO_BIN"
  mkdir -p "${BIN_DIR}"
  GO111MODULE=off "${GO_BIN}" build -trimpath -ldflags="-s -w" -o "${BIN_PATH}" "${SRC_DIR}/main.go" \
    || fail "failed to build sigmap Go generator"
}

if [[ "${SKIP_BUILD}" != "1" ]]; then
  if need_rebuild; then
    build_generator
  fi
elif [[ ! -x "${BIN_PATH}" ]]; then
  fail "SIGMAP_SKIP_GO_BUILD=1 but binary missing: ${BIN_PATH}"
fi

exec "${BIN_PATH}" "$@"
