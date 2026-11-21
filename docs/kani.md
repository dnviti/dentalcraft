# Formal verification with Kani

[Kani](https://github.com/model-checking/kani) is a bounded model checker for Rust. A proof harness
takes symbolic inputs (`kani::any()`), and Kani checks every value they can take, within the bounds
the harness sets. It reports either a pass or a concrete counterexample. Besides the `assert!`s in
the harness, it also checks every panic, overflow, out-of-bounds index and `unwrap` it reaches.

Kani is a local gate, separate from CI: `scripts/ci-local.sh` stays an exact replica of the runner
workflows, and the runner never runs Kani.

## Install (once per machine)

```sh
cargo install --locked kani-verifier
cargo kani setup        # ~/.kani bundle and its pinned nightly toolchain, about 2 GB
```

Kani 0.68.0 is installed on the workstation (2026-11-17). Kani uses its own compiler and nightly
toolchain and ignores the `rust-toolchain.toml` of each repo; plain cargo builds still use 1.99.1.

To uninstall: `cargo uninstall kani-verifier; rm -rf ~/.kani; rustup toolchain uninstall nightly-2026-08-21`.

## Run

```sh
scripts/kani-local.sh <core|aligners|app|all> [--ref <git-ref>] [--dev] [-- <cargo kani args>]
```

- The default verifies a committed ref. Like `ci-local.sh`, it uses a clean checkout under
  `~/.cache/dentalcraft-ci/<repo>/src` and the dependencies from the pinned tags.
  - A pass writes `~/.cache/dentalcraft-ci/<repo>/kani-passed/<sha>`.
- `--dev` verifies the working tree inside the superproject, with the `[patch]`. It restores
  `Cargo.lock` afterwards. Use it while writing harnesses.
- `-- --harness <name>` runs a single harness. For a failure,
  `-- --harness <name> -Z concrete-playback --concrete-playback=print` prints the failing inputs.
- Every run is capped at `DC_KANI_MEM` (default `16G`, no swap) through
  `systemd-run --user --scope`. CBMC once used 44 GB on a badly bounded harness.
- Each workspace sets `[workspace.metadata.kani]` with `flags = { ignore-global-asm = true }` and
  `unstable-options`. This is needed because kiddo pulls in `generator`, which contains global
  asm; no harness reaches that code. Core also enables `stubbing`, so `#[kani::stub]` works with
  a plain `cargo kani`.

## Writing harnesses

- Harnesses live in a `#[cfg(kani)] mod kani_proofs { ... }` module, in the file of the code under
  proof. Normal builds, clippy and tests never compile them.
- Every crate that holds harnesses declares the cfg, otherwise clippy `-D warnings` fails on the
  runner:

  ```toml
  [lints.rust]
  unexpected_cfgs = { level = "warn", check-cfg = ['cfg(kani)'] }
  ```

  In a crate with `[lints] workspace = true`, add the entry under `[workspace.lints.rust]` instead.
- Keep the inputs small and bounded. Good inputs:
  - small integers;
  - enums that derive or implement `kani::Arbitrary`;
  - fixed-size arrays;
  - vectors of concrete length, or built at the maximum length and then truncated.
- Set `#[kani::unwind(N)]` to just above the largest loop bound.
- Prove pure logic, not I/O. These did not finish or are not supported here, so harness the
  small pure helper they call, or use proptest:
  - vectors grown to a symbolic length (also inside the function under test) and std's stable
    `sort`;
  - `HashMap` and `HashSet`, whose random-key `syscall` Kani does not support (rules out
    `UndoStack` and `StepHistory`);
  - `format!` and string splitting;
  - lengths read back from bytes (DCM1 `decode`);
  - maps of boxed closures;
  - the whole `AlignersState`;
  - ZIP, BLAKE3, serde_json and egui.
- Floats are fine for bit conversions and sign laws. Use discrete value sets (for example unit
  quaternions) rather than arbitrary `f64` for arithmetic.
- One property per harness, named after the property (`mirror_is_valid_involution`). Each
  harness starts with a comment that states the law in plain words.
- A failing harness on a real defect is a bug report: fix the code. Never weaken the property.
  Narrow the bounds only when Kani does not finish, and write down why.

## Current harnesses

| Repo | Crate | Harness | Law |
|---|---|---|---|
| core | dc-case `fdi.rs` | `new_accepts_exactly_iso_numbers` | For all 256 `u8`: `Fdi::new` accepts exactly 11–48 and 51–85 |
| core | dc-case `fdi.rs` | `mirror_is_valid_involution` | The mirror is a different valid tooth; mirroring twice gives the original |
| core | dc-case `fdi.rs` | `mirror_keeps_arch_and_flips_side` | Mirroring keeps upper/lower, permanent/deciduous and position, and flips the side |
| core | dc-case `fdi.rs` | `permanent_arch_is_the_16_teeth_of_the_arch` | 16 distinct valid permanent teeth of the requested arch |
| core | dc-geom `sdf/store.rs` | `pack_round_trips_in_range` | `unpack(pack(b)) == b` within ±2^20 |
| core | dc-geom `sdf/store.rs` | `pack_orders_by_z_then_y_then_x` | Packed key order is z, y, x (packing is injective) |
| core | dc-geom `sdf/store.rs` | `voxel_splits_into_block_and_local_index` | `local_of(g) < 512` and block × 8 + local == g for any `i32` |
| core | dc-geom `sdf/store.rs` | `local_index_round_trips` | `local_of(local_coord(i)) == i` |
| core | dc-geom `sdf/store.rs` | `inside_is_always_negative` | `signed(d, true) < 0` for every `f32`, NaN included |
| core | dc-geom `mc.rs` | `pack_round_trips_in_range` | `unpack(pack(b)) == b` within ±2^20 |
| core | dc-geom `mc.rs` | `pack_orders_by_x_then_y_then_z` | Packed key order is x, y, z |
| core | dc-geom `mc.rs` | `voxel_splits_into_block_and_local_index` | Same, with Euclidean division |
| core | dc-geom `mc.rs` | `local_index_round_trips` | `local_of(local_coord(i)) == i` |
| core | dc-geom `qem.rs` | `entry_pack_round_trips` | Unpacking returns the packed queue entry |
| core | dc-geom `qem.rs` | `entry_pack_orders_by_cost_then_fields` | `u128` order equals (cost, a, b, stamps, placement) order |
| core | dc-geom `qem.rs` | `key_cost_is_a_valid_queue_key` | Any `f64` gives a finite cost ≥ 0 with the sign bit clear |
| core | dc-geom `sdf/flood.rs` | `domain_index_then_block_is_identity` | `index` is Some exactly inside the box, below the cell count, and `block` inverts it |
| core | dc-geom `sdf/flood.rs` | `domain_block_then_index_is_identity` | `index(block(c)) == Some(c)` |
| core | dc-project `codec.rs` | `load_refuses_newer_schema` | A module state newer than the code is refused, for every `u32` |
| aligners | dca-algo `schedule.rs` | `days_in_month_is_a_month_length` | Months have 28–31 days; February has 29 exactly in leap years |
| aligners | dca-algo `schedule.rs` | `date_days_roundtrip` | `from_days(d.days()) == d` for every valid date, years −10000..10000 |
| aligners | dca-algo `schedule.rs` | `from_days_gives_a_valid_date` | Any day count in range gives a valid date that maps back to it |
| aligners | dca-algo `schedule.rs` | `add_days_moves_by_n` | `add_days(n)` moves the day count by exactly n, \|n\| ≤ 100 000 |
| aligners | dca-algo `schedule.rs` | `run_rows_follow_each_other` | Interval 5..=21, any offset: no overflow, one row per aligner, rows back to back, total = sum |
| aligners | dca-algo `schedule.rs` | `next_visit_is_the_day_after_a_row` | No panic; empty calendar gives `None` |
| aligners | dca-algo `schedule.rs` | `day_of_stage_stays_in_its_row` | No panic for any `f64` (NaN, ±inf); stage k falls inside row k |
| aligners | dca-algo `anatomy.rs` | `slot_is_inside_the_table` | A table index is always inside its table |
| aligners | dca-algo `anatomy.rs` | `the_tables_answer_every_tooth` | No panic and positive values for every valid tooth, deciduous included |
| aligners | dca-algo `anatomy.rs` | `mesial_and_distal_neighbours_are_symmetric` | On any subset of an arch, mesial and distal neighbours mirror each other (except across the midline) |
| aligners | dca-algo `rotation.rs` | `canonical_takes_the_short_way` | Canonical quaternion has w ≥ 0 (no 360° spin); result is q or −q. Discrete unit quaternions |
| aligners | dca-model `state.rs` | `every_tooth_is_in_exactly_one_arch` | Every valid tooth is in exactly one of Upper and Lower, never Bite |
| aligners | dca-model `state.rs` | `set_arch_seeds_reports_a_change_iff_the_seeds_differ` | "Changed" is true exactly when old and new seeds differ as multisets |
| aligners | dca-model `print.rs` | `printed_only_by_the_user_or_the_printer` | An aligner becomes printed only by the user's confirmation (from any status but printed) or by the printer's report on a job it was sent; the app alone never marks one printed |
| aligners | dca-model `print.rs` | `a_printed_aligner_leaves_only_for_a_reprint_by_the_user` | A printed aligner leaves printed only when the user asks to print it again |
| app | dc-workspace `timeline.rs` | `week_never_overflows` | `week` is exact, or `u32::MAX` when it does not fit |
| app | dc-workspace `timeline.rs` | `step_stays_in_the_timeline` | For \|delta\| ≤ 5: stays in 0..=last, moves at most \|delta\|, no overflow |
| app | dc-workspace `timeline.rs` | `tick_stops_at_the_last_stage` | Playback never passes the last stage and never overflows |
| app | dc-ui `pacing.rs` | `frames_never_come_faster_than_the_cap` | A frame starts at least 1/60 s after the previous one (at most 60 fps); the wait is never longer than one interval |

## Known open findings

- **DCM1 save then reopen** (core, `dc-mesh` `dcm.rs`, `dc-project` `write.rs`): `encode` accepts
  attribute arrays of the wrong length, and the save path never calls `TriMesh::check`. Example: 1
  vertex, `normals = Some([])` and 7 labels saves, then reopens as a different mesh with an
  invented normal. 2 vertices with 1 label saves, then fails on open. Not fixed: the fix changes
  save behaviour, so it needs the user's decision. The Kani harness did not finish (lengths read
  from bytes); use proptest.
- **`set_arch_seeds` accepts seeds of the other arch** (aligners, `dca-model` `state.rs`). No
  current caller passes them, because all five filter first.
- **`Date::from_days` overflows** near the `i64` limits. No caller comes close.
- **Not reachable with Kani, needs proptest:** `UndoStack` and `StepHistory` (`HashMap`
  syscall), the `ModuleCodec` migration chain, `valid_module_id`, `clear_arch`,
  `numbering_sequence`, and the JSON round trip of `AlignersState`.
- **GOO run round trip** (core, `dc-print` `goo/rle.rs`): one run of any length 1..=`MAX_RUN`
  and any value encodes and decodes to itself. The Kani harness did not finish (still running
  after 17 minutes at 3.6 GB; split by the number of length bytes, just as slow): the encoder's
  flush loop and the chunk byte loop are unrolled over a buffer of symbolic length, as in the
  DCM1 decode. Sampled by the proptest `any_run_round_trips`; the unit test
  `every_length_class_uses_the_fewest_bytes` covers the edges of every length class.
