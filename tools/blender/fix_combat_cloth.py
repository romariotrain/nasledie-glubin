"""Shape a conservative rest-space coat envelope for the authored nine clips."""
import bpy, json, importlib.util
from pathlib import Path
from mathutils import Matrix, Vector

ROOT = Path(__file__).resolve().parents[2]; OUT = Path(bpy.data.filepath).parent
spec = importlib.util.spec_from_file_location('audit', ROOT / 'tools/blender/audit_swordsman_collisions.py')
audit = importlib.util.module_from_spec(spec); spec.loader.exec_module(audit)
obj, rig = audit.obj, audit.rig
original = {i: obj.data.vertices[i].co.copy() for i in audit.coat}
weights = {v.index: [(obj.vertex_groups[g.group].name, g.weight) for g in v.groups
                     if obj.vertex_groups[g.group].name in rig.pose.bones] for v in obj.data.vertices}
inverse = {b.name: b.matrix_local.inverted() for b in rig.data.bones}
iterations = []
for iteration in range(12):
    proposals = {}; count = 0
    for action in bpy.data.actions:
        rig.animation_data.action = action
        for frame in range(round(action.frame_range[0]), round(action.frame_range[1]) + 1):
            bpy.context.scene.frame_set(frame)
            result = audit.evaluate(return_points=True)
            count += len(result['_records'])
            if not result['_records']: continue
            transforms = {p.name: (p.matrix @ inverse[p.name]).to_3x3() for p in rig.pose.bones}
            for record in result['_records']:
                delta = record['nearest'] + record['normal'] * .004 - record['point']
                for i in record['indices']:
                    transform = Matrix.Identity(3) * 0
                    for bone, weight in weights[i]: transform += transforms[bone] * weight
                    local = transform.inverted_safe() @ delta
                    if i not in proposals or local.length > proposals[i].length:
                        proposals[i] = local
    iterations.append(dict(iteration=iteration, contacts=count, proposed_vertices=len(proposals)))
    print('COMBAT_CLOTH', iterations[-1], flush=True)
    if not proposals: break
    # Couple nearby shell surfaces, then smooth the displacement field one ring.
    bases = list(proposals.items())
    for i in audit.coat:
        for j, delta in bases:
            if (obj.data.vertices[i].co - obj.data.vertices[j].co).length < .024:
                if i not in proposals or delta.length > proposals[i].length: proposals[i] = delta
    field = {}
    for i in audit.coat:
        own = proposals.get(i, Vector())
        adjacent = [proposals.get(j, Vector()) for j in audit.adjacency[i] if j in audit.coat]
        mean = sum(adjacent, Vector()) / max(1, len(adjacent))
        field[i] = own * .70 + mean * .30
    for i, delta in field.items():
        if delta.length > .014: delta = delta.normalized() * .014
        point = obj.data.vertices[i].co + delta * .9
        change = point - original[i]
        if change.length > .065: point = original[i] + change.normalized() * .065
        obj.data.vertices[i].co = point
    obj.data.update()
report = dict(method='Rest-space inverse-skinning contact correction, shell coupling and one-ring displacement smoothing',
              iterations=iterations, max_rest_displacement_m=max((obj.data.vertices[i].co-p).length for i,p in original.items()),
              changed_vertices=sum((obj.data.vertices[i].co-p).length>.00001 for i,p in original.items()),
              limits='Lower-coat/leg sample test only; not a runtime simulation or exhaustive intersection test')
(OUT / 'cloth_correction.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
rig.animation_data.action = bpy.data.actions['idle']; bpy.context.scene.frame_set(1)
bpy.ops.wm.save_as_mainfile(filepath=bpy.data.filepath)
print('CLOTH_CORRECTION_SAVED', flush=True)
