"""Per-frame source audit, contact samples and explicitly bounded evidence."""
import bpy, json, math, importlib.util, hashlib
from pathlib import Path
from mathutils import Vector

ROOT = Path(__file__).resolve().parents[2]; OUT = Path(bpy.data.filepath).parent
rig = bpy.data.objects['Rig_Swordsman']; obj = bpy.data.objects['SK_Swordsman_Animation']
sword = bpy.data.objects['SM_Longsword']; scene = bpy.context.scene
module_spec = importlib.util.spec_from_file_location('coat_audit', ROOT / 'tools/blender/audit_swordsman_collisions.py')
audit = importlib.util.module_from_spec(module_spec); module_spec.loader.exec_module(audit)
reports = {}; endpoints = {}; errors = []; reference_grip = None
run_feet = []


def points():
    evaluated = obj.evaluated_get(bpy.context.evaluated_depsgraph_get()); mesh = evaluated.to_mesh()
    pts = [evaluated.matrix_world @ v.co for v in mesh.vertices]; evaluated.to_mesh_clear()
    pts.extend(sword.matrix_world @ v.co for v in sword.data.vertices)
    return pts


for action in bpy.data.actions:
    rig.animation_data.action = action
    first, last = map(round, action.frame_range)
    contacts = []; floor = 100; root_drift = 0; grip_drift = 0; all_pts = []
    for frame in range(first, last + 1):
        scene.frame_set(frame); bpy.context.view_layer.update()
        result = audit.evaluate()
        if result['penetrating_samples']:
            contacts.append(dict(frame=frame, **result))
        root = rig.pose.bones['Root']
        if action.name == 'run':
            run_feet.append(dict(frame=frame, t=(frame-first)/(last-first),
                                 feet={s:list(rig.matrix_world @ rig.pose.bones['Foot.'+s].head) for s in ('L','R')}))
        root_drift = max(root_drift, root.location.length, root.rotation_quaternion.angle)
        relative = rig.pose.bones['WeaponSocket.R'].matrix.inverted() @ sword.matrix_world
        if reference_grip is None: reference_grip = relative.copy()
        grip_drift = max(grip_drift, max(abs(relative[r][c] - reference_grip[r][c]) for r in range(4) for c in range(4)))
        pts = points(); floor = min(floor, min(p.z for p in pts))
        if frame in (first, first + 1, last - 1, last):
            all_pts.append((frame, pts))
    endpoints[action.name] = dict(all_pts)
    reports[action.name] = dict(frames=[first, last], coat_leg_penetrations=contacts,
                                minimum_geometry_z_m=floor, root_channel_max_drift=root_drift,
                                socket_relative_matrix_max_error=grip_drift)
    if root_drift > 1e-5: errors.append(action.name + ': root drift')
    if grip_drift > 1e-4: errors.append(action.name + ': weapon attachment changed')
    if floor < -.02: errors.append(action.name + ': geometry below floor >2cm')
    if contacts: errors.append(action.name + ': confirmed lower-coat/leg sample penetrations')
    print('SOURCE_AUDIT', action.name, 'coat frames', len(contacts), 'floor', floor, flush=True)

links = [('idle', 'attack_1'), ('attack_1', 'attack_2'), ('attack_2', 'attack_3'), ('attack_3', 'idle'),
         ('idle', 'dodge'), ('dodge', 'idle'), ('idle', 'piercing_lunge'), ('piercing_lunge', 'idle'),
         ('idle', 'hurt'), ('hurt', 'idle'), ('idle', 'death')]
transitions = []
for source, target in links:
    left = endpoints[source]; right = endpoints[target]
    end, start = max(left), min(right)
    gap = max((p - q).length for p, q in zip(left[end], right[start]))
    velocity_gap = max((((p - a) - (b - q)) * 30).length for p, a, q, b in
                       zip(left[end], left[end - 1], right[start], right[start + 1]))
    # idle -> death starts at idle, combo clips have explicit matched boundary poses.
    if gap > .001: errors.append(f'{source}->{target}: endpoint pose gap')
    transitions.append(dict(source=source, target=target, position_gap_m=gap,
                            finite_difference_velocity_gap_m_s=velocity_gap))
report = dict(source_sha256=hashlib.sha256(Path(bpy.data.filepath).read_bytes()).hexdigest(),
              clips=reports, transitions=transitions, errors=errors,
              collision_method='All frames; lower-coat vertices and face centroids vs labeled legs BVH + horizontal parity; >1mm; waist above z=.76 excluded',
              contact_test_limits='Sampling, not exhaustive triangle-triangle proof; excludes torso/hand self intersections; no runtime cloth simulation')
events=json.loads((OUT/'combat_events.json').read_text(encoding='utf-8'))
gait=events.get('run_gait',dict(stance_fraction=.44,plant_core=[0,.44]))
speed=events['run_reference_speed_m_s']
stance_errors = []
for previous, current in zip(run_feet, run_feet[1:]):
    for side, offset in [('L',0),('R',.5)]:
        a, b = (previous['t']+offset)%1, (current['t']+offset)%1
        if gait['plant_core'][0] < a < b < gait['plant_core'][1]:
            actual = Vector(current['feet'][side])-Vector(previous['feet'][side])
            expected = Vector((0,speed/30,0))
            stance_errors.append((actual-expected).length)
report['run_stance'] = dict(reference_speed_m_s=speed, tested_intervals=len(stance_errors),
                            max_ankle_displacement_error_per_frame_m=max(stance_errors,default=0),
                            limits='Ankle trajectory only, assumes matching controller speed; not a sole/friction simulation')
if max(stance_errors,default=0) > .003: errors.append('run: stance ankle displacement error >3mm per frame')
(OUT / 'source_validation.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
print('COMBAT_SOURCE_AUDIT_COMPLETE', json.dumps(dict(errors=errors)), flush=True)
if errors: raise RuntimeError('; '.join(errors))
