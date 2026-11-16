"""Wall and roof panels: skin + perimeter flanges (= ribs) + tongue-and-groove seams.

Each panel is modelled in its own print frame (outer skin face on the bed,
flanges rising), with every feature given as a world-aligned box that is
mapped into that frame. M is the panel's local -> world matrix."""
import numpy as np

import parts_led
from features import apply_joints
from sc import Part, frame_matrix, to_local


class Panel(Part):
    def __init__(self, name, M, P):
        super().__init__(name)
        self.M, self.P = M, P
        self.n = M[:, 2]                       # inward normal (world)
        self.o = float(M[:, 3] @ self.n)       # outer-face plane offset

    def wbox(self, lo, hi, op="join"):
        a, b = to_local(self.M, lo), to_local(self.M, hi)
        self.box(np.minimum(a, b), np.maximum(a, b), op)

    def web(self, p_local, a_local, d, length):
        """Flange boss: a block boss_d wide over the full flange depth (skin to tip), boss_len
        along the insert axis; flush with the flange tip, so it prints without overhang."""
        lo, hi = np.zeros(3), np.zeros(3)
        for k in range(2):
            if abs(a_local[k]) > 0.9:
                e = p_local[k] + a_local[k] * length
                lo[k], hi[k] = min(p_local[k], e), max(p_local[k], e)
            else:
                lo[k], hi[k] = p_local[k] - d / 2, p_local[k] + d / 2
        lo[2], hi[2] = 0.0, self.P.wall_t + self.P.flange_d
        self.box(lo, hi)


def _frame(kind, G):
    if kind == "right":
        return frame_matrix([G.x_out, 0, 0], [0, -1, 0], [0, 0, 1], [-1, 0, 0])
    if kind == "left":
        return frame_matrix([-G.x_out, 0, 0], [0, 1, 0], [0, 0, 1], [1, 0, 0])
    if kind == "back":
        return frame_matrix([0, G.y_back_out, 0], [1, 0, 0], [0, 0, 1], [0, -1, 0])
    return frame_matrix([0, 0, G.z_top], [-1, 0, 0], [0, 1, 0], [0, 0, -1])


def build_side(G, js, s, col, row):
    P = G.P
    sd = "right" if s > 0 else "left"
    name = f"side_{sd}_{col}_{row}"
    pn = Panel(name, _frame(sd, G), P)
    ft, fd, t, hb = P.flange_t, P.flange_d, P.wall_t, G.skin_boss_h
    ys, zs, yb = P.side_split_y, P.split_z, G.y_back_in
    y0, y1 = (G.y_front, ys) if col == "front" else (ys, G.y_back_out)
    yf1 = y1 if col == "front" else yb - hb        # flanges stop at the rear flange
    z0, z1 = (G.z_base, zs) if row == "lower" else (zs, G.z_rb)

    def X(a, b):                                   # inward offsets a..b from the outer face
        return sorted([s * (G.x_out - a), s * (G.x_out - b)])
    xs, xf = X(0, t), X(0, t + fd)
    ze = [z0, z0 + ft] if row == "lower" else [z1 - hb - ft, z1 - hb]     # foot / top flange (under roof bosses)
    if s == P.jack_side and col == "front" and row == "lower":
        # DC-jack pass-through, built in (not cut): the skin is one outline with the notch, so the
        # notch corners are rounded in 2D with the skin (inside corners filleted); the foot flange
        # stops at the notch and its ends are rounded as pieces
        w, zn = P.jack_notch_w / 2, z0 + P.jack_notch_h
        world = [(y0, z0), (-w, z0), (-w, zn), (w, zn), (w, z0), (y1, z0), (y1, z1), (y0, z1)]
        poly = [to_local(pn.M, [s * G.x_out, yy, zz])[:2] for yy, zz in world]
        pn.prism([0, 0, 0], [1, 0, 0], [0, 1, 0], poly, t)
        for a, b in ((y0, -w), (w, y1)):
            pn.wbox([xf[0], a, ze[0]], [xf[1], min(b, yf1), ze[1]])
    else:
        pn.wbox([xs[0], y0, z0], [xs[1], y1, z1])                             # skin
        pn.wbox([xf[0], y0, ze[0]], [xf[1], yf1, ze[1]])
    zh = [zs - ft, zs] if row == "lower" else [zs, zs + ft]               # horizontal seam flange
    pn.wbox([xf[0], y0, zh[0]], [xf[1], yf1, zh[1]])
    if col == "front":
        pn.wbox([xf[0], y0, z0], [xf[1], y0 + ft, z1])                    # open front edge
        pn.wbox([xf[0], ys - ft, z0], [xf[1], ys, z1])                    # vertical seam
    else:
        pn.wbox([xf[0], ys, z0], [xf[1], ys + ft, z1])
        pn.wbox([xf[0], yb - hb - ft, z0], [xf[1], yb - hb, z1])          # against the back-wall bosses
    xt = X(1.0, 2.0)                                                      # tongue: middle of the skin
    xg = X(1.0 - P.groove_fit, 2.0 + P.groove_fit)
    gl = P.tongue_l + P.groove_fit
    if row == "lower":
        pn.wbox([xt[0], y0 + 1, zs], [xt[1], y1 - 1, zs + P.tongue_l])
    else:
        pn.wbox([xg[0], y0 - 1, zs - 1], [xg[1], y1 + 1, zs + gl], op="cut")
    if col == "front":
        pn.wbox([xt[0], ys, z0 + 1], [xt[1], ys + P.tongue_l, z1 - 1])
    else:
        pn.wbox([xg[0], ys - 1, z0 - 1], [xg[1], ys + gl, z1 + 1], op="cut")
    parts_led.panel_features(pn, G, name)
    apply_joints(pn, name, js, P, pn.M, pn.web)
    return pn


def build_back(G, js, row):
    P = G.P
    name = f"back_{row}"
    pn = Panel(name, _frame("back", G), P)
    ft, fd, t, hb = P.flange_t, P.flange_d, P.wall_t, G.skin_boss_h
    yb, ybo, zs = G.y_back_in, G.y_back_out, P.split_z
    z0, z1 = (G.z_base, zs) if row == "lower" else (zs, G.z_rb)
    xi = G.x_in
    xt = xi - fd - 0.3                                   # clear the side-wall rear flanges
    pn.wbox([-xi, yb, z0], [xi, ybo, z1])
    ze = [z0, z0 + ft] if row == "lower" else [z1 - hb - ft, z1 - hb]
    zh = [zs - ft, zs] if row == "lower" else [zs, zs + ft]
    for zz in (ze, zh):
        pn.wbox([-xt, yb - fd, zz[0]], [xt, yb, zz[1]])
    for xr in (-G.back_rib_x, G.back_rib_x):            # vertical ribs, ends buried in the flanges
        pn.wbox([xr - ft / 2, yb - fd, z0], [xr + ft / 2, yb, z1 if row == "lower" else z1 - hb])
    if row == "lower":
        pn.wbox([-xi + 1, ybo - 2.0, zs], [xi - 1, ybo - 1.0, zs + P.tongue_l])
    else:
        g = P.groove_fit
        pn.wbox([-xi - 1, ybo - 2.0 - g, zs - 1], [xi + 1, ybo - 1.0 + g, zs + P.tongue_l + g], op="cut")
        w, h = P.usb_slot_w, P.usb_slot_h                # USB-C pass-through: one obround cut
        zc1 = G.z_rb - hb - ft - 8.0 - w / 2
        zc0 = zc1 - (h - w)
        a = np.radians(np.linspace(0, 180, 91))
        top = np.column_stack([w / 2 * np.cos(a), zc1 + w / 2 * np.sin(a)])
        bot = np.column_stack([-w / 2 * np.cos(a), zc0 - w / 2 * np.sin(a)])
        pn.prism([0, 0, -1.0], [1, 0, 0], [0, 1, 0], np.vstack([top, bot]), t + fd + 2.0, op="cut")
    parts_led.panel_features(pn, G, name)
    apply_joints(pn, name, js, P, pn.M, pn.web)
    return pn


def build_roof(G, js, col):
    P = G.P
    name = f"roof_{col}"
    pn = Panel(name, _frame("roof", G), P)
    ft, fd = P.flange_t, P.flange_d
    ys, yb, zr, zt = P.side_split_y, G.y_back_in, G.z_rb, G.z_top
    y0, y1 = (G.y_front, ys) if col == "front" else (ys, G.y_back_out)
    xo = G.x_out
    xl = G.x_in - fd - 0.3                               # locating flanges sit inside the side walls
    yl1 = ys if col == "front" else yb - fd - 0.3
    dl = 8.0
    pn.wbox([-xo, y0, zr], [xo, y1, zt])
    # at the open front the lips, rib and front flange stop edge_r behind the skin edge, so the
    # skin's rounded front edge runs uninterrupted (no flush feature end on a round)
    yf = y0 + P.edge_r if col == "front" else y0
    for sx in (-1, 1):                                                  # side locating flanges
        xa, xb = sorted([sx * xl, sx * (xl - ft)])
        pn.wbox([xa, yf, zr - dl], [xb, yl1, zr])
    pn.wbox([-ft / 2, yf + ft / 2 if col == "front" else y0, zr - dl], [ft / 2, yl1, zr])   # centre rib
    if col == "front":
        pn.wbox([-xl, yf, zr - dl], [xl, yf + ft, zr])                  # front edge
        pn.wbox([-xl, ys - ft, zr - fd], [xl, ys, zr])                  # seam
        pn.wbox([-xo + 1, ys, zr + 1.0], [xo - 1, ys + P.tongue_l, zr + 2.0])
    else:
        pn.wbox([-xl, yl1 - ft, zr - dl], [xl, yl1, zr])                # against the back wall
        pn.wbox([-xl, ys, zr - fd], [xl, ys + ft, zr])                  # seam
        g = P.groove_fit
        pn.wbox([-xo - 1, ys - 1, zr + 1.0 - g], [xo + 1, ys + P.tongue_l + g, zr + 2.0 + g], op="cut")
    parts_led.panel_features(pn, G, name)
    apply_joints(pn, name, js, P, pn.M, pn.web)
    return pn
