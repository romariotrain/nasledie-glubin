"""Read-only: dump per-face UVs, dominant bone, height and sampled basecolour for flat-zone classification.

Run: blender -b <character .blend> --python tools/blender/export_face_zones_data.py -- <out.json>
"""
import bpy, sys, json, colorsys
import numpy as np

out = sys.argv[sys.argv.index('--') + 1]
obj = bpy.data.objects['SK_Swordsman_Animation']
me = obj.data
image = next(n.image for m in me.materials for n in m.node_tree.nodes if n.type == 'TEX_IMAGE' and n.image and 'basecolor' in n.image.name.lower())
w, h = image.size
pixels = np.empty(w * h * 4, dtype=np.float32); image.pixels.foreach_get(pixels); pixels = pixels.reshape(h, w, 4)
uv = me.uv_layers.active.data
rig = obj.find_armature()
# Only deform bones decide the body part; helper groups such as Retopo_Joint_Rings are skipped.
groups = {g.index: g.name for g in obj.vertex_groups if rig and g.name in rig.data.bones and rig.data.bones[g.name].use_deform}


def sample(u, v):
    x = min(w - 1, max(0, int(u % 1 * w))); y = min(h - 1, max(0, int(v % 1 * h)))
    return pixels[y, x, :3]


faces = []
for poly in me.polygons:
    loops = list(poly.loop_indices)
    uvs = [tuple(uv[i].uv) for i in loops]
    # Average colour over the face: centroid plus points towards each corner, ignoring the seam edge.
    cu = sum(p[0] for p in uvs) / len(uvs); cv = sum(p[1] for p in uvs) / len(uvs)
    cols = [sample(cu, cv)] + [sample(cu + (p[0] - cu) * .6, cv + (p[1] - cv) * .6) for p in uvs]
    rgb = np.mean(cols, axis=0)
    weights = {}
    for vi in poly.vertices:
        for g in me.vertices[vi].groups:
            name = groups.get(g.group)
            if name: weights[name] = weights.get(name, 0) + g.weight
    bone = max(weights, key=weights.get) if weights else ''
    centre = poly.center
    faces.append(dict(uv=[[round(a, 6), round(b, 6)] for a, b in uvs], bone=bone,
                      z=round(centre.z, 4), x=round(centre.x, 4), y=round(centre.y, 4),
                      rgb=[round(float(c), 4) for c in rgb], verts=list(poly.vertices)))
json.dump(dict(image=image.name, size=[w, h], faces=faces), open(out, 'w'))
print('FACE_ZONE_DATA', len(faces), image.name, w, h)
