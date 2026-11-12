#!/usr/bin/env bash
# Local replica of release-please.yml and of the jobs it chains, used while
# GitHub Actions are disabled (docs/local-ci.md). The workflow files under
# .github/ stay the source of truth: keep this script in step with them.
#
#   scripts/release-local.sh <core|aligners|app|server> [--dry-run]
#       release-please.yml: `github-release`, then `release-pr`, with the
#       release-please version bundled in googleapis/release-please-action@v5.
#       When a release is created, the chained jobs follow: app -> binaries,
#       server -> image + binaries. Requires local main == origin/main and a
#       passing `scripts/ci-local.sh <repo> --ref origin/main` on that commit.
#   scripts/release-local.sh binaries <app|server> <tag> [--no-upload] [--out DIR] [--only NAME]
#       binaries.yml alone (workflow_dispatch). --no-upload builds and packages
#       only; --out copies the archives to DIR; --only (app: linux_x86_64 or
#       windows_x86_64) builds one matrix entry and stops after packaging.
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
# binaries.yml of dentalcraft-app: Windows is cross-compiled with mingw-w64 in a
# throwaway container of this image.
WIN_IMAGE=registry.fedoraproject.org/fedora:45

usage() { sed -n '2,22p' "${BASH_SOURCE[0]}" | sed 's/^# \{0,1\}//' >&2; exit 2; }

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
    app) cmd_binaries_app "$created" 0 "" "" ;;
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

# "Build" and "Package" of binaries.yml, verbatim (run in the checkout).
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
cp README.md "$STAGE/"
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

# linux_x86_64 on this host, like the self-hosted runner.
app_build_linux() {
  local tag=$1
  (
    set -e
    checkout_remote app "refs/tags/$tag" app-binaries/linux_x86_64
    clean_env
    export CARGO_INCREMENTAL=0 CARGO_TERM_COLOR=always CARGO_NET_GIT_FETCH_WITH_CLI=true
    export TAG=$tag TARGET=x86_64-unknown-linux-gnu NAME=linux_x86_64
    export CARGO_TARGET_X86_64_PC_WINDOWS_GNU_LINKER=x86_64-w64-mingw32-gcc
    cd "$SRC"
    rm -rf dist ./dentalcraft_*
    c_toolchain_step
    ssh_env
    run_step "Install Rust $RUST_TOOLCHAIN ($TARGET)" "rustup toolchain list | grep -q '^$RUST_TOOLCHAIN-' || rustup toolchain install $RUST_TOOLCHAIN --profile minimal --no-self-update
rustup target add --toolchain $RUST_TOOLCHAIN $TARGET
rustc --version --verbose"
    run_step "Build" "$APP_BUILD"
    run_step "Package" "$APP_PACKAGE"
  )
}

# The steps run in the container, with the scripts handed over in the environment.
# shellcheck disable=SC2016
WIN_DRIVER='set -euo pipefail
step() { printf "\n##[group]%s\n%s\n##[endgroup]\n" "$1" "$2"; bash --noprofile --norc -eo pipefail -c "$2"; printf -- "--> %s: ok\n" "$1"; }
step "Check the tag" "$STEP_TAG_CHECK"
step "Install C toolchain" "dnf install -y -q gcc make pkgconf-pkg-config mingw64-gcc zip git-core openssh-clients >/dev/null
x86_64-w64-mingw32-gcc --version | head -n 1"
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
step "Package" "$STEP_PACKAGE"'

# windows_x86_64: the runner installs mingw64-gcc and zip; here that happens in a
# throwaway Fedora container (removed with --rm). rustup and the cargo registry
# live in mounted cache directories so that reruns are incremental.
app_build_windows() (
  set -e
  tag=$1 cache=$CACHE/app-binaries/windows_x86_64 rc=0 pulled=0 cname="dc-ci-win-$$"
  checkout_remote app "refs/tags/$tag" app-binaries/windows_x86_64
  rm -rf "$SRC/dist" "$SRC"/dentalcraft_*
  mkdir -p "$cache/rustup" "$cache/cargo-home"
  [ -n "${SSH_AUTH_SOCK:-}" ] || die "no ssh agent (SSH_AUTH_SOCK): the private dependencies are fetched over SSH"
  image_existed "$WIN_IMAGE" || pulled=1
  printf '\n##[group]Container %s (%s), removed on exit\n##[endgroup]\n' "$cname" "$WIN_IMAGE"
  podman run --rm --name "$cname" \
    --security-opt label=disable \
    -v "$SRC:/work/dentalcraft-app" -w /work/dentalcraft-app \
    -v "$cache/rustup:/opt/rustup" -v "$cache/cargo-home:/opt/cargo" \
    -v "$SSH_AUTH_SOCK:/run/ssh-agent.sock" -e SSH_AUTH_SOCK=/run/ssh-agent.sock \
    -e RUSTUP_HOME=/opt/rustup -e CARGO_HOME=/opt/cargo \
    -e PATH=/opt/cargo/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin \
    -e CARGO_NET_GIT_FETCH_WITH_CLI=true -e CARGO_INCREMENTAL=0 -e CARGO_TERM_COLOR=always \
    -e TAG="$tag" -e TARGET=x86_64-pc-windows-gnu -e NAME=windows_x86_64 \
    -e CARGO_TARGET_X86_64_PC_WINDOWS_GNU_LINKER=x86_64-w64-mingw32-gcc \
    -e ORG="$ORG" -e GITHUB_HOST_KEY="$GITHUB_HOST_KEY" -e RUST_TOOLCHAIN="$RUST_TOOLCHAIN" \
    -e STEP_TAG_CHECK="$APP_TAG_CHECK" -e STEP_BUILD="$APP_BUILD" -e STEP_PACKAGE="$APP_PACKAGE" \
    "$WIN_IMAGE" bash --noprofile --norc -c "$WIN_DRIVER" || rc=$?
  if [ "$pulled" = 1 ]; then
    podman rmi -f "$WIN_IMAGE" >/dev/null && echo "removed image $WIN_IMAGE (pulled by this run)"
  fi
  podman_stop_pause
  exit "$rc"
)

cmd_binaries_app() {
  local tag=$1 no_upload=$2 out=$3 only=$4 dist=$CACHE/app-binaries/dist failed=0 n
  printf '\n========== binaries %s %s ==========\n' "$(gh_repo app)" "$tag"
  TAG=$tag run_step "Check the tag" "TAG='$tag'
$APP_TAG_CHECK"
  lock "binaries-app-$tag"
  podman_note_state
  case "$only" in ''|linux_x86_64|windows_x86_64) ;; *) die "--only: linux_x86_64 or windows_x86_64" ;; esac
  rm -rf "$dist"
  mkdir -p "$dist"
  # strategy.fail-fast: false - both entries run; the release job needs both.
  for n in linux_x86_64 windows_x86_64; do
    [ -z "$only" ] || [ "$only" = "$n" ] || continue
    printf '\n---------- build %s ----------\n' "$n"
    set +e
    if [ "$n" = linux_x86_64 ]; then app_build_linux "$tag"; else app_build_windows "$tag"; fi
    local rc=$?
    set -e
    if [ "$rc" -ne 0 ]; then failed=1; echo "##[error]build $n failed"; continue; fi
    # actions/upload-artifact + download-artifact (merge-multiple) into one dist/
    cp "$CACHE/app-binaries/$n/src/dist/"* "$dist/"
  done
  [ "$failed" = 0 ] || die "a build failed: nothing is attached"
  if [ -n "$out" ]; then mkdir -p "$out" && cp "$dist"/* "$out/" && echo "copied to $out"; fi
  [ -z "$only" ] || { echo "--only $only: stopping after packaging ($dist)"; return 0; }
  (
    cd "$dist"
    run_step "Checksums" 'ls -l
[ "$(ls | wc -l)" -eq 2 ] || { echo "expected 2 archives (Linux, Windows)" >&2; exit 1; }
sha256sum -- * > SHA256SUMS
cat SHA256SUMS'
  )
  [ -z "$out" ] || cp "$dist/SHA256SUMS" "$out/"
  if [ "$no_upload" = 1 ]; then echo "--no-upload: archives in $dist"; return 0; fi
  (
    export GH_TOKEN GH_REPO TAG
    GH_TOKEN=$(gh auth token) GH_REPO=$(gh_repo app) TAG=$tag
    cd "$CACHE/app-binaries"
    run_step "Upload to the release" 'gh release view "$TAG" >/dev/null   # the release must already exist
gh release upload "$TAG" dist/* --clobber'
    run_step "Release notes" 'marker='"'"'<!-- binaries-note -->'"'"'
gh release view "$TAG" --json body --jq .body > notes.md
if ! grep -qF "$marker" notes.md; then
  {
    echo
    echo "$marker"
    echo "## Binaries"
    echo
    # When macOS is re-enabled, append to the line below: "; macOS universal (Apple Silicon and Intel): \`.zip\` with \`DentalCraft.app\`"
    echo "- Linux x86_64: \`.tar.gz\`; Windows x86_64: \`.zip\` (\`dentalcraft.exe\`)."
    echo "- Each archive also holds \`dentalcraft-cli\`: the command line and MCP server that drive DentalCraft headless or through a running app."
    echo "- Verify the downloads against \`SHA256SUMS\`."
    echo "- **The binaries are not code-signed.** Windows: SmartScreen may warn."
  } >> notes.md
  gh release edit "$TAG" --notes-file notes.md
fi'
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
gh release download "$tag" -R "$repo" -p '"'"'dentalcraft_*'"'"' -D downloads
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
    BUILD_ARGS=()
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
      case "${1:-}" in '') ;; --dry-run) dry=1; shift ;; *) usage ;; esac
      [ $# -eq 0 ] || usage
      cmd_release "$cmd" "$dry"
      ;;
    binaries)
      local repo=${1:-} tag=${2:-} no_upload=0 out='' only=''
      [ -n "$repo" ] && [ -n "$tag" ] || usage
      shift 2
      while [ $# -gt 0 ]; do
        case "$1" in
          --no-upload) no_upload=1; shift ;;
          --out) [ $# -ge 2 ] || usage; out=$(realpath -m "$2"); shift 2 ;;
          --only) [ $# -ge 2 ] || usage; only=$2; shift 2 ;;
          *) usage ;;
        esac
      done
      case "$repo" in
        app) cmd_binaries_app "$tag" "$no_upload" "$out" "$only" ;;
        server) [ -z "$only" ] || usage; cmd_binaries_server "$tag" "$no_upload" "$out" ;;
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
