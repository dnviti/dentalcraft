"""Photometric check of the LED layout inside the scan enclosure.

Geometry is taken from ../../src/params.py at the defaults (inside X +-117, Y -120 (open front)..273,
Z 8.5..319; aim point T = (0, 0, 105.2); scanner 190 mm from T at 40 deg). Prints:
  * whether any LED channel is inside the camera/projector view cone (elevation 30..50, distance 175..205),
  * illuminance at the model per lm/m emitted by the diffusers,
  * illuminance uniformity over the model envelope,
  * the light sensor reading and how much of a room-light change the loop cancels at the model.
Run: python photometry.py   (numpy only)
"""
import numpy as np

D = np.radians
T = np.array([0.0, 0.0, 105.2])
FRONT_Y, X_IN, Z_BASE, Z_ROOF = -120.0, 117.0, 8.5, 319.0

# LED runs: strip start, strip end, aperture normal (the diffuser faces this way); points are on the
# diffuser face. Strip lengths are multiples of the 25 mm cut pitch: roof 6 x 25 = 150 mm, walls 5 x 25 = 125 mm.
# The scanner looks from +Y towards -Y, so the lights sit on the camera side and overhead: the faces the
# camera sees (up and +Y) get the light; no run is near the optical axis (no head-on glare).
RUNS = {
    "roof_left":  (np.array([-90.0, -90, 307]), np.array([-90.0, 60, 307]), np.array([0.0, 0, -1])),
    "roof_right": (np.array([90.0, -90, 307]),  np.array([90.0, 60, 307]),  np.array([0.0, 0, -1])),
    "wall_left":  (np.array([-105.0, 95, 175]), np.array([-105.0, 95, 300]), np.array([1.0, 0, 0])),
    "wall_right": (np.array([105.0, 95, 175]),  np.array([105.0, 95, 300]),  np.array([-1.0, 0, 0])),
}
# light sensor: TEPT5700 dome tip on the inside of the -X upper front side piece, above the model sweep, facing
# up, axis tilted 10 deg towards the open front; own response cos^1.57 (+-50 deg half sensitivity). A D16 collar
# 0.5 mm below the tip hides everything more than atan(0.5/8) = 3.6 deg below the tip plane (cut-off 86.4 deg
# off the axis): the platter and the model, which stay >= 10.9 deg below it at every tilt (see clearance()).
SENSOR_POS = np.array([-110.0, -40.0, 180.0])
SENSOR_ELEV, SENSOR_AZ, SENSOR_N, SENSOR_CUT = 80.0, 0.0, 1.57, 86.4


def clearance(pos=None, elev=None, az=None):
    """highest angle (deg, + = above) of the platter (r 100, top Z 90.2, rim to 80.2) and a D100 x 60 model,
    any rotation, tilt -30..+30 about the X axis at Z 43.2, seen from the sensor tip against its collar plane."""
    pos = SENSOR_POS if pos is None else pos
    nv = axis(SENSOR_ELEV if elev is None else elev, SENSOR_AZ if az is None else az)
    ang = np.linspace(0, 2 * np.pi, 72, endpoint=False)
    pts = [(r * np.cos(a), r * np.sin(a), z) for r in (50, 75, 100) for a in ang for z in (90.2, 80.2)]
    pts += [(50 * np.cos(a), 50 * np.sin(a), z) for a in ang for z in (90.2, 120.0, 150.2)]
    pts = np.array(pts)
    worst = -90.0
    for t in np.linspace(-30, 30, 13):
        c, s = np.cos(D(t)), np.sin(D(t))
        y, z = pts[:, 1], pts[:, 2] - 43.2
        q = np.stack([pts[:, 0], y * c - z * s, y * s + z * c + 43.2], 1) - pos
        q /= np.linalg.norm(q, axis=1)[:, None]
        worst = max(worst, np.degrees(np.arcsin(np.clip(q @ nv, -1, 1))).max())
    return worst


def axis(elev, az):
    """unit vector, elev above horizontal, az from -Y (front) towards +X."""
    e, a = D(elev), D(az)
    return np.array([np.cos(e) * np.sin(a), -np.cos(e) * np.cos(a), np.sin(e)])


def camera(elev=40.0, dist=190.0):
    e = np.array([0.0, -np.cos(D(elev)), -np.sin(D(elev))])
    up = np.array([0.0, -np.sin(D(elev)), np.cos(D(elev))])
    return T - dist * e, e, up


def in_view(p, elev=40.0, dist=190.0, h=35.5 / 2, v=29.7 / 2, margin=3.0):
    pos, e, up = camera(elev, dist)
    d = p - pos
    z = d @ e
    if z <= 0:
        return False
    return abs(d[0]) / z < np.tan(D(h + margin)) and abs(d @ up) / z < np.tan(D(v + margin))


def run_points(run, step=2.0):
    a, b, n = run
    L = np.linalg.norm(b - a)
    k = max(1, int(L / step))
    t = (np.arange(k) + 0.5) / k
    return a + np.outer(t, b - a), L / k, n


def response(cos_t, n=1.0, cut=90.0):
    """receiver response: cos^n inside the cut-off cone, 0 outside."""
    c = np.clip(cos_t, 0.0, None)
    return np.where(cos_t >= np.cos(D(cut)), c ** n, 0.0)


def E_led(p, normal, lm_per_m=1.0, n=1.0, cut=90.0, runs=RUNS):
    """illuminance (lx) from lambertian line sources of lm_per_m (lm per metre leaving the diffuser)."""
    E = 0.0
    for r in runs.values():
        P, dl, nrm = run_points(r)
        I0 = lm_per_m * (dl / 1000.0) / np.pi            # cd, on-axis, per element
        d = P - p
        r2 = (d ** 2).sum(1) / 1e6
        u = d / np.sqrt((d ** 2).sum(1))[:, None]
        E += np.sum(I0 * np.clip(-(u @ nrm), 0, None) * response(u @ normal, n, cut) / r2)
    return E


def E_room(p, normal, L=1.0, n=1.0, cut=90.0, grid=60):
    """illuminance (lx) from the open front as a uniform luminance L (cd/m2) (room light)."""
    xs = np.linspace(-X_IN, X_IN, grid)
    zs = np.linspace(Z_BASE, Z_ROOF, grid)
    dA = (2 * X_IN / grid) * ((Z_ROOF - Z_BASE) / grid) / 1e6
    X, Z = np.meshgrid(xs, zs)
    P = np.stack([X.ravel(), np.full(X.size, FRONT_Y), Z.ravel()], 1)
    d = P - p
    r2 = (d ** 2).sum(1) / 1e6
    u = d / np.sqrt((d ** 2).sum(1))[:, None]
    return np.sum(L * np.clip(-u[:, 1], 0, None) * response(u @ normal, n, cut) * dA / r2)


# faces of the model the camera sees (it looks from +Y, 40 deg down): up, towards the camera, sideways.
_c, _s = np.cos(D(40)), np.sin(D(40))
MODEL_DIRS = [(0, 0, 1), (0, 1, 0), (1, 0, 0), (-1, 0, 0), (0, _c, _s), (0.7071, 0.7071, 0), (-0.7071, 0.7071, 0)]


def model_mean(fn, p=T + np.array([0, 0, -10.0])):
    return np.mean([fn(p, np.array(v, float) / np.linalg.norm(v)) for v in MODEL_DIRS])


def main():
    print("LED channels inside the camera/projector view (elev 30/40/50, dist 175/190/205, +3 deg)?")
    total = 0.0
    for name, r in RUNS.items():
        P, _, _ = run_points(r, 5.0)
        vis = any(in_view(p, el, di) for p in P for el in (30, 40, 50) for di in (175, 190, 205))
        L = np.linalg.norm(r[1] - r[0])
        total += L
        print(f"  {name:11s} strip {L:5.0f} mm  in view: {vis}")
    print(f"  total strip length {total:.0f} mm")

    M = T + np.array([0, 0, -10.0])
    print("\nModel point (10 mm under T), per 1 lm/m from the diffusers / per 1 cd/m2 of room light:")
    for v in MODEL_DIRS:
        v = np.array(v, float) / np.linalg.norm(v)
        print(f"  facing {str(np.round(v, 2)):18s} LED {E_led(M, v):.3f} lx   room {E_room(M, v):.3f} lx")
    em, rm = model_mean(E_led), model_mean(E_room)
    v = np.array([0, -1.0, 0])
    print(f"  facing (0, -1, 0) (away from the camera) LED {E_led(M, v):.3f} lx   room {E_room(M, v):.3f} lx")
    print(f"  mean of the camera-side faces   LED {em:.3f} lx   room {rm:.3f} lx")

    # uniformity: horizontal faces on a 100 mm disc at the model top (z = platter + 40) and vertical faces round it
    zt = 90.2 + 40
    pts = [np.array([r * np.cos(a), r * np.sin(a), zt]) for r in (0, 25, 50) for a in np.linspace(0, 2 * np.pi, 8, endpoint=False)]
    up = [E_led(p, np.array([0, 0, 1.0])) for p in pts]
    side = []
    for a in np.linspace(np.radians(30), np.radians(150), 5):   # side faces turned towards the camera (+Y)
        nrm = np.array([np.cos(a), np.sin(a), 0.0])
        side.append(E_led(np.array([50 * np.cos(a), 50 * np.sin(a), 110.0]), nrm))
    print(f"\nUniformity, top faces (D100 at z={zt:.0f}): min/max = {min(up)/max(up):.2f}; "
          f"camera-side vertical faces (+-60 deg round +Y): min/max = {min(side)/max(side):.2f}")

    nv = axis(SENSOR_ELEV, SENSOR_AZ)
    pv = SENSOR_POS
    vis = any(in_view(pv, el, di) for el in (30, 40, 50) for di in (175, 190, 205))
    es = E_led(pv, nv, n=SENSOR_N, cut=SENSOR_CUT)
    rs = E_room(pv, nv, n=SENSOR_N, cut=SENSOR_CUT)
    comp = (rs / es) / (rm / em)
    cl = clearance()
    print(f"\nSensor at {pv.tolist()} axis elev {SENSOR_ELEV} az {SENSOR_AZ}: in view {vis}; "
          f"platter and model at most {cl:+.1f} deg vs the tip plane (collar hides below "
          f"{SENSOR_CUT - 90:+.1f} deg): {'OK' if cl < SENSOR_CUT - 90 else 'SEES THE MODEL'}")
    print(f"  reads {es:.3f} lx per lm/m (LED), {rs:.3f} lx per cd/m2 (room)")
    print(f"  room-light compensation at the model: {comp:.2f} (1.00 = a room change is fully cancelled)")
    spread = [(E_room(pv, axis(SENSOR_ELEV + de, SENSOR_AZ + da), n=SENSOR_N, cut=SENSOR_CUT) /
               E_led(pv, axis(SENSOR_ELEV + de, SENSOR_AZ + da), n=SENSOR_N, cut=SENSOR_CUT)) / (rm / em)
              for de in (-10, 0, 10) for da in (-10, 0, 10)]
    print(f"  with the axis off by +-10 deg: {min(spread):.2f} .. {max(spread):.2f}")
    return dict(em=em, rm=rm, es=es, rs=rs, comp=comp, up=E_led(M, np.array([0, 0, 1.0])))


def coefficients():
    """numbers the loop simulation needs: lx per lm/m and per cd/m2, at the model and at the sensor."""
    nv = axis(SENSOR_ELEV, SENSOR_AZ)
    return dict(em=model_mean(E_led), rm=model_mean(E_room),
                es=E_led(SENSOR_POS, nv, n=SENSOR_N, cut=SENSOR_CUT),
                rs=E_room(SENSOR_POS, nv, n=SENSOR_N, cut=SENSOR_CUT))


if __name__ == "__main__":
    main()
