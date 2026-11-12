# Handoff, 2026-11-08

Current state and what to do next. Plan: [`PLAN.md`](PLAN.md); overrides: [`DECISIONS.md`](DECISIONS.md); port plan: [`PORT-PLAN.md`](PORT-PLAN.md). The day-2 notes ([`HANDOFF-2026-10-31.md`](HANDOFF-2026-10-31.md)) stay as history; their open issues 1 to 6 (standard export, stamps, bridges, shell speed, occlusion, trim) are still open and are parked, not current.

## Mode

From 2026-11-07, GitHub Actions are suspended (CLAUDE.md "Current mode", `docs/local-ci.md`). CI, PR merges and release-please run locally, and they must reproduce the runners exactly. Pushing manually is allowed. The `.github/` workflows stay in the repos, untouched, until the user re-enables Actions. Before this, the mode was local-only: the first public alpha (2026-11-01) was tagged and released, and later work stayed local.

## Released: alpha tags on `main`

| Submodule | Tag | Notes |
| --- | --- | --- |
| `dentalcraft-core` | `v0.3.0-alpha.2` | module scene entries with arch, tooth and stage |
| `dentalcraft-aligners` | `v0.2.0-alpha.2` | find the teeth, 3D teeth, real-scan autoseed oracle test |
| `dentalcraft-app` | `v0.2.0-alpha.2` | find the teeth and 3D teeth in the viewport; linux and windows binaries on the release |
| `dentalcraft-server` | `v0.5.0` | |
| `dentalcraft-web` | none (`main` `5093413`) | no release-please; downloads point at app `v0.2.0-alpha.2`. Its image (`ghcr.io/dnviti-personal-org/dentalcraft-web`) is not pushed yet: `gh` lacks `write:packages`, so run `gh auth refresh -h github.com -s write:packages`, then `scripts/release-local.sh web-image` |

The `.1` alphas include scan import and the simple left menu (six groups, eight steps; see `docs/design/ui-spec.md` section 6). The `.2` alphas (2026-11-08, through the local CI and release flow) add "Trova i denti" and "Denti 3D": the `feat/find-teeth` and `feat/teeth-3d` branches are merged into `main` and no longer the base of the work. The `feat/port-b0` branches of the earlier handoff are superseded by these tags.

## Current feature: "Separa denti e gengiva" (Separate teeth and gum)

Branch `feat/separate-teeth-gum` in `dentalcraft-aligners` and `dentalcraft-app` (local, not pushed, no PR; from `main` at the `.2` alphas). Spec: `docs/design/ui-spec.md`, section "Separate teeth and gum". Per CLAUDE.md, finish this feature before moving on, and wait for the user to ask for the next one.

Done:

- Aligners (`aligners.preparation.segmentation.automatic`): refusal of a separation without usable tooth marks, the case parameters `aligners.settings.segmentation` (`target_faces` 5000 to 200000, `eta_convex` 0.01 to 1, `sigma` 0.1 to 10; out-of-range values are refused and change nothing), invalidation of what depends on the old labels (output `invalidated`, in a fixed order), the doubts of the check, and the progress of the five sub-steps in the status bar. Output carries `teeth`, `seconds`, `invalidated` and per arch the report.
- App: the leaf inspector with the parameters (sliders for the three settings), the result line and the out-of-date notice for what the new separation left stale. Headless test `dc-workspace/tests/separate_teeth.rs`; CLI test `the_segmentation_settings_and_run_work_on_the_demo_case` in `dc-cli/tests/aligners_pipeline.rs`.
- Real-scan oracle (`dentalcraft-aligners/crates/dca-algo/tests/segmentation_real.rs`, oracle script `tests/fixtures/gen_segmentation_real.py`), 4 real scans, plugin `42e6d87`, Blender 5.2.2, measured 2026-11-08:
  - Blender's simplified mesh fed to the port: label agreement 1.0 (final labels 1.00000 / 1.00000 / 1.00000 / 0.99997, same CG iteration counts).
  - The port's own simplification (`dc_geom::qem`): final agreement 0.995 to 0.998 (0.99797 / 0.99479 / 0.99688 / 0.99660), threshold 0.99. Worst tooth IoU 0.83: last molar 17 of scan b (patch that goes to the neighbouring molar or to the gingiva).

Run the real-scan test (needs the scans, Blender on PATH for the oracle; the oracle folder stays outside the repository and is deleted after the run; never commit scans or coordinates):

```sh
cd dentalcraft-aligners
out=$(mktemp -d /tmp/dc-segreal-XXXX)
for l in a b c d; do DC_REAL_SCANS=<scans> python3 -B crates/dca-algo/tests/fixtures/gen_segmentation_real.py "$out" --only $l & done; wait
DC_REAL_SCANS=<scans> DC_SEGMENTATION_REAL_ORACLE="$out" cargo test --release -p dca-algo --test segmentation_real -- --nocapture --test-threads=1
rm -r "$out"
```

Without both variables the test skips itself.

Open points closed (2026-11-12):

- The result line (teeth and seconds) now survives reopening a project: the last separation result is stored in the case.
- The decimal gap in the mono slider value ("0. 20") is fixed (tight decimal point in `dc-ui` `widgets.rs`).
- The all-cases segmentation oracle on the demo case (`segmentation_oracle.rs`) runs by default (not ignored any more); about 33 s in release CI.

Open point:

- Aligners must be released before the app branch builds standalone: the app uses the new aligners API (settings, `invalidated`), and the standalone build resolves the pinned aligners tag. Release aligners, move the app pin, then merge the app.

## Licence

- DentalCraft is proprietary. Holder: Daniele Viti. The end-user licence (EULA, Italian and English) is `dentalcraft-app/LICENSE.md` and the licence page of the web site (`dentalcraft-web`).
- Every repository has a source notice `LICENSE.md` (superproject, core, aligners, app, server, web). Branches `chore/licence` in core (`d2d8e00`), server (`eba2d46`) and web (`a2b699e`, `abfef8f`) are committed locally and not pushed yet.
- The app shows the licence and the third-party notices in the "Licence and notices" dialog (user menu); both files are embedded in the binary.
- Third-party notices are generated: `scripts/third-party-notices.py dentalcraft-app -o dentalcraft-app/THIRD-PARTY-NOTICES.md`. Rerun it whenever the app dependencies change (see `docs/local-ci.md`).

Known gaps:

- Release archives do not bundle `LICENSE.md` and `THIRD-PARTY-NOTICES.md`: it needs a change in `binaries.yml` and `release-local.sh`; the workflows must stay untouched while Actions are suspended.
- The MCP server info (core `dc-mcp`) has no copyright line.
- The app `Cargo.lock` lags the manifest versions (release-please bumps the manifests only).

## Released: "Trova i denti" (Find the teeth)

Merged into `main` of `dentalcraft-aligners` and `dentalcraft-app` and released in `v0.2.0-alpha.2` (with `feat/teeth-3d`). Spec: `docs/design/ui-spec.md`, section "Find the teeth".

Real-scan oracle test: `dentalcraft-aligners/crates/dca-algo/tests/autoseed_real.rs`.

- Env vars: `DC_REAL_SCANS` (folder with the scans; see the test-scans memory, never commit them) and `DC_AUTOSEED_REAL_ORACLE` (oracle output).
- Oracle script: `crates/dca-algo/tests/fixtures/gen_autoseed_real.py`.
- The test compares the port with the plugin on 4 real scans (seeds within 0.5 mm, arch frame within 0.05 mm and 0.05 degrees). It is skipped without both env vars. Re-run on 2026-11-08: 4/4 pass, deviations about 1e-14 mm.

The seed check after segmentation and the crown-width verification loop, first deferred to "Denti 3D", are ported (in `aligners.auto`; command `aligners.preparation.segmentation.check`) and released in aligners `v0.2.0-alpha.2`.

## Side request done: "Denti 3D" (3D teeth)

Done on `feat/teeth-3d` in `dentalcraft-core`, `dentalcraft-aligners` and `dentalcraft-app` (from `feat/find-teeth`), merged into `main` and released in the `.2` alphas. It is a side request, not the current feature. Spec: `docs/design/ui-spec.md`, section "3D teeth".

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
cd dentalcraft-aligners && git switch main && cargo test      # inside the superproject, local [patch] applies
cd ../dentalcraft-app && git switch main && cargo test
# real-scan oracle test (needs the scans and the oracle output)
cd ../dentalcraft-aligners && DC_REAL_SCANS=<scans dir> DC_AUTOSEED_REAL_ORACLE=<oracle dir> cargo test -p dca-algo --test autoseed_real -- --nocapture
# segmentation oracle: see "Current feature" above (branch feat/separate-teeth-gum)
```

Read `CLAUDE.md` for the quality gate and the `Cargo.lock` rule (`git checkout -- Cargo.lock` in the submodule before committing).

## Known risks

- Aligners and app build standalone against the pinned core (and aligners) tags. If a change uses unreleased core APIs, release core first and move the pins; resolve `Cargo.lock` outside the superproject so it records the tag sources.
- The setup and staging stages are not trustworthy yet (719-stage anomaly, overlaps); do not present planning output as production-ready.
- The standard-quality export is slow and fails the print check (see the day-2 handoff).
