"""Derived layout: pose, frames, envelope and every screw joint, from params.

World frame (assembly): Z up, Z=0 is the table under the base. The turntable
centre is at X=Y=0, its tilt axis runs along X. The scanner sits on +Y in the
plane of tilt (X=0), the open front is at -Y.
Body frame of the scanner/cradle: s along the line of sight (T -> scanner),
t = body "up", x = world X.
"""
import math
import numpy as np


def rad(a):
    return math.radians(a)


class Geo:
    def __init__(self, P):
        self.P = P
        p = P
        self.z_base = p.base_t
        self.z_axis = p.base_t + p.tilt_axis_h
        self.z_ptop = self.z_axis + p.platter_above_axis
        self.T = np.array([0.0, 0.0, self.z_ptop + p.target_above_platter])
        self.x_in = p.platter_d / 2 + p.side_clear
        self.x_out = self.x_in + p.wall_t
        base_y = p.base_d if p.base_shape == "round" else p.base_w
        self.y_front = -(base_y / 2 + p.front_margin)
        # cradle (body frame)
        self.x_gi = p.body_w / 2 + p.guide_clear
        self.x_go = self.x_gi + p.cradle_side_t
        self.s_mc = p.distance + p.body_d / 2 + p.mount_off_s
        self.ch_len = 2 * p.dist_adjust + p.mount_disc_d + 1.0
        self.ch_w = p.mount_disc_d + 1.0
        self.t_f = -p.body_h / 2 - p.mount_stack
        self.t_pt = self.t_f + p.channel_depth
        self.t_pb = self.t_f - p.cradle_plate_under
        self.t_top = -p.body_h / 2 + p.end_guide_overlap
        self.s0 = self.s_mc - self.ch_len / 2 - p.cradle_margin
        self.s1 = self.s_mc + self.ch_len / 2 + p.cradle_margin
        self.bolts = [(self.s_mc - p.bolt_ds, p.bolt_t), (self.s_mc + p.bolt_ds, p.bolt_t)]
        # cheeks
        self.xc0 = self.x_go
        self.xc1 = self.x_go + p.cheek_t
        # joints: skin bosses, rib extents, foot stub screw stack
        m3 = p.inserts["M3"]
        self.skin_boss_h = m3["boss_len"] - p.wall_t
        self.x_rib = self.x_in - p.flange_d - 1.0            # base seam ribs stop short of the wall feet
        self.back_rib_x = self.x_in - 17.0                   # vertical ribs of the back wall
        fi = p.inserts[p.foot_screw]
        longest = max(L for L in p.screw_lengths
                      if p.foot_h - (L - p.foot_engage) >= p.m3_head_h + 0.5)
        self.foot_screw_len = longest
        self.foot_clamp = longest - p.foot_engage            # stub length under the counterbore
        self.foot_cbore = p.foot_h - self.foot_clamp
        self.foot_top_boss = max(0.0, p.foot_recess_depth + fi["boss_len"] - p.base_t)
        self.key_x = []
        self._cheek_outline()
        self._envelope()

    # ---- pose ---------------------------------------------------------
    def e(self, phi):
        return np.array([0.0, math.cos(rad(phi)), math.sin(rad(phi))])

    def u(self, phi):
        return np.array([0.0, -math.sin(rad(phi)), math.cos(rad(phi))])

    def body_to_world(self, phi, s, t, x=0.0):
        return self.T + x * np.array([1.0, 0, 0]) + s * self.e(phi) + t * self.u(phi)

    def cradle_matrix(self, phi):
        """Rigid 3x4 matrix: cradle local (x, s, t) -> world."""
        e, u = self.e(phi), self.u(phi)
        R = np.column_stack([[1.0, 0, 0], e, u])
        return np.hstack([R, self.T.reshape(3, 1)])

    def scanner_box(self, phi, dist, usb=False):
        """World corners of the scanner body (or of its USB-C clearance box)."""
        p = self.P
        s_a, s_b = (dist + p.body_d, dist + p.body_d + p.rear_clear) if usb else (dist, dist + p.body_d)
        pts = []
        for s in (s_a, s_b):
            for t in (-p.body_h / 2, p.body_h / 2):
                for x in (-p.body_w / 2, p.body_w / 2):
                    pts.append(self.body_to_world(phi, s, t, x))
        return np.array(pts)

    def cradle_corners(self, phi):
        pts = [self.body_to_world(phi, s, t, x) for s in (self.s0, self.s1)
               for t in (self.t_pb, self.t_top) for x in (-self.x_go, self.x_go)]
        return np.array(pts)

    # ---- cheek outline (world Y,Z) -------------------------------------
    def bolt_arc(self, i):
        s, t = self.bolts[i]
        r = math.hypot(s, t)
        d = math.degrees(math.atan2(t, s))
        return r, self.P.elev_min + d, self.P.elev_max + d

    def _cheek_outline(self):
        p = self.P
        pts = []
        for i in range(2):
            r, a0, a1 = self.bolt_arc(i)
            rr = p.m3_clear / 2 + p.cheek_margin
            for a in np.linspace(a0, a1, 25):
                c = self.T[1:] + r * np.array([math.cos(rad(a)), math.sin(rad(a))])
                for b in np.linspace(0, 360, 24, endpoint=False):
                    pts.append(c + rr * np.array([math.cos(rad(b)), math.sin(rad(b))]))
        pts = np.array(pts)
        self.yf0 = p.base_seam_y + p.seam_rib_t + 3.0
        self.yf1 = max(pts[:, 0].max(), self.yf0 + 90.0)
        pts = np.vstack([pts, [[self.yf0, self.z_base], [self.yf1, self.z_base]]])
        self.cheek_poly = convex_hull(pts)
        self.cheek_ymax = self.cheek_poly[:, 0].max()
        self.cheek_zmax = self.cheek_poly[:, 1].max()
        # ribs stand inside the plate outline: clip foot and gussets to it, inset by rib_inset
        zf = self.z_base + p.cheek_foot_t
        lo, hi = strip_range(self.cheek_poly, self.z_base, zf)
        self.foot_y = (lo + p.rib_inset, hi - p.rib_inset)
        lo, hi = strip_range(self.cheek_poly, zf, zf + p.cheek_gusset_h)
        self.gusset_y = (lo + p.rib_inset, hi - p.rib_inset)

    def feet(self):
        """Foot stub centres (x, y): inset so the sleeve clears edges and the base seam."""
        p = self.P
        k = p.sleeve_d / 2 + p.sleeve_clear
        xs = self.x_out - k
        ys = (self.y_front + k, self.y_back_out - k)
        for y in ys:
            if abs(y - p.base_seam_y) < k:
                raise ValueError("a foot sleeve would cross the base seam")
        return [(sx * xs, y) for y in ys for sx in (-1, 1)]

    def boss_d(self, thread="M3"):
        return self.P.inserts[thread]["boss_d"]

    # ---- envelope -----------------------------------------------------
    def _envelope(self):
        p = self.P
        pts = [self.scanner_box(p.elevation, p.distance, usb=True)]
        for phi in (p.elev_min, p.elevation, p.elev_max):
            pts.append(self.cradle_corners(phi))
            for dd in (-p.dist_adjust, 0.0, p.dist_adjust):
                pts.append(self.scanner_box(phi, p.distance + dd))
        pts = np.vstack(pts)
        ymax = max(pts[:, 1].max(), self.cheek_ymax)
        zmax = max(pts[:, 2].max(), self.cheek_zmax)
        self.y_back_in = math.ceil(ymax + p.back_clear + p.flange_d)
        self.y_back_out = self.y_back_in + p.wall_t
        self.z_rb = math.ceil(zmax + p.roof_clear)
        self.z_top = self.z_rb + p.wall_t

    def summary(self):
        return dict(T=self.T.tolist(), x_out=self.x_out, y_front=self.y_front,
                    y_back_out=self.y_back_out, z_top=self.z_top, z_rb=self.z_rb,
                    outer=[2 * self.x_out, self.y_back_out - self.y_front, self.z_top])


def strip_range(poly, z0, z1, n=60):
    """Y interval (lo, hi) fully inside the convex polygon (y, z) for every z in [z0, z1]."""
    zs = np.concatenate([np.linspace(z0, z1, n), poly[(poly[:, 1] >= z0) & (poly[:, 1] <= z1), 1]])
    lo, hi = -np.inf, np.inf
    m = len(poly)
    for z in zs:
        xs = []
        for i in range(m):
            a, b = poly[i], poly[(i + 1) % m]
            if (a[1] - z) * (b[1] - z) <= 0 and a[1] != b[1]:
                xs.append(a[0] + (b[0] - a[0]) * (z - a[1]) / (b[1] - a[1]))
            elif a[1] == b[1] == z:
                xs += [a[0], b[0]]
        if not xs:
            raise ValueError(f"z={z} is outside the outline")
        lo, hi = max(lo, min(xs)), min(hi, max(xs))
    return lo, hi


def convex_hull(pts):
    """Monotone chain, CCW, no repeated end point."""
    pts = sorted(set(map(lambda q: (round(q[0], 4), round(q[1], 4)), pts)))

    def cross(o, a, b):
        return (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])
    lower, upper = [], []
    for q in pts:
        while len(lower) >= 2 and cross(lower[-2], lower[-1], q) <= 0:
            lower.pop()
        lower.append(q)
    for q in reversed(pts):
        while len(upper) >= 2 and cross(upper[-2], upper[-1], q) <= 0:
            upper.pop()
        upper.append(q)
    return np.array(lower[:-1] + upper[:-1])


def simplify(poly, min_len=4.0):
    """Drop hull vertices closer than min_len to the previous kept one."""
    out = [poly[0]]
    for q in poly[1:]:
        if np.linalg.norm(q - out[-1]) >= min_len:
            out.append(q)
    if np.linalg.norm(out[-1] - out[0]) < min_len:
        out.pop()
    return np.array(out)


if __name__ == "__main__":
    import json
    from params import load
    g = Geo(load())
    print(json.dumps(g.summary(), indent=1))
    print("cheek z max", g.cheek_zmax, "ymax", g.cheek_ymax, "foot", g.yf0, g.yf1)
    print("bolt arcs", [g.bolt_arc(i) for i in range(2)])
