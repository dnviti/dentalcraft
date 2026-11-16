"""Part-level checks for validate.py: rib outline, joints and inserts, iron access, feet,
rounding and sharp edges. Each function returns (lines, failures)."""
import json
import math
import os

import numpy as np

import edges
import meshio
from sc import BUILD


def perp(a):
    a = a / np.linalg.norm(a)
    u = np.cross(a, [1.0, 0, 0] if abs(a[0]) < 0.9 else [0, 1.0, 0])
    u /= np.linalg.norm(u)
    return u, np.cross(a, u)


def outline_loop(tris):
    """Outer boundary (XY polygon) of the faces lying on Z 0, holes filled."""
    on = np.all(np.abs(tris[:, :, 2]) < 1e-4, axis=1)
    f = tris[on][:, :, :2]
    key = np.round(f.reshape(-1, 2) / 1e-4).astype(np.int64)
    uniq, inv = np.unique(key, axis=0, return_inverse=True)
    pts = uniq * 1e-4
    idx = inv.reshape(-1, 3)
    he = np.concatenate([idx[:, [0, 1]], idx[:, [1, 2]], idx[:, [2, 0]]])
    s = {(a, b) for a, b in he}
    bnd = {a: b for a, b in he if (b, a) not in s}
    loops, seen = [], set()
    for a0 in bnd:
        if a0 in seen:
            continue
        loop, a = [], a0
        while a not in seen and a in bnd:
            seen.add(a)
            loop.append(pts[a])
            a = bnd[a]
        if len(loop) > 2:
            loops.append(np.array(loop))

    def area(l):
        return 0.5 * abs(np.dot(l[:, 0], np.roll(l[:, 1], 1)) - np.dot(l[:, 1], np.roll(l[:, 0], 1)))
    return max(loops, key=area)


def dist_outside(poly, q):
    """Distance of points q (n, 2) outside polygon poly (0 inside)."""
    x, y = q[:, 0][:, None], q[:, 1][:, None]
    a, b = poly, np.roll(poly, -1, axis=0)
    cond = (a[:, 1] > y) != (b[:, 1] > y)
    xi = a[:, 0] + (y - a[:, 1]) * (b[:, 0] - a[:, 0]) / np.where(b[:, 1] != a[:, 1], b[:, 1] - a[:, 1], 1)
    inside = (np.sum(cond & (x < xi), axis=1) % 2) == 1
    ab = b - a
    t = np.clip(((q[:, None, :] - a) * ab).sum(-1) / np.maximum((ab * ab).sum(-1), 1e-12), 0, 1)
    d = np.linalg.norm(q[:, None, :] - (a + t[..., None] * ab), axis=-1).min(1)
    return np.where(inside, 0.0, d)


def rib_outline(P, names):
    """Nothing stands outside the outline of the face the part is printed on (raw B-rep mesh).
    Only the panel tongues may (they are the seam alignment)."""
    lines, fails = ["| part | max overhang past its outline (mm) | allowed |", "|---|---|---|"], []
    for n in names:
        t = meshio.read_stl(os.path.join(BUILD, "print_raw", n + ".stl"))
        poly = outline_loop(t)
        v = np.unique(t.reshape(-1, 3).round(4), axis=0)
        d = dist_outside(poly, v[:, :2])
        tongue = (v[:, 2] > 1.0 - 1e-3) & (v[:, 2] < 2.0 + 1e-3) & (d <= P.tongue_l + 0.01)
        bad = d[~tongue].max() if (~tongue).any() else 0.0
        lines.append(f"| {n} | {bad:.2f} | tongue {P.tongue_l:.0f} mm at skin mid-thickness |")
        if bad > 0.01:
            fails.append(f"{n}: material {bad:.2f} mm outside its outline")
    return lines, fails


def joint_checks(P, js, asm):
    """Clearance and insert holes coaxial (+-0.2), insert depth, floor, boss wall, iron access,
    screw length, inserts not crowding each other."""
    lines, fails = [], []
    samples = {n: meshio.surface_samples(m, 1.0) for n, m in asm.items()}
    stats = dict(screw=0, iron_ok=0, iron_bad=0, wall_min=99.0, floor_min=99.0, depth_err=0.0)
    for j in js:
        if j["kind"] == "dowel":
            continue
        p, a = np.array(j["p"]), np.array(j["a"])
        s = P.inserts[j["thread"]]
        ins = asm[j["insert"]]
        u, w = perp(a)
        rh = s["hole_d"] / 2
        # insert hole open over its depth, also 0.2 mm off-axis in four directions
        ok = len(meshio.ray_hits(ins, p - a * 0.2, a, 0.0, s["hole_depth"] - 0.3)) == 0
        for dvec in (u, -u, w, -w):
            ok &= len(meshio.ray_hits(ins, p + dvec * (rh - 0.2) - a * 0.2, a, 0.0, s["hole_depth"] - 0.3)) == 0
        hits = meshio.ray_hits(ins, p - a * 0.2, a, 0.0, 60.0)
        if len(hits) > 1:                       # a ray through a vertex hits several triangles
            hits = hits[np.concatenate([[True], np.diff(hits) > 0.01])]
        depth = hits[0] - 0.2 if len(hits) else 99
        floor = (hits[1] - hits[0]) if len(hits) > 1 else 99
        stats["depth_err"] = max(stats["depth_err"], abs(depth - s["hole_depth"]))
        stats["floor_min"] = min(stats["floor_min"], floor)
        # boss wall: from the hole wall outward at mid depth, 8 directions
        mid = p + a * s["hole_depth"] / 2
        wall = 99.0
        for k in range(8):
            dvec = math.cos(k * math.pi / 4) * u + math.sin(k * math.pi / 4) * w
            h = meshio.ray_hits(ins, mid + dvec * (rh + 0.01), dvec, 0.0, 30.0)
            wall = min(wall, h[0] if len(h) else 30.0)
        stats["wall_min"] = min(stats["wall_min"], wall)
        # clearance side open on the same axis (screw joints; slot joints are checked on the slot)
        if j["kind"] == "screw" and j["clear"] in asm:   # (the control board is not printed)
            cl = asm[j["clear"]]
            rc = P.m3_clear / 2
            for dvec in (np.zeros(3), u * (rc - 0.2), -u * (rc - 0.2), w * (rc - 0.2), -w * (rc - 0.2)):
                ok &= len(meshio.ray_hits(cl, p + dvec - a * (j["clamp"] - 0.1), a, 0.0, j["clamp"] - 0.2)) == 0
        # iron access: no material of the insert part in the cylinder in front of the hole
        q = samples[j["insert"]] - p
        t = q @ (-a)
        r = np.linalg.norm(q - np.outer(t, -a), axis=1)
        blocked = int(((t > 0.3) & (t < P.iron_len) & (r < P.iron_d / 2)).sum())
        stats["iron_ok" if blocked == 0 else "iron_bad"] += 1
        L = j["screw"]
        eff = j["clamp"] + (0.5 if j["kind"] == "slot" else 0.0)
        good_len = P.engage_min <= L - eff <= s["hole_depth"] - 0.5
        stats["screw"] += 1
        if not ok:
            fails.append(f"{j['name']}: holes not open/coaxial within 0.2 mm")
        if abs(depth - s["hole_depth"]) > 0.15:
            fails.append(f"{j['name']}: insert hole depth {depth:.2f} (want {s['hole_depth']})")
        if floor < P.insert_floor - 0.05:
            fails.append(f"{j['name']}: floor behind the insert {floor:.2f} < {P.insert_floor}")
        if wall < P.boss_wall - 0.05:
            fails.append(f"{j['name']}: boss wall {wall:.2f} < {P.boss_wall}")
        if blocked:
            fails.append(f"{j['name']}: iron access blocked ({blocked} points of {j['insert']})")
        if not good_len:
            fails.append(f"{j['name']}: M3x{L} engagement {L - eff:.1f} mm outside {P.engage_min}..{s['hole_depth'] - 0.5}")
    by_part = {}
    for j in js:
        if j["kind"] != "dowel":
            by_part.setdefault(j["insert"], []).append(j)
    for n, lst in by_part.items():
        for i in range(len(lst)):
            for k in range(i + 1, len(lst)):
                d = np.linalg.norm(np.array(lst[i]["p"]) - np.array(lst[k]["p"]))
                if d < P.inserts["M3"]["boss_d"]:
                    fails.append(f"{n}: inserts {lst[i]['name']} and {lst[k]['name']} only {d:.1f} mm apart")
    lines.append(f"- {stats['screw']} screw joints: holes coaxial within 0.2 mm, insert depth error "
                 f"{stats['depth_err']:.2f} mm, smallest floor {stats['floor_min']:.2f} mm (min {P.insert_floor}), "
                 f"smallest boss wall {stats['wall_min']:.2f} mm (min {P.boss_wall}), iron access free on "
                 f"{stats['iron_ok']}/{stats['iron_ok'] + stats['iron_bad']}")
    return lines, fails


def sharp_exceptions(G):
    """Documented exceptions to the strict sharp-edge check: (part, world box, reason)."""
    P = G.P
    out = []
    for sx in (-1, 1):
        x = sx * G.x_rib
        out.append(("base_front", [x - 1.5, P.base_seam_y - 1.2, G.z_base - 0.6], [x + 1.5, P.base_seam_y + 0.2, G.z_base + 0.3],
                    "end of the base seam rib on the seam face: within 0.5 mm of base_rear's rib face, hidden once bolted"))
    return out


def sharp_edges(P, parts, asm, exceptions=()):
    """Convex edges turning by more than sharp_deg left after rounding, by reason."""
    lines = ["| part | bed chamfer (exempt) | fit lead-ins (exempt) | covered by a mating part (exempt) | "
             "listed exception | exposed |",
             "|---|---|---|---|---|---|"]
    fails = []
    samples = {n: meshio.surface_samples(m, 0.7) for n, m in asm.items()}
    total = 0
    for t in parts:
        n = t["name"]
        m = meshio.read_stl(os.path.join(BUILD, "rounded", n + ".stl"))
        job = json.load(open(os.path.join(BUILD, "rounded", n + ".stl.job.json")))
        p0, p1, ang = edges.sharp_convex_edges(m, P.sharp_deg)
        c = edges.classify(p0, p1, ang, P, job["lead_in_zones"])
        M = np.array(t["p2w"])
        wn = n if n != "foot_stub" else "foot_stub_0"
        Q = c["other_mid"] @ M[:, :3].T + M[:, 3]
        near = np.zeros(len(Q), bool)
        if len(Q):
            lo, hi = Q.min(0) - 1, Q.max(0) + 1
            for on, S in samples.items():
                if on == wn:
                    continue
                S = S[np.all((S >= lo) & (S <= hi), axis=1)]
                for i in range(0, len(S), 20000):
                    d = np.linalg.norm(Q[:, None, :] - S[None, i:i + 20000, :], axis=2).min(1)
                    near |= d < 0.6
        listed = np.zeros(len(Q), bool)
        for part_, lo_, hi_, _ in exceptions:
            if part_ == n:
                listed |= np.all((Q >= np.array(lo_)) & (Q <= np.array(hi_)), axis=1)
        listed &= ~near
        exposed = Q[~near & ~listed]
        total += len(exposed)
        lines.append(f"| {n} | {c['bed']} | {c['fit']} | {int(near.sum())} | {int(listed.sum())} | {len(exposed)} |")
        t["exposed_sharp"] = [list(np.round(x, 1)) for x in exposed]
        t["listed_sharp"] = [list(np.round(x, 1)) for x in Q[listed]]
    return lines, fails, total


def rounding_deviation(names, reach=3.5):
    """Every point of the rounded mesh lies within `reach` mm of the B-rep mesh (catches stray
    faces a mesh operation might leave). Voxel test at 1 mm."""
    worst = {}
    for n in names:
        raw = meshio.read_stl(os.path.join(BUILD, "print_raw", n + ".stl"))
        rnd = meshio.read_stl(os.path.join(BUILD, "rounded", n + ".stl"))
        rs = meshio.surface_samples(raw, 0.8)
        qs = meshio.surface_samples(rnd, 1.5)
        lo = rs.min(0) - reach - 2
        shape = np.ceil((rs.max(0) + reach + 2 - lo)).astype(int) + 1
        occ = np.zeros(shape, bool)
        idx = np.floor(rs - lo).astype(int)
        occ[idx[:, 0], idx[:, 1], idx[:, 2]] = True
        for _ in range(int(math.ceil(reach))):
            g = occ.copy()
            for ax in range(3):
                g |= np.roll(occ, 1, axis=ax) | np.roll(occ, -1, axis=ax)
            occ = g
        qi = np.floor(qs - lo).astype(int)
        ok = np.all((qi >= 0) & (qi < shape), axis=1)
        bad = ~ok
        bad[ok] = ~occ[qi[ok, 0], qi[ok, 1], qi[ok, 2]]
        worst[n] = int(bad.sum())
    return worst


def fillet_check(P, parts, asm, step=3.0, probe=0.78):
    """Inside corners: every concave 90 deg (60-120) edge of the exact B-rep, sampled every
    `step` mm, must have material in the rounded part `probe` mm along the corner bisector (a
    2 mm fillet reaches 0.83 mm along it). Exempt: fit zones, the bed, corners another part sits
    in (within 2 mm of it). Returns (lines, failures, per-part misses in world coordinates)."""
    lines = ["| part | inside-corner samples | filleted | exempt (fit, bed, mating) | without fillet |",
             "|---|---|---|---|---|"]
    fails, misses = [], {}
    others_pts = {n: meshio.surface_samples(m, 1.5) for n, m in asm.items()}
    for t in parts:
        n = t["name"]
        raw = meshio.read_stl(os.path.join(BUILD, "print_raw", n + ".stl"))
        rnd = meshio.read_stl(os.path.join(BUILD, "rounded", n + ".stl"))
        job = json.load(open(os.path.join(BUILD, "rounded", n + ".stl.job.json")))
        p0, p1, n1, n2 = edges.concave_edges(raw)
        pts, bis = [], []
        for a, b, u, v in zip(p0, p1, n1, n2):
            L = np.linalg.norm(b - a)
            k = max(1, int(L // step))
            bi = (u + v) / np.linalg.norm(u + v)
            for s in (np.arange(k) + 0.5) / k:
                pts.append(a + (b - a) * s)
                bis.append(bi)
        if not pts:
            lines.append(f"| {n} | 0 | 0 | 0 | 0 |")
            continue
        pts, bis = np.array(pts), np.array(bis)
        q = pts + bis * probe
        ex = q[:, 2] < P.bed_chamfer + 0.3
        for z in job["lead_in_zones"]:
            ex |= np.all((pts >= np.array(z[:3]) - 0.5) & (pts <= np.array(z[3:]) + 0.5), axis=1)
        M = np.array(t["p2w"])
        W = q @ M[:, :3].T + M[:, 3]
        wn = n if n != "foot_stub" else "foot_stub_0"
        lo, hi = W.min(0) - 3, W.max(0) + 3
        for on, S in others_pts.items():
            if on == wn:
                continue
            S = S[np.all((S >= lo) & (S <= hi), axis=1)]
            for i in range(0, len(S), 20000):
                d = np.linalg.norm(W[:, None, :] - S[None, i:i + 20000, :], axis=2).min(1)
                ex |= d < 2.0
        ok = meshio.inside_mesh(rnd, q)
        miss = ~ok & ~ex
        misses[n] = W[miss]
        lines.append(f"| {n} | {len(q)} | {int((ok & ~ex).sum())} | {int(ex.sum())} | {int(miss.sum())} |")
        if miss.any():
            fails.append(f"{n}: {int(miss.sum())} inside-corner samples without a fillet >= 2 mm")
    return lines, fails, misses
