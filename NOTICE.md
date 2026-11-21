# Notice

Required Notice: Copyright (c) Daniele Viti

## Licence

The content of this repository (documentation, design files, hardware designs, scripts) is source-available under the PolyForm Noncommercial License 1.0.0. The full text is in `LICENSE.md`. The same licence applies to the code repositories this repository gathers: `dentalcraft-core`, `dentalcraft-aligners`, `dentalcraft-app` and `dentalcraft-web`.

You may use, change and share it for any noncommercial purpose. Commercial use is not allowed. This is not an open source licence in the OSI sense.

## Commercial licensing

For commercial use, contact the author, Daniele Viti: hello@dentalcraft.app.

## Closed component

The sign-in server `dentalcraft-server` is closed source, lives in a private repository and is not covered by this licence. It is not part of this repository.

## Origin of the algorithms

The aligner algorithms of DentalCraft are a port of the Blender add-on `blender-ortho-aligner`, which the author wrote alone. That add-on was published under GPL-3.0-or-later. As its only copyright holder, the author relicenses the Rust port under the terms above. The add-on itself is a separate, private repository and is not part of DentalCraft.

## Not a medical device

DentalCraft is not a certified medical device. It has no regulatory clearance. Do not use it on patients or for clinical decisions without independent professional validation. It is provided as is, without warranty.

## Third-party material

- This repository does not copy third-party source code. The scripts under `scripts/` and `hardware/` use tools such as Python, NumPy, OrcaSlicer and the Rust and Go toolchains, which stay under their own licences and are not redistributed here.
- The scientific, technical and standards sources behind the algorithms, the scanner and turntable protocols and the print file formats are listed in [`SOURCES.md`](SOURCES.md).
- The dependencies of each code repository are listed in `NOTICE.md` of that repository and, for the application, in `THIRD-PARTY-NOTICES.md` of `dentalcraft-app`.
- Revopoint, Elegoo, 3Shape, Align Technology (iTero), Dentsply Sirona, Blender and the other product names are trademarks of their owners. They are used only to state compatibility or to cite a source. DentalCraft is not affiliated with or endorsed by them.
- Teeth3DS+ (CC BY-NC-ND 4.0) is used for validation only and is never part of any repository.
