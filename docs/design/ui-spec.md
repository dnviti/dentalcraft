# DentalCraft UI spec (v0.8 design pass)

Source of truth: `dentalcraft.figcraft` (pages **Screens**, **Components**, **Design System**). Tokens: `tokens.json`. PNG exports: `screens/`.
All sizes are egui points at 100 % scale; frames are 1920 x 1080.

## 1. Identity in one paragraph

Metaphor: the **curing light** and the **shade guide** of a dental bench.
- **Amber** (`accent/amber`, like the amber shield of a curing lamp) marks actions only: primary buttons, the open action on module cards, links. At most one amber filled button per view.
- **Curing blue** (`select/blue`) marks selection, focus and the current stage. Focus ring = `focus/ring`, 2 pt, outside the widget.
- Everything else is graphite (backgrounds) and enamel (text), so the dental model is the brightest object on screen.
- **Shade-tab shape** (radii 16/16/4/4, dark "handle" band with a mono code such as `AL`) is used for module cards, the logo tile and module chips.
- **B612 Mono** for every measured value (mm, degrees, stages, counts, paths, versions in tables). **Atkinson Hyperlegible Next** for all other text. **Phosphor Regular** icons via font.

## 2. Fonts and icons

| Role | Family | Licence | egui notes |
|---|---|---|---|
| UI text | Atkinson Hyperlegible Next (Regular, Medium, SemiBold, Bold, ExtraBold) | OFL 1.1 | Register each weight as its own `FontFamily::Name` (egui has no weight axis). Proportional default = Regular. |
| Readouts | B612 Mono (Regular, Bold) | OFL 1.1 | `FontFamily::Monospace`. No OpenType features needed (egui cannot apply `tnum`). |
| Icons | Phosphor Regular | MIT | `egui-phosphor` crate, feature `regular`; add as fallback to Proportional so `format!("{} Save", egui_phosphor::regular::FLOPPY_DISK)` works. A copy of the TTF is in `fonts/Phosphor.ttf`. |

Icon sizes: 12 (badges, carets), 16 (buttons, menu status), 18 to 20 (toolbars, panel headers), 32 (module cards), 40 (state hero icons).
Icons used (Phosphor names): tooth, cube-focus, shield, crown-simple, screwdriver, folder-open, file-plus, plus, floppy-disk, arrow-counter-clockwise, arrow-clockwise, sliders-horizontal, chart-bar, arrows-in-line-vertical, stack, calendar-check, export, wrench, ruler, angle, split-horizontal, cube, cube-transparent, polygon, square, diamond, circle-dashed, check-circle, circle-half, circle, lock-key, warning, warning-circle, x-circle, x, lifebuoy, question, arrow-square-out, cloud-slash, cloud-check, circle-notch, hourglass-medium, eye, magnifying-glass, list, book-open, play-circle, newspaper, keyboard, printer, paperclip, upload-simple, link, user, user-switch, house, caret-left/right/down/up, skip-back, skip-forward, play, sparkle, lightbulb, timer, paint-brush, clock-counter-clockwise, arrows-clockwise, arrows-left-right.

## 3. Global layout rules

- Grid: 4 pt. Panel padding 16 (inspector), 20 (cards), 24 to 48 page gutters.
- Separation by 1 pt `border/subtle` lines and background steps (`canvas` < `panel` < `raised`), never by shadows, except floating things over the 3D view (e1) and dialogs (e2).
- Hit targets: 36 pt buttons in panels, 44 pt on Home/dialogs, 48 pt for the single sign-in call to action; icon buttons 32 to 36 pt; menu rows 28 to 36 pt (desktop pointer UI, all rows are full-width hit areas).
- Status always = icon + word (or shape + label in the viewport legend). Colour never carries meaning alone.
- Light theme is the same layout with the `Light` mode of the Color collection (see `01 Home (light)`, `05 Aligners workspace (light)`).

## 4. Screens

### 01 Home / launcher (`01 Home`, id 237; IT 2429; light 1674)
- Top bar 56: padding 0/24, `bg/panel`, bottom hairline. Left: logo tile 28 x 32 (shade-tab radius 10/10/3/3, amber, tooth glyph) + wordmark (ExtraBold 18) + version (12 Medium). Right, gap 12: language segmented control (EN/IT, 28 tall, active = `bg/hover` + Bold), ghost button "Support", 1 pt divider, account chip (32 avatar ring in curing blue, name 13 SemiBold, status line with green dot + "Signed in, licence active", caret).
- Body: padding 40/48/32/48, horizontal gap 40: **Main** (fill) + **Rail** (380).
- Hero (gap 10): date line (13 Medium secondary), headline Display/Hero, sub Body/L at max 640 wide. Actions right-aligned to the bottom: secondary "Open project…" + primary "New project", both 44 tall.
- Modules: title Title/M + count caption; row of 5 ModuleCards, gap 20; Aligners card 340 wide (only installed module), others fill.
- Recent projects: header with mono path and ghost "Show all 24"; 4 ProjectCards (thumbnail 168 tall on `bg/viewport`, name 13 SemiBold truncated to 1 line, status pill + stage count in mono + edited time).
- Rail: Account card (title, Signed-in badge, email, licence block with seat bar, "Manage account" secondary + "Sign out" ghost); "From the bench" news/tips list (3 items, icon 20 + title + body + optional link).
- Status bar 28: licence/offline note left, renderer + GPU mono right.
- Signed-out variant (not drawn): account chip becomes ghost button "Sign in"; account card shows "Not signed in" neutral badge, primary "Sign in" and the offline/evaluation note from 02.

### 02 Sign in (`02 Sign in` 530, `02b Sign in, waiting for browser` 591, `02c Signed in` 652)
- Split: left Story panel 820 wide on `bg/sunken` (padding 56/72) with brand, the **shade-guide illustration** (5 tabs 92 wide, 300/360/420/360/300 tall, A3 highlighted in amber) and pitch text; right column centres a 480 card (padding 36, radius 12, e2).
- Default: title Display/L, body, primary 48 "Sign in with DentalCraft account" (shown in focus state = keyboard default), hint about the browser, divider "no account yet", secondary "Start 30-day evaluation" + ghost "Create account", offline/evaluation note box.
- Waiting (OAuth 2.1 + PKCE, loopback redirect): blue spinner, title "Finish signing in in your browser", indeterminate bar (120 pt run), 3-step checklist (done / current / to do), buttons Reopen browser, Copy sign-in link, Cancel, expiry countdown in mono.
- Signed in: green check, facts table (account, workstation seat, licence badges), primary "Continue to DentalCraft", ghost "Switch account".
- Interaction: primary opens the system browser with `code_challenge`; app listens on `127.0.0.1:<port>/callback`; card switches to Waiting immediately; on callback with matching `state` it exchanges the code and shows Signed in; on timeout (5 min) show error state with "Try again". Escape = Cancel.

### 03 Support (`03 Support` 771)
- Header: breadcrumb back to Home, Display/L title, sub; search field 460 x 44 with `Ctrl K` hint.
- 3 columns, gap 24: Documentation (440; 7 link rows 12 padding, hover row shown on "Keyboard shortcuts"), Ticket form (fill), Side (460: tickets list + workstation info).
- Form: Subject (Input, focus state), Category select (260), Description textarea 150 tall, **Attach diagnostics bundle** checkbox (checked, selection-tinted box listing what is and is not included, "Preview what is sent" link), drop zone (dashed), footer note + ghost "Save draft" + primary "Send ticket" (44).
- Tickets: id in mono, title, status badge (Waiting for you = warning, In progress = info, Resolved = success) and last update.
- Workstation: 2-column grid of key / mono value (version + build hash, OS, renderer, GPU + driver, memory, log folder), "Copy system info", "Open log folder", "Keyboard shortcuts (F1)".

### 04 New project / module chooser (`04 New project` 951)
- Numbered columns (a real sequence): 1 Module (400), 2 Case (fill), 3 Scans (640). Footer bar: save path in mono + "Change location" link, ghost Cancel, primary "Create project and segment" (44).
- Module options: shade-tab code tile 44 x 48 + name + description + radio; non-installed modules disabled with "Coming soon" badge.
- Case: Case ID (Input), Patient alias (pseudonymised; helper forbids real names), Jaw segmented (Upper / Lower / Both jaws), technician notes textarea (150), units note.
- Scans: drop zone (dashed, 28 padding), file list rows (cube icon, file name, mono size / triangles / units, jaw badge, OK check). Unit-mismatch row shows a warning sentence and a secondary "Convert" button. Preview panel shows the detected arch.

### 05 Aligners workspace (`05 Aligners workspace` 1138; IT 2695; light 1940)
Measurements:

| Region | Size |
|---|---|
| Top bar | 48 tall, padding 0/12, gap 16 |
| Left menu | 288 wide, `bg/panel`, right hairline |
| Viewport | fills (1272 x 892 at 1920 x 1080) |
| Timeline | 112 tall (padding 8/16/10/16), under the viewport only |
| Inspector | 360 wide, left hairline |
| Status bar | 28 tall, full width |

- Top bar: logo tile (back to Home), module chip (`AL` + "Aligners"), project name + extension, unsaved dot + text; spacer; Undo / Redo (ghost, Redo disabled when stack empty), primary Save, divider, Help, avatar.
- Left menu: filter field (32, `/` shortcut) then the tree (section 6). Footer: workflow progress (`14/37` mono + success bar).
- Viewport overlays (absolute, 16 pt inset): toolbar (views Occlusal/Front/Left/Right/Back as text segments; display Solid / Transparent / Wireframe; Measure, Angle, Section; layer toggles Attachments, IPR, Target), tooltip pattern (label + mono shortcut), view-info pill, **view cube** 100 x 100 top-right, tooth callout with leader (selected tooth 13: buccal, rotation, remaining), legend bottom-left (shape + label for selected tooth, final position, attachment, IPR), scale bar bottom-right (10 mm). IPR values in mono magenta-bordered tags.
- 3D colours: enamel `model/enamel` with `model/enamel-shade` 1.5 pt outline; gingiva `model/gingiva` (palate at 45 % opacity); selected tooth 3 pt `select/blue` outline; target (setup) positions dashed `text/primary` at 70 %; attachments `model/attachment`; IPR planes `model/ipr`.
- Timeline: transport (first, previous, play, next, last; 36 pt), stage readout (`Stage 09 of 14, week 18`, mono 20 Bold), jaw toggles + "Overlay stage 0"; stage cells row 0..14 (each fill width, bar 20 tall radius 3): past = `bg/hover` + strong border, current = `select/blue` fill + bold number, future = `bg/sunken`, over-limit stage = warning outline + warning glyph. Event markers above cells: attachment (square, teal), IPR (diamond, magenta), warning (triangle).
- Inspector for **Planning > Staging**: header (circle-half icon, title, help, description), tabs Stages / Per tooth / Report, summary readouts (stages upper | lower, duration), "Max movement per stage" with reset link and 4 sliders (Translation 0.25 mm, Rotation 2.0° shown focused, Root torque 1.0°, Intrusion / extrusion 0.15 mm; value boxes 84 x 26 mono), stage table (Stage, Largest step, Moving, Events; current row = select/soft + 3 pt bar; warning row = warning text + icon), footer toggle "Keep upper and lower in step" + primary "Recompute staging" (40).
- Status bar: hint, background job (spinner, label, 120 pt bar, mono %, cancel x), units / numbering / fps / memory in mono.
- Interactions: `,` / `.` previous / next stage, Shift = 5 stages, Space = play, Home/End = first/last; clicking a tooth selects it (callout + inspector "Per tooth" tab gets the tooth); dragging across stage cells scrubs; Ctrl Z / Ctrl Shift Z undo / redo; Ctrl S save; F1 shortcuts sheet; `/` focuses the menu filter; Up/Down move in the menu, Left/Right collapse/expand, Enter activates.

### 06 Design system (`06 Design system`, page Design System)
Colour tokens (dark and light panels), type scale, spacing, radii, elevation, components (buttons, inputs, 3-level menu states, module cards, tabs, toggles, badges, sliders, progress, toasts), iconography.

## 5. Components

| Component | Variants / props | Spec |
|---|---|---|
| Button | Variant Primary/Secondary/Ghost x State Default/Hover/Focus/Disabled; text props Label, Icon | 36 tall (44/48 overrides), padding 0/16 (ghost 0/12), gap 8, radius 4, label 13 SemiBold, icon 16. Primary: amber fill, `on-amber` text; hover `amber-hover`; pressed `amber-pressed`; focus = 2 pt `focus/ring` outside. Secondary: `bg/raised` + 1 pt `border/strong`. Ghost: no fill, hover `bg/hover`. Disabled: `bg/hover` / no stroke, `text/disabled`. |
| Input | State Default/Focus/Error/Disabled; Label, Value, Helper | label 12 Medium, field 36 tall radius 4 `bg/sunken` + 1 pt `border/strong` (3.0:1), focus 2 pt ring inside, error 2 pt danger + warning-circle icon + danger helper with a fix. |
| MenuItem | Level Group/Item/Sub x State Default/Hover/Active/Disabled (+ Item Focus); Label, Icon, Caret, Meta, Status, Shortcut | Group 36 tall, padding 0/12, caret 12 + icon 18 + label 13 SemiBold + progress meta mono 11. Item 32, left padding 40, status glyph 16 + label 13. Sub 28, left padding 64, label 12 + shortcut mono. Hover `bg/hover`; Active `select/soft` + 3 pt left bar `select/blue`, label SemiBold; Focus 2 pt ring inside; Disabled `text/disabled`, lock glyph. |
| ModuleCard | State Available/Hover/Focus/Coming soon; Code, Meta, Icon, Name, Description, Status, StatusIcon, Action | 248 wide (fill in rows), radius 16/16/4/4, handle band 44 (`bg/sunken`, code mono Bold 20 amber-text), body padding 20 gap 8 (icon 32, name 18 SemiBold, description 13 secondary), footer hairline + status + action. Coming soon: dashed `border/strong` 4/4, no amber. |
| ProjectCard | Name, Status, StatusIcon, Stage, Edited | 330, radius 8, thumb 168 (`ArchThumb` 240 x 160 on `bg/viewport`). |
| Badge | Tone Neutral/Info/Success/Warning/Danger/Amber; Label, Icon | 22 tall pill, padding 0/8/0/6, icon 12, label 12 Medium, 1 pt tone stroke, tone text. |
| Toggle | State On/Off/Focus/Disabled; Label | track 36 x 20 pill, knob 14; On = `select/blue` track; Off = `bg/sunken` + strong border. |
| Tab | State Selected/Default/Hover/Focus; Label | 36 tall, padding 0/14, Selected = 2 pt bottom `select/blue` + SemiBold primary. |
| Slider | (frames) | label row + value box 84 x 26 mono; track 4 pt, fill `select/blue`, thumb 14 (`text/primary` fill, 2 pt blue ring; focused 4 pt `focus/ring`). Drag, arrow keys step by the unit (0.01 mm / 0.1°), Shift x10, double-click resets to lab default. |
| Progress | (frames) | 4 pt bar radius 2; label + mono value above. Indeterminate: 120 pt run sliding. |
| Toast | (frames) | `bg/raised`, 3 pt left bar in tone, icon 20, title 13 SemiBold, body 12, one underlined action, close x; e1; bottom-right of viewport, auto-dismiss 6 s except errors. |

## 6. Aligners left menu tree (i18n)

Group rows show `done/total` in mono; items show status (done / current / to do / locked). Sub-items are tools or modes inside a step.

| Level | i18n key | English | Italiano |
|---|---|---|---|
| 1 | `aligners.menu.case` | Case | Caso |
| 2 | `aligners.menu.case.import_scans` | Import scans | Importa scansioni |
| 2 | `aligners.menu.case.units_orientation` | Units & orientation | Unità e orientamento |
| 2 | `aligners.menu.case.case_info` | Case info | Dati del caso |
| 1 | `aligners.menu.preparation` | Preparation | Preparazione |
| 2 | `aligners.menu.preparation.auto_orientation` | Auto orientation & arch | Orientamento e arcata automatici |
| 2 | `aligners.menu.preparation.tooth_numbering` | Tooth numbering (FDI) | Numerazione denti (FDI) |
| 2 | `aligners.menu.preparation.segmentation` | Segmentation | Segmentazione |
| 3 | `aligners.menu.preparation.segmentation.auto` | Auto segmentation | Segmentazione automatica |
| 3 | `aligners.menu.preparation.segmentation.manual_brush` | Manual brush | Pennello manuale |
| 2 | `aligners.menu.preparation.tooth_reconstruction` | Tooth reconstruction | Ricostruzione dentale |
| 2 | `aligners.menu.preparation.gingiva` | Gingiva | Gengiva |
| 1 | `aligners.menu.diagnosis` | Diagnosis | Diagnosi |
| 2 | `aligners.menu.diagnosis.space_analysis` | Space analysis | Analisi dello spazio |
| 2 | `aligners.menu.diagnosis.little_index` | Little irregularity index | Indice di irregolarità di Little |
| 2 | `aligners.menu.diagnosis.bolton` | Bolton | Bolton |
| 2 | `aligners.menu.diagnosis.complexity_score` | Complexity score | Punteggio di complessità |
| 1 | `aligners.menu.planning` | Planning | Pianificazione |
| 2 | `aligners.menu.planning.setup` | Setup (final position) | Setup (posizione finale) |
| 2 | `aligners.menu.planning.tooth_movements` | Per-tooth movements (6-DOF) | Movimenti per dente (6 gradi) |
| 2 | `aligners.menu.planning.staging` | Staging | Stadiazione |
| 2 | `aligners.menu.planning.ipr` | IPR | IPR |
| 2 | `aligners.menu.planning.attachments` | Attachments | Attacchi |
| 2 | `aligners.menu.planning.schedule` | Schedule | Calendario |
| 1 | `aligners.menu.occlusion` | Occlusion | Occlusione |
| 2 | `aligners.menu.occlusion.virtual_bite` | Virtual bite | Occlusione virtuale |
| 2 | `aligners.menu.occlusion.bite_registration` | Bite registration (ICP) | Registrazione del morso (ICP) |
| 2 | `aligners.menu.occlusion.contact_map` | Contact map | Mappa dei contatti |
| 2 | `aligners.menu.occlusion.bite_with_aligners` | Bite with aligners | Occlusione con allineatori |
| 2 | `aligners.menu.occlusion.bite_ramps` | Bite ramps | Rialzi occlusali |
| 1 | `aligners.menu.production` | Aligner production | Produzione allineatori |
| 2 | `aligners.menu.production.model_base` | Model base & labels | Base del modello ed etichette |
| 2 | `aligners.menu.production.shell` | Aligner shell (thickness/clearance) | Guscio allineatore (spessore/gioco) |
| 2 | `aligners.menu.production.trim_line` | Trim line | Linea di rifinitura |
| 2 | `aligners.menu.production.id_stamp` | Identification stamp | Marcatura identificativa |
| 2 | `aligners.menu.production.print_check` | Print check | Verifica di stampa |
| 1 | `aligners.menu.follow_up` | Follow-up | Controlli |
| 2 | `aligners.menu.follow_up.control_visits` | Control visits | Visite di controllo |
| 2 | `aligners.menu.follow_up.tracking_replan` | Tracking & re-plan | Monitoraggio e ripianificazione |
| 1 | `aligners.menu.output` | Output | Esportazione |
| 2 | `aligners.menu.output.export_stl` | Export STL per stage | Esporta STL per stadio |
| 2 | `aligners.menu.output.report` | Report | Relazione |
| 2 | `aligners.menu.output.patient_viewer` | Patient viewer/animation | Visualizzatore/animazione per il paziente |
| 1 | `aligners.menu.tools` | Tools | Strumenti |
| 2 | `aligners.menu.tools.manual_tools` | Manual tools | Strumenti manuali |
| 2 | `aligners.menu.tools.history` | History | Cronologia |

Other keys used on the workspace (sample): `aligners.inspector.staging.title` Staging / Stadiazione; `aligners.inspector.staging.max_movement` Max movement per stage / Movimento massimo per stadio; `aligners.inspector.staging.recompute` Recompute staging / Ricalcola la stadiazione; `aligners.timeline.stage` Stage / Stadio; `aligners.viewport.view.occlusal` Occlusal / Occlusale; `common.save` Save / Salva; `common.undo` Undo / Annulla; `common.redo` Redo / Ripeti; `common.help` Help / Guida; `home.new_project` New project / Nuovo progetto; `home.open_project` Open project… / Apri progetto…; `home.modules` Modules / Moduli; `home.recent_projects` Recent projects / Progetti recenti; `account.sign_in_with` Sign in with DentalCraft account / Accedi con l'account DentalCraft; `support.title` Help & support / Assistenza.

i18n notes: Italian runs about 20 to 35 % longer (verified in `01 Home (IT)` and `05 Aligners workspace (IT)`): menu labels up to "Orientamento e arcata automatici" fit 288 pt; inspector section headers must wrap (header row is vertical for that reason); never set fixed widths on buttons.

## 7. Accessibility

- Contrast (dark): text/primary on panel 14.0:1, text/secondary 6.9:1, amber text 8.7:1, blue 6.5:1, on-amber on amber 9.2:1; inputs' `border/strong` 3:1 against panels. Light: primary 16.5:1, secondary 7.0:1, amber-text 5.9:1, blue 5.3:1.
- `text/disabled` intentionally below 4.5:1 (disabled controls are exempt) but always paired with a lock or the disabled state explanation.
- Every focusable widget has the 2 pt focus ring; tab order follows reading order (top bar, menu, viewport toolbar, timeline, inspector).
- Patient privacy: aliases only in UI and exports; diagnostics bundles exclude scan geometry and aliases.
