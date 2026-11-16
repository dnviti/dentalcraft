"""Blender headless: build one part from its pre-rounded primitives (print frame, bed = Z 0).

Run: blender -b --factory-startup --python src/round_csg_blender.py -- job.json
job: {out, steps_file}; steps_file: [{op: join|cut, V, F}] in the order of the part's history.
Joins are unioned, cut tools (already flared at their mouths) subtracted, with the Manifold
solver. The primitives carry every round, chamfer, fillet and lead-in (src/csg_plan.py), so no
bevel runs on the merged mesh."""
import json
import sys

import bmesh
import bpy


def make(name, st):
    me = bpy.data.meshes.new(name)
    me.from_pydata(st["V"], [], st["F"])
    me.validate()
    ob = bpy.data.objects.new(name, me)
    bpy.context.scene.collection.objects.link(ob)
    return ob


def boolean(target, tools, op):
    m = target.modifiers.new("b", "BOOLEAN")
    if op == "join":
        coll = bpy.data.collections.new("tools")
        bpy.context.scene.collection.children.link(coll)
        for t in tools:
            bpy.context.scene.collection.objects.unlink(t)
            coll.objects.link(t)
        m.operation, m.operand_type, m.collection = "UNION", "COLLECTION", coll
    else:
        m.operation, m.object = "DIFFERENCE", tools[0]
    m.solver = "MANIFOLD"
    bpy.context.view_layer.objects.active = target
    bpy.ops.object.modifier_apply(modifier=m.name)
    for t in tools:
        bpy.data.objects.remove(t, do_unlink=True)


def main():
    job = json.load(open(sys.argv[sys.argv.index("--") + 1]))
    bpy.ops.wm.read_factory_settings(use_empty=True)
    steps = json.load(open(job["steps_file"]))
    ob = make("part", steps[0])
    i = 1
    while i < len(steps):
        op = steps[i]["op"]
        j = i + 1
        while op == "join" and j < len(steps) and steps[j]["op"] == "join":
            j += 1
        boolean(ob, [make(f"t{k}", steps[k]) for k in range(i, j)], op)
        i = j
    # drop the slivers the booleans leave, triangulate, and keep the first variant that is a closed
    # manifold without zero-area triangles (the raw boolean result is the last resort)
    for ops in (("doubles", "degenerate", "collapse"), ("doubles", "degenerate"), ("doubles",), ()):
        bm = bmesh.new()
        bm.from_mesh(ob.data)
        if "doubles" in ops:
            bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=1e-4)
        if "degenerate" in ops:
            bmesh.ops.dissolve_degenerate(bm, edges=bm.edges, dist=1e-3)
        if "collapse" in ops:
            bmesh.ops.collapse(bm, edges=[e for e in bm.edges if e.calc_length() < 2e-3], uvs=False)
            bmesh.ops.dissolve_degenerate(bm, edges=bm.edges, dist=1e-3)
        bmesh.ops.triangulate(bm, faces=bm.faces, quad_method="BEAUTY", ngon_method="BEAUTY")
        ok = all(len(e.link_faces) == 2 for e in bm.edges) and all(f.calc_area() > 1e-9 for f in bm.faces)
        if ok or not ops:
            bm.to_mesh(ob.data)
            bm.free()
            print("CLEANUP", ops, ok)
            break
        bm.free()
    for o in list(bpy.context.scene.objects):
        o.select_set(o is ob)
    bpy.ops.wm.stl_export(filepath=job["out"], export_selected_objects=True, ascii_format=False)
    print("CSG_DONE", len(steps), len(ob.data.polygons))


main()
