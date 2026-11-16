"""Build every part: SolidCraft (B-rep, joints) -> STEP + design, then the rounded print mesh
(pre-rounded primitives unioned in Blender) -> stl/ (print pose) and build/asm/ (assembly pose).

Usage: python3 src/build.py [--scanner mini2] [--turntable revopoint_a230_ii] [--only NAME...] [name=value ...]
"""
import argparse
import concurrent.futures as cf
import copy
import json
import os
import subprocess

import numpy as np

import brep_round
import csg
import csg_fillet
import csg_plan
import joints
import meshio
import parts_base
import parts_feet
import parts_led
import parts_panels
import parts_tower
from geom import Geo
from params import load
from sc import BUILD, ROOT
from zones import zones_for

OUT_STL = os.path.join(ROOT, "stl")
OUT_STEP = os.path.join(ROOT, "step")
OUT_CAD = os.path.join(ROOT, "cad", "parts")
ASM = os.path.join(BUILD, "asm")
RAW = os.path.join(BUILD, "print_raw")
ROUNDED = os.path.join(BUILD, "rounded")
I34 = np.hstack([np.eye(3), np.zeros((3, 1))])


def inverse(M):
    R, O = M[:, :3], M[:, 3]
    return np.hstack([R.T, (-R.T @ O).reshape(3, 1)])


def compose(A, B):
    """A after B, both 3x4 rigid."""
    return np.hstack([A[:, :3] @ B[:, :3], (A[:, :3] @ B[:, 3] + A[:, 3]).reshape(3, 1)])


def cradle_print(G):
    """Cradle local (x, s, t) -> print: lying on its -X side plate, so both side-plate inserts
    are perpendicular to the layers."""
    return np.array([[0, 1.0, 0, 0], [0, 0, 1.0, 0], [1.0, 0, 0, G.x_go]])


def part_list(G, js):
    """(part, B2W, B2P): build frame -> world and build frame -> print frame."""
    P = G.P
    out = [(parts_base.build_base(G, js, w), I34, I34) for w in ("front", "rear")]
    for s in (-1, 1):
        for col in ("front", "rear"):
            for row in ("lower", "upper"):
                pn = parts_panels.build_side(G, js, s, col, row)
                out.append((pn, pn.M, I34))
    for row in ("lower", "upper"):
        pn = parts_panels.build_back(G, js, row)
        out.append((pn, pn.M, I34))
    for col in ("front", "rear"):
        pn = parts_panels.build_roof(G, js, col)
        out.append((pn, pn.M, I34))
    for s in (-1, 1):
        out.append((parts_tower.build_cheek(G, js, s), I34, inverse(parts_tower.cheek_frame(G, s))))
    out.append((parts_tower.build_cradle(G, js), G.cradle_matrix(P.elevation), cradle_print(G)))
    out.append((parts_feet.build_foot_stub(G), parts_feet.stub_matrix(G, 0), I34))
    for r in parts_led.runs(G):                       # lighting: diffuser covers, bay cover
        out.append((parts_led.build_cover(G, r), parts_led.cover_matrix(G, r), I34))
    out.append((parts_led.build_bay_cover(G), parts_led.bay_cover_matrix(G), I34))
    return out


def world_prims(G, js):
    """Join primitives of every part in assembly coordinates (fresh builders, so --only still
    sees every neighbour)."""
    out = {}
    for part, B2W, _ in part_list(G, js):
        part.move(B2W)
        part.export("world")
        out[part.name] = [p for p in csg.replay(part.cmds) if p.op == "join"]
    return out


def keep_out_prims(world, name, P2W):
    """Join primitives of every other part near this one, in this part's print frame (fillets
    must not grow into a mating part)."""
    lo = np.min([p.bbox()[0] for p in world[name]], axis=0) - 5.0
    hi = np.max([p.bbox()[1] for p in world[name]], axis=0) + 5.0
    W2P = inverse(P2W)
    out = []
    for other, prims in world.items():
        if other == name:
            continue
        for p in prims:
            plo, phi = p.bbox()
            if np.all(phi >= lo) and np.all(plo <= hi):
                q = copy.deepcopy(p)
                q.transform(W2P)
                out.append(q)
    return out


def zone_boxes(G, js, name, P2W):
    """Lead-in and corner zones of a part (world point sets) as boxes in its print frame."""
    W2P = inverse(P2W)

    def boxes(lst):
        res = []
        for pts in lst:
            q = pts @ W2P[:, :3].T + W2P[:, 3]
            res.append([*q.min(0).tolist(), *q.max(0).tolist()])
        return res
    zones = zones_for(name, G, js)
    return boxes(zones["lead_in"]), boxes(zones["corner"])


def inside_r(P, name):
    return P.fillet_in_big if name.startswith("cheek") else P.fillet_in_r


def round_best(P, G, js, part, raw, out, P2W, keep_out):
    """Exact B-rep rounding in SolidCraft (brep_round) where it rounds the part at least as well as
    the mesh pipeline: kept outright when it leaves no exposed sharp edge and every inside corner it
    planned is filleted; otherwise the mesh pipeline runs too and the part with fewer exposed sharp
    edges wins (B-rep on a tie when it filleted at least half its inside corners)."""
    name = part.name
    lead, corner = zone_boxes(G, js, name, P2W)
    if not P.brep_round:
        return dict(method="mesh", **round_mesh(P, G, js, part, raw, out, P2W, keep_out))
    b_stl, b_step, b_sc = out + ".brep.stl", out + ".brep.step", out + ".brep.solidcraft"
    b, mid_b = None, None
    try:
        b = brep_round.round_part(P, part, lead, corner, keep_out, inside_r(P, name), b_stl, b_step, b_sc, P2W,
                                  budget_s=P.brep_budget_s)
        tb = meshio.read_stl(b_stl)
        t = meshio.topology(tb)
        if t["watertight"] and t["manifold"] and t["oriented"]:
            mid_b = sharp_mids(P, tb, lead, keep_out)
    except Exception as e:                     # noqa: BLE001 - the mesh pipeline is the fallback
        b = dict(error=str(e)[:300])
    ins = (b or {}).get("inside", {})
    frac = ins.get("ok", 0) / ins["edges"] if ins.get("edges") else 1.0
    summary = {k: (dict(v, refused=len(v["refused"])) if isinstance(v, dict) and "refused" in v else v)
               for k, v in (b or {}).items()}
    use_b = mid_b is not None and len(mid_b) == 0 and frac == 1.0
    st = {}
    if not use_b:
        st = round_mesh(P, G, js, part, raw, out, P2W, keep_out)
        mid_m = sharp_mids(P, meshio.read_stl(out), lead, keep_out)
        st["exposed_sharp_mesh"] = len(mid_m)
        use_b = mid_b is not None and (len(mid_b) < len(mid_m) or (len(mid_b) == len(mid_m) and frac >= 0.5))
    if mid_b is not None:
        st["exposed_sharp_brep"] = len(mid_b)
    st["brep"] = summary
    if use_b:
        os.replace(b_stl, out)
        os.replace(b_step, os.path.join(OUT_STEP, name + ".step"))
        os.replace(b_sc, os.path.join(OUT_CAD, name + ".solidcraft"))
        json.dump(dict(out=out, method="brep", lead_in_zones=lead, corner_zones=corner), open(out + ".job.json", "w"))
        st["method"] = "brep"
    else:
        st["method"] = "mesh"
    for f in (b_stl, b_step, b_sc, b_sc + ".bak"):
        if os.path.exists(f):
            os.remove(f)
    return st


def round_mesh(P, G, js, part, raw, out, P2W, keep_out=()):
    """Rounded print mesh: every primitive of the part's history rounded on its own, with its
    inside fillets (csg_plan, csg_fillet), then unioned / cut in Blender (round_csg_blender).
    Zones (world point sets) are mapped to the print frame."""
    lead, corner = zone_boxes(G, js, part.name, P2W)
    prims = csg.replay(part.cmds)
    hull = csg_plan.footprint_hull(meshio.read_stl(raw))
    f_in = inside_r(P, part.name)
    sp, jp = out + ".steps.json", out + ".job.json"

    def run(no_fillet, with_fillets):
        steps, log, fil = csg_plan.build_job(prims, P, hull, lead, corner, keep_out, f_in, no_fillet,
                                             fillets=with_fillets)
        with open(sp, "w") as f:
            json.dump(steps, f)
        json.dump(dict(out=out, steps_file=sp, lead_in_zones=lead, corner_zones=corner, primitives=log,
                       no_fillet=sorted(no_fillet)), open(jp, "w"), default=float)
        r = subprocess.run(["blender", "-b", "--factory-startup", "--python",
                            os.path.join(ROOT, "src", "round_csg_blender.py"), "--", jp],
                           capture_output=True, text=True, timeout=900)
        if r.returncode != 0 or "CSG_DONE" not in r.stdout or not os.path.exists(out):
            raise RuntimeError(f"{part.name}: blender CSG failed\n{r.stdout[-2000:]}\n{r.stderr[-2000:]}")
        return log, fil, sharp_mids(P, meshio.read_stl(out), lead, keep_out)
    no_fillet = set()
    if P.fillet_solids:
        # a fillet that leaves a new sharp crease where it meets its neighbours is dropped; edges the
        # fillet-free part already has are not the fillets' fault
        _, _, base_mid = run(no_fillet, False)
        for _ in range(7):
            log, fil, mid = run(no_fillet, True)
            bad = fillet_defects(mid, base_mid, fil)
            if not bad:
                break
            no_fillet |= bad
        else:
            log, fil, mid = run(no_fillet, True)
    else:
        log, fil, mid = run(no_fillet, False)
    t = meshio.topology(meshio.read_stl(out))
    if P.fillet_solids and not (t["watertight"] and t["manifold"] and t["oriented"]):
        log, fil, mid = run(no_fillet, False)      # the part stays printable: no fillets rather than holes
        no_fillet = set(fil) | no_fillet | {"all"}
    os.remove(sp)
    dropped = no_fillet
    kinds = [p["kind"] for p in log]
    return dict(primitives=len(log), joins=sum(k != "cut" for k in kinds), cuts=kinds.count("cut"),
                lead_in=kinds.count("lead_in"), corner=kinds.count("corner"),
                fillet_feet=sum(1 for p in log if p.get("fillet", 0) > 0),
                fillet_strips=sum(p.get("strips", 0) for p in log), fillets_dropped=len(dropped))


def sharp_mids(P, tris, lead, keep_out):
    """Midpoints of the exposed sharp convex edges (not on the bed, not in a fit zone, not
    against another part)."""
    import edges
    p0, p1, ang = edges.sharp_convex_edges(tris, P.sharp_deg)
    mid = edges.classify(p0, p1, ang, P, lead)["other_mid"]
    if not len(mid):
        return mid
    cov = np.zeros(len(mid), bool)
    for d in np.vstack([np.eye(3), -np.eye(3)]) * 0.6:
        cov |= csg_fillet.inside(keep_out, mid + d)
    return mid[~cov]


def fillet_defects(mid, base_mid, fil):
    """Fillets to drop: for every sharp edge that the fillet-free build does not have, the
    nearest fillet (if within 1.5 mm)."""
    from scipy.spatial import cKDTree
    if not fil or not len(mid):
        return set()
    if base_mid is not None and len(base_mid):
        mid = mid[cKDTree(base_mid).query(mid)[0] > 0.3]
    keys = list(fil)
    trees = [cKDTree(fil[k_]) for k_ in keys]
    bad = set()
    for q in mid:
        d = [t_.query(q)[0] for t_ in trees]
        if min(d) < 1.5:
            bad.add(keys[int(np.argmin(d))])
    return bad


def finish(P, G, js, part, B2W, B2P, world):
    name = part.name
    raw, rnd = os.path.join(RAW, name + ".stl"), os.path.join(ROUNDED, name + ".stl")
    P2W = compose(B2W, inverse(B2P))
    stats = round_best(P, G, js, part, raw, rnd, P2W, keep_out_prims(world, name, P2W))
    tris = meshio.read_stl(rnd)
    rlo, rhi = meshio.bbox(meshio.read_stl(raw))
    olo, ohi = meshio.bbox(tris)
    stats["overshoot_mm"] = round(float(max((rlo - olo).max(), (ohi - rhi).max(), 0.0)), 3)
    asm_names = [name] if name != "foot_stub" else [f"foot_stub_{i}" for i in range(parts_feet.stub_count(G))]
    for i, an in enumerate(asm_names):
        M = P2W if name != "foot_stub" else parts_feet.stub_matrix(G, i)
        meshio.write_stl(os.path.join(ASM, an + ".stl"), meshio.transform(tris, M), an)
    lo, hi = meshio.bbox(tris)
    shift = np.array([-(lo[0] + hi[0]) / 2, -(lo[1] + hi[1]) / 2, -lo[2]])
    meshio.write_stl(os.path.join(OUT_STL, name + ".stl"), tris + shift, name)
    qty = len(asm_names)
    return dict(name=name, qty=qty, size=(hi - lo).round(2).tolist(),
                volume_cm3=round(meshio.volume(tris) / 1000, 1), rounding=stats, p2w=P2W.tolist())


def build(P, only=None):
    G = Geo(P)
    js = joints.build_joints(G)
    for d in (OUT_STL, OUT_STEP, OUT_CAD, ASM, RAW, ROUNDED):
        os.makedirs(d, exist_ok=True)
    todo = []
    for part, B2W, B2P in part_list(G, js):
        if only and part.name not in only:
            continue
        part.move(B2P)
        part.export(os.path.join(RAW, part.name + ".stl"))
        part.move(compose(B2W, inverse(B2P)))
        part.export(os.path.join(OUT_STEP, part.name + ".step"))
        todo.append((part, B2W, B2P))
    with cf.ThreadPoolExecutor(max_workers=6) as ex:
        list(ex.map(lambda t: t[0].run(save_sc=os.path.join(OUT_CAD, t[0].name + ".solidcraft")), todo))
        world = world_prims(G, js)
        table = list(ex.map(lambda t: finish(P, G, js, t[0], t[1], t[2], world), todo))
    for t in table:
        print(f"{t['name']:26s} x{t['qty']} {t['size']}  {t['volume_cm3']} cm3  rounding {t['rounding']}", flush=True)
    if not only:
        meta = dict(geometry=G.summary(), parts=table, seams=joints.SEAMS,
                    joints=[dict(name=j["name"], seam=j["seam"], kind=j["kind"], clear=j["clear"],
                                 insert=j["insert"], boss=j["boss"], thread=j["thread"], clamp=j["clamp"],
                                 p=j["p"].round(3).tolist(), a=j["a"].tolist(),
                                 screw=None if j["kind"] == "dowel" else joints.screw_length(P, j)) for j in js],
                    foot=dict(screw_len=G.foot_screw_len, cbore=G.foot_cbore, clamp=G.foot_clamp))
        with open(os.path.join(BUILD, "build.json"), "w") as f:
            json.dump(meta, f, indent=1)
    return G, js, table


def parse(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--scanner", default="mini2")
    ap.add_argument("--turntable", default="revopoint_a230_ii")
    ap.add_argument("--only", nargs="*")
    ap.add_argument("overrides", nargs="*", help="name=value")
    a = ap.parse_args(argv)
    ov = {}
    for kv in a.overrides:
        k, v = kv.split("=", 1)
        try:
            ov[k] = float(v)
        except ValueError:
            ov[k] = v
    for k in ("jack_side",):          # integer parameters
        if k in ov:
            ov[k] = int(ov[k])
    return load(a.scanner, a.turntable, **ov), a.only


if __name__ == "__main__":
    P, only = parse()
    build(P, only)
