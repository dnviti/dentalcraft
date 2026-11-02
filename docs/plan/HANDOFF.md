# Handoff, 2026-11-02

Current state and what to do next. Plan: [`PLAN.md`](PLAN.md); overrides: [`DECISIONS.md`](DECISIONS.md); port plan: [`PORT-PLAN.md`](PORT-PLAN.md). The day-2 notes ([`HANDOFF-2026-10-31.md`](HANDOFF-2026-10-31.md)) stay as history; their open issues 1 to 6 (standard export, stamps, bridges, shell speed, occlusion, trim) are still open and are parked, not current.

## Mode

Local-only, speed-first (CLAUDE.md "Current mode"), with one exception: the first public alpha (requested 2026-11-01) was tagged and released. Work after the tags is local only.

## Released: alpha tags on `main`

| Submodule | Tag | Notes |
| --- | --- | --- |
| `dentalcraft-core` | `v0.3.0-alpha.1` | |
| `dentalcraft-aligners` | `v0.2.0-alpha.1` | |
| `dentalcraft-app` | `v0.2.0-alpha.1` | |
| `dentalcraft-server` | `v0.5.0` | |

The alphas include scan import and the simple left menu (six groups, eight steps; see `docs/design/ui-spec.md` section 6). The `feat/port-b0` branches of the earlier handoff are superseded by these tags and no longer the base of the work.

## Current feature: "Trova i denti" (Find the teeth)

Local branches `feat/find-teeth` in `dentalcraft-aligners` and `dentalcraft-app`; `dentalcraft-core` is untouched on that branch. Spec: `docs/design/ui-spec.md`, section "Find the teeth". Per CLAUDE.md, finish this feature before moving on, and wait for the user to ask for the next one.

Real-scan oracle test: `dentalcraft-aligners/crates/dca-algo/tests/autoseed_real.rs`.

- Env vars: `DC_REAL_SCANS` (folder with the scans; see the test-scans memory, never commit them) and `DC_AUTOSEED_REAL_ORACLE` (oracle output).
- Oracle script: `crates/dca-algo/tests/fixtures/gen_autoseed_real.py`.
- The test compares the port with the plugin on 4 real scans (seeds within 0.5 mm, arch frame within 0.05 mm and 0.05 degrees). It is skipped without both env vars. TODO: not re-run in this check (needs the scans and the oracle output); confirm the result before stating that it matches.

The seed check after segmentation and the crown-width verification loop, first deferred to "Denti 3D", are now ported (in `aligners.auto`; command `aligners.preparation.segmentation.check`). Uncommitted at the time of writing (another agent commits them).

## Side request done: "Denti 3D" (3D teeth)

Done on local branches `feat/teeth-3d` in `dentalcraft-core`, `dentalcraft-aligners` and `dentalcraft-app` (from `feat/find-teeth`). It is a side request: the current feature in the sequence is still "Trova i denti", awaiting the user's trial. Spec: `docs/design/ui-spec.md`, section "3D teeth".

- Leaf `aligners.teeth.build`: closed teeth and gingiva per arch, diagnosis, one undo step, partial rebuild of hand-corrected teeth. Viewport toggle Scan / 3D teeth, gingiva deformed per stage, number chips follow the stage poses, `model` and `stage` in CLI and MCP renders.
- Performance: the teeth build takes about 27 s per real pair of scans instead of 49 s, with bit-identical output.

Known open points of this side request:

- The bite scan is still drawn together with the built teeth.
- The gingiva deformation is tested only on synthetic data (the demo case has no stages).
- One tooth attempt produces non-finite vertices (the quadratic self-intersection check; also at HEAD).

## Known issue for planning: 719-stage anomaly

Root cause: a quaternion with `w < 0` comes out of the setup pose composition (`dca-module/src/commands/setup.rs:166-167` and `:264-266`), and glam's `to_scaled_axis` is used without a sign flip in `dca-algo/src/staging.rs:541` (`q_from_pose`). The rotation vector then takes the long way round, and staging counts hundreds of stages.

Same pattern, to check when fixing: `frame::matrix_to_rotvec`, `setup.rs:272`, `dca-module/src/commands/visits.rs:740` and `:753`, `dca-algo/src/export.rs:398`.

Measured: flipping the sign gave 12 / 9 aligners (upper / lower) instead of 637 / 498. Separately, setup still leaves overlaps up to 2.6 mm. Not fixed (still open, in planning); it belongs to the setup and staging feature, not to the current one.

## Parked branches

- `dentalcraft-aligners`: `fix/model-stamps` (`03be70d`), `wip/standard-export` (`04e471b`).
- `feat/port-b0` in core, aligners and app: old port work, local only.

## Open items (still valid from wave 1)

- **Golden harness.** Teeth3DS is CC BY-NC-ND: keep it out of the repositories (`$DC_TEETH3DS`). Real scans for tests are in `datasets/development/arcate_singole_T10` (gitignored, read-only).
- **Tokens in two places.** `dc-theme` (core, placeholder) and `dc-ui` (app, real) overlap; consolidate from `docs/design/tokens.json`.
- **App stubs.** News, documentation URLs, ticket list and attachments, evaluation flow. Attachments are not modelled (old anomaly ANO-001).
- **Regulatory dossier** not carried over; `cargo xtask trace --check` not written.
- **release-please checks** do not run on PRs opened by `github-actions[bot]`.

## How to resume

```sh
cd <your checkout>
export PATH="$HOME/.cargo/bin:$PATH"
git submodule status
cd dentalcraft-aligners && git switch feat/find-teeth && cargo test      # inside the superproject, local [patch] applies
cd ../dentalcraft-app && git switch feat/find-teeth && cargo test
# 3D teeth side request: git switch feat/teeth-3d in core, aligners and app
# real-scan oracle test (needs the scans and the oracle output)
cd ../dentalcraft-aligners && DC_REAL_SCANS=<scans dir> DC_AUTOSEED_REAL_ORACLE=<oracle dir> cargo test -p dca-algo --test autoseed_real -- --nocapture
```

Read `CLAUDE.md` for the quality gate and the `Cargo.lock` rule (`git checkout -- Cargo.lock` in the submodule before committing).

## Known risks

- Everything after the alpha tags exists only on this machine until local-only mode ends.
- The setup and staging stages are not trustworthy yet (719-stage anomaly, overlaps); do not present planning output as production-ready.
- The standard-quality export is slow and fails the print check (see the day-2 handoff).
