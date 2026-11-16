"""Foot stub: a copy of the Centauri Carbon 2 stock foot, so the Elegoo anti-vibration
sleeves slip on it. Built standing on its large (base) end, which is its print orientation;
an M3 screw from the table end, head hidden in a counterbore, goes into an insert in the base.
The stub is a solid of revolution, so turning it in its recess changes nothing: no keys."""
from sc import Part, frame_matrix


def build_foot_stub(G):
    P = G.P
    part = Part("foot_stub")
    part.cmds.append({"command": "solid.cone", "params": {
        "diameter": P.foot_d_top, "top_diameter": P.foot_d_bottom, "height": P.foot_h,
        "base": [0, 0, 0], "axis": "Z", "operation": "new", "body_name": "foot_stub"}})
    part.started = True
    part.cyl([0, 0, P.foot_h - G.foot_cbore], [0, 0, 1], P.cbore_d, G.foot_cbore + 1.0, op="cut")
    part.cyl([0, 0, -1.0], [0, 0, 1], P.m3_clear, P.foot_h + 2.0, op="cut")
    return part


def stub_matrix(G, i):
    """Print/local frame of stub i -> world: large end up against the recess floor."""
    x, y = G.feet()[i]
    return frame_matrix([x, y, G.P.foot_recess_depth], [1, 0, 0], [0, -1, 0], [0, 0, -1])


def stub_count(G):
    return len(G.feet())

