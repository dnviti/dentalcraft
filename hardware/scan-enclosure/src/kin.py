"""Turntable and scanner kinematics shared by validate.py and section.py."""
import math

import numpy as np


def tilt_matrix(G, deg):
    """Rotation about the tilt axis (world X through z_axis): 3x4 rigid matrix."""
    a = math.radians(deg)
    R = np.array([[1, 0, 0], [0, math.cos(a), -math.sin(a)], [0, math.sin(a), math.cos(a)]])
    piv = np.array([0.0, 0.0, G.z_axis])
    return np.hstack([R, (piv - R @ piv).reshape(3, 1)])


def sweep_distance(G, pts, tilts):
    """Distance from each world point to the platter + model, minimised over tilts.

    Platter and model are cylinders on the platter axis, so they are symmetric
    under the platter's own rotation. Returns (dist, tilt_of_min)."""
    P = G.P
    R, pt, rm, h = P.platter_d / 2, P.platter_t, P.model_d / 2, P.model_h
    z1 = G.z_ptop
    best = np.full(len(pts), np.inf)
    arg = np.zeros(len(pts))
    y, z = pts[:, 1], pts[:, 2] - G.z_axis
    rx2 = pts[:, 0] ** 2
    for t in tilts:
        a = math.radians(t)
        # rotate the point by -t into the platter frame
        yl = math.cos(a) * y + math.sin(a) * z
        zl = -math.sin(a) * y + math.cos(a) * z + G.z_axis
        rho = np.sqrt(rx2 + yl ** 2)
        d1 = np.hypot(np.maximum(rho - R, 0), np.maximum(np.maximum(z1 - pt - zl, zl - z1), 0))
        d2 = np.hypot(np.maximum(rho - rm, 0), np.maximum(np.maximum(z1 - zl, zl - z1 - h), 0))
        d = np.minimum(d1, d2)
        upd = d < best
        best[upd], arg[upd] = d[upd], t
    return best, arg


def box_samples(corner_fn, step=2.0):
    """Surface samples of a box given as corner_fn(i, j, k) with i, j, k in [0, 1]."""
    out = []
    n = 0
    for fixed in range(3):
        for side in (0.0, 1.0):
            g = np.linspace(0, 1, 40)
            for a in g:
                for b in g:
                    c = [a, b]
                    c.insert(fixed, side)
                    out.append(corner_fn(*c))
                    n += 1
    return np.array(out)


def scanner_samples(G, phi, dist, usb=False):
    P = G.P
    s0, s1 = (dist + P.body_d, dist + P.body_d + P.rear_clear) if usb else (dist, dist + P.body_d)

    def f(i, j, k):
        return G.body_to_world(phi, s0 + i * (s1 - s0), -P.body_h / 2 + j * P.body_h, -P.body_w / 2 + k * P.body_w)
    return box_samples(f)


def scanner_poses(P):
    return [(phi, P.distance + dd) for phi in (P.elev_min, P.elevation, P.elev_max)
            for dd in (-P.dist_adjust, 0.0, P.dist_adjust)]


def in_scanner_box(G, pts, phi, dist, usb=False, grow=0.0):
    """Mask of world points inside the scanner body (or USB-C clearance) box."""
    P = G.P
    s0, s1 = (dist + P.body_d, dist + P.body_d + P.rear_clear) if usb else (dist, dist + P.body_d)
    d = pts - G.T
    s, t = d @ G.e(phi), d @ G.u(phi)
    return ((s > s0 - grow) & (s < s1 + grow) & (np.abs(t) < P.body_h / 2 + grow)
            & (np.abs(pts[:, 0]) < P.body_w / 2 + grow))


def in_view_cone(G, pts, F, axis, depth_max):
    """Mask of points inside the view pyramid from F along axis, up to depth_max."""
    P = G.P
    ex = np.array([1.0, 0, 0])
    up = np.cross(axis, ex)
    up /= np.linalg.norm(up)
    d = pts - F
    dep = d @ axis
    ok = (dep > 0.5) & (dep < depth_max)
    th, tv = math.tan(math.radians(P.fov_h_deg / 2)), math.tan(math.radians(P.fov_v_deg / 2))
    return ok & (np.abs(d @ ex) < dep * th) & (np.abs(d @ up) < dep * tv)
