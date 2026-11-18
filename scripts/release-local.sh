#!/usr/bin/env bash
# Local replica of release-please.yml and of the jobs it chains, used while
# GitHub Actions are disabled (docs/local-ci.md). The workflow files under
# .github/ stay the source of truth: keep this script in step with them.
#
#   scripts/release-local.sh <core|aligners|app|server> [--dry-run] [--require-authenticode (app)]
#       release-please.yml: `github-release`, then `release-pr`, with the
#       release-please version bundled in googleapis/release-please-action@v5.
#       When a release is created, the chained jobs follow: app -> binaries,
#       server -> image + binaries. Requires local main == origin/main and a
#       passing `scripts/ci-local.sh <repo> --ref origin/main` on that commit.
#   scripts/release-local.sh binaries <app|server> <tag> [--no-upload] [--out DIR] [--only NAME]
#                                     [--src DIR] [--no-sign] [--require-authenticode]
#       binaries.yml alone (workflow_dispatch). --no-upload builds and packages
#       only; --out copies the release assets to DIR; --only (app: linux_x86_64,
#       windows_x86_64 or installers) runs one job and stops there (installers
#       reuses the two archives of the last run). app only, local tests (need
#       --no-upload): --src DIR builds a working tree (its HEAD plus uncommitted
#       changes) instead of the tag; --no-sign builds without the release keys
#       (no GPG, minisign or Authenticode signature). The Windows programs and
#       installers are Authenticode-signed with the self-signed key in
#       ~/.config/dentalcraft-release/authenticode; without that directory they
#       stay unsigned with a warning, unless --require-authenticode (app only),
#       which fails instead.
#   scripts/release-local.sh image server <tag> [--no-push]
#       dentalcraft-server image.yml alone (workflow_dispatch).
#   scripts/release-local.sh web-image [--ref <main|vX.Y.Z>] [--no-push]
#       dentalcraft-web image.yml, as after a push of main (default) or of a v* tag.
#
# Writes to GitHub (releases, PRs, assets, ghcr images) unless --dry-run,
# --no-upload or --no-push. Uses the token of `gh auth token`.
# The job steps are scripts in single quotes, expanded by the step shell
# (SC2016); the jobs run in subshells on purpose (SC2030, SC2031).
# shellcheck disable=SC2016,SC2030,SC2031
set -euo pipefail

# shellcheck source=scripts/ci-local.sh
. "$(dirname "${BASH_SOURCE[0]}")/ci-local.sh"

# googleapis/release-please-action@v5 (tag v5 -> v5.0.0, commit
# 45996ed1f6d02564a971a2fa1b5860e934307cf7) bundles release-please 17.6.0:
# package.json "release-please": "^17.6.0", package-lock.json
# node_modules/release-please "version": "17.6.0". Re-check when v5 moves:
#   gh api 'repos/googleapis/release-please-action/contents/package-lock.json?ref=v5' --jq .content | base64 -d | jq '.packages["node_modules/release-please"].version'
RELEASE_PLEASE_VERSION=17.6.0
# binaries.yml of dentalcraft-app. linux_x86_64 runs in the self-hosted runner image,
# pinned by digest as in the self-hosted runner (ghcr.io/actions/actions-runner,
# Ubuntu 24.04, glibc 2.39): binaries built on the host would need its newer glibc.
LINUX_IMAGE=ghcr.io/actions/actions-runner@sha256:759a1d94a15b05941aba5196974ff43fe15b4cbba29b694b35cbc32a1166b232
# Windows is cross-compiled with mingw-w64 in a throwaway container of this image.
WIN_IMAGE=registry.fedoraproject.org/fedora:45
# The installers job runs packaging/installers.sh in a throwaway container of this image.
PKG_IMAGE=registry.fedoraproject.org/fedora:45
# Release signing keys (dentalcraft-web README, Keys): GPG for the Linux repositories,
# minisign for the update manifest. They stand in for the DENTALCRAFT_* secrets.
RELEASE_KEYS=${DENTALCRAFT_RELEASE_KEYS:-$HOME/.config/dentalcraft-release}
RELEASE_GPG_FPR=83B0A31CA19DE14A1648A875C10CE2EB009DE538
# The self-signed Authenticode key of the Windows programs and installers (directory with
# dentalcraft-selfsigned.p12 and storepass, format in packaging/windows/authenticode.sh),
# standing in for the DENTALCRAFT_AUTHENTICODE_* secrets.
AUTHENTICODE_KEYS=$RELEASE_KEYS/authenticode
# --require-authenticode: fail instead of leaving the Windows files unsigned.
APP_REQUIRE_AUTHENTICODE=0

usage() { sed -n '2,31p' "${BASH_SOURCE[0]}" | sed 's/^# \{0,1\}//' >&2; exit 2; }

gh_repo() { printf '%s/dentalcraft-%s\n' "$ORG" "$1"; }

# Only one run per tag at a time (the workflows' concurrency groups, not cancelled).
lock() {
  mkdir -p "$CACHE/locks"
  exec 9>"$CACHE/locks/$1"
  flock 9
}

# actions/checkout of a ref of the GitHub repository (not of the local
# submodule): the release tag exists on GitHub. Sets SRC.
checkout_remote() {
  local repo=$1 ref=$2 dir=$3 sha
  SRC=$CACHE/$dir/src
  mkdir -p "$SRC"
  [ -d "$SRC/.git" ] || git init -q "$SRC"
  (
    ssh_env >/dev/null
    git -C "$SRC" fetch -q --force --no-tags "https://github.com/$(gh_repo "$repo").git" "$ref"
  )
  git -C "$SRC" checkout -q --force --detach FETCH_HEAD
  git -C "$SRC" clean -ffdxq -e /target
  sha=$(git -C "$SRC" rev-parse HEAD)
  printf '##[group]Checkout\n  repository: %s\n  ref:        %s\n  commit:     %s\n  path:       %s\n##[endgroup]\n' \
    "$(gh_repo "$repo")" "$ref" "$sha" "$SRC"
}

# ---------------------------------------------------------------- podman

PODMAN_PAUSE_BEFORE=
podman_note_state() {
  if pgrep -u "$(id -u)" -x catatonit >/dev/null; then PODMAN_PAUSE_BEFORE=1; else PODMAN_PAUSE_BEFORE=0; fi
}
# Stop the rootless pause process only if this script started it.
podman_stop_pause() {
  [ "$PODMAN_PAUSE_BEFORE" = 0 ] || return 0
  [ -z "$(podman ps -aq)" ] || return 0
  pkill -u "$(id -u)" -x catatonit || true
}
# Remove an image only if it was not there before.
image_existed() { podman image exists "$1"; }

# ---------------------------------------------------------------- release-please

release_tags() { gh api --paginate "repos/$1/releases?per_page=100" --jq '.[].tag_name' | sort; }

cmd_release() {
  local repo=$1 dry=$2 dir name local_main remote_main before after created flags=()
  dir=$(repo_dir "$repo")
  name=$(gh_repo "$repo")
  [ "$dry" = 1 ] && flags=(--dry-run)
  printf '\n========== release-please %s%s ==========\n' "$name" "${flags[*]:+ (dry run)}"
  git -C "$dir" fetch -q origin main
  local_main=$(git -C "$dir" rev-parse --verify -q refs/heads/main) || die "$dir has no local main branch"
  remote_main=$(git -C "$dir" rev-parse --verify origin/main)
  [ "$local_main" = "$remote_main" ] \
    || die "local main ($local_main) differs from origin/main ($remote_main) in $dir: release-please releases what is on GitHub, align them first"
  if [ ! -f "$CACHE/$repo/passed/$remote_main" ]; then
    local msg="no passing ci-local run on origin/main $remote_main: run scripts/ci-local.sh $repo --ref origin/main first"
    [ "$dry" = 1 ] || die "$msg"
    printf '##[warning]%s (dry run: continuing)\n' "$msg"
  else
    printf 'ci-local: %s\n' "$(cat "$CACHE/$repo/passed/$remote_main")"
  fi
  # The server's image job pushes to ghcr: check the scope before releasing anything.
  [ "$repo" = server ] && [ "$dry" = 0 ] && need_packages_scope
  local token
  token=$(gh auth token)
  before=$(release_tags "$name")
  # release-please-action@v5: releases first, then the release PR, target branch
  # the default branch, config and manifest read from that branch on GitHub.
  (
    export RP_TOKEN=$token npm_config_cache=$CACHE/npm npm_config_update_notifier=false
    for c in github-release release-pr; do
      run_step "release-please $c" "npx --yes release-please@$RELEASE_PLEASE_VERSION $c --repo-url $name --config-file release-please-config.json --manifest-file .release-please-manifest.json --token \"\$RP_TOKEN\"${flags[*]:+ ${flags[*]}}"
    done
  )
  if [ "$dry" = 1 ]; then
    echo "dry run: nothing written; the chained jobs run only after a real release"
    return 0
  fi
  after=$(release_tags "$name")
  created=$(comm -13 <(printf '%s\n' "$before") <(printf '%s\n' "$after") | grep . || true)
  if [ -z "$created" ]; then
    echo "release_created=false: no chained jobs"
    return 0
  fi
  [ "$(printf '%s\n' "$created" | wc -l)" -eq 1 ] || die "more than one new release: $created"
  echo "release_created=true tag_name=$created"
  case "$repo" in
    app) cmd_binaries_app "$created" 0 "" "" 0 ;;
    server)
      # Two independent jobs on GitHub: one failing does not stop the other.
      # Plain statements, not `||` lists, so that errexit stays on inside each job.
      local rc_image rc_binaries
      set +e
      ( set -e; cmd_image_server "$created" 0 )
      rc_image=$?
      ( set -e; cmd_binaries_server "$created" 0 "" )
      rc_binaries=$?
      set -e
      [ "$rc_image" = 0 ] && [ "$rc_binaries" = 0 ] \
        || die "a chained job failed for $created (image: $rc_image, binaries: $rc_binaries): rerun it with scripts/release-local.sh image server $created / binaries server $created"
      ;;
  esac
}

# ---------------------------------------------------------------- app binaries

APP_TAG_CHECK='case "$TAG" in
  v[0-9]*.[0-9]*.[0-9]*) ;;
  *) echo "tag must look like vX.Y.Z, got '"'"'$TAG'"'"'" >&2; exit 1 ;;
esac'

# "Install C toolchain", "Build" and "Package" of binaries.yml, verbatim (run in the checkout).
APP_C_TOOLCHAIN='SUDO=""; [ "$(id -u)" -ne 0 ] && SUDO="sudo"
need_cc=0; need_mingw=0
command -v cc >/dev/null || need_cc=1
if [ "$TARGET" = x86_64-pc-windows-gnu ]; then
  command -v x86_64-w64-mingw32-gcc >/dev/null && command -v zip >/dev/null || need_mingw=1
fi
[ "$need_cc" = 0 ] && [ "$need_mingw" = 0 ] && exit 0
if command -v apt-get >/dev/null; then
  pkgs=""
  [ "$need_cc" = 1 ] && pkgs="$pkgs build-essential pkg-config"
  [ "$need_mingw" = 1 ] && pkgs="$pkgs gcc-mingw-w64-x86-64 zip"
  $SUDO apt-get update -qq && $SUDO apt-get install -y --no-install-recommends $pkgs
elif command -v dnf >/dev/null; then
  pkgs=""
  [ "$need_cc" = 1 ] && pkgs="$pkgs gcc make pkgconf-pkg-config"
  [ "$need_mingw" = 1 ] && pkgs="$pkgs mingw64-gcc zip"
  $SUDO dnf install -y $pkgs
elif command -v apk >/dev/null; then
  pkgs=""
  [ "$need_cc" = 1 ] && pkgs="$pkgs build-base pkgconf"
  [ "$need_mingw" = 1 ] && pkgs="$pkgs mingw-w64-gcc zip"
  $SUDO apk add --no-cache $pkgs
else
  echo "no supported package manager to install the toolchain" >&2; exit 1
fi'
APP_BUILD='export RUSTFLAGS="--remap-path-prefix=$HOME=/home --remap-path-prefix=${CARGO_HOME:-$HOME/.cargo}=/cargo --remap-path-prefix=$PWD=/src"
cargo build -p dc-app -p dc-cli --release --target "$TARGET"'
APP_PACKAGE='VERSION="${TAG#v}"
STAGE="dentalcraft_${VERSION}_${NAME}"
mkdir -p "$STAGE/LICENSES" dist
# Third-party licences shipped with the sources (fonts: SIL OFL; icons: MIT).
find crates -path '"'"'*/assets/fonts/*'"'"' -type f \( -name '"'"'OFL*'"'"' -o -name '"'"'LICENSE*'"'"' \) | while read -r f; do
  d="$STAGE/LICENSES/$(basename "$(dirname "$f")")"
  mkdir -p "$d" && cp "$f" "$d/"
done
# The licence (EULA) and the third-party notices, also built into the programs.
cp README.md LICENSE.md THIRD-PARTY-NOTICES.md "$STAGE/"
# How this copy was installed, read by the in-app updater (packaging/README.md).
echo standalone > "$STAGE/install-kind"
case "$TARGET" in
  x86_64-pc-windows-gnu)
    cp "target/$TARGET/release/dentalcraft.exe" "target/$TARGET/release/dentalcraft-cli.exe" "$STAGE/"
    zip -qr "dist/$STAGE.zip" "$STAGE"
    ;;
  *)
    cp "target/$TARGET/release/dentalcraft" "target/$TARGET/release/dentalcraft-cli" "$STAGE/"
    tar -czf "dist/$STAGE.tar.gz" "$STAGE"
    ;;
esac
ls -l dist'

# The sources of an app job: the tag from GitHub (actions/checkout) or, with --src,
# a local working tree: its HEAD commit plus the uncommitted changes (untracked
# files included, ignored ones not). Sets SRC.
APP_SRC=
app_checkout() {
  local ref=$1 dir=$2 wt=$APP_SRC
  if [ -z "$wt" ]; then
    checkout_remote app "$ref" "$dir"
    return
  fi
  SRC=$CACHE/$dir/src
  mkdir -p "$SRC"
  [ -d "$SRC/.git" ] || git init -q "$SRC"
  git -C "$SRC" fetch -q --force --no-tags "$wt" HEAD
  git -C "$SRC" checkout -q --force --detach FETCH_HEAD
  git -C "$SRC" clean -ffdxq -e /target
  git -C "$wt" ls-files -z --cached --others --exclude-standard \
    | rsync -a --from0 --files-from=- --ignore-missing-args "$wt/" "$SRC/"
  git -C "$wt" ls-files -z --deleted | (cd "$SRC" && xargs -0r rm -f --)
  printf '##[group]Checkout (--src: a local working tree, not the tag)\n  path:   %s\n  commit: %s plus the uncommitted changes\n  into:   %s\n##[endgroup]\n' \
    "$wt" "$(git -C "$SRC" rev-parse HEAD)" "$SRC"
}

# The steps of a build job in its container, with the scripts handed over in the environment.
# shellcheck disable=SC2016
BUILD_DRIVER='set -euo pipefail
step() { printf "\n##[group]%s\n%s\n##[endgroup]\n" "$1" "$2"; bash --noprofile --norc -eo pipefail -c "$2"; printf -- "--> %s: ok\n" "$1"; }
step "Check the tag" "$STEP_TAG_CHECK"
step "Install C toolchain" "$STEP_C_TOOLCHAIN"
step "Use SSH for private dentalcraft repositories" "git config --global url.\"git@github.com:$ORG/\".insteadOf \"https://github.com/$ORG/\"
mkdir -p ~/.ssh && chmod 700 ~/.ssh
echo \"$GITHUB_HOST_KEY\" >> ~/.ssh/known_hosts"
step "Install Rust" "if [ ! -x \"\$CARGO_HOME/bin/rustup\" ]; then
  curl -fsSL -o /tmp/rustup-init https://static.rust-lang.org/rustup/dist/x86_64-unknown-linux-gnu/rustup-init
  chmod +x /tmp/rustup-init && /tmp/rustup-init -y -q --no-modify-path --profile minimal --default-toolchain none
fi
rustup toolchain install $RUST_TOOLCHAIN --profile minimal --target \$TARGET --no-self-update
rustup default $RUST_TOOLCHAIN
rustc --version --verbose"
step "Build" "$STEP_BUILD"
[ -z "${STEP_SIGN:-}" ] || step "Sign the Windows programs" "$STEP_SIGN"
step "Package" "$STEP_PACKAGE"'

# "Sign the Windows programs" of binaries.yml, after its key directory is written:
# the Authenticode signature of the two programs, before they are packed.
APP_SIGN_PROGRAMS='bash packaging/windows/authenticode.sh "target/$TARGET/release/dentalcraft.exe" "target/$TARGET/release/dentalcraft-cli.exe"'

# The podman options that hand the Authenticode key to packaging/windows/authenticode.sh:
# $AUTHENTICODE_KEYS mounted read-only (the runner writes the DENTALCRAFT_AUTHENTICODE_*
# secrets into a directory the same way), unless no_sign or the directory is absent; then
# the script warns, or fails with --require-authenticode. Arg: no_sign. Sets AUTHENTICODE_PODMAN.
authenticode_podman_args() {
  AUTHENTICODE_PODMAN=(-e AUTHENTICODE_REQUIRED="$APP_REQUIRE_AUTHENTICODE")
  if [ "$1" = 0 ] && [ -d "$AUTHENTICODE_KEYS" ]; then
    AUTHENTICODE_PODMAN+=(-v "$AUTHENTICODE_KEYS:/run/secrets/authenticode:ro"
      -e AUTHENTICODE_KEY_DIR=/run/secrets/authenticode)
  fi
}

# One build job in a throwaway container (removed with --rm) of an image, as root so
# that the files written into the checkout stay yours. rustup and the cargo registry
# live in mounted cache directories, so that reruns are incremental.
# Args: image matrix-name target install-c-toolchain-step [sign-step no_sign]. Needs SRC and TAG.
app_build_in_container() (
  set -e
  image=$1 name=$2 target=$3 c_toolchain=$4 sign=${5:-} cache=$CACHE/app-binaries/$2 cname="dc-ci-$2-$$"
  AUTHENTICODE_PODMAN=()
  [ -z "$sign" ] || authenticode_podman_args "$6"
  mkdir -p "$cache/rustup" "$cache/cargo-home"
  [ -n "${SSH_AUTH_SOCK:-}" ] || die "no ssh agent (SSH_AUTH_SOCK): the private dependencies are fetched over SSH"
  printf '\n##[group]Container %s (%s), removed on exit\n##[endgroup]\n' "$cname" "$image"
  podman run --rm --name "$cname" --user root \
    --security-opt label=disable \
    -v "$SRC:/work/dentalcraft-app" -w /work/dentalcraft-app \
    -v "$cache/rustup:/opt/rustup" -v "$cache/cargo-home:/opt/cargo" \
    -v "$SSH_AUTH_SOCK:/run/ssh-agent.sock" -e SSH_AUTH_SOCK=/run/ssh-agent.sock \
    -e HOME=/root -e RUSTUP_HOME=/opt/rustup -e CARGO_HOME=/opt/cargo \
    -e PATH=/opt/cargo/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin \
    -e CARGO_NET_GIT_FETCH_WITH_CLI=true -e CARGO_INCREMENTAL=0 -e CARGO_TERM_COLOR=always \
    -e TAG="$TAG" -e TARGET="$target" -e NAME="$name" \
    -e CARGO_TARGET_X86_64_PC_WINDOWS_GNU_LINKER=x86_64-w64-mingw32-gcc \
    -e ORG="$ORG" -e GITHUB_HOST_KEY="$GITHUB_HOST_KEY" -e RUST_TOOLCHAIN="$RUST_TOOLCHAIN" \
    -e STEP_TAG_CHECK="$APP_TAG_CHECK" -e STEP_C_TOOLCHAIN="$c_toolchain" \
    -e STEP_BUILD="$APP_BUILD" -e STEP_SIGN="$sign" -e STEP_PACKAGE="$APP_PACKAGE" \
    "${AUTHENTICODE_PODMAN[@]}" \
    "$image" bash --noprofile --norc -c "$BUILD_DRIVER"
)

# linux_x86_64: the runner runs the job in its own image; here a container of the
# same image does, with the workflow's "Install C toolchain" step.
app_build_linux() (
  set -e
  tag=$1
  app_checkout "refs/tags/$tag" app-binaries/linux_x86_64
  rm -rf "$SRC/dist" "$SRC"/dentalcraft_*
  # A target/ built elsewhere (on the host, before 2026-11-15) holds build scripts
  # linked against another glibc: start it over.
  if [ "$(cat "$SRC/target/.dc-ci-image" 2>/dev/null)" != "$LINUX_IMAGE" ]; then
    rm -rf "$SRC/target"
    mkdir -p "$SRC/target"
    printf '%s\n' "$LINUX_IMAGE" > "$SRC/target/.dc-ci-image"
  fi
  TAG=$tag app_build_in_container "$LINUX_IMAGE" linux_x86_64 x86_64-unknown-linux-gnu "$APP_C_TOOLCHAIN"
)

# windows_x86_64: the runner installs mingw64-gcc and zip; here that happens in a
# throwaway Fedora container, which also needs git and ssh. Args: tag no_sign.
WIN_C_TOOLCHAIN='dnf install -y -q gcc make pkgconf-pkg-config mingw64-gcc zip git-core openssh-clients >/dev/null
x86_64-w64-mingw32-gcc --version | head -n 1'
app_build_windows() (
  set -e
  tag=$1
  app_checkout "refs/tags/$tag" app-binaries/windows_x86_64
  rm -rf "$SRC/dist" "$SRC"/dentalcraft_*
  TAG=$tag app_build_in_container "$WIN_IMAGE" windows_x86_64 x86_64-pc-windows-gnu "$WIN_C_TOOLCHAIN" \
    "$APP_SIGN_PROGRAMS" "$2"
)

# The installers job: packaging/installers.sh builds the AppImage, deb, rpm, Flatpak,
# setup.exe and MSI from the two archives, in a throwaway Fedora container (docker run
# on the runner, podman here), --privileged because flatpak-builder sandboxes the
# build with bubblewrap. The DENTALCRAFT_GPG_KEY secret is the armored secret release
# key, exported here from $RELEASE_KEYS/gpg; the container reads it from a mounted
# file. Unlike the runner, the tool downloads and the Flatpak runtime are kept between
# runs (DC_PKG_CACHE).
app_installers() (
  set -e
  tag=$1 no_sign=$2 dist=$3 version=${1#v} cache=$CACHE/app-binaries/installers cname="dc-ci-installers-$$"
  app_checkout "refs/tags/$tag" app-binaries/installers
  # The apt and dnf repository definitions installed by the deb and the rpm must be
  # byte-identical to the ones the site serves.
  for f in dentalcraft.list dentalcraft.repo; do
    cmp "$SRC/packaging/linux/$f" "$ROOT/dentalcraft-web/linux/$f" \
      || die "packaging/linux/$f differs from dentalcraft-web/linux/$f: they must be identical (packaging/README.md)"
  done
  rm -rf "$SRC/dist" "$SRC/installers"
  mkdir -p "$SRC/dist" "$cache/cache"
  # actions/download-artifact, pattern binaries-*
  cp "$dist/dentalcraft_${version}_linux_x86_64.tar.gz" "$dist/dentalcraft_${version}_windows_x86_64.zip" "$SRC/dist/"
  keyfile=$(mktemp "$cache/gpg-key.XXXXXX")
  trap 'rm -f "$keyfile"' EXIT
  export ALLOW_UNSIGNED='' SOURCE_DATE_EPOCH
  if [ "$no_sign" = 1 ]; then
    ALLOW_UNSIGNED=1
  else
    [ -d "$RELEASE_KEYS/gpg" ] || die "no release GPG key in $RELEASE_KEYS/gpg: pass --no-sign for an unsigned local test"
    gpg --homedir "$RELEASE_KEYS/gpg" --batch --armor --export-secret-keys "$RELEASE_GPG_FPR" > "$keyfile"
    gpgconf --homedir "$RELEASE_KEYS/gpg" --kill gpg-agent 2>/dev/null || true
    [ -s "$keyfile" ] || die "could not export the release GPG key $RELEASE_GPG_FPR from $RELEASE_KEYS/gpg"
  fi
  SOURCE_DATE_EPOCH=$(git -C "$SRC" log -1 --format=%ct)
  printf '\n##[group]Container %s (%s, --privileged), removed on exit\n##[endgroup]\n' "$cname" "$PKG_IMAGE"
  podman run --rm --name "$cname" --privileged \
    -v "$SRC:/work/dentalcraft-app" -w /work/dentalcraft-app \
    -v "$keyfile:/run/secrets/dentalcraft-gpg-key:ro" -e DENTALCRAFT_GPG_KEY_FILE=/run/secrets/dentalcraft-gpg-key \
    -v "$cache/cache:/var/cache/dentalcraft-installers" -e DC_PKG_CACHE=/var/cache/dentalcraft-installers \
    -e TAG="$tag" -e SOURCE_DATE_EPOCH -e ALLOW_UNSIGNED \
    "$PKG_IMAGE" bash packaging/installers.sh
  # "Sign the Windows installers": setup.exe and the MSI (they already hold the signed
  # programs), in another throwaway container of the same image, before the release job
  # hashes them for update.json and the checksums.
  authenticode_podman_args "$no_sign"
  printf '\n##[group]Container %s-sign (%s), removed on exit\n##[endgroup]\n' "$cname" "$PKG_IMAGE"
  podman run --rm --name "$cname-sign" --security-opt label=disable \
    -v "$SRC:/work/dentalcraft-app" -w /work/dentalcraft-app "${AUTHENTICODE_PODMAN[@]}" \
    "$PKG_IMAGE" bash packaging/windows/authenticode.sh \
    "installers/DentalCraft-$version-setup.exe" "installers/DentalCraft-$version-x86_64.msi"
)

# "Update manifest", "Checksums" (in dist/) and "Release notes" of the release job, verbatim.
APP_UPDATE_MANIFEST='VERSION="${TAG#v}"
python3 packaging/update-manifest.py --version "$VERSION" --assets dist --date "$(date -u -d "@$(git log -1 --format=%ct)" +%F)"'
APP_CHECKSUMS='VERSION="${TAG#v}"
assets="dentalcraft_${VERSION}_linux_x86_64.tar.gz dentalcraft_${VERSION}_windows_x86_64.zip DentalCraft-${VERSION}-x86_64.AppImage dentalcraft_${VERSION}_amd64.deb dentalcraft-${VERSION}-1.x86_64.rpm DentalCraft-${VERSION}.flatpak DentalCraft-${VERSION}-setup.exe DentalCraft-${VERSION}-x86_64.msi"
ls -l
for f in $assets; do [ -f "$f" ] || { echo "missing release asset $f" >&2; exit 1; }; done
for f in *; do
  case " $assets update.json update.json.minisig " in
    *" $f "*) ;;
    *) echo "unexpected file among the release assets: $f" >&2; exit 1 ;;
  esac
done
sha256sum -- * > "dentalcraft_${VERSION}_SHA256SUMS.txt"
cat "dentalcraft_${VERSION}_SHA256SUMS.txt"'
APP_RELEASE_NOTES='VERSION="${TAG#v}"
marker='"'"'<!-- binaries-note -->'"'"'
gh release view "$TAG" --json body --jq .body > notes.md
if ! grep -qF "$marker" notes.md; then
  {
    echo
    echo "$marker"
    echo "## Downloads"
    echo
    echo "- Windows x86_64 installers: \`DentalCraft-${VERSION}-setup.exe\` (for the current user, no administrator rights) or \`DentalCraft-${VERSION}-x86_64.msi\` (for all users)."
    echo "- Linux x86_64 installers: Flatpak, \`.deb\` (Debian, Ubuntu), \`.rpm\` (Fedora), AppImage."
    # When macOS is re-enabled, append to the line below: "; macOS universal (Apple Silicon and Intel): \`.zip\` with \`DentalCraft.app\`"
    echo "- Standalone, without installation: Linux \`.tar.gz\`, Windows \`.zip\` (\`dentalcraft.exe\`)."
    echo "- Updates: the \`.deb\` and the \`.rpm\` add the DentalCraft apt or dnf repository, the Flatpak updates from the DentalCraft Flatpak repository, the other versions check dentalcraft.app at startup."
    echo "- Each download also holds \`dentalcraft-cli\`: the command line and MCP server that drive DentalCraft headless or through a running app."
    echo "- Verify the downloads against \`dentalcraft_${VERSION}_SHA256SUMS.txt\`. The Linux packages and repositories are signed with the DentalCraft release key, https://dentalcraft.app/keys/dentalcraft.gpg."
    # Signed or not: the certificate table (PE data directory 4) of setup.exe is empty when unsigned.
    if python3 -c '"'"'import struct,sys; d=open(sys.argv[1],"rb").read(); p=struct.unpack_from("<I",d,60)[0]; o=p+24+(96 if struct.unpack_from("<H",d,p+24)[0]==0x10b else 112); sys.exit(0 if struct.unpack_from("<I",d,o+36)[0] else 1)'"'"' "dist/DentalCraft-${VERSION}-setup.exe"; then
      # The sha256 fingerprint of the pinned self-signed certificate (DER), the only key authenticode.sh accepts.
      fpr=$(python3 -c '"'"'import base64,hashlib,sys; t=open(sys.argv[1]).read(); print(hashlib.sha256(base64.b64decode(t.split("-----BEGIN CERTIFICATE-----")[1].split("-----END CERTIFICATE-----")[0])).hexdigest().upper())'"'"' packaging/windows/dentalcraft-selfsigned.crt.pem)
      echo "- The Windows programs and installers carry a **self-signed** Authenticode signature (with an RFC 3161 timestamp). Windows does not trust a self-signed certificate, so SmartScreen still warns and shows an unknown publisher. Certificate SHA-256 fingerprint: \`${fpr}\`."
    else
      echo "- **The Windows programs are not code-signed.** SmartScreen may warn."
    fi
  } >> notes.md
  gh release edit "$TAG" --notes-file notes.md
fi'

# The images that a run pulls are removed at its end (the runner image is large).
APP_PULLED=()
app_cleanup() {
  local img
  for img in "${APP_PULLED[@]}"; do
    podman image exists "$img" || continue
    podman rmi -f "$img" >/dev/null && echo "removed image $img (pulled by this run)"
  done
  APP_PULLED=()
  podman_stop_pause
}

cmd_binaries_app() {
  local tag=$1 no_upload=$2 out=$3 only=$4 no_sign=$5 version=${1#v} dist=$CACHE/app-binaries/dist failed=0 n rc img
  printf '\n========== binaries %s %s%s ==========\n' "$(gh_repo app)" "$tag" "${APP_SRC:+ (--src $APP_SRC)}"
  TAG=$tag run_step "Check the tag" "TAG='$tag'
$APP_TAG_CHECK"
  case "$only" in ''|linux_x86_64|windows_x86_64|installers) ;; *) die "--only: linux_x86_64, windows_x86_64 or installers" ;; esac
  if [ "$no_upload" = 0 ] && { [ -n "$APP_SRC" ] || [ "$no_sign" = 1 ]; }; then
    die "--src and --no-sign are for local tests: add --no-upload"
  fi
  if [ "$APP_REQUIRE_AUTHENTICODE" = 1 ]; then
    [ "$no_sign" = 0 ] || die "--require-authenticode and --no-sign exclude each other"
    [ -d "$AUTHENTICODE_KEYS" ] || die "--require-authenticode: no Authenticode key in $AUTHENTICODE_KEYS (docs/local-ci.md)"
  elif [ "$no_sign" = 0 ] && [ ! -d "$AUTHENTICODE_KEYS" ]; then
    echo "##[warning]no $AUTHENTICODE_KEYS: the Windows programs and installers will not be Authenticode-signed"
  fi
  lock "binaries-app-$tag"
  podman_note_state
  for img in "$LINUX_IMAGE" "$WIN_IMAGE" "$PKG_IMAGE"; do
    image_existed "$img" && continue
    case " ${APP_PULLED[*]} " in *" $img "*) ;; *) APP_PULLED+=("$img") ;; esac
  done
  trap app_cleanup EXIT
  if [ "$only" = installers ]; then
    for n in linux_x86_64.tar.gz windows_x86_64.zip; do
      [ -f "$dist/dentalcraft_${version}_$n" ] || die "--only installers: no $dist/dentalcraft_${version}_$n, run the build jobs first"
    done
    find "$dist" -mindepth 1 -maxdepth 1 ! -name "dentalcraft_${version}_linux_x86_64.tar.gz" \
      ! -name "dentalcraft_${version}_windows_x86_64.zip" -exec rm -rf {} +
  else
    rm -rf "$dist"
    mkdir -p "$dist"
    # strategy.fail-fast: false - both entries run; the next jobs need both.
    for n in linux_x86_64 windows_x86_64; do
      [ -z "$only" ] || [ "$only" = "$n" ] || continue
      printf '\n---------- build %s ----------\n' "$n"
      set +e
      if [ "$n" = linux_x86_64 ]; then app_build_linux "$tag"; else app_build_windows "$tag" "$no_sign"; fi
      rc=$?
      set -e
      if [ "$rc" -ne 0 ]; then failed=1; echo "##[error]build $n failed"; continue; fi
      # actions/upload-artifact + download-artifact (merge-multiple) into one dist/
      cp "$CACHE/app-binaries/$n/src/dist/"* "$dist/"
    done
    [ "$failed" = 0 ] || die "a build failed: nothing is attached"
    if [ -n "$only" ]; then
      if [ -n "$out" ]; then mkdir -p "$out" && cp "$dist"/* "$out/" && echo "copied to $out"; fi
      echo "--only $only: stopping after packaging ($dist)"
      return 0
    fi
  fi
  printf '\n---------- installers ----------\n'
  app_installers "$tag" "$no_sign" "$dist" || die "the installers job failed: nothing is attached"
  cp "$CACHE/app-binaries/installers/src/installers/"* "$dist/"
  if [ "$only" = installers ]; then
    if [ -n "$out" ]; then mkdir -p "$out" && cp "$dist"/* "$out/" && echo "copied to $out"; fi
    echo "--only installers: stopping before the release job ($dist)"
    return 0
  fi
  printf '\n---------- attach to release ----------\n'
  (
    set -e
    app_checkout "refs/tags/$tag" app-binaries/release
    cd "$SRC"
    rm -rf dist notes.md
    # actions/download-artifact, every artifact (merge-multiple)
    cp -r "$dist" dist
    export TAG=$tag DENTALCRAFT_MINISIGN_KEY=
    if [ "$no_sign" = 1 ]; then
      echo "##[warning]--no-sign: no update.json, the update manifest is only ever published signed"
    else
      [ -f "$RELEASE_KEYS/minisign.key" ] || die "no $RELEASE_KEYS/minisign.key: pass --no-sign for an unsigned local test"
      DENTALCRAFT_MINISIGN_KEY=$(cat "$RELEASE_KEYS/minisign.key")
      run_step "Update manifest" "$APP_UPDATE_MANIFEST"
      DENTALCRAFT_MINISIGN_KEY=
    fi
    (cd dist && run_step "Checksums" "$APP_CHECKSUMS")
    cp dist/* "$dist/"
    if [ -n "$out" ]; then mkdir -p "$out" && cp dist/* "$out/" && echo "copied to $out"; fi
    if [ "$no_upload" = 1 ]; then echo "--no-upload: release assets in $dist"; exit 0; fi
    export GH_TOKEN GH_REPO
    GH_TOKEN=$(gh auth token) GH_REPO=$(gh_repo app)
    run_step "Upload to the release" 'gh release view "$TAG" >/dev/null   # the release must already exist
gh release upload "$TAG" dist/* --clobber'
    run_step "Release notes" "$APP_RELEASE_NOTES"
    rm -f notes.md
  )
}

# ---------------------------------------------------------------- server binaries

SERVER_TAG_CHECK='if ! printf '"'"'%s'"'"' "$TAG" | grep -Eq '"'"'^v[0-9]+\.[0-9]+\.[0-9]+(-[0-9A-Za-z.-]+)?$'"'"'; then
  echo "tag must be a release tag like v1.2.3, got: $TAG" >&2
  exit 1
fi'

cmd_binaries_server() {
  local tag=$1 no_upload=$2 out=$3
  printf '\n========== binaries %s %s ==========\n' "$(gh_repo server)" "$tag"
  (
    set -e
    export TAG=$tag
    run_step "Check the tag and derive the version" "$SERVER_TAG_CHECK"
    lock "binaries-server-$tag"
    checkout_remote server "refs/tags/$tag" server-binaries
    clean_env
    cd "$SRC"
    local ver
    ver=$(go_version_of) || die "no go version in go.mod"
    export GOTOOLCHAIN="go$ver" GOPATH=$CACHE/go GOCACHE=$CACHE/go-build
    run_step "Setup Go $ver" 'go version'
    PATH="$(go env GOROOT)/bin:$PATH"
    export PATH VERSION=${tag#v}
    # Verbatim, except that a missing zip is an error instead of a package install.
    run_step "Build and archive" 'set -euo pipefail
command -v zip >/dev/null || { echo "zip is missing: sudo dnf install zip" >&2; exit 1; }
mkdir -p dist
for target in linux/amd64 linux/arm64 darwin/amd64 darwin/arm64 windows/amd64; do
  os="${target%/*}"; arch="${target#*/}"
  ext=""; [ "$os" = windows ] && ext=".exe"
  name="dentalcraft-server_${VERSION}_${os}_${arch}"
  stage="dist/stage/${name}"
  mkdir -p "$stage"
  CGO_ENABLED=0 GOOS="$os" GOARCH="$arch" go build -trimpath \
    -ldflags "-s -w -X main.version=${VERSION}" \
    -o "${stage}/dentalcraft-server${ext}" ./cmd/dentalcraft-server
  cp README.md "$stage/"
  for f in LICENSE LICENSE.md LICENSE.txt; do [ -f "$f" ] && cp "$f" "$stage/"; done
  if [ "$os" = windows ]; then
    (cd dist/stage && zip -qr "../${name}.zip" "${name}")
  else
    tar -C dist/stage --owner=0 --group=0 --numeric-owner -czf "dist/${name}.tar.gz" "${name}"
  fi
done
rm -rf dist/stage
(cd dist && sha256sum -- *.tar.gz *.zip > SHA256SUMS && cat SHA256SUMS)'
    if [ -n "$out" ]; then mkdir -p "$out" && cp dist/* "$out/" && echo "copied to $out"; fi
    if [ "$no_upload" = 1 ]; then echo "--no-upload: archives in $SRC/dist"; exit 0; fi
    export GH_TOKEN GITHUB_REPOSITORY
    GH_TOKEN=$(gh auth token) GITHUB_REPOSITORY=$(gh_repo server)
    run_step "Attach to the release" 'set -euo pipefail
api="https://api.github.com/repos/${GITHUB_REPOSITORY}"
auth=(-H "Authorization: Bearer ${GH_TOKEN}" -H "Accept: application/vnd.github+json" -H "X-GitHub-Api-Version: 2022-11-28")
rel="$(curl -fsS "${auth[@]}" "${api}/releases/tags/${TAG}")"
id="$(printf '"'"'%s'"'"' "$rel" | grep -oE '"'"'"id": *[0-9]+'"'"' | head -1 | grep -oE '"'"'[0-9]+'"'"')"
[ -n "$id" ] || { echo "no release for tag ${TAG}" >&2; exit 1; }
existing="$(curl -fsS "${auth[@]}" "${api}/releases/${id}/assets?per_page=100")"
for f in dist/*; do
  name="$(basename "$f")"
  # delete an asset of the same name (id and name are on one line pair in the JSON)
  old="$(printf '"'"'%s'"'"' "$existing" | tr -d '"'"'\n'"'"' | grep -oE '"'"'"id": *[0-9]+, *"node_id": *"[^"]*", *"name": *"'"'"'"${name//./\\.}"'"'"'"'"'"' | grep -oE '"'"'"id": *[0-9]+'"'"' | head -1 | grep -oE '"'"'[0-9]+'"'"' || true)"
  if [ -n "$old" ]; then
    curl -fsS -X DELETE "${auth[@]}" "${api}/releases/assets/${old}"
    echo "replaced existing asset ${name}"
  fi
  case "$name" in *.zip) ct=application/zip ;; *.tar.gz) ct=application/gzip ;; *) ct=text/plain ;; esac
  curl -fsS -X POST "${auth[@]}" -H "Content-Type: ${ct}" --data-binary "@${f}" \
    "https://uploads.github.com/repos/${GITHUB_REPOSITORY}/releases/${id}/assets?name=${name}" >/dev/null
  echo "uploaded ${name}"
done'
  )
}

# ---------------------------------------------------------------- images

need_packages_scope() {
  gh auth status 2>&1 | grep -q "write:packages" && return 0
  die "the gh token lacks the write:packages scope needed to push to ghcr.io. Run: gh auth refresh -h github.com -s write:packages"
}

# docker/login-action + docker/build-push-action with podman. Pushes every tag
# unless no_push, then removes the built image and any base image this run pulled.
# Args: no_push context file label... -- tag...
podman_build_push() {
  local no_push=$1 file=$2; shift 2
  local args=() tags=() bases=() pulled=() b rc=0 authfile
  while [ "$1" != -- ]; do args+=(--label "$1"); shift; done
  shift
  tags=("$@")
  mapfile -t bases < <(sed -n 's/^FROM[[:space:]]\{1,\}\(--[^[:space:]]*[[:space:]]\{1,\}\)*\([^[:space:]]*\).*/\2/p' "$file" | sort -u)
  for b in "${bases[@]}"; do image_existed "$b" || pulled+=("$b"); done
  podman_note_state
  local targs=()
  for b in "${tags[@]}"; do targs+=(-t "$b"); done
  # --format docker: buildx keeps HEALTHCHECK in the image config; the OCI format drops it.
  printf '\n##[group]Build\n  podman build --format docker --pull=always --layers=false -f %s %s %s .\n##[endgroup]\n' "$file" "${args[*]}" "${targs[*]}"
  podman build --format docker --pull=always --layers=false -f "$file" "${BUILD_ARGS[@]}" "${args[@]}" "${targs[@]}" . || rc=$?
  if [ "$rc" = 0 ] && [ "$no_push" = 0 ]; then
    authfile=$(mktemp "$CACHE/auth.XXXXXX.json")
    echo '{}' >"$authfile"   # podman login parses an existing authfile; mktemp leaves it empty
    if gh auth token | podman login ghcr.io --authfile "$authfile" -u "$(gh api user --jq .login)" --password-stdin; then
      for b in "${tags[@]}"; do
        podman push --authfile "$authfile" "$b" || { rc=$?; break; }
        echo "pushed $b"
      done
    else
      rc=1
    fi
    rm -f "$authfile"
  fi
  [ "$no_push" = 1 ] && [ "$rc" = 0 ] && podman image inspect "${tags[0]}" --format '{{json .Labels}}'
  podman rmi -f "${tags[@]}" >/dev/null 2>&1 || true
  for b in "${pulled[@]}"; do podman rmi -f "$b" >/dev/null 2>&1 && echo "removed base image $b (pulled by this run)"; done
  podman_stop_pause
  return "$rc"
}

cmd_image_server() {
  local tag=$1 no_push=$2 version image sha
  printf '\n========== image %s %s ==========\n' "$(gh_repo server)" "$tag"
  REF=$tag run_step "Check the ref and derive the version" "REF='$tag'
$(printf '%s' "$SERVER_TAG_CHECK" | sed -e 's/\$TAG/$REF/g' -e 's/tag must be a release tag/ref must be a release tag/')"
  [ "$no_push" = 1 ] || need_packages_scope
  lock "image-server-$tag"
  version=${tag#v}
  checkout_remote server "refs/tags/$tag" server-image
  sha=$(git -C "$SRC" rev-parse HEAD)
  image="ghcr.io/$ORG/dentalcraft-server"
  (
    cd "$SRC"
    BUILD_ARGS=(--build-arg "VERSION=$version")
    podman_build_push "$no_push" Dockerfile \
      "org.opencontainers.image.source=https://github.com/$(gh_repo server)" \
      "org.opencontainers.image.version=$version" \
      "org.opencontainers.image.revision=$sha" \
      -- "$image:$version" "$image:latest"
  )
}

cmd_web_image() {
  local ref=$1 no_push=$2 ref_type=branch fetch sha image version
  printf '\n========== image %s %s ==========\n' "$(gh_repo web)" "$ref"
  case "$ref" in
    main) fetch=refs/heads/main ;;
    v*) ref_type=tag; fetch=refs/tags/$ref ;;
    *) die "web-image --ref: main or a v* tag (the workflow's push triggers)" ;;
  esac
  [ "$no_push" = 1 ] || need_packages_scope
  lock "image-web-$ref"
  checkout_remote web "$fetch" web-image
  sha=$(git -C "$SRC" rev-parse HEAD)
  (
    set -e
    cd "$SRC"
    export GH_TOKEN
    GH_TOKEN=$(gh auth token)   # stands in for the APP_RELEASE_TOKEN secret
    run_step "Fetch the app downloads" 'if [ -z "$GH_TOKEN" ]; then
  echo "secret APP_RELEASE_TOKEN is empty: add a fine-grained token with read access to Contents of the app repo" >&2
  exit 1
fi
# The runner has no guaranteed node or jq: read the two values with sed (the file is pretty-printed JSON).
repo=$(sed -n '"'"'s/^ *"repo": *"\([^"]*\)".*/\1/p'"'"' content/site.data.json | head -n 1)
tag=$(sed -n '"'"'s/^ *"tag": *"\(v[^"]*\)".*/\1/p'"'"' content/site.data.json | head -n 1)
printf '"'"'%s'"'"' "$repo" | grep -Eq '"'"'^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$'"'"' || { echo "bad release.repo in content/site.data.json: '"'"'$repo'"'"'" >&2; exit 1; }
printf '"'"'%s'"'"' "$tag" | grep -Eq '"'"'^v[0-9]+\.[0-9]+\.[0-9]+(-[0-9A-Za-z.-]+)?$'"'"' || { echo "bad release.tag in content/site.data.json: '"'"'$tag'"'"'" >&2; exit 1; }
mkdir -p downloads
gh release download "$tag" -R "$repo" -D downloads
ls -l downloads
sha256sum downloads/*'
    unset GH_TOKEN
    image="ghcr.io/$(printf '%s' "$ORG" | tr '[:upper:]' '[:lower:]')/dentalcraft-web"
    local tags=("$image:latest" "$image:sha-${sha::7}")
    version=$sha
    if [ "$ref_type" = tag ]; then
      printf '%s' "$ref" | grep -Eq '^v[0-9]+\.[0-9]+\.[0-9]+(-[0-9A-Za-z.-]+)?$' \
        || die "tag must look like v1.2.3, got: $ref"
      tags+=("$image:${ref#v}")
      version=${ref#v}
    fi
    # Stands in for the DENTALCRAFT_GPG_KEY secret (build secret "gpg"): the env var when set,
    # else the key in the dedicated GNUPGHOME. The file lives only for the build.
    local gpgfile
    gpgfile=$(mktemp "$CACHE/gpg.XXXXXX.asc")
    trap 'rm -f "$gpgfile"' EXIT
    if [ -n "${DENTALCRAFT_GPG_KEY:-}" ]; then
      printf '%s\n' "$DENTALCRAFT_GPG_KEY" >"$gpgfile"
    else
      GNUPGHOME=$RELEASE_KEYS/gpg gpg --batch --armor --export-secret-keys "$RELEASE_GPG_FPR" >"$gpgfile"
      GNUPGHOME=$RELEASE_KEYS/gpg gpgconf --kill gpg-agent || true
    fi
    [ -s "$gpgfile" ] || die "no release GPG key: set DENTALCRAFT_GPG_KEY or create $RELEASE_KEYS/gpg"
    BUILD_ARGS=(--secret "id=gpg,src=$gpgfile")
    podman_build_push "$no_push" Containerfile \
      "org.opencontainers.image.source=https://github.com/$(gh_repo web)" \
      "org.opencontainers.image.revision=$sha" \
      "org.opencontainers.image.version=$version" \
      -- "${tags[@]}"
  )
}

# ---------------------------------------------------------------- main

release_main() {
  local cmd=${1:-}
  [ -n "$cmd" ] || usage
  shift
  case "$cmd" in
    core|aligners|app|server)
      local dry=0
      while [ $# -gt 0 ]; do
        case "$1" in
          --dry-run) dry=1; shift ;;
          --require-authenticode) [ "$cmd" = app ] || usage; APP_REQUIRE_AUTHENTICODE=1; shift ;;
          *) usage ;;
        esac
      done
      # Before release-please creates the release, not after the chained builds.
      if [ "$APP_REQUIRE_AUTHENTICODE" = 1 ] && [ ! -d "$AUTHENTICODE_KEYS" ]; then
        die "--require-authenticode: no Authenticode key in $AUTHENTICODE_KEYS (docs/local-ci.md)"
      fi
      cmd_release "$cmd" "$dry"
      ;;
    binaries)
      local repo=${1:-} tag=${2:-} no_upload=0 out='' only='' src='' no_sign=0
      [ -n "$repo" ] && [ -n "$tag" ] || usage
      shift 2
      while [ $# -gt 0 ]; do
        case "$1" in
          --no-upload) no_upload=1; shift ;;
          --out) [ $# -ge 2 ] || usage; out=$(realpath -m "$2"); shift 2 ;;
          --only) [ $# -ge 2 ] || usage; only=$2; shift 2 ;;
          --src) [ $# -ge 2 ] || usage; src=$(realpath -e "$2") || die "--src: no such directory: $2"; shift 2 ;;
          --no-sign) no_sign=1; shift ;;
          --require-authenticode) APP_REQUIRE_AUTHENTICODE=1; shift ;;
          *) usage ;;
        esac
      done
      case "$repo" in
        app)
          if [ -n "$src" ]; then
            git -C "$src" rev-parse --is-inside-work-tree >/dev/null 2>&1 || die "--src: $src is not a git working tree"
          fi
          APP_SRC=$src cmd_binaries_app "$tag" "$no_upload" "$out" "$only" "$no_sign"
          ;;
        server)
          [ -z "$only$src" ] && [ "$no_sign" = 0 ] && [ "$APP_REQUIRE_AUTHENTICODE" = 0 ] || usage
          cmd_binaries_server "$tag" "$no_upload" "$out"
          ;;
        *) usage ;;
      esac
      ;;
    image)
      [ "${1:-}" = server ] && [ -n "${2:-}" ] || usage
      local tag=$2 no_push=0
      shift 2
      case "${1:-}" in '') ;; --no-push) no_push=1; shift ;; *) usage ;; esac
      [ $# -eq 0 ] || usage
      cmd_image_server "$tag" "$no_push"
      ;;
    web-image)
      local ref=main no_push=0
      while [ $# -gt 0 ]; do
        case "$1" in
          --ref) [ $# -ge 2 ] || usage; ref=$2; shift 2 ;;
          --no-push) no_push=1; shift ;;
          *) usage ;;
        esac
      done
      cmd_web_image "$ref" "$no_push"
      ;;
    *) usage ;;
  esac
}

mkdir -p "$CACHE"
release_main "$@"
