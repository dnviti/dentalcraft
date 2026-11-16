"""Rounding plan of every primitive of a part (print frame) and the Blender job that unions them.

Per join primitive: outline corners get corner_r on the part's footprint corners, edge_r
elsewhere (fillet_in_r on concave outline corners); each cap is a 45 deg bed chamfer on Z 0,
flat where another primitive covers it (it disappears in the union), else a quarter-round.
Primitives inside a fit zone (tongues, keys, dowels) take lead_in_r. Every radius is reduced
to what the primitive can carry. Cut primitives stay sharp: the Blender pass rounds the edges
they leave, after the booleans."""

import numpy as np
from shapely.geometry import Point, Polygon

import csg_fillet
import csg_mesh

BED_EPS = 1e-3


def in_box(lo, hi, z, pad=0.5):
    return np.all(lo >= np.array(z[:3]) - pad) and np.all(hi <= np.array(z[3:]) + pad)


def on_hull(p, hull, tol=0.6):
    n = len(hull)
    for i in range(n):
        a, b = hull[i], hull[(i + 1) % n]
        ab = b - a
        t = np.clip((p - a) @ ab / max(ab @ ab, 1e-12), 0, 1)
        if np.linalg.norm(a + ab * t - p) < tol:
            return True
    return False


def cap_samples(pr, h, outline, out_dir):
    """Points just outside the cap face at height h (outline inset 0.2, centroid, grid)."""
    poly = Polygon(outline)
    inner = poly.buffer(-0.2)
    pts = list(np.asarray(inner.exterior.coords)[:-1]) if not inner.is_empty and inner.geom_type == "Polygon" else []
    lo, hi = outline.min(0), outline.max(0)
    for x in np.linspace(lo[0], hi[0], 7)[1:-1]:
        for y in np.linspace(lo[1], hi[1], 7)[1:-1]:
            if poly.contains(Point(x, y)):
                pts.append(np.array([x, y]))
    pts = np.array(pts)
    W = pr.world(pts[:, 0], pts[:, 1], np.full(len(pts), h))
    return W + out_dir * 0.3


def plan_prim(pr, others, P, hull, lead, corner):
    lo, hi = pr.bbox()
    if any(in_box(lo, hi, z) for z in lead):
        want, kind = P.lead_in_r, "lead_in"
    elif any(in_box(lo, hi, z, 1.0) for z in corner):
        want, kind = P.corner_r, "corner"
    else:
        want, kind = P.edge_r, "edge"
    raw = pr.outline
    turn = csg_mesh.corner_turn(raw)
    vertical = abs(pr.n[2]) > 0.99
    radii = np.zeros(len(raw))
    for i in range(len(raw)):
        if abs(turn[i]) < 20.0:
            continue
        lim = csg_mesh.max_corner_r(raw, i)
        if turn[i] < 0:
            radii[i] = min(P.fillet_in_r, lim)
            continue
        w = want
        if kind == "edge" and vertical:
            q = pr.world(raw[i:i + 1, 0], raw[i:i + 1, 1], [pr.h0])[0]
            if on_hull(q[:2], hull):
                w = P.corner_r
        radii[i] = min(max(w, want), lim)
    convex = (np.abs(turn) >= 20.0) & (turn > 0)
    r_cap = want
    if convex.any():
        r_cap = min(r_cap, radii[convex].min() - 0.05)
    outline = csg_mesh.round_outline(raw, radii)
    caps = []
    for h, sgn in ((pr.h0, -1.0), (pr.h1, 1.0)):
        nrm = pr.n * sgn
        c = pr.world([0.0], [0.0], [h])[0]
        if nrm[2] < -0.99 and abs(c[2]) < BED_EPS:
            caps.append(["chamfer", P.bed_chamfer])
            continue
        s = 1.0 if sgn < 0 else pr.s1
        S = cap_samples(pr, h, outline * s, nrm)
        cov = np.zeros(len(S), bool)
        for o in others:
            cov |= o.contains(S)
        caps.append(["flat", 0.0] if cov.all() else ["round", r_cap])
    hgt = pr.h1 - pr.h0
    rounded = [c for c in caps if c[0] != "flat"]
    lim_h = 0.45 * hgt if len(rounded) == 2 else 0.9 * hgt
    poly = Polygon(outline)
    for c in rounded:
        r = min(c[1], lim_h)
        while r > 0.1 and poly.buffer(-(r + 0.05)).is_empty:
            r *= 0.8
        c[1] = max(r, 0.0) if c[0] == "round" else min(c[1], r)
    return outline, caps, dict(kind=kind, rc=float(radii.max()) if len(radii) else 0.0,
                               caps=[(c[0], round(c[1], 3)) for c in caps])


def columns(pr, outline, caps):
    """Per-column profile of a join primitive: both cap profiles (flat, bed chamfer or
    quarter-round), the same in every column. A flat cap is buried in another primitive and
    reaches 0.3 into it, so the union has no coplanar faces there."""
    prof = []
    for kind, r in caps:
        p = [(0.0, -0.3)] if kind == "flat" else csg_mesh.cap_profile(kind, r)
        prof.append(p + [(0.0, p[-1][1] + 1e-3 * (i + 1)) for i in range(10 - len(p))])
    col = [(d, pr.h0 + h) for d, h in prof[0]] + [(d, pr.h1 - h) for d, h in reversed(prof[1])]
    return outline, [col] * len(outline)


def plan_tool(pr, joins, cuts, P, lead, k=8, pocket=True):
    """Flared cut tool: along every column of the tool wall, the first and last heights with
    material are mouths; each gets a lead-in chamfer (fit zones), the bed chamfer (on Z 0) or
    a quarter-round (elsewhere), sized to what the tool and the material depth allow."""
    lo, hi = pr.bbox()
    c = (lo + hi) / 2
    fit = any(np.all(c >= np.array(z[:3])) and np.all(c <= np.array(z[3:])) for z in lead)
    raw = pr.outline
    if not fit and pocket:                         # pocket corners: the part's inside corner gets fillet_in_r
        turn = csg_mesh.corner_turn(raw)
        radii = [min(P.fillet_in_r, csg_mesh.max_corner_r(raw, i)) if turn[i] > 20.0 else 0.0
                 for i in range(len(raw))]
        raw = csg_mesh.round_outline(raw, radii)
    outline = csg_mesh.densify(raw, 0.5)
    m = csg_mesh.miters(outline)
    hs = np.arange(pr.h0, pr.h1 + 1e-9, 0.05)
    probe = outline + m * 0.05 / np.linalg.norm(m, axis=1)[:, None]
    W = pr.world(np.repeat(probe[:, 0], len(hs)), np.repeat(probe[:, 1], len(hs)), np.tile(hs, len(outline)))

    def hit(prims, eps=1e-6):
        out = np.zeros(len(W), bool)
        for o in prims:
            lo2, hi2 = o.bbox()
            sel = np.all((W >= lo2 - 0.1) & (W <= hi2 + 0.1), axis=1)
            if sel.any():
                out[sel] |= o.contains(W[sel], eps)
        return out
    inside = (hit(joins) & ~hit(cuts, -1e-6)).reshape(len(outline), len(hs))     # material left so far

    def hit_pts(Q):
        a_ = np.zeros(len(Q), bool)
        c_ = np.zeros(len(Q), bool)
        for o in joins:
            a_ |= o.contains(Q)
        for o in cuts:
            c_ |= o.contains(Q, eps=-1e-6)
        return a_ & ~c_
    rect = Polygon(pr.outline).minimum_rotated_rectangle
    e = np.diff(np.asarray(rect.exterior.coords), axis=0)
    width = float(np.linalg.norm(e, axis=1).min())
    mouths = []                                    # per column: (bottom mouth, top mouth, depth) or None
    for j in range(len(outline)):
        idx = np.nonzero(inside[j])[0]
        if not len(idx):
            mouths.append(None)
            continue
        a, b = hs[idx[0]], hs[idx[-1]]
        mouths.append((None if idx[0] == 0 else a, None if idx[-1] == len(hs) - 1 else b, b - a))
    ok = [mo for mo in mouths if mo]
    if not ok:
        return outline, [[(0.0, pr.h0), (0.0, pr.h1)] for _ in outline], dict(kind="cut", flare=None)
    depth = min(mo[2] for mo in ok)
    bot = [mo[0] for mo in ok if mo[0] is not None]
    top = [mo[1] for mo in ok if mo[1] is not None]
    a_ref = float(np.median(bot)) if bot else pr.h0 + 0.02
    b_ref = float(np.median(top)) if top else pr.h1 - 0.02

    def refine(h_in, h_out, j):                    # bisect the face between a grid point inside and out
        for _ in range(8):
            hm = (h_in + h_out) / 2
            if hit_pts(pr.world([probe[j, 0]], [probe[j, 1]], [hm]))[0]:
                h_in = hm
            else:
                h_out = hm
        return (h_in + h_out) / 2
    if bot:
        j = min((abs(mo[0] - a_ref), j) for j, mo in enumerate(mouths) if mo and mo[0] is not None)[1]
        a_ref = refine(mouths[j][0], mouths[j][0] - 0.05, j)
    if top:
        j = min((abs(mo[1] - b_ref), j) for j, mo in enumerate(mouths) if mo and mo[1] is not None)[1]
        b_ref = refine(mouths[j][1], mouths[j][1] + 0.05, j)
    snap = [None if not mo else (None if mo[0] is None else (a_ref if abs(mo[0] - a_ref) < 0.11 else mo[0]),
                                 None if mo[1] is None else (b_ref if abs(mo[1] - b_ref) < 0.11 else mo[1]))
            for mo in mouths]

    def thickness(hm, j):                          # material beside the tool wall at a mouth
        ts = np.arange(0.05, 6.0, 0.1)
        q = outline[j] + m[j] / np.linalg.norm(m[j]) * ts[:, None]
        ins = hit_pts(pr.world(q[:, 0], q[:, 1], np.full(len(ts), hm)))
        return ts[np.argmin(ins)] if not ins.all() else 6.0

    cols_b = [j for j, s in enumerate(snap) if s and s[0] is not None]
    cols_t = [j for j, s in enumerate(snap) if s and s[1] is not None]
    th_b = min([thickness(snap[j][0] + 0.2, j) for j in cols_b[::4]] or [6.0])
    th_t = min([thickness(snap[j][1] - 0.2, j) for j in cols_t[::4]] or [6.0])

    def size(face, th):
        if fit:
            f, kd = P.lead_in_r, "chamfer"
        elif face == "bed":
            f, kd = P.bed_chamfer, "chamfer"
        else:
            f, kd = P.edge_r, "round"
        return kd, max(0.05, min(f, 0.3 * width, 0.4 * depth, 0.4 * th))
    kb, fb = size("bed" if bot and max(abs(v) for v in bot) < 0.06 else "face", th_b)
    kt, ft = size("face", th_t)
    pb, pt = csg_mesh.mouth_profile(kb, fb, k), csg_mesh.mouth_profile(kt, ft, k)
    sb, st = (0.0 if kb == "chamfer" else 0.025 * fb), (0.0 if kt == "chamfer" else 0.025 * ft)
    # an end that stops inside the material (a pocket floor) is rounded: an inside fillet in the part
    rin = 0.0 if fit or not pocket else min(P.fillet_in_r, 0.4 * depth, 0.45 * width)
    pin = csg_mesh.cap_profile("round", rin) if rin > 0.1 else None
    cols = []
    for s in snap:                                 # rounds sunk 2.5 % into the air: no tangent slivers
        a = s[0] if s else None
        b = s[1] if s else None
        if a is None and s and pin and len(pin) == k + 1:
            col = [(rin, pr.h0)] + [(d, pr.h0 + h) for d, h in pin]
        else:
            col = [(-(fb + 0.3) if a is not None else 0.0, pr.h0)]
            base = a - sb if a is not None else a_ref
            col += [(d if a is not None else 0.0, base + dh) for d, dh in pb]
        if b is None and s and pin and len(pin) == k + 1:
            col += [(d, pr.h1 - h) for d, h in reversed(pin)] + [(rin, pr.h1)]
        else:
            roof = b + st if b is not None else b_ref
            col += [(d if b is not None else 0.0, roof - dh) for d, dh in reversed(pt)]
            col.append((-(ft + 0.3) if b is not None else 0.0, pr.h1))
        hh = np.array([h for _, h in col]) + np.arange(len(col)) * 1e-4
        hh = np.maximum.accumulate(hh)
        cols.append([(d, float(h)) for (d, _), h in zip(col, hh)])
    return outline, cols, dict(kind="cut", flare=[kb, round(fb, 3), kt, round(ft, 3)], fit=fit)


def build_job(prims, P, hull, lead, corner, keep_out=(), f_in=None, no_fillet=(), fillets=True):
    """List of boolean steps [{op, V, F}] in the replay order, a log per primitive, and the
    fillet vertices of each primitive (to find which fillet a defect belongs to). Join
    primitives carry their fillet feet; fillet strips follow them as extra joins; primitives in
    no_fillet get none."""
    f_in = f_in or P.fillet_in_r
    joins = [p for p in prims if p.op == "join"]
    steps, log, fil = [], [], {}
    for i, pr in enumerate(prims):
        extra = []
        if pr.op == "join":
            others = [o for o in joins if o is not pr]
            outline, caps, info = plan_prim(pr, others, P, hull, lead, corner)
            if fillets and info["kind"] != "lead_in":
                extra = [(k, m) for k, m in enumerate(csg_fillet.strips(pr, outline, caps, others, f_in))
                         if f"{i}:s{k}" not in no_fillet]
                info["strips"] = len(extra)
            if not fillets or info["kind"] == "lead_in" or f"{i}:feet" in no_fillet:   # fits: no fillet
                if extra:                      # strips need the square ends of feet(), with no foot
                    outline, cols, _ = csg_fillet.feet(pr, outline, caps, others, keep_out, P, 0.0)
                else:
                    outline, cols = columns(pr, outline, caps)
                info["fillet"] = 0.0
            else:
                outline, cols, info["fillet"] = csg_fillet.feet(pr, outline, caps, others, keep_out, P, f_in,
                                                                square=bool(extra))
        else:
            pocket = fillets and f"{i}:pocket" not in no_fillet
            outline, cols, info = plan_tool(pr, [o for o in prims[:i] if o.op == "join"],
                                            [o for o in prims[:i] if o.op == "cut"], P, lead, pocket=pocket)
        V, F = csg_mesh.tool_mesh(pr, outline, cols)
        steps.append(dict(op=pr.op, V=np.round(V, 5).tolist(), F=F))
        if pr.op == "cut" and pocket and not info.get("fit"):
            fil[f"{i}:pocket"] = V                  # rounded pocket ends and corners (inside fillets)
        if pr.op == "join":
            neg = np.array([[d < -0.01 for d, _ in c] for c in cols]).T.ravel()   # (ring, column) order
            if neg.any():
                fil[f"{i}:feet"] = V[neg]
            for k, (Vs, _) in extra:
                fil[f"{i}:s{k}"] = Vs
        for _, (Vs, Fs) in extra:
            steps.append(dict(op="join", V=np.round(Vs, 5).tolist(), F=Fs))
        info["index"] = i
        log.append(info)
    return steps, log, fil


def footprint_hull(tris):
    v = tris.reshape(-1, 3)
    pts = sorted({(round(a, 3), round(b, 3)) for a, b, c in v if abs(c) < 1e-3})
    if len(pts) < 3:
        return np.zeros((0, 2))

    def cross(o, a, b):
        return (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])
    lo, up = [], []
    for q in pts:
        while len(lo) >= 2 and cross(lo[-2], lo[-1], q) <= 0:
            lo.pop()
        lo.append(q)
    for q in reversed(pts):
        while len(up) >= 2 and cross(up[-2], up[-1], q) <= 0:
            up.pop()
        up.append(q)
    return np.array(lo[:-1] + up[:-1])
