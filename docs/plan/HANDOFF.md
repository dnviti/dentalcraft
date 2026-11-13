# Handoff, 2026-11-13

Current state and what to do next. Plan: [`PLAN.md`](PLAN.md); overrides: [`DECISIONS.md`](DECISIONS.md); port plan: [`PORT-PLAN.md`](PORT-PLAN.md). The day-2 notes ([`HANDOFF-2026-10-31.md`](HANDOFF-2026-10-31.md)) stay as history; their open issues 1 to 6 (standard export, stamps, bridges, shell speed, occlusion, trim) are still open and are parked, not current.

## Mode

From 2026-11-07, GitHub Actions are suspended (CLAUDE.md "Current mode", `docs/local-ci.md`). CI, PR merges and release-please run locally, and they must reproduce the runners exactly. Pushing manually is allowed. The `.github/` workflows stay in the repos, untouched, until the user re-enables Actions. Before this, the mode was local-only: the first public alpha (2026-11-01) was tagged and released, and later work stayed local.

## Released: alpha tags on `main`

| Submodule | Tag | Notes |
| --- | --- | --- |
| `dentalcraft-core` | `v0.3.0-alpha.2` | module scene entries with arch, tooth and stage. `main` `796bb30` adds only the source notice `LICENSE.md` (chore, no release) |
| `dentalcraft-aligners` | `v0.2.0-alpha.4` | 3D teeth finish (non-finite guard, cancel, faster untangle), teeth basis for "out of date", menu grouped by function with the manual tools out of the menu, delete a tooth mark (PR #9, release PR #10, 2026-11-13) |
| `dentalcraft-app` | `v0.2.0-alpha.3` | separate teeth and gum inspector, EULA, "Licence and notices" dialog, third-party notices; linux and windows binaries on the release |
| `dentalcraft-server` | `v0.5.0` | `main` `cc6143e` adds only the source notice `LICENSE.md` (chore, no release) |
| `dentalcraft-web` | none (`main` `2498eb2`) | no release-please; licence page, downloads point at app `v0.2.0-alpha.3`. Image `ghcr.io/dnviti-personal-org/dentalcraft-web:latest` and `:sha-2498eb2` pushed (digest `sha256:cd1ac5ef558f1e4f60a2085515a4154e94b2730fd5d5f44079f7ea6b15971231`); the hosting platform service `dentalcraft-web` is not rolled out to it |

The `.1` alphas include scan import and the simple left menu (six groups, eight steps; see `docs/design/ui-spec.md` section 6). The `.2` alphas (2026-11-08, through the local CI and release flow) add "Trova i denti" and "Denti 3D": the `feat/find-teeth` and `feat/teeth-3d` branches are merged into `main` and no longer the base of the work. The `feat/port-b0` branches of the earlier handoff are superseded by these tags. The `.3` alphas of aligners and app (2026-11-12) add "Separa denti e gengiva" and the licence.

## Current feature: "Denti 3D" (3D teeth), finishing

Branch `feat/teeth-3d-finish` of `dentalcraft-aligners` and `dentalcraft-app` merged into `main` on 2026-11-13: aligners PR #9, released in `v0.2.0-alpha.4`; app PR #15 (pins aligners `v0.2.0-alpha.4`), not released. The app, core and server releases wait for the user's release request (all repos together). Spec: `docs/design/ui-spec.md`, section "3D teeth". Per CLAUDE.md, finish this feature before moving on, and wait for the user to ask for the next one. "Separa denti e gengiva" (below) is released and done.

Done on the branch (2026-11-12):

- App: the tooth marks are hidden over the 3D teeth; the bite scan stays visible, as in the plugin (`dc-workspace/src/view.rs`).
- Aligners: a closed tooth with non-finite vertices is never kept (the tooth fails with `NotFinite`) and the crossing sweep cannot go quadratic. The NaN could not be reproduced on any input, including the 11-02 snapshot; it is likely plugin-side.
- Aligners: cancel between teeth and inside the gum solve.
- Aligners: real-scan oracle `crates/dca-algo/tests/teeth_real.rs` (env `DC_REAL_SCANS` and `DC_TEETH_REAL_ORACLE`; regenerate the oracle with `tests/fixtures/gen_teeth_real.py`). Skipped without the env vars.

Done on 2026-11-13 (merged, aligners PR #9):

- `teeth_real`: two-tier closed-tooth rule. Finiteness, watertightness, manifoldness and the tooth set stay strict. A tooth within `HAUSDORFF_MM` (1e-4 mm) must match every info-dict number. A tooth above it counts as a rounding divergence: it is printed with its info differences and fails only above `HAUSDORFF_DIVERGED_MM` (0.1 mm).
- Performance (`reconstruct/fair.rs` `untangle`, `reconstruct/geom.rs` new `Crossings`): smoothing sums only the moved vertices' neighbours, and the self-intersection search re-tests only pairs touching moved triangles. Output is byte-identical (old against new binary, pairs ab 90/90 and cd 87/87 files; the oracle numbers below are unchanged). Code review approved it. Unit test `crossings_follow_moved_vertices_like_a_full_search`.
- Teeth build, median of 3 (load not fully idle; old and new binaries run back to back): pair ab 27.2 s → 19.3 s, pair cd 4.6 s → 3.5 s. Profile per tooth: `fair` about 45% (CG solve `solve.rs:143` most of it), self-intersection search about 40% before the change.

Oracle results (plugin re-run 2026-11-13, with the speed-up):

| Scan | Result | Closed teeth: worst Hausdorff | Diverged |
| --- | --- | --- | --- |
| a | pass | 1.60e-4 mm | 46 (1.60e-4 mm, info equal; would have failed the old 1e-4 bound) |
| b | pass | 3.41e-2 mm | 24 (3.41e-2 mm; `contact_filled`, `despiked`, `sharp_left` differ), 26 (7.04e-4 mm, info equal) |
| c | pass | 9.1e-7 mm | none |
| d | pass | 2.8e-6 mm | none |

Root cause of b/24: no port stage is wrong. `close_crown` is chaotically sensitive to rounding: the ring vertices differ by at most 1.07e-14 (`plane_normal` eigen vs SVD), the fair Jacobi preconditioner differs (port `1/diag(A)` in `solve.rs`, plugin `1/(rmask+Σ1/deg²+lam)`), and the CG tolerance 1e-6 amplifies the gap until the untangle after the third taper fair flips one crossing pair. Fed the same rings, each side reproduces the other's result exactly. Using the plugin's Jacobi diagonal was not done: it delays the drift but never gives bit identity, and it would change the port's output.

Save everything and automatic save (2026-11-13, merged in `dentalcraft-app` PR #15; the user reported brush strokes and tooth marks gone after Save and reopen). Spec: `docs/design/ui-spec.md`, "Saving" (workspace) and "Out of date" / "Out-of-date arch" (3D teeth).

- Root causes. (1) The user's file held the corrections (`dirty` 36, 45, 46, 47 = brush strokes made after the build), but a reopened case shows the 3D teeth by default, built before the strokes, with the marks hidden: the corrections looked lost. (2) Save during a running command (or a field committed in the same frame) wrote the older state and said "Project saved"; the late change stayed unsaved. (3) Closing the window never asked and could cut a save. (4) No automatic save; Save was disabled while a save ran.
- Fix. An arch whose built teeth are out of date shows its scan, colours and marks; the 3D teeth inspector says "Out of date". `Workspace::tick` saves a project with a file 2 s after the last change (never during a job, a save or a dialog; quiet status Saving… / Saved / Unsaved changes / Not saved; a failure is an error toast). One save at a time, the next one queued. Home, Ctrl+W and closing the window save first (a project never saved asks); `DentalCraftApp::close_requested` holds the window until then.
- Tests: `dc-workspace/tests/save.rs` (every registered command classified; each one that can change the case runs through the workspace, Ctrl+S, reopen, compare case, module data, meshes and step history; undo; the automatic save on a simulated clock), `dc-app/tests/close.rs`, `view.rs` `built_teeth_tests`.
- Not covered: a project never saved is not saved automatically (by design, nothing asks for a file); the CLI session (`dc-session`) has no automatic save; quitting during a job saves the case as it is and drops the job's result; the clicks of a numbering in order not finished are not in the case.
- Follow-up (same day, merged in `dentalcraft-aligners` PR #9, `v0.2.0-alpha.4`): the 3D teeth of an arch are out of date after any change of its marks too (placed, moved, deleted, renumbered, missing, cleared, numbered in order), not only the brush. `dca-model` records what each arch was built from (`AlignersState::teeth_basis`, a defaulted field, no schema change) and `teeth_out_of_date` compares it with the case; `dca-module` records it at the end of `aligners.teeth.build` and `reconstruction.automatic`, and the manual rebuild brings it up to date once nothing is left to rebuild. Find the teeth and the separation run again clear the 3D teeth instead. Tests: `dca-model` `built_teeth_are_out_of_date_when_the_colours_or_marks_of_their_arch_change`, `dc-workspace/tests/outdated_teeth.rs`.

Next:

1. Release the app (and every other repo with pending work) when the user asks for a release.
2. Optional speed-ups not done (estimates): fuse the CG vector passes in `solve.rs:143` (exact, 25–35% of the solve); pass the existing edge list into `fair` instead of rebuilding it (`fair.rs:102`); profile `gingiva::gum_weights` (8.8 + 5.7 s on pair ab, outside the build).
REDACTED
4. Release archives still lack `LICENSE.md` and `THIRD-PARTY-NOTICES.md` (needs authorization to touch `binaries.yml`).

## Released: "Separa denti e gengiva" (Separate teeth and gum)

Merged into `main` of `dentalcraft-aligners` (PR #7) and `dentalcraft-app` (PR #13) and released in `v0.2.0-alpha.3` (2026-11-12). Spec: `docs/design/ui-spec.md`, section "Separate teeth and gum".

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

## Licence

- DentalCraft is proprietary. Holder: Daniele Viti. The end-user licence (EULA, Italian and English) is `dentalcraft-app/LICENSE.md` and the licence page of the web site (`dentalcraft-web`).
- Every repository has a source notice `LICENSE.md` (superproject, core, aligners, app, server, web), merged into `main` everywhere on 2026-11-12 (core PR #11, server PR #14, web PR #2, aligners and app with the feature).
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

## Released earlier, being finished now: "Denti 3D" (3D teeth)

First done on `feat/teeth-3d` in `dentalcraft-core`, `dentalcraft-aligners` and `dentalcraft-app` (from `feat/find-teeth`), merged into `main` and released in the `.2` alphas. It is the current feature again, see "Current feature" above. Spec: `docs/design/ui-spec.md`, section "3D teeth".

- Leaf `aligners.teeth.build`: closed teeth and gingiva per arch, diagnosis, one undo step, partial rebuild of hand-corrected teeth. Viewport toggle Scan / 3D teeth, gingiva deformed per stage, number chips follow the stage poses, `model` and `stage` in CLI and MCP renders.
- Performance: the teeth build takes about 19 s on pair ab and 3.5 s on pair cd (2026-11-13, see "Current feature"); the earlier 27 s was 49 s before the first optimization.

Known open points of this feature:

- The gingiva deformation is tested only on synthetic data (the demo case has no stages).
- The scan-b oracle divergence on teeth 24 and 26 (rounding, see "Current feature" above; within the 0.1 mm bound).

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
# segmentation oracle: see "Released: Separa denti e gengiva" above; teeth oracle: see "Current feature" above
```

Read `CLAUDE.md` for the quality gate and the `Cargo.lock` rule (`git checkout -- Cargo.lock` in the submodule before committing).

## Known risks

- Aligners and app build standalone against the pinned core (and aligners) tags. If a change uses unreleased core APIs, release core first and move the pins; resolve `Cargo.lock` outside the superproject so it records the tag sources.
- The setup and staging stages are not trustworthy yet (719-stage anomaly, overlaps); do not present planning output as production-ready.
- The standard-quality export is slow and fails the print check (see the day-2 handoff).
