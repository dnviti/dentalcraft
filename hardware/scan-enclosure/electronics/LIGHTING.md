# Lighting for 3D scanning in the scan enclosure

Controlled LED lighting for the enclosure: diffuse LED strips behind printed opal covers, and an
analog closed loop (no microcontroller) that holds the light at the model at a chosen level.
The circuit, its calculations and its simulation are in [DESIGN.md](DESIGN.md); parts in [BOM.md](BOM.md);
build and calibration in [ASSEMBLY.md](ASSEMBLY.md).

Geometry is the default enclosure from `../src/params.py`. Inside: X ±117 mm, Y -120 (open front) to
273, Z 8.5 (base) to 319 (roof). The scanner looks from +Y towards the open front: 190 mm from the aim
point T = (0, 0, 105.2), 40° down. All light numbers come from `sim/photometry.py`.

## 1. What light helps and what hurts

The Revopoint MINI 2 builds depth from a blue structured-light projector and stereo depth cameras, and
takes texture with an RGB camera (MJPG 1600×1200, up to 30 fps). Depth is computed on the device at
about 3–10 fps. Exposure is automatic.

| factor | effect on depth | effect on texture | choice |
|---|---|---|---|
| ambient level vs projector | ambient light fills the dark parts of the projected pattern, lowering its contrast; more noise and holes | more light: shorter exposure, less noise | **dimmable**: low for geometry-only scans, higher for texture; the knob is the trade-off |
| blue content (white LEDs have a 440–455 nm pump peak, right in the projector band) | the most harmful part of the ambient | needed for colour | **4000 K**: less blue than 5000–6500 K with neutral white for texture |
| colour rendering | none | dental stone, resin and gums need a full spectrum (R9 red) | **CRI (Ra) > 90** |
| infrared (incandescent, halogen, sunlight) | IR-sensitive depth sensors see it as ambient; heat | none (IR-cut on the RGB camera) | **LEDs only** (no emission above about 750 nm); keep sunlight and halogen lamps off the open front |
| specular hotspots on glossy stone/resin | saturated pixels become holes | white blotches | **large, low-luminance diffusers away from the camera axis**; matte scanning spray stays the fallback for very glossy prints |
| flicker | auto-exposure hunting, unstable pattern contrast | banding, frame-to-frame brightness steps | **DC current, no PWM** (section 2) |

The walls are matte black. They reflect almost nothing, so only the direct light from the diffusers
counts, and the geometry below sets it.

## 2. Flicker: PWM or analog

The RGB camera runs at up to 30 fps (frame time 33 ms) with automatic exposure. The depth cameras also
expose automatically, and the projector modulates its own light.

| method | what the camera sees | cost |
|---|---|---|
| low-frequency PWM (100 Hz – 2 kHz, cheap dimmers) | a rolling shutter turns on/off light into horizontal **bands**; a beat between the PWM and the 30 fps frame rate makes frames pulse; auto-exposure chases it | cheap, but unusable for scanning |
| PWM ≥ 20–25 kHz | invisible at long exposures. With a bright scene the exposure gets short (100 µs = 2.5 periods at 25 kHz), and banding of up to about 20 % comes back exactly when light is abundant | triangle generator + comparator + gate driver; fast edges on 0.6 m of strip wire run next to the scanner's USB cable (EMI) |
| **analog constant current (linear)** | **DC: no modulation at all** | the MOSFET drops the excess voltage as heat (0.45 W worst case, computed); white-LED colour shifts slightly with current (tens of K) |

**Chosen: analog constant-current dimming.** It is the only option with no flicker for any exposure time.
At 12 V with 12 V strips the extra heat is small: the simulated worst case is 0.45 W in a TO-220 MOSFET
with no heatsink. The only ripple left on the LED current comes from the light loop reacting to 100 Hz
room-light flicker. Simulated, it is **0.017 % peak-peak**, far below what a camera can see.

## 3. LED strips

**BTF-LIGHTING FCOB, 12 V, 480 LED/m, 8 mm FPC, 4000 K (natural white), Ra > 90, IP30** (variant
"4000K Natural White / 12v 480 leds / 1m",
<https://www.btf-lighting.com/products/fcob-dimmable-led-strip-336-480-528-leds>).
Datasheet: 11 W/m max, 928–1114 lm/m (8 mm, 12 V), can be cut every 25 mm. COB has no LED dots, so even a small
gap gives a smooth line.
An SMD alternative that fits the same channel: 2835, 120 LED/m, 12 V, 8 mm, Ra ≥ 90, 4000 K. It also cuts
every 25 mm (3 LEDs), and the 8 mm gap is about its 8.3 mm LED pitch.

| run | where | strip | channel (centre line) |
|---|---|---|---|
| roof_left | roof_front underside, X = -90, facing down | 150 mm (6 cuts), Y -90..+60 | Y -95..+65 (3 mm clear of the Y = 72 seam flange) |
| roof_right | same at X = +90 | 150 mm | same |
| wall_left | -X upper rear side panel, Y = 95, facing +X | 125 mm (5 cuts), Z 175..300 | Z 170..305 |
| wall_right | +X upper rear side panel, Y = 95, facing -X | 125 mm | Z 170..305 |
| **total** | | **550 mm = 22 cuts** (one 1 m reel) | |

- **Electrical.** Rated 0.50 A / 6.1 W at 12.0 V across the strip. With the controller's drops (PTC, Schottky
  diode, sense resistor, MOSFET; 0.75 V in total) a 12.0 V adapter reaches at most **0.38 A (4.6 W)**. The
  controller can never drive the strip above its rating: the current command tops out at 0.45 A.
- **Light at full power** (12.0 V, 0.38 A, diffuser 0.55, `sim/loop_sim.py`): about **425 lx on the
  camera-side faces** of the model (the mean of up, towards the camera and sideways) and **925 lx on the
  top faces**. The knob sets anything from 0 to that.
- **Uniformity** over a D100 model: top faces min/max 0.72; vertical faces turned towards the camera
  min/max 0.89.
- **More light, if needed:** BTF 528 LED/m (12 W/m, 10 mm FPC, 1157–1398 lm/m, cut 22.5 mm; still
  fits the 16 mm channel) gives about +25 %. A 12.5–12.6 V adapter gives about +15 %.

### Supply: separate 12 V adapter, not the turntable's

Use a separate **12 V ≥ 1 A, 5.5×2.1 mm, centre-positive** adapter. Do not share the turntable's 12 V/2 A one:

1. Revopoint sizes that adapter for the turntable. Two stepper motors with holding current leave no
   documented margin for another 0.4 A.
2. Motor current steps make the shared rail sag at every step. The current regulator rejects ripple only
   while it has headroom, and at high brightness it has none: the dips would go straight into the light,
   in sync with the scan.
3. A shared DC return carries motor current through the scanner's USB ground reference.
4. A fault in the lighting (a pinched strip wire, for example) would stop the turntable halfway through a scan.

A second adapter costs about €5.

### Placement: why camera side and overhead

The camera sees the faces of the model that point up and towards +Y. Lights near the open front would light only the faces turned away
from the camera (a first layout did exactly that; the photometry caught it). Hence:

- **Roof runs at X = ±90.** They light occlusal and top faces from both sides. From T they are about 65° up and
  90° to the side of the camera plane.
- **Wall runs at Y = 95.** These are the key lights: they hit the faces turned towards the camera at about ±48°
  from its direction. That is far enough off-axis that head-on reflections of a large diffuser do not go
  straight back into the lens.
- **No light near the optical axis.** A source behind or above the camera makes glare on every surface facing
  the camera.
- **Out of view:** no channel is inside the camera/projector view cone, for elevation 30–50° and distance
  175–205 mm with a 3° margin (`sim/photometry.py` prints the check). The scanner looks down; the roof and
  side walls are outside its field.
- **Lens shading:** the wall channels have an 8 mm visor on their +Y (scanner) side, so no diffuser surface
  faces the scanner's front glass at a grazing angle.

## 4. Diffuser channel (for the CAD)

```
      cover 17.7 x 1.2, natural PETG, slides in from one end
      ┌────────────────────────────┐   ← lip 1.2
  ════╡▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓╞════ ← groove 1.4 high x 1.0 deep, lower edge 10.0 above skin
      │                            │
      │        gap 8.0             │      inner width 16.0
      │                            │      walls 1.6, wall height 12.6, outer width 19.2
      │     ┌──────────────┐       │
──────┴─────┤ strip 8 x ~2 ├───────┴────── roof / wall skin (strip stuck on the skin)
```

| item | value |
|---|---|
| strip | 8.0 mm FPC, about 2 mm thick with its tape, centred on the skin |
| inner width | 16.0 mm: the emitting band is twice the strip width, so its luminance is about half that of a bare-fitting diffuser and specular highlights are softer |
| strip-to-cover gap | 8.0 mm. Rule: gap ≥ LED pitch (COB 2.1 mm; 2835 SMD 8.3 mm), so either strip type gives an even line |
| cover | 17.7 wide × 1.2 thick × (channel length − 1), slides into 1.4 × 1.0 mm grooves (0.2 mm fit) |
| channel length | strip length + 10 mm. One end is open for the cover; the other is closed, and its end wall has a Ø3 wire hole 1.5 mm above the skin (holes rather than notches, so the edges can be rounded). Roof runs are open at the front (Y −95), closed at the rear. Wall runs are closed at the bottom, so the cover cannot slide out, and open at the top: insert the cover before the roof goes on. |
| visor | wall runs only: +Y wall extends 8 mm past the cover face |

**Diffuser material.** Use a printed **natural (uncoloured) PETG** cover:

- **Transmission:** about 50–65 % at 1.2 mm. This is an estimate, not measured; the simulation uses 0.55.
- **How it diffuses:** the internal layer and line boundaries scatter the light into a milky, even glow.
- **Opaque white PETG/PLA:** stops too much light at 1.2 mm (estimate 20–35 %). If only white is at hand, print the cover 0.8 mm thick.

Print settings (Centauri Carbon 2, 0.4 mm nozzle):

- Lay the cover flat on the textured PEI plate. The matte textured face goes **towards the model**, the smooth face towards the strip.
- 0.20 mm layers, 6 layers for 1.2 mm, 100 % rectilinear infill with lines along the length, 2 perimeters.
- No ironing, fan 30–50 %, 240 °C nozzle / 80 °C bed, about 60 mm/s.
- Before printing all four covers, print one 50 mm sample. Measure it over a lit strip with a phone lux app, cover against no cover.

**Heat.** At full current (0.39 A on 0.55 m, about 7 W/m in the channel) the strip warms the skin it
sits on.

- **PETG parts** (glass transition about 80 °C) can carry the channels.
- **PLA parts** (about 60 °C) are fine at the typical 30–60 % but not for hours at full power.

For long full-power use, mount the strip on an aluminium U-profile instead. A 17 × 7 mm profile with an
opal PC cover (about 60 % transmission) is about €2–3 per metre on AliExpress; the channel then holds the
profile instead of the strip.

## 5. Light sensor placement

The sensor is a **Vishay TEPT5700** phototransistor with a response matched to the human eye. It sits
on the inside of the -X upper front side piece, above everything the turntable can sweep:

- **Position and aim:** dome tip at (-110, -40, 180), facing up, axis tilted 10° towards the open front.
- **Collar:** a flat Ø16 collar, 0.5 mm below the dome tip, hides everything more than atan(0.5/8) = 3.6°
  below the tip plane.
- **Clearance:** the platter (r 100, rim down to Z 80) and a D100 × 60 model, at any rotation and tilt
  from −30° to +30°, stay at least **10.9° below** the tip plane: a 7.3° margin (`clearance()` in
  `sim/photometry.py`). The model top reaches Z 161 at full tilt; the tip is at Z 180.
- **Out of view:** outside the camera and projector view at every elevation and distance.

An earlier spec, with the tip at (-110, 40, 135) and a Ø12 collar 1 mm down, failed this check: the tip
sat lower than the model top, so the sensor saw the platter rim and the model (found by the CAD
validation).

Why there and why facing up:

- **It measures the light falling at the model, not the light reflected by the model.** A sensor looking at
  the model would follow the model's colour and shape as the turntable turns. It would also see the
  projector's flashes (3–10 Hz). Either way the loop would change the brightness during a scan.
- **It sees the diffusers, never a bare LED** (every LED is behind a cover). Since all four runs are on one
  driver, how much each run contributes to the sensor does not matter. What matters is the ratio of room
  light to LED light at the sensor, compared with the same ratio at the model.
- **Result:** the loop cancels **98 %** of a room-light change at the model (65–148 % if the sensor axis is
  off by ±10°; above 100 % the model gets slightly darker when the room gets brighter). The simulation
  agrees: a ceiling light that adds 73 lx at the model in MANUAL adds only 2 lx in AUTO (97 % cancelled). Room light
  reaches mostly the faces turned away from the camera, so the image changes even less.

Mount geometry for the CAD:

- **Holder bore:** Ø5.2, with a Ø6.0 × 1.5 counterbore for the flange, both from below. The sensor goes in from below and is held by a drop of glue.
- **Collar:** Ø16, its top face 0.5 mm below the dome tip.
- **Leads:** the holder is open at the bottom, with no floor and no wall hole. The 2-wire lead drops down the inside of the −X wall at Y ≈ −40 into the strip-harness clips at Y −50, down to the Z 30 cable guide, and along it to the electronics bay on `base_rear`.

## 6. Alternative: a microcontroller (Arduino) — evaluated, not chosen

An MCU (Arduino Nano or ESP32-C3) reading the same sensor would allow:

- software control from DentalCraft over USB, for example lighting presets per scan mode (low for geometry, higher for texture), set by the `scan.*` commands and saved with the project;
- logging of the light level next to each frame;
- a scripted calibration.

It would also bring firmware to write, sign and keep up to date, and a second USB device to enumerate next
to the scanner. The MCU also needs a PWM-to-DC stage (or ≥ 25 kHz PWM, with the banding and EMI problems
above) to keep the light flicker-free.

**Decision:** the analog loop does the one job that matters, steady light with no flicker, with no software
and a lower cost. A DentalCraft-controlled version can be added later by replacing the knob voltage
(VSET) with a filtered MCU output; the rest of the circuit stays.

| | analog loop (chosen) | Arduino/ESP32 version |
|---|---|---|
| parts cost (controller only) | about €3.50 | about €7–10 (clone board + RC/DAC stage) |
| flicker | none (DC) | none only with a DC stage; PWM ≥ 25 kHz risks banding at short exposures |
| control from DentalCraft | no (knob) | yes (USB serial, CLI/MCP command) |
| presets, logging | no | yes |
| firmware / maintenance | none | firmware, flashing, USB device handling |
| failure modes | analog drift (calibrated once) | software bugs, USB disconnects |
| build effort | perfboard, 34 parts | perfboard + board + firmware |
