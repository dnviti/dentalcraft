# Printing from DentalCraft: Elegoo Saturn 4 Ultra 16K (plan, 2026-11-20)

This is a plan only; no code exists yet. It covers the last step of the workflow: from the open project, a dedicated popup prints the **aligners themselves** on the user's Saturn 4 Ultra 16K, in clear aligner resin.

Inputs:
- the printer research of 2026-11-20 (sources [S#] at the end);
- the user's printer (Device Details screen and a read-only SDCP probe, 2026-11-20 21:22);
- the user's answers of 2026-11-20 22:36;
- the code as it is today.

Paths: **C** = `dentalcraft-core/crates/`, **A** = `dentalcraft-aligners/crates/`, **X** = `dentalcraft-app/crates/`. [INFERENCE] marks reasoning, not a source.

## 0. In brief
- **v1 prints the directly printed aligner shells**, upper and lower, active and passive, in clear biocompatible aligner resin. Each shell is oriented on the plate and gets automatic supports on its outer (occlusal and buccal/lingual outer) surface only; the fitting side never touches a support. Thermoforming models come later, as an option.
- **v1 also tracks prints.** Each aligner (arch, stage, passive) is queued, sent, printed, failed or due for a reprint. The tracking is stored in the module state and saved in the `.dcprj`; the popup preselects what is missing.
- **New core crate `C/dc-print`.** Headless, pure Rust, and extensible like `dc-scanner`. It holds:
  - printer profiles and resin presets;
  - orientation, supports and plate nesting;
  - the scanline slicer and the GOO V3 writer and reader;
  - the printer backends: SDCP V3 over Wi-Fi, USB stick or folder, and a simulated printer;
  - the `print.*` commands.
- **New app crate `X/dc-print-ui`.** The generic print popup, hosted like `dc-scan-ui`. The aligners module gets the leaf **Production → Print** (`aligners.output.print`) and its tracking commands.
- **Verification without the printer.** No test prints happen until the user allows them. Until then the checks are a byte comparison with Elegoo SatelLite files on the Windows VM, read-only SDCP on the real printer (from Linux and from the VM) and the simulated printer. Test prints are a **gated milestone** (M6) that needs the user's approval.
- **Out of scope.** Washing and post-curing are done by the lab with professional equipment; the job summary only carries a post-processing note. There is no camera. There is no CTB writer, because CTB is encrypted. No AGPL or GPL code is used.

## 1. Goal and scope

| What | Today | To print it | When |
|---|---|---|---|
| Directly printed aligner shells (`stampa_resina/{SUP,INF}_allineatore_NN[_passivo].stl`) | 1.0 mm hollow cup (`shell_thickness_mm` 1.0, `clearance_mm` 0). Trimmed edge, bite ramps, stamp engraved. Passes the print check. Standard quality takes ≈ 67 s per aligner. Passive aligners are written only for the Direct workflow | Orientation; automatic supports, on the outer side only; nesting; clear-resin settings; compensation for printed walls coming out thicker | **v1** |
| Print tracking per aligner | none | Module state and `.dcprj`; shown in the inspector and the popup | **v1** |
| Thermoforming models (`modelli_termoformatura/*_modello_NN.stl`) | Solid, flat 3 mm base, stamp embossed | Flat on the plate, no supports | Later option (M7) |
| Study models (`aligners.output.study-models`) | Flat-based solids | Same path as the models | Later |

**What the printed shells need.** Clear aligner resin prints thin walls of ≈ 1.0 mm. Printed shells come out thicker than designed: the export already says so (`A/dca-algo/src/export/text.rs:465`). Post-curing also shrinks them and changes their thickness. The resin preset therefore carries compensation (XY erosion and clearance). Those values are measured in the gated test and are noted in every job summary.

## 2. Architecture

### 2.1 Who owns what

| Repo / crate | Change | Owns |
|---|---|---|
| core `C/dc-print` | new | Profiles and resin presets (data); printer store; orientation search; support generator; nesting; slicer; `SliceFormat` (GOO V3 writer and reader); `PrinterBackend` / `PrinterDevice` (`sdcp3`, `folder`, `sim`); `PrintController` with the `print.*` command infos; background jobs. No GPU and no UI strings, only stable error codes |
| core `C/dc-session` | changed | `print_specs()` beside `scan_specs()` (`builtins.rs`). The session owns one `PrintController` (headless CLI and MCP) |
| core `C/dc-module-api` | changed | `PrinterInput` on `MenuItem`, like `ScannerInput` (`menu.rs:49`) |
| aligners `A/dca-algo` | changed | The export writes per-shell **face labels** (fitting, outer, rim, stamp) next to each shell. The print-check plate comes from the chosen profile (`export/printcheck.rs:73`) |
| aligners `A/dca-model` | changed | `AlignersState::prints` (tracking), with a schema bump and a migration (older projects start with no prints) |
| aligners `A/dca-module` | changed | Leaf `aligners.output.print`; `aligners.output.print-parts`, `aligners.print.status`, `aligners.print.mark`; `printer` in `aligners.settings.production` |
| app `X/dc-print-ui` | new | The popup: printer, resin, what to print (missing preselected), plate preview with supports, estimates, Print, progress, job summary. Simple and advanced views, en/it |
| app `X/dc-workspace` | changed | Hosts the popup, hands it the parts, feeds job events back to the tracking, routes an agent's `print.*` |
| app `X/dc-app` | changed | Bridge specs and dispatch (`control.rs`, beside `scan_specs` at `:780`); the `Info.plist` key in `dentalcraft-app/packaging/macos` |
| `dentalcraft-web` | changed | Feature text, status and What's new at every release |

### 2.2 Extension points (printers are added the way scanners are)

```rust
pub trait PrinterBackend: Send + Sync {            // like dc_scanner::ScannerBackend
    fn id(&self) -> &'static str;                  // "sdcp3", "folder", "sim"
    fn discover(&self, o: &DiscoverOptions) -> Result<Vec<PrinterInfo>>; // quick, opens nothing
    fn open(&self, p: &PrinterInfo) -> Result<Box<dyn PrinterDevice>>;
}
pub trait PrinterDevice: Send {
    fn attributes(&self) -> Result<Attributes>;    // resolution, formats, memory, sizes, devices
    fn status(&self) -> PrinterStatus;             // last pushed state, never blocks
    fn upload(&mut self, file: &Path, name: &str, p: &Progress) -> Result<()>;
    fn start(&mut self, name: &str) -> Result<()>;
    fn pause(&mut self) -> Result<()>;  fn resume(&mut self) -> Result<()>;  fn stop(&mut self) -> Result<()>;
}
pub trait SliceFormat {                            // GOO V3 now; GOO V5 or other vendors later
    fn id(&self) -> &'static str;
    fn write(&self, plate: &SlicedPlate, out: &mut dyn Write) -> Result<FileSummary>; // streamed, MD5 on the fly
}
```

- **Profiles are data.** A profile holds:
  - how to match a discovered printer (`MachineName`, resolution);
  - the pixel pitch per axis and the build volume;
  - the formats, the backend and the defaults.
  
  Built in: the Saturn 4 Ultra 16K, and the Formlabs Form 3 as "plate check only". More profiles can be added as JSON in the data folder.
- **`sim`** is a simulated SDCP printer, in process: UDP reply, WebSocket and HTTP upload. Like the scanner's `sim`, it is always registered. It covers every write path until the gated milestone.
- **Generic parts.** A part is a closed mesh plus optional per-face labels in the project's `DCM1` blob format (per-face u16 labels). Supports may touch only faces labelled `outer`; with no labels, every face may be touched. Other modules and plain STL files use the same path.

### 2.3 Data flow

```
stages in the case
 └─ Export for printing (workflow Direct or Both) ─▶ stampa_resina/*_allineatore_NN[_passivo].stl + .dcm face labels + manifest.json
     └─ aligners.output.print-parts {stages, arches, passive, missing_only} ─▶ parts: shell, labels, name "SUP 03", group (arch, stage, passive)
         └─ print.parts ─▶ print.layout: orientation ─▶ supports ─▶ nesting ─▶ checks (no contact on the fitting side, every island supported)
             └─ print.slice ─▶ per plate .goo (MD5, volume incl. supports, weight, time, previews)
                 ├─ print.export {path} ─▶ USB stick / folder        tracking: queued ─▶ sent ─▶ printed on the user's confirmation
                 └─ print.upload ─▶ print.start ─▶ status ─▶ done    tracking: queued ─▶ sent ─▶ printed / failed (from the printer)
```

- **The parts are the export's own files**, so what is printed is what the report, the manifest and the print check describe.
  - When the export is missing or older than the case, Print first exports the chosen aligners. The manifest records the hash of the case inputs; it is added if missing.
  - The shells are ≈ 85 % of today's 9–11 min export: Print exports only the aligners it needs, never the whole series.
- **Face labels.** The shell build already knows each vertex's side of the shell (inside or outside of the wall, measured from the stage's model). The export stores a label per face:
  - `fitting`: the intaglio;
  - `outer`;
  - `rim`: a 1 mm band along the trim edge;
  - `stamp`: the engraved text and 1 mm around it.
  
  Supports may touch `outer` only.
- One plate = one `.goo` = one print job. Its record lists the aligners it carries, for the tracking.

### 2.4 Threads, jobs, errors
- **Controller.** `PrintController::execute(id, params, cancel) -> Result<Value>`, like `ScanController` (`C/dc-scanner/src/control.rs`): one command at a time, on the popup's job thread. `print.layout`, `print.slice`, `print.upload` and `print.run` answer `{started}` and go on in the background, with progress and cancel.
- **Connection.** One WebSocket per printer, on its own thread (blocking `tungstenite` with a read timeout). Pushes land in a status cell; the UI reads it with `try_lock`.
- **Errors.** `PrintError` has stable kebab-case codes: `print-printer-busy`, `print-md5-failed`, `print-resolution-mismatch`, `print-fitting-side-unsupportable`, `print-island-unsupported`, `print-no-resin-preset`, and so on. `dc-print-ui` maps them to en/it, and does the same for the printer's `ErrorStatusReason` 0–34 and its Ack codes.
- **Recovery, as an operator would:**

  | Event | What happens |
  |---|---|
  | BUSY | Wait for idle, retry |
  | A failed chunk | Resend from its offset |
  | A dropped WebSocket | Reconnect and read the status again |
  | A new address | Rediscover by `MainboardID` |
  | A part does not fit | Another plate |
  | An orientation needs supports on the fitting side | Try the next orientation; if none passes, refuse with the part's name |
  | An unsupported island | Add a support there, or re-orient |

  A stop is never retried. A start never falls back to another file.

## 3. Printer, resin, plate

### 3.1 Saturn 4 Ultra 16K

**Observed on the user's printer** (Device Details screen; read-only probe from the workstation on the same LAN, 2026-11-20 21:22; the LAN addresses and the device ids are left out of this document):

| Item | Value |
|---|---|
| Discovery (`M99999` → `<printer address>:3000`) | `Id` (a 32-digit hex id); `Name` / `MachineName` "Saturn 4 Ultra 16K"; `BrandName` ELEGOO; `MainboardID` (a 16-digit hex id, the serial on the screen); `ProtocolVersion` V3.0.0; `FirmwareVersion` V1.5.6 (as in the real-device notes [S14]) |
| Control | `ws://<printer address>:3030/websocket`, no authentication. Cmd 0 and Cmd 1 → Ack 0. Topic `sdcp/request/<MainboardID>`; answers on `sdcp/{response,attributes,status}/<MainboardID>` |
| Attributes | `Resolution` "15120x6230"; **`XYZsize` "218.88x128.88x220"**; `SupportFileType` [CTB, GOO]; `Capabilities` FILE_TRANSFER, PRINT_CONTROL; `NetworkStatus` wlan; `UsbDiskStatus` 1; `RemainingMemory` 6 249 381 888 B; `DevicesStatus` all 1 (UV LED temperature sensor, tank, LCD, strain gauge, Z motor, rotate motor, release film); `ReleaseFilm` 839 of `ReleaseFilmMax` 60000 |
| Status (idle) | `CurrentStatus` [0]; `HeatStatus` 1; `TempOfTank` 20 / `TempTargetTank` 45 °C; `TempOfUVLED` 19.8 °C |
| Network | Same LAN as the workstation, and the Windows VM reaches it too (user, 2026-11-20) |

**From the sources:**

| Item | Value | Source |
|---|---|---|
| Pixel pitch | 14 µm (X, 15120 px) × 19 µm (Y, 6230 px), giving 211.68 × 118.37 mm | [S1][S2] |
| **Mismatch** | The printer reports 218.88 × 128.88 mm, which would mean 14.48 × 20.69 µm pixels. This is risk 4 (§10.2). It is settled first by the platform size SatelLite writes into its header (§9.3), then by the gated dimensional print. Until then the profile uses 211.68 × 118.37 | probe; [S14] |
| Layer height | 0.01–0.2 mm | [S2] |
| Release | Tilting vat; fast or normal is set on the touchscreen only; the first 50 layers are always slow; the file's lift and retract values are ignored | [S2][S14] |
| Heated vat | Target 45 °C on this printer. At start the printer holds layer 0 until warm (≈ 3 min from cold [S14]; longer from 20 → 45 °C [INFERENCE]) | probe; [S14] |
| Resin sensor | Needs ≥ 1/3 of the vat, and compares the level with the file's volume | [S2] |
| USB | FAT32, ≤ 16 GB, ASCII file names | [S9] |

The `sdcp3` backend picks this profile from `MachineName` "Saturn 4 Ultra 16K" and resolution 15120×6230. It compares the attributes with the profile at every connect; a mismatch is shown and logged with `diag = true`, never applied silently.

### 3.2 Resin presets
- **The user's resin is a clear, biocompatible aligner resin**; its brand and its exposure values for this printer are still open (§11 Q1). v1 ships **no built-in aligner-resin preset**: the user enters the maker's values once (advanced view or `print.resin.save`), and without a preset Print is refused with `print-no-resin-preset`. For the shape of such values: RayForm lists a resin for directly printed aligners on this printer at 0.1 mm, 5.7 s / 35 s bottom [S28] (not the user's resin).
- **Storage.** User presets live in `<data dir>/dentalcraft/print/resins/`. This is the rig calibration's data dir: `%APPDATA%`, `~/Library/Application Support`, `$XDG_DATA_HOME`. Move that helper to a shared core place instead of copying it a third time.
- **Fields.** `id`, en/it names, `profile`, `source`; one row per layer height {`layer_mm`, `exposure_s`, `bottom_exposure_s`, `bottom_layers`, `transition_layers`, `rest_before_exposure_s`, `pwm`}; `density_g_ml`; compensation `xy_scale` (X, Y), `erosion_px` (thinner walls), `clearance_mm` (added to the shell's inner clearance at export); support defaults (tip Ø, spacing, self-supporting angle); `post_note`, the maker's post-processing line for the job summary.
- **Transition stays 0** until a SatelLite file with transition > 0 shows how it is written (Q3). Per-layer values would need the "advance" mode, which once stopped Z on this printer [S7].
- **Compensation starts neutral.** The gated test measures wall thickness and fit, then sets `erosion_px`, `clearance_mm` and `xy_scale`.

### 3.3 The print check plate
- Today `DEFAULT_PLATE_MM = [145, 145, 185]` (Formlabs Form 3, `A/dca-algo/src/export/printcheck.rs:73`) is the default of `CheckOptions`, `export/package.rs:132` and `A/dca-module/src/commands/export.rs:653`.
- `aligners.settings.production` gains `printer`, a profile id saved with the case (one undo step).
  - With the Saturn, the check uses its build volume minus the layout's margin.
  - With no printer chosen, it keeps the Form 3 plate, so older projects and tests do not change.
  - Choosing a printer in the popup sets it; `print_check.json` records it.
- The export's own checks stay as they are: closed, genus 0, no self-intersections, minimum wall 0.3 mm, `shell_reach`.

## 4. Orientation, supports, nesting

- **Orientation (per shell).** A search over a small set: occlusal plane at 45/60/75/90° to the plate [INFERENCE], front up or down, small turns. Hard rules: the fitting side faces away from the plate (the cavity opens toward the vat floor, so resin drains and no cup forms), and no `fitting` or `rim` face overhangs beyond the preset's self-supporting angle. Score: fewest support contacts, then the smallest largest cross-section (peel force), then the lowest height. If no orientation passes, `print-fitting-side-unsupportable` names the shell; the agent or the user changes the angle set.
- **Supports (automatic, outer side only).** Contacts go on the overhangs and islands of `outer` faces, never on `fitting`, `rim` or `stamp`. Cone tips with a small contact (≈ 0.3 mm Ø on a 1 mm wall [INFERENCE]), columns, a raft and a ≈ 5 mm lift for drainage and removal; defaults from the resin preset, editable in the advanced view. Supports are separate closed meshes overlapping the shell slightly: the slicer's nonzero rule merges them, so no mesh boolean is needed.
- **Island check (hard gate before any file is written).** On the sliced runs, each layer's connected regions are linked to the layer before. A region that starts in mid-air must sit on a support tip; otherwise a support is added there and the layer is sliced again.
- **Contact check (hard gate).** Every support-to-shell contact face must be `outer`. A test asserts this on every plate.
- **Nesting.** Footprints of the oriented shell with its supports and raft, rasterised at 0.25 mm; bottom-left fill, largest first; upper and lower of a stage, and the passive aligners, on one plate; margin and gap 3 mm [INFERENCE]; deterministic (same parts, same layout, same hashes).
- **Plate estimate.** About 8–12 shells per plate when angled [INFERENCE]; the layout reports the real count. Height ≈ 40–60 mm with supports: 800–1200 layers at 0.05 mm, 400–600 at 0.1 mm, so ≈ 1–2.5 h per plate at 5.5–8 s per layer [S14] [INFERENCE].
- **Labels.** The engraved stamp ("SUP 03" / "INF 03", the date) is the shell's own. A stamp that reads mirrored on a printed shell is the quickest chirality alarm.

## 5. Slicer and GOO V3 writer
- **Sampling.** Layer i at z = (i + ½)·h: triangles swept in z order, each crossing gives a segment with its winding. Row j at y = (j + ½) × 19 µm: crossings sorted and filled with the nonzero rule (shell and supports merge). Pixel k lit when x = (k + ½) × 14 µm is inside. Runs go straight into the RLE, across row ends; a 94 Mpx bitmap is never built.
- **Pixels and chirality.** Binary pixels in v1. At 14 × 19 µm a 1.0 mm wall is ≈ 70 × 52 pixels across. One function maps the plate frame to pixel indices through the profile's mirror flags; the writer, the reader and the preview all use it. The header's mirror fields take the vendor's values from the golden file (Q2).
- **Compensation.** `erosion_px` shrinks every lit region by whole pixels, which thins the wall from both sides; the extra `clearance_mm` is applied in the shell export. Layer Z = (i + 1)·h, from integer micrometres, never accumulated [S7].
- **GOO V3** (Elegoo "Goo Format Spec V1.2" [S5]):
  - **Layout.** Big-endian. The header is exactly 195 477 bytes, with RGB565 previews of 116×116 and 290×290 drawn by `dc-raster`. Each layer has 64 bytes of settings (two u16 and 15 floats, five of them timings; the research table's per-layer offsets after the layer Z are one field off), then `0D 0A`, the data size, the image and `0D 0A`. The file ends with `00 00 00 07 00 00 00 44 4C 50 00`.
  - **Image.** Each image is `0x55`, the chunks, then a NOT 8-bit-sum checksum. Every one of the 94 197 600 pixels must be covered [S18].
  - **Values for this tilt-vat printer** [S7][S14]: advance mode 0; lift and retract values 0; delay mode 1 with the preset's rest before exposure; transition 0 (Q3); PWM from the preset (255 by default); resolution exactly 15120 × 6230 (otherwise Ack 5); platform 211.68 × 118.37 × 220 until §9.3 says otherwise; printer name and type as in the SatelLite file (Q4); volume and weight always filled in.
  - **Layer 0.** The firmware may ignore the wait before layer 0 [S16]; the golden file decides whether a blank first layer is needed.
  - **Writing.** Layers are encoded in parallel and written in order to a `.tmp` file, with the MD5 computed on the way, then renamed. A reader serves the tests, the golden comparison and `print.inspect`.
- **Volume, weight, time.** Volume = Σ lit pixels × 0.014 × 0.019 mm² × h, supports included (the printer checks its resin against it); weight = volume × density. Time = preheat + bottom layers × (bottom exposure + slow tilt) + other layers × (exposure + rest + tilt); the tilt time starts at 5.5 s fast / ≈ 8 s normal per layer [S14] and is learnt per printer from finished jobs (`TotalTicks`), preheat from the tank gap (20 → 45 °C).
- **Performance targets** (measured in M2 on Linux, Windows and macOS builds): a plate of 10 shells (≈ 2.5 M triangles with supports) at 1000 layers in ≤ 60 s; peak memory ≤ 1 GB (runs only); files ≈ 20–60 MB [INFERENCE], ≈ 6 min to upload at ≈ 170 KB/s [S14].

## 6. Network and USB

### 6.1 SDCP V3 client
All pure Rust: `std::net::UdpSocket` + `if-addrs`, `tungstenite` (plain ws), `ureq` with TLS off (already in the app), `md-5`, `uuid`, `serde_json`.

- **Discovery.** `M99999` by UDP to port 3000 on each interface's directed broadcast and on 255.255.255.255; ≤ 3 s per round (the Windows firewall window [S31]), 2 rounds; plus unicast probes of a typed address and of each known printer's last address.
- **Control.** `ws://<ip>:3030/websocket`, heartbeat "ping" → "pong" every 20 s [S13]; envelope `Id`, `Data{Cmd, Data, RequestID, MainboardID, TimeStamp, From: 0}`, `Topic` `sdcp/request/<MainboardID>`, answers matched by `RequestID` [S11]; one connection per printer (the firmware takes about 4 clients [S17]).
- **Commands used.** 0 status, 1 attributes, 128 start `{Filename, StartLayer: 0}`, 129 pause, 130 stop, 131 resume, 258 file list, 259 delete, and 320/321 history. Commands 132, 133 and 260 are not used: they give no answer on V1.5.6 [S14].
- **Upload.** `POST http://<ip>:3030/uploadFile/upload`, multipart, one request per 1 MiB chunk [S11][S13], fields `Check`="1", `S-File-MD5` (lowercase hex, whole file), `Offset`, `Uuid`, `TotalSize`, `File`. Success `code` "000000"; codes −1…−4 mapped; a failed chunk is resent from its offset (3 tries).
- **Start.** After the last chunk the printer stays in status 2 while it checks the MD5: wait for idle (or ≈ 15 s), then Cmd 128. Ack 1 (BUSY) → retry every 3 s up to 60 s [S14][S16]; Acks 2–7 → errors (not found, MD5 failed, read error, resolution mismatch, unknown format, model mismatch).
- **Preconditions before Cmd 128.** `CurrentStatus` idle; every `DevicesStatus` 1 (a fault refuses the start and names the part); GOO supported and resolution 15120x6230; `RemainingMemory` > file size; `ReleaseFilm` < `ReleaseFilmMax` (warning near the limit). Tank heating needs no wait: the printer heats before layer 1, and the popup shows "Heating the resin 20 → 45 °C". The resin level is the printer's own check; its error is shown.
- **File names.** `DC_<case code>_S<from>-<to>_P<n>.goo`, ASCII only [S9]. The case code is the pseudonymised one, never a patient name.
- **Status.** `CurrentStatus` 0 idle, 1 printing, 2 file transfer, 3 exposure test, 4 self-test; `PrintInfo{Status, CurrentLayer, TotalLayer, CurrentTicks, TotalTicks, Filename, ErrorNumber, TaskId}`; sub-states (16 preheating, 20 levelling) and tank temperatures where present [S17]. Unknown codes are shown as "printer state n" and logged.
- **Security.** SDCP has no authentication: anyone on the LAN can drive the printer [S16]. DentalCraft only connects out. Its help says to keep the printer on a trusted network.

### 6.2 Connections that survive restarts (product rule)
- **The printer store.** `<data dir>/dentalcraft/print/printers.json`, written atomically and shared by the app and the CLI: per printer `MainboardID` (the identity) and `Id`, name, profile, last address, firmware, default flag, last resin, learnt tilt time and heating rate, and the job log (plate, file, MD5, `TaskId`, aligners carried).
- **At app start** (and at the CLI's first `print.*`): a unicast probe of the default printer at its last address; no answer → a broadcast for the same `MainboardID`, and the address is updated; then the WebSocket opens. A running print is picked up again by `TaskId` and file name, and its tracking moves on (§7.4).
- **First connect must work.** `print.connect` retries transient failures itself (3 tries, with backoff). A printer is forgotten only by `print.printers.forget`.

### 6.3 Same behaviour on Linux, Windows, macOS

| Platform | Specific | Plan |
|---|---|---|
| Linux | firewalld may drop unicast replies to a broadcast [S32] [INFERENCE for SDCP] | Unicast probes always work; the help shows how to type an address. Broadcast discovery already works on this workstation |
| Windows | The firewall accepts unicast replies to a broadcast for 3 s only [S31]; possible first-run prompt | Rounds of ≤ 3 s. The Windows VM reaches the printer, so read-only discovery, connect and status are tested on the real printer from Windows (M1) |
| macOS 15+ | Local network privacy covers TCP to LAN addresses and UDP broadcast [S30] | `NSLocalNetworkUsageDescription` (en/it) in `packaging/macos`; a refusal gives `print-local-network-denied`. Built and linted only: no Mac is known yet (§11 Q2), and the macOS build is disabled. Every report says so |

### 6.4 USB stick or folder
- `print.export {path}` writes the plate files to a folder or removable drive (FAT32, ≤ 16 GB, ASCII names [S9]), chosen with the host's file dialog (`rfd`).
- The popup then explains: put the stick in, choose the file on the touchscreen, print. The aligners become `sent`; the user confirms `printed` or `failed` in the popup or with `aligners.print.mark`. The 16K may copy a USB file to its memory first (Q7).
- Advanced: "Save the arranged plate (shells and supports) as STL", for SatelLite users and for the golden comparison.

## 7. Print popup UX and tracking

### 7.1 Menu and inspector (menu law)
- **The leaf.** **Production → Print** (`aligners.output.print`, "Print" / "Stampa", icon `printer`). It sits after "Export for printing" and is `not_a_step()`. A click, Enter or its key only selects it.
- **The inspector.**
  - **Status:** the printer state, and the tracking ("Printed 6 of 18. Missing: upper 4–9, lower 4–9. 1 to reprint").
  - **Parameters:** which aligners (missing only by default, or a stage range), arches, and the passive aligners.
  - **Automatic:** "Print…" (primary) opens the popup with those aligners. While a job runs, it shows "Show printing".
  - **Manual corrections:** mark aligners as printed, failed or to reprint (`aligners.print.mark`).
- **Opening the popup** lists the printers and lays out the plate when the shells exist. Nothing is written or sent before its Print button.

### 7.2 Simple view (advanced options OFF, the default)
1. **Printer:** a picker with a state badge (known and found printers, plus "USB stick or folder"); "Find printers"; "Add by address".
2. **Resin:** the user's preset. With none: "Enter your resin's values" opens the preset editor.
3. **What:** the aligners to print, with missing ones preselected. Each row shows SUP/INF, number and passive, with a status badge (missing, printed, failed, to reprint, printed with an older design).
4. **Plate preview:** a top view of the oriented shells and their supports, "Plate 1 of 2", with arrows.
5. **Estimate:** time and resin (ml, g) per plate and in total. Warnings: printer busy, film near its limit, the export still to run.
6. **One button: Print.** It becomes "Save to the USB stick" for that target, or "Print plate 2" after the first plate.
7. **Progress:** Exporting the aligners → Placing and supporting → Preparing the layers → Sending (MB/s, time left) → The printer checks the file → Heating the resin → Printing layer x of y → Done. Pause / Resume, and Stop with a confirmation.
8. **Job summary** (at the end, also in `print.history`): the aligners on the plate, with file, time and resin used. Then the **post-processing note**, done by the lab and not by the app:
   - remove the supports from the outer surface;
   - wash and post-cure as the resin maker prescribes;
   - printed shells come out thicker than designed and change with curing, so check the wall thickness and the fit before use.

### 7.3 Advanced view (advanced options ON)
- **Resin and print settings:**
  - the preset editor;
  - exposure, bottom exposure and bottom layers;
  - transition (locked at 0 until Q3);
  - rest before exposure, PWM, layer height;
  - compensation: XY scale, erosion, clearance.
- **Orientation:** the angle set and per-shell overrides.
- **Supports:**
  - tip Ø, spacing, self-supporting angle, raft, lift;
  - "Show contacts", which highlights each contact on the shell (all must be on the outer side).
- **Plate:** margin, gap, arranging by hand, moving a shell to another plate, saving the plate as STL, the file name.
- **Layer viewer:** a slider over the decoded layers of the file to be sent. Use it to check chirality and the island check.
- **Printer:** firmware, `MainboardID`, resolution and reported sizes against the profile, free memory, USB stick, device checks, tank temperature and target, UV LED temperature, release film used / max, its files (list, delete), and the printer's own history.
- **Gating:** one read of `dc_module_api::advanced_ui(ctx)` per frame, with the sections marked in one table, as the inspector's `FUNCTIONS` does.

### 7.4 Print tracking (v1 requirement)
- **Records.** `AlignersState::prints` holds one record per aligner, keyed by (arch, stage, passive):
  - `state`: `queued` | `sent` | `printed` | `failed` | `reprint`;
  - the time;
  - the plate and file, with MD5, printer and `TaskId`;
  - the design hash of the shell that was printed;
  - a reason, for `failed` and `reprint`;
  - the history of earlier states.
- **Saving.** The records are saved in `modules/aligners/state.json` of the `.dcprj`. The module schema version goes up, and older projects open with no records.
- **Transitions.** `next_state(state, event)` is a pure function:

  | Transition | Trigger |
  |---|---|
  | missing → `queued` | On a prepared plate |
  | `queued` → `sent` | Upload done and start accepted, or the file saved to USB |
  | `sent` → `printed` | Printer reports the job complete for that `TaskId`, or the user confirms a USB print |
  | `sent` → `failed` | Printer error or stop |
  | `printed` → `reprint` | The user asks for it (broken or lost aligner) |
  | `failed` / `reprint` → `queued` | Placed on a new plate |

  `printed` is never set without a printer report or a user confirmation.
- **Stale designs.** A record whose design hash differs from the current shell shows "printed, older design", and the popup offers it again.
- **Undo.** Records are facts, not edits. An undo or redo keeps the latest tracking: the workspace carries it into the state it restores. Every change is autosaved.
- **Where it shows.** The tracking is shown in the inspector and the popup (missing preselected), through `aligners.print.status`, and in the export report.

### 7.5 Words and tests
- Fluent keys go in `X/dc-print-ui/i18n/{en,it}/dc-print-ui.ftl`, with a key parity test.
- The jargon ban of `X/dc-workspace/tests/wording.rs` covers the popup. The simple view never says "slice", "RLE", "GOO", "SDCP" or "mesh".
- `egui_kittest` tests cover simple against advanced, the Print flow on `sim`, the tracking badges, and both languages.

## 8. Agent commands

`print.*` live in `dc-print`. They are registered in the headless session (CLI, MCP) and in the app bridge. In the app, an agent's command that acts on the printer opens the popup. Long commands answer `{started}`, and `print.status` follows them.

| id | Parameters | Result |
|---|---|---|
| `print.profiles` | — | Profiles |
| `print.resins` | `profile?` | Resin presets |
| `print.resin.save` / `print.resin.delete` | `preset` / `id` | The saved preset / `{}` |
| `print.printers.list` | — | Known printers with live state; the default |
| `print.printers.discover` | `timeout_s?` (3), `rounds?` (2), `address?` | `{found}` |
| `print.printers.add` / `print.printers.forget` | `address`, `name?` / `id` | The printer / `{}` |
| `print.connect` / `print.disconnect` | `id?` / — | `{printer, attributes, profile_check}` / `{}` |
| `print.parts` | `parts: [{path, labels?, name, group?}]`, `replace?` | Part ids, sizes |
| `print.settings` | `resin?`, `layer_mm?`, `exposure_s?`, `bottom_exposure_s?`, `bottom_layers?`, `rest_s?`, `pwm?`, `xy_scale?`, `erosion_px?`, `margin_mm?`, `gap_mm?`, `target?` (`printer` / `folder`) | The settings in force |
| `print.orient` | `part?`, `angles_deg?`, `front?` (`up` / `down`) | Orientation per part, score, rejected angles with the reason |
| `print.supports` | `tip_mm?`, `spacing_mm?`, `angle_deg?`, `raft_mm?`, `lift_mm?` | Contacts per part, support volume |
| `print.layout` | `interlock?` | `{started}`; then plates (orientation, supports, nesting), checks, estimates |
| `print.layout.move` | `part`, `plate?`, `x_mm?`, `y_mm?`, `rot_deg?`, `remove?` | Plates |
| `print.check` | `plate?` | The hard checks: contacts only on `outer`, every island supported, fits the plate; with the failing parts |
| `print.slice` | `plate?` | `{started}`; then layers, height, volume, weight, time, bytes, MD5 |
| `print.preview` | `plate`, `layer?`, `path` | A PNG of the plate or of one decoded layer |
| `print.inspect` | `path` (a `.goo`) | The decoded header and a layer summary |
| `print.export` | `path`, `plate?`, `what?` (`goo` / `stl`) | `{files}` |
| `print.upload` | `plate`, `name?` | `{started}` |
| `print.start` | `name` or `plate` | `{started}` once the preconditions pass; BUSY is retried |
| `print.run` | `plate?` | `{started}`: slice, upload, start. This is the Print button |
| `print.status` | — | Printer state and checks, job step, progress, layer, time left, last error |
| `print.pause` / `print.resume` | — | Status |
| `print.stop` | `confirm: true` | Status; refused without `confirm` |
| `print.cancel` | — | Stops a running layout, slice or upload, never a print |
| `print.files` / `print.files.delete` | `where?` / `names` | Files on the printer / `{}`. Names are checked against the list first, because Cmd 259 also acknowledges missing files |
| `print.history` | `limit?` | DentalCraft's job log (plates, aligners, files, states, summaries) plus the printer's own history (Cmd 320/321) |
| `print.close` | — | Ends the session; refused while a job runs |

Module and host:

| id | Parameters | Result |
|---|---|---|
| `aligners.output.print` | `stages?` `{from, to}`, `arches?`, `passive?`, `missing_only?` (true) | Run by the host, like `scan.import`: in the app it opens the popup with the parts. Headless it runs `print-parts`, then `print.parts` and `print.layout` |
| `aligners.output.print-parts` | The same, plus `export_dir?` | Shell files, face labels, names, groups. It exports the missing aligners first |
| `aligners.print.status` | `arch?`, `state?` | Per aligner: state, time, plate, file, printer, outdated flag. Totals printed / missing |
| `aligners.print.mark` | `items: [{arch, stage, passive?}]`, `state` (`printed` / `failed` / `reprint`), `reason?` | The updated records |
| `aligners.settings.production` | `printer` (profile id) | The plate used by the print check |

The doc keys are `print-cmd-*` (en/it). The bridge list goes at the top of `X/dc-app/src/control.rs`, and the CLI gets describe and run tests.

## 9. Verification (no prints until the user allows them)

### 9.1 Unit and property tests (headless, in CI)
- **RLE.** Random runs (1 pixel, 2^28 − 1, across row ends): decoding the encoding gives them back, with the fewest length bytes, a correct checksum and a total of 94 197 600.
- **Header.** Every offset and the 195 477 size against the spec; big-endian.
- **Slicer.** Known solids: a box (exact pixel counts), cylinders and spheres (within one ring of pixels); overlapping meshes form a union; a 1.0 mm shell wall gives the expected pixel width; an "R" glyph keeps its handedness; volume against the mesh volume within 2 %; exact Z values.
- **Supports**, on the golden arches' shells at every candidate orientation: no contact on `fitting`, `rim` or `stamp`; every island supported; orientations needing fitting-side supports refused; deterministic results.
- **Tracking.** Every transition of `next_state`. Records survive save and load, the schema migration and undo/redo.
- **SDCP.** Recorded messages from this probe and [S14], with unknown codes. The `sim` printer covers upload, chunk retry, MD5 failure, 15 s BUSY, a dropped connection, a new address, pause, resume, stop, completion (→ `printed`) and errors (→ `failed`).
- **Popup.** `egui_kittest` flows on `sim`.

### 9.2 Kani laws (candidates; `#[cfg(kani)] mod kani_proofs`, then listed in `docs/kani.md`)

| Repo | Crate | Harness | Law |
|---|---|---|---|
| core | dc-print `goo/rle.rs` | `run_length_round_trips` | For any length 1..2^28−1 and colour, `decode(encode(run))` is the run, with the fewest length bytes |
| core | dc-print `goo/rle.rs` | `runs_round_trip` | Up to 4 symbolic runs come back, merged where the colour repeats |
| core | dc-print `goo/rle.rs` | `checksum_detects_one_byte_change` | Changing any one byte changes the checksum |
| core | dc-print `goo/rle.rs` | `row_runs_cover_the_row` | Spans in a row of width ≤ 16 give runs summing to the width, alternating colour |
| core | dc-print `goo/header.rs` | `header_is_195477_bytes` | Any field values give a header of exactly 195 477 bytes |
| core | dc-print `slice/z.rs` | `layer_z_is_exact_and_increasing` | For h in 10..=200 µm and i < 22 000: z(i) = (i+1)·h, z(i+1) > z(i), and the last z ≤ 220 mm |
| core | dc-print `slice/pixel.rs` | `pixel_of_point_is_inside` | Finite points on the plate map inside 15120 × 6230; NaN, ±inf and points outside give `None` |
| core | dc-print `slice/pixel.rs` | `mirror_is_an_involution` | Mirroring twice gives the index back, in range |
| core | dc-print `support/mask.rs` | `contact_only_on_allowed_faces` | For any face label and contact, a contact is accepted only on `outer` |
| core | dc-print `sdcp/upload.rs` | `chunks_cover_the_file_once` | For any size < 2^32, the chunks cover [0, size) once, each ≤ 1 MiB |
| core | dc-print `sdcp/codes.rs` | `every_code_has_a_message` | Every `u32` Ack, status and error code maps to a message or "unknown n" |
| aligners | dca-model `prints.rs` | `printed_needs_a_report_or_a_confirmation` | For every state and event, `next_state` gives only allowed transitions, and `printed` comes only from `sent` with a printer report or a user confirmation |

Before merging, run `scripts/kani-local.sh <core|aligners>` on the committed ref, together with `ci-local.sh`.

### 9.3 Golden comparison with Elegoo SatelLite (Windows VM, no printer needed)
- **Inputs (small, committed).**
  - A 20 × 10 × 5 mm box at a known corner, an "R" with an arrow, and a 1–5 mm stair.
  - One real aligner shell of the test piece.
  - **Our oriented and supported plate, exported as STL.**
- **SatelLite.** Slice in SatelLite (Windows), printer "Saturn 4 Ultra 16K", with AA off and **no extra supports** (ours are already in the STL). Use known exposures, bottom 4 and transition 0, and make a second file with transition 10.
- **Compare** with `print.inspect` and a test:
  - the header byte by byte, with an allow-list (software, time, previews, estimates);
  - the 64 setting bytes of each layer;
  - the decoded images pixel by pixel: identical on the box, ≤ 1-pixel edges elsewhere, the same mirror and origin on the "R";
  - volume and weight within 1 %;
  - **the platform size SatelLite writes** (211.68 × 118.37 or 218.88 × 128.88).
- **Qualitative check.** SatelLite's own auto-supports on the same shell, as a reference for contact density. This is not a pixel comparison.
- **Settles** Q2 (mirror and origin), Q3 (transition), Q4 (printer name and type), layer 0, and the first answer to risk 4. Files ≤ 1 MB become fixtures in core; larger ones stay in `/var/tmp/dc-print-data` with a README.

### 9.4 Real printer, read-only (allowed now)
- From Linux and from the Windows VM: discovery, connect, attributes, status pushes, the file list (Cmd 258), reconnect after an app restart, rediscovery when the address changes.
- No upload, start, delete or print until M6.

### 9.5 End to end in the open app (before the gate)
- An agent drives the app over the bridge (`dentalcraft --control`) while the user watches.
- **The run:** project `Provino-superiore-HQ2` → Production → Print → missing aligners preselected → USB-folder target (a folder, no printer) and then the `sim` printer → orientation, supports, plate preview → Print → tracking moves queued → sent → printed (sim) → the job summary.
- **Checks:** the `.goo` written for the folder target passes `print.inspect` and the golden checks. The tracking survives a save, a reopen and an undo.
- **Failures:** the agent finds and fixes them, then starts the run again from the beginning. The release build is made after every change.

### 9.6 Gated milestone M6: real prints (only with the user's approval)
1. The first real upload and start on the printer, with pause, resume and stop.
2. The printer's own exposure test with the user's resin.
3. A chirality plate and a dimensional plate: X and Y separately, settling 211.68 against 218.88.
4. One plate of shells of the test piece:
   - the lab removes supports, washes and post-cures;
   - check that no support mark is on the fitting side;
   - measure wall thickness (target 1.0 mm after compensation);
   - check the fit on the test piece;
   - scan the intaglio with the MINI 2 against the design (≥ 95 % of points within ±0.15 mm [target]).
5. The compensation values go into the user's preset, and Wi-Fi printing is released.

## 10. Milestones and risks

### 10.1 Milestones
Each milestone is a release of every repo, the website included (downloads; "Printing aligners on the Saturn 4 Ultra 16K" moving from planned to in progress to exists; What's new). The exception is M5, which is released together with M6. Sizes [estimate]: S ≈ 1 day, M ≈ 2–4 days, L ≈ 1–2 weeks.

| M | Content | Ships | Size | Done when |
|---|---|---|---|---|
| M0 | Probe (**done** 2026-11-20 21:22); SatelLite reference files on the VM; the resin maker's values (§11 Q1) | Data | S | Files and values recorded |
| M1 | `dc-print` skeleton: profiles, printer store, read-only SDCP (discovery, typed address, connect, attributes, status, heartbeat, reconnect, rediscovery), `sim`; `print.profiles`, `printers.*`, `connect`, `disconnect`, `status` in CLI and MCP | CLI/MCP: finds the printer, shows its state, keeps it across restarts | M | 9.4 from Linux and the Windows VM; a restart test |
| M2 | Slicer, GOO V3 writer and reader, volume, weight, time, previews; `print.parts`, `settings`, `slice`, `preview`, `inspect`, `export`; Kani laws | CLI/MCP: plate files for a USB stick (no supports yet) | L | 9.1, 9.2 and 9.3 (box, "R", stair) green |
| M3 | Face labels in the export; orientation search; supports on the outer side only; island and contact checks; shell nesting; `print.orient`, `supports`, `layout`, `check`; `aligners.output.print-parts` | CLI/MCP: supported shell plates | L | 9.1 supports; 9.3 with our supported plate |
| M4 | `dc-print-ui` (simple and advanced, USB/folder target, printer status, job summary); the Print leaf; print tracking (`AlignersState::prints`, `.dcprj`, `aligners.print.status`, `mark`, `print.history`); the print-check plate; the bridge | App: aligners to a USB stick, with tracking | M | 9.5 with the folder target |
| M5 | Upload, preconditions, start with BUSY retry, pause, resume, stop, printer files, `print.run`, tracking from printer events | Released with M6 | M | 9.1 on `sim`; 9.5 with `sim` |
| M6 | **Gated:** real prints and the first real Wi-Fi print (§9.6) | App: printing aligners over Wi-Fi | M | User approval; 9.6 passed |
| M7 | Thermoforming models as an option (flat, no supports, 19 mm height warning [S24][S27]); study models | App | M | 9.5; prints after approval |

Later: hollow models with drain holes, anti-aliasing, GOO V5 and other printers.

### 10.2 Risks, most serious first

| # | Risk | Mitigation |
|---|---|---|
| 1 | Support contacts or marks on the fitting side (intaglio) spoil the fit and can irritate | Face labels from the shell build; contacts only on `outer`, never on `fitting`, `rim` or `stamp`; contact check as a hard gate; Kani law on the contact rule; "Show contacts" in the advanced view; checked on printed shells in M6 |
| 2 | Intaglio accuracy: unsupported fitting-side overhangs sag, and layer steps run across the fitting surface | Orientation rule: the fitting side faces away from the plate, within the self-supporting angle; layer height from the maker; intaglio scanned against the design in M6 |
| 3 | Mirrored or rotated image: a left/right-swapped aligner (silent clinical error) (Q2) | One mapping function; golden comparison; Kani mirror law; the engraved stamp reads mirrored on a wrong print; chirality plate in M6 |
| 4 | Pixel pitch: the printer reports 218.88 × 128.88 mm, the spec says 211.68 × 118.37 (+3.4 % X, +8.9 % Y) (Q5) | SatelLite header first; dimensional plate in M6; per-axis XY scale; attributes compared at each connect |
| 5 | Printed walls thicker than designed; post-cure shrinkage changes thickness and fit | Per-resin compensation (erosion, clearance, XY scale) measured in M6; the job summary says to check thickness and fit |
| 6 | Unsupported islands (cusps, ramps, the trim edge) fail mid-print, and thin shells peel off or warp | Island check as a hard gate; raft and lift; support spacing from the preset; orientation that keeps the largest cross-section small |
| 7 | Firmware V1.5.6 rejects or misreads our GOO V3 (Q1), or ignores fields: advance mode, transition, layer 0 (Q3) | Vendor-like values; byte comparison with SatelLite; the first real file in M6 is checked against a SatelLite file of the same plate |
| 8 | Wrong volume: the printer's resin check refuses, or the vat runs dry | Volume from lit pixels, supports included; checked against the golden file |
| 9 | Tracking drifts from reality (USB prints, app closed during a print, undo) | Re-attach by `TaskId` at start; USB prints need the user's confirmation; records survive undo; `printed` only from a report or a confirmation (Kani law) |
| 10 | Discovery blocked or upload slow (firewalls, macOS privacy, ≈ 170 KB/s, BUSY after upload) | Typed address and unicast; rediscovery by `MainboardID`; chunk and BUSY retry; progress and cancel; the USB path |
| 11 | No authentication on SDCP | Connect out only; trusted-LAN note |
| 12 | Printed aligners are a medical device: resin certification and a validated process | DentalCraft stays an alpha, "not a medical device"; it writes the file, and the lab's certified resin and validated process decide clinical use; the job summary says so |
| 13 | AGPL or GPL code slips in | §12 rules |

## 11. Open questions for the user

Answered on 2026-11-20:
- same LAN, firmware V1.5.6, SDCP V3.0.0;
- clear biocompatible aligner resin;
- v1 = directly printed aligners;
- no test prints yet, so test prints are gated (M6);
- washing and curing are done by the lab;
- no camera;
- the Windows VM reaches the printer;
- print tracking is required.

Still open:
1. Which aligner resin (brand and product), and what are the maker's exposure values for this printer?
2. Is a Mac available for the macOS test?
3. When may the printer be used for the gated test prints (M6)?

## 12. Licensing
- **Never copy, translate or port code** from UVtools (AGPL-3.0) [S6], mslicer or `msla_format` (GPL-3.0) [S20], or saturn4-bridge-linux (GPL-3.0) [S16]. DentalCraft is proprietary.
- **The elegooofficial/GOO repository** is GPL-3.0 and holds only the spec PDF: implement from its documented facts, and do not copy its text.
- **Facts are free.** Offsets, values, command numbers and quirks may come from any source; each one is cited with its [S#] in a doc comment.
- **Usable with attribution** (add a notice in "Licence and notices" when their code is used):
  - the `goo` crate (MIT) [S18];
  - elegoo-link (Apache-2.0; port the logic only, keep its NOTICE) [S13];
  - the Home Assistant Elegoo integration (MIT) [S17];
  - alfiedennen's notes (MIT) [S14].
- **SDCP V3.0.0 spec** (CBD, "open protocol", no licence file) [S11]: implement from it, and do not copy it.
- **No CTB:** it is encrypted with Chitu's key and exists only in AGPL code.
- **New dependencies**, all pure Rust, licences checked on 2026-11-20:
  - `tungstenite` (MIT/Apache-2.0);
  - `md-5` (MIT/Apache-2.0);
  - `if-addrs` (MIT/BSD-3).

  `ureq`, `uuid` and `serde_json` are already in use. Run cargo-deny on the new set. Brand names appear only to state compatibility.

## Sources (accessed 2026-11-20)
- **Probe:** read-only SDCP probe of the user's printer from the workstation, 2026-11-20 21:22 (discovery reply, Cmd 0, Cmd 1), and its Device Details screen. **User answers:** 2026-11-20 22:36.
- [S1] Elegoo, Saturn 4 Ultra 16K product page — https://us.elegoo.com/products/saturn-4-ultra-16k-10inch-monochrome-lcd-resin-3d-printer
- [S2] Elegoo, Saturn 4 Ultra 16K User Manual V2 (2024-10-21) — https://www.123-3d.nl/pdf/DKI00322_Manual_EN.pdf
- [S5] Elegoo, "Goo Format Spec V1.2" — https://github.com/elegooofficial/GOO
- [S6] UVtools `GooFile.cs` (AGPL-3.0; facts only) — https://github.com/sn4k3/UVtools/blob/master/UVtools.Core/FileFormats/GooFile.cs
- [S7] UVtools issues on the Saturn 4 Ultra / 16K (#1013, #997, #1162) — https://github.com/sn4k3/UVtools/issues/1013
- [S9] Elegoo Wiki, USB drive and file names — https://wiki.elegoo.com/troubleshooting/lcd-printer/usb-drive-not-inserted
- [S11] CBD Technology, SDCP V3.0.0 — https://github.com/cbd-tech/SDCP-Smart-Device-Control-Protocol-V3.0.0
- [S13] Elegoo, elegoo-link SDK (Apache-2.0) — https://github.com/elegooofficial/elegoo-link
- [S14] alfiedennen, SDCP V3 on the Saturn 4 Ultra 16K, firmware V1.5.6 (MIT) — https://github.com/alfiedennen/sdcp-saturn-4-ultra
- [S16] Bulrok, saturn4-bridge-linux (GPL-3.0; facts only) — https://github.com/Bulrok/saturn4-bridge-linux
- [S17] Home Assistant Elegoo integration (MIT): README, status models — https://github.com/danielcherubini/elegoo-homeassistant
- [S18] connorslade, `goo` crate (MIT) — https://github.com/connorslade/goo
- [S20] mslicer, printers and compatibility (GPL-3.0; facts only) — https://github.com/connorslade/mslicer ; https://mslicer.com/docs/printer-compatibility
- [S24] Tran & Pham, Front Dent Med 2026, model base height (thermoforming option) — https://pmc.ncbi.nlm.nih.gov/articles/PMC13630649
- [S27] Formlabs, thermoformed aligners on printed models (2018) — https://media.mikran.pl/image/cache/catalog/mikran/banners//51/drukowanie-modeli-pod-retainery-retainer-model.pdf
- [S28] RayForm, Saturn 4 Ultra 16K dental resin settings (2026-10-07) — https://www.rayformtech.com/elegoo-saturn-4-ultra-16k-resin-settings.html
- [S30] Apple TN3179, local network privacy — https://developer.apple.com/documentation/technotes/tn3179-understanding-local-network-privacy
- [S31] Windows Firewall, unicast response to broadcast (3 s window) — https://learn.microsoft.com/en-us/windows/client-management/mdm/firewall-csp
- [S32] firewalld issue #848, unicast replies to broadcast — https://github.com/firewalld/firewalld/issues/848
