"""Section through the scanner plane (world X = 0): parts cut, cheek silhouette,
turntable at 0 / +-tilt with the model, scanner at the nominal pose (and the
adjustment extremes), view cone and aim point T. Writes renders/section-scanner-plane.png."""
import math
import os

import numpy as np
from PIL import Image, ImageDraw, ImageFont

import kin
import meshio
from geom import Geo
from build import parse
from sc import BUILD, ROOT

K = 3.0                      # px per mm
Y0, Y1, Z0, Z1 = -150.0, 300.0, -15.0, 345.0
W, H = int((Y1 - Y0) * K), int((Z1 - Z0) * K)


def px(y, z):
    return ((y - Y0) * K, H - (z - Z0) * K)


def font(sz):
    for f in ("/usr/share/fonts/dejavu-sans-fonts/DejaVuSans.ttf", "/usr/share/fonts/TTF/DejaVuSans.ttf"):
        if os.path.exists(f):
            return ImageFont.truetype(f, sz)
    return ImageFont.load_default(size=sz)


def poly_yz(d, pts, fill=None, outline=None, width=2):
    d.polygon([px(p[1], p[2]) for p in pts], fill=fill, outline=outline, width=width)


def dashed(d, a, b, fill, width=2, dash=10):
    a, b = np.array(px(*a)), np.array(px(*b))
    L = np.linalg.norm(b - a)
    n = max(1, int(L / dash))
    for i in range(0, n, 2):
        p, q = a + (b - a) * i / n, a + (b - a) * min(i + 1, n) / n
        d.line([tuple(p), tuple(q)], fill=fill, width=width)


def rect_world(G, M, y0, y1, z0, z1):
    return [(M[:, :3] @ np.array([0, y, z]) + M[:, 3]) for y, z in ((y0, z0), (y1, z0), (y1, z1), (y0, z1))]


def main():
    P, _ = parse()
    G = Geo(P)
    img = Image.new("RGB", (W, H + 150), "white")
    d = ImageDraw.Draw(img, "RGBA")
    asm = os.path.join(BUILD, "asm")
    # tower silhouettes projected on the plane: cheek hull, cradle triangles
    poly_yz(d, [(0, y, z) for y, z in G.cheek_poly], fill=(230, 160, 70, 70), outline=(200, 120, 40, 255))
    sil = Image.new("L", (W, H + 150), 0)
    ds_ = ImageDraw.Draw(sil)
    for tri in meshio.read_stl(os.path.join(asm, "cradle.stl")):
        ds_.polygon([px(p[1], p[2]) for p in tri], fill=255)
    img.paste(Image.new("RGB", img.size, (225, 165, 70)), (0, 0), sil.point(lambda v: 150 if v else 0))
    d = ImageDraw.Draw(img, "RGBA")
    # turntable base (stand-in) and platter + model at -tilt, 0, +tilt
    poly_yz(d, rect_world(G, kin.tilt_matrix(G, 0), -P.base_d / 2, P.base_d / 2, G.z_base, G.z_axis + 6),
            fill=(225, 225, 225, 255), outline=(150, 150, 150, 255))
    zt = G.z_ptop
    for tilt, col in ((-P.tilt_max, (40, 150, 60)), (P.tilt_max, (190, 60, 160)), (0.0, (90, 90, 90))):
        M = kin.tilt_matrix(G, tilt)
        a = 255 if tilt == 0 else 200
        poly_yz(d, rect_world(G, M, -P.platter_d / 2, P.platter_d / 2, zt - P.platter_t, zt),
                fill=(*col, 60 if tilt else 140), outline=(*col, a), width=3)
        poly_yz(d, rect_world(G, M, -P.model_d / 2, P.model_d / 2, zt, zt + P.model_h),
                fill=(240, 225, 190, 90 if tilt else 200), outline=(*col, a), width=3)
    # scanner extremes (outlines) and nominal pose (filled), quick mount
    for ph, ds in kin.scanner_poses(P):
        c = [G.body_to_world(ph, s, t) for s, t in ((ds, -P.body_h / 2), (ds + P.body_d, -P.body_h / 2),
                                                     (ds + P.body_d, P.body_h / 2), (ds, P.body_h / 2))]
        if (ph, ds) != (P.elevation, P.distance):
            poly_yz(d, c, outline=(77, 127, 209, 110), width=1)
    ph, ds = P.elevation, P.distance
    c = [G.body_to_world(ph, s, t) for s, t in ((ds, -P.body_h / 2), (ds + P.body_d, -P.body_h / 2),
                                                 (ds + P.body_d, P.body_h / 2), (ds, P.body_h / 2))]
    poly_yz(d, c, fill=(77, 127, 209, 230), outline=(30, 60, 140, 255))
    usb = [G.body_to_world(ph, s, t) for s, t in ((ds + P.body_d, -8), (ds + P.body_d + P.rear_clear, -8),
                                                   (ds + P.body_d + P.rear_clear, 8), (ds + P.body_d, 8))]
    poly_yz(d, usb, outline=(30, 60, 140, 255), width=1)
    m = [G.body_to_world(ph, G.s_mc + s, t) for s, t in ((-P.mount_disc_d / 2, G.t_f), (P.mount_disc_d / 2, G.t_f),
                                                          (12, -P.body_h / 2), (-12, -P.body_h / 2))]
    poly_yz(d, m, fill=(40, 40, 40, 220))
    # view cone (vertical FOV) and optical axis to T
    F = G.body_to_world(ph, ds, P.optic_off_t)
    hv = math.radians(P.fov_v_deg / 2)
    L = ds + 60
    for sg in (-1, 1):
        dirv = -G.e(ph) * math.cos(hv) + sg * G.u(ph) * math.sin(hv)
        d.line([px(*F[1:]), px(*(F + dirv * L)[1:])], fill=(230, 60, 40, 255), width=2)
    poly_yz(d, [F, F + (-G.e(ph) * math.cos(hv) - G.u(ph) * math.sin(hv)) * L,
                F + (-G.e(ph) * math.cos(hv) + G.u(ph) * math.sin(hv)) * L], fill=(230, 60, 40, 35))
    dashed(d, F[1:], G.T[1:], (230, 60, 40), 2)
    tx, ty = px(*G.T[1:])
    d.ellipse([tx - 7, ty - 7, tx + 7, ty + 7], outline=(200, 0, 0), width=3)
    # cut parts at X = 0 (drawn last so walls are on top)
    for f in sorted(os.listdir(asm)):
        segs = meshio.section_segments(meshio.read_stl(os.path.join(asm, f)), 0, 0.0)
        col = (200, 120, 40) if f.startswith(("cheek", "cradle")) else (20, 24, 32)
        for a, b in segs:
            d.line([px(a[1], a[2]), px(b[1], b[2])], fill=col, width=3)
    # labels
    f1, f2 = font(30), font(24)
    d.text((20, 15), "Section X = 0 (scanner plane = plane of tilt)", font=f1, fill="black")
    d.text((tx + 12, ty - 30), "T", font=f1, fill=(200, 0, 0))
    mid = (F + G.T) / 2
    mx, my = px(*mid[1:])
    d.text((mx + 10, my - 40), f"{P.distance:.0f} mm, {P.elevation:.0f} deg", font=f2, fill=(200, 0, 0))
    items = ((f"platter + {P.model_h:.0f} mm model at 0 deg", (90, 90, 90)),
             (f"tilt -{P.tilt_max:.0f} deg", (40, 150, 60)), (f"tilt +{P.tilt_max:.0f} deg", (190, 60, 160)),
             (f"scanner {P.elevation:.0f} deg / {P.distance:.0f} mm (outlines 30-50 deg, +-{P.dist_adjust:.0f} mm)",
              (77, 127, 209)),
             (f"view cone {P.fov_v_deg} deg vertical, axis to T", (230, 60, 40)),
             ("cheek and cradle (projected, behind the plane)", (200, 120, 40)),
             ("enclosure cut at X = 0", (20, 24, 32)))
    for i, (txt, col) in enumerate(items):
        lx, y = (20 if i % 2 == 0 else W // 2 - 60), H + 10 + 34 * (i // 2)
        d.rectangle([lx, y + 6, lx + 30, y + 26], fill=col)
        d.text((lx + 40, y), txt, font=f2, fill="black")
    # scale bar 100 mm, top right
    x0, y0 = W - 100 * K - 40, 32
    d.line([(x0, y0), (x0 + 100 * K, y0)], fill="black", width=4)
    d.text((x0 - 110, y0 - 15), "100 mm", font=f2, fill="black")
    out = os.path.join(ROOT, "renders", "section-scanner-plane.png")
    img.save(out)
    print(out)


if __name__ == "__main__":
    main()
