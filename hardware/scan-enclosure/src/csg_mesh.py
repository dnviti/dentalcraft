"""Closed meshes of pre-rounded primitives: the outline corners are rounded in 2D, each end
cap gets its own profile (flat, 45 deg chamfer or quarter-round), so every edge of the
primitive is rounded in isolation before the boolean union."""
import math

import numpy as np

SEG_DEG = 11.25          # arc tessellation: every facet turns by at most this


def corner_turn(poly):
    """Turning angle (deg) at every vertex of a CCW polygon (positive = convex)."""
    a = poly - np.roll(poly, 1, axis=0)
    b = np.roll(poly, -1, axis=0) - poly
    cr = a[:, 0] * b[:, 1] - a[:, 1] * b[:, 0]
    dt = np.einsum("ij,ij->i", a, b)
    return np.degrees(np.arctan2(cr, dt))


def max_corner_r(poly, i):
    """Largest radius at corner i that keeps half of each adjacent edge free."""
    p, a, b = poly[i], poly[i - 1], poly[(i + 1) % len(poly)]
    u, v = a - p, b - p
    lu, lv = np.linalg.norm(u), np.linalg.norm(v)
    ang = math.acos(np.clip(u @ v / (lu * lv), -1, 1))
    return 0.5 * min(lu, lv) * math.tan(ang / 2)


def round_outline(poly, radii):
    """Replace corner i by an arc of radius radii[i] (0 = keep it), facets <= SEG_DEG."""
    poly = np.asarray(poly, float)
    out = []
    n = len(poly)
    for i in range(n):
        r = radii[i]
        p, a, b = poly[i], poly[i - 1], poly[(i + 1) % n]
        if r <= 1e-6:
            out.append(p)
            continue
        u, v = (a - p) / np.linalg.norm(a - p), (b - p) / np.linalg.norm(b - p)
        ang = math.acos(np.clip(u @ v, -1, 1))
        t = r / math.tan(ang / 2)
        c = p + (u + v) / np.linalg.norm(u + v) * r / math.sin(ang / 2)
        p0, p1 = p + u * t, p + v * t
        a0, a1 = math.atan2(*(p0 - c)[::-1]), math.atan2(*(p1 - c)[::-1])
        da = (a1 - a0 + math.pi) % (2 * math.pi) - math.pi
        k = max(2, int(math.ceil(abs(math.degrees(da)) / SEG_DEG)))
        for j in range(k + 1):
            th = a0 + da * j / k
            out.append(c + r * np.array([math.cos(th), math.sin(th)]))
    out = np.array(out)
    keep = np.linalg.norm(out - np.roll(out, 1, axis=0), axis=1) > 1e-6
    return out[keep]


def miters(poly):
    """Outward offset vectors (unit offset of both adjacent edges) of a CCW polygon."""
    e = np.roll(poly, -1, axis=0) - poly
    e /= np.linalg.norm(e, axis=1)[:, None]
    nrm = np.column_stack([e[:, 1], -e[:, 0]])          # outward normal of edge i -> i+1
    prev = np.roll(nrm, 1, axis=0)
    m = nrm + prev
    m /= np.einsum("ij,ij->i", m, nrm)[:, None]          # m . n_edge = 1 on both edges
    return m


def cap_profile(kind, r):
    """(inset, height) from the cap face boundary to the side wall (height measured from the cap)."""
    if kind == "flat" or r <= 1e-6:
        return [(0.0, 0.0)]
    if kind == "chamfer":
        return [(r, 0.0), (0.0, r)]
    k = max(2, int(math.ceil(90.0 / SEG_DEG)))
    th = np.radians(np.linspace(0, 90, k + 1))
    return [(r * (1 - math.sin(t)), r * (1 - math.cos(t))) for t in th]


def densify(poly, step=0.5):
    out = []
    for i in range(len(poly)):
        a, b = poly[i], poly[(i + 1) % len(poly)]
        k = max(1, int(np.ceil(np.linalg.norm(b - a) / step)))
        out += [a + (b - a) * j / k for j in range(k)]
    return np.array(out)


def mouth_profile(kind, f, k):
    """k+1 (inset, dh) points of a cut-tool flare from the face (inset -f, dh 0) to the wall
    (inset 0, dh f): a 45 deg chamfer or the tool side of a quarter-round."""
    if kind == "chamfer":
        return [(-f * (1 - j / k), f * j / k) for j in range(k + 1)]
    ps = np.radians(np.linspace(-90, 0, k + 1))
    return [(-f + f * math.cos(p), f + f * math.sin(p)) for p in ps]


def tool_mesh(pr, outline, cols):
    """Closed mesh of one primitive with a per-column profile: cols[j] = [(inset, h), ...], same
    length for all columns, heights increasing; inset > 0 moves the wall in (a round or chamfer),
    inset < 0 out (a fillet foot or a cut-tool flare). Tapered primitives scale the outline."""
    m = miters(outline)
    nr, n = len(cols[0]), len(outline)
    V = np.zeros((nr, n, 3))
    span = max(pr.h1 - pr.h0, 1e-9)
    for j in range(n):
        for i, (d, h) in enumerate(cols[j]):
            s = 1.0 + (pr.s1 - 1.0) * (h - pr.h0) / span
            q = outline[j] * s - m[j] * d
            V[i, j] = pr.world([q[0]], [q[1]], [h])[0]
    F = []
    for i in range(nr - 1):
        a, b = i * n, (i + 1) * n
        for j in range(n):
            k = (j + 1) % n
            F.append([a + j, a + k, b + k, b + j])
    F.append(list(range(n - 1, -1, -1)))
    top = (nr - 1) * n
    F.append(list(range(top, top + n)))
    return V.reshape(-1, 3), F
