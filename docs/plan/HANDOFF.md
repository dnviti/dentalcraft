# Handoff, 2026-11-13

Current state and what to do next. Plan: [`PLAN.md`](PLAN.md); overrides: [`DECISIONS.md`](DECISIONS.md); port plan: [`PORT-PLAN.md`](PORT-PLAN.md). The day-2 notes ([`HANDOFF-2026-10-31.md`](HANDOFF-2026-10-31.md)) stay as history; their open issues 1 to 6 (standard export, stamps, bridges, shell speed, occlusion, trim) are still open and are parked, not current.

## Mode

From 2026-11-07, GitHub Actions are suspended (CLAUDE.md "Current mode", `docs/local-ci.md`). CI, PR merges and release-please run locally, and they must reproduce the runners exactly. Pushing manually is allowed. The `.github/` workflows stay in the repos, untouched, until the user re-enables Actions. Before this, the mode was local-only: the first public alpha (2026-11-01) was tagged and released, and later work stayed local.

## In progress (2026-11-14): selecting 3D components, outline and gizmo

Branch `feat/teeth-components` of `dentalcraft-aligners` and `dentalcraft-app` (working trees, not committed). Spec: `docs/design/ui-spec.md`, "Selecting a component and the gizmo (viewport)".

- Aligners: command `aligners.components.transform` (`dca-module/src/commands/components.rs`): tooth move/turn = its pose in the plan (stage given, or the final position), through `run_adjust` (same data as "Move a tooth"); tooth scale = its closed solid scaled about `dca_model::tooth_centre`, kept as `ComponentEdits::tooth_scales` (valid while the tooth keeps that solid; `move_arch` carries it); gingiva/scan = the whole arch through `occlusion::move_arch` (bite scans alone), total kept per scan id in `ComponentEdits::scan_moves`; scale refused on gingiva and scans; stage 0 refused for a tooth. Model in `dca-model/src/components.rs` (field `AlignersState::components`, defaulted, no schema change).
- Display fix found on the way: the 3D teeth, the posed scans and the tooth numbers turned a tooth about its frame origin, while the setup, staging, export and adjust use `teeth::rest_pose` (centre of resistance); with a rotation the shown tooth was off by (I−R)·cor. Now all use the rest pose (`dca-module/src/scene.rs`, `dc-workspace` `overlay::tooth_move`, `labels::posed_point`).
- App: `dc-viewport` outline (mask + composite passes, `render.rs`, `outline.wgsl`), hover tint, transform gizmo (`transform.rs`); `dc-workspace/src/select.rs` (picking to components, preview, commit, inspector section, W/E/R, Esc).
- Not done when this was written: the full gates of both repos, the release build, a screenshot, a manual check in the window. Next: run the gates, `cargo build --release --workspace --bins`, try it on a real case, then commit on the branch.
- Tooth region view (gap map 4.3, branch `feat/tooth-region` of aligners and app, not committed): `oa.tooth_highlight` is "Show the region" / "End" in the 3D teeth inspector (`dc-workspace/src/region.rs`) over the new read-only command `aligners.manual.tooth-region` (`dca-module/src/manual/region.rs`, margin line `dca-algo/src/manual/margin.rs`, token `model_margin`); spec in `ui-spec.md`, "Show the region". Not checked by eye in the window.
- Case leftovers (gap map 1.3 and 1.6, branch `feat/case-leftovers` of aligners and app, on `feat/tooth-region`, not committed): `aligners.case.set-arch` (`dca-module/src/commands/set_arch.rs`, the plugin's `oa.arch_set`: renumber on an arch change, rebuild built teeth, flip the occlusal side through `frame::Input::occlusal_flipped`) and `aligners.case.make-base` (`commands/make_base.rs`, `dca-algo/src/scan_base.rs`, Blender oracle `tests/scan_base_oracle.rs`), both in the Import scans inspector; spec in `ui-spec.md`, "Import scans, manual corrections". Not checked by eye in the window.
- Case analysis by hand (gap map 5.2, branch `feat/diagnosis-edit` of aligners and app, on `feat/case-leftovers`, not committed): `aligners.diagnosis.edit-values` (`dca-module/src/commands/diagnosis.rs`, the plugin's `oa.diagnosis_edit`; hand values kept apart in `Diagnosis::edits`, items recomputed in `dca-algo/src/diagnosis/edit.rs`, oracle = the plugin's `diagnosis_override` run by `golden/oracle.py`); "Manual corrections" of the Case analysis inspector; the export report marks hand values; a new analysis of an arch drops its hand values as the plugin does. Spec in `ui-spec.md`, "Case analysis". Not checked by eye in the window.
- Bite (gap map 6.1-6.5, branch `feat/bite` of aligners and app, on `feat/diagnosis-edit`, not committed): the report of the last bite kept in the case (`dca-model/src/bite_report.rs`, `AlignersState::bite_report`, the plugin's `bite_json`; method registration / three points / virtual, correction), the Bite inspector (`dc-workspace/src/bite.rs`: report, bite scan slots with "Import the bite scans…", the tool Three points with markers and scan focus, "Correct the interpenetration"), the new command `aligners.occlusion.bite-correct` (`dca_algo::bite::correct_penetration`). Spec in `ui-spec.md`, "Bite". Not checked by eye in the window.
  - Plugin oracle `dca-algo/tests/bite_oracle.rs`, fixture `tests/fixtures/bite.json` from `gen_bite.py` (run in Blender: `blender -b --factory-startup -P gen_bite.py -- --out bite.json`). Input: the plugin's demo arches at 16 points per ring and a 1 mm gum, occlusal plane at z = 0; bite scans cut by the plugin's own `tests/bitesim.py` (canine to first molar), 0.3 mm under load. On the coarse arches of `occlusion.json` the plugin's own search landed 178° off, so they are not used.
  - Numbers, port vs plugin: 3-point pairing 2.6e-13 mm; correction from the plugin's pose 1.9e-6 mm (f32 rays); two scans upper arch 1.5e-5 mm, bite scans 4e-7 mm; one scan 1.3e-3 mm; from 3 points 1.2e-3 and 3.0e-3 mm. Verdict and reasons equal; areas within 0.4 mm².
  - Not 1e-6 for the registrations, by evidence: the plugin itself moves by up to 5.9e-3 mm / 6.8e-3° when its bite points move by 1e-6 mm (the ICP picks one of two equidistant faces at a convex edge by rounding; the port's BVH queries are f32). Its fine ICP started from the port's coarse pose ends within 2e-6 mm of the port. Bounds in the test are that measured spread.
- Arch line and final ghost (gap map 7.5, 7.6, branch `feat/setup-tools` of aligners and app, not committed): new command `aligners.planning.setup.line` (`dca-module/src/commands/setup_line.rs`, drawn line in `Setup::drawn`, followed by every setup), tool "Arch line" of Final position (`dc-workspace/src/archline.rs`), target layer = ghost of the teeth at their final pose (`view.rs` `scene_meshes`, tokens `model_arch_line`, `model_target`). Spec in `ui-spec.md`, "Final position: arch line and final ghost". Not checked by eye in the window.
- Final position inspector (gap map 7.1 d/e, 7.2, 7.3, same branches, not committed): setup parameters stored in the case (`dca-model` `SetupSettings`, command `aligners.settings.setup`, read by every run through `commands/setup.rs` `run_resolved`), result per arch (`Setup::results`), `aligners.planning.setup.reset`, Move a tooth with − / + steps, lock/unlock, exact values (`exact`) and the movement notes (`dc-workspace/src/setup.rs`, `manual.rs` `adjust_controls`). New oracle `golden/fixtures/*/setup/setup_params.json` (non-default parameters, plugin-equal on 6 demo cases). Plugin 42e6d87 crashes with midline CENTER on every demo case. Not checked by eye in the window.

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

## Fixed (2026-11-14): teeth turned the long way round in the setup and the staging ("719-stage anomaly")

Branch `feat/setup-alignment` of `dentalcraft-aligners` and `dentalcraft-app` (working trees, not committed). User report: the alignment spun the teeth 360 degrees.

- **Root cause.** A rotation has two quaternions, q and −q.
  - The setup command composed the stored pose from quaternions of matrices (`Pose::from_mat4` of the arch frame and of its inverse), so the sign came out arbitrary: all 12 setup poses of the user's project had w ≈ −1.
  - glam reads a quaternion with w < 0 the long way round (`to_axis_angle`, `to_scaled_axis`: an angle in (π, 2π)), and the staging read the stored pose that way (`staging::q_from_pose`). A 4° turn became a 356° rotation vector, divided into aligners at 2° each: 713 upper / 705 lower aligners on the user's project, every moved tooth turning up to 180° and back.
  - The same reading was in `frame::matrix_to_rotvec` (glam gives w < 0 for some rotations beyond 90°), in the `rotation_deg` of the setup and adjust reports (350–360°), in visits and in the export table.
- **Fix: one helper, `dca_algo::rotation`.** Canonical quaternion w ≥ 0, every angle in [0, π], the plugin's axis at exactly 180°.
  - Functions: `to_rotvec`, `from_rotvec`, `matrix_to_rotvec`, `rotvec_to_matrix`, `angle`, `degrees`, `canonical_pose`, `pose_from_mat4`.
  - Every conversion uses it:
    - staging: `q_from_pose`, `pose_from_q`, `local_pose`, `q_from_delta`;
    - setup: it stores `staging::pose_from_q(q_from_delta(F, D))`, the plugin's own conversion;
    - visits: the deviation and the achieved pose;
    - export, through `q_from_pose`;
    - adjust and the gizmo command: the poses they store and their reports;
    - occlusion and ramps: matrix to pose.
  - Removed: `frame::rotvec_to_matrix`, `frame::matrix_to_rotvec`, `frame::rotation_degrees`, `occlusion::pose_of`, `ramps::pose_of`.
  - A pose stored with w < 0 (projects saved before the fix) is now read the short way.
- **Same convention everywhere** (the rest pose has its origin at the centre of resistance). Two places still turned a tooth about its frame origin, and both now use `teeth::rest_pose`:
  - the ramps at a stage (`dca-module/src/commands/ramps.rs` `stage_deltas`);
  - the pose carried over when a tooth is rebuilt (`teeth_build.rs` `carried_pose`; the plugin's `T0 R0⁻¹ F`).
  - App: when the line of sight runs along the plane of the gizmo ring, the ring kept the angle of the turn but lost its sign (`dc-viewport/src/transform.rs`). It now keeps the last turn.
- **Tests.**
  - `rotation.rs` unit tests: w < 0; turns next to 180°; the plugin's rotation vector on 400 matrices, of which more than 10 get w < 0 from glam.
  - `staging.rs`: `a_stored_pose_with_negative_w_is_staged_the_short_way`, `a_turn_next_to_180_degrees_is_staged_the_short_way`.
  - `staging_oracle.rs`: `stored_target_poses_of_either_quaternion_sign_give_the_plugins_aligners`. On the six demo cases, the stored poses of either sign give the plugin's aligner counts and poses.
  - dca-module: `the_setup_and_its_aligners_do_not_depend_on_where_the_arch_lies`, `setup_poses_saved_with_negative_w_are_staged_the_short_way`, `a_gizmo_turn_sent_with_negative_w_is_stored_and_reported_the_short_way`, `carrying_a_pose_keeps_the_move_in_the_world`.
  - dc-viewport: `a_ring_keeps_its_turn_when_the_pointer_leaves_its_plane`.
- **Real-scan oracle (new).** `crates/dca-algo/tests/planning_real.rs`, generator `tests/fixtures/gen_planning_real.py`.
  - Environment variable `DC_PLANNING_REAL_ORACLE`. Run the generator after `gen_segmentation_real.py`, into the same folder. It uses the golden oracle's own stage functions and builds the plugin's closed teeth in a process pool.
  - Scan d (upper arch of the user's patient), measured 2026-11-14 on plugin 42e6d87:
    - setup targets within 1e-12 mm / 1.3e-12°, arch line within 7.5e-5 mm;
    - staging through stored poses with w < 0: 12 aligners (plugin 12), poses within 6.8e-7 mm / 2.7e-5°, largest turn of a tooth per aligner 1.406° (plugin 1.406°);
    - the port's setup, then stored poses, then the staging: 12 aligners (plugin 12).
  - Scan c (lower arch of the same patient), same day and plugin:
    - setup targets within 7e-13 mm / 1.5e-12°, arch line within 7.7e-5 mm, setup `overlap_max` 0.295 mm (plugin 0.295 mm);
    - staging through stored poses with w < 0: 12 aligners (plugin 12), poses within 6.6e-7 mm / 2.8e-5°, largest turn of a tooth per aligner 1.450° (plugin 1.450°);
    - the port's setup, then stored poses, then the staging: 12 aligners (plugin 12);
    - overlaps equal the plugin's for every pair; the largest are 37|38 (2.21 mm at rest and final) and 43|41 (1.69 mm at rest, 1.78 mm final).
  - Run time: the plugin's segmentation took about 3 min per scan and its closed teeth 190 s (d) and 1204 s (c) with 8 jobs. The port test takes under 1 s per scan in release. Delete the oracle folder after the run (patient data).
- **Overlaps "up to 2.6 mm": not a setup defect.**
  - The figure is the staging's "residual overlap in the final setup", measured on the closed crowns, and the crowns already overlap at rest by the same metric.
  - Scan d: 17|16 0.99 mm and 13|12 1.66 mm at rest. A pair the setup does not move keeps its rest overlap.
  - On the same inputs the plugin gives the same numbers for every pair, at rest and in the final setup.
  - In the user's project the largest pairs, 35|36 (3.9 mm) and 36|37 (2.1 mm), are teeth the setup does not move.
- **Old plans kept their length.** Staging again never dropped the trailing aligners of a longer old plan (`dentalcraft-aligners/crates/dca-module/src/commands/staging.rs` `merge_arch`): on the user's project, the new 12 / 8 aligners stayed padded to 713. It now keeps only up to the end of both series. Test: `staging_again_drops_the_aligners_of_a_longer_old_plan`. `AlignersState::clear_arch` (dca-model) now does the same: when one arch is cleared, the other keeps only its own series, up to its last movement or IPR. The repeats of its last pose that only kept up with the cleared arch go, as in the plugin, where each arch has its own `n_stages`. Test: `the_repeats_of_the_other_arch_go_with_the_longer_series`.
- **An existing project:** Final position → Run again (stores the poses with w ≥ 0), then Aligners → Run again.
  - On a copy of the user's project with the release CLI, the setup now reports rotations of 0–10° (before: 350–360°) and the staging plans 12 upper / 8 lower aligners, every stored pose with w ≥ 0.
  - The largest turn of a tooth per aligner is 1.66° and the largest rotation over all stages 9.96°, the setup's own.
- **Gap map correction (scope for the next step).** `PORT-GAP-MAP.md` 7.1 (c) said the plugin coordinates the upper arch line with the lower one through the bite. In plugin 42e6d87 that code is dead:
  - `case_plan.run_setup` sets `coord = None`;
  - `coordination()` is called only by `_setup_line()`, which nothing calls;
  - `coord_changed()` returns False.

  Still live; ported on 2026-11-14 (decided with Main: port only these):
  - **The setup refusal** (`case_plan.py:386-389`).
    - Plugin condition: `opposing_pair(obj)` (both arches have their 3D teeth), then `not arches_related(lower, upper)`. Related means `bite.info(lower)["fonte"]` is set (MORSO, VIRTUALE, SCANSIONI) or `occlusion.in_occlusion`.
    - Port: `dca_algo::occlusion::bite_needed`. It checks that both arches have a scan with tooth colours (the teeth the setup measures), that `bite_registered` is not set (by the registrations and the virtual bite), and that `in_occlusion` is false on the arch frames.
    - `aligners.planning.setup.automatic` refuses whichever arch it is asked for, with `aligners-err-setup-bite-first`, and changes nothing.
    - The Final position inspector shows the notice "Bite first", which points to Bite. The Run button stays; a run gives the error toast. The bite is never run from there (menu law).
  - **The bite before the setup in `aligners.auto`** (`case_auto.py:424-434`).
    - The order is now diagnosis, bite, setup, staging, schedule, contact map, export. The bite step runs only when `bite_needed` is true at that point.
    - The virtual bite adds the plugin's warning ("Arches put in VIRTUAL occlusion before the final position…") to `warnings`.
    - Difference: with a bite scan in the case, the port registers on it, as the Bite leaf does, instead of estimating. The plugin's auto always estimates.
    - With `occlusion: false`, two arches that are not related stop the run at the setup.
    - The other differences in order are not live. The orientation runs right after the numbering (the plugin takes the frame from the seeds; `worldframe.auto_align` only sets the display). The schedule is a step (the plugin builds the calendar on demand). The contact map runs at the end (`occlusion.auto_pair` refreshes the summary there). Classifications are not ported (1.7).

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
- The setup and staging rotations are fixed (2026-11-14, above). The setup refusal without a bite and the bite before the setup in `aligners.auto` are ported (2026-11-14, above).
- The standard-quality export is slow and fails the print check (see the day-2 handoff).
