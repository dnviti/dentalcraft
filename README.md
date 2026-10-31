# dentalcraft

**DentalCraft** is a desktop application for digital dentistry, written in Rust. Its first module, *Aligners*, plans orthodontic aligner treatments from intraoral scans: segmentation, setup, staging, attachments, trimming and export. The project replaces the earlier Blender add-on with a standalone application and a headless engine.

This repository holds no application code and is not versioned. It collects the project as **git submodules**, together with the plan, the decisions and the cross-cutting documentation.

## Repositories

| Folder | Repository | Language | Role |
| --- | --- | --- | --- |
| [`dentalcraft-core/`](dentalcraft-core) | `dnviti-personal-org/dentalcraft-core` | Rust | Engine: meshes, geometry, case model, `.dcprj` I/O, commands, jobs, module API, i18n, theme. Headless. |
| [`dentalcraft-aligners/`](dentalcraft-aligners) | `dnviti-personal-org/dentalcraft-aligners` | Rust | The *Aligners* module. Depends on core. |
| [`dentalcraft-app/`](dentalcraft-app) | `dnviti-personal-org/dentalcraft-app` | Rust | The shipped application (eframe shell, viewport, auth client, packaging). Depends on core and aligners. |
| [`dentalcraft-server/`](dentalcraft-server) | `dnviti-personal-org/dentalcraft-server` | Go | OpenID Connect identity provider, later licensing and support tickets. |

Other folders:

| Folder | Content |
| --- | --- |
| [`docs/plan/`](docs/plan) | Implementation plan (`PLAN.md`) and decisions that override it (`DECISIONS.md`). |
| [`docs/adr/`](docs/adr) | Architecture decision records. |
| [`.cargo/config.toml`](.cargo/config.toml) | Cargo settings for builds started from this folder, including local `[patch]` overrides. |

All repositories are private and live in the `dnviti-personal-org` organization.

## Clone

Submodule URLs are relative (`../<repo>.git`), so they resolve with the same protocol (HTTPS or SSH) and credentials used to clone this repository.

```sh
git clone --recurse-submodules https://github.com/dnviti-personal-org/dentalcraft.git
```

Already cloned without submodules:

```sh
git submodule update --init --recursive
```

## Bump the submodule pointers

Each submodule is pinned to a commit and tracks `main`.

```sh
# Move all submodules to the latest commit of main
git submodule update --remote --merge

# Record the new pointers in this repository
git add dentalcraft-core dentalcraft-aligners dentalcraft-app dentalcraft-server
git commit -m "chore(submodule): bump dentalcraft-core to v0.2.0"
```

Pointer bumps are manual and use the `chore(submodule): ...` prefix. Releases are cut inside each submodule by release-please (tags `vX.Y.Z`); this repository has no version.

## Local builds and `[patch]`

`dentalcraft-aligners` and `dentalcraft-app` depend on the other repositories through git dependencies (`https://github.com/dnviti-personal-org/dentalcraft-core.git`, by tag, or `branch = "main"` before core v0.1.0). In CI each repository builds against those pinned revisions.

For local work, the `[patch]` tables in [`.cargo/config.toml`](.cargo/config.toml) redirect those git dependencies to the working trees of the submodules, so changes in core are picked up by aligners and app without publishing anything. The config applies only to builds started from this folder, not inside a submodule checked out on its own. The tables are still a TODO until the crate names are final. Because `net.git-fetch-with-cli` is enabled, git dependencies are fetched with the git CLI and your SSH agent or credential helper.

Toolchain: Rust 1.99.1 (`rust-toolchain.toml` in each Rust repository), Go as declared in `dentalcraft-server/go.mod`.

## CI

Every repository runs GitHub Actions on a self-hosted runner. Private cross-repository access in CI uses read-only SSH deploy keys stored as secrets (`DEPLOY_KEY_CORE`, `DEPLOY_KEY_ALIGNERS`). This repository only validates `.gitmodules` (`.github/workflows/submodules.yml`).
