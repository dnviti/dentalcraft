"""Replay a part's SolidCraft command list as solid primitives in the print frame.

A primitive is an extrusion: 2D outline (CCW) in the plane (O, u, v), from h0 to h1 along
n = u x v, optionally tapered (outline scale s1 at h1). op is "join" or "cut". Boxes are
extruded along their print-frame Z (every box is axis-aligned in its print frame)."""
import math

import numpy as np
import shapely
from shapely.geometry import Polygon


def circle(rad, n):
    a = np.linspace(0, 2 * math.pi, n, endpoint=False)
    return np.column_stack([rad * np.cos(a), rad * np.sin(a)])


def basis(n):
    n = np.asarray(n, float) / np.linalg.norm(n)
    t = np.array([1.0, 0, 0]) if abs(n[0]) < 0.9 else np.array([0, 1.0, 0])
    u = np.cross(t, n)
    u /= np.linalg.norm(u)
    return u, np.cross(n, u), n


def ccw(poly):
    poly = np.asarray(poly, float)
    x, y = poly[:, 0], poly[:, 1]
    area = 0.5 * np.sum(x * np.roll(y, -1) - np.roll(x, -1) * y)
    return poly if area > 0 else poly[::-1]


class Prim:
    def __init__(self, op, kind, O, u, v, outline, h0, h1, s1=1.0):
        self.op, self.kind = op, kind
        self.O, self.u, self.v = (np.asarray(a, float) for a in (O, u, v))
        self.n = np.cross(self.u, self.v)
        self.outline = ccw(outline)
        self.h0, self.h1, self.s1 = float(h0), float(h1), float(s1)
        self.poly = Polygon(self.outline).buffer(0)
        shapely.prepare(self.poly)

    def transform(self, M):
        R, t = M[:, :3], M[:, 3]
        self.O = R @ self.O + t
        self.u, self.v, self.n = R @ self.u, R @ self.v, R @ self.n

    def local(self, p):
        d = np.asarray(p, float) - self.O
        return np.stack([d @ self.u, d @ self.v, d @ self.n], axis=-1)

    def world(self, x, y, h):
        return self.O + np.outer(x, self.u) + np.outer(y, self.v) + np.outer(h, self.n)

    def contains(self, pts, eps=1e-6):
        """Points inside the raw (unrounded) primitive."""
        q = self.local(np.atleast_2d(pts))
        ok = (q[:, 2] >= self.h0 - eps) & (q[:, 2] <= self.h1 + eps)
        s = 1.0 + (self.s1 - 1.0) * (q[:, 2] - self.h0) / max(self.h1 - self.h0, 1e-9)
        return ok & shapely.intersects_xy(self.poly, q[:, 0] / s, q[:, 1] / s)

    def bbox(self):
        pts = []
        for h, s in ((self.h0, 1.0), (self.h1, self.s1)):
            pts.append(self.world(self.outline[:, 0] * s, self.outline[:, 1] * s, np.full(len(self.outline), h)))
        pts = np.vstack(pts)
        return pts.min(0), pts.max(0)


def _box(op, p):
    lo = np.array(p["corner"], float)
    sz = np.array([p["length"], p["width"], p["height"]], float)
    rect = [[lo[0], lo[1]], [lo[0] + sz[0], lo[1]], [lo[0] + sz[0], lo[1] + sz[1]], [lo[0], lo[1] + sz[1]]]
    return Prim(op, "box", [0, 0, 0], [1, 0, 0], [0, 1, 0], rect, lo[2], lo[2] + sz[2])


def _cyl(op, p, seg_len=0.35):
    rad = p["diameter"] / 2
    u, v, n = basis(p["axis"])
    nseg = max(32, int(math.ceil(2 * math.pi * rad / seg_len)) // 4 * 4)
    return Prim(op, "cyl", p["base"], u, v, circle(rad, nseg), 0.0, p["height"])


def _arc(c, rad, a0, a1, n):
    a = np.radians(np.linspace(a0, a1, n))
    return np.column_stack([c[0] + rad * np.cos(a), c[1] + rad * np.sin(a)])


def _arc3(s, e, t, seg_len=0.35):
    """Points of the circular arc start -> through -> end (without the end point)."""
    s, e, t = (np.asarray(q, float) for q in (s, e, t))
    A = np.array([[e[0] - s[0], e[1] - s[1]], [t[0] - s[0], t[1] - s[1]]]) * 2
    b = np.array([e @ e - s @ s, t @ t - s @ s])
    c = np.linalg.solve(A, b)
    rad = np.linalg.norm(s - c)
    ang = [math.degrees(math.atan2(*(q - c)[::-1])) for q in (s, t, e)]
    a0, at, a1 = ang
    d1 = (a1 - a0) % 360
    dt = (at - a0) % 360
    sweep = d1 if dt <= d1 else d1 - 360
    n = max(8, int(abs(math.radians(sweep)) * rad / seg_len))
    return _arc(c, rad, a0, a0 + sweep, n + 1)[:-1]


def replay(cmds, nth=1):
    """Primitives of a part in the frame of its nth file.export (1: print frame, 2: assembly)."""
    prims, sketch, out = [], None, None
    for c in cmds:
        k, p = c["command"], c["params"]
        op = {"new": "join"}.get(p.get("operation"), p.get("operation"))
        if k == "solid.box":
            prims.append(_box(op, p))
        elif k == "solid.cylinder":
            prims.append(_cyl(op, p))
        elif k == "solid.cone":
            pr = _cyl(op, {"diameter": p["diameter"], "base": p["base"], "axis": [0, 0, 1], "height": p["height"]})
            pr.s1 = p["top_diameter"] / p["diameter"]
            pr.kind = "cone"
            prims.append(pr)
        elif k == "sketch.create":
            pl = p["plane"]
            sketch = dict(O=pl["origin"], u=pl["x_dir"], v=pl["y_dir"], pts=[])
        elif k == "sketch.line":
            sketch["pts"] += [list(q) for q in p["points"]]
        elif k == "sketch.arc.three_point":
            sketch["pts"] += _arc3(p["start"], p["end"], p["through"]).tolist()
        elif k == "solid.extrude":
            d = p["distance"]
            h0, h1 = (-d / 2, d / 2) if p.get("direction") == "symmetric" else (0.0, d)
            prims.append(Prim(op, "prism", sketch["O"], sketch["u"], sketch["v"], sketch["pts"], h0, h1))
        elif k == "solid.move":
            M = np.array(p["matrix"], float)
            for pr in prims:
                pr.transform(M)
        elif k == "file.export":
            nth -= 1
            if nth == 0:
                out = prims
                break
    return out
