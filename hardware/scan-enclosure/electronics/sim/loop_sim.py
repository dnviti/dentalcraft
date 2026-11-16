"""Numerical model of the MCU-less automatic-brightness loop (no SPICE: behavioural, time domain).

Blocks, values from the schematic (reference designators in brackets):
  setpoint   RV1 10k + R2 2.2k from the 5 V rail, R3 22k / C5 10 uF filter          -> VSET
  sensor     TEPT5700 (PH1) current source into R4 2.2k + RV2 (R_L, calibrated),
             R5 10k / C6 1 uF filter                                               -> V_F
  integrator U1A, R6 100k, C7 1 uF film; output limited 0 .. 10.2 V, windup modelled -> VC
  manual     SW1 feeds R6 from R7 12k / R8 10k (k_m = 0.4545) instead of V_F
  current    R9 47k / R10 1k -> VCMD; U1B + Q1 IRF520N + R14 0.47 ohm: I = VCMD / R14
             (inner loop about 16 kHz: static here), limited by the strip headroom
  strip      0.55 m BTF FCOB 480 LED/m 12 V (22 x 25 mm cuts); each cut = 4 strings of 3 chips +
             series resistor, rated 0.504 A at 12.0 V
  light      1000 lm/m at rating, droop x(1.15 - 0.15 x), diffuser 0.55, geometry from photometry.py
Writes: ../step_response.png, ../room_light.png, ../loop_bode.png, ../mosfet_dissipation.png
Run: python loop_sim.py   (numpy, scipy, matplotlib)
"""
import os

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

import photometry

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")

# ---------------------------------------------------------------- component values
V5 = 5.0
R2, RV1 = 2.2e3, 10e3
R3, C5 = 22e3, 10e-6
R4 = 2.2e3
R5, C6 = 10e3, 1e-6
R6, C7 = 100e3, 1e-6
R7, R8 = 12e3, 10e3
R9, R10 = 47e3, 1e3
R14 = 0.47
VC_MAX = 10.2           # LM358 output high at 11.6 V supply, light load (datasheet: V+ - 1.5 V typ)
VSENS_MAX = 4.6         # TEPT5700 saturates at VCE ~ 0.4 V from the 5 V rail
K_M = R8 / (R7 + R8)
K_CMD = R10 / (R9 + R10)
VSET_MAX = V5 * RV1 / (RV1 + R2)

# ---------------------------------------------------------------- strip and light
STRIP_M = 0.55
I_RATED = 11.0 / 12.0 * STRIP_M                        # 0.504 A
N_STRINGS = int(round(STRIP_M / 0.025)) * 4           # 88 strings of 3 chips
I_STR0 = I_RATED / N_STRINGS                          # 5.73 mA
VF0, NVT = 2.85, 0.052                                # chip Vf at I_STR0, slope per e-fold
R_STR = (12.0 - 3 * VF0) / I_STR0                     # 602 ohm
LM_PER_M = 1000.0                                     # BTF datasheet 928..1114 lm/m (12 V 480 LED, 8 mm)
T_DIFF = 0.55                                         # printed natural PETG 1.2 mm (estimate)


def v_strip(i_total):
    i = np.maximum(i_total / N_STRINGS, 1e-9)
    return 3 * (VF0 + NVT * np.log(i / I_STR0)) + R_STR * i


def i_headroom(v_rail):
    """largest strip current when Q1 is fully on (Rds 0.27 ohm max) at a given rail voltage."""
    lo, hi = 0.0, 2 * I_RATED
    for _ in range(60):
        mid = 0.5 * (lo + hi)
        if v_strip(mid) + mid * (R14 + 0.27) < v_rail:
            lo = mid
        else:
            hi = mid
    return lo


def flux(i_total):
    x = np.clip(i_total / I_RATED, 0, None)
    return x * (1.15 - 0.15 * x)


COEF = photometry.coefficients()       # em, rm (model), es, rs (sensor): lx per lm/m and per cd/m2


def lmpm(i_total):
    return LM_PER_M * T_DIFF * flux(i_total)


def e_model(i_total, room_lum):
    return COEF["em"] * lmpm(i_total) + COEF["rm"] * room_lum


def e_sensor(i_total, room_lum):
    return COEF["es"] * lmpm(i_total) + COEF["rs"] * room_lum


# ---------------------------------------------------------------- one run
def simulate(t_end, knob, room, mode, gain=1.0, v_in=12.0, dt=20e-6, rl=None):
    """knob(t) 0..1, room(t) cd/m2 at the open front, mode(t) 'auto'/'manual'.
    gain scales the sensor sensitivity left after calibration (1.0 = calibrated)."""
    v_rail = v_in - 0.40 - 0.2                         # Schottky D1 1N5819 0.40 V at 0.4 A, PTC F1 about 0.2 V
    i_lim = i_headroom(v_rail)
    if rl is None:
        rl = calibrated_rl(v_in)
    s_eff = gain * SENS_UA_PER_LX * 1e-6
    n = int(t_end / dt)
    t = np.arange(n) * dt
    out = {k: np.zeros(n) for k in ("vset", "vc", "i", "em", "vs", "vf")}
    vset = vf = vcap = 0.0     # vcap = V(-) - VC across C7
    for k in range(n):
        tk = t[k]
        # setpoint filter
        vw = knob(tk) * VSET_MAX
        vset += dt * (vw - vset) / (R3 * C5)
        # op-amp U1A with output limits; V(-) = VSET while linear
        vc = vset - vcap
        vminus = vset
        if vc > VC_MAX:
            vc, vminus = VC_MAX, VC_MAX + vcap
        elif vc < 0.0:
            vc, vminus = 0.0, vcap
        i_led = min(vc * K_CMD / R14, i_lim)
        lum = room(tk)
        e_s = e_sensor(i_led, lum)
        # sensor node: phototransistor current into R_L || (R5 -> V_F)
        i_ph = s_eff * e_s
        vs = min((i_ph + vf / R5) / (1 / rl + 1 / R5), VSENS_MAX)
        m = mode(tk)
        vin_r6 = vf if m == "auto" else K_M * vc
        i_r6 = (vin_r6 - vminus) / R6
        vcap += dt * i_r6 / C7
        i_r6_f = i_r6 if m == "auto" else 0.0
        vf += dt * ((vs - vf) / R5 - i_r6_f) / C6
        for key, val in (("vset", vset), ("vc", vc), ("i", i_led), ("em", e_model(i_led, lum)), ("vs", vs), ("vf", vf)):
            out[key][k] = val
    out["t"] = t
    out["i_lim"] = i_lim
    return out


SENS_UA_PER_LX = 0.56       # TEPT5700 geometric mean of groups A..C (5.2..24 uA at 20 lx)


def calibrated_rl(v_in=12.0):
    """ASSEMBLY.md calibration: AUTO, knob at max, room light off, turn RV2 until the strip just starts
    to dim: the sensor then reads VSET_MAX at the largest current the strip reaches."""
    i_top = min(VC_MAX * K_CMD / R14, i_headroom(v_in - 0.60))
    return VSET_MAX / (SENS_UA_PER_LX * 1e-6 * e_sensor(i_top, 0.0))


def settle_time(t, y, t0, band=0.02, t1=None):
    """time after t0 (window up to t1) until y stays inside +-band of its final value; overshoot in %."""
    m = (t >= t0) & (t < (t1 if t1 is not None else np.inf))
    tt, yy = t[m], y[m]
    y0, yf = yy[0], np.mean(yy[-max(10, len(yy) // 50):])
    step = yf - y0
    err = np.abs(yy - yf) > band * abs(step)
    idx = np.nonzero(err)[0]
    ts = (tt[idx[-1]] - t0) if len(idx) else 0.0
    if step > 0:
        ov = max(0.0, (yy.max() - yf) / step * 100)
    else:
        ov = max(0.0, (yf - yy.min()) / -step * 100)
    return ts, ov


# ---------------------------------------------------------------- linear loop analysis
def loop_gain(w, gain=1.0, i_op=None):
    """open-loop L(jw) of the light loop around the operating point."""
    if i_op is None:
        i_op = 0.5 * I_RATED
    rl = calibrated_rl()
    di = 1e-4
    dvs_di = gain * SENS_UA_PER_LX * 1e-6 * rl * (e_sensor(i_op + di, 0) - e_sensor(i_op - di, 0)) / (2 * di)
    gp = dvs_di * K_CMD / R14                          # dV_s / dV_C
    rpar = rl * R5 / (rl + R5)
    s = 1j * w
    h_filter = 1 / (1 + s * (rl + R5) * C6)            # current source into R_L || (R5 + C6): V_F/I = R_L/(1+sC6(R_L+R5))
    h_int = 1 / (s * R6 * C7)
    h_cmd = 1 / (1 + s * (R9 * R10 / (R9 + R10)) * 100e-9)     # C8 on VCMD
    h_inner = 1 / (1 + s / (2 * np.pi * 16e3))                 # current loop
    return gp * h_filter * h_int * h_cmd * h_inner, gp


def margins(gain=1.0, i_op=None):
    w = np.logspace(-2, 6, 40000)
    L, gp = loop_gain(w, gain, i_op)
    mag = np.abs(L)
    k = np.argmin(np.abs(mag - 1))
    pm = 180 + np.degrees(np.angle(L[k]))
    return w[k], pm, gp


def inner_loop(gm):
    """inner current loop of U1B: LM358 (GBW 0.7 MHz, A0 100 dB, second pole 1.5 MHz), C9 10 nF / R11 1k
    local feedback, R12 100 ohm into the IRF520N gate (Ciss 330 pF), source degeneration R14.
    Returns the loop gain, its crossover and phase margin, and the -3 dB bandwidth of I / VCMD."""
    w = np.logspace(1, 8, 20000)
    s = 1j * w
    a0, gbw = 1e5, 2 * np.pi * 0.7e6
    A = a0 / (1 + s * a0 / gbw) / (1 + s / (2 * np.pi * 1.5e6))
    tau = 1e3 * 10e-9
    hg = 1 / (1 + s * (100 + 50) * 330e-12)            # 50 ohm LM358 output resistance
    ks = gm * R14 / (1 + gm * R14)
    L = A * (s * tau + hg * ks) / (1 + s * tau)
    Tcl = A * hg * ks / (1 + s * tau) / (1 + L)
    k = np.argmin(np.abs(np.abs(L) - 1))
    kb = np.argmax(np.abs(Tcl) < np.abs(Tcl[0]) / np.sqrt(2))
    return w, L, w[k], 180 + np.degrees(np.angle(L[k])), w[kb]


# ---------------------------------------------------------------- figures
def fig_step():
    gains = [(0.75, "sensor gain -25 %"), (1.0, "calibrated"), (1.33, "sensor gain +33 %")]
    knob = lambda t: 0.5 if t < 3.0 else 0.75
    room = lambda t: 0.0
    auto = lambda t: "auto"
    fig, ax = plt.subplots(3, 1, figsize=(9, 9), sharex=True)
    lines = []
    for g, lab in gains:
        r = simulate(6.0, knob, room, auto, gain=g, dt=50e-6)
        t = r["t"]
        ts_on, ov_on = settle_time(t, r["em"], 0.0, t1=3.0)
        ts, ov = settle_time(t, r["em"], 3.0)
        lines.append((lab, ts_on, ov_on, ts, ov))
        ax[0].plot(t, r["em"], label=f"{lab}: soft start settles {ts_on:.2f} s; knob step settles {ts:.2f} s, "
                                     f"overshoot {ov:.1f} % (2 % band)")
        ax[1].plot(t, r["i"] * 1000, label=lab)
        ax[2].plot(t, r["vc"], label=f"VC ({lab})")
    ax[2].plot(t, r["vset"], "k--", label="VSET (R3/C5 filtered knob)")
    ax[0].set_ylabel("illuminance on the camera-side\nfaces of the model [lx]")
    ax[1].set_ylabel("LED strip current [mA]")
    ax[2].set_ylabel("voltage [V]")
    ax[2].set_xlabel("time [s]")
    ax[0].set_title("Power-on soft start (knob at 50 %), then knob step 50 % -> 75 % at t = 3 s\n"
                    "AUTO mode, room light off; sensor sensitivity left after calibration -25 % / 0 / +33 %")
    for a in ax:
        a.grid(alpha=0.3)
        a.legend(fontsize=8, loc="lower right")
    fig.tight_layout()
    fig.savefig(os.path.join(OUT, "step_response.png"), dpi=120)
    plt.close(fig)
    return lines


def fig_room():
    knob = lambda t: 0.6
    # ceiling light switched on at 2 s, off at 6 s; 100 Hz flicker of 30 % (cheap LED/fluorescent lamp)
    base = 400.0     # cd/m2 seen through the open front: a bright room

    def room(t):
        on = 2.0 <= t < 6.0
        return (base * (1 + 0.3 * np.sin(2 * np.pi * 100 * t))) if on else 0.0

    res = {}
    for name, mode in (("AUTO (closed loop)", lambda t: "auto"), ("MANUAL (fixed current)", lambda t: "manual")):
        res[name] = simulate(9.0, knob, room, mode, dt=20e-6)
    fig, ax = plt.subplots(3, 1, figsize=(9, 9))
    for name, r in res.items():
        ax[0].plot(r["t"], r["em"], label=name, lw=0.8)
        ax[1].plot(r["t"], r["i"] * 1000, label=name, lw=0.8)
    ra = res["AUTO (closed loop)"]
    t = ra["t"]
    m = (t > 4.5) & (t < 5.5)
    ripple = (ra["i"][m].max() - ra["i"][m].min()) / ra["i"][m].mean() * 100
    pre = ra["em"][(t > 1.5) & (t < 2.0)].mean()
    during = ra["em"][(t > 4.5) & (t < 6.0)].mean()
    rm = res["MANUAL (fixed current)"]
    during_m = rm["em"][(t > 4.5) & (t < 6.0)].mean()
    ts, ov = settle_time(t[t < 6.0], ra["i"][t < 6.0], 2.0, band=0.05)
    ax[2].plot(t[m] - 4.5, ra["i"][m] * 1000, lw=0.8)
    ax[2].set_title(f"zoom, AUTO: LED current ripple from the 100 Hz room flicker = {ripple:.2f} % peak-peak", fontsize=9)
    ax[0].set_title("Room light through the open front: a 100 Hz-flickering ceiling light switched on at 2 s, off at 6 s\n"
                    f"model (camera-side faces): before {pre:.0f} lx; light on: AUTO {during:.0f} lx (mean), "
                    f"MANUAL {during_m:.0f} lx", fontsize=9)
    ax[0].set_ylabel("illuminance at the model [lx]")
    ax[1].set_ylabel("LED current [mA]")
    ax[2].set_ylabel("LED current [mA]")
    ax[2].set_xlabel("time [s] (zoom: 4.5 s + t)")
    ax[1].set_xlabel("time [s]")
    for a in ax[:2]:
        a.legend(fontsize=8)
    for a in ax:
        a.grid(alpha=0.3)
    fig.tight_layout()
    fig.savefig(os.path.join(OUT, "room_light.png"), dpi=120)
    plt.close(fig)
    return dict(ripple_pct=ripple, before=pre, auto=during, manual=during_m, settle_5pct=ts)


def fig_bode():
    fig, ax = plt.subplots(2, 2, figsize=(11, 7))
    w = np.logspace(-1, 4, 3000)
    out = []
    for g, lab in ((0.75, "-25 %"), (1.0, "calibrated"), (1.33, "+33 %")):
        for iop, il in ((0.1 * I_RATED, "10 %"), (0.75 * I_RATED, "75 %")):
            L, gp = loop_gain(w, g, iop)
            wc, pm, _ = margins(g, iop)
            out.append((lab, il, wc, pm, gp))
            ax[0, 0].semilogx(w / 2 / np.pi, 20 * np.log10(np.abs(L)), label=f"{lab}, I={il}: fc={wc/2/np.pi:.2f} Hz, PM={pm:.0f} deg")
            ax[1, 0].semilogx(w / 2 / np.pi, np.degrees(np.unwrap(np.angle(L))))
    ax[0, 0].axhline(0, color="k", lw=0.5)
    ax[0, 0].set_title("light loop L(jw) (sensor gain x current level)")
    ax[0, 0].set_ylabel("|L| [dB]")
    ax[1, 0].set_ylabel("phase [deg]")
    ax[1, 0].set_xlabel("frequency [Hz]")
    ax[0, 0].legend(fontsize=7)
    inner = []
    for gm in (0.05, 0.3, 1.5):
        wi, Li, wci, pmi, wbw = inner_loop(gm)
        inner.append((gm, wci / 2 / np.pi, pmi, wbw / 2 / np.pi))
        ax[0, 1].semilogx(wi / 2 / np.pi, 20 * np.log10(np.abs(Li)),
                          label=f"gm={gm} S: crossover {wci/2/np.pi/1e3:.0f} kHz, PM={pmi:.0f} deg; I/VCMD -3 dB at {wbw/2/np.pi/1e3:.1f} kHz")
        ax[1, 1].semilogx(wi / 2 / np.pi, np.degrees(np.unwrap(np.angle(Li))))
    ax[0, 1].axhline(0, color="k", lw=0.5)
    ax[0, 1].set_title("inner current loop (U1B + Q1 + R14)")
    ax[0, 1].legend(fontsize=7)
    ax[1, 1].set_xlabel("frequency [Hz]")
    for a in ax.ravel():
        a.grid(alpha=0.3, which="both")
    fig.tight_layout()
    fig.savefig(os.path.join(OUT, "loop_bode.png"), dpi=120)
    plt.close(fig)
    return out, inner


def fig_mosfet():
    fig, ax = plt.subplots(figsize=(8, 4.5))
    worst = []
    for v_in in (11.4, 12.0, 12.6):
        v_rail = v_in - 0.40 - 0.2
        i_max = min(VC_MAX * K_CMD / R14, i_headroom(v_rail))
        i = np.linspace(0, i_max, 400)
        p = np.maximum(v_rail - v_strip(i) - i * R14, 0) * i
        ax.plot(i * 1000, p, label=f"input {v_in} V (strip max {i_max*1000:.0f} mA)")
        worst.append((v_in, p.max(), i[np.argmax(p)], i_max))
    ax.set_xlabel("LED strip current [mA]")
    ax.set_ylabel("Q1 dissipation [W]")
    ax.set_title("Q1 (IRF520N) dissipation in linear dimming, 0.55 m strip (3-chip strings)")
    ax.grid(alpha=0.3)
    ax.legend()
    fig.tight_layout()
    fig.savefig(os.path.join(OUT, "mosfet_dissipation.png"), dpi=120)
    plt.close(fig)
    return worst


if __name__ == "__main__":
    print(f"photometry: model {COEF['em']:.3f} lx/(lm/m), {COEF['rm']:.3f} lx/(cd/m2); "
          f"sensor {COEF['es']:.3f} lx/(lm/m), {COEF['rs']:.3f} lx/(cd/m2)")
    print(f"strip: rated {I_RATED*1000:.0f} mA, string R {R_STR:.0f} ohm, headroom limit at 12.0 V in: "
          f"{i_headroom(12.0-0.60)*1000:.0f} mA, 11.4 V: {i_headroom(11.4-0.60)*1000:.0f} mA, "
          f"12.6 V: {i_headroom(12.6-0.60)*1000:.0f} mA; command limit {VC_MAX*K_CMD/R14*1000:.0f} mA")
    i_top = min(VC_MAX * K_CMD / R14, i_headroom(12.0 - 0.60))
    print(f"light at the model at full ({i_top*1000:.0f} mA): camera-side {e_model(i_top,0):.0f} lx, "
          f"up-facing {photometry.E_led(photometry.T+np.array([0,0,-10.0]), np.array([0,0,1.0]))*lmpm(i_top):.0f} lx; "
          f"sensor {e_sensor(i_top,0):.0f} lx")
    rl = calibrated_rl()
    print(f"VSET max {VSET_MAX:.2f} V; calibrated R_L (typ sensor) {rl/1e3:.1f} k "
          f"(group A {rl*0.56/0.26/1e3:.1f} k, group C {rl*0.56/1.2/1e3:.1f} k)")
    for g in (0.75, 1.0, 1.33):
        for frac in (0.1, 0.5, 0.75):
            wc, pm, gp = margins(g, frac * I_RATED)
            print(f"  light loop gain x{g} at {frac*100:.0f} % current: Gp={gp:.3f} V/V  crossover {wc:.2f} rad/s "
                  f"({wc/2/np.pi:.2f} Hz), tau={1/wc:.2f} s, phase margin {pm:.1f} deg")
    print("step:", fig_step())
    print("room:", fig_room())
    b, inner = fig_bode()
    print("inner loop:", inner)
    print("mosfet:", fig_mosfet())
