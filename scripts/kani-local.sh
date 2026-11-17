#!/usr/bin/env bash
# Kani bounded model checking of the Rust repositories (docs/kani.md). This
# is not part of the runner CI: ci-local.sh stays an exact replica of the
# workflows, and the proof harnesses live behind #[cfg(kani)], so builds,
# clippy and tests on the runner never see them.
#
#   scripts/kani-local.sh <core|aligners|app|all> [--ref <git-ref>] [--dev] [-- <cargo kani args>]
#
#   core|aligners|app  run every #[kani::proof] harness of that workspace
#   all                core, aligners, app; stops at the first failure
#   --ref <git-ref>    commit to verify (default: HEAD, which must be clean)
#   --dev              verify the working tree inside the superproject instead,
#                      with the .cargo/config.toml [patch]; Cargo.lock is
#                      restored afterwards. No pass marker.
#   -- <args>          passed to `cargo kani`, e.g. -- --harness save_roundtrip
#
# Without --dev the commit is checked out like ci-local.sh does (same cache,
# same clean environment, dependencies from the pinned git tags) and a pass
# writes ~/.cache/dentalcraft-ci/<repo>/kani-passed/<sha>.
# CBMC can eat all the RAM on a badly bounded harness: every run is capped at
# DC_KANI_MEM (default 16G, no swap) through a transient systemd user scope.
set -euo pipefail

KANI_ROOT=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
# shellcheck source=scripts/ci-local.sh
. "$KANI_ROOT/scripts/ci-local.sh"

kani_usage() { sed -n '2,20p' "${BASH_SOURCE[0]}" | sed 's/^# \{0,1\}//' >&2; exit 2; }

kani_check_installed() {
  command -v cargo-kani >/dev/null ||
    die "cargo-kani not found: cargo install --locked kani-verifier && cargo kani setup"
}

# cargo kani under the memory cap; the scope keeps this environment.
KANI_MEM=${DC_KANI_MEM:-16G}
kani_cmd() {
  local args=''
  [ $# -eq 0 ] || args=$(printf '%q ' "$@")
  printf 'systemd-run --user --scope --quiet -p MemoryMax=%s -p MemorySwapMax=0 cargo kani --workspace %s' \
    "$KANI_MEM" "$args"
}

# Committed ref, clean checkout, pinned dependencies (ci-local.sh helpers).
kani_repo_ref() (
  set -e
  repo=$1 ref=$2 t0=$SECONDS
  shift 2
  printf '\n========== kani %s ==========\n' "$repo"
  checkout "$repo" "$ref" 0
  clean_env
  export CARGO_TERM_COLOR=always
  case "$repo" in
    aligners|app) export CARGO_NET_GIT_FETCH_WITH_CLI=true; ssh_env ;;
  esac
  cd "$SRC"
  run_step "cargo kani --workspace $* (MemoryMax=$KANI_MEM)" "$(kani_cmd "$@")"
  mkdir -p "$CACHE/$repo/kani-passed"
  printf 'kani-local passed %s ref=%s duration=%ss\n' "$(date -Is)" "${ref:-HEAD}" "$((SECONDS - t0))" \
    > "$CACHE/$repo/kani-passed/$TESTED_SHA"
  printf '\nkani %s: passed on %s (%ss)\n' "$repo" "$TESTED_SHA" "$((SECONDS - t0))"
)

# Working tree inside the superproject ([patch] applies); Cargo.lock restored.
kani_repo_dev() (
  set -e
  repo=$1 t0=$SECONDS
  shift
  dir=$(repo_dir "$repo")
  printf '\n========== kani %s (working tree) ==========\n' "$repo"
  lock=$(mktemp)
  cp "$dir/Cargo.lock" "$lock"
  trap 'cp "$lock" "$dir/Cargo.lock"; rm -f "$lock"' EXIT
  cd "$dir"
  run_step "cargo kani --workspace $* (MemoryMax=$KANI_MEM)" "$(kani_cmd "$@")"
  printf '\nkani %s: passed on the working tree (%ss)\n' "$repo" "$((SECONDS - t0))"
)

kani_main() {
  local target=${1:-} ref='' dev=0 extra=()
  [ -n "$target" ] || kani_usage
  shift
  while [ $# -gt 0 ]; do
    case "$1" in
      --ref) [ $# -ge 2 ] || kani_usage; ref=$2; shift 2 ;;
      --dev) dev=1; shift ;;
      --) shift; extra=("$@"); break ;;
      *) kani_usage ;;
    esac
  done
  [ "$dev" = 1 ] && [ -n "$ref" ] && die "--dev verifies the working tree: it does not take --ref"
  local repos
  case "$target" in
    all) repos=(core aligners app) ;;
    core|aligners|app) repos=("$target") ;;
    *) kani_usage ;;
  esac
  kani_check_installed
  mkdir -p "$CACHE"
  local r t0 rc=0 results=() failed=0
  for r in "${repos[@]}"; do
    t0=$SECONDS
    set +e
    if [ "$dev" = 1 ]; then
      kani_repo_dev "$r" "${extra[@]}"
    else
      kani_repo_ref "$r" "$ref" "${extra[@]}"
    fi
    rc=$?
    set -e
    if [ "$rc" = 0 ]; then
      results+=("$r	pass	$((SECONDS - t0))s")
    else
      results+=("$r	FAIL	$((SECONDS - t0))s")
      failed=1
      break
    fi
  done
  printf '\n%-10s %-6s %s\n' REPO RESULT DURATION
  for r in "${results[@]}"; do
    IFS=$'\t' read -r a b c <<<"$r"
    printf '%-10s %-6s %s\n' "$a" "$b" "$c"
  done
  [ "$failed" = 0 ] || return "$rc"
}

kani_main "$@"
