"""Assembly design for the SolidCraft app, plus assembled and exploded renders.

Needs build.py first (build/asm/*.stl, step/*.step)."""
import json
import os
import subprocess
import sys

import numpy as np

import meshio
from geom import Geo
from build import parse
from sc import BUILD, CLI, ROOT

RENDERS = os.path.join(ROOT, "renders")
ASM = os.path.join(BUILD, "asm")


def context_cmds(G, tilt=0.0):
    """Turntable, platter, model, Quick Mount and scanner stand-ins (primitive bodies)."""
    P = G.P
    c = []

    def body(cmd, name, **prm):
        c.append({"command": cmd, "params": {**prm, "operation": "new", "body_name": name}})

    def move(name, M):
        c.append({"command": "solid.move", "params": {"bodies": [name], "matrix": [[float(v) for v in r] for r in M]}})
    body("solid.cylinder", "TT_base", diameter=P.base_d - 4, height=G.z_axis - G.z_base + 6, base=[0, 0, G.z_base])
    zt = G.z_ptop - P.platter_t
    body("solid.cylinder", "TT_platter", diameter=P.platter_d, height=P.platter_t, base=[0, 0, zt])
    body("solid.cylinder", "Model", diameter=P.model_d, height=P.model_h, base=[0, 0, G.z_ptop])
    a = np.radians(tilt)
    R = np.array([[1, 0, 0], [0, np.cos(a), -np.sin(a)], [0, np.sin(a), np.cos(a)]])
    piv = np.array([0, 0, G.z_axis])
    Mt = np.hstack([R, (piv - R @ piv).reshape(3, 1)])
    move("TT_platter", Mt)
    move("Model", Mt)
    Mc = G.cradle_matrix(P.elevation)
    sm, h = G.s_mc, P.body_h
    body("solid.box", "Scanner", length=P.body_w, width=P.body_d, height=h,
         corner=[-P.body_w / 2, P.distance, -h / 2])
    body("solid.cylinder", "QuickMount", diameter=P.mount_disc_d, height=8.0, base=[P.mount_off_x, sm, G.t_f])
    c.append({"command": "solid.box", "params": {"length": 24, "width": 24, "height": P.mount_stack - 8.0,
              "corner": [P.mount_off_x - 12, sm - 12, G.t_f + 8.0], "operation": "join", "targets": ["QuickMount"]}})
    move("Scanner", Mc)
    move("QuickMount", Mc)
    return c


COLORS = {"led_cover": "#f6f6ee", "bay_cover": "#4a5260", "foot_stub": "#1c1c1c",
          "base": "#5b6470", "side": "#2f3540", "back": "#3a4250", "roof": "#2f3540",
          "cheek": "#c9822b", "cradle": "#d9a441", "TT_base": "#e6e6e6", "TT_platter": "#bfc7cf",
          "Model": "#f2e6c9", "Scanner": "#4d7fd1", "QuickMount": "#222222"}


def color_of(name):
    for k, v in COLORS.items():
        if name.startswith(k):
            return v
    return "#888888"


def snapshot(script_cmds, out, names, camera, see_through=(), w=1600, h=1200):
    path = os.path.join(BUILD, "render_" + os.path.basename(out).replace(".png", ".json"))
    with open(path, "w") as f:
        json.dump({"commands": script_cmds}, f)
    cmd = [CLI, "snapshot", path, "--out", out, "--width", str(w), "--height", str(h),
           "--camera", json.dumps(camera), "--no-axes", "--quality", "fine"]
    for n in names:
        op = ",opacity=0.18" if any(n.startswith(s) for s in see_through) else ""
        cmd += ["--body", f"{n}:color={color_of(n)}{op}"]
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        sys.exit(r.stderr[-2000:])


def part_names():
    return sorted(f[:-4] for f in os.listdir(ASM) if f.endswith(".stl"))


EXPLODE = {"base_front": (0, -40, 0), "base_rear": (0, 40, 0), "back": (0, 330, 0), "roof": (0, 0, 330),
           "side_left": (-330, 0, 0), "side_right": (330, 0, 0), "cheek_left": (-40, 60, 40),
           "cheek_right": (40, 60, 40), "cradle": (0, 60, 150), "foot_stub": (0, 0, -90),
           "led_cover_roof_left": (0, -150, 250), "led_cover_roof_right": (0, -150, 250),
           "led_cover_wall_left": (-250, 0, 90), "led_cover_wall_right": (250, 0, 90),
           "bay_cover": (0, 40, 120)}


def explode_vec(n):
    v = np.zeros(3)
    for k, d in EXPLODE.items():
        if n.startswith(k):
            v = np.array(d, float)
    if "upper" in n:
        v = v + (0, 0, 90)
    if n.startswith("side") and "rear" in n:
        v = v + (0, 90, 0)
    if n.startswith("roof") and "rear" in n:
        v = v + (0, 90, 0)
    return v


def main():
    P, _ = parse()
    G = Geo(P)
    os.makedirs(RENDERS, exist_ok=True)
    names = part_names()
    ctx = context_cmds(G)
    ctx_names = ["TT_base", "TT_platter", "Model", "Scanner", "QuickMount"]
    # assembly design for the app: the rounded print meshes in assembly pose + stand-ins
    # (the exact unrounded B-rep of each part is in step/ and cad/parts/)
    meshes = [{"command": "file.insert_mesh", "params": {"path": os.path.join(ASM, n + ".stl")}} for n in names]
    with open(os.path.join(BUILD, "assembly.json"), "w") as f:
        json.dump({"commands": meshes + ctx}, f)
    os.makedirs(os.path.join(ROOT, "cad"), exist_ok=True)
    subprocess.run([CLI, "run", os.path.join(BUILD, "assembly.json"), "--quiet", "--save",
                    os.path.join(ROOT, "cad", "scan-enclosure-assembly.solidcraft")], check=True)
    cam = {"target": [0, 70, 150], "yaw": -0.8, "pitch": 0.42, "distance": 1050, "fov": 0.6}
    snapshot(meshes + ctx, os.path.join(RENDERS, "assembled.png"), names + ctx_names, cam)
    snapshot(meshes + ctx, os.path.join(RENDERS, "assembled-see-through.png"), names + ctx_names, cam,
             see_through=("side_left", "side_right", "roof", "back"))
    ex_dir = os.path.join(BUILD, "explode")
    os.makedirs(ex_dir, exist_ok=True)
    ex = []
    for n in names:
        t = meshio.read_stl(os.path.join(ASM, n + ".stl")) + explode_vec(n)
        meshio.write_stl(os.path.join(ex_dir, n + ".stl"), t, n)
        ex.append({"command": "file.insert_mesh", "params": {"path": os.path.join(ex_dir, n + ".stl")}})
    cam_ex = {"target": [0, 120, 260], "yaw": -0.8, "pitch": 0.5, "distance": 2300, "fov": 0.6}
    snapshot(ex, os.path.join(RENDERS, "exploded.png"), names, cam_ex)
    print("renders written to", RENDERS)


if __name__ == "__main__":
    main()
