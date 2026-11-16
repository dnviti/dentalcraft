"""SolidCraft command-script emitter and headless runner (solidcraft-cli run)."""
import json
import math
import os
import subprocess

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
BUILD = os.path.join(ROOT, "build")
# SolidCraft CLI to run: the installed one by default; SOLIDCRAFT_CLI=/abs/path/solidcraft-cli selects
# another build (e.g. a nightly extracted from its tarball) without installing it
CLI = os.environ.get("SOLIDCRAFT_CLI", "solidcraft-cli")


def r(v):
    return round(float(v), 4)


def vec(v):
    return [r(c) for c in v]


class Part:
    """One printed part = one SolidCraft body built from boxes, cylinders and sketches."""

    def __init__(self, name):
        self.name = name
        self.cmds = []
        self.started = False
        self.n_sk = 0

    def _op(self, op):
        if not self.started:
            if op == "cut":
                raise ValueError(f"{self.name}: first feature cannot be a cut")
            self.started = True
            return {"operation": "new", "body_name": self.name}
        return {"operation": op, "targets": [self.name]}

    def box(self, lo, hi, op="join"):
        lo, hi = np.minimum(lo, hi), np.maximum(lo, hi)
        size = hi - lo
        if min(size) <= 1e-6:
            return
        self.cmds.append({"command": "solid.box", "params": {
            "length": r(size[0]), "width": r(size[1]), "height": r(size[2]),
            "corner": vec(lo), **self._op(op)}})

    def cyl(self, base, axis, d, h, op="join"):
        axis = np.asarray(axis, float)
        axis = axis / np.linalg.norm(axis)
        self.cmds.append({"command": "solid.cylinder", "params": {
            "diameter": r(d), "height": r(h), "base": vec(base), "axis": vec(axis),
            **self._op(op)}})

    def _sketch(self, origin, xdir, ydir):
        self.n_sk += 1
        name = f"{self.name}_S{self.n_sk}"
        self.cmds.append({"command": "sketch.create", "params": {
            "plane": {"origin": vec(origin), "x_dir": vec(xdir), "y_dir": vec(ydir)}, "name": name}})
        return name

    def _extrude(self, name, depth, op, symmetric):
        prm = {"sketch": name, "distance": r(depth), **self._op(op)}
        if symmetric:
            prm["direction"] = "symmetric"
        self.cmds.append({"command": "solid.extrude", "params": prm})

    def prism(self, origin, xdir, ydir, poly, depth, op="join", symmetric=False):
        """Closed polygon in the plane (origin, xdir, ydir), extruded along xdir x ydir."""
        name = self._sketch(origin, xdir, ydir)
        self.cmds.append({"command": "sketch.line", "params": {
            "points": [vec(q) for q in poly], "closed": True}})
        self.cmds.append({"command": "sketch.finish", "params": {}})
        self._extrude(name, depth, op, symmetric)

    def arc_slot(self, origin, xdir, ydir, c, rad_, a0, a1, w, depth, op="cut", symmetric=True):
        """Slot of width w along a circular arc (centre c, radius rad_, degrees a0..a1)."""
        name = self._sketch(origin, xdir, ydir)
        c = np.asarray(c, float)
        ro, ri, h = rad_ + w / 2, rad_ - w / 2, w / 2

        def pol(rr, a):
            return c + rr * np.array([math.cos(math.radians(a)), math.sin(math.radians(a))])
        am = (a0 + a1) / 2
        e1 = pol(rad_, a1)
        e0 = pol(rad_, a0)
        t1 = np.array([-math.sin(math.radians(a1)), math.cos(math.radians(a1))])
        t0 = np.array([math.sin(math.radians(a0)), -math.cos(math.radians(a0))])
        arcs = [
            (pol(ro, a0), pol(ro, a1), pol(ro, am)),       # outer
            (pol(ro, a1), pol(ri, a1), e1 + h * t1),       # end cap at a1
            (pol(ri, a1), pol(ri, a0), pol(ri, am)),       # inner
            (pol(ri, a0), pol(ro, a0), e0 + h * t0),       # end cap at a0
        ]
        for s, e, t in arcs:
            self.cmds.append({"command": "sketch.arc.three_point", "params": {
                "start": vec(s), "end": vec(e), "through": vec(t)}})
        self.cmds.append({"command": "sketch.finish", "params": {}})
        self._extrude(name, depth, op, symmetric)

    def move(self, M):
        M = np.asarray(M, float)
        self.cmds.append({"command": "solid.move", "params": {
            "bodies": [self.name], "matrix": [[float(c) for c in row] for row in M[:3, :4]]}})

    def export(self, path):
        self.cmds.append({"command": "file.export", "params": {"path": path, "bodies": [self.name]}})

    def run(self, save_sc=None, timeout=900):
        os.makedirs(BUILD, exist_ok=True)
        script = os.path.join(BUILD, f"{self.name}.json")
        with open(script, "w") as f:
            json.dump({"commands": self.cmds}, f)
        cmd = [CLI, "run", script, "--quiet"]
        if save_sc:
            cmd += ["--save", save_sc]
        res = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        if res.returncode != 0:
            raise RuntimeError(f"{self.name}: solidcraft-cli failed\n{res.stdout[-3000:]}\n{res.stderr[-3000:]}")
        return res


def frame_matrix(O, eu, ev, ez):
    """Local (u, v, z) -> world, as a 3x4 rigid matrix."""
    R = np.column_stack([eu, ev, ez]).astype(float)
    if abs(np.linalg.det(R) - 1) > 1e-6:
        raise ValueError("frame is not right-handed orthonormal")
    return np.hstack([R, np.asarray(O, float).reshape(3, 1)])


def to_local(M, p):
    R, O = M[:, :3], M[:, 3]
    return R.T @ (np.asarray(p, float) - O)


def dir_local(M, a):
    return M[:, :3].T @ np.asarray(a, float)
