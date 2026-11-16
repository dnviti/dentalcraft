"""Schematic of the MCU-less LED auto-brightness controller, drawn with schemdraw.

Writes ../schematic.svg and ../schematic.png.  Run: python schematic.py  (schemdraw, matplotlib)
"""
import os

import schemdraw
import schemdraw.elements as elm

schemdraw.use("matplotlib")
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
GREY = "#555555"


def gnd(d, xy):
    d += elm.Ground().at(xy)


def rail(d, xy, name):
    d += elm.Vdd().at(xy).label(name, fontsize=9)


def wire(d, a, b, shape="-"):
    d += elm.Wire(shape).at(a).to(b)


def dot(d, xy, open_=False):
    d += elm.Dot(open=open_).at(xy)


def text(d, xy, s, size=9, color="black", halign="left", valign="center"):
    d += elm.Label().at(xy).label(s, fontsize=size, color=color, halign=halign, valign=valign)


def box(d, x0, y0, x1, y1, title=None, ls="--", color=GREY):
    for a, b in (((x0, y0), (x1, y0)), ((x1, y0), (x1, y1)), ((x1, y1), (x0, y1)), ((x0, y1), (x0, y0))):
        d += elm.Line().at(a).to(b).linestyle(ls).color(color).linewidth(0.8)
    if title:
        text(d, (x0 + 0.2, y1 - 0.45), title, size=9, color=color)


def draw():
    d = schemdraw.Drawing(show=False)
    d.config(unit=2.5, fontsize=9, lw=1.1)

    # ------------------------------------------------------------------ power input
    box(d, -1.5, 15.2, 21.5, 27.2, "POWER INPUT AND PROTECTION")
    Y = 25.0
    dot(d, (0, Y), True)
    text(d, (-0.3, Y + 0.55), "J1-1", 8, halign="right")
    dot(d, (0, 17.5), True)
    text(d, (-0.3, 17.0), "J1-2", 8, halign="right")
    text(d, (-1.2, 21.3), "J1: from JK1\nDC-022B 5.5x2.1\npanel jack,\ncentre +\n12 V >= 1 A\nadapter", 7.5, GREY)
    gnd(d, (0, 17.5))
    d += elm.Fuse().at((0, Y)).right().length(3).label("F1\nRXEF075\nPTC 0.75 A hold", fontsize=8)
    d += elm.Schottky().right().length(3).label("D1  1N5819", fontsize=8).label("reverse polarity", loc="bottom", fontsize=7)
    dot(d, (6, Y))
    text(d, (6.1, Y + 0.6), "+12V", 9)
    wire(d, (6, Y), (13.5, Y))
    d += elm.DiodeTVS().at((6, Y)).down().length(3.5).reverse().label("D2\nP6KE15A\nTVS 15 V", loc="bottom", fontsize=8)
    gnd(d, (6, Y - 3.5))
    dot(d, (8.5, Y))
    d += elm.Capacitor(polar=True).at((8.5, Y)).down().length(3.5).label("C1\n100u\n25 V", loc="bottom", fontsize=8)
    gnd(d, (8.5, Y - 3.5))
    dot(d, (11, Y))
    d += elm.Resistor().at((11, Y)).down().length(2.5).label("R1\n4k7", loc="bottom", fontsize=8)
    d += elm.LED().down().length(2.5).label("D3 green\n3 mm\n(panel)\npower on", loc="bottom", fontsize=8)
    gnd(d, (11, Y - 5))
    dot(d, (13.5, Y))
    d += elm.Capacitor().at((13.5, Y)).down().length(3.5).label("C2\n100n", loc="bottom", fontsize=8)
    gnd(d, (13.5, Y - 3.5))
    reg = elm.VoltageRegulator().at((15, Y)).anchor("in").right().label("U2\n78L05", loc="top", fontsize=8)
    d += reg
    wire(d, (13.5, Y), reg.absanchors["in"])
    gnd(d, reg.absanchors["gnd"])
    outp = reg.absanchors["out"]
    wire(d, outp, (outp[0] + 1.6, outp[1]))
    p5 = (outp[0] + 1.6, outp[1])
    dot(d, p5)
    d += elm.Capacitor().at(p5).down().length(3.5).label("C3\n1u", loc="bottom", fontsize=8)
    gnd(d, (p5[0], p5[1] - 3.5))
    wire(d, p5, (p5[0], p5[1] + 1.0))
    rail(d, (p5[0], p5[1] + 1.0), "+5V")
    wire(d, (13.5, Y), (15, Y))

    # op-amp supply
    box(d, 22.5, 15.2, 30.5, 27.2, "U1 SUPPLY (LM358, DIP-8)")
    rail(d, (24, 25.5), "+12V")
    wire(d, (24, 25.5), (24, 24))
    dot(d, (24, 24))
    wire(d, (24, 24), (27, 24))
    text(d, (27.1, 24), "U1 pin 8 (V+)", 8)
    d += elm.Capacitor().at((24, 24)).down().length(3).label("C4\n100n\nat pin 8", loc="bottom", fontsize=8)
    gnd(d, (24, 21))
    wire(d, (27, 19.5), (27, 18.5))
    text(d, (27.1, 20.0), "U1 pin 4 (V-)", 8)
    gnd(d, (27, 18.5))

    # ------------------------------------------------------------------ setpoint
    box(d, -1.5, 2.8, 9.8, 14.4, "SETPOINT / MANUAL LEVEL")
    rail(d, (0.5, 12.7), "+5V")
    d += elm.Resistor().at((0.5, 12.7)).down().length(2.0).label("R2\n2k2", fontsize=8)
    pot = elm.Potentiometer().at((0.5, 10.7)).down().length(3.5)
    d += pot
    text(d, (0.0, 9.0), "RV1\n10k lin\npanel", 8, halign="right")
    gnd(d, (0.5, 7.2))
    tap = pot.absanchors["tap"]
    d += elm.Resistor().at(tap).right().length(3).label("R3 22k", fontsize=8)
    vset = (tap[0] + 3, tap[1])
    dot(d, vset)
    d += elm.Capacitor(polar=True).at(vset).down().length(3).label("C5\n10u 16 V", loc="bottom", fontsize=8)
    gnd(d, (vset[0], vset[1] - 3))
    text(d, (vset[0] + 0.25, vset[1] + 0.45), "VSET", 9, "blue")
    text(d, (-1.2, 4.3), "VSET = 0..4.10 V; R3/C5 = 0.22 s:\nsoft start and knob filter", 7.5, GREY)

    # ------------------------------------------------------------------ sensor
    box(d, -1.5, -14.0, 10.2, 2.0, "LIGHT SENSOR")
    rail(d, (0.5, 0.5), "+5V")
    wire(d, (0.5, 0.5), (0.5, -0.5))
    dot(d, (0.5, -0.5), True)
    text(d, (0.75, -0.3), "J3-1", 8)
    ph = elm.NpnPhoto().right().at((0.5, -0.5)).anchor("collector").label("PH1\nTEPT5700", loc="left", fontsize=8)
    d += ph
    em = ph.absanchors["emitter"]
    wire(d, em, (em[0], -4.3))
    dot(d, (em[0], -4.3), True)
    text(d, (em[0] + 0.25, -4.1), "J3-2", 8)
    box(d, -1.2, -4.0, 2.2, 0.0, None, ls=":")
    text(d, (-1.2, -5.0), "on the -X wall,\nfacing up,\n2-wire twisted", 7.5, GREY)
    sens = (em[0], -6.5)
    wire(d, (em[0], -4.3), sens)
    dot(d, sens)
    text(d, (sens[0] - 0.25, sens[1] + 0.4), "SENS", 9, "blue", halign="right")
    d += elm.Resistor().at(sens).down().length(2.5).label("R4\n2k2", loc="bottom", fontsize=8)
    d += elm.ResistorVar().down().length(2.5).label("RV2\n50k trim\n(3296W)", loc="bottom", fontsize=8)
    gnd(d, (sens[0], sens[1] - 5))
    d += elm.Resistor().at(sens).right().length(3.5).label("R5 10k", fontsize=8)
    sf = (sens[0] + 3.5, sens[1])
    dot(d, sf)
    text(d, (sf[0] + 0.2, sf[1] - 0.5), "SF", 9, "blue")
    d += elm.Capacitor().at(sf).down().length(3).label("C6\n1u", loc="bottom", fontsize=8)
    gnd(d, (sf[0], sf[1] - 3))
    text(d, (2.0, -12.6), "R_L = R4 + RV2:\ncalibrate (ASSEMBLY.md)\nR5/C6 filter: 6-12 Hz", 7.5, GREY)

    # ------------------------------------------------------------------ integrator
    box(d, 10.6, -14.0, 31.5, 14.4, "LIGHT LOOP: INTEGRATOR U1A + AUTO/MANUAL")
    sw = elm.SwitchSpdt2().at((15.5, -6.5)).anchor("b").left().flip()
    d += sw
    # orientation: drawn leftwards so the common 'a' is on the right
    a, b, c = sw.absanchors["a"], sw.absanchors["b"], sw.absanchors["c"]
    wire(d, sf, b, "-|")
    text(d, (b[0] - 0.2, b[1] + 0.45), "AUTO", 8)
    text(d, (c[0] + 0.3, c[1] - 1.9), "SW1 AUTO/MAN\nSPDT panel toggle", 8)
    text(d, (c[0] - 0.3, c[1] - 0.2), "MAN", 8, halign="right")
    # drawn flipped: + input on top (VSET from above), - input below (R6 from below), C7 underneath
    op1 = elm.Opamp(leads=True).right().flip().at((22.5, 1.0)).anchor("in1").label("U1A\nLM358", loc="center", ofst=(-0.3, 0), fontsize=8)
    d += op1
    in1, in2, out1 = op1.absanchors["in1"], op1.absanchors["in2"], op1.absanchors["out"]
    # R6 from the switch common to the inverting input
    d += elm.Resistor().at(a).right().length(3).label("R6 100k", fontsize=8)
    r6e = (a[0] + 3, a[1])
    inv_a = (in1[0] - 0.8, in1[1])
    wire(d, r6e, (in1[0] - 1.6, r6e[1]))
    wire(d, (in1[0] - 1.6, r6e[1]), (in1[0] - 1.6, in1[1]))
    wire(d, (in1[0] - 1.6, in1[1]), in1)
    dot(d, inv_a)
    text(d, (in1[0] - 1.7, in1[1] + 0.45), "INV_A", 8, "blue", halign="right")
    # C7 feedback, below the op-amp
    wire(d, inv_a, (inv_a[0], in1[1] - 2.2))
    d += elm.Capacitor().at((inv_a[0], in1[1] - 2.2)).right().to((out1[0] + 0.8, in1[1] - 2.2)).label("C7  1u film (MKT)", loc="bottom", fontsize=8)
    wire(d, (out1[0] + 0.8, in1[1] - 2.2), (out1[0] + 0.8, out1[1]))
    # + input from VSET
    wire(d, vset, (in2[0] - 1.6, vset[1]))
    wire(d, (in2[0] - 1.6, vset[1]), (in2[0] - 1.6, in2[1]))
    wire(d, (in2[0] - 1.6, in2[1]), in2)
    wire(d, out1, (out1[0] + 2.0, out1[1]))
    vc = (out1[0] + 0.8, out1[1])
    dot(d, vc)
    vcx = (out1[0] + 2.0, out1[1])
    dot(d, vcx)
    text(d, (vc[0] + 0.15, vc[1] + 0.45), "VC", 9, "blue")
    # manual feedback divider R7/R8
    d += elm.Resistor().at(vcx).down().length(2.5).label("R7\n12k", loc="bottom", fontsize=8)
    mfb = (vcx[0], vcx[1] - 2.5)
    dot(d, mfb)
    d += elm.Resistor().at(mfb).down().length(2.5).label("R8\n10k", loc="bottom", fontsize=8)
    gnd(d, (mfb[0], mfb[1] - 2.5))
    text(d, (mfb[0] + 0.2, mfb[1] + 0.35), "MFB", 9, "blue")
    wire(d, mfb, (mfb[0] - 0.9, mfb[1]))
    wire(d, (mfb[0] - 0.9, mfb[1]), (mfb[0] - 0.9, -11.0))
    wire(d, (mfb[0] - 0.9, -11.0), (c[0], -11.0))
    wire(d, (c[0], -11.0), c)
    text(d, (11.0, 12.6), "AUTO: dVC/dt = (VSET - V_SF) / (R6 C7), tau_loop = 0.15..0.32 s\n"
                         "MAN:  VC -> VSET x (R7+R8)/R8 (0..9.0 V), tau = 0.22 s\n"
                         "the switch never steps VC: bumpless change-over", 7.5, GREY)
    # to the current regulator
    wire(d, vcx, (vcx[0] + 1.6, vcx[1]))
    vcr = (vcx[0] + 1.6, vcx[1])
    dot(d, vcr)

    # ------------------------------------------------------------------ current regulator
    box(d, 32.5, -14.0, 52.0, 14.4, "LINEAR CONSTANT-CURRENT STRIP DRIVER (no PWM)")
    d += elm.Resistor().at(vcr).right().length(3).label("R9 47k", fontsize=8)
    vcmd = (vcr[0] + 3, vcr[1])
    dot(d, vcmd)
    text(d, (vcmd[0] - 0.2, vcmd[1] + 0.9), "VCMD = VC/48", 8, "blue")
    d += elm.Resistor().at(vcmd).down().length(2.5).label("R10\n1k", loc="bottom", fontsize=8)
    gnd(d, (vcmd[0], vcmd[1] - 2.5))
    wire(d, vcmd, (vcmd[0] + 1.5, vcmd[1]))
    dot(d, (vcmd[0] + 1.5, vcmd[1]))
    d += elm.Capacitor().at((vcmd[0] + 1.5, vcmd[1])).down().length(2.5).label("C8\n100n", loc="bottom", fontsize=8)
    gnd(d, (vcmd[0] + 1.5, vcmd[1] - 2.5))
    # drawn flipped: + input on top (VCMD), - input below; C9 underneath, R11 from below
    op2 = elm.Opamp(leads=True).right().flip().at((vcmd[0] + 4.0, vcmd[1])).anchor("in2").label("U1B\nLM358", loc="center", ofst=(-0.3, 0), fontsize=8)
    d += op2
    b1, b2, bo = op2.absanchors["in1"], op2.absanchors["in2"], op2.absanchors["out"]
    wire(d, (vcmd[0] + 1.5, vcmd[1]), b2)
    # C9 out -> in1
    nb = (b1[0] - 0.8, b1[1])
    wire(d, (b1[0] - 1.6, b1[1]), b1)
    dot(d, nb)
    wire(d, nb, (nb[0], nb[1] - 2.2))
    d += elm.Capacitor().at((nb[0], nb[1] - 2.2)).right().to((bo[0] + 0.6, nb[1] - 2.2)).label("C9  10n", loc="bottom", fontsize=8)
    wire(d, (bo[0] + 0.6, nb[1] - 2.2), (bo[0] + 0.6, bo[1]))
    dot(d, (bo[0] + 0.6, bo[1]))
    text(d, (b1[0] - 1.5, nb[1] + 0.35), "INV_B", 7, "blue")
    wire(d, bo, (bo[0] + 0.6, bo[1]))
    d += elm.Resistor().at((bo[0] + 0.6, bo[1])).right().length(2.5).label("R12 100", fontsize=8)
    gate = (bo[0] + 3.1, bo[1])
    dot(d, gate)
    text(d, (gate[0] - 0.1, gate[1] + 0.45), "GATE", 8, "blue")
    d += elm.Resistor().at(gate).down().length(3.0).label("R13\n100k", loc="bottom", fontsize=8)
    gnd(d, (gate[0], gate[1] - 3.0))
    q = elm.NFet().right().reverse().at((gate[0] + 3.2, gate[1])).anchor("gate").label("Q1\nIRF520N\nTO-220", loc="right", fontsize=8)
    d += q
    wire(d, gate, q.absanchors["gate"])
    dr, src = q.absanchors["drain"], q.absanchors["source"]
    # sense resistor
    wire(d, src, (src[0], src[1] - 1.0))
    sense = (src[0], src[1] - 1.0)
    dot(d, sense)
    text(d, (sense[0] + 0.25, sense[1] + 0.1), "SENSE", 8, "blue")
    d += elm.Resistor().at(sense).down().length(2.5).label("R14\n0R47 1 %\n0.6 W", loc="bottom", fontsize=8)
    gnd(d, (sense[0], sense[1] - 2.5))
    # R11 back to INV_B
    wire(d, sense, (sense[0] + 1.8, sense[1]))
    wire(d, (sense[0] + 1.8, sense[1]), (sense[0] + 1.8, -10.8))
    d += elm.Resistor().at((sense[0] + 1.8, -10.8)).left().to((b1[0] - 1.6, -10.8)).label("R11 1k", loc="bottom", fontsize=8)
    wire(d, (b1[0] - 1.6, -10.8), (b1[0] - 1.6, b1[1]))
    # drain to the strip
    wire(d, dr, (dr[0], 8.0))
    lk = (dr[0], 8.0)
    dot(d, lk, True)
    text(d, (lk[0] + 0.3, lk[1]), "J2-2  strip -", 8)
    d += elm.LED().at(lk).up().length(3.0).reverse().label("LED strip\nBTF FCOB 480/m\n12 V, 4000 K, CRI>90\n0.55 m (4 runs\nin parallel)", loc="top", fontsize=7.5)
    top = (lk[0], 11.0)
    dot(d, top, True)
    text(d, (top[0] + 0.3, top[1]), "J2-1  strip +", 8)
    wire(d, top, (top[0], 12.0))
    rail(d, (top[0], 12.0), "+12V")
    box(d, lk[0] - 1.5, 7.6, lk[0] + 4.6, 11.4, None, ls=":")
    text(d, (33.0, -12.6), "I_LED = VCMD / R14 = VC / 22.6 ohm: 0..452 mA, limited to about 0.38 A at 12.0 V by the strip\n"
                          "Q1 worst-case dissipation 0.43 W (12.6 V in): no heatsink (TO-220 free air, Tj < 80 C)", 7.5, GREY)

    # ------------------------------------------------------------------ notes and title block
    text(d, (33.0, 22.6), "NOTES\n"
                          "1. Resistors 1/4 W 1 % metal film unless noted.\n"
                          "2. No microcontroller: closed-loop analog control, DC current, flicker-free.\n"
                          "3. Off-board: JK1 jack, RV1, SW1, D3 (panel); PH1 (sensor); LED strip.\n"
                          "4. Net names in blue; values checked in sim/loop_sim.py.", 7.5)
    tb = (38.0, 15.4)
    box(d, tb[0], tb[1], 52.0, 20.4, None, ls="-", color="black")
    wire(d, (tb[0], tb[1] + 2.2), (52.0, tb[1] + 2.2))
    text(d, (tb[0] + 0.3, tb[1] + 4.3), "DentalCraft scan enclosure", 10)
    text(d, (tb[0] + 0.3, tb[1] + 3.2), "LED auto-brightness controller, analog, no MCU", 9)
    text(d, (tb[0] + 0.3, tb[1] + 1.5), "Rev A   2026-11-16   sheet 1/1", 8)
    text(d, (tb[0] + 0.3, tb[1] + 0.6), "hardware/scan-enclosure/electronics/sim/schematic.py", 7)
    return d


if __name__ == "__main__":
    dr = draw()
    dr.save(os.path.join(OUT, "schematic.svg"))
    dr.save(os.path.join(OUT, "schematic.png"), dpi=130)
    print("written")
