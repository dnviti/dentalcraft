"""Scanner tower: two cheeks with arc slots centred on the aim line through T,
and the cradle that carries the scanner (disc channel + 1/4"-20 slot + end guides).

Rotating the cradle in the arc slots changes the elevation while the optical
axis keeps passing through T; the 1/4" slot slides the scanner along the line
of sight."""
import math

import numpy as np

from features import apply_joints
from geom import simplify
from sc import Part, frame_matrix


def cheek_frame(G, s):
    """Print frame: inner face on the bed, outward = up."""
    return frame_matrix([s * G.xc0, 0, 0], [0, s, 0], [0, 0, 1], [s, 0, 0])


def _tick(c, r0, r1, a, w):
    """Radial tick (rectangle) in the plane, from radius r0 to r1 at angle a (deg)."""
    d = np.array([math.cos(math.radians(a)), math.sin(math.radians(a))])
    n = np.array([-d[1], d[0]]) * w / 2
    return [c + d * r0 - n, c + d * r1 - n, c + d * r1 + n, c + d * r0 + n]


def gusset_positions(G):
    """Gussets inside the clipped range, clear of the foot screws and dowels (heads, iron)."""
    P = G.P
    g0, g1 = G.gusset_y[0] + P.cheek_gusset_t / 2 + 1.0, G.gusset_y[1] - P.cheek_gusset_t / 2 - 1.0  # ends off the foot ends
    keep = sorted(G.cheek_screw_y + G.cheek_dowel_y)
    cand = [g0, g1] + [(keep[i] + keep[i + 1]) / 2 for i in range(len(keep) - 1)]
    room = P.cheek_gusset_t / 2 + P.m3_head_d / 2 + 1.0
    return sorted({round(y, 3) for y in cand if g0 - 1e-6 <= y <= g1 + 1e-6
                   and all(abs(y - k) >= room for k in keep)})


def build_cheek(G, js, s):
    P = G.P
    name = f"cheek_{'right' if s > 0 else 'left'}"
    part = Part(name)
    xd, yd = [0, s, 0], [0, 0, 1]

    def sk(q):                      # world (y, z) -> sketch coords on a YZ plane with x_dir (0, s, 0)
        return [s * q[0], q[1]]

    def sa(a):                      # world angle in YZ -> sketch angle
        return a if s > 0 else 180.0 - a
    poly = [sk(q) for q in simplify(G.cheek_poly)]
    part.prism([s * G.xc0, 0, 0], xd, yd, poly, P.cheek_t)
    zb, zf = G.z_base, G.z_base + P.cheek_foot_t
    x1, x2 = sorted([s * G.xc1, s * (G.xc1 + P.cheek_foot_w)])
    f0, f1 = G.foot_y                                             # clipped to the plate outline
    part.box([x1, f0, zb], [x2, f1, zf])                          # outer foot
    for y in gusset_positions(G):
        # triangle corner in the plate/foot corner; both tips carried 3 mm on along the hypotenuse
        # into the foot and the plate, so the gusset meets them with its sloped face, not a tip
        A = np.array([G.xc1 - 0.5, zf - 0.5])
        B = np.array([G.xc1 + P.cheek_foot_w - 3.0, zf - 0.5])
        C = np.array([G.xc1 - 0.5, zf + P.cheek_gusset_h])
        hyp = (B - C) / np.linalg.norm(B - C)
        tri = [A, B + hyp * 3.0, C - hyp * 3.0]
        part.prism([0, y, 0], [s, 0, 0], [0, 0, 1], [list(map(float, q)) for q in tri], P.cheek_gusset_t,
                   symmetric=True)
    c = sk(G.T[1:])
    for i in range(2):
        r, a0, a1 = G.bolt_arc(i)
        b0, b1 = sorted([sa(a0), sa(a1)])
        part.arc_slot([s * G.xc0, 0, 0], xd, yd, c, r, b0, b1, P.m3_clear, 4 * P.cheek_t)
    # elevation ticks on the outer face, beside the outer slot
    r, a0, _ = G.bolt_arc(1)
    k = 0
    while P.elev_min + k * P.elev_ticks <= P.elev_max + 1e-9:
        phi = P.elev_min + k * P.elev_ticks
        a = sa(a0 + phi - P.elev_min)
        r1 = r + P.m3_clear / 2 + (7.0 if abs(phi - P.elevation) < 1e-6 else 4.5)
        part.prism([s * G.xc1, 0, 0], xd, yd, _tick(c, r + P.m3_clear / 2 + 3.2, r1 + 2.0, a, 1.5),
                   2.0, op="cut", symmetric=True)
        k += 1
    apply_joints(part, name, js, P)
    return part


def build_cradle(G, js):
    """Built in its local frame (x, s, t) = print frame; G.cradle_matrix(phi) places it."""
    P = G.P
    part = Part("cradle")
    xo, xi = G.x_go, G.x_gi
    part.box([-xo, G.s0, G.t_pb], [xo, G.s1, G.t_pt])                       # mount plate
    for sx in (-1, 1):
        a, b = sorted([sx * xi, sx * xo])
        part.box([a, G.s0, G.t_pb], [b, G.s1, G.t_top])                     # side plates / end guides
    xm = P.mount_off_x
    part.box([xm - G.ch_w / 2, G.s_mc - G.ch_len / 2, G.t_f], [xm + G.ch_w / 2, G.s_mc + G.ch_len / 2, G.t_pt + 1],
             op="cut")                                                       # disc channel
    q = P.quarter_clear
    part.box([xm - q / 2, G.s_mc - P.dist_adjust, G.t_pb - 1], [xm + q / 2, G.s_mc + P.dist_adjust, G.t_f + 1],
             op="cut")                                                       # 1/4"-20 slot
    for sc_ in (G.s_mc - P.dist_adjust, G.s_mc + P.dist_adjust):
        part.cyl([xm, sc_, G.t_pb - 1], [0, 0, 1], q, G.t_f - G.t_pb + 2, op="cut")
    # distance ticks beside the channel: disc front edge at -adj..+adj every 5 mm
    k = -int(P.dist_adjust // 5)
    while k * 5 <= P.dist_adjust + 1e-9:
        sx = G.s_mc - P.mount_disc_d / 2 + k * 5
        ln = 7.0 if k == 0 else 4.5
        x0 = xm + G.ch_w / 2 + 1.5
        part.box([x0, sx - 0.4, G.t_pt - 0.8], [x0 + ln, sx + 0.4, G.t_pt + 1], op="cut")
        k += 1
    apply_joints(part, "cradle", js, P, G.cradle_matrix(P.elevation))
    return part
