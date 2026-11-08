#!/usr/bin/env bash
# Local replica of the GitHub Actions CI of the dentalcraft repositories, used
# while Actions are disabled (docs/local-ci.md). The workflow files under
# .github/ stay the source of truth: keep this script in step with them.
#
#   scripts/ci-local.sh <core|aligners|app|server|super|all> [--ref <git-ref>] [--pr]
#   scripts/ci-local.sh clean
#
#   core|aligners|app  dentalcraft-<repo>/.github/workflows/ci.yml
#   server             dentalcraft-server/.github/workflows/ci.yml
#   super              .github/workflows/submodules.yml (superproject)
#   all                super, core, aligners, app, server; stops at the first failure
#   --ref <git-ref>    commit to test (default: HEAD of the repository, which must be clean)
#   --pr               test the merge of the ref into origin/main, like the
#                      refs/pull/N/merge checkout of a pull_request run
#   clean              remove the cache (~/.cache/dentalcraft-ci)
#
# The commit is checked out into ~/.cache/dentalcraft-ci/<repo>/src, outside
# the superproject, so its .cargo/config.toml [patch] does not apply and the
# dependencies resolve to the pinned git tags, as on the runner. The target/
# directory there persists between runs (it stands in for Swatinem/rust-cache).
# A passing run of a plain ref (not --pr) records
# ~/.cache/dentalcraft-ci/<repo>/passed/<sha>: scripts/release-local.sh
# requires it for the commit it releases.
# The job steps are scripts in single quotes, expanded by the step shell (SC2016).
# shellcheck disable=SC2016
set -euo pipefail

ROOT=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
CACHE=${DC_CI_CACHE:-$HOME/.cache/dentalcraft-ci}
ORG=dnviti-personal-org
# ci.yml: dtolnay/rust-toolchain@stable with toolchain: 1.99.1, components: rustfmt, clippy
RUST_TOOLCHAIN=1.99.1
# ci.yml "Use SSH for private dentalcraft repositories": GitHub's published ed25519 host key
GITHUB_HOST_KEY='github.com ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIOMqqnkVzrm0SdG6UOoqKLsabgH5C9okWi0dh2l9GKJl'
export PATH="$HOME/.cargo/bin:$PATH"

usage() { sed -n '2,24p' "${BASH_SOURCE[0]}" | sed 's/^# \{0,1\}//' >&2; exit 2; }
die() { printf '##[error]%s\n' "$*" >&2; exit 1; }

repo_dir() {
  case "$1" in
    super) printf '%s\n' "$ROOT" ;;
    core|aligners|app|server) printf '%s\n' "$ROOT/dentalcraft-$1" ;;
    *) return 1 ;;
  esac
}

# A `run:` step: GitHub runs it with `bash --noprofile --norc -eo pipefail {0}`.
run_step() {
  local name=$1 script=$2 t0=$SECONDS rc=0
  printf '\n##[group]%s\n' "$name"
  printf '%s\n' "$script" | sed 's/^/  | /'
  printf '##[endgroup]\n'
  bash --noprofile --norc -eo pipefail -c "$script" || rc=$?
  if [ "$rc" -ne 0 ]; then
    printf '##[error]Step "%s" failed with exit code %s (%ss)\n' "$name" "$rc" "$((SECONDS - t0))"
    return "$rc"
  fi
  printf -- '--> %s: ok (%ss)\n' "$name" "$((SECONDS - t0))"
}

# actions/checkout: a clean tree of one commit (or of the PR merge commit).
# Sets SRC, HEAD_SHA, BASE_SHA (empty without --pr) and TESTED_SHA.
checkout() {
  local repo=$1 ref=$2 pr=$3 dir status_args=()
  dir=$(repo_dir "$repo")
  [ "$repo" = super ] && status_args=(--ignore-submodules=all)
  if [ -z "$ref" ]; then
    if [ -n "$(git -C "$dir" status --porcelain "${status_args[@]}")" ]; then
      git -C "$dir" status --short "${status_args[@]}" >&2
      die "$dir has uncommitted changes. CI tests a committed ref: commit them, or pass --ref <ref> to test a committed ref anyway."
    fi
    ref=HEAD
  fi
  case "$ref" in origin/*) git -C "$dir" fetch -q origin ;; esac
  HEAD_SHA=$(git -C "$dir" rev-parse --verify -q "$ref^{commit}") || die "unknown ref '$ref' in $dir"
  SRC=$CACHE/$repo/src
  mkdir -p "$SRC"
  [ -d "$SRC/.git" ] || git init -q "$SRC"
  git -C "$SRC" fetch -q --no-tags "$dir" "$HEAD_SHA"
  BASE_SHA=
  if [ "$pr" = 1 ]; then
    git -C "$dir" fetch -q origin main
    BASE_SHA=$(git -C "$dir" rev-parse --verify origin/main)
    git -C "$SRC" fetch -q --no-tags "$dir" "$BASE_SHA"
    git -C "$SRC" checkout -q --force --detach "$BASE_SHA"
    git -C "$SRC" clean -ffdxq -e /target
    if ! GIT_AUTHOR_NAME=ci-local GIT_AUTHOR_EMAIL=ci-local@localhost \
        GIT_COMMITTER_NAME=ci-local GIT_COMMITTER_EMAIL=ci-local@localhost \
        git -C "$SRC" merge -q --no-ff --no-edit -m "Merge $HEAD_SHA into $BASE_SHA" "$HEAD_SHA"; then
      git -C "$SRC" merge --abort || true
      die "$ref ($HEAD_SHA) does not merge cleanly into origin/main ($BASE_SHA): GitHub would not build a merge ref either. Rebase it."
    fi
    TESTED_SHA=$(git -C "$SRC" rev-parse HEAD)
  else
    git -C "$SRC" checkout -q --force --detach "$HEAD_SHA"
    git -C "$SRC" clean -ffdxq -e /target
    TESTED_SHA=$HEAD_SHA
  fi
  printf '##[group]Checkout\n  repository: %s\n  ref:        %s\n  commit:     %s\n' \
    "$(basename "$dir")" "$ref" "$HEAD_SHA"
  [ -n "$BASE_SHA" ] && printf '  merged into origin/main %s -> %s\n' "$BASE_SHA" "$TESTED_SHA"
  printf '  path:       %s\n##[endgroup]\n' "$SRC"
}

# Environment of a fresh runner pod: drop the variables of this shell that
# change cargo, rustc or git behaviour, and refuse cargo configs that the
# runner would not see.
clean_env() {
  local v
  for v in $(compgen -e); do
    case "$v" in
      RUSTUP_HOME) ;;
      CARGO_*|RUST*|GIT_CONFIG*|GO*|CGO_*) unset "$v" ;;
    esac
  done
  export CARGO_HOME=$CACHE/cargo-home
  mkdir -p "$CARGO_HOME"
  local dir=$SRC f
  while :; do
    for f in "$dir/.cargo/config" "$dir/.cargo/config.toml" "$CARGO_HOME/config" "$CARGO_HOME/config.toml"; do
      [ -e "$f" ] && die "cargo config $f would apply to this build but not on the runner: move it away or set DC_CI_CACHE elsewhere"
    done
    [ "$dir" = / ] && break
    dir=$(dirname "$dir")
  done
  return 0
}

# webfactory/ssh-agent + "Use SSH for private dentalcraft repositories", without
# touching ~/.gitconfig or ~/.ssh: the insteadOf mapping and the pinned host key
# only live in this process environment. The user's ssh agent stands in for the
# deploy keys.
ssh_env() {
  printf '%s\n' "$GITHUB_HOST_KEY" > "$CACHE/known_hosts"
  export GIT_CONFIG_COUNT=1
  export GIT_CONFIG_KEY_0="url.git@github.com:$ORG/.insteadOf"
  export GIT_CONFIG_VALUE_0="https://github.com/$ORG/"
  export GIT_SSH_COMMAND="ssh -o BatchMode=yes -o StrictHostKeyChecking=yes -o UserKnownHostsFile=$CACHE/known_hosts"
  [ -n "${SSH_AUTH_SOCK:-}" ] || die "no ssh agent (SSH_AUTH_SOCK): the private dependencies are fetched over SSH"
  printf '\n##[group]Use SSH for private dentalcraft repositories (process-scoped)\n'
  printf '  GIT_CONFIG_KEY_0=%s\n  GIT_CONFIG_VALUE_0=%s\n  known_hosts: %s\n##[endgroup]\n' \
    "$GIT_CONFIG_KEY_0" "$GIT_CONFIG_VALUE_0" "$CACHE/known_hosts"
}

c_toolchain_step() {
  # The runner installs gcc when `cc` is missing; here it must already be there.
  run_step "Install C toolchain" 'command -v cc >/dev/null || { echo "no cc: install gcc (sudo dnf install gcc make pkgconf-pkg-config)" >&2; exit 1; }
cc --version | head -n 1'
}

job_rust() {
  local repo=$1
  clean_env
  # dtolnay/rust-toolchain exports these two when unset (the other variables it
  # may set only apply to toolchains older than 1.72).
  export CARGO_INCREMENTAL=0 CARGO_TERM_COLOR=always
  case "$repo" in
    aligners|app) export CARGO_NET_GIT_FETCH_WITH_CLI=true ;;   # ci.yml job env
  esac
  cd "$SRC"
  c_toolchain_step
  [ -f Cargo.toml ] || { echo "no Cargo.toml: the remaining steps are skipped, as on the runner"; return 0; }
  case "$repo" in aligners|app) ssh_env ;; esac
  run_step "Install Rust $RUST_TOOLCHAIN" "rustup toolchain list | grep -q '^$RUST_TOOLCHAIN-' || rustup toolchain install $RUST_TOOLCHAIN --profile minimal --component rustfmt,clippy --no-self-update
rustup component add --toolchain $RUST_TOOLCHAIN rustfmt clippy
rustc --version --verbose"
  printf '\n--> Cache cargo: CARGO_HOME=%s, target dir %s/target (persistent)\n' "$CARGO_HOME" "$SRC"
  run_step "Format" 'cargo fmt --all --check'
  run_step "Clippy" 'cargo clippy --workspace --all-targets -- -D warnings'
  if [ "$repo" = aligners ]; then
    # Step env of "Tests"; it is the last step, so exporting it is step-scoped.
    export CARGO_PROFILE_RELEASE_DEBUG_ASSERTIONS=true CARGO_PROFILE_RELEASE_OVERFLOW_CHECKS=true
    run_step "Tests (env CARGO_PROFILE_RELEASE_DEBUG_ASSERTIONS=true CARGO_PROFILE_RELEASE_OVERFLOW_CHECKS=true)" 'cargo test --workspace --release'
  else
    run_step "Tests" 'cargo test --workspace'
  fi
}

# actions/setup-go with go-version-file: go.mod (toolchain directive first, then go).
# A major.minor version resolves to its latest patch release, as setup-go does.
go_version_of() {
  local v
  v=$(sed -n 's/^toolchain go\([0-9][0-9.a-z]*\)$/\1/p' go.mod | head -n 1)
  [ -n "$v" ] || v=$(sed -n 's/^go \([0-9][0-9.a-z]*\)$/\1/p' go.mod | head -n 1)
  [ -n "$v" ] || return 1
  if [[ "$v" =~ ^[0-9]+\.[0-9]+$ ]]; then
    v=$(curl -fsS 'https://go.dev/dl/?mode=json&include=all' \
      | jq -r --arg p "go$v." '[.[] | select(.stable) | .version | select(startswith($p))][0] | ltrimstr("go")')
  fi
  printf '%s\n' "$v"
}

job_go() {
  local ver
  clean_env
  cd "$SRC"
  c_toolchain_step
  [ -f go.mod ] || { echo "no go.mod: the remaining steps are skipped, as on the runner"; return 0; }
  ver=$(go_version_of) || die "no go version in go.mod"
  # The exact release, downloaded by the go command into the cache GOPATH.
  export GOTOOLCHAIN="go$ver" GOPATH=$CACHE/go GOCACHE=$CACHE/go-build
  run_step "Setup Go $ver" 'go version'
  PATH="$(go env GOROOT)/bin:$PATH"
  export PATH
  run_step "Go environment" 'command -v go gofmt; go version; go env GOROOT GOTOOLCHAIN GOEXPERIMENT GOFLAGS'
  run_step "Format" 'test -z "$(gofmt -l .)"'
  run_step "Vet" 'go vet ./...'
  export CGO_ENABLED=1   # step env of "Tests", the last step
  run_step "Tests (env CGO_ENABLED=1)" 'go test -race -count=1 ./...'
}

job_super() {
  cd "$SRC"
  # Verbatim from .github/workflows/submodules.yml
  run_step "Relative URLs and branch main" 'set -eu
names=$(git config -f .gitmodules --name-only --get-regexp '"'"'^submodule\..*\.path$'"'"' | sed -e '"'"'s/^submodule\.//'"'"' -e '"'"'s/\.path$//'"'"')
test -n "$names"
for n in $names; do
  url=$(git config -f .gitmodules "submodule.$n.url")
  branch=$(git config -f .gitmodules "submodule.$n.branch" || true)
  case "$url" in
    ../*.git) ;;
    *) echo "non-relative URL for $n: $url" >&2; exit 1 ;;
  esac
  test "$branch" = "main" || { echo "branch is not main for $n: '"'"'$branch'"'"'" >&2; exit 1; }
  echo "ok: $n -> $url ($branch)"
done'
  run_step "Every submodule is registered in the index" 'set -eu
for p in $(git config -f .gitmodules --get-regexp '"'"'\.path$'"'"' | awk '"'"'{print $2}'"'"'); do
  mode=$(git ls-files -s -- "$p" | awk '"'"'{print $1}'"'"')
  test "$mode" = "160000" || { echo "$p is not a submodule (gitlink) in the index" >&2; exit 1; }
  echo "ok: $p"
done'
}

# One repository, in a subshell so that the environment changes stay there.
run_repo() (
  set -e
  repo=$1 ref=$2 pr=$3 t0=$SECONDS
  printf '\n========== %s ==========\n' "$repo"
  checkout "$repo" "$ref" "$pr"
  case "$repo" in
    super) job_super ;;
    core|aligners|app) job_rust "$repo" ;;
    server) job_go ;;
  esac
  if [ "$pr" = 0 ]; then
    mkdir -p "$CACHE/$repo/passed"
    printf 'ci-local passed %s ref=%s duration=%ss\n' "$(date -Is)" "${ref:-HEAD}" "$((SECONDS - t0))" \
      > "$CACHE/$repo/passed/$TESTED_SHA"
  fi
  printf '\n%s: passed on %s (%ss)\n' "$repo" "$TESTED_SHA" "$((SECONDS - t0))"
)

clean_cache() {
  [ -d "$CACHE" ] || { echo "nothing to clean: $CACHE does not exist"; return 0; }
  # The Go module cache is read-only on disk.
  [ -d "$CACHE/go" ] && chmod -R u+w "$CACHE/go"
  rm -rf -- "$CACHE"
  echo "removed $CACHE"
}

main() {
  local target=${1:-} ref='' pr=0
  [ -n "$target" ] || usage
  shift
  if [ "$target" = clean ]; then
    [ $# -eq 0 ] || usage
    clean_cache
    return 0
  fi
  while [ $# -gt 0 ]; do
    case "$1" in
      --ref) [ $# -ge 2 ] || usage; ref=$2; shift 2 ;;
      --pr) pr=1; shift ;;
      *) usage ;;
    esac
  done
  local repos
  case "$target" in
    all) repos=(super core aligners app server) ;;
    super|core|aligners|app|server) repos=("$target") ;;
    *) usage ;;
  esac
  mkdir -p "$CACHE"
  local r t0 rc=0 results=() failed=0
  for r in "${repos[@]}"; do
    t0=$SECONDS
    # Not in an `if` or `||` list: errexit must stay on inside the job.
    set +e
    run_repo "$r" "$ref" "$pr"
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

# Sourced by release-local.sh for the shared helpers; run main only when executed.
if [ "${BASH_SOURCE[0]}" = "$0" ]; then
  main "$@"
fi
