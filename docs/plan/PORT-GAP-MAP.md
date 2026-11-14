# Port gap map: Blender plugin → DentalCraft (2026-11-14)

Every user-facing function of the plugin, in workflow order, with its counterpart in the port and what is still missing. Verified in code on `feat/setup-alignment` (aligners, app), based on `feat/teeth-components`. Hints came from [`PORT-PLAN.md`](PORT-PLAN.md), [`HANDOFF.md`](HANDOFF.md) and [`HANDOFF-2026-10-31.md`](HANDOFF-2026-10-31.md).

Paths:
- **P** = `blender-ortho-aligner/ortho_aligner/` (read-only oracle)
- **C** = `dentalcraft-aligners/crates/dca-module/src/commands/`
- **M** = `dentalcraft-aligners/crates/dca-module/src/`
- **A** = `dentalcraft-aligners/crates/dca-algo/src/`
- **T** = `dentalcraft-aligners/crates/dca-algo/tests/`
- **W** = `dentalcraft-app/crates/dc-workspace/src/`
- **TD** = `M/tree_data.rs` (menu leaves and tools)
- **FN** = `W/function.rs:88-133` (`FUNCTIONS`, what each inspector shows)

Status:
- **DONE**: ported and reachable as a command (CLI/MCP), tested. That means a plugin oracle where the plugin gives numbers, or unit and UI tests for an interactive tool, which has no numeric oracle.
- **PARTIAL**: ported in part. The missing pieces are listed.
- **STUB**: present in the UI but only answers "not available yet".
- **MISSING**: no command and no UI. "By decision" means PORT-PLAN chose not to port it.
- **N/A**: specific to Blender, with nothing to port. Not counted.

Menu law: the inspector of a leaf must show its parameters, its run button and its manual tools. An inspector that FN does not list shows only its run button (`W/function.rs:329` tests this for the bite). This is counted as a UI gap.

## Summary

| Status | Rows |
|---|---|
| DONE | 36 |
| PARTIAL | 33 |
| MISSING | 19 (2 by decision: AI classifier, live test) |
| STUB | 4 |
| N/A | 5 |

Cross-cutting known defects:
- **719-stage anomaly.** Fixed on 2026-11-14 (branch `feat/setup-alignment`, not committed). Every quaternion, rotation vector and angle conversion now goes through `A/rotation.rs` and takes the shortest rotation (see HANDOFF.md, "Fixed (2026-11-14)"). On real scan d (`T/planning_real.rs`), the port and the plugin both give 12 aligners.
- **Setup overlaps.** Not a port defect. The "up to 2.6 mm" figure is the staging's residual overlap of the closed crowns, which already overlap at rest. On the same inputs the plugin gives the same numbers (`T/planning_real.rs`, scan d).
- **Standard quality export (0.1 mm).**
  - It fails the print check: "trim: 3 holes through the wall" on all 12 upper aligners.
  - It takes about 22 min, with the shell at about 23 s per stage per arch.
  - The fix is parked on branch `wip/standard-export` (`04e471b`).
- **Model stamps dropped.** The model stamps are dropped with "text does not fit" since the embrasure fills went in. Parked on branch `fix/model-stamps` (`03be70d`).
- **Shell and trim deviations.** `contact_bridges` / `pair_bridge` are not ported (`A/shell.rs:49-53`, `A/shell/embrasure.rs:24-26`).
- **In-progress work.** The 3D components gizmo (`feat/teeth-components`) is not committed. The gates, the release build and the manual check have not been run.

## 1. Case and import

| # | Plugin function | Port (command · algo · UI) | Status | Missing pieces / defects | Oracle / tests |
|---|---|---|---|---|---|
| 1.1 | `oa.import_scans` `P/ops_import.py:21`; drop on the view `OA_FH_scan` `:332` | `aligners.case.import-scans` `C/import.rs:43,52`; `TD:19`; IMPORT inspector (roles, scan list) `W/function.rs:76-81`; drop overlay `W/view.rs:1310` | DONE | — | `dca-module/tests/import_real.rs` (4 real scans, within 5 % of the plugin's counts) |
| 1.2 | Arch recognition (phase ARCATA `P/ui_phases.py:404`, `autoseed.detect_arch`) | `aligners.case.detect-arch` `C/import.rs:46,59`; run by `aligners.auto` and the find step; check on the built crowns `A/arch_check.rs` | DONE | — | `import_real.rs` (detection); unit tests |
| 1.3 | `oa.arch_set` (choose the arch by hand, renumber, flip the occlusal side) `P/ops_manual.py:827` | core `case.set-role` (`dentalcraft-core/crates/dc-session/src/builtins.rs:33`); role correction in the IMPORT scan list | PARTIAL | A role change clears the arch's results (`C/import.rs:959`) instead of renumbering seeds, colours and teeth; no manual flip of the occlusal side | unit |
| 1.4 | `oa.create_case` (Blender mesh as the case) `P/ops_import.py:79` | — | N/A | No Blender scene | — |
| 1.5 | `oa.demo` `P/ops_import.py:104` | `aligners.demo` `C/demo.rs:19`; `A/demo.rs` | DONE | CLI/MCP only; not in the menu (the plugin has it under "Altri modi di iniziare") | `T/foundations_oracle.rs` (demo replayed vertex by vertex), `T/autoseed_demo.rs` |
| 1.6 | `oa.make_base` (close an open scan with a base) `P/ops_seeds_seg.py:115`; `base_height` `P/props.py:385` | — (the shell model has its own `base_height_mm`, `A/shell.rs:157`) | MISSING | No command; the export already closes the models | — |
| 1.7 | `oa.auto_analyze` `P/ops_import.py:291`; `api.auto` `P/api.py:210` | `aligners.auto` `C/auto.rs:88`; `TD:25` | PARTIAL | The bite before the final position is done (2026-11-14). With two arches not related, the bite runs between diagnosis and setup, with the plugin's warning (`P/case_auto.py:424-434`). Still missing: no classifications step; no `start` step; all or nothing (the plugin keeps the finished phases on Esc) | `dc-cli/tests/aligners_pipeline.rs`; `C/auto.rs` tests (plugin order, bite before the setup) |
| 1.8 | `oa.align_world` (world frame) `P/ops_view_anim.py:34`, `worldframe.py` | `aligners.frame` `C/frame.rs:15`; `A/frame.rs` | DONE | — | `T/foundations_oracle.rs`; `T/autoseed_real.rs` (frame within 0.05 mm / 0.05°) |

## 2. Find the teeth (numbering)

| # | Plugin function | Port | Status | Missing pieces / defects | Oracle / tests |
|---|---|---|---|---|---|
| 2.1 | `oa.auto_seeds` `P/ops_seeds_seg.py:133`; `include_third_molars`, `missing_teeth` `P/props.py:376,680` | `aligners.teeth.find` `C/wrappers.rs:36,50` (numbering `C/autoseed.rs:46`, orientation `:39`); settings `aligners.settings.find-teeth` `C/autoseed.rs:63`; `A/autoseed.rs` (+`autoseed/*`); FN FIND_TEETH (module inspector `M/lib.rs:162`) | DONE | — | `T/autoseed_oracle.rs`, `T/autoseed_demo.rs`, `T/autoseed_real.rs` (4/4, about 1e-14 mm) |
| 2.2 | `oa.place_seeds` (click the teeth in order; S skip, Backspace, Enter) `P/ops_seeds_seg.py:14` | `aligners.preparation.numbering.sequence` `C/manual.rs:51`; numbering in order `W/manual.rs:277-310` | DONE | — | `M/manual/tests.rs`, `W/manual.rs` tests |
| 2.3 | `oa.seed_at_cursor` `P/ops_seeds_seg.py:85` | `aligners.preparation.numbering.place-seeds` `C/manual.rs:37`; Tool::Seeds `TD:153` | DONE | — | unit |
| 2.4 | (port only) delete one mark | `…numbering.delete-seed` `C/manual.rs:44`; Tool::Delete `TD:159` | DONE | — | unit |
| 2.5 | `oa.clear_seeds` `P/ops_seeds_seg.py:101` | `…numbering.clear-seeds` `C/manual.rs:58`; `W/manual.rs:47` | DONE | — | unit |
| 2.6 | `oa.label_renumber` `P/ops_manual.py:555` | `…numbering.renumber` `C/manual.rs:23`; Tool::Renumber `TD:165` | DONE | — | unit |
| 2.7 | `oa.tooth_set_missing` `P/ops_manual.py:611` | `…numbering.mark-missing` `C/manual.rs:30`; Tool::Missing `TD:171` | DONE | — | unit |
| 2.8 | Seed check after the separation, crown-width loop (`segmentation.renumber_spans`, `plan_corrections`) | `aligners.preparation.segmentation.check` `C/seed_check.rs:46`; `A/seed_check.rs` | DONE | — | `T/seed_check_oracle.rs` |

## 3. Separate teeth and gum (segmentation)

| # | Plugin function | Port | Status | Missing pieces / defects | Oracle / tests |
|---|---|---|---|---|---|
| 3.1 | `oa.segment` `P/ops_seeds_seg.py:167`; `rw_faces`, `rw_eta_convex`, `rw_sigma` `P/props.py:379-384` | `aligners.preparation.segmentation.automatic` `C/segmentation.rs:52,60`; settings `aligners.settings.segmentation` `:54,67`; `A/segmentation.rs` (+`segmentation/*`); FN SEGMENT (params, results, note) `TD:46` | DONE | Worst tooth IoU 0.83 (last molar 17 of scan b) with the port's own QEM | `T/segmentation_oracle.rs` (6 demo), `T/segmentation_real.rs` (agreement 1.0 with Blender's decimation; 0.995-0.998 with the port's QEM) |
| 3.2 | `oa.label_paint` + `oa.label_paint_end` `P/ops_manual.py:149,493` | `…segmentation.manual-brush` `C/manual.rs:9` (paint, erase, fill, stroke, `view_dir`, `only_over`; `M/manual/brush.rs:54`); Tool::Brush (key B) `TD:177` | DONE | — | `M/manual/tests.rs`; `W/tests/save.rs` |
| 3.3 | `oa.label_assign` / `oa.assign_selection` (selection in Edit Mode) `P/ops_manual.py:516`, `P/ops_seeds_seg.py:199` | brush `vertices` parameter (`M/manual/brush.rs:63`), CLI only | PARTIAL | No box or lasso selection in the viewport | unit |
| 3.4 | `oa.label_clean` `P/ops_manual.py:667` | `…segmentation.clean-borders` `C/manual.rs:16`; Tool::Clean `TD:184` | DONE | — | unit |

## 4. 3D teeth

| # | Plugin function | Port | Status | Missing pieces / defects | Oracle / tests |
|---|---|---|---|---|---|
| 4.1 | `oa.build_teeth` `P/ops_seeds_seg.py:222` | `aligners.teeth.build` `C/wrappers.rs:57` (`C/teeth_build.rs`: `aligners.teeth.frames` `C/teeth.rs:27`, reconstruction `C/reconstruct.rs:33`, gingiva `C/gingiva.rs:24`, diagnosis); `A/teeth.rs`, `A/reconstruct.rs` (+`reconstruct/*`), `A/gingiva.rs`; FN BUILD_TEETH (results, out of date) `TD:53` | DONE | b/24 diverges by 3.4e-2 mm (rounding, within the 0.1 mm bound); gum deformation tested only on synthetic data; 19 s on pair ab | `T/teeth_oracle.rs`, `T/reconstruct_oracle.rs`, `T/gingiva_oracle.rs`, `T/teeth_real.rs` (4/4) |
| 4.2 | `oa.tooth_rebuild` (one tooth, or the changed teeth) `P/ops_manual.py:759` | `aligners.manual.rebuild-tooth` `C/manual.rs:65` (`vertices`, `resegment`; `M/manual/rebuild.rs:34`); `…reconstruction.rebuild-tooth` `C/reconstruct.rs:40`; Tool::Rebuild; partial rebuild in `teeth.build` | DONE | — | unit; `W/tests/outdated_teeth.rs` |
| 4.3 | `oa.tooth_highlight` / `_end` (crown region and yellow margin line) `P/ops_manual.py:703,741` | — | MISSING | No view of one tooth's region and margin | — |
| 4.4 | 3D components: select, outline, gizmo (plugin `oa.tooth_grab` `P/ops_plan.py:128`, no scaling) | `aligners.components.transform` `C/components.rs:37`; `W/select.rs:56`; outline and gizmo in `dc-viewport` | PARTIAL | On `feat/teeth-components`, not committed: gates, release build and manual check not run. The port allows a tooth scale (user requirement); the plugin forbids it | `C/components.rs` tests |

## 5. Diagnosis

| # | Plugin function | Port | Status | Missing pieces / defects | Oracle / tests |
|---|---|---|---|---|---|
| 5.1 | `oa.analyze` `P/ops_plan.py:10` (`case_plan.analyze`: space, crowding, Little, CAT-CAT, level) | `aligners.diagnosis.space-analysis` `C/diagnosis.rs:38`, `…little-index` `:45`, `…bolton` `:52`, `…complexity` `:59`; `A/diagnosis.rs`; FN CASE_ANALYSIS results `TD:66` | DONE | Bolton is not oracle-tested (the demo cases have one arch) | `T/diagnosis_oracle.rs` (6 demo cases) |
| 5.2 | `oa.diagnosis_edit` (clinician's own values; complexity follows them) `P/ops_manual.py:883` | — (`C/diagnosis.rs:312` asserts that `aligners.diagnosis.edit-values` is absent) | MISSING | Command, model field and inspector controls | — |
| 5.3 | Per-tooth crown type and plausibility (`classify.segmentation_plausible`, `tooth_type`) | `classification` block of `C/diagnosis.rs:139-160`; `A/diagnosis/classify.rs:89` | DONE | Not shown in the UI | unit |

## 6. Bite and occlusion

| # | Plugin function | Port | Status | Missing pieces / defects | Oracle / tests |
|---|---|---|---|---|---|
| 6.1 | Phase MORSO page (bite report, scan slots, register, 3 points, virtual) `P/ui_phases.py:771` | leaf `aligners.occlusion.align` `C/wrappers.rs:41,64` (ICP with a bite scan, else virtual, then the contact map); `TD:79` | PARTIAL | Only a run button in the inspector (`W/function.rs:329`): no report (verdict, RMS, teeth, area, side agreement), no scan slots, no 3-point tool, no correction button | `C/bite.rs` tests |
| 6.2 | `oa.import_bite` `P/ops_occlusion.py:86` | import-scans with role `bite` (`C/import.rs:90,177`; `W/import.rs:56`) | DONE | — | `C/import.rs:877` tests |
| 6.3 | `oa.register_bite` `P/ops_occlusion.py:122` (`bite.py`) | `aligners.occlusion.bite-registration.icp` `C/bite.rs:31`; `A/bite.rs:1260` `register` | PARTIAL | No plugin oracle (tests run only on the synthetic `demo_bite_scan` `A/bite.rs:1456`); no real bite scan in the test data | unit |
| 6.4 | `oa.bite_points` (3 points per arch) `P/ops_occlusion.py:348` | `…bite-registration.three-points` `C/bite.rs:38` | PARTIAL | CLI only; no picking in the viewport; no oracle | unit |
| 6.5 | `oa.bite_correct` (lift the upper arch to the first contact) `P/ops_occlusion.py:501` | — (`A/occlusion.rs:917` `first_contact` exists) | MISSING | Command and button | — |
| 6.6 | `oa.occlusion` (virtual bite) `P/ops_occlusion.py:16` | `aligners.occlusion.virtual-bite` `C/occlusion.rs:32`; `A/occlusion.rs:767` `align` | DONE | — | `T/occlusion_oracle.rs` (height grid, first contact) |
| 6.7 | `oa.contact_map` `P/ops_occlusion.py:525` | `aligners.occlusion.contact-map` `C/occlusion.rs:39`; contacts layer `W/view.rs:1048-1060`, legend `W/view.rs:1708` | DONE | Computed on the UI thread; drawn on the scans (the plugin shows it at the stage shown) | `T/occlusion_oracle.rs` (contact distances) |

## 7. Setup (final position) and movements

| # | Plugin function | Port | Status | Missing pieces / defects | Oracle / tests |
|---|---|---|---|---|---|
| 7.1 | `oa.auto_setup` `P/ops_plan.py:24`; parameters `cons_*`, `midline`, `priority`, `expansion_*`, `advance_max`, `retract_max`, `ipr_*`, `leveling`, `vertical_max`, `close_spaces` `P/props.py:388-468`; page `P/ui_phases.py:579` | `aligners.planning.setup.automatic` `C/setup.rs:34`; `A/setup.rs` (`Params` `:1871`, `setup/line.rs`, `setup/crown.rs`); FN SETUP (only the Adjust tool) `TD:85` | PARTIAL | See the list below the table | `T/setup_oracle.rs` (6 demo cases, one arch, no lock, no line, no opposing arch) |
| 7.2 | `oa.reset_setup` `P/ops_plan.py:43` | — (per-tooth reset only, see 7.3) | MISSING | A command to clear the whole final position | — |
| 7.3 | `oa.adjust_tooth`, `oa.reset_tooth`, `oa.setup_tooth_edit`, lock (`OA_Tooth.locked` `P/props.py:274`) `P/ops_plan.py:90,114`, `P/ops_manual.py:921` | `aligners.planning.movements` `C/manual.rs:72` (clinical components, `delta`, `absolute`, `reset`, `lock`, `stage`, `refuse_on_collision`; `M/manual/adjust.rs:77`); Tool::Adjust `TD:190`, `W/manual.rs:1345-1349` | PARTIAL | No −/+ step buttons with a step size (`adjust_step_mm`/`_deg`); no per-tooth movement flags (`A/diagnosis/classify.rs:153` unused); no exact absolute clinical values | unit |
| 7.4 | `oa.tooth_grab` / `_end` (gizmo on the tooth axes, centre of resistance) `P/ops_plan.py:128,179` | `aligners.components.transform` + `W/select.rs` | PARTIAL | Same branch as 4.4 | `C/components.rs` tests |
| 7.5 | `oa.arch_line_show` / `_edit` / `_apply` / `_reset` / `_hide` `P/ops_plan.py:200-303` | setup `line` parameter `A/setup.rs:1936`; stored `Setup::lines` | PARTIAL | CLI only: no line in the viewport, no point editing, no "save without recompute", no back to automatic | `C/setup.rs:507-535` test |
| 7.6 | Ghost of the final target (`ghost_final` `P/props.py:711`) | layer "target" `W/view.rs:1066` → toast "not available" | STUB | Draw the final pose ghost | — |

Gaps of 7.1:
- (a) Fixed: it was the source of the 719-stage anomaly (quaternion `w < 0`).
- (b) Not a defect: the overlaps are the closed crowns' own, the same in the plugin (see above).
- (c) Corrected on 2026-11-14. The plugin does **not** coordinate the upper arch line with the lower one: in plugin 42e6d87, `coordination()` (`P/case_plan.py:150`) is dead code (`run_setup` sets `coord = None`, nothing calls `_setup_line()`, `coord_changed()` returns False). The two live parts are ported (2026-11-14):
  - The refusal when both arches have their teeth and are not related (`:386-389`): `A/occlusion.rs` `bite_needed` and `C/setup.rs`. The Final position inspector shows "Bite first", pointing to Bite.
  - In auto, the virtual occlusion before the setup (`P/case_auto.py:424-434`), see 1.7.
- (d) No parameters in the inspector and no `aligners.settings.setup`: the parameters exist only as CLI overrides.
- (e) The result is not shown: expansion, advancement, IPR total, distalisation, residual crowding, log lines.

## 8. Staging, aligners and calendar

| # | Plugin function | Port | Status | Missing pieces / defects | Oracle / tests |
|---|---|---|---|---|---|
| 8.1 | `oa.staging` `P/ops_plan.py:57`; `perio`, `pattern`, `step_*`, `max_crown_step`, `collision*`, `overcorrection` `P/props.py:470-498` | `aligners.planning.staging.automatic` `C/staging.rs:43`; leaf `aligners.planning.aligners` `C/wrappers.rs:71` (staging + calendar) `TD:91`; `A/staging.rs`; `StagingSettings` in `dca-model/src/settings.rs` | PARTIAL | The 719-stage anomaly at `A/staging.rs:540-541`; no parameters in the inspector and no settings command (the stored `StagingSettings` cannot be changed); no result line (aligners, days, pattern, slowed teeth, collisions left) | `T/staging_oracle.rs` (6 demo cases: poses, phases, IPR timing) |
| 8.2 | Calendar: `start_date`, `interval_policy` FIXED/ADAPTIVE, `interval_days` `P/props.py:499,726-732`; `schedule.py`; `api.calendar` `P/api.py:391` | `aligners.planning.schedule` `C/schedule.rs:26` (start, interval, policy, attachments); `A/schedule.rs` | DONE | The leaf passes only `start_date` and `interval_days`, not the policy (`C/wrappers.rs:181-188`); none of them in the UI | `T/staging_oracle.rs::the_calendar_matches_the_plugin` |
| 8.3 | `oa.tooth_speed` (slow one tooth) `P/ops_manual.py:978` | — (`ToothMove.speed` `A/staging.rs:281` is set only from a visit, `C/visits.rs:754`) | MISSING | Command and stored per-tooth speed | — |
| 8.4 | Player: `oa.stage_step`, `oa.play`, stage slider `P/ops_view_anim.py:85,105`, `P/ui_common.py:260-272` | `W/timeline.rs:143` (step, play at 0.6 s per stage, Home/End, slider), stage-0 ghost `overlay0` | DONE | See 17.6 and 17.7 for interpolation and the clock | `W/timeline.rs` tests, `W/view.rs:2218` |

## 9. Clinical review (classifications)

| # | Plugin function | Port | Status | Missing pieces / defects | Oracle / tests |
|---|---|---|---|---|---|
| 9.1 | `oa.classify` `P/ops_review.py:13` (`review.py`, `classify.py`): complexity, staging pattern, suitability, movement risk and attachment per tooth, segmentation, tooth type | — (algorithm parts in `A/diagnosis/classify.rs`: `movement_flags` `:153`, `attachment_rule` `:274`, `complexity_math` `:295`, `choose_pattern` `:328`, not used by `dca-module`) | MISSING | Records model, command, leaf and inspector | unit tests of `classify.rs` only |
| 9.2 | `oa.review_decide`, `oa.review_set_value`, `oa.review_bulk`; `OA_ClassRecord` `P/props.py:227`; filter `P/props.py:689` | — | MISSING | Decisions (confirm, value, reset, confirm all without notes) | — |
| 9.3 | AI classifier (`jev.py`), `oa.ai_test`, `oa.open_prefs`, `oa.ai_guide` `P/ops_misc.py:248,268,283` | — | MISSING (by decision) | PORT-PLAN: "Not ported: jev" | — |

## 10. Attachments

| # | Plugin function | Port | Status | Missing pieces / defects | Oracle / tests |
|---|---|---|---|---|---|
| 10.1 | Attachment indication per tooth (review kind `attachment`, `classify.attachment_rule` `P/classify.py:108`); "bond the attachments" in the calendar `P/schedule.py:98-99` | `A/diagnosis/classify.rs:274` (unused); schedule `attachments` parameter `C/schedule.rs:48`; the export passes an empty map (`C/export.rs:387-388`) | PARTIAL | Wire it through the review (9.1); feed the calendar and the report | unit |
| 10.2 | Attachment geometry (not in the plugin either; ANO-001 open) | layer "attachments" `W/view.rs:1063` → "not available" | STUB | Data model decision pending | — |

## 11. IPR

| # | Plugin function | Port | Status | Missing pieces / defects | Oracle / tests |
|---|---|---|---|---|---|
| 11.1 | IPR planned by the setup and timed by the staging | `Setup::ipr`, `Stage::ipr` (`dca-model/src/state.rs:152,176`); `IprPlan` in staging | DONE | — | `T/setup_oracle.rs`, `T/staging_oracle.rs` (IPR timing equal) |
| 11.2 | IPR in the calendar and the report | `A/schedule.rs:330` ("IPR a\|b mm"), report tables | DONE | — | `T/staging_oracle.rs` (calendar) |
| 11.3 | IPR shown in the view and the totals on the final-position page | layer "IPR" `W/view.rs:1064` → "not available" | STUB | Marks at the contacts, totals in the inspector | — |

## 12. Shell, trim and aligner models (Production sections 2-5)

| # | Plugin function | Port | Status | Missing pieces / defects | Oracle / tests |
|---|---|---|---|---|---|
| 12.1 | Shell and printable model (`aligner.py`, `case_print.py`) | `aligners.production.shell.automatic` `C/shell.rs:37`, `…base-labels` `:44`, `…blockout` `:51`; `A/shell.rs` (+`shell/cast.rs`, `shell/embrasure.rs`) | PARTIAL | `contact_bridges`, `pair_bridge` and `_tuck_below_margin` not ported (`A/shell.rs:49-53`); about 23 s per stage per arch at 0.1 mm; base-labels: "the labels are not part of it yet" (`C/shell.rs:9`) | `T/shell_oracle.rs` (coarse stage; full resolution and OpenVDB comparison are `#[ignore]`) |
| 12.2 | Trim line: `trim_mode` EQUATOR/STRAIGHT/SCALLOPED/SMOOTH, `insertion_axis`, `trim_margin_gap`, `trim_scallop`, `trim_recess`, `trim_equator_offset`, `trim_extension` `P/props.py:545-593` | `aligners.production.trim-line` `C/trim.rs:42`; `A/trim.rs` (+`trim/*`); case `TrimParams` (`dca-model/src/settings.rs`) | PARTIAL | Not ported: bars over gaps, `fill_out`, plugs and slots, equator refinements, panel checks (`A/trim.rs:49-52`, `A/trim/cutter.rs:220`). Standard quality: 3 holes through the wall. `insertion_axis` and `recess_mm` are not used from the case. No settings command or UI | `T/trim_oracle.rs` (1e-6 mm on synthetic teeth) |
| 12.3 | `shell_thickness`, `clearance` `P/props.py:594-596` | `Settings.shell_thickness_mm`, `clearance_mm` (`dca-model/src/settings.rs`), per-command overrides | PARTIAL | No settings command or UI | unit |
| 12.4 | Bite with the aligners worn (`occlusal_mode`, `occlusal_thickness`, `bite_opening_target`, `bite_closing`, hinge, equilibration `P/props.py:600-637`; `oa.aligner_bite` `P/ops_occlusion.py:163`) | `aligners.occlusion.bite-with-aligners` `C/ramps.rs:44`; `A/aligner_bite.rs` (+`aligner_bite/occlusal.rs`) | DONE | No UI (see 12.11) | `T/aligner_bite_oracle.rs`, `T/aligner_bite_demo.rs` |
| 12.5 | Ramps: `oa.ramp_add`, `oa.ramps_propose`, `oa.ramps_remove`; `ramps_enabled`, sizes, `ramp_overbite_min` `P/ops_occlusion.py:217,288,322`, `P/props.py:646-661` | `aligners.occlusion.bite-ramps` `C/ramps.rs:51` (action add/remove/set, proposal); `A/ramps.rs` | PARTIAL | CLI only: no click to place, no move/turn/size of a selected ramp | `T/aligner_bite_oracle.rs` (shape, frame, overbite, proposal) |
| 12.6 | Where the aligner ends: `oa.aligner_end`, `oa.aligner_end_apply`, suggestions `P/ops_misc.py:96,132`, `aligner_end_right/left` `P/props.py:342-347` | setup `excluded` parameter (`C/setup.rs:108-121`) | PARTIAL | Not stored in the case; shell, trim and bite still cover every crown (`C/ramps.rs:603`); no suggestions; no "setup computed with another end" warning | `C/setup.rs:483` test |
| 12.7 | Stamp: `stamp_*` `P/props.py:515-542`; `oa.stamp_preview` `P/ops_misc.py:157` | `aligners.production.stamp` `C/stamp.rs:36`; `A/stamp.rs` (+`stamp/*`); `stamp` and `stamp_code` of the export | PARTIAL | Model stamps dropped with "text does not fit" (`fix/model-stamps` `03be70d`); stamp settings not stored and not in the UI; no preview on the shell | `A/stamp/tests.rs` (no oracle) |
| 12.8 | `oa.aligner_exact`, `show_aligner` (aligner shown in the view) `P/ops_view_anim.py:128`, `P/props.py:715` | — (the commands build the solids on demand and never show them) | MISSING | Aligner preview in the viewport | — |
| 12.9 | Manual aligner correction: `oa.aligner_edit`, `_apply`, `_discard`, `oa.aligner_edits_clean` `P/ops_export.py:361,445,553`, `P/ops_misc.py:322` | — | MISSING | Mesh editing (sculpt), re-solidify, certify, store per stage | — |
| 12.10 | Quality presets for the print files (`quality`, `export_voxel`, `shell_voxel`, `mesh_tolerance` `P/props.py:665-750`, `quality.py`) | `Quality` Draft/Light/Standard/High `A/export/provider.rs:33`; `voxel_mm` | PARTIAL | Standard fails the print check and takes about 22 min (`wip/standard-export` `04e471b`); no choice in the UI | unit |
| 12.11 | Aligner contacts and push arrows in the view (`view_bite.py`; `show_aligner_contacts`, `show_push`, `push_arrow_scale` `P/props.py:638-664`) | — | MISSING | Overlays | — |

## 13. Study models (B6, port only)

| # | Plugin function | Port | Status | Missing pieces / defects | Oracle / tests |
|---|---|---|---|---|---|
| 13.1 | None (user request 2026-10-31, `B6-STUDY-MODEL-TRIMMING.md`) | `aligners.output.study-models` `C/study_base.rs:30`, settings `:32`; `A/study_base.rs`; `M/inspector.rs:38`; `TD:114` | PARTIAL | Lower ABO side angle 64.4° (0.56° off); lower ABO arc built from 2.5° segments; no French or Tweed style; no hollowing or drain holes; no folder picker (the leaf has no Folder input) | `A/study_base/tests.rs` (no plugin oracle) |

## 14. Export and print

| # | Plugin function | Port | Status | Missing pieces / defects | Oracle / tests |
|---|---|---|---|---|---|
| 14.1 | `oa.export` `P/ops_export.py:200` (`case_export.py`, `export_parallel.py`; `export_arches`, `workflow`, `export_dir`, `export_workers` `P/props.py:502-513,675`) | `aligners.output.export-all` `C/wrappers.rs:78,218-232` (dir, quality, lang, stamp_code); `aligners.output.report` `C/export.rs:88` (`FullParams` `A/export/package.rs:63`: workflow, parallel...); `aligners.output.export-stl` `C/export.rs:67`; `TD:106` | PARTIAL | Standard quality fails and is slow; no arch choice; no first/last range or resume; `workflow` and quality not in the UI (only a run button) | `C/export.rs` tests (no oracle) |
| 14.2 | Print check (`printcheck.py`) | `aligners.output.print-check` `C/export.rs:74`; `A/export/printcheck.rs` | PARTIAL | `shell_reach` not ported (`A/export/printcheck.rs:18-20`) | unit |
| 14.3 | Manifest (resin ml, dates, quality line) | `aligners.output.manifest` `C/export.rs:81`; `A/export/manifest.rs` | DONE | — | unit |
| 14.4 | Report (`report.py`) | `aligners.output.report`; `A/export/report.rs`, `html.rs`, `text.rs` | PARTIAL | Missing: tracking and visit history, the review table, the trim and stamp description, the CAT-CAT items (`A/export/report.rs:11-14`); attachments are empty | unit |
| 14.5 | Patient programme (`schedule.patient_html`) | `A/export/patient.rs` | DONE | — | unit |
| 14.6 | `.ics` calendar and per-stage tables | export-stl and report (`A/export.rs`, `A/schedule.rs`) | DONE | — | `T/staging_oracle.rs` (calendar), unit |

## 15. Control visits and follow-up

| # | Plugin function | Port | Status | Missing pieces / defects | Oracle / tests |
|---|---|---|---|---|---|
| 15.1 | `oa.import_visit_scan` + `oa.new_visit` `P/ops_visit.py:15,33` (`visit.py`; `visit_last_aligner`, `visit_date`, `lag_speed` `P/props.py:807-813`) | `aligners.followup.visits` `C/visits.rs:62` (scan, arch, date, stage, thresholds, `lag_speed`, `segment`); `A/visits.rs`; leaf with ScanFile input `TD:129` | PARTIAL | Inspector: no parameters (last aligner, date, lag) and no tooth-by-tooth tracking (`P/ui_common.py:471`); no expected-position ghost (`ghost_expected` `P/props.py:712`) | `T/visits_oracle.rs`, `T/visits_synthetic.rs` |
| 15.2 | `oa.replan_from` (new plan from a delivered aligner) `P/ops_visit.py:82` | `aligners.followup.tracking` `C/visits.rs:69` | PARTIAL | No `replan_stage` in the UI; no oracle | unit |
| 15.3 | Treatment history and `oa.show_case` `P/ops_visit.py:109`, `P/ui_phases.py:1046` | data in `AlignersState::visits` | MISSING | History list and per-visit display | — |
| 15.4 | Visit-by-visit production (`treatment_mode` PROGRESSIVE, `aligners_per_visit`, `delivered`, `aligner_offset` `P/props.py:335-350`; `api.production` `P/api.py:511`) | — | MISSING | Model fields, export of the next delivery only | — |

## 16. Steps, re-plan and undo

| # | Plugin function | Port | Status | Missing pieces / defects | Oracle / tests |
|---|---|---|---|---|---|
| 16.1 | `oa.step_rewind` `P/ops_steps.py:32` | core `steps.rewind` (`dc-session/src/builtins.rs:41`, MCP `steps` tool) | PARTIAL | Headless only: the app bridge refuses it (`dentalcraft-app/crates/dc-app/src/control.rs:598`); no "Redo or go back" in the inspector | core tests |
| 16.2 | `oa.step_retry` (then the following steps) `P/ops_steps.py:75` | "Run again" of each leaf; `aligners.auto` | PARTIAL | No "redo this step and continue" | — |
| 16.3 | `oa.step_undo_rewind` `P/ops_steps.py:213` | `StepHistory::undo_rewind` `dentalcraft-core/crates/dc-command/src/steps.rs:474` | PARTIAL | No command, no UI | core tests |
| 16.4 | Blender undo | `edit.undo` / `edit.redo`; one undo step per command | DONE | — | `W/tests/save.rs` |
| 16.5 | Save the `.blend` | `.dcprj` save plus automatic save | DONE | — | `W/tests/save.rs`, `dc-app/tests/close.rs` |

## 17. View, display, help and other

| # | Plugin function | Port | Status | Missing pieces / defects | Oracle / tests |
|---|---|---|---|---|---|
| 17.1 | `oa.view` (occlusal, frontal, right, left, lingual) `P/ops_view_anim.py:13` | `ViewChoice` `W/view.rs:39` (occlusal, front, left, right, back) + view cube; core `view.set` | DONE | No lingual view (back instead) | `W/view.rs:2050` |
| 17.2 | `color_mode` MATERIAL/TOOTH/RISK/MOVEMENT/ACTIVE/TRACKING `P/props.py:717` | labels layer (TOOTH), enamel colour, contacts layer `W/view.rs:1048-1060` | PARTIAL | No RISK, MOVEMENT or TRACKING colours | `W/view.rs:1973` |
| 17.3 | `show_labels` (tooth numbers) `P/props.py:706` | numbers layer (`W/overlay.rs:29`, `labels.rs`) | DONE | — | `W/view.rs:2480` |
| 17.4 | `ghost_initial` `P/props.py:710` | `overlay0` `W/timeline.rs:56,179` | DONE | — | `W/view.rs:2564` |
| 17.5 | Series gallery (`show_series`, `series_step` `P/props.py:733-737`; `api.series`) | — | MISSING | — | — |
| 17.6 | Animation (`frames_per_stage`, `smooth_animation`, `sync_timeline` `P/props.py:698-703,677`) | fixed 0.6 s per stage (`W/timeline.rs:78`) | PARTIAL | No interpolation between stages; no speed setting | unit |
| 17.7 | Treatment clock (`show_hud`: aligner, day, date, events) `P/ui_common.py:269-272` | timeline readout (stage, week) | PARTIAL | No date or events (IPR, attachments) at the stage | unit |
| 17.8 | `oa.focus_tooth` `P/ops_view_anim.py:58` | — | MISSING | Frame one tooth | — |
| 17.9 | `oa.ortho_mode` `P/ops_view_anim.py:73` | — | N/A | Blender workspace | — |
| 17.10 | `oa.references` (bibliography) `P/ops_misc.py:212` | references of `A/evidence.rs`, listed in the report | PARTIAL | No bibliography in the app | `T/foundations_oracle.rs` (evidence) |
| 17.11 | `oa.open_manual` (`docs/manuale.html`) `P/ops_misc.py:234` | app documentation link is a stub | MISSING | User manual | — |
| 17.12 | `oa.live_test` (`livetest.py`, `collaudo_report.py`) `P/ops_misc.py:297` | — | MISSING (by decision) | PORT-PLAN: not ported | — |
| 17.13 | `oa.quality_answer`, `oa.quality_undo_limit`; view-detail presets (`gum_display`, `ghost_detail`, `preview_*`) `P/ops_misc.py:359,375` | — | N/A | Blender memory and display settings | — |
| 17.14 | `oa.phase`, `oa.step_manual` `P/ops_misc.py:17,63` | menu law: a click on a leaf only selects it and shows its inspector | N/A | — | — |
| 17.15 | Scripting surface `P/api.py` | `dentalcraft-cli` (run, commands, describe, render, mcp, `--connect`); core `dc-session`, `dc-mcp` | DONE | `status` and `summary` map to `inspect` | `dc-cli/tests` |
| 17.16 | Regulatory dossier (`blender-ortho-aligner/docs/regolatorio/`) | planned `dentalcraft-app/regulatory/` (PLAN §6) | MISSING | Folder absent; `cargo xtask trace --check` not written | — |
| 17.17 | (port only) measure, angle and section tools | `W/view.rs:1037-1047` → "not available" | STUB | — | — |
| 17.18 | GPU acceleration (`accel.py`, `gpu_*.py`, `kernels/`) `P/ui.py:94` | — | N/A | Not ported by decision (rayon on the CPU) | — |

## What to finish next (workflow order)

1. **3D teeth wrap-up**: gates, release build and commit of `feat/teeth-components` (4.4, 7.4); the tooth region view (4.3). Small.
2. **Case leftovers**: flip the occlusal side and renumber on an arch change instead of clearing (1.3); `make_base` (1.6). Small. (The bite before the setup in `aligners.auto`, 1.7, is done.)
3. **Diagnosis**: values entered by hand (5.2). Small.
4. **Bite**:
   - an inspector with the registration report, the bite scan slots and the 3-point picking (6.1, 6.4);
   - `bite_correct` (6.5);
   - a bite-registration oracle (6.3).

   Medium.
5. **Setup**:
   - the quaternion sign fix (719 anomaly) and the 2.6 mm overlaps;
   - the upper arch coordinated with the lower through the bite;
   - the parameters in the inspector and a settings command; reset setup (7.2);
   - showing and editing the arch line (7.5); the −/+ steps and the movement flags (7.3); the target ghost (7.6).

   Large.
6. **Staging and aligners**: the sign fix in `q_from_pose` and its siblings; parameters and calendar policy in the inspector; a staging settings command; slowing a tooth (8.3); the result line. Medium.
7. **Clinical review and attachment indication**: records, decisions, bulk, the attachment rule wired into the calendar and the report (9.1, 9.2, 10.1); IPR marks (11.3). Medium.
8. **Shell, trim and aligner design**:
   - contact bridges and the missing trim pieces;
   - the standard-quality holes and speed (`wip/standard-export`); the model stamps (`fix/model-stamps`);
   - aligner end stored and honoured (12.6);
   - trim, shell, stamp, aligner bite and ramp settings in the UI (12.2-12.7);
   - the aligner preview and contact overlays (12.8, 12.11).

   Large.
9. **Study models**: the lower ABO angle and arc, French and Tweed styles, hollowing and drain holes, a folder picker (13.1). Medium.
10. **Export and print**: arch choice, range and resume, report sections, `shell_reach`, the export inspector (14.1, 14.2, 14.4); visit-by-visit production (15.4). Medium.
11. **Visits**: inspector parameters, tracking display, history, the expected ghost, the re-plan UI (15.1-15.3). Medium.
12. **Steps**: undo-rewind command, bridge support, "Redo or go back" UI (16.1-16.3). Small.
13. **Display and help**: colour modes, series gallery, interpolation, clock, focus a tooth, manual and bibliography, regulatory dossier (17.x). Medium. The manual aligner sculpt (12.9) is large and needs a user decision.
