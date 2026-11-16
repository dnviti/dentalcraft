"""Minimal STL I/O and mesh checks with numpy (no external mesh library)."""
import struct

import numpy as np


def read_stl(path):
    """Return triangles as an (n, 3, 3) float64 array."""
    with open(path, "rb") as f:
        data = f.read()
    if len(data) >= 84:
        n = struct.unpack_from("<I", data, 80)[0]
        if len(data) == 84 + 50 * n:
            rec = np.frombuffer(data, dtype=np.dtype([("n", "<f4", 3), ("v", "<f4", (3, 3)), ("a", "<u2")]),
                                count=n, offset=84)
            return rec["v"].astype(np.float64)
    tris, cur = [], []
    for line in data.decode("ascii", "replace").splitlines():
        w = line.split()
        if w and w[0] == "vertex":
            cur.append([float(x) for x in w[1:4]])
            if len(cur) == 3:
                tris.append(cur)
                cur = []
    return np.array(tris, dtype=np.float64)


def write_stl(path, tris, name="part"):
    tris = np.asarray(tris, dtype=np.float64)
    nrm = np.cross(tris[:, 1] - tris[:, 0], tris[:, 2] - tris[:, 0])
    ln = np.linalg.norm(nrm, axis=1, keepdims=True)
    nrm = np.divide(nrm, ln, out=np.zeros_like(nrm), where=ln > 0)
    rec = np.zeros(len(tris), dtype=np.dtype([("n", "<f4", 3), ("v", "<f4", (3, 3)), ("a", "<u2")]))
    rec["n"], rec["v"] = nrm, tris
    with open(path, "wb") as f:
        f.write(name.encode()[:80].ljust(80, b"\0"))
        f.write(struct.pack("<I", len(tris)))
        f.write(rec.tobytes())


def transform(tris, M):
    M = np.asarray(M, float)
    return tris @ M[:3, :3].T + M[:3, 3]


def bbox(tris):
    v = tris.reshape(-1, 3)
    return v.min(0), v.max(0)


def volume(tris):
    return float(np.einsum("ij,ij->i", tris[:, 0], np.cross(tris[:, 1], tris[:, 2])).sum() / 6.0)


def topology(tris, tol=1e-5):
    """Edge-manifold and watertight check after welding vertices on a tol grid (the STL writers
    share vertices bit-exactly; a coarser grid would weld the sub-micron facets of boolean seams
    into false defects).

    Returns dict(watertight, manifold, oriented, open_edges, nonmanifold_edges,
    flipped_edges, shells, degenerate)."""
    v = tris.reshape(-1, 3)
    key = np.round(v / tol).astype(np.int64)
    _, inv = np.unique(key, axis=0, return_inverse=True)
    f = inv.reshape(-1, 3)
    degenerate = int(((f[:, 0] == f[:, 1]) | (f[:, 1] == f[:, 2]) | (f[:, 0] == f[:, 2])).sum())
    f = f[(f[:, 0] != f[:, 1]) & (f[:, 1] != f[:, 2]) & (f[:, 0] != f[:, 2])]
    he = np.concatenate([f[:, [0, 1]], f[:, [1, 2]], f[:, [2, 0]]])
    und = np.sort(he, axis=1)
    uniq, cnt = np.unique(und, axis=0, return_counts=True)
    open_e = int((cnt == 1).sum())
    nonman = int((cnt > 2).sum())
    # orientation: each directed half-edge must appear once
    _, dcnt = np.unique(he, axis=0, return_counts=True)
    flipped = int((dcnt > 1).sum())
    shells = _components(f, int(inv.max()) + 1)
    return dict(watertight=open_e == 0, manifold=nonman == 0, oriented=flipped == 0,
                open_edges=open_e, nonmanifold_edges=nonman, flipped_edges=flipped,
                shells=shells, degenerate=degenerate, triangles=len(f))


def _components(f, nv):
    parent = np.arange(nv)

    def find(a):
        while parent[a] != a:
            parent[a] = parent[parent[a]]
            a = parent[a]
        return a
    for a, b, c in f:
        ra, rb, rc = find(a), find(b), find(c)
        parent[rb] = ra
        parent[find(rc)] = ra
    used = np.unique(f)
    return len({find(i) for i in used})


def section_segments(tris, axis=0, value=0.0):
    """Segments where the plane coord[axis] == value cuts the mesh: (m, 2, 3)."""
    d = tris[:, :, axis] - value
    segs = []
    for tri, dd in zip(tris, d):
        if dd.min() > 0 or dd.max() < 0:
            continue
        pts = []
        for i in range(3):
            a, b = tri[i], tri[(i + 1) % 3]
            da, db = dd[i], dd[(i + 1) % 3]
            if (da > 0) != (db > 0) and da != db:
                pts.append(a + (b - a) * (da / (da - db)))
        if len(pts) == 2:
            segs.append(pts)
    return np.array(segs).reshape(-1, 2, 3)


def ray_hits(tris, origin, direction, tmin=0.0, tmax=np.inf):
    """Distances along the ray where it crosses triangles (Moller-Trumbore)."""
    o, dvec = np.asarray(origin, float), np.asarray(direction, float)
    v0, e1, e2 = tris[:, 0], tris[:, 1] - tris[:, 0], tris[:, 2] - tris[:, 0]
    pv = np.cross(dvec, e2)
    det = np.einsum("ij,ij->i", e1, pv)
    ok = np.abs(det) > 1e-12
    inv = np.where(ok, 1.0 / np.where(ok, det, 1), 0)
    tv = o - v0
    uu = np.einsum("ij,ij->i", tv, pv) * inv
    qv = np.cross(tv, e1)
    vv = (qv @ dvec) * inv
    tt = np.einsum("ij,ij->i", e2, qv) * inv
    hit = ok & (uu >= 0) & (vv >= 0) & (uu + vv <= 1) & (tt >= tmin) & (tt <= tmax)
    return np.sort(tt[hit])


def surface_samples(tris, step=2.0):
    """Points on the mesh surface about `step` apart: vertices, points along every edge, and
    interior points in proportion to each triangle's area (long thin triangles stay cheap)."""
    out = [tris.reshape(-1, 3)]
    for i, j in ((0, 1), (1, 2), (2, 0)):
        a, b = tris[:, i], tris[:, j]
        k = np.ceil(np.linalg.norm(b - a, axis=1) / step).astype(int)
        frac = np.concatenate([np.arange(1, n) / n for n in k]) if len(k) else np.zeros(0)
        idx = np.repeat(np.arange(len(tris)), np.maximum(k - 1, 0))
        out.append(a[idx] + (b[idx] - a[idx]) * frac[:, None])
    area = 0.5 * np.linalg.norm(np.cross(tris[:, 1] - tris[:, 0], tris[:, 2] - tris[:, 0]), axis=1)
    m = np.floor(area / (0.5 * step * step)).astype(int)
    if m.sum():
        rng = np.random.default_rng(0)
        idx = np.repeat(np.arange(len(tris)), m)
        u, v = rng.random(len(idx)), rng.random(len(idx))
        flip = u + v > 1
        u[flip], v[flip] = 1 - u[flip], 1 - v[flip]
        t = tris[idx]
        out.append(t[:, 0] + (t[:, 1] - t[:, 0]) * u[:, None] + (t[:, 2] - t[:, 0]) * v[:, None])
    return np.unique(np.round(np.vstack(out), 3), axis=0)


def inside_mesh(tris, pts, cell=2.0):
    """Points inside a closed mesh: parity of the crossings of a +Z ray (slightly skewed in XY
    to avoid hitting edges exactly), triangles binned on an XY grid."""
    jit = np.array([1.3e-4, 0.7e-4])
    q = pts[:, :2] + jit
    lo = tris[:, :, :2].min(1)
    hi = tris[:, :, :2].max(1)
    g0 = np.floor(lo.min(0) / cell)
    bins = {}
    ilo = np.floor(lo / cell - g0).astype(int)
    ihi = np.floor(hi / cell - g0).astype(int)
    for t in range(len(tris)):
        for i in range(ilo[t, 0], ihi[t, 0] + 1):
            for j in range(ilo[t, 1], ihi[t, 1] + 1):
                bins.setdefault((i, j), []).append(t)
    out = np.zeros(len(pts), bool)
    for k, (p, z) in enumerate(zip(q, pts[:, 2])):
        cand = bins.get(tuple(np.floor(p / cell - g0).astype(int)), [])
        if not cand:
            continue
        T = tris[cand]
        a, b, c = T[:, 0, :2], T[:, 1, :2], T[:, 2, :2]

        def cr(u, v, w):
            return (v[:, 0] - u[:, 0]) * (w[1] - u[:, 1]) - (v[:, 1] - u[:, 1]) * (w[0] - u[:, 0])
        d1, d2, d3 = cr(a, b, p), cr(b, c, p), cr(c, a, p)
        hit = ((d1 > 0) & (d2 > 0) & (d3 > 0)) | ((d1 < 0) & (d2 < 0) & (d3 < 0))
        if not hit.any():
            continue
        T = T[hit]
        den = d1[hit] + d2[hit] + d3[hit]
        zz = (d2[hit] * T[:, 0, 2] + d3[hit] * T[:, 1, 2] + d1[hit] * T[:, 2, 2]) / den
        out[k] = int((zz > z).sum()) % 2 == 1
    return out
