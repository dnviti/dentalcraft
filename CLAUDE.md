# CLAUDE.md

Guidance for AI agents working in this repository. Read `README.md` and `docs/plan/HANDOFF.md` first.

## Current mode: local-only, speed first (from 2026-10-31, until the user revokes it)

This rule overrides "Versioning workflow" and "CI notes" below.

- Do all work locally, git included: commit on local branches (or local `main`). Never `git push`, never open PRs, never trigger or wait for CI, and never tag or cut releases.
- Build and test locally only, inside the superproject, so the `.cargo/config.toml` `[patch]` uses the submodule working trees. No tag bumps between repos. Run `git checkout -- Cargo.lock` in a submodule before committing it.
- Priority: finish the features that make up the application by porting them from the Blender plugin `REDACTED-PATH`. That repo is read-only and is the oracle.
- Keep the local quality gate (`cargo fmt --check`, `cargo clippy --all-targets -- -D warnings`, `cargo test`) for the crates you touch.
- When the user ends this mode, push the branches and run the normal release flow.

## Feature order: one at a time

- Work on one feature at a time, in workflow order, starting from scan import. Touch other features only where they interact with the current one.
- The feature must end up working well. Never move to the next feature on your own: when it is done, report and wait until the user expressly asks to go on.
- If the user asks for work on a specific other feature, do it, then return to the feature reached in the sequence.
- Every agent works on the current feature. Parallel agents may take different tasks of that same feature, never different features.
- Keep the user informed: every status update names the current feature, its tasks with their status, and the issues found. Explain every problem plainly, including unresolved ones.

## Requirement: agent-drivable (CLI + MCP, like the ArtCraft apps)

DentalCraft must ship `dentalcraft-cli` and an MCP server (`dentalcraft-cli mcp`) so that AI agents can drive everything:
- Every user action is a registered command with an id, a params schema and docs.
- Modes: a headless in-process engine session, or bridge mode where the app runs with `--control <port>` and the CLI uses `mcp --connect <port>`.
- MCP tools: list/describe/execute/batch commands, inspect state, render, open/save, undo/redo.
- New features are not done until they are reachable as commands from the CLI/MCP.

## What this is

DentalCraft is a desktop application for digital dentistry, written in Rust. It replaces the Blender add-on at `REDACTED-PATH`, which stays read-only and is the oracle for algorithms and regulatory documents. Decision: [`docs/adr/0001-full-rewrite-in-rust.md`](docs/adr/0001-full-rewrite-in-rust.md). Plan: `docs/plan/PLAN.md`; `docs/plan/DECISIONS.md` overrides it.

This superproject has no code and no version. It pins four private submodules (org `dnviti-personal-org`, tracking `main`).

## Repository and crate map

| Submodule | Lang | Crates / content |
| --- | --- | --- |
| `dentalcraft-core` | Rust | `dc-mesh`, `dc-geom`, `dc-case`, `dc-command`, `dc-jobs`, `dc-scene`, `dc-project`, `dc-module-api`, `dc-i18n`, `dc-theme`. Headless engine. |
| `dentalcraft-aligners` | Rust | `dca-model`, `dca-algo` (one file per pipeline stage), `dca-module`. Module id `aligners`, display name "Aligners" / "Allineatori". Depends on core. |
| `dentalcraft-app` | Rust | `dc-app` (shell, screens), `dc-ui` (widgets, tokens), `dc-viewport`, `dc-workspace`, `dc-auth-client`. Depends on core and aligners. |
REDACTED

Superproject folders: `docs/plan` (plan, decisions, handoff), `docs/adr`, `docs/design` (`tokens.json`, `ui-spec.md`, `screens/`, FigCraft file), `docs/screenshots`, `.cargo/config.toml`.

## Build, run, test

```sh
export PATH="$HOME/.cargo/bin:$PATH"          # Rust 1.99.1, pinned per repo

cd dentalcraft-app && cargo run -p dc-app --release   # the application
REDACTED

cargo fmt --check && cargo clippy --all-targets -- -D warnings && cargo test   # per Rust repo
go vet ./... && gofmt -l . && go test -race ./...                               # server
```

REDACTED

Auth integration test (off by default, needs the Go server):
`cd dentalcraft-app && DC_AUTH_IT=1 cargo test -p dc-auth-client --test server_it -- --ignored --nocapture`.

## Local `[patch]` and Cargo.lock

`.cargo/config.toml` redirects the git dependencies on core and aligners to the working trees, but only for builds started inside this superproject. Standalone builds (CI, a submodule cloned alone) use the pinned git tags. `net.git-fetch-with-cli = true` makes cargo use the git CLI (SSH agent, credential helpers).

Building inside the superproject rewrites the submodule `Cargo.lock` with path sources for `dc-*` / `dca-*`. Never commit that: run `git checkout -- Cargo.lock` in the submodule before committing. Consumers pin tags (`tag = "vX.Y.Z"`).

## Versioning workflow

1. Work on a `feat/*` (or `fix/*`) branch in the submodule, open a PR.
2. CI runs on a self-hosted runner.
3. Squash merge with a conventional title (`feat:`, `fix:`, `chore:` ...): release-please reads it.
4. Merge the release-please PR; it tags `vX.Y.Z` and updates the changelog.
5. Consumers move to the new tag; then bump the pointers here with a commit `chore(submodule): <repo> a vX.Y.Z` (manual, see README).

Internal path dependencies must not carry a `version =` requirement (release-please would rewrite them and break the build). Release type: `rust` for Rust repos, `go` for the server; tags have no component prefix.

## CI notes

- The self-hosted runner has no C toolchain: jobs install it. No GPU, so only headless and `egui_kittest` logic tests run in CI.
- Jobs pin the GitHub SSH host key. Private cross-repo access uses read-only deploy keys, secrets `DEPLOY_KEY_CORE` and `DEPLOY_KEY_ALIGNERS` in the consumers.
- Checks do not run on release-please PRs opened by `github-actions[bot]` (events by that token do not trigger workflows). Merge those PRs without the checks, or switch release-please to a PAT.

## Constraints

- Pure Rust, no C++ toolchain on the build machines: `rustls` with `ring` (not `aws-lc`), `zip` with deflate (not zstd).
- `egui` / `eframe` are pinned to `=0.37.0`; upgrade them together.
- Core stays headless and testable without a GPU; modules depend only on core.
- Never commit Teeth3DS data (`$DC_TEETH3DS`).

## UI conventions

- Design source: `docs/design` (`tokens.json`, `ui-spec.md`, `screens/`). Build UI from the `dc-ui` widgets and tokens, not ad-hoc styling.
- Every user-visible string is a Fluent key, in English and Italian (`i18n/{en,it}/<crate>.ftl`). Tests check key parity between languages. Never hard-code text.
- Module name: "Aligners" (en) / "Allineatori" (it); id `aligners`.

## `.dcprj` format (v1)

ZIP container. First entry `mimetype` (stored): `application/vnd.dentalcraft.project+zip`. JSON entries deflated. Contents: `manifest.json` (format_version, modules, blake3 and size per entry), `case.json` (pseudonymised patient code, scans, world frame), `modules/<id>/state.json`, `history/steps.json`, `blobs/<blake3>.dcm` (`DCM1` mesh blobs), `thumbnail.png`. BLAKE3 is verified on load; save is atomic (`.tmp`, fsync, rename, one `.bak`). Newer versions open read-only; unknown module state is preserved. Full spec: PLAN.md section 2.

## Commits

Conventional commits. Only `git add` your own paths, never `git add -A`. End every commit message with a blank line and:

`Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`

Working hours: stop by 23:30 Europe/Rome; no risky or long operations after 23:00.
