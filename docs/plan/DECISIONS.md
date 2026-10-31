# DentalCraft – decisions overriding/adding to PLAN.md (2026-10-31)
- Full rewrite in Rust (no PyO3 bridge). Project format `.dcprj`.
- Repos (all PRIVATE, org dnviti-personal-org): umbrella `dentalcraft` (no code, no versioning) + submodules `dentalcraft-core`, `dentalcraft-app`, `dentalcraft-aligners`, `dentalcraft-server` (Go).
- Local root: REDACTED-PATH ; submodules at ./dentalcraft-core etc.
- Versioning logic: each submodule own release-please (release-type rust / go), single package ".", include-component-in-tag false, tags vX.Y.Z, bump-minor-pre-major true, initial-version 0.1.0, trunk main; superproject pointer bumps manual `chore(submodule): ...`; superproject has `.github/workflows/submodules.yml` validating .gitmodules (copy from REDACTED-PATH).
- CI runs on a self-hosted runner (self-hosted ARC, DinD; toolchains must be installed by the job: dtolnay/rust-toolchain, actions/setup-go). No GPU/Vulkan on runners.
- Cross-repo private access in CI: read-only SSH deploy keys on each dependency repo (dentalcraft-core, dentalcraft-aligners), private keys stored as repo secrets in consumers; job uses webfactory/ssh-agent + `git config --global url."git@github.com:dnviti-personal-org/".insteadOf "https://github.com/dnviti-personal-org/"`; cargo `net.git-fetch-with-cli = true`.
REDACTED
- UI: English base + Italian translation (Fluent .ftl, runtime switch). Module display name "Aligners"/"Allineatori", internal id `aligners`.
- Toolchain: Rust 1.99.1 at ~/.cargo/bin -> always `export PATH="$HOME/.cargo/bin:$PATH"`. No cmake/g++ : no C++ crates (rustls+ring, not aws-lc). No -devel wayland/x11 pkgs: rely on winit dlopen.
- Old plugin (read-only reference/oracle): REDACTED-PATH
- Commits: conventional commits, end messages with `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`. Only commit your own paths (`git add <paths>`), never `git add -A` in shared repos.
- Hard stop 23:30 Europe/Rome; no risky/long ops after 23:00.
