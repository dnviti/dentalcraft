# dentalcraft

**DentalCraft** is a desktop application for digital dentistry, written in Rust. Its first module, *Aligners*, plans clear-aligner treatments from intraoral scans: it finds and separates the teeth, builds 3D teeth, analyses the case, registers the bite, sets a final position, stages the movement, designs the aligners and prepares print-ready files. It also drives a 3D scanner and a turntable, so a project can start from a scan instead of an STL file. The project replaces an earlier Blender add-on with a standalone application and a headless engine.

> **Alpha. Not a medical device.** DentalCraft is not certified, has no regulatory clearance and has not been validated for clinical use. Do not use it on patients or for clinical decisions without independent professional validation. See [Disclaimer](#disclaimer).

This repository holds no application code and is not versioned. It gathers the project as **git submodules**, together with the plan, the decisions, the design files, the scanner enclosure design, the scripts for local CI and releases, and the sources of the science behind it ([`SOURCES.md`](SOURCES.md)).

- Website and downloads: <https://dentalcraft.app>
- This repository: <https://github.com/dnviti/dentalcraft>
- Documentation: <https://github.com/dnviti/dentalcraft-docs>

## Repositories

| Folder | Repository | Language | Role |
| --- | --- | --- | --- |
| [`dentalcraft-core/`](dentalcraft-core) | [`dnviti/dentalcraft-core`](https://github.com/dnviti/dentalcraft-core) | Rust | Engine: meshes, geometry, case model, `.dcprj` project files, commands, jobs, module API, scanner and turntable drivers, i18n, theme. Headless. |
| [`dentalcraft-aligners/`](dentalcraft-aligners) | [`dnviti/dentalcraft-aligners`](https://github.com/dnviti/dentalcraft-aligners) | Rust | The *Aligners* module: one file per pipeline stage. Depends on core. |
| [`dentalcraft-app/`](dentalcraft-app) | [`dnviti/dentalcraft-app`](https://github.com/dnviti/dentalcraft-app) | Rust | The application: shell, 3D viewport, scan popup, sign-in client, updater, diagnostics, `dentalcraft-cli` (command line and MCP server), packaging. Depends on core and aligners. |
| [`dentalcraft-web/`](dentalcraft-web) | [`dnviti/dentalcraft-web`](https://github.com/dnviti/dentalcraft-web) | Node | The website (English and Italian), the downloads, the Linux package repositories and the signed update feed. |
| `dentalcraft-server` | private | Go | The account and sign-in server. **Closed source, not part of this repository.** See [Sign-in server](#sign-in-server). |
| [`dentalcraft-docs`](https://github.com/dnviti/dentalcraft-docs) | [`dnviti/dentalcraft-docs`](https://github.com/dnviti/dentalcraft-docs) | Docs | Documentation (separate repository, not a submodule). |

Other folders:

| Folder | Content |
| --- | --- |
| [`docs/plan/`](docs/plan) | Implementation plan (`PLAN.md`), decisions that override it (`DECISIONS.md`), the port plan and gap map, and the handoff notes. |
| [`docs/adr/`](docs/adr) | Architecture decision records. |
| [`docs/design/`](docs/design) | Design files: `tokens.json`, `ui-spec.md`, screen exports, the FigCraft file. |
| [`docs/scanner/`](docs/scanner) | Notes on the Revopoint MINI 2 and on turntable scanning. |
| [`docs/screenshots/`](docs/screenshots) | Screenshots of the running application. |
| [`docs/kani.md`](docs/kani.md) | Formal-verification laws (Kani proof harnesses) and how to run them. |
| [`docs/local-ci.md`](docs/local-ci.md) | How CI and releases run locally. |
| [`hardware/scan-enclosure/`](hardware/scan-enclosure) | Parametric enclosure with LED lighting for the scanner and the turntable. |
| [`scripts/`](scripts) | Local CI, pull-request merge, release, third-party notices and Kani scripts. |
| [`SOURCES.md`](SOURCES.md) | Papers, books, datasets, standards, RFCs and specifications the project relies on. |

## Workflow

The *Aligners* module follows the clinical path in one workspace. The menu is grouped by function; clicking an item only shows its inspector, and every step has its own *Run* button.

| Step | What it does |
| --- | --- |
| Case | Start from STL, OBJ or PLY scans, or scan with a connected 3D scanner (alpha). Projects open without an account. |
| Preparation | Find the teeth, separate teeth and gum, build 3D teeth. |
| Diagnosis | Measure the case before planning. |
| Planning | Register the bite, set the final position, stage the movement. |
| Aligner production | Design the aligners and prepare print-ready files. |
| Follow-up and output | Compare plan and progress; files and reports. |

Everything the window does is also a registered command. `dentalcraft-cli` runs the commands headless and serves them over MCP, so an agent can drive the whole workflow.

## Install

Builds and installers are on the [download page](https://dentalcraft.app/download/). Every platform has an installer and a standalone build:

| Platform | Installer | Standalone |
| --- | --- | --- |
| Linux | Flatpak, Fedora (dnf), Debian and Ubuntu (apt), AppImage | `.tar.gz` |
| Windows | Setup `.exe` (per user), `.msi` (per machine) | `.zip` |

The installed application updates itself, and checks the signature of every update. There is no macOS download at the moment. The Windows files carry a self-signed signature, so SmartScreen may warn.

## Build

Rust 1.99.1 is pinned in each Rust repository (`rust-toolchain.toml`). No C++ toolchain is needed. On Linux you also need the usual GUI development libraries.

```sh
git clone --recurse-submodules https://github.com/dnviti/dentalcraft.git
cd dentalcraft
export PATH="$HOME/.cargo/bin:$PATH"

cd dentalcraft-app && cargo run -p dc-app --release     # the application
cd dentalcraft-app && cargo run -p dc-cli -- --help     # dentalcraft-cli

# per Rust repository
cargo fmt --check && cargo clippy --all-targets -- -D warnings && cargo test
```

Submodule URLs are relative (`../<repo>.git`), so they resolve next to this repository with the same protocol (HTTPS or SSH). Already cloned without submodules: `git submodule update --init --recursive`.

**Local builds and `[patch]`.** `dentalcraft-aligners` and `dentalcraft-app` depend on core and aligners through git dependencies pinned by tag. Builds started from this folder redirect those dependencies to the working trees of the submodules (see [`.cargo/config.toml`](.cargo/config.toml)), so a change in core is picked up by aligners and the app without a release. The redirect applies only to builds started here, not to a submodule cloned alone. Cargo then rewrites the `Cargo.lock` of the submodule with path sources: do not commit it; run `git checkout -- Cargo.lock` first.

**Formal verification.** Rules that must always hold are written as Kani proof harnesses. See [`docs/kani.md`](docs/kani.md).

## Sign-in server

The account and sign-in server, `dentalcraft-server`, is **closed source and private**. It is not a submodule of this repository, and it is not needed to build, run or test the open parts. Projects open and work without an account; sign-in is for licences and support.

To sign in, the application needs an **OpenID Connect issuer** with this behaviour (the client is `dc-auth-client` in `dentalcraft-app`):

| Need | Detail |
| --- | --- |
| Issuer URL | `https` (plain `http` only on a loopback host, for development). No query or fragment. Set it with `DC_AUTH_ISSUER`. A debug build defaults to `http://127.0.0.1:8787`, a release build to the production server. |
| Discovery | `GET {issuer}/.well-known/openid-configuration` with `issuer` (equal to the configured URL), `authorization_endpoint`, `token_endpoint`, `revocation_endpoint` and `jwks_uri`. Every endpoint must be on the issuer's origin. |
| Client | Public client `dentalcraft-desktop`, no secret. |
| Authorization | Authorization code flow with PKCE (`S256`). Redirect URI `http://127.0.0.1:<random port>/callback` (RFC 8252), with `state`, `nonce` and `ui_locales` (`en` or `it`). Scopes `openid profile email offline_access`. The redirect carries `iss` (RFC 9207). |
| Token endpoint | `authorization_code` and `refresh_token` grants. Refresh tokens may rotate; the app refreshes one request at a time. An `invalid_grant` answer ends the session. |
| Revocation | RFC 7009 endpoint, called at sign-out. |
| id_token | JWT signed with `EdDSA` (Ed25519). Keys in the JWKS as `OKP` / `Ed25519`. Claims `iss`, `aud` (the client id), `exp`, `sub` and `nonce` are checked. |
| User info | `GET {issuer}/api/v1/me` with the access token as a bearer token. JSON with `sub`, `email`, `name` and `entitlements.modules` (a list of module ids, for example `["aligners"]`). |
| Optional | `GET {issuer}/signup` (the "Create account" page), `POST {issuer}/api/v1/support/tickets` (support), and `POST {issuer}/api/v1/diagnostics/reports` (anonymous diagnostics, sent only after an explicit opt-in). |

The standards involved are listed in [`SOURCES.md`](SOURCES.md).

## Bump the submodule pointers

Each submodule is pinned to a commit and tracks `main`.

```sh
# Move all submodules to the latest commit of main
git submodule update --remote --merge

# Record the new pointers in this repository
git add dentalcraft-core dentalcraft-aligners dentalcraft-app dentalcraft-web
git commit -s -m "chore(submodule): dentalcraft-core a v0.3.0-alpha.8"
```

Pointer bumps are made by the maintainer and use the `chore(submodule): ...` prefix. Releases are cut inside each submodule by release-please (tags `vX.Y.Z`); this repository has no version.

## CI and releases

GitHub Actions are suspended for now. The workflows stay in place in every repository, and CI, pull-request merges and releases run locally with the scripts in [`scripts/`](scripts), which replay the workflows. See [`docs/local-ci.md`](docs/local-ci.md).

## Status

DentalCraft is in **alpha**: screens, commands and the project format can still change. Planning (setup, staging) and production are in development and not validated. The scanner connector is in alpha.

| Repository | Release | State |
| --- | --- | --- |
| `dentalcraft-core` | v0.3.0-alpha.8 | Engine, scanner and turntable drivers (Linux and Windows; macOS code is compile-checked only), resin print preparation for the Elegoo Saturn 4 Ultra 16K (alpha). |
| `dentalcraft-aligners` | v0.2.0-alpha.12 | *Aligners* module. Case, preparation and diagnosis work; planning and production are in development; print tracking of the aligners. |
| `dentalcraft-app` | v0.2.0-alpha.13 | Application with installers for Linux and Windows and automatic updates; Settings with a simple interface by default; print window for the aligners (alpha). |
| `dentalcraft-web` | no release | Website and downloads for 0.2.0-alpha.12. |

Other modules (model builder, splint, crown and bridge, implant) are planned. They have no dates.

## Licence

Source-available under the [PolyForm Noncommercial License 1.0.0](LICENSE.md). You may read, use, change and share the content of this repository for any noncommercial purpose. **Commercial use is not allowed.** This is not an open source licence in the OSI sense. The same licence applies to the code repositories above. The closed server is not covered.

**Commercial licensing.** To use DentalCraft commercially, contact the author, Daniele Viti: hello@dentalcraft.app.

Third-party components keep their own licences: see [`NOTICE.md`](NOTICE.md) and the `THIRD-PARTY-NOTICES.md` of the application.

## Disclaimer

DentalCraft is **not a certified medical device** under Regulation (EU) 2017/745 or any other regime. It has no regulatory clearance. Its results (plans, models, measures, files) are not clinically validated. It is provided as is, without warranty, as the licence says. A qualified professional must check every result before it is used on a person.

## Contributing

Read [`CONTRIBUTING.md`](CONTRIBUTING.md) (DCO sign-off, licence of contributions) and the [Code of Conduct](CODE_OF_CONDUCT.md). Report security problems privately, as described in [`SECURITY.md`](SECURITY.md). Never send patient data.
