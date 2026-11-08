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
- Viewport overlays (absolute, 16 pt inset): toolbar (views Occlusal/Front/Left/Right/Back as text segments; **arches** Upper / Lower as two toggle segments, see below; display Solid / Transparent / Wireframe; Measure, Angle, Section; layer toggles Tooth colours, Tooth marks, Tooth numbers, Contact map; marks Attachments, IPR, Target), tooltip pattern (label + mono shortcut), view-info pill, **view cube** 100 x 100 top-right, tooth callout with leader (selected tooth 13: buccal, rotation, remaining), legend bottom-left (shape + label for selected tooth, final position, attachment, IPR), scale bar bottom-right (10 mm). IPR values in mono magenta-bordered tags.
- **Arch selection** (viewport toolbar, right after the view segments, a separator on each side): two toggle segments **Upper** / **Lower** (`ws-arch-upper`, `ws-arch-lower`; same text-segment style as the views, selected = `bg/hover` and semibold; role checkbox for screen readers; tooltip "Show or hide the upper arch" / "...lower arch"). They choose which arches are shown and are independent of the 3D view: no view preset (Occlusal, Front, Left, Right, Back, nor a click on the view cube) changes them, and they never change the camera except in one case: while the camera is on an occlusal view, hiding or showing an arch moves it to the one that looks at what is shown (from below at the upper arch, from above at the lower one; both shown = the upper one). At least one arch that has a scan stays on: the click on the last one is refused and its tooltip adds "At least one arch stays shown". A hidden arch is not drawn, not picked (hover and the manual tools), has no tooth number chips and no seed gems, and its stage 0 ghost and seed markers are hidden with it. The choice is kept for the workspace session (not saved in the `.dcprj`). The caption chip shows "Upper jaw" / "Lower jaw" / "Both jaws". Headless renders (CLI/MCP) choose arches with `view.set {"visible": [...]}`, independent of `view`/`preset`. Tooth number chips follow the teeth at the stage shown (anchor moved by the tooth pose) and sit on the crown of the 3D teeth or, in Scan view, on the crown painted on the scan. Renders also take `model` (`scan` | `teeth`) and `stage` (integer): the CLI defaults to the 3D teeth at the initial position, the app bridge to what the viewport shows (model and stage); the raster draws scans at rest whatever the stage.
- 3D colours: enamel `model/enamel` with `model/enamel-shade` 1.5 pt outline; gingiva `model/gingiva` (palate at 45 % opacity); selected tooth 3 pt `select/blue` outline; target (setup) positions dashed `text/primary` at 70 %; attachments `model/attachment`; IPR planes `model/ipr`.
- Timeline: transport (first, previous, play, next, last; 36 pt), stage readout (`Stage 09 of 14, week 18`, mono 20 Bold), the "Overlay stage 0" toggle (the arch toggles are in the viewport toolbar); stage cells row 0..14 (each fill width, bar 20 tall radius 3): past = `bg/hover` + strong border, current = `select/blue` fill + bold number, future = `bg/sunken`, over-limit stage = warning outline + warning glyph. Event markers above cells: attachment (square, teal), IPR (diamond, magenta), warning (triangle).
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
| | `aligners.teeth.find` | Find the teeth | Trova i denti | step |
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

### Tooth numbers and the Alt+click brush (viewport)

- **Tooth numbers.** Every tooth that has a tooth mark, a measured tip or painted colours gets a **chip** over the viewport: 28 x 17 pt, radius 4, text mono 11 (points, so they scale with the UI scale), filled with the colour of the tooth (the same palette as the scan colours), the FDI number in black or white, whichever has the higher contrast (always at least 4.5:1), and a 1 pt outline of `border/strong`. The chip sits centred 6 pt above its anchor on the screen. Anchor, best first: the cusp tip measured by the teeth stage, else the top of the painted crown (centre of the crown raised to its highest point along the occlusal direction, as the plugin does), else the tooth mark. Chips that would overlap are moved up a few steps (the nearest to the camera keeps its place). A chip whose anchor is behind the scan (a ray from the camera meets the scan first) is hidden; so is that of an arch that is hidden. Teeth marked missing have none. They follow the stage shown (a moved tooth carries its chip). They are drawn in every state of the workspace, not only in Find the teeth, and are switched on and off by the layer toggle **Tooth numbers** (`ws-layer-numbers`, hash icon, in the layers group of the toolbar, on by default).
- **Alt+click chooses the brush tooth.** From any manual tool, and also when no tool is open (Find the teeth), Alt+click on: a tooth number chip (the topmost first), else a tooth mark gem (the nearest to the pointer within its drawn radius + 4 pt), else the scan (the tooth painted under the pointer; the bare gingiva chooses the gingiva, brush 0) opens the tooth brush if it is not the open tool and sets its tooth. Toast "Brush" with "Tooth 36" (or "Gingiva"). Alt+click never paints, places a mark or picks a tooth for the tool; the brush modifiers are unchanged (Shift gingiva, Ctrl fill the crown, Ctrl+Shift fill with gingiva). While the numbering in order is going on Alt+click only says to finish it first. While Alt is held, the chip or gem under the pointer is outlined in `select/blue`; the chip of the brush tooth is always outlined so. The hint of the brush panel says: "Alt+click on a tooth, its number or its mark: paint that tooth." On Linux some window managers take Alt+drag/click for moving windows: set the manager's window key to Super.

### Find the teeth (`aligners.teeth.find`)

The leaf runs the wrapper command `aligners.teeth.find`: the automatic numbering (`aligners.preparation.numbering.automatic`) first, then the automatic orientation (`aligners.preparation.orientation.automatic`), as **one undo step**. Each arch is numbered on its own. An arch that fails keeps the tooth marks it had and is named in a notice; the other arch gets its new marks.

Inspector (below the description of the leaf):

- Section "Options" with the checkbox "Search also the third molars".
- Field "Missing teeth" (hint "e.g. 35, 45"; FDI numbers separated by commas, semicolons or spaces; helper "FDI numbers separated by commas. They are applied when you leave the field."). While you type, a wrong number shows the red message "Not a tooth number: <entries>. Use FDI numbers: 11 to 18, 21 to 28, 31 to 38, 41 to 48." The field is labelled for screen readers. The list is saved when the field loses focus and the text is valid; a wrong text is not saved. **Run is not blocked**: it uses the last saved list.
- Section "Teeth found": for each arch that has a scan, a title ("Upper arch" / "Lower arch") and a grid of 8 columns by 2 rows, one cell per tooth, right side of the patient first (upper: 18..11, 21..28; lower: 48..41, 31..38). The third molars (18, 28, 38, 48) are left out when the checkbox is off. A cell is a small box and the tooth number, in one of three states: filled box (the tooth has a mark; hover and screen-reader text "<n>: has a mark"), crossed box ("<n>: missing"; a tooth in the missing list wins over a mark), empty box ("<n>: no mark"). Under the grids: "<n> teeth numbered" and the legend "Filled box: the tooth has a mark. Crossed box: the tooth is missing." Without any arch scan the section says "Import the scan of an arch to see its teeth."
- The checkbox and the list are saved in the case through `aligners.settings.find-teeth` (`Settings.find_teeth`), one undo step each, so they come back when the project is reopened.
- The primary button runs the leaf with these settings; a step already done offers Run again as a secondary button (as for every leaf).

Notices after a change of the tooth marks (toasts of the workspace, not part of the inspector):

- Automatic numbering drops what depends on the marks of that arch. Toast "Results cleared": "Cleared because the tooth marks changed: <list>. Run those steps again; Ctrl+Z brings the previous tooth marks and these results back."
- Manual mark edits (place, sequence, clear) keep that data and mark it out of date. Toast "Results out of date": "Kept but out of date because the tooth marks changed: <list>. Run teeth and gum again, then the steps after it."
- An arch that could not be numbered: toast "An arch was not numbered": "<reasons>. That arch keeps the tooth marks it had; the other arch has its new ones."

Manual tools, in the "Mark a tooth" panel (`aligners.preparation.numbering.place-seeds`):

- **Number the teeth in order** (button, with the checkbox "Include the third molars", which starts from the setting of Find the teeth). The command is `aligners.preparation.numbering.sequence`, sent once at the end, so the whole numbering is one undo step. The panel asks "Click tooth <n>" (or "Click a tooth on the scan to start" while the arch is not known, "All the teeth are numbered" at the end) and the hint says "Click the centre of the biting surface of the tooth shown, from the patient's right to the left. S: skip this tooth. Backspace: go back. Enter or Esc: done." The order is upper 18..11 then 21..28, lower 48..41 then 31..38, without the teeth that already have a mark or are missing. With two arches the first click chooses the arch; a click on the other scan shows "Click on the same scan until the numbering is done."
- Keys and buttons: **S** or "Skip (S)" skips the tooth (not added to the missing teeth), **Backspace** or "Back (Backspace)" takes the last step back, **Enter** or **Esc** or "Done (Enter)" finishes and keeps the marks, "Cancel" discards the marks of the session. The numbering also ends by itself on the last tooth of the order. It stops with the notice "The numbering in order stopped because the case changed (undo, redo or another command): start it again." when the undo stack moves under it. Finishing with no click sends nothing; success shows "The teeth were numbered." with the count and the next tooth.
- **Clear all the tooth marks** (button; `aligners.preparation.numbering.clear-seeds`, called with no parameters, so both arches) removes all the marks of the case and keeps the missing-teeth list. Notice "The tooth marks were cleared."

Other keys used on the workspace (sample): `aligners.inspector.staging.title` Staging / Stadiazione; `aligners.inspector.staging.max_movement` Max movement per stage / Movimento massimo per stadio; `aligners.inspector.staging.recompute` Recompute staging / Ricalcola la stadiazione; `aligners.timeline.stage` Stage / Stadio; `aligners.viewport.view.occlusal` Occlusal / Occlusale; `common.save` Save / Salva; `common.undo` Undo / Annulla; `common.redo` Redo / Ripeti; `common.help` Help / Guida; `home.new_project` New project / Nuovo progetto; `home.open_project` Open project… / Apri progetto…; `home.modules` Modules / Moduli; `home.recent_projects` Recent projects / Progetti recenti; `account.sign_in_with` Sign in with DentalCraft account / Accedi con l'account DentalCraft; `support.title` Help & support / Assistenza.

i18n notes: Italian runs about 20 to 35 % longer (verified in `01 Home (IT)` and `05 Aligners workspace (IT)`): menu labels up to "Cambia il numero di un dente" fit 288 pt; inspector section headers must wrap (header row is vertical for that reason); never set fixed widths on buttons.

### Separate teeth and gum (`aligners.preparation.segmentation.automatic`, "Separa denti e gengiva")

The leaf (menu label "Separate teeth and gum" / "Separa denti e gengiva") runs `aligners.preparation.segmentation.automatic` as **one undo step**, one arch at a time (an arch with a scan; with two arches each is separated on its own). It starts from the tooth marks (see Find the teeth) and paints every tooth on the scan with its own colour; the gum stays uncoloured.

Refusals (nothing changes, localised notice that names the arch, "Upper arch" / "Lower arch"):

- Fewer than 4 tooth marks on the arch: "<arch>: mark at least 4 teeth first." / "<arch>: segna prima almeno 4 denti."
- Marks missing on one side (right or left) or on the incisors: "<arch>: the tooth marks must cover both sides and the front teeth." / "<arch>: i segni dei denti devono coprire entrambi i lati e i denti anteriori."

Inspector (below the description of the leaf):

- Info line: "It starts from the tooth marks. Running it again erases the colours you painted by hand." / "Parte dai segni dei denti. Se lo esegui di nuovo, cancella i colori dipinti a mano."
- Folded section "Separation parameters" / "Parametri di separazione" (closed by default), three sliders with the unit-less value shown:
  - "Scan detail (faces)" / "Dettaglio della scansione (facce)": 5000 to 200000, default 30000.
  - "Tooth edge sensitivity" / "Sensibilità dei bordi dei denti": 0.01 to 1, default 0.2.
  - "Border smoothing" / "Levigatura dei bordi": 0.1 to 10, default 1.0.

  They are stored in the case settings (one undo step each), come back when the project is reopened, and are the same values **Run everything** uses.
- After a run, the result line "<n> teeth separated in <s> s" / "<n> denti separati in <s> s" (one line per arch that ran; the same text in the success toast "Teeth and gum separated" / "Denti e gengiva separati").
- The primary button runs the leaf; once done it offers Run again as a secondary button (as for every leaf).

Progress: the job runs in the status bar with the label "Separating teeth and gum" / "Separazione di denti e gengiva", the usual progress bar and cross to stop, and these sub-steps, in order: "Simplified scan" / "Scansione semplificata", "First separation" / "Prima separazione", "Tooth colours on the full scan" / "Colori dei denti sulla scansione completa", "Borders at full resolution" / "Bordi alla piena risoluzione", "Cleanup" / "Pulizia". Stopping leaves the arch as it was.

After a successful run:

- 3D teeth and the steps after it (and their check marks in the menu) are marked out of date: the check marks are removed and the toast "Results out of date" lists them (same wording as after a change of the tooth marks).
- The viewport switches to **Scan** view, so the new colours are visible (the 3D teeth toggle is described above).
- Seed-check problems and notes found by the run are kept in the case and shown again as a warning when the case is exported.

Reachable from CLI and MCP as the command `aligners.preparation.segmentation.automatic` (parameters `arch`, and the three separation parameters, defaulting to the saved settings); the whole automatic pipeline (`aligners.auto`) runs it after the numbering and orientation.

### 3D teeth (`aligners.teeth.build`, "Denti 3D")

The leaf (menu label "3D teeth", description "Gives you every tooth as a closed 3D model with its axis, and a gum that follows the teeth.") runs `aligners.teeth.build` with parameters `arch` (all, upper, lower) and `teeth` (FDI numbers to build again), as **one undo step**. It needs teeth and gum separated. Per arch:

- **All the teeth** (the default for an arch not built yet, or built with no hand corrections): closes every tooth as a 3D solid (measuring the teeth first), then builds the gingiva. The final position (setup) and the aligners of that arch are cleared, since they were planned on the old teeth.
- **Some teeth** (`teeth` given, or, without it, an arch already built whose teeth were corrected by hand with the brush or clean-up, plus teeth with colours but no solid and solids left without colours): the arch is measured again, only those teeth are closed again (a tooth with no colour left is removed, as a missing tooth), the gingiva is built again. The other teeth keep their solids. A rebuilt tooth keeps its planned movement in the world and its lock; a locked tooth goes back to rest; a removed tooth loses both. The aligners of the arch are cleared, the setup is kept.
- Then **Case analysis** (the diagnosis) runs on the new teeth.
- The scan is not deleted: where the viewport shows the 3D teeth, the built teeth of an arch replace its scan (see the toggle below). Wrong tooth numbers, or teeth of an arch not asked for, are refused before anything runs.

Progress: the job runs in the status bar with the label "Building the 3D teeth" and the usual progress bar and cross to stop. Success toast "3D teeth built" with the detail "<n> teeth built (upper <u>, lower <l>), gingiva for upper and lower." (the last part reads "gingiva for upper", "gingiva for lower" or is left out when no gingiva was built; for a partial rebuild <u> and <l> count the rebuilt teeth).

Viewport toolbar, right after the arch toggles: a two-segment toggle **Scan** / **3D teeth** (role radio button; tooltips "Show the scans of the arches" / "Show the built teeth and gingiva instead of the scans"). The default is 3D teeth, which show only for arches that were built; an arch not built keeps its scan. The scan is shown whatever the choice while the brush, the clean-up or the seed tools are open (they paint and read the scan labels) and while the **Contact map** layer is on; the toggle then shows Scan and its tooltip adds "The scan is shown while a tool works on it or the contact map is on". Closing the tool or switching the contact map off returns to the 3D teeth. A tool that picks a tooth works on the 3D teeth. The choice is kept for the workspace session.

Stages: with 3D teeth shown, a later stage poses each tooth by its pose of that stage, the stage 0 ghost draws the rest position, and the **gingiva deforms** with the teeth (blended by weights on the teeth). The weights are slow the first time: they are computed in the background and the gingiva is drawn at rest until they are ready. The scans always stay at rest. Tooth number chips follow the stage poses (see above).

Reachable from CLI and MCP as the command `aligners.teeth.build`; the whole automatic pipeline (`aligners.auto`) runs it after the check of the segmented teeth. `render` takes `model` and `stage` (see Arch selection).

## 7. Accessibility

- Contrast (dark): text/primary on panel 14.0:1, text/secondary 6.9:1, amber text 8.7:1, blue 6.5:1, on-amber on amber 9.2:1; inputs' `border/strong` 3:1 against panels. Light: primary 16.5:1, secondary 7.0:1, amber-text 5.9:1, blue 5.3:1.
- `text/disabled` intentionally below 4.5:1 (disabled controls are exempt) but always paired with a lock or the disabled state explanation.
- Every focusable widget has the 2 pt focus ring; tab order follows reading order (top bar, menu, viewport toolbar, timeline, inspector).
- Patient privacy: aliases only in UI and exports; diagnostics bundles exclude scan geometry and aliases.
