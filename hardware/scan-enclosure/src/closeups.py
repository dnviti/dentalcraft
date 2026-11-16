"""Close-up renders of joints, rounding and feet (renders/closeup-*.png). Needs build.py."""
import json
import os
import subprocess

import joints
import parts_tower
from build import parse
from geom import Geo
from sc import BUILD, CLI, ROOT

ASM = os.path.join(BUILD, "asm")
OUT = os.path.join(ROOT, "renders")


def shot(name, bodies, cam, extra=(), see=(), w=1200, h=900):
    cmds = [{"command": "file.insert_mesh", "params": {"path": os.path.join(ASM, b + ".stl")}} for b in bodies]
    cmds += list(extra)
    path = os.path.join(BUILD, f"closeup_{name}.json")
    json.dump({"commands": cmds}, open(path, "w"))
    cmd = [CLI, "snapshot", path, "--out", os.path.join(OUT, f"closeup-{name}.png"), "--width", str(w),
           "--height", str(h), "--no-axes", "--quality", "fine", "--camera", json.dumps(cam)]
    colors = ["#c98a3b", "#5b6470", "#d9a441", "#3a4250"]
    for i, b in enumerate(bodies):
        op = ",opacity=0.25" if b in see else ""
        cmd += ["--body", f"{b}:color={colors[i % len(colors)]}{op}"]
    for e in extra:
        nm = e["params"].get("body_name")
        if nm:
            cmd += ["--body", f"{nm}:color=#3060d0,opacity=0.3"]
    subprocess.run(cmd, check=True, capture_output=True)


def main():
    P, _ = parse()
    G = Geo(P)
    joints.build_joints(G)                 # sets the cheek screw and dowel positions
    os.makedirs(OUT, exist_ok=True)
    f0, f1 = G.foot_y
    zb = G.z_base
    # 1. the reviewed corner: right cheek, front of the foot and gussets (same camera as "before")
    shot("cheek-front-after", ["cheek_right"],
         {"target": [92, 138, 35], "yaw": -0.8, "pitch": 0.3, "distance": 170, "fov": 0.6})
    # 2. base seam: rib, keys, inserts (rear half see-through)
    shot("joint-base-seam", ["base_front", "base_rear"],
         {"target": [30, P.base_seam_y, zb + 6], "yaw": -2.3, "pitch": 0.55, "distance": 160, "fov": 0.6},
         see=("base_rear",))
    # 3. wall-roof corner from inside: roof skin bosses on the lowered side top flange
    shot("joint-wall-roof", ["side_right_front_upper", "roof_front"],
         {"target": [108, -40, G.z_rb - 8], "yaw": 2.6, "pitch": -0.35, "distance": 150, "fov": 0.6},
         see=("roof_front",))
    # 4. cheek foot on the base: dowels and screws
    shot("joint-cheek-base", ["cheek_right", "base_rear"],
         {"target": [92, (f0 + f1) / 2, zb + 5], "yaw": -0.5, "pitch": 0.7, "distance": 190, "fov": 0.6})
    # 5. outer panel corner, rounded
    shot("round-panel-corner", ["side_left_front_lower"],
         {"target": [-118, G.y_front + 4, zb + 4], "yaw": -0.6, "pitch": 0.45, "distance": 70, "fov": 0.6})
    # 6. gusset root on the cheek foot
    shot("round-gusset-root", ["cheek_right"],
         {"target": [86, (f0 + f1) / 2, zb + 14], "yaw": -0.2, "pitch": 0.35, "distance": 80, "fov": 0.6})
    # 6b. panel flange end: back_lower foot flange ending short of the side wall, seen from inside
    xt = G.x_in - P.flange_d - 0.3
    shot("round-flange-end", ["back_lower"],
         {"target": [xt, G.y_back_in - P.flange_d / 2, zb + 6], "yaw": -0.6, "pitch": 0.5, "distance": 70,
          "fov": 0.6})
    # 6c. base corner (rear right, outside)
    shot("round-base-corner", ["base_rear"],
         {"target": [G.x_out - 4, G.y_back_out - 4, 4], "yaw": 0.7, "pitch": 0.4, "distance": 70, "fov": 0.6})
    # 6d. inside fillets: a gusset root on the right cheek, and a rib / boss root on back_lower
    gy = parts_tower.gusset_positions(G)[1]
    shot("fillet-gusset-root", ["cheek_right"],
         {"target": [G.xc1 + 2, gy, zb + P.cheek_foot_t + 2], "yaw": -0.35, "pitch": 0.45, "distance": 55,
          "fov": 0.6})
    shot("fillet-rib-boss-root", ["back_lower"],
         {"target": [G.back_rib_x, G.y_back_in - 2, zb + 25], "yaw": -0.9, "pitch": 0.6, "distance": 70,
          "fov": 0.6})
    # 6e. exact SolidCraft B-rep rounding (brep_round.py): the cradle, side plate root fillet, rounded
    # plate edges, lead-ins on the disc channel and the scale ticks
    import meshio
    lo, hi = meshio.bbox(meshio.read_stl(os.path.join(ASM, "cradle.stl")))
    c = (lo + hi) / 2
    shot("brep-cradle", ["cradle"],
         {"target": [float(c[0]) - 40, float(c[1]), float(c[2])], "yaw": -0.7, "pitch": 0.5, "distance": 260,
          "fov": 0.6})
    # 7. arc slot end
    r, a0, a1 = G.bolt_arc(1)
    import math
    c = G.T[1:] + r * __import__("numpy").array([math.cos(math.radians(a1)), math.sin(math.radians(a1))])
    shot("round-slot-end", ["cheek_right"],
         {"target": [G.xc1, float(c[0]), float(c[1])], "yaw": -1.2, "pitch": 0.2, "distance": 60, "fov": 0.6})
    # 8. foot stub under the base with the sleeve outline (D sleeve_d, assumed)
    x, y = G.feet()[0]
    sleeve = {"command": "solid.cylinder", "params": {
        "diameter": P.sleeve_d, "height": P.foot_h + 1, "base": [x, y, P.foot_recess_depth - P.foot_h - 1],
        "operation": "new", "body_name": "sleeve_outline"}}
    shot("foot-stub-sleeve", ["foot_stub_0", "base_front"],
         {"target": [x, y, -10], "yaw": -0.9, "pitch": -0.25, "distance": 170, "fov": 0.6}, extra=[sleeve])
    # 9. lighting: roof and wall LED channels with their covers, seen from inside; sensor holder;
    #    electronics bay with its vented cover (see-through)
    shot("led-channels", ["roof_front", "roof_rear", "side_left_rear_upper", "led_cover_roof_left",
                          "led_cover_wall_left"],
         {"target": [-90, 60, G.z_rb - 40], "yaw": -2.0, "pitch": -0.35, "distance": 330, "fov": 0.6})
    tip = P.sensor_tip
    shot("light-sensor", ["side_left_front_upper"],
         {"target": [tip[0], tip[1], tip[2] - 5], "yaw": 0.9, "pitch": 0.35, "distance": 90, "fov": 0.6})
    shot("electronics-bay", ["base_rear", "bay_cover"],
         {"target": [0, P.bay_y, zb + 10], "yaw": -0.7, "pitch": 0.6, "distance": 260, "fov": 0.6},
         see=("bay_cover",))
    print("close-ups written to", OUT)


if __name__ == "__main__":
    main()
