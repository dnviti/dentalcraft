# Handoff, 2026-10-31

State at the end of day 1, and what to do next. Plan: [`PLAN.md`](PLAN.md); overrides: [`DECISIONS.md`](DECISIONS.md).

## Pinned versions

`dentalcraft-core` v0.2.1, `dentalcraft-aligners` v0.1.0, `dentalcraft-app` v0.1.0, `dentalcraft-server` v0.1.0.

## State per repository

Wave 1 (WP1 to WP11) is done: the skeleton runs end to end (sign-in, home, new project, workspace with viewport, save and load `.dcprj`).

| Repository | Real | Stubbed |
| --- | --- | --- |
| `dentalcraft-core` | Mesh I/O, `.dcprj` read/write, case model, commands and undo, jobs, module API (select hook, `ModuleCodec`), i18n, theme. | `dc-geom` is not validated against the old plugin yet (Wave 2). `dc-theme` carries placeholder tokens. |
| `dentalcraft-aligners` | Data model, menu tree, inspectors, en/it strings, state codec. | All `dca-algo` stages (autoseed, segmentation, reconstruct, diagnosis, setup, staging, occlusion, shell, trim, stamp, visits, export, bite) are stubs; commands answer "Not yet available". |
| `dentalcraft-app` | Shell, sign-in (PKCE loopback, keyring), home, new project, workspace, viewport, support screen, en/it, real design tokens in `dc-ui`. | News, documentation URLs, ticket list and attachments, evaluation and create-account flows. Release issuer URL is a placeholder (`RELEASE_ISSUER` in `dc-app/src/config.rs`). Regulatory dossier not carried over; `xtask` is absent. |
REDACTED

## Next waves (PLAN section 4)

Suggested order:

1. **Wave 2, core geometry (WP12 to WP18).** Start with WP12, the golden harness: run the old plugin headless in Blender to produce JSON and `.dcm` fixtures. Everything else is validated against it. After WP12, WP13 to WP18 are independent and can run in parallel, one agent each: BVH/closest/ray (WP13), ICP (WP14), QEM (WP15), Liepa hole fill (WP16), PCG and harmonic solves (WP17), SDF (WP18). WP14 and WP18 are the heaviest. Tolerances are in PLAN section 5.
2. **Wave 3, import and segmentation (WP19 to WP24).** WP19 (world frame, import) first; WP20 and WP21 follow, WP22 and WP23 depend on WP21; WP24 (overlays, paint) can run alongside.
3. **Wave 4, setup and staging (WP25 to WP28).** WP25 first; WP26 and WP27 in parallel; WP28 last.
4. **Wave 5, appliance (WP29 to WP33).** WP29 first; WP30, WP31 and WP32 in parallel; WP33 last.
5. **Wave 6 (WP34 to WP39).** WP34 and WP35 on top of Wave 5. WP36 (wgpu compute) is independent and can start any time after Wave 2. WP37 (licensing, tickets) needs the server deployed. WP38 (xtask trace, SOUP) can start early and should, see below. WP39 (packaging) last.

Per wave: one core release, then consumers move to the tag, then the pointer bump here.

## Open items

- **Golden harness (WP12).** Needs a headless run of the old plugin to produce fixtures. Teeth3DS is licensed CC BY-NC-ND: decide whether to use it for fixtures at all or use our own scans. Until decided, keep it out of the repositories (`$DC_TEETH3DS`).
- **Tokens in two places.** `dc-theme` (core, placeholder tokens) and `dc-ui` (app, real tokens) overlap. Consolidate so tokens live in one place, derived from `docs/design/tokens.json`.
REDACTED
- **release-please checks.** Checks do not trigger on PRs opened by `github-actions[bot]`. Merge without them or switch to a PAT.
- **App CI takes about 17 minutes**, mostly runner queue time.
- **App stubs.** News, documentation URLs, ticket list and attachments, evaluation and create-account. The server tickets API returns 501; both sides must land together.
- **Regulatory dossier.** Carry over from the old `docs/regolatorio` to `dentalcraft-app/regulatory` (`requisiti.toml`, `rischi.toml`, `soup.toml`, `anomalie.toml`, `classificazione.md`) and implement `cargo xtask trace --check` to replace `build_trace.py`. Not started.
- **Attachments are not modelled** (old anomaly ANO-001). Decide the data model before WP26 and WP33.

## How to resume

```sh
git clone --recurse-submodules https://github.com/dnviti-personal-org/dentalcraft.git   # or: git submodule update --init --recursive
export PATH="$HOME/.cargo/bin:$PATH"
cd dentalcraft-core && cargo test        # inside the superproject, local [patch] applies
```

Read `CLAUDE.md` for commands, versioning workflow and the `Cargo.lock` rule.

## Known risks

- Geometry ports may miss the golden tolerances (Hausdorff < 0.01 mm, labels >= 99 %); budget time for WP14 and WP18.
- Fixtures depend on a Blender run of the old plugin; keep the oracle repository untouched.
- Release issuer URL and server domain are unconfirmed.
