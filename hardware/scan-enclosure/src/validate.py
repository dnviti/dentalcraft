"""Validation of the built parts. Run after build.py; writes validation-report.md.

1. print size and build volume  2. manifold / watertight meshes
3. optical axis measured from the cradle mesh: hits T at the set distance and elevation;
   cheek slots cover the elevation range
4. clearance of platter (+-tilt) + model to walls, roof, scanner (and info for the rest)
5. view cone, USB-C clearance and scanner travel inside the box
6. ribs/gussets/flanges inside the outline of their print face
7. joints: coaxial holes, insert depth/floor/boss wall, iron access, screw lengths
8. feet  9. rounding: no growth, no exposed sharp convex edge."""
import json
import math
import os
import sys

import numpy as np

import kin
import meshio
import validate_led as vl
import validate_parts as vp
from geom import Geo
from build import parse
from sc import BUILD, CLI, ROOT
ASM, STL = os.path.join(BUILD, "asm"), os.path.join(ROOT, "stl")
lines, fails = [], []


def check(ok, msg):
    lines.append(f"- {'PASS' if ok else 'FAIL'}: {msg}")
    if not ok:
        fails.append(msg)


def unit(v):
    return v / np.linalg.norm(v)


def optical_axis(G, cradle):
    P = G.P
    v = cradle
    n = np.cross(v[:, 1] - v[:, 0], v[:, 2] - v[:, 0])
    area = np.linalg.norm(n, axis=1)
    nn = n / np.maximum(area, 1e-12)[:, None]
    cx = v[:, :, 0].mean(1)
    up = (nn[:, 2] > 0.3) & (np.abs(cx - P.mount_off_x) < G.ch_w / 2 - 0.2) & (area > 1e-9)
    # dominant orientation among the up-facing faces in the channel band = floor and plate top
    keys = np.round(nn[up], 3)
    uk, inv = np.unique(keys, axis=0, return_inverse=True)
    n0 = unit(uk[np.argmax(np.bincount(inv.ravel(), weights=area[up]))])
    par = up & (nn @ n0 > 0.9999)
    off = (v[:, 0] @ n0)
    sel = par & (off < off[par].min() + 1.0)          # lowest parallel plane = channel floor
    nrm = unit((n[sel]).sum(0))
    sdir = unit(np.cross(nrm, [1.0, 0, 0]))
    fv = v[sel].reshape(-1, 3)
    proj = fv @ sdir
    smin, smax = proj.min(), proj.max()
    xm = (fv[:, 0].min() + fv[:, 0].max()) / 2
    base = fv[np.argmin(proj)]
    C0 = base + sdir * ((smin + smax) / 2 - base @ sdir)
    C0 = C0 + np.array([xm - C0[0], 0, 0])
    travel = (smax - smin - P.mount_disc_d) / 2
    lines.append(f"- channel floor normal {nrm.round(4).tolist()}, channel length {smax - smin:.2f} mm, "
                 f"disc travel +-{travel:.2f} mm")
    check(abs(travel - P.dist_adjust) <= 1.0, f"distance adjustment +-{travel:.2f} mm (target +-{P.dist_adjust})")
    for dd in (0.0, -P.dist_adjust, P.dist_adjust):
        C = C0 + sdir * dd
        F = C + nrm * (P.mount_stack + P.body_h / 2 + P.optic_off_t) - sdir * (P.body_d / 2 + P.mount_off_s)
        F = F - np.array([P.mount_off_x, 0, 0])
        ax = -sdir
        w = G.T - F
        along = w @ ax
        miss = np.linalg.norm(w - along * ax)
        elev = math.degrees(math.atan2(sdir[2], sdir[1]))
        tgt = P.distance + dd
        tag = "nominal" if dd == 0 else f"slide {dd:+.0f}"
        check(miss <= 1.0 and abs(along - tgt) <= 1.0 and abs(elev - P.elevation) <= 0.5,
              f"optical axis ({tag}): misses T by {miss:.3f} mm, T at {along:.2f} mm (target {tgt:.0f} +-1), "
              f"elevation {elev:.3f} deg (target {P.elevation} +-0.5)")
        if dd == 0:
            res = (F, ax)
    return res


def slot_checks(G):
    P = G.P
    for side, s in (("left", -1), ("right", 1)):
        ch = meshio.read_stl(os.path.join(ASM, f"cheek_{side}.stl"))
        for phi in (P.elev_min, P.elevation, P.elev_max):
            for i, (sb, tb) in enumerate(G.bolts):
                B = G.body_to_world(phi, sb, tb)
                o = np.array([s * (G.xc1 + 5), B[1], B[2]])
                d = np.array([-s, 0.0, 0])
                hits = meshio.ray_hits(ch, o, d, 0, P.cheek_t + 10)
                r = unit(B[1:] - G.T[1:])
                off = np.array([0, *(r * (P.m3_clear / 2 + 0.6))])
                side_hits = [len(meshio.ray_hits(ch, o + k * off, d, 0, P.cheek_t + 10)) for k in (-1, 1)]
                check(len(hits) == 0 and min(side_hits) >= 2,
                      f"cheek_{side} bolt {i} at {phi:.0f} deg passes the arc slot (slot wall hit both sides)")


def main():
    P, _ = parse()
    G = Geo(P)
    names = sorted(f[:-4] for f in os.listdir(STL) if f.endswith(".stl"))
    lines.append("## 1-2. Print size and mesh quality\n")
    lines.append("| part | print size X x Y x Z (mm) | volume cm3 | triangles | watertight | manifold | shells |")
    lines.append("|---|---|---|---|---|---|---|")
    asm = {}
    for n in names:
        t = meshio.read_stl(os.path.join(STL, n + ".stl"))
        lo, hi = meshio.bbox(t)
        sz = hi - lo
        topo = meshio.topology(t)
        vol = meshio.volume(t)
        lines.append(f"| {n} | {sz[0]:.1f} x {sz[1]:.1f} x {sz[2]:.1f} | {vol / 1000:.1f} | {topo['triangles']} | "
                     f"{topo['watertight']} | {topo['manifold'] and topo['oriented']} | {topo['shells']} |")
        if sz.max() > P.max_part + 1e-6 or min(P.bed[0] - sz[0], P.bed[1] - sz[1], P.bed[2] - sz[2]) < 0 or lo[2] < -1e-6:
            fails.append(f"{n} does not fit {P.max_part} mm / the build volume")
        if not (topo["watertight"] and topo["manifold"] and topo["oriented"] and topo["shells"] == 1 and vol > 0):
            fails.append(f"{n} mesh is not a single closed manifold solid: {topo}")
    anames = sorted(f[:-4] for f in os.listdir(ASM) if f.endswith(".stl"))
    asm = {n: meshio.read_stl(os.path.join(ASM, n + ".stl")) for n in anames}
    check(not any("does not fit" in f for f in fails), f"all {len(names)} parts <= {P.max_part} mm and inside "
          f"{P.bed[0]:.0f}x{P.bed[1]:.0f}x{P.bed[2]:.0f}, resting on Z=0")
    check(not any("manifold" in f for f in fails), "every STL is one closed, consistently oriented manifold shell")
    lines.append("\n## 3. Optical axis (measured from the cradle mesh) and elevation slots\n")
    F, ax = optical_axis(G, asm["cradle"])
    slot_checks(G)
    lines.append("\n## 4. Clearance: platter (+-tilt) + model to every part\n")
    tilts = np.arange(-P.tilt_max, P.tilt_max + 1e-9, 1.0)
    reach = math.hypot(P.model_d / 2, P.platter_above_axis + P.model_h) + 40
    lines.append(f"Platter D{P.platter_d:.0f} x {P.platter_t:.0f} mm, model D{P.model_d:.0f} x {P.model_h:.0f} mm, "
                 f"tilt {-P.tilt_max:.0f}..{P.tilt_max:.0f} deg in 1 deg steps; part surfaces sampled at <= 1.5 mm.\n")
    lines.append("| part | min clearance (mm) | at tilt (deg) | requirement |")
    lines.append("|---|---|---|---|")
    allpts = {}
    for n in anames:
        pts = meshio.surface_samples(asm[n], 1.5)
        allpts[n] = pts
        near = pts[np.hypot(pts[:, 1], pts[:, 2] - G.z_axis) < reach + 60]
        if not len(near):
            lines.append(f"| {n} | > 60 | - | >= {P.min_clear:.0f} |")
            continue
        d, a = kin.sweep_distance(G, near, tilts)
        i = int(np.argmin(d))
        req = not n.startswith("base")
        lines.append(f"| {n} | {d[i]:.1f} | {a[i]:+.0f} | {'>= %.0f' % P.min_clear if req else 'info (turntable sits on it)'} |")
        if req and d[i] < P.min_clear:
            fails.append(f"{n} clearance {d[i]:.1f} mm < {P.min_clear}")
    sc_min = min(kin.sweep_distance(G, kin.scanner_samples(G, ph, ds), tilts)[0].min() for ph, ds in kin.scanner_poses(P))
    lines.append(f"| scanner (all 9 poses) | {sc_min:.1f} | - | >= {P.min_clear:.0f} |")
    check(sc_min >= P.min_clear and not any("clearance" in f for f in fails),
          f"platter + model clear walls, roof, tower and scanner by >= {P.min_clear:.0f} mm")
    lines.append("\n## 5. View cone, USB-C and scanner travel\n")
    pts = np.vstack([allpts[n] for n in anames])
    blocked = kin.in_view_cone(G, pts, F, ax, P.distance)
    check(blocked.sum() == 0, f"view cone {P.fov_h_deg} x {P.fov_v_deg} deg from the front face to T is free "
          f"({int(blocked.sum())} part points inside)")
    usb = kin.in_scanner_box(G, pts, P.elevation, P.distance, usb=True)
    check(usb.sum() == 0, f"USB-C clearance {P.rear_clear:.0f} mm behind the scanner is free at the nominal pose")
    hits = {}
    ymax = zmax = -np.inf
    for ph, ds in kin.scanner_poses(P):
        a = math.radians(ph - P.elevation)       # the cradle turns with the scanner about the aim line
        R = np.array([[1, 0, 0], [0, math.cos(a), -math.sin(a)], [0, math.sin(a), math.cos(a)]])
        cr = (allpts["cradle"] - G.T) @ R.T + G.T
        sp = kin.scanner_samples(G, ph, ds)
        ymax, zmax = max(ymax, cr[:, 1].max(), sp[:, 1].max()), max(zmax, cr[:, 2].max(), sp[:, 2].max())
        for n in anames:
            q = cr if n == "cradle" else allpts[n]
            k = int(kin.in_scanner_box(G, q, ph, ds, grow=-0.05).sum())
            if k:
                hits[(n, ph, ds)] = k
    check(not hits, f"scanner body collides with no part at elevation 30/40/50 deg x distance -15/0/+15 mm {hits or ''}")
    yl, zl = G.y_back_in - P.flange_d, G.z_rb - 8.0
    check(ymax <= yl - 1 and zmax <= zl - 1, f"moving scanner + cradle stay {yl - ymax:.1f} mm in front of the back-wall "
          f"flanges and {zl - zmax:.1f} mm under the roof ribs over the whole adjustment range")
    build = json.load(open(os.path.join(BUILD, "build.json")))
    js = build["joints"]
    lines.append("\n## 6. Ribs, gussets and flanges inside their outline\n")
    l6, f6 = vp.rib_outline(P, names)
    lines.extend(l6)
    fails.extend(f6)
    check(not f6, "no rib, gusset, foot or flange stands outside the outline of the face it is printed on")
    lines.append("\n## 7. Joints and heat-set inserts\n")
    l7, f7 = vp.joint_checks(P, js, asm)
    lines.extend(l7)
    fails.extend(f7)
    check(not f7, "every clearance hole is coaxial with its insert hole (+-0.2 mm), insert depth, floor, boss wall, "
          "iron access and screw lengths are within the rules")
    lines.append("\n## 8. Feet\n")
    k = P.sleeve_d / 2 + P.sleeve_clear
    ok = all(abs(x) + k <= G.x_out + 1e-6 and G.y_front + k - 1e-6 <= y <= G.y_back_out - k + 1e-6
             and abs(y - P.base_seam_y) >= k for x, y in G.feet())
    rmin = min(math.hypot(x, y) for x, y in G.feet()) - P.foot_d_top / 2
    check(ok, f"{len(G.feet())} foot stubs: sleeve D{P.sleeve_d:.0f} + {P.sleeve_clear:.0f} mm inside the base "
          f"footprint and off the base seam; nearest stub edge {rmin:.0f} mm from the turntable centre "
          f"(locating arcs end at {P.base_d / 2 + P.fit + P.loc_w:.1f})")
    lines.append("\n## 9. Rounding\n")
    over = {t["name"]: t["rounding"]["overshoot_mm"] for t in build["parts"]}
    worst = max(over, key=over.get)
    check(over[worst] <= 0.3, f"rounding grows no part by more than 0.3 mm (largest {over[worst]:.2f} mm on {worst})")
    lines.append(f"Rounding method per part (SolidCraft CLI `{CLI}`; B-rep = exact SolidCraft fillets and chamfers, "
                 "mesh = Blender CSG pipeline; the B-rep is kept when it leaves no more exposed sharp edges than the "
                 "mesh):\n")
    lines.append("| part | method | B-rep inside fillets built / planned | B-rep outer rounds + chamfers built / planned | "
                 "not tried (time budget) | refusals | exposed sharp: B-rep | exposed sharp: mesh |")
    lines.append("|---|---|---|---|---|---|---|---|")
    for t in build["parts"]:
        r = t["rounding"]
        b = r.get("brep", {})
        ins = b.get("inside", {})
        grp = [b[k] for k in ("inside", "corner", "edge", "lead_in", "bed") if isinstance(b.get(k), dict)]
        outer = grp[1:]
        o_ok, o_n = sum(x["ok"] for x in outer), sum(x["edges"] for x in outer)
        nt = sum(x.get("not_tried", 0) for x in grp)
        why = ", ".join(sorted({e for x in grp for e in x.get("errors", [])})) or "-"
        lines.append(f"| {t['name']} | {r.get('method', 'mesh')} | {ins.get('ok', '-')} / {ins.get('edges', '-')} | "
                     f"{o_ok if outer else '-'} / {o_n if outer else '-'} | {nt if grp else '-'} | {why} | "
                     f"{r.get('exposed_sharp_brep', '-')} | {r.get('exposed_sharp_mesh', '-')} |")
    lines.append("")
    exc = vp.sharp_exceptions(G)
    l9, f9, exposed = vp.sharp_edges(P, build["parts"], asm, exc)
    lines.append(f"Convex mesh edges whose faces turn by more than {P.sharp_deg:.0f} deg (interior angle under "
                 f"{180 - P.sharp_deg:.0f} deg), after rounding:\n")
    lines.extend(l9)
    lines.append("\nListed exceptions:\n")
    lines.extend(f"- {p_}: X {lo[0]:.1f}..{hi[0]:.1f}, Y {lo[1]:.1f}..{hi[1]:.1f}, Z {lo[2]:.1f}..{hi[2]:.1f}: {why}"
                 for p_, lo, hi, why in exc)
    lines.append("")
    check(exposed == 0, f"no exposed sharp convex edge outside the listed exceptions ({exposed} left, listed in "
          "build/build.json -> exposed_sharp)")
    lf, ff, _ = vp.fillet_check(P, build["parts"], asm)
    lines.append("\nInside corners (concave B-rep edges of 60-120 deg, sampled every 3 mm): material 0.78 mm "
                 "along the corner bisector, as a fillet of 2 mm or more gives:\n")
    lines.extend(lf)
    fails.extend(ff)
    check(not ff, "inside corners have a fillet >= 2 mm (outside fits, the bed and corners another part sits in)")
    dev = vp.rounding_deviation(names)
    check(not any(dev.values()), "every rounded surface lies within 3.5 mm of the exact B-rep (no stray faces) "
          + str({k: v for k, v in dev.items() if v} or ""))
    lines.append("\n## 10. Lighting\n")
    l10, f10 = vl.led_checks(P, G, asm, F)
    lines.extend(l10)
    fails.extend(f10)
    check(not f10, "lit diffusers outside the camera view cone (+3 deg), sensor collar hides platter and model, "
          "lighting clear of the cable pass-throughs")
    with open(os.path.join(BUILD, "build.json"), "w") as f:
        json.dump(build, f, indent=1)
    with open(os.path.join(ROOT, "validation-report.md"), "w") as f:
        f.write(f"# Validation report\n\nProfiles: {P.scanner_label} on {P.turntable_label}. "
                f"Generated by `src/validate.py`.\n\n" + "\n".join(lines) + "\n\n" +
                (f"**{len(fails)} FAILURES**\n" + "\n".join("- " + x for x in fails) if fails else "**ALL CHECKS PASS**") + "\n")
    print("\n".join(lines))
    print("FAILURES:" if fails else "ALL CHECKS PASS", *fails, sep="\n")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
