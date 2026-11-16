"""Controlled lighting, from the lighting/electronics interface (LIGHTING in params.py,
electronics/DESIGN.md): LED channels with slide-in diffuser covers, the light-sensor holder,
the electronics bay with its vented cover, the back-panel cutouts, cable guides and wire holes.

Channels: two on the roof_front underside (X +-90, along Y, aperture down) and one on each
upper rear side panel (Y 95, along Z, aperture towards the middle). Two walls on the skin with
a cover groove each and an end wall with a wire hole at the closed end; the cover slides in
from the open end. Wall runs: the +Y wall (scanner side) runs `visor` past the cover face."""
import numpy as np

from sc import Part, frame_matrix, to_local


def unit(v):
    v = np.asarray(v, float)
    return v / np.linalg.norm(v)


def runs(G):
    """LED runs: skin point o (channel start, centre line), along L_dir for length L, across
    w_dir (+w = scanner side), inward normal n; closed: "start" or "end"; visor: wall runs."""
    P = G.P
    y0, y1 = P.roof_run_y
    z0, z1 = P.wall_run_z
    out = []
    for s, sd in ((-1, "left"), (1, "right")):
        out.append(dict(name=f"roof_{sd}", part="roof_front", o=np.array([s * P.roof_run_x, y0, G.z_rb]),
                        L_dir=np.array([0, 1.0, 0]), L=y1 - y0, w_dir=np.array([1.0, 0, 0]),
                        n=np.array([0, 0, -1.0]), closed="end", visor=False))
    for s, sd in ((-1, "left"), (1, "right")):
        out.append(dict(name=f"wall_{sd}", part=f"side_{sd}_rear_upper", o=np.array([s * G.x_in, P.wall_run_y, z0]),
                        L_dir=np.array([0, 0, 1.0]), L=z1 - z0, w_dir=np.array([0, 1.0, 0]),
                        n=np.array([-s * 1.0, 0, 0]), closed="start", visor=True))
    return out


def cover_h(P):
    """Cover inner face and lit (outer) face above the skin: centred in the groove."""
    h0 = P.groove_z + (P.groove_h - P.cover_t) / 2
    return h0, h0 + P.cover_t


def box_w(r, u0, u1, v0, v1, h0, h1):
    """World box from run coordinates (along, across, up from the skin)."""
    pts = [r["o"] + r["L_dir"] * u + r["w_dir"] * v + r["n"] * h for u in (u0, u1) for v in (v0, v1) for h in (h0, h1)]
    pts = np.array(pts)
    return pts.min(0), pts.max(0)


def channel_boxes(G, r):
    """(joins, cuts) world boxes of one LED channel."""
    P = G.P
    w, t, L, hw = P.ch_w / 2, P.ch_wall, r["L"], P.ch_h
    hv = P.groove_z + P.groove_h + P.visor if r["visor"] else hw
    e0, e1 = (-P.end_wall, 0.0) if r["closed"] == "start" else (L, L + P.end_wall)
    joins = [box_w(r, min(e0, 0), max(e1, L), -w - t, -w, -0.5, hw),
             box_w(r, min(e0, 0), max(e1, L), w, w + t, -0.5, hv),
             box_w(r, e0, e1, -w - t, w + t, -0.5, hw)]
    g0, g1 = (-1.0, L) if r["closed"] == "end" else (0.0, L + 1.0)      # groove open at the open end
    cuts = [box_w(r, g0, g1, -w - P.groove_d, w + P.groove_d, P.groove_z, P.groove_z + P.groove_h)]
    return joins, cuts


def wire_holes(G, name):
    """Closed round wire holes through thin walls, just above the skin (a closed hole has its
    mouths on the wall faces only, so they are rounded all round): dict(c, axis, d, depth),
    c = hole centre on the wall mid-plane."""
    P = G.P
    out = []
    for r in runs(G):                          # strip leads through the closed end wall
        if r["part"] == name:
            e = -P.end_wall / 2 if r["closed"] == "start" else r["L"] + P.end_wall / 2
            d = P.wire_hole_d
            out.append(dict(c=r["o"] + r["L_dir"] * e + r["n"] * (P.wire_hole_lift + d / 2), axis=r["L_dir"],
                            d=d, depth=P.end_wall + 2.0))
    xl = G.x_in - P.flange_d - 0.3
    walls = []
    if name == "roof_front":                   # left lip at the riser, centre rib at the crossing
        walls = [(-(xl - P.flange_t / 2), P.riser_y), (0.0, P.roof_cross_y)]
    if name == "roof_rear":                    # both lips over the Y 72 seam
        walls = [(sx * (xl - P.flange_t / 2), P.lip_hole_y) for sx in (-1, 1)]
    d = P.harness_hole_d
    for x, y in walls:
        out.append(dict(c=np.array([x, y, G.z_rb - P.wire_hole_lift - d / 2]), axis=np.array([1.0, 0, 0]),
                        d=d, depth=P.flange_t + 2.0))
    return out


def cover_matrix(G, r):
    """Cover print frame (x along, y across from its edge, z up from its inner face) -> world."""
    P = G.P
    L, w, n = r["L_dir"], r["w_dir"], r["n"]
    if np.dot(np.cross(L, w), n) < 0:
        w = -w
    O = r["o"] + n * cover_h(P)[0] - w * (P.cover_w / 2) + L * 0.5
    return frame_matrix(O, L, w, n)


def build_cover(G, r):
    P = G.P
    part = Part(f"led_cover_{r['name']}")
    part.box([0, 0, 0], [r["L"] - 1.0, P.cover_w, P.cover_t])
    return part


def sensor(G):
    """Sensor dome tip and axis (tilted from vertical towards -Y)."""
    P = G.P
    a = np.radians(P.sensor_tilt)
    return np.array(P.sensor_tip, float), np.array([0.0, -np.sin(a), np.cos(a)])


def bay_cover_h(P):
    return P.standoff_h + P.board_t + P.board_free + P.bay_top + 1.0


def bay(G):
    """Board standoff and cover post centres (x, y) on base_rear, cover outline."""
    P = G.P
    bx, by = P.board_hole_dx / 2, P.board_hole_dy / 2
    cw, ch = P.board_w + 24.0, P.board_h + 24.0
    px, py = cw / 2 - P.bay_wall - 4.5, ch / 2 - P.bay_wall - 4.5
    stand = [(sx * bx, P.bay_y + sy * by) for sx in (-1, 1) for sy in (-1, 1)]
    posts = [(sx * px, P.bay_y + sy * py) for sx in (-1, 1) for sy in (-1, 1)]
    return stand, posts, cw, ch


def build_bay_cover(G):
    """Vented cover, printed top down: top plate on the bed, walls up, open side = base."""
    P = G.P
    _, posts, cw, ch = bay(G)
    part = Part("bay_cover")
    top, h = P.bay_top, bay_cover_h(P)
    part.box([-cw / 2, -ch / 2, 0], [cw / 2, ch / 2, h])
    part.box([-cw / 2 + P.bay_wall, -ch / 2 + P.bay_wall, top], [cw / 2 - P.bay_wall, ch / 2 - P.bay_wall, h + 1],
             op="cut")
    a = np.radians(np.linspace(0, 180, 31))
    for i in range(6):                                     # obround vent slots, between the posts
        x = -20.0 + 8.0 * i
        slot = np.vstack([np.column_stack([x + 1.5 * np.cos(a), 9.0 + 1.5 * np.sin(a)]),
                          np.column_stack([x - 1.5 * np.cos(a), -9.0 - 1.5 * np.sin(a)])])
        part.prism([0, 0, -1.0], [1, 0, 0], [0, 1, 0], slot, top + 2.0, op="cut")
    # cable hole (closed, its edges round all round) 3.5 mm above the base, in the wall facing the
    # back: thread the harness through before connecting it to the board
    part.cyl([0, -ch / 2 - 1.0, h - P.bay_cable_d / 2 - 3.5], [0, 1, 0], P.bay_cable_d, P.bay_wall + 2.0, op="cut")
    return part


def bay_cover_matrix(G):
    return frame_matrix([0, G.P.bay_y, G.z_base + bay_cover_h(G.P)], [1, 0, 0], [0, -1, 0], [0, 0, -1])


def guides(G):
    """Cable guides: (part, skin point, inward normal, cable direction). Strip harness: bay ->
    base_rear -> Z 30 along the -X lower walls -> up the -X front wall at riser_y -> across the
    roof_front at roof_cross_y to both roof channels. Sensor lead: down the -X front wall into
    the riser clips, then the Z 30 run."""
    P = G.P
    zb, xi = G.z_base, G.x_in
    xn, zn, yn = (1, 0, 0), (0, 0, 1), (0, 1, 0)
    g = [("side_left_front_lower", (-xi, P.riser_y, 70.0), xn, zn),
         ("side_left_front_lower", (-xi, P.riser_y, 125.0), xn, zn),
         ("side_left_front_upper", (-xi, P.riser_y, 210.0), xn, zn),   # clear of the sensor holder
         ("side_left_front_upper", (-xi, P.riser_y, 255.0), xn, zn),
         ("side_left_front_upper", (-xi, P.riser_y, 300.0), xn, zn),
         ("side_left_front_lower", (-xi, -20.0, 30.0), xn, yn),
         ("side_left_front_lower", (-xi, 40.0, 30.0), xn, yn),
         ("side_left_rear_lower", (-xi, 110.0, 30.0), xn, yn),
         ("side_left_rear_lower", (-xi, 200.0, 30.0), xn, yn),
         ("base_rear", (-90.0, 240.0, zb), zn, (1, 0, 0)),
         ("base_rear", (-60.0, 240.0, zb), zn, (1, 0, 0))]
    for x in (-60.0, -20.0, 20.0, 60.0):
        g.append(("roof_front", (x, P.roof_cross_y, G.z_rb), (0, 0, -1), (1, 0, 0)))
    return g


def guide_boxes(G, n, cdir):
    """Envelope of the two posts either side of the cable, cable_slot apart (relative to the
    skin point)."""
    P = G.P
    n, c = np.array(n, float), np.array(cdir, float)
    side = np.cross(n, c)
    w, s, h = P.cable_post_w + 1.0, P.cable_slot, P.cable_post_h
    out = []
    for k in (-1, 1):
        ctr = side * k * (s / 2 + w / 2)
        out.append(np.array([ctr + side * a + c * b + n * d for a in (-w / 2, w / 2) for b in (-w / 2, w / 2)
                             for d in (-0.5, h)]))
    return out


def guide_posts(G, p, n, cdir):
    """Two round posts either side of the cable (round posts round cleanly at the top)."""
    P = G.P
    n, c = np.array(n, float), np.array(cdir, float)
    side = np.cross(n, c)
    w, s = P.cable_post_w + 1.0, P.cable_slot
    return [(np.array(p, float) + side * k * (s / 2 + w / 2) - n * 0.5, n, w, P.cable_post_h + 0.5)
            for k in (-1, 1)]


def panel_holes(G):
    """(name, world centre, diameter) of the back_lower cutouts, plus the pot anti-rotation hole."""
    P = G.P
    out = []
    for i, (nm, dia) in enumerate(P.panel_holes):
        x = (i - (len(P.panel_holes) - 1) / 2) * P.panel_pitch
        out.append((nm, np.array([x, G.y_back_out, P.panel_z]), dia))
        if nm.startswith("potentiometer"):
            out.append(("pot anti-rotation tab", np.array([x, G.y_back_out, P.panel_z + P.pot_tab_off]), P.pot_tab_d))
    return out


def sensor_features(G):
    """Sensor holder (world): (joins, cuts) as cylinders (base, axis, d, h) and boxes (lo, hi).
    A tube with the flat collar on top (1 mm under the dome tip), on a block to the wall skin;
    bore and flange counterbore from below (the sensor goes in from below and is glued; the
    leads drop straight down inside the wall)."""
    P = G.P
    tip, a = sensor(G)
    top = tip - a * P.sensor_collar_below
    ln = P.sensor_h - P.sensor_collar_below
    bot = top - a * ln
    r = P.sensor_collar_d / 2
    zlo = bot[2] - r * np.sin(np.radians(P.sensor_tilt))
    zhi = top[2] - r * np.sin(np.radians(P.sensor_tilt)) - 0.5
    cyl_j = [(bot, a, P.sensor_collar_d, ln)]
    box_j = [([-G.x_in - 0.5, tip[1] - r + 0.5, zlo], [tip[0], tip[1] + r - 0.5, zhi])]   # never tangent to the tube
    cyl_c = [(bot - a * 4.0, a, P.sensor_bore, ln + 5.0),
             (bot - a * 4.0, a, P.sensor_cb_d, P.sensor_cb_h + 4.0)]
    return cyl_j, box_j, cyl_c


def panel_features(pn, G, name):
    """Add the lighting features that live on panel `name` (Panel builder, world geometry)."""
    P = G.P
    R = pn.M[:, :3].T
    for r in runs(G):
        if r["part"] == name:
            joins, cuts = channel_boxes(G, r)
            for lo, hi in joins:
                pn.wbox(lo, hi)
            for lo, hi in cuts:
                pn.wbox(lo, hi, op="cut")
    for part, p, n, c in guides(G):
        if part == name:
            for base, axis, d, h in guide_posts(G, p, n, c):
                pn.cyl(to_local(pn.M, base), R @ axis, d, h)
    for wh in wire_holes(G, name):
        pn.cyl(to_local(pn.M, wh["c"] - wh["axis"] * wh["depth"] / 2), R @ wh["axis"], wh["d"], wh["depth"],
               op="cut")
    if name == "side_left_front_upper":
        cj, bj, cc = sensor_features(G)
        for lo, hi in bj:
            pn.wbox(lo, hi)
        for base, axis, d, h in cj:
            pn.cyl(to_local(pn.M, base), R @ axis, d, h)
        for base, axis, d, h in cc:
            pn.cyl(to_local(pn.M, base), R @ axis, d, h, op="cut")
    if name == "back_lower":
        for _, c, dia in panel_holes(G):
            pn.cyl(to_local(pn.M, c + np.array([0, 1.0, 0])), [0, 0, 1], dia, P.wall_t + 2, op="cut")


def lead_zones(G, name):
    """Fit zones for rounding: cover grooves, sensor bore, panel holes."""
    from zones import box
    z = []
    for r in runs(G):
        if r["part"] == name:
            lo, hi = channel_boxes(G, r)[1][0]
            z.append(box(lo - 0.8, hi + 0.8))
    if name == "side_left_front_upper":
        for base, a, d, h in sensor_features(G)[2]:
            for t in np.arange(0, h + 0.1, 1.0):
                c = base + a * t
                z.append(box(c - (d / 2 + 1.0), c + (d / 2 + 1.0)))
    if name == "back_lower":
        for _, c, dia in panel_holes(G):
            z.append(box(c - [dia / 2 + 0.8, G.y_back_out - G.y_back_in + 1, dia / 2 + 0.8],
                         c + [dia / 2 + 0.8, 1, dia / 2 + 0.8]))
    return z
