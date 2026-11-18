# Handoff, 2026-11-18

Current state and what to do next. Plan: [`PLAN.md`](PLAN.md); overrides: [`DECISIONS.md`](DECISIONS.md); port plan: [`PORT-PLAN.md`](PORT-PLAN.md). The day-2 notes ([`HANDOFF-2026-10-31.md`](HANDOFF-2026-10-31.md)) stay as history; their open issues 1 to 6 (standard export, stamps, bridges, shell speed, occlusion, trim) are still open and are parked, not current.

## Mode

From 2026-11-07, GitHub Actions are suspended (CLAUDE.md "Current mode", `docs/local-ci.md`). CI, PR merges and release-please run locally, and they must reproduce the runners exactly. Pushing manually is allowed. The `.github/` workflows stay in the repos, untouched, until the user re-enables Actions. Before this, the mode was local-only: the first public alpha (2026-11-01) was tagged and released, and later work stayed local.

## Resume here (2026-11-18 night, scan reliability: NOT released yet)

User report: calibration did not work, scanning was very slow and unreliable, lost the object, the test piece could not be scanned; the scanner LEDs blinked. Work is on branch `fix/scan-reliability` of `dentalcraft-core` and `dentalcraft-app` (pushed, not merged, not released).

- **Root causes (measured on the rig, `docs/scanner/`):** turntable tilt speed values < 40 refused by the firmware (`ERR=007`) so calibration died at step 0; tilt wait model 6× too long; calibration turning ~7°/frame at 2.74 fps; frames arrive ~0.8 s late and the table angle was read at arrival; residual gate 0.2 mm below real noise; 20 mm jump limit; a lost frame was lost forever; ICP locked on the static scene and still said OK; `scan.auto` said "Done" with 4/49 frames; the view never re-framed the object; Full mode streamed IR for nothing.
- **Core (`fix/scan-reliability`):** tracking with prior-relative checks, Tukey + degeneracy guard, recovery through lost frames, static-lock detection; angle history at capture time (scanner latency 800 ms); stop-and-capture `scan.auto` (default when calibrated: 10° steps, settle, median of 3 frames, pose from the table, constrained ICP, loop closure, clutter removal) with a quality report; `turntable.calibrate` rewritten (24×15° stops, background removal, pairwise registration, axis fit, validation with error codes); accepted tilt speeds only; depth-only stream; newest frame; fill light (see below).
- **App (`fix/scan-reliability`):** the popup keeps the object framed; stop-and-capture by default with step/frames controls; calibration residuals, pairs and gain, and the scan quality report shown; slower default turn (8°/s); new Fluent codes EN+IT.
- **Live results on the test piece:** calibration 101 s, 24/24 pairs, 1.63°/1.28 mm; `scan.auto` 1 tilt 122 s, 37/37 stops, 0.276 mm, loop −0.01°; 2 tilts 250 s, 74/74 stops, 0.289 mm, 305k points, one clean horseshoe. ICP refinement is mostly refused on real frames (geometry not quite metric: no factory calibration); the table pose is exact and carries the scan.
- **Fill light (user decision 21:31, tested live):** UVC XU unit 4 selector 7, only the ON/OFF lines; on while streaming (97.0% valid pixels, 19 µm noise vs 92.8%, 27 µm off), off otherwise, so the LEDs no longer blink. Linux only.
- **Vendor tiers T1–T3 (user approval 21:43, supervised session):**
  - T1: firmware `v4.1.54.20260203|v31.7.1.0203`; XU selector 3 = live exposure in µs.
  - T2: factory calibration read through the XU file-read channel (open-for-read, read, 60-zero close frame only): rectified left pinhole fx = fy = 1142.37, cx = 163.19, cy = 329.85, baseline 88.42 mm (our FOV estimate was 1190 / centre). Replay on real data: pairwise rotation RMS 1.68° → 0.23°, fused residual 0.278 → 0.112 mm, loop error −0.37° → −0.07°, the slow continuous spin tracks 263/263 frames (was lost at ~25°). Loaded at connect when no user calibration file exists, cached under `<data_dir>/dentalcraft/revopoint-usb/factory/<serial>/`.
  - T3: manual exposure profile `0x912 0`, `0x911 6000`, `0x910 8000` → 6.76 fps (was 2.74), piece coverage 96–99%, pixel noise 21 µm (17), static ICP 0.05 mm (0.075); a 360° spin at 10°/s tracks 294/294. `0xa05 6` has no effect; AE mode `0x912 1` is not deterministic. Setting `fast_exposure`. The registers stay set until the scanner is replugged (the factory AE mode cannot be read back).
  - Never: file writes, firmware, factory calibration writes, serial, HID, any line outside the closed enums; never run Revo Scan's calibration (it overwrites the factory file).
- **Data (not committed):** `/var/tmp/dc-scan-data` (datasets, results, README), tools in `/var/tmp/dc-scratch`.
- **Next:** the user tests the release build from the branch; then merge, release (core, aligners pin, app, web) per the usual flow.

## 2026-11-18 evening, diagnostics, Windows scanner, signed Windows release

Released on the evening of 2026-11-18 through the local CI and release flow. Latest app: **`v0.2.0-alpha.10`**, the first with signed Windows files.

- **Signed Windows release** (user request "rilasciare l'applicazione firmata"): `dentalcraft-app` `v0.2.0-alpha.10` (PR #28, release PR #29) signs `dentalcraft.exe`, `dentalcraft-cli.exe`, `setup.exe` and the MSI with Authenticode: self-signed certificate `CN=DentalCraft (self-signed)`, SHA-256 `24DD542E337BCEA99C793D57DE53B6D355DC015BF1270D20D1321D56DCF0AA26`, valid to 2031-11-18, timestamped by SSL.com (`packaging/windows/authenticode.sh`, `binaries.yml`; superproject `26a3d68` `release-local.sh` and `docs/local-ci.md`). Run `release-local.sh app --require-authenticode`. Verified on the published files: signature, timestamp and fingerprint ok, SHA256SUMS and `update.json` match the signed files. SmartScreen still warns (not a public CA); the NSIS `uninstall.exe` is not signed. Site: signature text with the fingerprint and What's new (PR #10, `619f48d`).

- **Opt-in anonymous diagnostics** (user request):
REDACTED
  - `dentalcraft-app` `v0.2.0-alpha.8` (PR #24, release PR #25): crate `dc-diagnostics` (sanitizer, queue in `<data>/diagnostics/queue`, sender, tracing layer for ERROR and `diag = true` WARN, crash pickup, session event), first-start consent dialog (unticked; `consent.rs`), account-menu checkbox, Support "Show what is sent", commands `app.diagnostics.{status,set,preview,send}` (bridge and CLI). Nothing is collected without consent; turning it off deletes the queue and the install id. The EULA was left unchanged (user decision: it only excludes sending projects and scans).
- **Windows scanner** (user report: Windows did not see the MINI 2): `revopoint-usb` was a stub outside Linux. `dentalcraft-core` `v0.3.0-alpha.5` (PR #17, release PR #18) adds Media Foundation capture (`revopoint_usb/{device,linux,win,mf}.rs`, MF DLLs loaded at run time) and stops rejecting frame headers on word 4, which is not constant (IMU and timestamps were dropped on every platform). Verified on the real scanner on Linux (two rounds with restart) and in the `Windows VM` VM (`scan.*` session: 38 frames fused, 20718 points). `dentalcraft-aligners` `v0.2.0-alpha.9` (PR #19, release PR #20) and `dentalcraft-app` `v0.2.0-alpha.9` (PR #26, release PR #27) only move to it.
- `dentalcraft-web`: alpha.8 content (privacy, FAQ 13, What's new; PR #8, `REDACTED-REVISION`), then alpha.9 (Windows scanner).
- Windows binaries of alpha.8 and alpha.9 are unsigned (built with the committed `release-local.sh` while the Authenticode edit was still uncommitted); alpha.10 is signed.
- The old local-only branches (`feat/find-teeth`, `feat/port-b0`, `feat/scan-import` in core, aligners and app; `fix/model-stamps`, `wip/standard-export` in aligners) are now also on origin, as backups; main is unchanged.

Open:
1. Stop → restart of the scanner on a physical Windows PC (the VM needs a manual USB re-attach after the device re-enumerates). Repeated libvirt attach/detach hung the scanner once; only a physical replug recovered it.
2. `dentalcraft-app/crates/dc-app/tests/update.rs`: six helpers used only by Linux-gated tests fail Windows clippy `-D warnings` (CI lints Linux only).
REDACTED
4. Items 1 and 2 of the 2026-11-17 section below are still open.

## 2026-11-18 afternoon, scanning at project start

Released on 2026-11-18 through the local CI and release flow (feature: the user asked to scan at project start, so that a new project is not blocked without STL files, and to make the scan popup generic for the whole app and its modules):

- `dentalcraft-core` `v0.3.0-alpha.4` (PR #15, release PR #16): `dc-module-api` `ScannerInput { roles }`, `MenuItem.scanner`, `MenuItem::with_scanner`; a module declares on its import-scans leaf that it accepts the 3D scanner and which roles. It also ships the Kani harnesses of PR #14.
- `dentalcraft-aligners` `v0.2.0-alpha.8` (PR #17, release PR #18): move to core `v0.3.0-alpha.4`; `aligners.case.import-scans` declares Upper, Lower and Bite.
- `dentalcraft-app` `v0.2.0-alpha.7` (PR #22, release PR #23): new crate `dc-scan-ui`, the generic scan popup. It does not depend on `dc-workspace` or any module; it runs its own jobs, and each `ScanOutput` owns its temp file until the host drops it. `dc-workspace/src/scan.rs` is now a thin host. Fluent keys `ws-scan-*` / `ws-tt-*` became `scan-*` / `turntable-*` in `dc-scan-ui`. New project screen: "Scan" beside "Browse files…"; scanned meshes join the scan list with their role and Create imports them. A project can be created with no scans; the workspace then opens on its empty state (Import, Scan). The Scan button shows only where the module declares `scanner`. All 11 assets, glibc ≤ 2.39, notices regenerated (new crate `tempfile`, MIT).
- Server: nothing due (dry-run: no user-facing commits).
- `dentalcraft-web` `main` `d11f02b` (PR #7): content (statuses, FAQ 12 "start without scans", What's new) and downloads for `0.2.0-alpha.7`. Live on the hosting platform as revision `REDACTED-REVISION` since 2026-11-18 15:04 (image `sha-d11f02b`, REDACTED); checked live: `/en/`, `/it/`, downloads, `/update/stable.json`, apt/rpm repos, msi size. The REDACTED service quota is REDACTED again: the next site rollout must wait for REDACTED or needs a decision first.
- Not checked by eye in the window; no manual test with the real scanner from the New project screen yet.

Next, in order: items 1 and 2 of the 2026-11-17 section below are still open.

## 2026-11-17 evening, Kani release

Next, in order:
1. **Build/release pipeline overhaul** (user request 2026-11-17 23:01): the best possible build and release pipeline.
   - sccache shared across core, aligners and app in `ci-local.sh`, in `release-local.sh` (mounted in the runner container) AND in the `.github` workflows (editing the workflows needs the user's OK).
   - mold for dev builds only, not release: the binaries must match the runner.
   - Profile where release time goes (Windows podman build, installers, flatpak).
   - Plan first, then implement.
2. Kani on the merged refs was skipped tonight (only the working trees were verified): run `scripts/kani-local.sh core --ref origin/main`, then aligners and app.

Released on the evening of 2026-11-17 through the local CI and release flow:

- Formal verification with Kani: 35 proof harnesses (`#[cfg(kani)] mod kani_proofs`): core 19, aligners 13, app 3. `scripts/kani-local.sh`, [`docs/kani.md`](../kani.md) (laws table, install, conventions), CLAUDE.md "Formal verification (Kani)". Kani is a local gate; `ci-local.sh` and the runners never run it.
- Dev builds inside the superproject use sccache and mold (`.cargo/config.toml`); `ci-local.sh` and `release-local.sh` do not.
- `dentalcraft-core`: PR #14 `test: add Kani proof harnesses` merged (`1686bec`); no user-facing commit, so no release: the tag stays `v0.3.0-alpha.3` and the gitlink sits one commit past it (like server).
- `dentalcraft-aligners` `v0.2.0-alpha.7` (PR #15, release PR #16): fixes found by Kani: days of wear validated 5..=21 in the schedule and export commands, stage day guarded against NaN, next visit on an empty calendar, seed change reported independently of order.
- `dentalcraft-app` `v0.2.0-alpha.6` (PR #20, release PR #21): week of a stage without overflow on the timeline, move to aligners `v0.2.0-alpha.7`; third-party notices regenerated, unchanged. All 11 assets (8 formats, SHA256SUMS, signed `update.json`), glibc ≤ 2.39.
- Server: nothing due (dry-run: no user-facing commits).
- `dentalcraft-web` `main` `8bd3499` (PR #6, by the web session): What's new and downloads for `0.2.0-alpha.6`. Image build and hosting platform rollout are owned by that session; check that https://dentalcraft.app shows `0.2.0-alpha.6`.

Earlier on 2026-11-17, every repo together:

- `dentalcraft-core` `v0.3.0-alpha.3` (PR #12, release PR #13): the in-app 3D scanner connector (alpha) with the Revopoint MINI 2 (`revopoint-usb`, no vendor SDK), the optional `revopoint-sdk` backend, the simulated scanner, and the Revopoint dual-axis turntable over Bluetooth LE (`dc-ble`, `dc-turntable`, `scan.auto`, `turntable.calibrate`).
- `dentalcraft-aligners` `v0.2.0-alpha.6` (PR #13 `fix(deps)`, release PR #14): only the move to core `v0.3.0-alpha.3`.
- `dentalcraft-app` `v0.2.0-alpha.5` (PR #18, release PR #19): Scan button and scan popup with the turntable block; fixes for the sign-in session across restarts and exact numbers on save and reopen. All installers, signed `update.json`, `dentalcraft_0.2.0-alpha.5_SHA256SUMS.txt`.
- `dentalcraft-web` `main` `92cb559` (PR #5): scanning and turntable content, What's new and downloads for `0.2.0-alpha.5`. Live on the hosting platform as revision `REDACTED-REVISION` since 2026-11-17 10:47 (image `sha-92cb559`, REDACTED). The REDACTED service quota is REDACTED again: the next site rollout must wait for REDACTED or needs a decision first.
- Server: nothing due (only the `LICENSE.md` chore on `main`).
- Superproject: `hardware/scan-enclosure` (parametric enclosure for the MINI 2 and the turntable, LED lighting with an MCU-less brightness controller). Not printed yet; its open points (sharp edges, missing inside fillets, measurements to take) are in its README.
- Scanner facts: managed skills `revopoint-mini2-usb-facts` and `revopoint-dual-axis-turntable-ble-facts`.
- Known: one harmless Windows-only warning (unused field `options` in `dc-scanner/src/revopoint_usb/mod.rs:127`); the scanner was tested on hardware only on Linux, not yet on a dental model.

- None of the chain is checked by eye in the window yet.
- Gap map: [`PORT-GAP-MAP.md`](PORT-GAP-MAP.md) is the source of truth for what is left.

The four notes below describe the work as it was before the release; all of it is now merged and released as listed above.

- Scans closed at import (2026-11-15, `feat/aligner-preview` of aligners and app, not committed; gap map 1.6 DONE): open arch scans are closed with a base by `aligners.case.import-scans` (seedless `occlusal_axis`, base labels 0), the scan as read kept as a prefix (`AlignersState::scan_bases`, with `closed_by`: import, hand, tooth marks; `dca-module/src/open_scan.rs`); make-base rebuilds from it. The Import scans inspector ("Base under the scans") shows per arch scan how it is closed and its button ("Close with a base", "Run again"). Checked: round trip with undo/redo in `dc-workspace/tests/save.rs`; real scans in `dca-module/tests/import_real.rs` (the prefix equals the file as the oracles read it, 4/4); `autoseed_real` 4/4 and `segmentation_real` scan d green; CLI import of scan d 0.53 s (2450 border edges, +2450 points, +7344 triangles, watertight, kept by save and reopen). Left: the full gates and the release build of the whole workspace (see DECISIONS.md, 2026-11-15).
- Installers, site side (2026-11-15, `dentalcraft-web` `feat/installers`, not committed): release keys generated once in `~/.config/dentalcraft-release/` (GPG ed25519 `83B0A31CA19DE14A1648A875C10CE2EB009DE538`, minisign `B155D07CF2A36DB0`; public halves in `dentalcraft-web/keys/`); `/en|it/download/` with Installer or Standalone per OS; the image build makes the signed APT, RPM and Flatpak repositories and `/update/stable.json(.minisig)` from the pinned app release (build secret `gpg` = `DENTALCRAFT_GPG_KEY`); `dentalcraft-app/packaging/update-manifest.py` signs the manifest. Details: `dentalcraft-web/README.md`.
- Installers, packaging side (2026-11-15, `dentalcraft-app` `feat/installers`, shared working copy `/tmp/dc-installers/dentalcraft-app`, not committed): `packaging/installers.sh` builds the AppImage, deb, signed rpm, Flatpak (runtime 25.08, signed commit), setup.exe (NSIS, per user, silent `/S`) and MSI (wixl, per machine, UpgradeCode `{90BDCF16-C5BE-4030-B024-F81F76394F48}`, never change it) from the two archives, which now also hold `LICENSE.md`, `THIRD-PARTY-NOTICES.md` and `install-kind`. `binaries.yml` gains the `installers` job, the signed `update.json` and `dentalcraft_<V>_SHA256SUMS.txt` (new secrets `DENTALCRAFT_GPG_KEY`, `DENTALCRAFT_MINISIGN_KEY`, not set yet). `scripts/release-local.sh binaries app` replays it and now builds linux in the pinned runner image (glibc 2.39; the host build of alpha.3 needs glibc 2.44); new flags `--src`, `--no-sign`, `--only installers`. Details: `dentalcraft-app/packaging/README.md`, `docs/local-ci.md`.
- Installers, app side (2026-11-15, same working copy, not committed): new crate `crates/dc-update` (minisign-verified `https://dentalcraft.app/update/stable.json`, release key built in; SemVer check; install kind from `install-kind`, `$APPIMAGE`, `/.flatpak-info`; download checked against size and SHA-256; standalone folder swapped and AppImage replaced when the app closes, setup.exe `/S` / `msiexec /passive` run after it quits, deb/rpm/Flatpak get the package manager command). App: check at startup (setting in the account menu), "Check for updates…" in the account menu and on Support, the update dialog (Update now / Later / Skip this version, progress, Restart now through the save on close). Agents: `app.update.check`, `app.update.apply` (bridge and CLI/MCP), `dentalcraft-cli update [--check]`. Details: `dentalcraft-app/README.md` "Updates".

Next, in order:
1. The user tries the release build (alignment fix: Final position → Run again, then Aligners → Run again on the existing project; 3D teeth → Run again first if the upper arch still shows the scan).
2. Production leftovers:
   - the trim bars over gaps and the weak-join check, which need the bar boxes in the shell model (interface change between shell and trim);
   - the ceilings of the embrasure fills;
   - the trim panel notes in the UI and the report;
   - the export aligner shell without bridges and fills;
   - the trim speed (about 50 s of the 66 s of a Standard aligner);
   - the `shell_reach` oracle;
   - the contact overlays (12.11). The aligner in the 3D view (12.8) is done on `feat/aligner-preview` (aligners, app; not committed): `aligners.view.aligner` / `-exact`, layer "Aligner" in the new toolbar group "Models in the view" (Study models, Target position, Aligner; the five-icon Layers group did not fit beside the cube at 960 x 640), the Aligners inspector section; oracle `dca-algo/tests/aligner_view_oracle.rs` bit for bit with the plugin's `_bind`/`_deform` (fused multiply-adds as numpy's sgemm); ignored golden test green (preview 5.2 s per arch at stage 2, exact Draft 7.7-8.0 s, the export's STL byte for byte); not done: `preview_auto_bases`, a check by eye.
3. Then gap-map items 9 to 13 in order: study models, export and print, visits, steps, display and help.
4. Done 2026-11-15: merged and released (see "Resume here").

Decisions waiting for the user:
- Leaving a project that has a file saves without asking (current behaviour).
- `aligners.auto` registers a bite scan when present, while the plugin's auto always uses the virtual bite.
- The tooth scale of the gizmo: the user asked for it, but the plugin forbids it.

## Work of 2026-11-14 (details)

## In progress (2026-11-14): selecting 3D components, outline and gizmo

Branch `feat/teeth-components` of `dentalcraft-aligners` and `dentalcraft-app` (committed and pushed). Spec: `docs/design/ui-spec.md`, "Selecting a component and the gizmo (viewport)".

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
- Aligners inspector (gap map 8.1-8.3, branch `feat/staging-tools` of aligners and app, not committed): staging and calendar settings in the case (`StagingSettings` with `overcorrection`, `Settings::interval_policy`, `start_date`; command `aligners.settings.staging`, plugin ranges), read by the staging, the schedule, the Aligners leaf (now also `policy`) and the exports; result per arch `AlignersState::staging_results`; "Slow a tooth" `aligners.planning.tooth-speed` (`AlignersState::tooth_speed`, the arch staged again in the same undo step); inspector `dc-workspace/src/staging.rs`. New oracle `golden/fixtures/*/staging/staging_params.json` (every staging parameter off its default, the four explicit patterns, one slowed tooth, FIXED and ADAPTIVE calendars: plugin-equal on the 6 demo cases). Not checked by eye in the window.
- Clinical review (gap map 9.1, 9.2, 10.1, 11.3, branch `feat/review` of aligners and app, not committed): records in the case (`dca-model/src/review.rs`, `AlignersState::review`), rules `dca-algo/src/review.rs`, commands `aligners.review.{classify,decide,set-value,bulk}` (`dca-module/src/commands/review.rs`; classify runs in `aligners.auto` between the staging and the calendar), leaf "Clinical review" in Planning (ninth workflow step: the footer reads `done/9`), inspector `dc-workspace/src/review.rs`; the attachments in force feed the calendar, the export and the report; the IPR layer marks each planned contact. Oracle `dca-algo/tests/review_oracle.rs` against `golden/fixtures/*/classify`: 6 demo cases, 59 records each, equal to the plugin (no AI classifier, 9.3). Spec: `docs/design/ui-spec.md`, "Clinical review".
- Production settings and where the aligner ends (gap map 12.2-12.7, 12.10, branch `feat/production` of aligners and app, not committed): settings in the case (`TrimParams::insertion_axis`, `Settings::{stamp, quality}`; `Quality` moved to `dca-model`, re-exported by `dca_algo::export::provider`), command `aligners.settings.production` (groups trim, shell, stamp, bite, ramps, quality; plugin ranges, one undo step; `dca-module/src/commands/production.rs`); the aligner end per arch and side (`AlignersState::aligner_end`, `dca-model/src/production.rs`; command `aligners.production.aligner-end` set / suggest / clear; the setup keeps the teeth left out at rest and records the end, `setup_end_changed` warns like the plugin; the bite with the aligners worn and the ramps count only the covered teeth; the shell, trim and stamp take `aligner_teeth`); `aligners.output.export-all` takes quality and case code from the case; the Parameters of Export for printing (`dc-workspace/src/production.rs`). Spec in `ui-spec.md`, "Export for printing: where the aligner ends and the production settings". Not ported: the advice from shell defects (no defect record). Not checked by eye in the window.
- Trim pieces (gap map 12.2, branch `feat/production` of aligners, not committed): `dca-algo/src/trim.rs` tries the plugin's three fills (the second and third also grow the outer side of the wall, `fill_out`). It then plugs the holes left where they are, or opens them to the border by slots of the trim surface and builds the shell again, keeping a round only with fewer holes, no cap lost and at most 5% of the volume taken (`trim/holes.rs`: `_handle_loops`, `_short_loops`, `_cap_loop`, `_plug_holes`, `_window_cuts`, `_open_holes`). EQUATOR: the field refinements (`_gum_cell_max`, `_grid_distance`, `_coarse_inside`) are in `trim/cutter.rs`; the border checks (`labial_cover`, `border_heights`, `border_offsets`, the lists of `_aligner_solid`) in `trim/checks.rs`; the rigid removal (`removal_lock`, `rigid_lock`) in `trim/removal.rs`. `aligners.production.trim-line` reads the insertion axis from the case and the aligner end (`aligner_teeth`), and reports fill, plugs, slots and checks. Plugin oracles: `tests/trim_oracle.rs` (`gen_trim.py`, new sections `refine` and `checks`) and `tests/holes_oracle.rs` (`gen_holes.py`, numpy only, also the removal). Still missing: the bars over gaps and their weak-join check (they need the model of the shell, not only its field), the ceilings of the embrasure fills, the panel notes. Not run: the full gates, the release build, a Standard export with holes (golden stage 1 has none).

## Released: alpha tags on `main`

| Submodule | Tag | Notes |
| --- | --- | --- |
| `dentalcraft-core` | `v0.3.0-alpha.5` | Windows capture of the MINI 2 through Media Foundation; frame header word 4 no longer checked (PR #17, release PR #18, 2026-11-18). Previous `v0.3.0-alpha.4`: `dc-module-api` scanner declaration for modules (PR #15, release PR #16); `v0.3.0-alpha.3`: in-app 3D scanner connector (alpha) (PR #12, release PR #13, 2026-11-17) |
| `dentalcraft-aligners` | `v0.2.0-alpha.9` | move to core `v0.3.0-alpha.5` (PR #19, release PR #20, 2026-11-18). Previous `v0.2.0-alpha.8`: scanner roles on import-scans (PR #17, release PR #18) |
| `dentalcraft-app` | `v0.2.0-alpha.10` | Windows programs and installers signed with Authenticode (self-signed, fingerprint `24DD542E…DCF0AA26`) (PR #28, release PR #29, 2026-11-18). Previous `v0.2.0-alpha.9`: move to core `v0.3.0-alpha.5` (Windows scanner) (PR #26, release PR #27); `v0.2.0-alpha.8`: opt-in anonymous diagnostics (PR #24, release PR #25); `v0.2.0-alpha.7`: generic scan popup, scanning at project start (PR #22, release PR #23). All 8 formats, signed `update.json`, SHA256SUMS, glibc ≤ 2.39 |
| `dentalcraft-server` | `v0.6.0` | anonymous diagnostics ingest, admin pages, MCP endpoint (PR #15, release PR #16, 2026-11-18); live as `REDACTED-REVISION` |
| `dentalcraft-web` | none (`main` `619f48d`) | no release-please; signed Windows downloads and What's new for `0.2.0-alpha.10` (PR #10), on top of `0.2.0-alpha.9` (Windows scanner, PR #9) and `0.2.0-alpha.8` (diagnostics, PR #8) |

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

1. Done 2026-11-15: app `v0.2.0-alpha.4` released with every repo (see "Resume here").
2. Optional speed-ups not done (estimates): fuse the CG vector passes in `solve.rs:143` (exact, 25–35% of the solve); pass the existing edge list into `fair` instead of rebuilding it (`fair.rs:102`); profile `gingiva::gum_weights` (8.8 + 5.7 s on pair ab, outside the build).
3. Done 2026-11-15: website live on `2cbe845` (`REDACTED-REVISION`, see "Resume here"); the planned `sha-ba97e88` rollout is superseded.
4. Fixed (2026-11-15, with the installers; the `binaries.yml` change was authorized by the user): the release archives bundle `LICENSE.md`, `THIRD-PARTY-NOTICES.md`, the font licences and `install-kind`.

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

- Fixed 2026-11-15: the release archives bundle `LICENSE.md` and `THIRD-PARTY-NOTICES.md` (installers work in `binaries.yml` and `release-local.sh`, authorized by the user).
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

- `feat/port-b0` in core, aligners and app: old port work, local only.
- No longer parked: `fix/model-stamps` (`03be70d`) and `wip/standard-export` (`04e471b`) are in `feat/production` of `dentalcraft-aligners` (2026-11-14, not committed yet): the model stamps kept, the Standard aligners 1 of the golden arches pass the print check.

## Parked: Windows code signing with SSL.com eSigner (apply only when the user asks)

- **Now:** every release signs the Windows programs and installers with a self-signed certificate (decision of 2026-11-18). The key is in `~/.config/dentalcraft-release/authenticode/`, SHA-256 fingerprint `24DD542E…DCF0AA26`. Windows does not trust it: SmartScreen still warns and the publisher shows as unknown. The release notes print the fingerprint. Details: `docs/local-ci.md` (Authenticode) and `dentalcraft-app/packaging/README.md` (how to trust the certificate on a Windows PC).
- **History:**
  - Azure Artifact Signing was tried and dropped on 2026-11-18.
  - SSL.com eSigner was chosen: an OV certificate (~$129, 1 year) plus eSigner Tier 1 (~$180/year, 240 signings). OV if SSL.com accepts the ditta individuale, otherwise IV.
  - The eSigner version was written (helper, workflow, `release-local.sh`, docs), then parked: self-signed for now. It has never signed with a real SSL.com certificate.
- **Where:** `~/.config/dentalcraft-release/parked/authenticode-esigner/`, not committed:
  - `dentalcraft-app.patch` and `superproject.patch` go from the self-signed version to the eSigner one, `git apply` in each repository;
  - `README.md`: how to apply, the `esigner.env` contract, the sandbox test, the pinned SSL.com roots.
  - The Italian step-by-step guide `docs/windows-code-signing.md` comes back with `superproject.patch`.
- **User steps before applying:**
  1. Ask SSL.com support whether OV can be issued to the ditta individuale (otherwise IV).
  2. Buy the certificate and eSigner Tier 1.
  3. Complete the validation.
  4. Enroll eSigner with **OTP APP** and save the `secret code` shown with the QR code.
  5. Fill `~/.config/dentalcraft-release/esigner.env` (0600): `ESIGNER_USERNAME`, `ESIGNER_PASSWORD`, `ESIGNER_CREDENTIAL_ID`, `ESIGNER_TOTP_SECRET`.
- **Gap (both versions):** the NSIS uninstaller `uninstall.exe`, written by the setup at install time, is not signed.

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
