"""Sharp-edge analysis of a print mesh (bed = Z 0)."""
import numpy as np


def sharp_convex_edges(tris, sharp_deg=30.0, tol=1e-3):
    """Mesh edges whose two faces turn by more than sharp_deg and that are convex.

    Returns arrays (p0, p1, angle_deg) per edge."""
    v = tris.reshape(-1, 3)
    key = np.round(v / tol).astype(np.int64)
    uniq, inv = np.unique(key, axis=0, return_inverse=True)
    verts = np.zeros((len(uniq), 3))
    verts[inv.ravel()] = v
    f = inv.reshape(-1, 3)
    ok = (f[:, 0] != f[:, 1]) & (f[:, 1] != f[:, 2]) & (f[:, 0] != f[:, 2])
    f = f[ok]
    n = np.cross(verts[f[:, 1]] - verts[f[:, 0]], verts[f[:, 2]] - verts[f[:, 0]])
    ln = np.linalg.norm(n, axis=1)
    good = ln > 1e-10
    f, n = f[good], n[good] / ln[good][:, None]
    he = np.concatenate([f[:, [0, 1]], f[:, [1, 2]], f[:, [2, 0]]])
    fid = np.tile(np.arange(len(f)), 3)
    key = he[:, 0] * (len(verts) + 1) + he[:, 1]
    rkey = he[:, 1] * (len(verts) + 1) + he[:, 0]
    order = np.argsort(key)
    pos = np.searchsorted(key[order], rkey)
    pos = np.clip(pos, 0, len(order) - 1)
    match = key[order][pos] == rkey
    a = np.nonzero(match & (he[:, 0] < he[:, 1]))[0]
    b = order[pos[a]]
    n1, n2 = n[fid[a]], n[fid[b]]
    ang = np.degrees(np.arccos(np.clip(np.einsum("ij,ij->i", n1, n2), -1, 1)))
    d = verts[he[a, 1]] - verts[he[a, 0]]
    convex = np.einsum("ij,ij->i", np.cross(n1, n2), d) > 0
    sel = (ang > sharp_deg) & convex
    return verts[he[a[sel], 0]], verts[he[a[sel], 1]], ang[sel]


def concave_edges(tris, lo_deg=60.0, hi_deg=120.0, tol=1e-3):
    """Concave mesh edges whose faces turn by lo..hi deg: (p0, p1, n1, n2), n = outward face normals."""
    v = tris.reshape(-1, 3)
    key = np.round(v / tol).astype(np.int64)
    uniq, inv = np.unique(key, axis=0, return_inverse=True)
    verts = np.zeros((len(uniq), 3))
    verts[inv.ravel()] = v
    f = inv.reshape(-1, 3)
    f = f[(f[:, 0] != f[:, 1]) & (f[:, 1] != f[:, 2]) & (f[:, 0] != f[:, 2])]
    n = np.cross(verts[f[:, 1]] - verts[f[:, 0]], verts[f[:, 2]] - verts[f[:, 0]])
    ln = np.linalg.norm(n, axis=1)
    good = ln > 1e-10
    f, n = f[good], n[good] / ln[good][:, None]
    he = np.concatenate([f[:, [0, 1]], f[:, [1, 2]], f[:, [2, 0]]])
    fid = np.tile(np.arange(len(f)), 3)
    key = he[:, 0] * (len(verts) + 1) + he[:, 1]
    rkey = he[:, 1] * (len(verts) + 1) + he[:, 0]
    order = np.argsort(key)
    pos = np.clip(np.searchsorted(key[order], rkey), 0, len(order) - 1)
    match = key[order][pos] == rkey
    a = np.nonzero(match & (he[:, 0] < he[:, 1]))[0]
    b = order[pos[a]]
    n1, n2 = n[fid[a]], n[fid[b]]
    ang = np.degrees(np.arccos(np.clip(np.einsum("ij,ij->i", n1, n2), -1, 1)))
    d = verts[he[a, 1]] - verts[he[a, 0]]
    concave = np.einsum("ij,ij->i", np.cross(n1, n2), d) < 0
    sel = (ang >= lo_deg) & (ang <= hi_deg) & concave
    return verts[he[a[sel], 0]], verts[he[a[sel], 1]], n1[sel], n2[sel]


def classify(p0, p1, ang, P, lead_boxes):
    """Split sharp convex edges into exempt (bed chamfer, fit lead-ins) and the rest."""
    mid = (p0 + p1) / 2
    bed = (np.maximum(p0[:, 2], p1[:, 2]) <= P.bed_chamfer + 0.02)
    fit = np.zeros(len(mid), bool)
    for b in lead_boxes:
        fit |= np.all((mid >= np.array(b[:3]) - 1e-6) & (mid <= np.array(b[3:]) + 1e-6), axis=1)
    fit &= ~bed
    rest = ~(bed | fit)
    return dict(bed=int(bed.sum()), fit=int(fit.sum()), other=int(rest.sum()), other_mid=mid[rest])
