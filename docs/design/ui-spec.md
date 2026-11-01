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
- Numbered columns (a real sequence): 1 Module (400), 2 Case (fill), 3 Scans (640). Footer bar: save path in mono + "Change location" link, ghost Cancel, primary "Create project" (44; it only creates the project, it does not segment).
- Module options: shade-tab code tile 44 x 48 + name + description + radio; non-installed modules disabled with "Coming soon" badge.
- Case: Case ID (Input), Patient alias (pseudonymised; helper forbids real names), Jaw segmented (Upper / Lower / Both jaws; stored in the case, it does not choose any scan's role), technician notes textarea (150), units note (metres, centimetres and micrometres are converted to millimetres on import; the file row shows the unit found and the conversion).
- Scans: drop zone (dashed; the text says the arch comes from the file name, or from the scan's shape when the name says nothing, and that a badge click changes it; the dialog and the drop accept STL, PLY and OBJ in any letter case) and the file list. Row: cube icon, file name, second line in mono (`size MB · triangles · units`, units as `mm` or `cm → mm`), role badge, remove button. The probe (`dc_case::import::prepare`) runs on a worker thread per file: the row shows a spinner and "Reading the file..." until it answers; an empty or corrupt file turns its row red with the reason at once and blocks nothing else; a removed row cancels its probe and its late answer is dropped. Role badge: **Auto** (neutral, wand icon) when the name says nothing, the name's role as a neutral hint, or the user's choice in blue. A click goes Auto, Upper, Lower, Bite, Auto; a row hinted by its name never goes to Auto (the name still counts), its cycle ends back on the hinted role, which is no choice at all. Only a chosen role is sent explicitly; the rest is `auto` and the import decides (file name, then the shape of the scan, then a free arch marked provisional). Create imports all rows in one call; a bad file does not stop the others and shows in the workspace report; if no file imports, the form stays and lists the reason of every file.
- Not built: the "Convert" button for a unit mismatch (units are converted automatically on import), and the real mesh preview. The preview panel shows a placeholder arch with a note that it is not the mesh.

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
- Left menu: filter field (32, `/` shortcut) then the tree (section 6). Footer: workflow progress (`3/8` mono + success bar: the steps done out of the eight steps of the workflow, section 6).
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

The menu is for the dentist and the technician: six groups and 19 commands (leaves), two levels, plus one closed sub-group. Wording is plain, with no name of an algorithm. The other commands of the module (the single stages, the settings) are reached from the CLI and the MCP server only. A leaf is the command `aligners.<path>`; its Fluent keys are `aligners-menu-<path>` (label) and `aligners-desc-<path>` (description in the inspector), the dots turned into hyphens.

Progress: the footer and the group rows count only the **eight steps** of the workflow, marked **step** below: Import scans, Find the teeth, Separate teeth and gum, 3D teeth, Case analysis, Bite, Final position, Aligners. The footer reads `done/8` (mono, with the success bar). A group row shows `done/total` of its own steps in mono; a group with no step (Production, Follow-up) shows no counter. Run everything automatically, the manual corrections, Move a tooth, Export for printing, Study models, Control visit and Re-plan are not steps: they are shortcuts, optional tools, outputs and follow-up, and never count.

A leaf shows a check mark when the case holds its result: after a fresh run and after reopening the project (the module reads it from the case data; undoing a step takes the mark away). The leaves that leave nothing in the case (Move a tooth, the exports, the re-plan, the pipeline) never show one.

| Group | Leaf / sub-group | English | Italiano | Counts |
|---|---|---|---|---|
| Case (`aligners.case`) | | Case | Caso | 1 step |
| | `aligners.case.import-scans` | Import scans | Importa scansioni | step |
| | `aligners.auto` | Run everything automatically | Esegui tutto in automatico | no |
| Teeth (`aligners.teeth`) | | Teeth | Denti | 3 steps |
| | `aligners.preparation.numbering.automatic` | Find the teeth | Trova i denti | step |
| | `aligners.preparation.segmentation.automatic` (key A) | Separate teeth and gum | Separa denti e gengiva | step |
| | `aligners.teeth.build` | 3D teeth | Denti 3D | step |
| | sub-group `aligners.teeth.manual`, closed by default | Manual corrections | Correzioni a mano | no |
| | `aligners.preparation.numbering.place-seeds` | Mark a tooth | Segna un dente | no |
| | `aligners.preparation.numbering.renumber` | Change a tooth number | Cambia il numero di un dente | no |
| | `aligners.preparation.numbering.mark-missing` | Missing tooth | Dente assente | no |
| | `aligners.preparation.segmentation.manual-brush` (key B) | Tooth brush | Pennello dei denti | no |
| | `aligners.preparation.segmentation.clean-borders` | Clean borders | Pulisci i bordi | no |
| Diagnosis (`aligners.diagnosis`) | | Diagnosis | Diagnosi | 1 step |
| | `aligners.diagnosis.space-analysis` | Case analysis | Analisi del caso | step |
| Plan (`aligners.planning`) | | Plan | Piano | 3 steps |
| | `aligners.occlusion.align` | Bite | Morso | step |
| | `aligners.planning.setup.automatic` | Final position | Posizione finale | step |
| | `aligners.planning.movements` | Move a tooth | Sposta un dente | no |
| | `aligners.planning.aligners` (key S) | Aligners | Allineatori | step |
| Production (`aligners.production`) | | Production | Produzione | none |
| | `aligners.output.export-all` (asks for a folder) | Export for printing | Esporta per la stampa | no |
| | `aligners.output.study-models` | Study models | Modelli da studio | no |
| Follow-up (`aligners.followup`) | | Follow-up | Visite | none |
| | `aligners.followup.visits` (asks for a scan) | Control visit | Visita di controllo | no |
| | `aligners.followup.tracking` | Re-plan | Ripianifica | no |

Behaviour of a click on a leaf:

- **Import scans** opens the file dialog (STL, OBJ, PLY).
- **Export for printing** opens a folder dialog, **Control visit** a scan file dialog; the answer goes to the command as its parameter (`dir`, `scan`). A cancelled dialog does nothing; while another command runs the click shows the "another operation is running" notice. The export runs in the background with the job in the status bar (name, bar, cancel cross), warns in one line that it can take a long time, can be stopped, and leaves no half-written folder: the files are built in a hidden folder inside the target and moved into place when all are made, the manifest last. When it ends, a notification that stays until closed gives the folder and the number of files.
- **Bite** shows which method ran: the registration on the bite scan, or the estimate (the case has no bite scan, said as a warning). **Run everything automatically** uses the same bite.
- **Run everything automatically** is one job with the step it is on named in the status bar and a cross to stop it. It stops with a clear message at the first step that fails, for instance on an arch the program only guessed (the message says which scan to check); the case is left as it was. When it ends it refreshes the viewport, selects the next leaf (the first step with no result, otherwise Case analysis) and shows a summary notification ("Everything ran: 14 steps in 3 min 20 s. Next: check the results in Case analysis, then use Export for printing.").
- **Case analysis** shows its results in the inspector, one card per arch (space available and needed, difference with the words Crowding / Spacing / Enough space, Little index with its category), then the Bolton ratios and the complexity of the case with its level.
- The inspector of a leaf has a clear primary button under the description (Run, or Choose the scan files…, Choose the folder and export…, Choose the scan of the visit…); a step already done offers Run again as a secondary button. Manual tools open their own panel instead.
- The keyboard sheet (F1) lists the keys of the tools in key order: A Separate teeth and gum, B Tooth brush, S Aligners.

Other keys used on the workspace (sample): `aligners.inspector.staging.title` Staging / Stadiazione; `aligners.inspector.staging.max_movement` Max movement per stage / Movimento massimo per stadio; `aligners.inspector.staging.recompute` Recompute staging / Ricalcola la stadiazione; `aligners.timeline.stage` Stage / Stadio; `aligners.viewport.view.occlusal` Occlusal / Occlusale; `common.save` Save / Salva; `common.undo` Undo / Annulla; `common.redo` Redo / Ripeti; `common.help` Help / Guida; `home.new_project` New project / Nuovo progetto; `home.open_project` Open project… / Apri progetto…; `home.modules` Modules / Moduli; `home.recent_projects` Recent projects / Progetti recenti; `account.sign_in_with` Sign in with DentalCraft account / Accedi con l'account DentalCraft; `support.title` Help & support / Assistenza.

i18n notes: Italian runs about 20 to 35 % longer (verified in `01 Home (IT)` and `05 Aligners workspace (IT)`): menu labels up to "Cambia il numero di un dente" fit 288 pt; inspector section headers must wrap (header row is vertical for that reason); never set fixed widths on buttons.

## 7. Accessibility

- Contrast (dark): text/primary on panel 14.0:1, text/secondary 6.9:1, amber text 8.7:1, blue 6.5:1, on-amber on amber 9.2:1; inputs' `border/strong` 3:1 against panels. Light: primary 16.5:1, secondary 7.0:1, amber-text 5.9:1, blue 5.3:1.
- `text/disabled` intentionally below 4.5:1 (disabled controls are exempt) but always paired with a lock or the disabled state explanation.
- Every focusable widget has the 2 pt focus ring; tab order follows reading order (top bar, menu, viewport toolbar, timeline, inspector).
- Patient privacy: aliases only in UI and exports; diagnostics bundles exclude scan geometry and aliases.
