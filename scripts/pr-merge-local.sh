#!/usr/bin/env bash
# Merge a pull request after testing it locally, while GitHub Actions are
# disabled (docs/local-ci.md).
#
#   scripts/pr-merge-local.sh <core|aligners|app|server|super|web> <pr-number> [--dry-run]
#
# 1. Reads the PR (must be open, against main) and fetches its head.
# 2. Runs `scripts/ci-local.sh <repo> --pr --ref <head sha>`: the checks of a
#    pull_request run, on the merge of the head into origin/main. Skipped where
#    GitHub runs no check either: release-please PRs (author github-actions[bot]
#    or branch release-please--*) and dentalcraft-web (no pull_request workflow).
# 3. gh pr merge <n> --squash --admin --match-head-commit <tested sha>, so the
#    merge fails if the PR moved after the test. --dry-run stops before merging.
#
# After the merge, run `scripts/ci-local.sh <repo> --ref origin/main` (the push
# run on main) and then `scripts/release-local.sh <repo>`.
set -euo pipefail

ROOT=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
# The public repositories live under the maintainer's account; only the closed
# dentalcraft-server stays in the private organisation.
OWNER=dnviti
ORG=dnviti-personal-org

usage() { sed -n '2,17p' "${BASH_SOURCE[0]}" | sed 's/^# \{0,1\}//' >&2; exit 2; }
die() { printf 'error: %s\n' "$*" >&2; exit 1; }

repo=${1:-} n=${2:-} dry=0
[ -n "$repo" ] && [ -n "$n" ] || usage
case "${3:-}" in '') ;; --dry-run) dry=1 ;; *) usage ;; esac
[ $# -le 3 ] || usage
[[ "$n" =~ ^[0-9]+$ ]] || usage
case "$repo" in
  super) name=dentalcraft; dir=$ROOT ;;
  core|aligners|app|server|web) name=dentalcraft-$repo; dir=$ROOT/dentalcraft-$repo ;;
  *) usage ;;
esac
case "$repo" in
  server) R="$ORG/$name" ;;
  *) R="$OWNER/$name" ;;
esac

IFS=$'\t' read -r state base head_ref head_sha author is_bot cross title < <(
  gh pr view "$n" -R "$R" --json state,baseRefName,headRefName,headRefOid,author,isCrossRepository,title \
    --jq '[.state, .baseRefName, .headRefName, .headRefOid, .author.login, (.author.is_bot // false), .isCrossRepository, .title] | @tsv') \
  || die "cannot read PR $R#$n"
printf 'PR %s#%s "%s"\n  %s -> %s, head %s, author %s, state %s\n' "$R" "$n" "$title" "$head_ref" "$base" "$head_sha" "$author" "$state"
[ "$state" = OPEN ] || die "PR $n is $state"
[ "$base" = main ] || die "PR $n targets $base: ci-local --pr tests merges into origin/main only"
[ "$cross" = false ] || echo "note: the head comes from a fork"

# Read-only: what --admin would bypass on main (the free plan has neither
# branch protection nor rulesets on private repositories: the API answers 403).
if prot=$(gh api "repos/$R/branches/main/protection" --jq '.required_status_checks.contexts // [] | join(",")' 2>/dev/null); then
  echo "branch protection on main: required checks [${prot}] (bypassed by --admin)"
else
  echo "branch protection on main: none readable (403/404); --admin bypasses nothing"
fi

skip=
case "$head_ref" in release-please--*) skip="release-please branch $head_ref" ;; esac
if [ "$is_bot" = true ] || [ "$author" = app/github-actions ] || [ "$author" = github-actions ]; then
  skip="authored by $author"
fi
[ "$repo" = web ] && skip="dentalcraft-web has no pull_request workflow"

git -C "$dir" fetch -q origin "pull/$n/head"
fetched=$(git -C "$dir" rev-parse FETCH_HEAD)
[ "$fetched" = "$head_sha" ] || die "fetched head $fetched differs from the PR head $head_sha: retry"

if [ -n "$skip" ]; then
  echo "no CI for this PR on GitHub ($skip): skipping ci-local"
else
  "$ROOT/scripts/ci-local.sh" "$repo" --pr --ref "$head_sha"
fi

if [ "$dry" = 1 ]; then
  echo "dry run: would run gh pr merge $n -R $R --squash --admin --match-head-commit $head_sha"
  exit 0
fi
gh pr merge "$n" -R "$R" --squash --admin --match-head-commit "$head_sha"
echo "merged. Next: scripts/ci-local.sh $repo --ref origin/main, then scripts/release-local.sh $repo (not for web/super)"
