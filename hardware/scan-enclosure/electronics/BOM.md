# Bill of materials: LED lighting and auto-brightness controller

All parts are through-hole (THT), for hand soldering. Designators match [schematic.png](schematic.png) and
[perfboard-wiring.md](perfboard-wiring.md).

**Prices are indicative** small-quantity prices in EUR, November 2026. They were **not** checked against
live listings. Mouser and DigiKey add minimum-order and shipping costs; AliExpress kits are cheaper per
piece for resistors and capacitors. To source a part, search its MPN at Mouser, DigiKey or LCSC.
"Generic" means any brand with the stated specification.

## Controller board (perfboard 60 × 40 mm)

| ref | value / part | package | qty | example part (MPN) | unit € | total € |
|---|---|---|---|---|---|---|
| U1 | LM358 dual op-amp | DIP-8 | 1 | TI LM358P | 0.25 | 0.25 |
| – | IC socket (optional) | DIP-8 | 1 | generic | 0.08 | 0.08 |
| U2 | 78L05 5 V regulator, 100 mA | TO-92 | 1 | ST L78L05ACZ | 0.15 | 0.15 |
| Q1 | IRF520N N-MOSFET, 100 V 9.7 A, planar | TO-220 | 1 | Infineon IRF520NPBF | 0.60 | 0.60 |
| D1 | 1N5819 Schottky, 1 A 40 V | DO-41 | 1 | onsemi 1N5819RLG (or any 1N5819) | 0.05 | 0.05 |
| D2 | P6KE15A TVS, 15 V, 600 W | DO-15 | 1 | Littelfuse P6KE15A | 0.15 | 0.15 |
| F1 | PTC fuse, 0.75 A hold / 1.5 A trip | radial, 5.1 mm | 1 | Littelfuse RXEF075 | 0.20 | 0.20 |
| R1 | 4.7 kΩ | 1/4 W 1 % metal film | 1 | Yageo MFR-25FBF52-4K7 | 0.02 | 0.02 |
| R2, R4 | 2.2 kΩ | 1/4 W 1 % | 2 | MFR-25FBF52-2K2 | 0.02 | 0.04 |
| R3 | 22 kΩ | 1/4 W 1 % | 1 | MFR-25FBF52-22K | 0.02 | 0.02 |
| R5, R8 | 10 kΩ | 1/4 W 1 % | 2 | MFR-25FBF52-10K | 0.02 | 0.04 |
| R6, R13 | 100 kΩ | 1/4 W 1 % | 2 | MFR-25FBF52-100K | 0.02 | 0.04 |
| R7 | 12 kΩ | 1/4 W 1 % | 1 | MFR-25FBF52-12K | 0.02 | 0.02 |
| R9 | 47 kΩ | 1/4 W 1 % | 1 | MFR-25FBF52-47K | 0.02 | 0.02 |
| R10, R11 | 1 kΩ | 1/4 W 1 % | 2 | MFR-25FBF52-1K | 0.02 | 0.04 |
| R12 | 100 Ω | 1/4 W 1 % | 1 | MFR-25FBF52-100R | 0.02 | 0.02 |
| R14 | 0.47 Ω current sense | 0.5–1 W, 1 % metal film, 0207-size body | 1 | Vishay PR01 series, 0.47 Ω (check the 1 % option), or any 0.47 Ω 1 % ≥ 0.5 W | 0.10 | 0.10 |
| RV2 | 50 kΩ multi-turn trimmer | 3296W, top adjust | 1 | Bourns 3296W-1-503LF | 0.30 | 0.30 |
| C1 | 100 µF 25 V electrolytic | radial 6.3 mm, 2.5 mm pitch | 1 | generic | 0.05 | 0.05 |
| C2, C4, C8 | 100 nF 50 V X7R | radial MLCC, 2.54 mm | 3 | generic | 0.03 | 0.09 |
| C3, C6 | 1 µF 50 V X7R | radial MLCC, 2.54 mm | 2 | generic | 0.05 | 0.10 |
| C5 | 10 µF 16–25 V electrolytic | radial 5 mm, 2 mm pitch | 1 | generic | 0.04 | 0.04 |
| C7 | **1 µF 63 V polyester film (MKT)**; not electrolytic, not ceramic | 5 mm pitch | 1 | WIMA MKS2 series 1 µF 63 V, or generic MKT | 0.20 | 0.20 |
| C9 | 10 nF 50 V | radial MLCC | 1 | generic | 0.03 | 0.03 |
| J1, J2, J3 | screw terminal 2-pole | 5.08 mm, KF301-2P | 3 | generic | 0.08 | 0.24 |
| – | perfboard, cut to 60 × 40 mm (from a 50 × 70 board) | FR4 0.1" | 1 | generic | 0.30 | 0.30 |
| – | tinned copper wire 0.6 mm, insulated hook-up wire for 3 jumpers | | – | generic | 0.10 | 0.10 |
| | | | | | **board** | **3.29** |

## Panel and off-board parts

| ref | value / part | qty | example part | unit € | total € |
|---|---|---|---|---|---|
| PH1 | ambient light sensor, phototransistor, 5 mm | 1 | Vishay TEPT5700 | 0.40 | 0.40 |
| RV1 | 10 kΩ linear pot, 16 mm, M7 bushing, 6 mm shaft | 1 | generic WH148 B10K | 0.40 | 0.40 |
| – | knob for 6 mm shaft (≤ Ø22) | 1 | generic | 0.20 | 0.20 |
| SW1 | mini toggle SPDT ON-ON, M6 bushing | 1 | generic MTS-102 | 0.30 | 0.30 |
| D3 | LED 3 mm green | 1 | generic | 0.03 | 0.03 |
| JK1 | DC jack 5.5 × 2.1 mm, panel mount | 1 | generic DC-022B | 0.30 | 0.30 |
| – | 2-core wire AWG22, red/black, 2 m (strip harness, panel) + 0.6 m 2-core for the sensor | 1 | generic | 1.00 | 1.00 |
| – | heat-shrink assortment (sensor leads, LED) | – | generic | 0.10 | 0.10 |
| | | | | **controller total** | **6.02** |

## Lighting and supply

| item | qty | example | unit € | total € |
|---|---|---|---|---|
| LED strip FCOB 12 V, 480 LED/m, 8 mm, 4000 K, Ra > 90, 1 m (0.55 m used: 22 × 25 mm) | 1 | BTF-LIGHTING "FCOB 336/480/528 LEDs/m", option 4000K / 12v 480 leds / 1m (listed at about $6.99) | 7.00 | 7.00 |
| power adapter 12 V ≥ 1 A, 5.5 × 2.1 mm, centre positive (separate from the turntable's) | 1 | generic | 5.00 | 5.00 |
| diffuser covers, natural PETG, about 15 g printed | – | any natural/clear PETG | 0.40 | 0.40 |
| M3 × 6 screws + M3 heat-set inserts for the board on the bay standoffs | 4 + 4 | generic | 0.10 | 0.40 |
| | | | **lighting + supply** | **12.80** |

## Total

| block | € |
|---|---|
| controller board | 3.29 |
| panel and off-board | 2.73 |
| LED strip, adapter, covers, fasteners | 12.80 |
| **total** | **≈ 18.80** |

The adapter and the strip are two thirds of the cost. Without a microcontroller, the electronics cost
about €6.
