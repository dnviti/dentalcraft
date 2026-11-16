"""Inside fillets as solids, unioned with the pre-rounded primitives (no bevel after the union).

1. Fillet feet: a primitive whose end stands on a support face (a flange or rib on a skin, a boss
   or post on a wall, a channel wall on the skin, a key or rib on the base plate) gets a concave
   fillet foot of width f all round its outline at the support face. The width is constant where
   the support is flat (clear of the support's own round) and no other part sits there (keep_out),
   and runs out at slope <= 0.2 where it is not. Two feet that meet form a valley, never a ridge.
2. Fillet strips: an exposed end face of a primitive whose outline edge is buried in a support (a
   gusset side face on the cheek plate and on the foot) gets a straight strip with the concave
   profile along the junction line; at a free end the arc shrinks into the corner over 4 f (the
   end is buried, no end face), at a buried end the strip runs on into the next support.
Every concave arc is sunk 2.5 % of its radius into the air, so it meets both faces at 13 deg
instead of tangentially (tangent booleans leave slivers)."""
import math

import numpy as np
import shapely

import csg_mesh

SINK = 0.025


def inside(prims, W, eps=1e-6):
    out = np.zeros(len(W), bool)
    for o in prims:
        lo, hi = o.bbox()
        sel = np.all((W >= lo - 0.1) & (W <= hi + 0.1), axis=1)
        if sel.any():
            out[sel] |= o.contains(W[sel], eps)
    return out


def feet(pr, outline, caps, others, keep_out, P, f, k=8, square=True):
    """Per-column profiles (cap profile, then the fillet foot where supported); returns
    (outline, cols, widest foot)."""
    outline = csg_mesh.densify(outline, 0.5)
    m = csg_mesh.miters(outline)
    mu = m / np.linalg.norm(m, axis=1)[:, None]
    n = len(outline)
    span = pr.h1 - pr.h0
    s = np.concatenate([[0], np.cumsum(np.linalg.norm(np.diff(outline, axis=0, append=outline[:1]), axis=1))])
    L, s = s[-1], s[:-1]
    dist = np.abs(s[:, None] - s[None, :])
    dist = np.minimum(dist, L - dist)
    nb, prof, fmax = 3, [], 0.0
    r_top = [c[1] if c[0] == "round" else 0.0 for c in caps]
    # columns on an outline edge buried in another primitive keep their end square where that
    # support continues past the end face (a round there would leave a groove along the junction);
    # the round comes back over 8 mm along the outline (a gentle change, no crease)
    hm = [pr.h0 + span * t for t in (0.25, 0.5, 0.75)]
    qb = outline + mu * 0.3
    bur = np.ones(n, bool)
    for h_ in hm:
        bur &= inside(others, pr.world(qb[:, 0], qb[:, 1], np.full(n, h_)))
    for ci, (kind, r) in enumerate(caps):
        if kind == "round":
            hc = pr.h0 - (r + 0.3) if ci == 0 else pr.h1 + (r + 0.3)
            sq = bur & inside(others, pr.world(qb[:, 0], qb[:, 1], np.full(n, hc))) if square else np.zeros(n, bool)
            cfac = np.ones(n)
            if sq.any():
                cfac = np.clip(np.min(np.where(sq, 0.0, 1e9)[None, :] + dist / 8.0, axis=1), 0.0, 1.0)
            p = csg_mesh.cap_profile(kind, r)
            p = p + [(0.0, r + 1e-3 * (i + 1)) for i in range(nb + k + 2 - len(p))]
            prof.append([[(d * cfac[j], h) for d, h in p] for j in range(n)])
            continue
        base = [(0.0, -0.3), (0.0, -0.299), (0.0, -0.298)] if kind == "flat" else \
            csg_mesh.cap_profile(kind, r) + [(0.0, r + 1e-3 * (i + 1)) for i in range(nb - 2)]
        b_end = base[-1][1]
        fw, h_ref = np.zeros(n), np.nan
        ds = np.arange(0.0, 0.6 * span, 0.05)
        hh = pr.h0 + ds if ci == 0 else pr.h1 - ds
        q = outline + mu * 0.3
        W = pr.world(np.repeat(q[:, 0], len(ds)), np.repeat(q[:, 1], len(ds)), np.tile(hh, n))
        ins = inside(others, W).reshape(n, len(ds))
        top = np.array([np.argmin(row) if row[0] and not row.all() else -1 for row in ins])
        hs = np.where(top > 0, ds[np.maximum(top - 1, 0)], np.nan)        # last height inside
        if (~np.isnan(hs)).any():
            h_ref = float(np.nanmedian(hs))
            walled = ins.all(axis=1)                    # the column faces into another feature: its
            ok = (np.abs(hs - h_ref) < 0.11) | walled   # foot is buried there, keep it full (no ramp)
            room = span - h_ref - r_top[1 - ci] - 0.3                       # below the other cap's round
            ts = np.arange(0.3, f + P.edge_r + 0.7, 0.1)
            Q = outline[:, None, :] + mu[:, None, :] * ts[None, :, None]
            X, Y = Q[..., 0].ravel(), Q[..., 1].ravel()

            def at(h):
                return pr.world(X, Y, np.full(len(X), pr.h0 + h if ci == 0 else pr.h1 - h))
            sup = inside(others, at(h_ref - 0.1)).reshape(n, len(ts))      # flat support beside the wall
            flat = np.where(sup.all(axis=1), ts[-1], ts[np.argmin(sup, axis=1)]) - P.edge_r - 0.2
            blk = inside(keep_out, at(h_ref + 0.2)).reshape(n, len(ts))     # another part sits there
            free = np.where(blk.any(axis=1), ts[np.argmax(blk, axis=1)] - 0.3, ts[-1])
            fw = np.where(ok, np.clip(np.where(walled, f, np.minimum(flat, free)), 0.0, max(min(f, room), 0.0)), 0.0)
            if room < 0.3:                     # the other cap's round reaches the support: no foot
                fw[:], h_ref = 0.0, np.nan
            fw = np.minimum(np.min(fw[None, :] + 0.2 * dist, axis=1), f)
        fmax = max(fmax, float(fw.max()))
        hf = h_ref if not np.isnan(h_ref) else b_end + 0.06
        p_cols = []
        for j in range(n):                     # same ring structure in every column, width fw[j]
            fj = max(fw[j], 0.05)
            sk = SINK * fj
            fl = [(-fj, hf - sk - 0.1)] + [(d, hf - sk + dh) for d, dh in csg_mesh.mouth_profile("round", fj, k)]
            if fw[j] < 0.05:
                fl = [(0.0, h) for _, h in fl]
            p_cols.append(base + fl)
        prof.append(p_cols)
    cols = []
    for j in range(n):
        col = [(d, pr.h0 + h) for d, h in prof[0][j]] + [(d, pr.h1 - h) for d, h in reversed(prof[1][j])]
        hs_ = np.maximum.accumulate(np.array([h for _, h in col]) + np.arange(len(col)) * 1e-5)
        cols.append([(d, float(h)) for (d, _), h in zip(col, hs_)])
    return outline, cols, fmax


def _profile(f, e=0.3, k=8):
    """Strip cross-section in (u, v): u out of the end face, v out of the support face. The
    concave arc (centre (f, f), radius 1.025 f) runs from the support face to the end face;
    the section reaches e into both."""
    R = f * (1 + SINK)
    a = f - math.sqrt(R * R - f * f)                      # where the arc crosses each face
    t0, t1 = math.atan2(-f, a - f), math.atan2(a - f, -f)
    arc = [(f + R * math.cos(t), f + R * math.sin(t)) for t in np.linspace(t0, t1, k + 1)]
    return np.array([(-e, -e), (a, -e)] + arc + [(-e, a)])


def _scaled(prof, s):
    """Profile with its exposed part (the arc and its two face points) scaled about the corner
    line; the buried corner (-e, -e) stays. At s = 0 the arc points sit just inside the corner,
    so the strip ends buried, without an end face or an apex."""
    q = prof.copy()
    if s > 1e-6:
        q[1:] *= s
        q[1, 1], q[-1, 0] = prof[1, 1], prof[-1, 0]       # (a s, -e) and (-e, a s)
        return q
    q[1] = (0.0, prof[1, 1])
    q[-1] = (prof[-1, 0], 0.0)
    for i in range(2, len(q) - 1):
        q[i] = (-1e-3 * (i - 1), -1e-3 * (i - 1))
    return q


def strips(pr, outline, caps, others, f, n_t=12):
    """Fillet strips where an exposed end face of `pr` meets the support its outline edge is
    buried in. Returns a list of (V, F) closed meshes."""
    out = []
    raw = pr.outline
    nr = len(raw)
    buried = []
    for i in range(nr):                       # outline edge i -> i+1 buried in a support?
        a, b = raw[i], raw[(i + 1) % nr]
        e = (b - a) / np.linalg.norm(b - a)
        m = np.array([e[1], -e[0]])
        mids = [a + (b - a) * t + m * 0.2 for t in (0.3, 0.5, 0.7)]
        hm = (pr.h0 + pr.h1) / 2
        W = np.vstack([pr.world([p[0]], [p[1]], [hm]) for p in mids])
        buried.append(bool(inside(others, W).all()))
    prof = _profile(f)
    for ci, (kind, _) in enumerate(caps):
        if kind != "round":
            continue
        h = pr.h0 if ci == 0 else pr.h1
        nc = -pr.n if ci == 0 else pr.n                          # out of the end face
        for i in range(nr):
            if not buried[i]:
                continue
            a, b = raw[i], raw[(i + 1) % nr]
            e2 = (b - a) / np.linalg.norm(b - a)
            m2 = np.array([e2[1], -e2[0]])
            # support face: march inwards from the edge until the probe leaves the support (at
            # several points along the edge: other features may stand on the same face)
            def probe(tt, d):
                p = a + (b - a) * tt - m2 * d
                return inside(others, pr.world([p[0]], [p[1]], [h]) + nc * 0.1)[0]
            sface = None
            for tt in (0.15, 0.35, 0.5, 0.65, 0.85):
                for d in np.arange(0.0, 3.0, 0.05):
                    if not probe(tt, d):
                        lo_, hi_ = max(d - 0.05, 0.0), d       # bisect the support face
                        for _ in range(10):
                            mid_ = (lo_ + hi_) / 2
                            lo_, hi_ = (mid_, hi_) if probe(tt, mid_) else (lo_, mid_)
                        sface = lo_ if sface is None else min(sface, lo_)
                        break
            if sface is None:
                continue
            sface -= 0.005                                      # the strip foot on the support face
            sup = [a + (b - a) * tt + m2 * 0.3 for tt in (0.15, 0.5, 0.85)]   # support beside the face
            if not any(inside(others, pr.world([p[0]], [p[1]], [h]) + nc * (f + 0.5))[0] for p in sup):
                continue
            A = pr.world([a[0] - m2[0] * sface], [a[1] - m2[1] * sface], [h])[0]
            B = pr.world([b[0] - m2[0] * sface], [b[1] - m2[1] * sface], [h])[0]
            m3 = pr.u * m2[0] + pr.v * m2[1]                    # into the support (world)
            ev = (B - A) / np.linalg.norm(B - A)
            # ends: run on into the next support (buried neighbour) or taper to a point (free end)
            ends = []
            for end, nb in ((A, buried[i - 1]), (B, buried[(i + 1) % nr])):
                ends.append("run" if nb else "taper")
            Lt = 4.0 * f
            # a free end stops where the face still stands f + its own round + 0.5 above the junction
            # (an acute gusset tip rounds away below that)
            Le = np.linalg.norm(b - a)
            reach = sface + f + 2.0

            def back(p0, d0):
                for t_ in np.arange(0.5, Le, 0.25):
                    q_ = p0 + d0 * t_ - m2 * reach
                    if pr.poly.contains(shapely.Point(q_[0], q_[1])):
                        return t_
                return Le
            tA = -f - 0.5 if ends[0] == "run" else back(a, e2)
            tB = Le + f + 0.5 if ends[1] == "run" else Le - back(b, -e2)
            if tB - tA < 2.0 * f:
                continue
            ts = np.linspace(tA, tB, n_t * 4)
            sc = np.ones(len(ts))
            if ends[0] == "taper":
                sc = np.minimum(sc, np.clip((ts - tA) / Lt, 0, 1))
            if ends[1] == "taper":
                sc = np.minimum(sc, np.clip((tB - ts) / Lt, 0, 1))
            V, F, ring = [], [], len(prof)
            for t, s_ in zip(ts, sc):
                c = A + ev * t
                q = _scaled(prof, s_)
                V.append(c + np.outer(q[:, 0], nc) + np.outer(q[:, 1], -m3))
            idx, starts = 0, []
            for v_ in V:
                starts.append(idx)
                idx += len(v_)
            for j in range(len(V) - 1):
                a0, a1 = starts[j], starts[j + 1]
                for q in range(ring):
                    q1 = (q + 1) % ring
                    F.append([a0 + q, a0 + q1, a1 + q1, a1 + q])
            F.append(list(range(ring - 1, -1, -1)))
            F.append(list(range(starts[-1], starts[-1] + ring)))
            V = np.vstack(V)
            if _volume(V, F) < 0:
                F = [f_[::-1] for f_ in F]
            out.append((V, F))
    return out


def _volume(V, F):
    vol = 0.0
    for f_ in F:
        for j in range(1, len(f_) - 1):
            vol += np.dot(V[f_[0]], np.cross(V[f_[j]], V[f_[j + 1]])) / 6.0
    return vol
