"""Rounding zones per part, as point sets in world coordinates (each zone = its corner points;
the rounding step maps them to the print frame and takes their bounding box there).

lead_in: fits that need only a 0.3 mm lead-in (holes, dowels, tongues, grooves, keys, slots,
disc channel, scale ticks). corner: hand-reachable edges of the open front (corner_r)."""
import math

import numpy as np


def box(lo, hi):
    lo, hi = np.minimum(lo, hi), np.maximum(lo, hi)
    return np.array([[x, y, z] for x in (lo[0], hi[0]) for y in (lo[1], hi[1]) for z in (lo[2], hi[2])])


def capsule(p0, p1, r):
    """Box around a segment with radius r (segments here are axis-aligned or short)."""
    p0, p1 = np.asarray(p0, float), np.asarray(p1, float)
    return box(np.minimum(p0, p1) - r, np.maximum(p0, p1) + r)


def zones_for(name, G, js):
    P = G.P
    lead, corner = [], []
    for j in js:
        if name not in (j["clear"], j["insert"]) and not (name == "foot_stub" and j["clear"].startswith("foot")):
            continue
        p, a = j["p"], j["a"]
        s = P.inserts[j["thread"]]
        if j["kind"] == "dowel":
            r = P.dowel_d / 2 + P.dowel_fit + 0.7
            lead.append(capsule(p - a * (j["clamp"] + 1), p + a * 0.5, r))     # hole in the clear part
            lead.append(capsule(p, p - a * (P.dowel_h + 0.5), r))               # pin on the insert part
        elif j["insert"] == name:
            lead.append(capsule(p - a * 0.5, p + a * (s["hole_depth"] + 0.5), s["hole_d"] / 2 + 0.7))
        else:
            lead.append(capsule(p - a * (j["clamp"] + 1), p + a * 0.5, P.m3_clear / 2 + 0.7))
    xs0, xs1 = G.x_in - 0.2, G.x_out + 0.2
    ys, zs, yb, ybo = P.side_split_y, P.split_z, G.y_back_in, G.y_back_out
    tl = P.tongue_l + 1.0
    if name.startswith("side"):
        for sx in (-1, 1):
            lead.append(box([sx * xs0, G.y_front - 1, zs - 1], [sx * xs1, ybo + 1, zs + tl]))
            lead.append(box([sx * xs0, ys - 1, G.z_base - 1], [sx * xs1, ys + tl, G.z_rb + 1]))
    if name.startswith("back"):
        lead.append(box([-G.x_in - 1, yb - 0.2, zs - 1], [G.x_in + 1, ybo + 0.2, zs + tl]))
    if name.startswith("roof"):
        lead.append(box([-G.x_out - 1, ys - 1, G.z_rb - 0.2], [G.x_out + 1, ys + tl, G.z_top + 0.2]))
    if name.startswith("base"):
        for xc in G.key_x:
            w = P.key_w / 2 + P.key_fit + 1.0
            lead.append(box([xc - w, P.base_seam_y - 1, -1], [xc + w, P.base_seam_y + P.key_l + 1.5,
                                                            G.z_base + P.seam_rib_h + 1]))
    if name.startswith("cheek"):
        s = 1 if name.endswith("right") else -1
        x0, x1 = s * (G.xc0 - 0.5), s * (G.xc1 + 0.5)
        for i in range(2):
            r, a0, a1 = G.bolt_arc(i)
            for ang in np.arange(a0 - 3, a1 + 3.01, 1.0):
                c = G.T[1:] + r * np.array([math.cos(math.radians(ang)), math.sin(math.radians(ang))])
                w = P.m3_clear / 2 + 0.8
                lead.append(box([x0, c[0] - w, c[1] - w], [x1, c[0] + w, c[1] + w]))
            if i == 1:          # elevation ticks beside the outer slot
                for ang in np.arange(a0, a1 + 0.01, 1.0):
                    for rr in np.arange(r + 4, r + 12, 2.0):
                        c = G.T[1:] + rr * np.array([math.cos(math.radians(ang)), math.sin(math.radians(ang))])
                        lead.append(box([x0, c[0] - 1.6, c[1] - 1.6], [x1, c[0] + 1.6, c[1] + 1.6]))
    if name == "cradle":
        M = G.cradle_matrix(P.elevation)

        def W(lo, hi):
            return box(lo, hi) @ M[:, :3].T + M[:, 3]
        xm = P.mount_off_x
        lead.append(W([xm - G.ch_w / 2 - 1, G.s_mc - G.ch_len / 2 - 1, G.t_f - 1],
                      [xm + G.ch_w / 2 + 10, G.s_mc + G.ch_len / 2 + 1, G.t_pt + 1]))
        lead.append(W([xm - P.quarter_clear / 2 - 1, G.s_mc - P.dist_adjust - P.quarter_clear / 2 - 1, G.t_pb - 1],
                      [xm + P.quarter_clear / 2 + 1, G.s_mc + P.dist_adjust + P.quarter_clear / 2 + 1, G.t_f + 1]))
    front = ("side_left_front", "side_right_front", "roof_front", "base_front")
    if name.startswith(front):
        corner.append(box([-G.x_out - 1, G.y_front - 1, -1], [G.x_out + 1, G.y_front + P.flange_t + 1, G.z_top + 1]))
    import parts_led
    lead += parts_led.lead_zones(G, name)
    return dict(lead_in=lead, corner=corner)
