"""Every fastener joint and every seam, in world coordinates, shared by both parts.

A joint: p = point on the contact face, a = unit axis from the clearance part into the
insert part, clamp = thickness the screw passes through. kind: "screw" (M3 into a heat-set
insert), "dowel" (printed pin on the insert part, hole in the clearance part), "slot"
(screw through a cheek arc slot into a cradle insert). boss: how the insert part carries the
insert: "flange" (cylinder along a flange, with a web down to the skin), "skin" (cylinder
standing on a skin), "solid" (the plate or rib is thick enough).
Screws sit at most seam_pitch apart, at least 2 per seam, seam_end from the seam ends."""
import math

import numpy as np

DOWN, UP, BACK, FWD = (0, 0, -1), (0, 0, 1), (0, -1, 0), (0, 1, 0)

SEAMS = {}     # seam id -> dict(parts, alignment, insert side) for the seam table


def J(seam, name, p, a, clear, insert, clamp, kind="screw", boss="solid", thread="M3"):
    return dict(seam=seam, name=name, p=np.array(p, float), a=np.array(a, float), clear=clear,
                insert=insert, clamp=float(clamp), kind=kind, boss=boss, thread=thread)


def seam(sid, parts, alignment, insert_side):
    SEAMS[sid] = dict(parts=parts, alignment=alignment, insert_side=insert_side)


def spread(a, b, P, avoid=()):
    """Screw positions on [a, b]: <= seam_pitch apart, >= 2, seam_end from the seam ends and
    10 mm from every avoided interval (notches, ribs, slots: no corner flange there)."""
    ranges = [(a, b, P.seam_end, P.seam_end)]
    for lo, hi in sorted(avoid):
        out = []
        for r0, r1, e0, e1 in ranges:
            if hi <= r0 or lo >= r1:
                out.append((r0, r1, e0, e1))
                continue
            if lo > r0:
                out.append((r0, lo, e0, 10.0))
            if hi < r1:
                out.append((hi, r1, 10.0, e1))
        ranges = out
    pos = []
    for r0, r1, e0, e1 in ranges:
        u0, u1 = r0 + e0, r1 - e1
        if u1 < u0:
            continue
        n = max(2 if len(ranges) == 1 else 1, math.ceil((u1 - u0) / P.seam_pitch) + 1)
        if u1 - u0 < 12.0:                 # too short for two bosses: one in the middle
            n = 1
        pos += list(np.linspace(u0, u1, n)) if n > 1 else [(u0 + u1) / 2]
    if len(pos) < 2:
        raise ValueError(f"seam {a:.0f}..{b:.0f} has room for fewer than 2 screws")
    return [float(v) for v in pos]


def mids(pos):
    """Points halfway between consecutive screws (dowels, keys)."""
    return [(pos[i] + pos[i + 1]) / 2 for i in range(len(pos) - 1)]


def side_name(s):
    return "right" if s > 0 else "left"


def build_joints(G):
    P = G.P
    SEAMS.clear()
    js = []
    M3 = P.inserts["M3"]
    hb = G.skin_boss_h
    zb, zr, ys, zs, yb = G.z_base, G.z_rb, P.side_split_y, P.split_z, G.y_back_in
    xf = G.x_in - P.flange_d / 2          # mid-depth of side-wall flanges
    xr = G.x_in - 5.0                     # roof bosses: clear of the roof lips' iron cylinder
    xk = G.x_in - 7.0                     # back bosses: 2.5 mm from the back skin edge
    yfl = yb - P.flange_d / 2
    xb = G.x_in - P.flange_d - 0.3        # half length of back/roof cross flanges
    seam_y = P.base_seam_y
    keep = 2 * P.seam_end / 2 + 4         # base inserts stay this far from the base seam

    def base_of(y):
        return "base_front" if y < seam_y else "base_rear"

    # 1. base halves: front rib carries the inserts (axis along Y, parallel to the layers)
    xs_ = spread(-G.x_rib, G.x_rib, P)
    G.key_x = mids(xs_)
    seam("base", "base_front / base_rear", "2+ keys (base_front) in notches", "base_front seam rib")
    for i, x in enumerate(xs_):
        js.append(J("base", f"base_seam{i}", (x, seam_y, zb + P.seam_rib_h / 2), BACK,
                    "base_rear", "base_front", P.seam_rib_t))
    for s in (-1, 1):
        sd = side_name(s)
        lf, lr, uf, ur = (f"side_{sd}_{a}" for a in ("front_lower", "rear_lower", "front_upper", "rear_upper"))
        # 2. side walls -> base: inserts in the base from the top, dowels on the base
        jack = [(-P.jack_notch_w / 2 - 12, P.jack_notch_w / 2 + 12)] if s == P.jack_side else []
        for piece, (y0, y1) in ((lf, (G.y_front, ys)), (lr, (ys, yb))):
            av = jack + [(seam_y - keep, seam_y + keep), (ys - 8, ys + 8)]
            pos = spread(y0, y1, P, av)
            seam(f"{piece}-base", f"{piece} / base", "2 dowels on the base + skin flush with the base edge",
                 "base (from the top)")
            for i, y in enumerate(pos):
                js.append(J(f"{piece}-base", f"{piece}_foot{i}", (s * xf, y, zb), DOWN, piece, base_of(y),
                            P.flange_t))
            for i, y in enumerate([v for v in mids(pos) if all(not (lo < v < hi) for lo, hi in av)][:2]):
                js.append(J(f"{piece}-base", f"{piece}_dowel{i}", (s * xf, y, zb), DOWN, piece, base_of(y),
                            P.flange_t, "dowel"))
        # 3. wall pieces with each other (flange to flange, inserts parallel to the layers)
        for lower, upper, rng in ((lf, uf, (G.y_front, ys)), (lr, ur, (ys, yb))):
            sid = f"{lower}-{upper}"
            seam(sid, f"{lower} / {upper}", "tongue (lower) in groove (upper)", lower)
            for i, y in enumerate(spread(*rng, P)):
                js.append(J(sid, f"{sid}{i}", (s * xf, y, zs), DOWN, upper, lower, P.flange_t, boss="flange"))
        for front, rear, rng in ((lf, lr, (zb, zs)), (uf, ur, (zs, zr - hb - P.flange_t))):
            sid = f"{front}-{rear}"
            seam(sid, f"{front} / {rear}", "tongue (front) in groove (rear)", front)
            for i, z in enumerate(spread(*rng, P)):
                js.append(J(sid, f"{sid}{i}", (s * xf, ys, z), BACK, rear, front, P.flange_t, boss="flange"))
        # 4. walls -> back: inserts in bosses on the back skin, screws from inside
        for piece, back, rng in ((lr, "back_lower", (zb, zs)), (ur, "back_upper", (zs, zr - hb - P.flange_t))):
            sid = f"{piece}-{back}"
            seam(sid, f"{piece} / {back}", "back captured between the side skins, base below", back + " skin bosses")
            for i, z in enumerate(spread(*rng, P)):
                js.append(J(sid, f"{sid}{i}", (s * xk, yb - hb, z), FWD, piece, back, P.flange_t, boss="skin"))
        # 5. walls -> roof: inserts in bosses on the roof skin, screws up from inside
        for piece, roof, rng in ((uf, "roof_front", (G.y_front, ys)), (ur, "roof_rear", (ys, yb - P.flange_d))):
            sid = f"{piece}-{roof}"
            seam(sid, f"{piece} / {roof}", "roof inner lips inside the side walls", roof + " skin bosses")
            for i, y in enumerate(spread(*rng, P)):
                js.append(J(sid, f"{sid}{i}", (s * xr, y, zr - hb), UP, piece, roof, P.flange_t, boss="skin"))
    # 6. back halves, back -> base, back -> roof, roof halves
    rib_av = [(-G.back_rib_x - 8, -G.back_rib_x + 8), (G.back_rib_x - 8, G.back_rib_x + 8)]
    pos = spread(-xb, xb, P, rib_av)
    seam("back-base", "back_lower / base_rear", "2 dowels on the base + side skins", "base_rear (from the top)")
    for i, x in enumerate(pos):
        js.append(J("back-base", f"back_foot{i}", (x, yfl, zb), DOWN, "back_lower", "base_rear", P.flange_t))
    for i, x in enumerate([pos[0] + (pos[1] - pos[0]) / 2, pos[-2] + (pos[-1] - pos[-2]) / 2]):
        js.append(J("back-base", f"back_dowel{i}", (x, yfl, zb), DOWN, "back_lower", "base_rear", P.flange_t, "dowel"))
    seam("back", "back_lower / back_upper", "tongue (lower) in groove (upper)", "back_lower")
    for i, x in enumerate(pos):
        js.append(J("back", f"back_hseam{i}", (x, yfl, zs), DOWN, "back_upper", "back_lower", P.flange_t,
                    boss="flange"))
    seam("back-roof", "back_upper / roof_rear", "roof rear lip inside the back wall", "roof_rear skin bosses")
    usb = [(-P.usb_slot_w / 2 - 8, P.usb_slot_w / 2 + 8)]
    for i, x in enumerate(spread(-xb, xb, P, usb)):
        js.append(J("back-roof", f"back_roof{i}", (x, yb - 5.0, zr - hb), UP, "back_upper", "roof_rear", P.flange_t,
                    boss="skin"))
    seam("roof", "roof_front / roof_rear", "tongue (front) in groove (rear)", "roof_front")
    for i, x in enumerate(spread(-xb, xb, P, [(-8, 8)])):
        js.append(J("roof", f"roof_seam{i}", (x, ys, zr - P.flange_d / 2), BACK, "roof_rear", "roof_front",
                    P.flange_t, boss="flange"))
    # 7. cheeks -> base_rear (outer foot), cheeks -> cradle (arc slots)
    for s in (-1, 1):
        sd = side_name(s)
        xo = s * (G.xc1 + P.cheek_foot_w / 2)
        sid = f"cheek_{sd}-base"
        seam(sid, f"cheek_{sd} / base_rear", "2 dowels on the base", "base_rear (from the top)")
        f0, f1 = G.foot_y
        pos = spread(f0, f1, P)
        G.cheek_screw_y = pos
        for i, y in enumerate(pos):
            js.append(J(sid, f"{sid}{i}", (xo, y, zb), DOWN, f"cheek_{sd}", "base_rear", P.cheek_foot_t))
        G.cheek_dowel_y = [pos[0] + 12.0, pos[-1] - 12.0]        # between the screws: gussets fit at the ends
        for i, y in enumerate(G.cheek_dowel_y):
            js.append(J(sid, f"{sid}_dowel{i}", (xo, y, zb), DOWN, f"cheek_{sd}", "base_rear", P.cheek_foot_t, "dowel"))
        sid = f"cheek_{sd}-cradle"
        seam(sid, f"cheek_{sd} / cradle", "cradle between the cheek inner faces, screws in the arc slots",
             "cradle side plate")
        for i, (sb, tb) in enumerate(G.bolts):
            p = G.body_to_world(P.elevation, sb, tb, s * G.x_go)
            js.append(J(sid, f"{sid}{i}", p, (-s, 0, 0), f"cheek_{sd}", "cradle", P.cheek_t, "slot"))
    # 8. foot stubs -> base (insert in the base from below)
    for i, (x, y) in enumerate(G.feet()):
        sid = f"foot{i}"
        seam(sid, f"foot_stub / {base_of(y)}", "locating recess in the base underside", base_of(y) + " (from below)")
        js.append(J(sid, f"foot{i}", (x, y, P.foot_recess_depth), UP, f"foot_stub_{i}", base_of(y), G.foot_clamp))
    # 9. electronics bay on base_rear: board standoffs and vented-cover posts (inserts from the top)
    import parts_led
    stand, posts, _, _ = parts_led.bay(G)
    seam("bay-board", "control board / base_rear", "board on 4 standoffs", "base_rear standoffs")
    for i, (x, y) in enumerate(stand):
        js.append(dict(J("bay-board", f"bay_board{i}", (x, y, zb + P.standoff_h), DOWN, "control_board", "base_rear",
                         1.6 + 0.8, boss="post"), post_h=P.standoff_h))
    seam("bay-cover", "bay_cover / base_rear", "cover walls around the 4 posts", "base_rear posts")
    hc = parts_led.bay_cover_h(P) - P.bay_top
    for i, (x, y) in enumerate(posts):
        js.append(dict(J("bay-cover", f"bay_cover{i}", (x, y, zb + hc), DOWN, "bay_cover",
                         "base_rear", P.bay_top, boss="post"), post_h=hc))
    return js


def for_part(js, name):
    return [j for j in js if j["clear"] == name or j["insert"] == name]


def screw_length(P, j):
    """Standard length: engagement >= engage_min and short of the insert hole bottom."""
    eff = j["clamp"] + (0.5 if j["kind"] == "slot" else 0.0)   # washer under slot screws
    depth = P.inserts[j["thread"]]["hole_depth"]
    fits = [L for L in P.screw_lengths if P.engage_min <= L - eff <= depth - 0.5]
    if not fits:
        raise ValueError(f"no screw length for {j['name']} (clamp {j['clamp']})")
    return min(fits)
