# DentalCraft — Implementation Plan v1 (see DECISIONS.md for overrides)

## 1. Repos & crates
Superproject `dentalcraft` (no code, no versioning): `.gitmodules`, `.github/workflows/submodules.yml`, `CODEOWNERS`, `docs/` (architecture, ADRs, plan), `.cargo/config.toml` (local `[patch]` overrides, see 1.1).

| Submodule | Lang | Purpose |
|---|---|---|
| dentalcraft-core | Rust lib workspace | Engine (no app shell): geometry, case model, project I/O, commands, jobs, module API, scene description, i18n, theme |
| dentalcraft-aligners | Rust lib workspace | First dental module, display "Aligners"/"Allineatori", id `aligners` |
| dentalcraft-app | Rust bin workspace | Shipped product: eframe shell, wgpu viewport, auth client, packaging, regulatory dossier |
| dentalcraft-server | Go | OIDC identity provider (closed, private repository; not part of the public superproject) |

Core headless (testable on CI without GPU). Modules depend only on core.

### dentalcraft-core crates
- `dc-mesh`: `TriMesh{positions: Vec<Vec3A>, tris: Vec<[u32;3]>, attrs}`, adjacency, boundary loops, components; STL/OBJ/PLY I/O; unit detection (m/cm/µm→mm); validation (manifold/watertight).
- `dc-geom`: BVH (parry3d), point-to-plane ICP, QEM decimation, Liepa hole fill, narrow-band SDF (offset/closing/mesher), sparse PCG (sprs, Jacobi), harmonic solves; rayon; `Backend` trait for later GPU.
- `dc-case`: `Case`, `Scan{role: Upper|Lower|Bite}`, `Fdi(u8)`, `WorldFrame`, `Pose{t: DVec3, q: DQuat}`, `BlobRef(blake3)`; immutable `Arc<CaseState>`, `ModuleState(Box<dyn ModuleData>)`.
- `dc-command`: `trait Command { fn id(&self)->&'static str; fn apply(&self, &CaseState, &mut JobCtx) -> Result<CaseState>; }`; `UndoStack` of `Arc<CaseState>` (structural sharing, memory budget); `StepHistory` port of old steps.py (`StepRecord{step, inputs_hash, outputs, by_hand}`, retry/rewind/undo-rewind).
- `dc-jobs`: `JobSystem::spawn(name_key, f) -> JobHandle<T>`, progress (fraction + message key), cancel token, rayon; results delivered as Commands (undoable).
- `dc-scene`: GPU-agnostic `SceneItem::{Mesh{blob, colors|labels, xform}, Lines, Points, Labels3d}`, `Overlay`.
- `dc-project`: `.dcprj` read/write + migrations (§2).
- `dc-module-api`: `trait Module { fn id(); fn name_key(); fn menu(&self)->MenuTree; fn commands(&self)->Vec<CommandDesc>; fn inspector(&mut self, ui:&mut egui::Ui, ctx:&mut ModuleCtx); fn scene(&self,&CaseState)->Vec<SceneItem>; fn data_codec()->Box<dyn ModuleCodec>; }`; `MenuTree`/`MenuItem{id,label_key,icon,command|submenu,status: Ready|Stub}`; `ModuleRegistry` (static registration; installed = compiled-in + enabled by entitlement).
- `dc-i18n`: i18n-embed + fluent, `fl!` macro (compile-time checked keys), per-crate `i18n/{en,it}/<crate>.ftl`, global runtime-switchable `Localizer`.
- `dc-theme`: `tokens/tokens.json` (from FigCraft) → `build.rs` generates `tokens.rs`; `Theme::apply(&egui::Context, Mode::{Light,Dark})`.

### dentalcraft-aligners crates
- `dca-model`: `AlignersState` (seeds, label blob, tooth frames, diagnosis, setup, `Stage{index, poses: BTreeMap<Fdi,Pose>, ipr}`, trim params), schema migrations.
- `dca-algo`: one module per pipeline stage (autoseed, segmentation, reconstruct, diagnosis, setup, staging, occlusion, shell, trim, stamp, visits, export).
- `dca-module`: `AlignersModule: Module`, full menu tree, inspectors, commands.

### dentalcraft-app crates
- `dc-app` (bin `dentalcraft`): screens `Home | Login | Support | ModuleChooser | Workspace(ModuleId)`, settings, recent projects.
- `dc-viewport`: egui_wgpu paint callback, orbit/pan/zoom camera, standard dental views, CPU picking via dc-geom BVH, per-vertex label palette.
- `dc-auth-client`: PKCE loopback + keyring.
- `xtask`: trace check, SOUP generation, packaging.

Deps constraints: eframe `wgpu` feature, winit dlopen; `rfd` xdg-portal; `keyring` async-secret-service (pure Rust zbus); reqwest rustls with `ring` (aws-lc needs cmake); no C++ crates.

### 1.1 Cross-submodule Cargo deps
Consumers: `dc-x = { git = "https://github.com/dnviti/dentalcraft-core.git", tag = "vX.Y.Z" }` (`branch="main"` until core v0.1.0; `dnviti-personal-org` before the 2026-11-21 move). Superproject `.cargo/config.toml`: `[patch."https://github.com/dnviti/dentalcraft-core.git"]` path overrides for every crate (and same for aligners) + `net.git-fetch-with-cli = true` → local builds inside the superproject use working trees; standalone CI builds against tags/branch. Cargo.lock committed; CI lock-guard fails if any dc-*/dca-* lock entry lacks a `git+` source; agents `git checkout -- Cargo.lock` before committing if only dc-* entries changed.

## 2. `.dcprj` v1
ZIP; first entry `mimetype` stored = `application/vnd.dentalcraft.project+zip`; JSON deflate, blobs zstd.
- `manifest.json`: `{format:"dcprj", format_version:1, project_id(uuid), app:{version,commit}, created, modified, units:"mm", modules:[{id,version,schema_version}], entries:{path:{blake3,bytes}}}`
- `case.json`: pseudonymised patient code (no names in v1), scans `[{id, role, source_name, source_units, import_xform, mesh: BlobRef}]`, `world_frame` (old worldframe.py convention: occlusal plane XY, midline Y, incisors −Y, lower +Z).
- `modules/<id>/state.json`: module data; stages per-tooth `Pose{t:[f64;3], q:[f64;4] xyzw}` relative to the tooth initial pose, world mm.
- `history/steps.json` (undo stack not persisted); `blobs/<blake3>.dcm`; `thumbnail.png`.
- Mesh blob `DCM1` LE: magic, version, nv, nf, attribute table; f32x3 positions, u32x3 indices, optional normals, per-vertex u16 labels, per-face u16 labels.
- BLAKE3 over uncompressed canonical bytes (dedup); verified on load; mismatch → read-only + error.
- Atomic save: `*.dcprj.tmp`, fsync, rename, keep one `.bak`.
- Migrations chained on serde_json::Value per container (`format_version`) and per module (`schema_version`); newer → read-only; unknown module state kept opaque and written back, flagged in UI.

## 3. Sign-in server (closed repository): the contract the app relies on
The server itself is closed source and is not documented here. The desktop app (`dc-auth-client`) needs an OpenID Connect issuer with: `/.well-known/openid-configuration` (all endpoints on the issuer's origin), `/oauth/jwks.json`, `GET /oauth/authorize` (authorization code with PKCE S256 required; the redirect is a loopback `http://127.0.0.1:{any}/callback`, RFC 8252; `iss` in the redirect, RFC 9207; `ui_locales` en/it), `POST /oauth/token` (`authorization_code` and rotating `refresh_token`), `POST /oauth/revoke` (RFC 7009), and `GET /api/v1/me` (profile and `entitlements:{modules:["aligners"]}`). Public client id `dentalcraft-desktop`; id_token signed with EdDSA (Ed25519). Full list: README, "Sign-in server".
Desktop flow: TcpListener 127.0.0.1:0 → system browser (webbrowser crate) with state, nonce, PKCE → one-shot callback page → exchange (reqwest/rustls) → verify id_token via cached JWKS → refresh token in keyring (service `dentalcraft`, account = issuer), access token in memory → silent refresh on start. Login optional for local work in v1.

## 4. Work packages
Wave 1 (today):
- WP1 Repos/CI (M): gh repo create ×5; per repo release-please, ci.yml (self-hosted runner; fmt, clippy -D warnings, test; Go vet/gofmt/test), release-please.yml, CODEOWNERS, rust-toolchain.toml 1.99.1, deps SSH step; superproject .gitmodules + submodules.yml.
- WP2 Core API contracts (C): all public traits/types above with minimal working impls, rustdoc, UndoStack/StepHistory tests.
- WP3 Sign-in server (M, closed repository): OIDC authorization code + PKCE flow, token rotation, dev mode.
- WP4 Theme + i18n infra (S): dc-i18n with en/it key parity test; dc-theme tokens codegen.
- WP5 Mesh I/O (M): STL ascii/bin, OBJ, PLY, unit fix, validation; round-trip tests.
- WP6 .dcprj (M): writer/reader, blake3, atomic save, migration fixture; byte-identical round-trip; corruption detected.
- WP7 Viewport (C): wgpu mesh pipeline, camera, picking, standard views; 300k tris 60 fps.
- WP8 App shell (C): Home, Login, Support, Module chooser, Workspace (multi-level left menu, viewport, inspector, status/job bar), en/it switch; egui_kittest smoke over all screens both languages.
- WP9 Aligners menu + stubs (M): full menu tree (mirror old ui_phases.py), stub commands "Not yet available"; en/it keys for every item.
- WP10 Auth client (M): PKCE loopback, keyring, refresh; integration test against a development issuer.
- WP11 Integration (C): Import→view→save/load .dcprj→reopen; release core v0.1.0, consumers to tag; superproject pointer bumps; screenshots in docs/.
Wave 2 (core geometry, golden-validated): WP12 golden harness (old plugin headless Blender → JSON/.dcm fixtures), WP13 BVH/closest/ray, WP14 ICP, WP15 QEM, WP16 Liepa, WP17 PCG/harmonic, WP18 SDF.
Wave 3: WP19 world frame/import, WP20 autoseed, WP21 segmentation, WP22 reconstruction, WP23 diagnosis, WP24 overlays/paint.
Wave 4: WP25 setup, WP26 staging/IPR/.ics, WP27 occlusion/bite ICP, WP28 animation.
Wave 5: WP29 shell/blockout, WP30 trim, WP31 stamp (SDF emboss), WP32 print check/export, WP33 bite with aligners/ramps.
Wave 6: WP34 visits, WP35 manual tools, WP36 wgpu compute, WP37 licensing/tickets, WP38 xtask trace/SOUP, WP39 packaging.

## 5. Testing
rustfmt + clippy --all-targets -D warnings; cargo-deny from wave 2; unit tests per crate; proptest for topology and .dcprj; golden tolerances: vertices Hausdorff < 0.01 mm, labels ≥ 99 %, poses < 0.01 mm / 0.05°, diagnosis rel < 1e-3; Teeth3DS via `$DC_TEETH3DS`, never committed; egui_kittest logic tests in CI, wgpu snapshot tests local/GPU-gated. Go: vet, gofmt, test -race.

## 6. Regulatory
`dentalcraft-app/regulatory/` (requisiti.toml, rischi.toml, soup.toml, anomalie.toml, classificazione.md) carried over from old docs/regolatorio; refs `test:<repo>/<crate>::<path>`; `cargo xtask trace --check` replaces build_trace.py; SOUP generated from Cargo.lock/go.mod then curated.
