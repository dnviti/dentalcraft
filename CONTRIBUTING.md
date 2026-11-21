# Contributing to dentalcraft

Thank you for your interest. This is a small project with one maintainer, so please keep changes focused and talk before you do something big.

This repository gathers the DentalCraft code repositories as git submodules, together with the plan, the decisions, the design files, the hardware designs and the local CI and release scripts. Code changes belong in the code repositories, each with its own `CONTRIBUTING.md`:

| Repository | What it holds |
| --- | --- |
| [`dentalcraft-core`](https://github.com/dnviti/dentalcraft-core) | Engine: meshes, geometry, case model, project files, commands, scanner and turntable drivers |
| [`dentalcraft-aligners`](https://github.com/dnviti/dentalcraft-aligners) | The *Aligners* module |
| [`dentalcraft-app`](https://github.com/dnviti/dentalcraft-app) | The desktop application and its installers |
| [`dentalcraft-web`](https://github.com/dnviti/dentalcraft-web) | The website, downloads and update feed |

Before you start, read the [README](README.md), the [Code of Conduct](CODE_OF_CONDUCT.md) and the [licence](LICENSE.md).

## What to change here

- Documentation under `docs/` and `SOURCES.md` (a missing or wrong source is a welcome fix).
- Design files under `docs/design/` and the parametric scanner enclosure under `hardware/`.
- The scripts under `scripts/`. They replay the CI and release workflows locally. Do not change `.github/workflows/*` or the release configuration unless an issue asks for it.

## Before you write

- Open an issue first for anything larger than a small fix, so the direction is agreed before you spend time.
- **Never commit patient data**: no real scans, no `.dcprj` files from real cases, no Teeth3DS or other third-party datasets. Test data must be synthetic.
- Do not add secrets, host names, customer data or other details of private infrastructure to any file.
- DentalCraft is not a certified medical device. Do not present a change as clinically validated.
- If you add a scientific, technical or standards source, add it to [`SOURCES.md`](SOURCES.md) with authors, year, title, venue and DOI or URL.

## Licence of your contribution

This project is source-available under the [PolyForm Noncommercial License 1.0.0](LICENSE.md). By sending a contribution (a pull request, a patch, or any other code, text or data) you agree to the following:

1. You wrote it, or you have the right to submit it under these terms (see the sign-off below).
2. You keep the copyright in your contribution.
3. You grant Daniele Viti a perpetual, worldwide, non-exclusive, royalty-free, irrevocable licence to use, copy, modify, distribute and sublicense your contribution, as part of this project or on its own, **under any licence terms, including commercial ones**. This lets the author relicense the project, for example to offer commercial licences.
4. Your contribution is also available to everyone under the PolyForm Noncommercial License 1.0.0, like the rest of the project.

This text is a plain-language agreement, not legal advice, and it has not been reviewed by a lawyer. If you cannot agree to it, do not send a contribution.

## Sign-off (Developer Certificate of Origin)

Every commit needs a `Signed-off-by` line with your real name and email. It says you accept the [Developer Certificate of Origin 1.1](https://developercertificate.org/). Git adds it for you:

```sh
git commit -s -m "docs: describe the change"
```

A pull request with unsigned commits is not merged.

## Working with the submodules

```sh
git clone --recurse-submodules https://github.com/dnviti/dentalcraft.git
cd dentalcraft
```

Builds started inside this folder use the working trees of the submodules instead of their pinned tags (see `.cargo/config.toml`). Cargo then rewrites the `Cargo.lock` of a submodule with path sources: never commit that. Run `git checkout -- Cargo.lock` in the submodule first.

Each submodule is pinned to a commit. Pointer bumps are made by the maintainer after a release, with the title `chore(submodule): <repo> a vX.Y.Z`. Do not include a pointer bump in a pull request.

## Branches, commits and pull requests

- Work on a branch named `feat/...`, `fix/...` or `docs/...`, and open a pull request against `main`.
- Use [Conventional Commits](https://www.conventionalcommits.org/): `feat:`, `fix:`, `perf:`, `docs:`, `test:`, `refactor:`, `chore:`. The pull request is squash-merged and its title becomes the commit message, so the title must follow the same format.
- Versions, changelogs and tags are made by [release-please](https://github.com/googleapis/release-please) in each code repository. Do not edit them by hand.

## Reporting problems

- Bugs and ideas: open an issue. Describe what you did, what you expected and what happened. Do not attach patient data.
- Security problems: do not open a public issue. Follow [`SECURITY.md`](SECURITY.md).
