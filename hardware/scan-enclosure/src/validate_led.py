"""Lighting checks: the lit diffuser covers stay outside the camera view cone (every scanner pose,
+3 deg margin), the sensor collar hides the platter from the sensor, the lighting parts stay
clear of the cable pass-throughs."""
import math

import numpy as np

import kin
import meshio
import parts_led

CONE_MARGIN = 3.0          # deg, added to each half-angle of the view cone


def box_dist(lo1, hi1, lo2, hi2):
    gap = np.maximum(0, np.maximum(lo1 - hi2, lo2 - hi1))
    return float(np.linalg.norm(gap))


def cone_margin(G, pts, F, axis):
    """Smallest angular distance (deg) of the points outside the view pyramid (negative inside)."""
    P = G.P
    ex = np.array([1.0, 0, 0])
    up = np.cross(axis, ex)
    up /= np.linalg.norm(up)
    d = pts - F
    dep = d @ axis
    ah = np.degrees(np.arctan2(np.abs(d @ ex), dep)) - P.fov_h_deg / 2
    av = np.degrees(np.arctan2(np.abs(d @ up), dep)) - P.fov_v_deg / 2
    return float(np.max(np.stack([ah, av]), axis=0).min())


def led_checks(P, G, asm, F):
    lines, fails = [], []
    e0, u0 = G.e(P.elevation), G.u(P.elevation)
    sF, tF, xF = (F - G.T) @ e0, (F - G.T) @ u0, F[0]
    lit_h = parts_led.cover_h(P)[1]
    worst = (1e9, None)
    total = 0
    for r in parts_led.runs(G):
        cov = asm[f"led_cover_{r['name']}"]
        pts = meshio.surface_samples(cov, 2.0)
        pts = pts[np.abs((pts - r["o"]) @ r["n"] - lit_h) < 0.05]          # the face that glows
        total += len(pts)
        for ph, ds in kin.scanner_poses(P):
            Fp = G.body_to_world(ph, sF + ds - P.distance, tF, xF)
            m = cone_margin(G, pts, Fp, -G.e(ph))
            if m < worst[0]:
                worst = (m, f"{r['name']} at {ph:.0f} deg / {ds:.0f} mm")
    lines.append(f"- {total} points on the lit faces of the 4 diffuser covers; nearest to the camera view cone "
                 f"({P.fov_h_deg} x {P.fov_v_deg} deg, 9 poses): {worst[0]:.1f} deg outside ({worst[1]}), "
                 f"required {CONE_MARGIN:.0f}")
    if worst[0] < CONE_MARGIN:
        fails.append(f"lit diffuser {worst[1]} only {worst[0]:.1f} deg outside the camera view cone")
    # sensor: the flat collar under the tip hides everything more than atan(below / r_collar) under
    # the tip plane; the platter must stay hidden at every tilt.
    S0, a = parts_led.sensor(G)
    dep = math.degrees(math.atan2(P.sensor_collar_below, P.sensor_collar_d / 2))
    ang = np.linspace(0, 2 * math.pi, 180, endpoint=False)
    below = {}
    for tilt in (-P.tilt_max, 0.0, P.tilt_max):
        R = kin.tilt_matrix(G, tilt)
        p = np.column_stack([P.platter_d / 2 * np.cos(ang), P.platter_d / 2 * np.sin(ang), np.full(len(ang), G.z_ptop)])
        v = p @ R[:, :3].T + R[:, 3] - S0
        below[tilt] = float(np.degrees(np.arcsin(np.clip(-(v @ a) / np.linalg.norm(v, axis=1), -1, 1))).min())
    lines.append(f"- light sensor (tip {np.round(S0, 1).tolist()}, axis {P.sensor_tilt:.0f} deg towards the front): "
                 f"the collar hides everything more than {dep:.1f} deg below the tip plane; platter rim at least "
                 + ", ".join(f"{v:.1f} deg below at tilt {t:+.0f}" for t, v in below.items()))
    if min(below.values()) <= dep:
        fails.append("the light sensor sees the platter past its collar")
    mt = G.z_ptop + P.model_h
    m_pts = np.column_stack([P.model_d / 2 * np.cos(ang), P.model_d / 2 * np.sin(ang), np.full(len(ang), mt)])
    mb = 90.0
    for tilt in (-P.tilt_max, 0.0, P.tilt_max):
        R = kin.tilt_matrix(G, tilt)
        v = m_pts @ R[:, :3].T + R[:, 3] - S0
        mb = min(mb, float(np.degrees(np.arcsin(np.clip(-(v @ a) / np.linalg.norm(v, axis=1), -1, 1))).min()))
    lines.append(f"- model envelope top rim (D{P.model_d:.0f} x {P.model_h:.0f}): at least {mb:.1f} deg below the tip plane")
    if mb <= dep:
        fails.append("the light sensor sees the model envelope past its collar")
    # pass-throughs: DC-jack notch and USB-C slot vs lighting features
    s = P.jack_side
    jack = (np.array([s * G.x_out - (3 + P.flange_d) * (s > 0) - 1, -P.jack_notch_w / 2, G.z_base]),
            np.array([s * G.x_out + (3 + P.flange_d) * (s < 0) + 1, P.jack_notch_w / 2, G.z_base + P.jack_notch_h]))
    jack = (np.minimum(*jack), np.maximum(*jack))
    w, h = P.usb_slot_w, P.usb_slot_h
    zc1 = G.z_rb - G.skin_boss_h - P.flange_t - 8.0
    usb = (np.array([-w / 2, G.y_back_in - P.flange_d, zc1 - h]), np.array([w / 2, G.y_back_out, zc1]))
    feats = []
    for part, p, n, c in parts_led.guides(G):
        for pts in parts_led.guide_boxes(G, n, c):
            feats.append((f"cable guide on {part}", pts.min(0) + p, pts.max(0) + p))
    _, _, cw, ch = parts_led.bay(G)
    feats.append(("bay cover", np.array([-cw / 2, P.bay_y - ch / 2, G.z_base]),
                  np.array([cw / 2, P.bay_y + ch / 2, G.z_base + parts_led.bay_cover_h(P)])))
    for r in parts_led.runs(G):
        for lo, hi in parts_led.channel_boxes(G, r)[0]:
            feats.append((f"LED channel {r['name']}", lo, hi))
    near = min((min(box_dist(lo, hi, *jack), box_dist(lo, hi, *usb)), name) for name, lo, hi in feats)
    lines.append(f"- lighting features vs the DC-jack notch and USB-C slot: nearest {near[0]:.0f} mm ({near[1]})")
    if near[0] < 5.0:
        fails.append(f"{near[1]} within {near[0]:.1f} mm of a cable pass-through")
    return lines, fails
