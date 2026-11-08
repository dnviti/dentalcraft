#!/usr/bin/env bash
# GitHub Actions switch of the dentalcraft repositories (docs/local-ci.md),
# against the original state recorded in scripts/actions-state.tsv.
#
#   scripts/actions-status.sh status            current state (read-only)
#   scripts/actions-status.sh on  [--dry-run]   restore each repository to its
#                                               original state (Actions enabled)
#   scripts/actions-status.sh off [--dry-run]   cancel queued runs, then switch
#                                               Actions off at repository level
#
# Only the repository-level switch changes (actions/permissions enabled); the
# workflow files and their per-workflow state are never touched. `on`/`off`
# need admin access to the repositories through `gh`.
set -euo pipefail

ORG=dnviti-personal-org
LIST="$(dirname "${BASH_SOURCE[0]}")/actions-state.tsv"

usage() { sed -n '2,13p' "${BASH_SOURCE[0]}" | sed 's/^# \{0,1\}//' >&2; exit 2; }

mode=${1:-}
dry=0
case "${2:-}" in
  '') ;;
  --dry-run) dry=1 ;;
  *) usage ;;
esac
[ $# -le 2 ] || usage
case "$mode" in on|off|status) ;; *) usage ;; esac
[ "$mode" = status ] && [ "$dry" = 1 ] && usage

run() {
  if [ "$dry" = 1 ]; then
    printf '  dry-run: %s\n' "$*"
  else
    "$@"
  fi
}

enabled_of() { gh api "repos/$ORG/$1/actions/permissions" --jq .enabled; }
workflows_of() {
  gh api "repos/$ORG/$1/actions/workflows" --jq '[.workflows[] | select(.state != "active") | "\(.path)=\(.state)"] | if length == 0 then "all active" else join(" ") end'
}
last_run_of() {
  gh api "repos/$ORG/$1/actions/runs?per_page=1" --jq '.workflow_runs[0] | if . == null then "-" else "\(.created_at) \(.name) \(.conclusion // .status)" end'
}

# Runs still waiting to start (not those already running), as the hosting platform's toggle does.
cancel_queued() {
  local repo=$1 st rid
  for st in queued pending waiting requested; do
    for rid in $(gh api --paginate "repos/$ORG/$repo/actions/runs?status=$st&per_page=100" --jq '.workflow_runs[].id'); do
      echo "  cancelling run $rid ($st)"
      run gh run cancel "$rid" -R "$ORG/$repo"
    done
  done
}

if [ "$mode" = status ]; then
  printf '%-22s %-9s %-9s %-20s %s\n' REPO ORIGINAL ENABLED WORKFLOWS LAST_RUN
else
  printf '%-22s %-9s %-9s %-9s %-20s %s\n' REPO ORIGINAL BEFORE AFTER WORKFLOWS LAST_RUN
fi
while IFS=$'\t' read -r repo orig _; do
  case "$repo" in ''|'#'*) continue ;; esac
  before=$(enabled_of "$repo")
  case "$mode" in
    status) want=$before ;;
    on) want=$orig ;;
    off) want=false ;;
  esac
  if [ "$before" != "$want" ]; then
    [ "$want" = false ] && cancel_queued "$repo"
    run gh api -X PUT "repos/$ORG/$repo/actions/permissions" -F "enabled=$want" --silent
  fi
  if [ "$mode" = status ]; then
    printf '%-22s %-9s %-9s %-20s %s\n' "$repo" "$orig" "$before" "$(workflows_of "$repo")" "$(last_run_of "$repo")"
    continue
  elif [ "$dry" = 1 ]; then
    after="$want?"
  else
    after=$(enabled_of "$repo")
    [ "$after" = "$want" ] || mismatch=1
  fi
  printf '%-22s %-9s %-9s %-9s %-20s %s\n' "$repo" "$orig" "$before" "$after" "$(workflows_of "$repo")" "$(last_run_of "$repo")"
done < "$LIST"

if [ "$mismatch" = 1 ]; then
  echo "ERROR: at least one repository is not in the expected state" >&2
  exit 1
fi
