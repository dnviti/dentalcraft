"""Exact B-rep rounding in SolidCraft (solid.fillet / solid.chamfer), one headless MCP session per part.

Order: inside corners first (fillet_in_r, fillet_in_big on the cheeks), then outer edges (edge_r,
corner_r in the corner zones), fit lead-ins (lead_in_r chamfer) and last the bed chamfer. Edges in a
fit zone keep their lead-in only; concave edges against a mating part get no fillet (keep-out). Each group is
tried as one feature; a refused group is split in halves down to single edges, and a single edge is
tried exact, then with fit: reduce (kept if the radius applied is at least min_r). A refused fillet
leaves the design unchanged, so the result is always the valid B-rep with what could be built.
"""
import json
import os
import subprocess
import sys
import threading
import time

import numpy as np

import csg
import csg_fillet
from sc import CLI

VERBOSE = bool(os.environ.get("BREP_VERBOSE"))


class Session:
    """Minimal stdio MCP client for `solidcraft-cli mcp --headless`."""

    def __init__(self):
        self.p = subprocess.Popen([CLI, "mcp", "--headless", "--allow-any-path", "--compact"], stdin=subprocess.PIPE,
                                  stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True, bufsize=1)
        self.n = 0
        self.rpc("initialize", {"protocolVersion": "2025-06-18", "capabilities": {},
                                "clientInfo": {"name": "scan-enclosure", "version": "1"}})
        self.p.stdin.write(json.dumps({"jsonrpc": "2.0", "method": "notifications/initialized"}) + "\n")

    def rpc(self, method, params, timeout=300):
        """One request; a call still running after `timeout` s kills the session (the caller falls
        back to the mesh rounding: an MCP call cannot be cancelled)."""
        self.n += 1
        self.p.stdin.write(json.dumps({"jsonrpc": "2.0", "id": self.n, "method": method, "params": params}) + "\n")
        dog = threading.Timer(timeout, self.p.kill)
        dog.start()
        try:
            while True:
                line = self.p.stdout.readline()
                if not line:
                    raise RuntimeError(f"solidcraft mcp closed (or {method} ran over {timeout} s)")
                m = json.loads(line)
                if m.get("id") == self.n:
                    return m
        finally:
            dog.cancel()

    def tool(self, name, args):
        m = self.rpc("tools/call", {"name": name, "arguments": args})
        if "error" in m:
            return False, m["error"]
        r = m["result"]
        txt = "".join(c.get("text", "") for c in r.get("content", []))
        try:
            val = json.loads(txt)
        except ValueError:
            val = txt
        return not r.get("isError", False), val

    def exe(self, command, params):
        return self.tool("execute", {"command": command, "params": params})

    def close(self):
        self.p.stdin.close()
        try:
            self.p.wait(timeout=30)
        except subprocess.TimeoutExpired:
            self.p.kill()


def solid_inside(prims, W):
    """Points inside the part's raw (unrounded) solid: joins and cuts in history order."""
    out = np.zeros(len(W), bool)
    for p in prims:
        lo, hi = p.bbox()
        sel = np.all((W >= lo - 0.1) & (W <= hi + 0.1), axis=1)
        if sel.any():
            c = np.zeros(len(W), bool)
            c[sel] = p.contains(W[sel])
            out = (out & ~c) if p.op == "cut" else (out | c)
    return out


def classify_edges(prims, E, F, eps=0.12, n=24):
    """Each B-rep edge: kind (convex, concave, smooth), the corner bisector and its tangent, by
    sampling a small circle round its midpoint against the primitives."""
    cyl = {f["name"]: f.get("cylinder") for f in F}
    th = np.linspace(0, 2 * np.pi, n, endpoint=False)
    out = []
    for e in E:
        s, m, t = (np.array(e[k], float) for k in ("start", "mid", "end"))
        tan = t - s
        if np.linalg.norm(tan) < 1e-6:          # closed circle: tangent from its cylinder
            c = next((cyl[f] for f in e["name"].split("|") if cyl.get(f)), None)
            if c is None:
                continue
            ax = np.array(c["axis"], float)
            r = m - np.array(c["origin"], float)
            tan = np.cross(ax, r - (r @ ax) * ax)
        tan /= np.linalg.norm(tan)
        a = np.cross(tan, [1.0, 0, 0] if abs(tan[0]) < 0.9 else [0, 1.0, 0])
        a /= np.linalg.norm(a)
        b = np.cross(tan, a)
        dirs = np.outer(np.cos(th), a) + np.outer(np.sin(th), b)
        ins = solid_inside(prims, m + eps * dirs)
        frac = ins.mean()
        kind = "convex" if frac < 0.45 else "concave" if frac > 0.55 else "smooth"
        air = dirs[~ins].mean(0) if (~ins).any() else np.zeros(3)
        nb = np.linalg.norm(air)
        out.append(dict(index=e["index"], mid=m, start=s, end=t, tan=tan, kind=kind,
                        air=air / nb if nb > 1e-9 else air))
    return out


def in_boxes(p, boxes, pad=0.0):
    return any(np.all(p >= np.array(b[:3]) - pad) and np.all(p <= np.array(b[3:]) + pad) for b in boxes)


def plan(P, edges, lead, corner, keep_out, f_in):
    """(group name, op, size, edges) in the order they are built; plus the skipped edges."""
    groups = {k: [] for k in ("inside", "corner", "edge", "lead_in", "bed")}
    skipped = []
    for e in edges:
        m, air = e["mid"], e["air"]
        zhi = max(e["start"][2], e["end"][2])
        if e["kind"] == "concave":
            # a fillet must not grow into a mating part (corner another part sits in)
            mate = bool(keep_out) and csg_fillet.inside(keep_out, (m + air * 0.8)[None])[0]
            if mate or in_boxes(m, lead, 0.5) or zhi <= P.bed_chamfer + 0.3:
                skipped.append((e, "fit/bed/mating"))
            else:
                groups["inside"].append(e)
        elif e["kind"] == "convex":
            # outer edges are rounded also where a mating part sits against them (seam faces), as in
            # the mesh pipeline: no crisp edge is left when the parts are apart
            if zhi <= 0.02:
                groups["bed"].append(e)
            elif in_boxes(m, lead):
                groups["lead_in"].append(e)
            elif in_boxes(m, corner):
                groups["corner"].append(e)
            else:
                groups["edge"].append(e)
    return [("inside", "solid.fillet", f_in, groups["inside"]),
            ("corner", "solid.fillet", P.corner_r, groups["corner"]),
            ("edge", "solid.fillet", P.edge_r, groups["edge"]),
            ("lead_in", "solid.chamfer", P.lead_in_r, groups["lead_in"]),
            ("bed", "solid.chamfer", P.bed_chamfer, groups["bed"])], skipped


REASONS = ("Fillet Corner Error", "Rollover", "contact line leaves", "larger than the faces", "CalcFillet",
           "proto edge", "where 2 edges meet", "too small", "Tolerance", "UVSpace", "BSplineCurve", "not built",
           "Boolean")


def reason(msg):
    """Short class of a SolidCraft refusal message."""
    return next((k for k in REASONS if k in msg), msg.strip()[-60:])


def apply(S, body, op, size, edges, min_r, log, deadline):
    """Build the edges as one feature; a refused group is split in halves."""
    if not edges or time.time() > deadline:
        for e in edges:
            log.append(dict(mid=e["mid"].round(3).tolist(), ok=False, how="time"))
        return
    key = "radius" if op == "solid.fillet" else "distance"
    prm = {"edges": [e["mid"].tolist() for e in edges], key: size, "body": body}
    t = time.time()
    ok, r = S.exe(op, prm)
    if VERBOSE:
        print(f"  brep {body} {op} {size} x{len(edges)}: {'ok' if ok else 'refused'} {time.time() - t:.1f}s",
              file=sys.stderr, flush=True)
    if ok:
        for e in edges:
            log.append(dict(mid=e["mid"].round(3).tolist(), ok=True, how="exact", size=size))
        return
    msg = str(r)
    if "smooth" in msg and "nothing to round" in msg and len(edges) == 1:
        log.append(dict(mid=edges[0]["mid"].round(3).tolist(), ok=True, how="already", size=size))
        return
    if len(edges) > 1:
        h = len(edges) // 2
        apply(S, body, op, size, edges[:h], min_r, log, deadline)
        apply(S, body, op, size, edges[h:], min_r, log, deadline)
        return
    # a single refused edge: picked off its midpoint when that is a vertex, without its tangent chain
    # (the chain often reaches the corner that fails), then with the radius reduced where it does not fit
    e = edges[0]
    tries = [({"tangent_chain": False}, "no_chain")]
    if "where 2 edges meet" in msg:
        off = (e["start"] + 0.4 * (e["end"] - e["start"])).tolist()
        tries = [({"edges": [off]}, "exact"), ({"edges": [off], "tangent_chain": False}, "no_chain")]
    if op == "solid.fillet":
        tries += [(dict(tries[0][0], fit="reduce"), "reduce"), (dict(tries[-1][0], fit="reduce"), "reduce")]
    for extra, how in tries:
        if time.time() > deadline:
            break
        ok, r2 = S.exe(op, dict(prm, **extra))
        if not ok:
            continue
        ra = r2.get("radius_applied") if isinstance(r2, dict) else None
        if ra is None or ra >= min_r:
            log.append(dict(mid=edges[0]["mid"].round(3).tolist(), ok=True, how=how,
                            size=size if ra is None else ra))
            return
        S.tool("undo", {})
    log.append(dict(mid=edges[0]["mid"].round(3).tolist(), ok=False, how="refused", err=msg[:600]))


def round_part(P, part, lead, corner, keep_out, f_in, out_stl, out_step, out_sc, P2W, budget_s=900):
    """Round the part's B-rep in its print frame; export the print STL, the STEP (assembly frame)
    and the design. Returns stats with the per-group outcome."""
    cmds = []
    for c in part.cmds:
        if c["command"] == "file.export":
            break
        cmds.append(c)
    prims = csg.replay(part.cmds, nth=1)
    t0 = time.time()
    S = Session()
    try:
        ok, r = S.tool("batch", {"commands": cmds, "verbose": False})
        if not ok:
            raise RuntimeError(f"{part.name}: B-rep build failed: {str(r)[:500]}")
        E = S.exe("model.edges", {"body": part.name})[1]["edges"]
        F = S.exe("model.faces", {"body": part.name})[1]["faces"]
        edges = classify_edges(prims, E, F)
        groups, skipped = plan(P, edges, lead, corner, keep_out, f_in)
        stats, deadline = {}, t0 + budget_s
        for name, op, size, lst in groups:
            log = []
            apply(S, part.name, op, size, lst, 0.5 if op == "solid.fillet" else 0.0, log, deadline)
            stats[name] = dict(edges=len(lst), ok=sum(x["ok"] for x in log),
                               reduced=sum(x["how"] == "reduce" for x in log),
                               refused=[x["mid"] for x in log if x["how"] == "refused"],
                               errors=sorted({reason(x["err"]) for x in log if x["how"] == "refused"}),
                               not_tried=sum(x["how"] == "time" for x in log))
        stats["skipped"] = len(skipped)
        S.exe("file.export", {"path": out_stl, "bodies": [part.name], "quality": "fine"})
        S.exe("solid.move", {"bodies": [part.name], "matrix": [[float(c) for c in row] for row in P2W]})
        S.exe("file.export", {"path": out_step, "bodies": [part.name]})
        S.tool("save", {"path": out_sc})
    finally:
        S.close()
    stats["seconds"] = round(time.time() - t0, 1)
    return stats
