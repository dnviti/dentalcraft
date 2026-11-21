# Local CI and releases (GitHub Actions disabled)

GitHub Actions are switched off on all six dentalcraft repositories (superproject, core, aligners, app, server, web) to save runner capacity. The workflow files under `.github/` stay as they are: they are suspended, not removed, and they remain the source of truth. The scripts in `scripts/` replay those workflows on this machine with the same commands, environment and versions, so a change behaves locally exactly as it would on the self-hosted runner. The server repository is closed and private; its steps are listed here only because the scripts drive it.

In this mode you push to GitHub by hand and merge pull requests with `gh pr merge --squash --admin`.

| Script | Replaces |
|---|---|
| `scripts/ci-local.sh` | `ci.yml` (core, aligners, app, server), `submodules.yml` (superproject) |
| `scripts/pr-merge-local.sh` | the pull-request checks, then the squash merge |
| `scripts/release-local.sh` | `release-please.yml` and the jobs it chains (`binaries.yml`, `image.yml`), plus the dentalcraft-web `image.yml` |
| `scripts/actions-status.sh` | shows the Actions switch of the six repositories, and turns it back on |

Everything temporary lives in `~/.cache/dentalcraft-ci` (override with `DC_CI_CACHE`). Nothing is written to the repositories, `~/.gitconfig`, `~/.ssh` or `~/.cargo`.

## Day-to-day flow

1. Commit on a branch in the submodule, then run `scripts/ci-local.sh <repo>`.
2. Push the branch and open the PR (`gh pr create`).
3. Run `scripts/pr-merge-local.sh <repo> <pr>`. It tests the merge of the PR head into `origin/main`, then squash-merges with `--admin --match-head-commit <tested sha>`.
4. Update local main to `origin/main`, then run `scripts/ci-local.sh <repo> --ref origin/main`. This is the run GitHub does on a push to main.
5. Run `scripts/release-local.sh <repo>`. Use `--dry-run` first to see what release-please would do.
   - It opens or updates the release PR.
   - Merging that PR with step 3 (no CI, as on GitHub), then repeating steps 4 and 5, creates the tag and the GitHub release, and runs the chained jobs.
6. For the superproject gitlink bumps (`chore(submodule): ...`), use `scripts/ci-local.sh super` and `scripts/pr-merge-local.sh super <pr>`.

## `scripts/ci-local.sh`

```sh
scripts/ci-local.sh <core|aligners|app|server|super|all> [--ref <git-ref>] [--pr]
scripts/ci-local.sh clean
```

**What it tests:**
- It tests a committed ref, like `actions/checkout`. The default is `HEAD` of the repository.
  - It refuses a dirty tree; pass `--ref` to test a committed ref anyway.
  - For `super`, changes in the submodule checkouts are not counted as dirt.
  - A ref starting with `origin/` fetches `origin` first.
- `--pr` tests the merge of the ref into the freshly fetched `origin/main`, as GitHub tests `refs/pull/N/merge`. A conflict fails the run.
- `all` runs `super`, `core`, `aligners`, `app` and `server` in that order. It stops at the first failure and prints a table of results and durations.

**Where it builds:**
- The commit is checked out into `~/.cache/dentalcraft-ci/<repo>/src`, outside the superproject.
  - The superproject's `.cargo/config.toml` `[patch]` does not apply there, so core and aligners resolve to the git tags pinned in `Cargo.toml`, exactly as on the runner.
  - The script refuses to run if any `.cargo/config(.toml)` exists in an ancestor directory or in its `CARGO_HOME`. As of 2026-11-07 there is none (`~/.cargo/config.toml` does not exist).
- `CARGO_HOME` is `~/.cache/dentalcraft-ci/cargo-home`.
- `src/target` persists between runs and stands in for `Swatinem/rust-cache`.

**Environment, as on a fresh runner pod:**
- Variables of the calling shell that change the build are dropped: `CARGO_*`, `RUST*` (except `RUSTUP_HOME`), `GIT_CONFIG*`, `GO*`, `CGO_*`.
- `CARGO_INCREMENTAL=0` and `CARGO_TERM_COLOR=always` are set, as `dtolnay/rust-toolchain` sets them.
- Aligners and app also get the job env `CARGO_NET_GIT_FETCH_WITH_CLI=true`.
- The step "Use SSH for private dentalcraft repositories" is replayed with process-scoped variables:
  - `GIT_CONFIG_COUNT/KEY_0/VALUE_0` carry the `https://github.com/dnviti-personal-org/` to `git@github.com:dnviti-personal-org/` `insteadOf` mapping, as the workflows still write it. The public repositories under `github.com/dnviti` do not match it and are fetched over plain HTTPS.
  - `GIT_SSH_COMMAND` uses a known_hosts file that holds only GitHub's pinned ed25519 key.
  - Your SSH agent stands in for the deploy keys.

**Steps** (each printed with its script and timing, like the runner log):

| Repo | Steps |
|---|---|
| core, app | `cargo fmt --all --check`; `cargo clippy --workspace --all-targets -- -D warnings`; `cargo test --workspace` |
| aligners | the same, but tests are `cargo test --workspace --release` with `CARGO_PROFILE_RELEASE_DEBUG_ASSERTIONS=true` and `CARGO_PROFILE_RELEASE_OVERFLOW_CHECKS=true` |
| server | `test -z "$(gofmt -l .)"`; `go vet ./...`; `CGO_ENABLED=1 go test -race -count=1 ./...` |
| super | the two checks of `submodules.yml`, verbatim |

**Toolchains:**
- Rust is 1.99.1 (the `ci.yml` pin, and `rust-toolchain.toml` in each repo). The script installs it with rustup only if it is missing.
- Go is the exact version from `go.mod`, as `actions/setup-go` with `go-version-file` uses it: the `toolchain` directive, otherwise `go`.
  - It runs through `GOTOOLCHAIN=go<version>`; the go command downloads that toolchain into `~/.cache/dentalcraft-ci/go`.
  - The toolchain's `bin/` goes first on `PATH`, so `gofmt` matches as well.
  - Fedora's packaged go (1.27 with `GOTOOLCHAIN=local` and `GOEXPERIMENT=nodwarf5` in its `go.env`) is not used for the build.
- The C toolchain must already be installed (`gcc`). The runner installs it with the package manager; the script does not.

**Pass marker:**
- A passing run without `--pr` writes `~/.cache/dentalcraft-ci/<repo>/passed/<sha>`.
- `release-local.sh` requires this marker for `origin/main`.

`clean` removes `~/.cache/dentalcraft-ci` entirely: checkouts, targets, toolchains, markers and the npm cache.

## `scripts/pr-merge-local.sh`

```sh
scripts/pr-merge-local.sh <core|aligners|app|server|super|web> <pr-number> [--dry-run]
```

**Checks before testing:**
- The PR must be open and target `main`.
- The script fetches `pull/<n>/head` and checks that it matches the PR head reported by GitHub.

**When it skips CI** (GitHub never runs checks on these either):
- Release-please PRs: author `github-actions[bot]`, or head branch `release-please--*`. The PRs that `release-local.sh` opens come from your account, but they keep the `release-please--*` branch.
- dentalcraft-web, which has no `pull_request` workflow.

**What it runs otherwise:**
1. `scripts/ci-local.sh <repo> --pr --ref <head sha>`.
2. `gh pr merge <n> --squash --admin --match-head-commit <head sha>`.

The merge fails if the PR moved after the test.

**Branch protection:** all repositories are public, except `dentalcraft-server`, which stays private. While the repositories were private on the free plan, `branches/main/protection`, `rulesets` and `rules/branches/main` all answered 403 ("Upgrade to GitHub Pro"), so no required status checks existed for `--admin` to bypass. On public repositories protection can exist; `--admin` is kept so the command works either way. The script prints the protection state before merging.

## `scripts/release-local.sh`

```sh
scripts/release-local.sh <core|aligners|app|server> [--dry-run] [--require-authenticode]   # the flag: app only
scripts/release-local.sh binaries <app|server> <tag> [--no-upload] [--out DIR] [--only linux_x86_64|windows_x86_64|installers] [--src DIR] [--no-sign] [--require-authenticode]
scripts/release-local.sh image server <tag> [--no-push]
scripts/release-local.sh web-image [--ref <main|vX.Y.Z>] [--no-push]
```

### Release (`release-please.yml`)

**Version:**
- `googleapis/release-please-action@v5` currently resolves to tag `v5.0.0`, commit `45996ed1f6d02564a971a2fa1b5860e934307cf7`.
- Its `package-lock.json` locks `release-please` to `17.6.0`, so the script runs the CLI at that exact version: `npx --yes release-please@17.6.0`, with the npm cache under `~/.cache/dentalcraft-ci/npm`.
- To re-check after the action moves:

  ```sh
  gh api 'repos/googleapis/release-please-action/contents/package-lock.json?ref=v5' --jq .content | base64 -d | jq '.packages["node_modules/release-please"].version'
  ```

**Before it runs:**
- Local `main` must equal the freshly fetched `origin/main`.
- `ci-local` must have passed on that commit (the pass marker).
- With `--dry-run`, a missing marker is only a warning.

**What it runs:** the same two calls as the action, in the same order, against the default branch:

```sh
release-please github-release --repo-url dnviti/<repo> --config-file release-please-config.json --manifest-file .release-please-manifest.json --token "$(gh auth token)"
release-please release-pr     (same flags)
```

The config and the manifest are read from `main` on GitHub, as the action reads them.

**Repository owners:** since 2026-11-21 the public repositories (superproject, core, aligners, app, web) live under `github.com/dnviti`; the closed `dentalcraft-server` and its ghcr image stay in the `dnviti-personal-org` organisation. The scripts keep the two apart: `ORG` (private organisation, in `ci-local.sh`) and `OWNER` (public account, in `release-local.sh`, `pr-merge-local.sh` and `actions-status.sh`). `--repo-url` is `dnviti/<repo>`, except `dnviti-personal-org/dentalcraft-server`.

**Chained jobs:**
- `release_created`/`tag_name` are derived by comparing the release tags before and after `github-release`.
- When a release was created, the chained jobs run as in the workflow:
  - app: `binaries`
  - server: `image`, then `binaries`
  - core and aligners: none

**Before an app release:** regenerate the third-party notices when the app dependencies changed, and commit the result in `dentalcraft-app` (it is embedded in the binary and shown in the "Licence and notices" dialog):

```sh
scripts/third-party-notices.py dentalcraft-app -o dentalcraft-app/THIRD-PARTY-NOTICES.md
```

### `binaries app` (`dentalcraft-app/.github/workflows/binaries.yml`)

**Source:** the tag is checked out from GitHub, not from the submodule. Each job has its own checkout (`~/.cache/dentalcraft-ci/app-binaries/<job>/src`) and the build entries their own `target/`.

**Build entries** (job `build`): each runs in a throwaway container (`podman run --rm`, as root so that the files in the checkout stay yours), with your SSH agent socket mounted. rustup and the cargo registry are kept in `~/.cache/dentalcraft-ci/app-binaries/<entry>/{rustup,cargo-home}`, so a rerun does not download them again.
- `linux_x86_64` runs in the runner image itself, `ghcr.io/actions/actions-runner@sha256:759a1d94…` (pinned by digest, as on the self-hosted runner; Ubuntu 24.04, glibc 2.39), with the workflow's "Install C toolchain" step (apt). The binaries need glibc 2.39 at most, as on GitHub.
  - Until 2026-11-15 this entry built on the Fedora 45 host. Those binaries needed glibc 2.44, so they ran only on the newest distributions, and not in the Flatpak runtime or on Debian 13.
  - A `target/` from such an earlier build is wiped once (marker `target/.dc-ci-image`).
- `windows_x86_64` runs in `registry.fedoraproject.org/fedora:45`. It installs the workflow's dnf packages (`gcc make pkgconf-pkg-config mingw64-gcc zip`) plus `git-core openssh-clients`, rustup with 1.99.1 and `x86_64-pc-windows-gnu`, and writes the `insteadOf` and known_hosts setup to its own global git config and `~/.ssh`.

**Build and package steps:** the workflow's Build and Package steps are passed through verbatim. They keep:
- the same `RUSTFLAGS` remaps;
- `cargo build -p dc-app -p dc-cli --release --target <triple>` without `--locked`;
- the archive names `dentalcraft_<version>_<name>`, with one top folder;
- `README.md`, `LICENSE.md`, `THIRD-PARTY-NOTICES.md`, the `LICENSES/` font licences and `install-kind` (`standalone`) next to the binaries.

**Installers** (job `installers`): `packaging/installers.sh` of the tag builds the AppImage, deb, rpm, Flatpak bundle, setup.exe and MSI from the two archives (formats, tools and layout: `dentalcraft-app/packaging/README.md`).
- It runs in a throwaway `registry.fedoraproject.org/fedora:45` container with `--privileged`: flatpak-builder sandboxes its build with bubblewrap. The workflow uses `docker run` with the same image, flags and environment.
- Unlike on the runner, the tool downloads and the Flatpak runtime and SDK (about 4 GB on disk) persist in `~/.cache/dentalcraft-ci/app-binaries/installers/cache`; `scripts/ci-local.sh clean` removes them with the rest.
- The rpm and the Flatpak commit are signed with the release GPG key. The script exports the key from `~/.config/dentalcraft-release/gpg` (fingerprint `83B0A31C…9DE538`; `DENTALCRAFT_RELEASE_KEYS` overrides the directory) into a 0600 file under the cache. It mounts that file read-only into the container and deletes it afterwards. On the runner the key comes from the `DENTALCRAFT_GPG_KEY` secret.
- First it checks that `packaging/linux/dentalcraft.list` and `dentalcraft.repo` (installed by the deb and the rpm) are byte-identical to `dentalcraft-web/linux/`.

**Authenticode (Windows):** `packaging/windows/authenticode.sh` of the tag signs the Windows files with the DentalCraft **self-signed** code-signing certificate.
- **What it gives:** Windows does not trust a self-signed certificate. SmartScreen still warns ("Windows protected your PC"), and the publisher shows as unknown. The signature only proves which key signed the files: users can check the certificate's SHA-256 fingerprint, printed in the release notes. A PC that installs the certificate as trusted accepts the signature (see "Trusting the self-signed certificate on a Windows PC" in `dentalcraft-app/packaging/README.md`). The SSL.com eSigner version (an OV/IV certificate that Windows trusts) is parked: see `docs/plan/HANDOFF.md`.
- **The certificate:** `CN=DentalCraft (self-signed), O=VITI DANIELE, C=IT`, RSA 3072, SHA-256, KU digitalSignature, EKU codeSigning, CA:FALSE, valid 2026-11-18 to 2031-11-18.
  - SHA-256 fingerprint `24DD542E337BCEA99C793D57DE53B6D355DC015BF1270D20D1321D56DCF0AA26`.
  - The public certificate is pinned in `dentalcraft-app/packaging/windows/dentalcraft-selfsigned.crt.pem`. Replacing the key means replacing that file in the same change.
- **Tools:**
  - jsign 7.6 (`--storetype PKCS12`), the jar pinned by URL (Maven Central) and sha256;
  - an RFC 3161 timestamp from `http://ts.ssl.com`;
  - `osslsigncode verify` for the check.
  - The script installs Java and osslsigncode with dnf or apt-get, only when there is a key.
- **Order:** every signature comes before `update.json`, `update.json.minisig` and the checksums, which hash the signed files.
  1. Job `build`, entry `windows_x86_64`, step "Sign the Windows programs": `dentalcraft.exe` and `dentalcraft-cli.exe` in `target/`, after Build and before Package. The zip, setup.exe and MSI therefore all hold signed programs.
  2. Job `installers`, step "Sign the Windows installers": `DentalCraft-<V>-setup.exe` and `DentalCraft-<V>-x86_64.msi`, in another throwaway `fedora:45` container after `installers.sh`.
  - `--replace` keeps a single signature when a rerun finds a `target/` program that is already signed.
- **Verification:** after signing, every file must pass `osslsigncode verify` with:
  - `Signature verification: ok`;
  - `Timestamp Server Signature verification: ok`;
  - exactly one signature.
  - The signature must chain to the pinned self-signed certificate (`AUTHENTICODE_CAFILE` overrides it, for tests with another key). The timestamp must chain to `packaging/windows/timestamp-root.pem`: SSL.com Root Certification Authority RSA (`85666A562EE0BE5CE925C1D8890A6F76A87EC16D4D7D5F29EA7419CF20123B69`), the root of the ts.ssl.com timestamps, from the [SSL.com repository](https://www.ssl.com/repository/) and also in Fedora's `objsign-ca-bundle.pem`. Windows trusts that root, so the timestamp is valid on Windows too.
  - osslsigncode alone exits 0 even when the timestamp fails, which is why the script checks those lines.
  - To check a downloaded file by hand:

    ```sh
    osslsigncode verify -in DentalCraft-<V>-setup.exe \
      -CAfile dentalcraft-app/packaging/windows/dentalcraft-selfsigned.crt.pem \
      -TSA-CAfile dentalcraft-app/packaging/windows/timestamp-root.pem
    ```

    On Windows: file Properties, Digital Signatures, or `Get-AuthenticodeSignature` (the signature shows as not trusted unless the certificate is installed).
- **The key:** `~/.config/dentalcraft-release/authenticode/` (`DENTALCRAFT_RELEASE_KEYS` overrides the parent directory), mode 0700:
  - `dentalcraft-selfsigned.p12` (0600): PKCS#12 with the key and the certificate, alias `dentalcraft`;
  - `storepass` (0600): its password, without a trailing newline;
  - `dentalcraft-selfsigned.crt.pem` and `dentalcraft-selfsigned.cer` (0644): the public certificate, PEM and DER (the `.cer` is the file to install on Windows PCs).
  - The script mounts the directory read-only into the signing containers as `AUTHENTICODE_KEY_DIR`. jsign reads the password with `--storepass file:`, so it is never on a command line or in the log.
  - A directory that is present but lacks the `.p12` or `storepass` fails the run.
  - On the runner the same key comes from the optional secrets `DENTALCRAFT_AUTHENTICODE_P12` (the `.p12`, base64) and `DENTALCRAFT_AUTHENTICODE_PASSWORD`. Each step writes them as 0600 files into a 0700 directory under `$RUNNER_TEMP` and deletes it afterwards.
- **Without a key** (no directory, or no secrets on the runner), each step prints `##[warning]no Authenticode key …` and the files stay unsigned: the behaviour before Authenticode. `--require-authenticode` turns this into a failure:
  - `release-local.sh app --require-authenticode` checks before release-please runs;
  - `binaries app … --require-authenticode` checks before building, and `authenticode.sh` checks again with `AUTHENTICODE_REQUIRED=1`.
- **Release notes:** when `setup.exe` carries a signature (a non-empty PE certificate table), the `<!-- binaries-note -->` step says that the Windows files carry a self-signed signature that Windows does not trust, so SmartScreen still warns, and prints the certificate's SHA-256 fingerprint (computed from the pinned `.crt.pem`). Otherwise it keeps the "not code-signed" line.
- **Testing:** run `bash packaging/windows/authenticode.sh FILE...` in a `fedora:45` container with the key directory mounted read-only and `AUTHENTICODE_KEY_DIR` set, as `release-local.sh` does.

**Attach to release** (job `release`, on its own checkout of the tag):
- `packaging/update-manifest.py` writes and signs `update.json` and `update.json.minisig`, with the minisign key `~/.config/dentalcraft-release/minisign.key` standing in for the `DENTALCRAFT_MINISIGN_KEY` secret.
- It requires the 8 assets (2 archives, 6 installers) plus the manifest, and nothing else. Then it writes `dentalcraft_<version>_SHA256SUMS.txt`.
- It runs `gh release upload --clobber`.
- It runs the same `<!-- binaries-note -->` release-notes step.

**Images:** the runner image and the Fedora image are removed at the end if the run pulled them. The rootless pause process (`catatonit`) is stopped only if it was not running before and no container is left.

**Flags:**
- `--only linux_x86_64|windows_x86_64` builds one entry and stops after packaging.
- `--only installers` reruns the installers job on the two archives of the last run of the same tag.
- `--no-upload` stops before the upload. The assets stay in `~/.cache/dentalcraft-ci/app-binaries/dist`.
- `--out DIR` copies the assets to DIR.
- `--require-authenticode` fails instead of leaving the Windows files unsigned when `~/.config/dentalcraft-release/authenticode` is missing (see Authenticode above).
- Local tests only, both need `--no-upload`:
  - `--src DIR` builds a local working tree instead of the tag: its HEAD commit plus the uncommitted changes, untracked files included, ignored ones not. It is built outside the superproject, so core and aligners are the pinned tags. Example: `scripts/release-local.sh binaries app v0.2.0-alpha.90 --no-upload --src dentalcraft-app`.
  - `--no-sign` builds without the release keys: the rpm and the Flatpak bundle are unsigned, there is no `update.json`, and there is no Authenticode signature (the key directory is not mounted, so the Windows files stay unsigned with the warning). Test builds then fetch no timestamps. `--no-sign` and `--require-authenticode` exclude each other.

### `binaries server` (`dentalcraft-server/.github/workflows/binaries.yml`)

- It checks the tag, uses the `go.mod` toolchain, and runs the verbatim build loop:
  - 5 targets: `linux/amd64 linux/arm64 darwin/amd64 darwin/arm64 windows/amd64`;
  - `-trimpath -ldflags "-s -w -X main.version=<version>"`;
  - root-owned tarballs, a zip for Windows, and `SHA256SUMS`.
- The upload is the workflow's `curl` script: it replaces assets of the same name. The token comes from `gh auth token`.
- If `zip` is missing, the run fails instead of installing it.

### `image server` and `web-image`

`podman build --format docker --pull=always --layers=false` builds the image with the workflow's tags, build args and OCI labels. The `docker` format keeps the Dockerfile `HEALTHCHECK`; the OCI format would drop it, while buildx keeps it.

| Image | Tags | Build arg | Labels |
|---|---|---|---|
| `ghcr.io/dnviti-personal-org/dentalcraft-server` | `:<version>`, `:latest` | `VERSION` | `source`, `version`, `revision` (= tag commit) |
| `ghcr.io/dnviti-personal-org/dentalcraft-web` | `:latest`, `:sha-<7>`, plus `:<version>` for a `v*` ref | none; build secret `gpg` | `version` = version or commit sha |

The web image stays at `ghcr.io/dnviti-personal-org/dentalcraft-web`, which the deployed site pulls. The web `image.yml` derives the owner from the repository, so after the move to `dnviti` it would push `ghcr.io/dnviti/dentalcraft-web`: move the deployment before re-enabling that workflow.

**Login and push:**
- The script logs in to ghcr.io with `gh auth token`, through a temporary `--authfile` that it deletes afterwards.
- Pushing needs the `write:packages` scope. The script checks for it and otherwise tells you to run `gh auth refresh -h github.com -s write:packages`.
- `--no-push` builds, prints the labels, and stops.

**Cleanup:** afterwards the built tags are removed, and so are base images that were not present before the run.

`web-image` first downloads every file of the app release pinned in `content/site.data.json` with `gh release download` (the workflow does the same). Your gh token stands in for the `APP_RELEASE_TOKEN` secret.

The image build then signs the Linux repositories (APT metadata, RPM `repomd.xml`, Flatpak OSTree commit and summary) with the build secret `gpg`, the armored secret key of DentalCraft Releases. On the runner it is the web repo secret `DENTALCRAFT_GPG_KEY`. Locally the script uses `$DENTALCRAFT_GPG_KEY` when set, otherwise it exports the key from `~/.config/dentalcraft-release/gpg` (override the directory with `DENTALCRAFT_RELEASE_KEYS`) into a 0600 file under the cache, passes it as `--secret id=gpg,src=...`, and deletes it after the build. Keys, repository layout and the update manifest: `dentalcraft-web/README.md`.

Run it after pushing dentalcraft-web `main` or a `v*` tag:
- `--ref main` (the default) gives the push-to-main run.
- `--ref vX.Y.Z` gives the tag run.

## `scripts/actions-status.sh`

```sh
scripts/actions-status.sh status            # read-only
scripts/actions-status.sh on  [--dry-run]   # restore the recorded original state
scripts/actions-status.sh off [--dry-run]   # cancel queued runs, then switch Actions off
```

**How Actions were switched off:**
- The switch is at repository level (`gh api repos/<owner>/<repo>/actions/permissions`, `enabled=false`).
- All workflows are still `active`.

**What the scripts change:**
- `on` and `off` only change that switch. They use `PUT .../actions/permissions -F enabled=<bool>`.
- They do not send `allowed_actions`, so GitHub keeps the previous policy.
- The original state is in `scripts/actions-state.tsv`: every repository had Actions enabled, with last runs between 2026-10-31 and 2026-11-02.

**After `on`:** check that `release-please.yml` does not run on the next push to `main` while a local release is half-done.

## Differences from the runner that cannot be avoided

- **Token identity:**
  - Locally, release-please, the release and the release PR act as your user, not as `github-actions[bot]`.
  - While Actions are off, nothing is triggered by that.
  - Once Actions are back on, tags and PRs created with a user token would trigger workflows. `GITHUB_TOKEN` events never trigger them.
- **Deploy keys:** your SSH agent replaces the read-only deploy keys `DEPLOY_KEY_CORE`/`DEPLOY_KEY_ALIGNERS`. It can read at least as much, so builds are the same.
- **C toolchain:** the runner installs `gcc` (and `zip`) when missing. The scripts require them and never install packages on the host.
- **Container image manifest:** `docker/build-push-action@v7` (buildx) adds a provenance attestation by default, so the image it pushes is an OCI index with an attestation manifest. Podman pushes a single Docker v2 manifest, without the attestation. Tags, labels, build args, `HEALTHCHECK` and the Dockerfile stages are the same; layer digests can differ, because the builder and the base-image pull time differ.
- **Cache:** `rust-cache` restores `~/.cargo/registry`, `~/.cargo/git` and `target/` keyed by the lockfile; locally they simply persist. Run `scripts/ci-local.sh clean` to start from nothing, like a cache miss.
- **Concurrency groups:** concurrency groups are replaced by a `flock` per tag or ref, so runs queue rather than run at the same time.
- **Windows build and installers environment:** the Windows build and the installers job run in a Fedora 45 container, not on the runner image (the installers job uses that same container on the runner too). The toolchain is mingw-w64 GCC either way, and the target triple, flags and packaging are the same.
- **Tag-push runs:** `ci.yml` also triggers on `v*` tags, but tags created by `GITHUB_TOKEN` never trigger it on GitHub. There is nothing to replay.
