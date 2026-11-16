"""Joint features applied to one part: insert bosses and holes, clearance holes, dowels.

Every insert hole uses the shared insert spec (params.insert_spec): hole_d x hole_depth,
boss_d around it, boss_len (hole depth + floor) along the axis."""
import numpy as np

from sc import to_local, dir_local


def apply_joints(part, name, js, P, M=None, web=None):
    """Cut/join the features of every joint touching `name`.

    M: 3x4 local->world matrix of the frame the part is built in (None = world).
    web(p_local, a_local, boss_d, boss_len): panels add a web from the skin up to a
    flange boss, so the boss prints without overhang."""
    def L(p):
        return np.asarray(p, float) if M is None else to_local(M, p)

    def D(a):
        return np.asarray(a, float) if M is None else dir_local(M, a)

    holes = []
    for j in js:
        if name not in (j["clear"], j["insert"]):
            continue
        p, a = L(j["p"]), D(j["a"])
        s = P.inserts[j["thread"]]
        if j["insert"] == name:
            if j["kind"] == "dowel":
                part.cyl(p, -a, P.dowel_d, P.dowel_h, op="join")
                continue
            if j["boss"] == "post":                       # standoff / post rising from a plate
                part.cyl(p, a, s["boss_d"], j["post_h"] + 0.5, op="join")
            elif j["boss"] == "skin" or (j["boss"] == "flange" and not web):
                part.cyl(p, a, s["boss_d"], s["boss_len"], op="join")
            elif j["boss"] == "flange":
                web(p, a, s["boss_d"], s["boss_len"])
            holes.append((p - a * 1.0, a, s["hole_d"], s["hole_depth"] + 1.0))
        else:
            if j["kind"] == "dowel":
                holes.append((p - a * (j["clamp"] + 1.0), a, P.dowel_d + 2 * P.dowel_fit, j["clamp"] + 2.0))
            elif j["kind"] == "screw":
                holes.append((p - a * (j["clamp"] + 1.0), a, P.m3_clear, j["clamp"] + 2.0))
    for base, a, d, h in holes:      # drill after every boss is in place
        part.cyl(base, a, d, h, op="cut")


def sector(r0, r1, a0, a1, n=12):
    """Annular sector polygon (degrees), CCW."""
    a = np.radians(np.linspace(a0, a1, n + 1))
    outer = np.column_stack([r1 * np.cos(a), r1 * np.sin(a)])
    inner = np.column_stack([r0 * np.cos(a[::-1]), r0 * np.sin(a[::-1])])
    return np.vstack([outer, inner])


def rounded_polygon(poly, r, seg=6):
    """Polygon with every corner replaced by an arc of radius r (smaller where an edge is short)."""
    poly = np.asarray(poly, float)
    n = len(poly)
    out = []
    for i in range(n):
        p, a, b = poly[i], poly[i - 1], poly[(i + 1) % n]
        u, v = a - p, b - p
        lu, lv = np.linalg.norm(u), np.linalg.norm(v)
        u, v = u / lu, v / lv
        ang = np.arccos(np.clip(u @ v, -1, 1))
        rr = min(r, 0.45 * min(lu, lv) * np.tan(ang / 2))
        t = rr / np.tan(ang / 2)                       # tangent distance from the corner
        bis = (u + v) / np.linalg.norm(u + v)
        c = p + bis * rr / np.sin(ang / 2)
        p0, p1 = p + u * t, p + v * t
        a0, a1 = np.arctan2(*(p0 - c)[::-1]), np.arctan2(*(p1 - c)[::-1])
        da = (a1 - a0 + np.pi) % (2 * np.pi) - np.pi
        for k in range(seg + 1):
            th = a0 + da * k / seg
            out.append(c + rr * np.array([np.cos(th), np.sin(th)]))
    return np.array(out)
