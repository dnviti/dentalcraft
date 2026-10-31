# 0001. Full rewrite in Rust

- Status: accepted
- Date: 2026-10-31
- Deciders: Daniele Viti

## Context and problem statement

The first implementation of the aligner workflow is a Blender add-on (Python, `blender-ortho-aligner`). It proved the algorithms, but Blender sets hard limits on the product:

- the user interface, undo system and data model belong to Blender, so a clinical workflow with its own case model, step history and audit trail has to fight the host;
- Python and `bpy` make heavy geometry work (ICP, decimation, SDF, sparse solves) slow and hard to parallelize, and the code cannot be tested without a Blender runtime;
- distributing a regulated medical-device software that embeds a general-purpose 3D suite complicates the SOUP list, packaging, licensing and the regulatory dossier;
- there is no clean way to ship dental modules as separately licensed units.

## Considered options

1. Keep the Blender add-on and improve it.
2. Rust core exposed to Python through a PyO3 bridge, UI still in Blender.
3. Full rewrite as a standalone Rust application, with the old add-on kept as a read-only oracle.

## Decision

Option 3: DentalCraft is rewritten entirely in Rust, with no PyO3 bridge. The project format is `.dcprj`. The code is split in separate private repositories (engine, aligners module, application, Go backend) gathered by this superproject.

## Consequences

- Good: headless, GPU-free core that runs in CI; one language for engine, module and application; a small, auditable dependency set; native undo and project format designed for traceability.
- Good: modules depend only on the core, so further dental modules can be added and licensed independently.
- Bad: every Blender feature used so far (viewport, file import, UI widgets) has to be rebuilt or replaced.
- Bad: no C++ toolchain on the build machines, so dependencies are limited to pure-Rust crates (rustls with `ring`, not `aws-lc`).
- The old add-on stays untouched as a behavioural reference to validate the Rust algorithms against.

See [`docs/plan/PLAN.md`](../plan/PLAN.md) and [`docs/plan/DECISIONS.md`](../plan/DECISIONS.md).
