"""Base plate, split in two at base_seam_y: base_front (turntable) and base_rear (tower).

Built in world coordinates, which are also the print orientation (flat side down)."""
import numpy as np

import parts_led
from features import apply_joints, sector
from sc import Part


def _locators(part, G):
    """Turntable locating arcs (round base) or corner stops (rect base), on top of the plate."""
    P = G.P
    z0, z1 = G.z_base, G.z_base + P.loc_h
    if P.base_shape == "round":
        r0 = P.base_d / 2 + P.fit
        for ang in (45, 135, 225, 315):
            poly = sector(r0, r0 + P.loc_w, ang - P.loc_span_deg / 2, ang + P.loc_span_deg / 2)
            part.prism([0, 0, z0], [1, 0, 0], [0, 1, 0], poly, z1 - z0)
    else:
        hx, hy, w, l = P.base_l / 2 + P.fit, P.base_w / 2 + P.fit, P.loc_w, 25.0
        for sx in (-1, 1):
            for sy in (-1, 1):
                part.box([sx * hx, sy * (hy - l), z0], [sx * (hx + w), sy * (hy + w), z1])
                part.box([sx * (hx - l), sy * hy, z0], [sx * (hx + w), sy * (hy + w), z1])


def build_base(G, js, which):
    P = G.P
    xo, seam, zb = G.x_out, P.base_seam_y, G.z_base
    xr = G.x_rib                                   # seam ribs stop short of the wall feet
    zr = zb + P.seam_rib_h
    part = Part(f"base_{which}")
    if which == "front":
        part.box([-xo, G.y_front, 0], [xo, seam, zb])
        part.box([-xr, seam - P.seam_rib_t_insert, zb], [xr, seam, zr])
        for xc in G.key_x:   # alignment keys into the rear piece, between the seam screws
            part.box([xc - P.key_w / 2, seam - 1.0, 0], [xc + P.key_w / 2, seam + P.key_l, zr])  # 1 mm into the plate
        _locators(part, G)
    else:
        part.box([-xo, seam, 0], [xo, G.y_back_out, zb])
        part.box([-xr, seam, zb], [xr, seam + P.seam_rib_t, zr])
        for xc in G.key_x:
            kw = P.key_w / 2 + P.key_fit
            part.box([xc - kw, seam - 1, -1], [xc + kw, seam + P.key_l + P.key_fit, zr + 1], op="cut")
    # foot stubs: boss on top where the insert needs more depth, locating recess underneath
    feet = [(x, y) for x, y in G.feet() if (y < seam) == (which == "front")]
    s = P.inserts[P.foot_screw]
    for x, y in feet:
        if G.foot_top_boss > 0:
            part.cyl([x, y, zb - 0.5], [0, 0, 1], s["boss_d"], G.foot_top_boss + 0.5)
    for pname, p, n, c in parts_led.guides(G):          # cable guides (lighting)
        if pname == part.name:
            for base, axis, d, h in parts_led.guide_posts(G, p, n, c):
                part.cyl(base, axis, d, h)
    apply_joints(part, part.name, js, P)
    for x, y in feet:
        part.cyl([x, y, -1.0], [0, 0, 1], P.foot_d_top + P.foot_recess_clear, P.foot_recess_depth + 1.0,
                 op="cut")
    return part
