# Port plan: Blender plugin → Rust, with CLI and MCP (2026-10-31)

Working mode: local only (see CLAUDE.md "Current mode"). Paths: P = `blender-ortho-aligner/ortho_aligner/`, C = `dentalcraft-core/crates/`, A = `dentalcraft-aligners/crates/`, X = `dentalcraft-app/crates/`.

## Starting point
- `dc-geom` is all stubs (bvh, icp, qem, holefill, sdf, sparse); the API contracts are already defined. `dc-mesh` is real. `X/dc-viewport/src/bvh.rs` has a working ray-cast BVH that can move into dc-geom.
- Every dca-algo stage is a stub. `dca-model::AlignersState` already holds seeds, labels, frames, diagnosis, setup and stages.
- `dc-command` has no params registry: `Command::apply(&CaseState, &JobCtx)` takes no parameters.
- Most of the plugin is pure numpy; `tests/unit/_carica.py` loads it without bpy. numpy and Blender 5.2.2 are installed locally. Only decimation, the Geometry Nodes/OpenVDB shell, stamp booleans and fill_holes need Blender.
- No Teeth3DS data on this machine. `P/demo.py` generates a synthetic arch with ground-truth labels, so its fixtures can be committed.
- `P/api.py` is the command surface to copy. ArtCraft CLIs (`/usr/bin/*craft-cli`) use hand-rolled JSON-RPC MCP (protocol 2025-06-18, serde_json, no tokio).

## Validation (does not block the port)
1. Port-time tests on synthetic meshes and the Rust demo arch. Compute in f64.
2. Tier A oracle without Blender: `dentalcraft-aligners/golden/oracle.py` loads the plugin modules with system python + numpy and dumps JSON/.dcm per stage. Compare each stage on its own, fed the oracle's intermediate inputs. Tolerances as in PLAN §5.
3. Tier B with Blender (`blender -b --factory-startup -P golden/blender_dump.py`): demo scans and decimated meshes in B1; full pipeline, shell and stamp later.
4. Teeth3DS: `#[ignore]` tests on `$DC_TEETH3DS`. Never commit the data.

## CLI and MCP
- `CommandSpec { id, label_key, doc_key, params_schema, run(&CaseState, &Value, &JobCtx) }` in dc-module-api, plus `Module::command_specs()` with an empty default. Schemas come from schemars.
- `C/dc-session` (headless): project, CaseState, UndoStack, StepHistory, JobSystem, registry; execute, batch, inspect; built-in commands project.*, case.import, edit.undo/redo, steps.*, view.set.
- `C/dc-mcp`: hand-rolled JSON-RPC over stdio behind a `Host` trait (headless Session or RemoteHost over TCP). Tools: list_commands, describe_command, execute, batch, inspect, render, screenshot, open, save, new_project, import_scan, undo, redo, steps, auto_analyze, stage_info, export.
- `X/dc-cli` (binary `dentalcraft-cli`): info, run, commands, describe, render, app, mcp [--connect PORT]. Headless render uses a CPU rasteriser in `C/dc-raster`.
- Bridge mode: `dc-app --control <port>` (127.0.0.1 TCP, dispatched on the UI thread). `screenshot` reads back the viewport texture.
- Each stage defines `dca_algo::<stage>::run(&Input, &Params)` and registers it with `A/dca-module/src/commands/<stage>.rs` via `stage_command!`. A menu item is Ready if and only if its command is registered.

## Plugin → Rust map
| Plugin | Rust target |
|---|---|
| worldframe, archform, anatomy, evidence, meshutil | `A/dca-algo/src/{frame,archform,anatomy,evidence}.rs` |
| demo.py | `demo.rs` |
| autoseed, case_auto.auto_seeds | `autoseed.rs` |
| segmentation, case_teeth | `segmentation.rs` |
| teeth.py | `teeth.rs` |
| reconstruct, gingiva | `reconstruct.rs`, `gingiva.rs` |
| planning, classify | `diagnosis.rs` |
| setup_conservativo | `setup.rs` |
| staging, schedule | `staging.rs`, `schedule.rs` |
| occlusion, bite | `occlusion.rs`, `bite.rs` |
| aligner_bite, ramps | `bite.rs`, `ramps.rs` |
| aligner, case_print (gpu_sdf as reference) | `shell.rs`, `trim.rs` |
| stamp | `stamp.rs` (text cut into the SDF) |
| printcheck, case_export, report | `export.rs` (rayon) |
| visit | `visits.rs` |
| manual | `A/dca-module/src/manual/` |
| steps.py | already `C/dc-command/src/steps.rs` |

Not ported: GPU kernels, engine*, export_worker (rayon replaces it), jev, livetest.

## Batches
- **B0** (1 agent): CommandSpec and registry, `commands/` stubs, menu status from the registry, workspace dependencies (schemars, nalgebra, kiddo, png, clap), `C/dc-geom/src/metrics.rs`, `golden/` skeleton, per-stage .ftl sections.
- **B1** (5 agents): 1.1 dc-session + dc-mcp · 1.2 BVH/KNN (WP13) · 1.3 sparse PCG/cotan (WP17) · 1.4 anatomy/archform/evidence/frame/demo · 1.5 golden harness (Tier A + Tier B demo).
- **B2** (6 agents): 2.1 dc-cli + dc-raster + bridge · 2.2 frame + autoseed · 2.3 segmentation · 2.4 QEM + ICP · 2.5 teeth · 2.6 SDF core (critical path).
- **B3** (5 agents): 3.1 reconstruct + gingiva · 3.2 diagnosis · 3.3 setup · 3.4 staging, schedule and slice export · 3.5 app wiring, occlusion and bite. **This batch completes the vertical slice.**
- **B4** (5 agents): shell/model/blockout · full export + report · stamp · aligner bite + ramps · visits.
- **B5** (4 agents): trim · manual tools · review UI + presets · Tier B full-pipeline checks.

Vertical slice (end of B3): import STL → frame/autoseed → segmentation → teeth → diagnosis → setup → staging → per-stage models + CSV + ICS, through `aligners.auto` in the app and the CLI.

- **B6** (after the final release build, requested 2026-10-31): automatic orthodontic study model trimming ("squadratura dello zoccolo ortodontico") on the 3D model. European and American (ABO) styles, chosen by the user in settings. Exposed as commands (CLI/MCP), with a menu leaf and en/it strings.

## Risks and libraries
- Risks: SDF speed and memory (sparse blocks are required), reproducing segmentation's deterministic CG, `reconstruct.close_crown` heuristics, trim (about 4450 lines), autoseed DP, manifold-safe QEM.
- Use: kiddo, nalgebra, schemars, clap, png, ttf-parser (+ lyon or i_overlay); faer optional.
- Avoid: meshopt, openvdb, manifold (C++); rmcp (tokio); parry3d.
