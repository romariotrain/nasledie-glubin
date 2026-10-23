"""Author the requested nine-clip combat set on the existing v005 rig."""
import bpy, math, json, hashlib, shutil, tempfile, importlib.util
from pathlib import Path
from mathutils import Vector, Quaternion, Matrix

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / 'art/characters/swordsman/hunyuan_combat_v006'
OUT.mkdir(parents=True, exist_ok=True)
tempfile.tempdir = str(ROOT / 'work/hunyuan2mini/export-temp')
scene = bpy.context.scene
rig = bpy.data.objects['Rig_Swordsman']
obj = bpy.data.objects['SK_Swordsman_Animation']
sword = bpy.data.objects['SM_Longsword']
source = Path(bpy.data.filepath)
scene.render.fps = 30
rig.animation_data_clear()
for ac in list(bpy.data.actions):
    bpy.data.actions.remove(ac)
for p in rig.pose.bones:
    p.rotation_mode = 'QUATERNION'
ankles = {s: rig.data.bones['Foot.' + s].head_local.copy() for s in ('L', 'R')}
rest_q = {b.name: b.matrix_local.to_quaternion() for b in rig.data.bones}
ik_errors = []
ik_clamps = {}


def reset():
    for p in rig.pose.bones:
        p.location = (0, 0, 0)
        p.rotation_quaternion = (1, 0, 0, 0)
        p.scale = (1, 1, 1)
    bpy.context.view_layer.update()


def local_world_rotation(name, x=0, y=0, z=0):
    q = Quaternion((0, 0, 1), math.radians(z)) @ Quaternion((1, 0, 0), math.radians(x)) @ Quaternion((0, 1, 0), math.radians(y))
    rig.pose.bones[name].rotation_quaternion = rest_q[name].inverted() @ q @ rest_q[name]


def shift_hips(x=0, y=0, z=0):
    rig.pose.bones['Hips'].location = rest_q['Hips'].inverted() @ Vector((x, y, z))


def orient(name, head, target=None, q=None):
    pb = rig.pose.bones[name]
    if q is None:
        direction = (target - head).normalized()
        rest = (pb.bone.tail_local - pb.bone.head_local).normalized()
        q = rest.rotation_difference(direction) @ rest_q[name]
    pb.matrix = Matrix.Translation(head) @ q.to_matrix().to_4x4()
    bpy.context.view_layer.update()


def limb(upper_name, lower_name, target, pole):
    upper, lower = rig.pose.bones[upper_name], rig.pose.bones[lower_name]
    head = upper.head.copy()
    delta = Vector(target) - head
    length = delta.length
    distance = min(max(length, .015), upper.bone.length + lower.bone.length - .0005)
    axis = delta.normalized()
    bend = Vector(pole) - axis * Vector(pole).dot(axis)
    if bend.length < .01:
        bend = Vector((1, 0, 0)) - axis * axis.x
    bend.normalize()
    along = (upper.bone.length ** 2 - lower.bone.length ** 2 + distance ** 2) / (2 * distance)
    knee = head + axis * along + bend * math.sqrt(max(0, upper.bone.length ** 2 - along ** 2))
    endpoint = head + axis * distance
    orient(upper_name, head, knee)
    orient(lower_name, knee, endpoint)
    ik_errors.append(max(0, length - distance))
    ik_clamps[upper_name] = max(ik_clamps.get(upper_name, 0), max(0, length - distance))
    return endpoint


def feet(left=None, right=None, rolls=(0, 0)):
    bpy.context.view_layer.update()
    for s, target, roll in [('L', left, rolls[0]), ('R', right, rolls[1])]:
        target = Vector(target) if target is not None else ankles[s].copy()
        end = limb('Thigh.' + s, 'Shin.' + s, target, (0, -1, .1))
        q = Quaternion((1, 0, 0), math.radians(roll)) @ rest_q['Foot.' + s]
        orient('Foot.' + s, end, q=q)


def arm(side, grip, direction):
    # Sword's local +Z is aligned with hand local +Y; grip offset is from v005.
    direction = Vector(direction).normalized()
    q = direction.to_track_quat('Y', 'Z')
    wrist = Vector(grip) - q @ Vector((0, .068, .025))
    end = limb('UpperArm.' + side, 'Forearm.' + side, wrist,
               (-1 if side == 'R' else 1, .45, -.1))
    orient('Hand.' + side, end, q=q)


def free_arm(amount=0):
    local_world_rotation('UpperArm.L', x=-5 - amount * .4, y=8 - amount * .35)
    local_world_rotation('Forearm.L', x=-16 - amount * .6)


def coat(front=0, back=0, twist=0):
    for side, sign in [('L', 1), ('R', -1)]:
        local_world_rotation('Coat_Front.' + side, x=front, y=sign * 4, z=twist)
        local_world_rotation('Coat_Back.' + side, x=back, y=sign * 4, z=twist * .7)
        local_world_rotation('Coat_Front.' + side + '_Tip', x=front * .25)
        local_world_rotation('Coat_Back.' + side + '_Tip', x=back * .25)


def ease(t):
    t = max(0, min(1, t))
    return t * t * t * (t * (t * 6 - 15) + 10)


# Author grip paths and blade directions explicitly instead of repeating FK swings.
# Character right is -X; forward is -Y, up is +Z in this Blender file.
IDLE = dict(grip=(-.40, -.19, .91), blade=(-.24, -.40, -.88), yaw=0, lean=0, crouch=.025,
            hip_y=0, left_y=0, right_y=0)
A1_WIND = dict(grip=(-.39, -.20, 1.43), blade=(-.72, .18, .67), yaw=-22, lean=-3, crouch=.055,
               hip_y=.012, left_y=0, right_y=.03)
LINK12 = dict(grip=(.20, -.33, 1.02), blade=(.88, -.27, -.39), yaw=24, lean=8, crouch=.06,
              hip_y=-.04, left_y=-.11, right_y=.02)
A1_HIT = dict(grip=(.08, -.40, 1.16), blade=(.52, -.75, -.41), yaw=18, lean=7, crouch=.06,
              hip_y=-.035, left_y=-.09, right_y=.02)
A2_MID = dict(grip=(-.13, -.48, 1.17), blade=(-.90, -.42, .06), yaw=-12, lean=6, crouch=.07,
              hip_y=-.055, left_y=-.13, right_y=-.035)
LINK23 = dict(grip=(-.30, -.22, 1.42), blade=(-.30, .05, .95), yaw=-24, lean=-5, crouch=.065,
              hip_y=-.035, left_y=-.12, right_y=.015)
A3_WIND = dict(grip=(-.15, -.10, 1.60), blade=(-.12, .35, .93), yaw=-28, lean=-9, crouch=.095,
               hip_y=.015, left_y=-.08, right_y=.06)
A3_HIT = dict(grip=(.10, -.45, 1.02), blade=(.25, -.83, -.50), yaw=22, lean=17, crouch=.12,
              hip_y=-.075, left_y=-.19, right_y=.025)
LUNGE_WIND = dict(grip=(-.36, -.10, 1.20), blade=(.06, -.98, .15), yaw=-18, lean=-3, crouch=.10,
                  hip_y=.035, left_y=-.07, right_y=.06)
LUNGE_HIT = dict(grip=(-.24, -.45, 1.19), blade=(.01, -1, .015), yaw=3, lean=16, crouch=.14,
                 hip_y=-.05, left_y=-.28, right_y=.12)
DODGE_LOW = dict(grip=(-.40, -.22, .91), blade=(-.30, -.42, -.85), yaw=-12, lean=20, crouch=.18,
                 hip_y=-.025, left_y=-.16, right_y=.15)
HURT = dict(grip=(-.40, -.12, 1.02), blade=(-.50, -.1, -.85), yaw=-12, lean=-14, crouch=.07,
            hip_y=.025, left_y=.025, right_y=.05)


def interpolate(first, second, t):
    return {k: tuple(x + (y - x) * t for x, y in zip(first[k], second[k]))
            if isinstance(first[k], tuple) else first[k] + (second[k] - first[k]) * t for k in first}


def path(keys, t):
    for (ta, pa), (tb, pb) in zip(keys, keys[1:]):
        if ta <= t <= tb:
            return interpolate(pa, pb, ease((t - ta) / (tb - ta)))
    return keys[-1][1]


def pose(params, flutter=0):
    shift_hips(y=params['hip_y'], z=-params['crouch'])
    local_world_rotation('Hips', z=params['yaw'] * .20)
    local_world_rotation('Spine', x=params['lean'] * .55, z=params['yaw'] * .30)
    local_world_rotation('Chest', x=params['lean'] * .45, z=params['yaw'] * .50)
    local_world_rotation('Head', x=-params['lean'] * .35, z=-params['yaw'] * .45)
    bpy.context.view_layer.update()
    arm('R', params['grip'], params['blade'])
    free_arm(abs(params['yaw']))
    left, right = ankles['L'].copy(), ankles['R'].copy()
    left.y += params['left_y']; right.y += params['right_y']
    feet(left, right)
    coat(front=-8 - params['crouch'] * 45 - flutter, back=6 + flutter, twist=-params['yaw'] * .08)


def idle(t):
    p = dict(IDLE)
    p['crouch'] += .004 * math.sin(2 * math.pi * t)
    p['grip'] = (IDLE['grip'][0], IDLE['grip'][1], IDLE['grip'][2] + .004 * math.sin(2 * math.pi * t))
    pose(p, math.sin(2 * math.pi * t))


def run(t):
    phase = 2 * math.pi * t
    p = dict(IDLE)
    p.update(crouch=.095 + .018 * math.cos(2 * phase), lean=13, yaw=7 * math.sin(phase))
    p['grip'] = (-.39, -.21 + .08 * math.cos(phase), 1.02 + .04 * math.sin(phase))
    p['blade'] = (-.38, -.25, .89)
    pose(p)
    for s, offset in [('L', 0), ('R', .5)]:
        cycle = (t + offset) % 1
        target = ankles[s].copy()
        if cycle < .44:
            u = cycle / .44
            target.y += -.30 + .60 * u
            lift = 0
        else:
            u = (cycle - .44) / .56
            target.y += .30 - .60 * ease(u)
            lift = .19 * math.sin(math.pi * u) ** 1.2
        target.z += lift
        end = limb('Thigh.' + s, 'Shin.' + s, target, (0, -1, .1))
        roll = 13 * math.sin(math.pi * max(0, (cycle - .44) / .56)) if cycle >= .44 else 0
        orient('Foot.' + s, end, q=Quaternion((1, 0, 0), math.radians(roll)) @ rest_q['Foot.' + s])
        local_world_rotation('Coat_Front.' + s, x=-18 - 12 * math.cos(phase + offset * 2 * math.pi), y=(5 if s == 'L' else -5))
        local_world_rotation('Coat_Back.' + s, x=15 + 8 * math.cos(phase + offset * 2 * math.pi))
    local_world_rotation('UpperArm.L', x=32 * math.cos(phase) - 12, y=-10)
    local_world_rotation('Forearm.L', x=-62)


def attack1(t):
    pose(path([(0, IDLE), (.25, A1_WIND), (.55, A1_HIT), (1, LINK12)], t), 5 * math.sin(math.pi * t))


def attack2(t):
    pose(path([(0, LINK12), (.52, A2_MID), (1, LINK23)], t), 6 * math.sin(math.pi * t))


def attack3(t):
    pose(path([(0, LINK23), (.30, A3_WIND), (.50, A3_HIT), (.60, A3_HIT), (1, IDLE)], t), 9 * math.sin(math.pi * t))


def dodge(t):
    pose(path([(0, IDLE), (.20, DODGE_LOW), (.62, DODGE_LOW), (1, IDLE)], t), 12 * math.sin(math.pi * t))


def lunge(t):
    pose(path([(0, IDLE), (.25, LUNGE_WIND), (.44, LUNGE_HIT), (.61, LUNGE_HIT), (1, IDLE)], t), 9 * math.sin(math.pi * t))


def hurt(t):
    pose(path([(0, IDLE), (.28, HURT), (1, IDLE)], t))


def death(t):
    if t < .20:
        pose(interpolate(IDLE, HURT, ease(t / .20)))
        return
    u = ease((t - .20) / .64)
    # Hips carry the fall; Root stays fixed, so gameplay position remains code-owned.
    shift_hips(y=.025 + .12 * u, z=-.07 - .61 * u)
    local_world_rotation('Hips', x=-94 * u, z=-7 * u)
    local_world_rotation('Spine', x=-7 * (1 - u))
    local_world_rotation('Chest', x=8 * u)
    local_world_rotation('Head', x=12 * u)
    local_world_rotation('UpperArm.R', x=-8 * u, y=42 * u)
    local_world_rotation('Forearm.R', x=-8 * u)
    local_world_rotation('UpperArm.L', x=-10 * u, y=-46 * u)
    local_world_rotation('Forearm.L', x=-12 * u)
    for s in ('L', 'R'):
        local_world_rotation('Thigh.' + s, x=-15 * math.sin(math.pi * u))
        local_world_rotation('Shin.' + s, x=24 * math.sin(math.pi * u))
    coat(front=-6 * (1 - u), back=6 * (1 - u))
    bpy.context.view_layer.update()
    evaluated = obj.evaluated_get(bpy.context.evaluated_depsgraph_get())
    mesh = evaluated.to_mesh()
    floor = min((evaluated.matrix_world @ v.co).z for v in mesh.vertices)
    evaluated.to_mesh_clear()
    if floor < .005:
        p = rig.pose.bones['Hips']
        p.location += rest_q['Hips'].inverted() @ Vector((0, 0, .005 - floor))


definitions = [
    ('idle', 61, idle, True, 'Neutral sword stance'),
    ('run', 19, run, True, 'Energetic run, airborne swing, in place'),
    ('attack_1', 13, attack1, False, 'Quick right-to-left descending diagonal; small forward step'),
    ('attack_2', 13, attack2, False, 'Reverse left-to-right horizontal cut; ends in overhead preparation'),
    ('attack_3', 21, attack3, False, 'Heavy overhead diagonal, weight transfer and 0.067s contact-pose hold'),
    ('dodge', 11, dodge, False, 'Low short forward dash pose; no roll and no root travel'),
    ('piercing_lunge', 17, lunge, False, 'Retract sword, thrust point forward, brief extension hold'),
    ('hurt', 8, hurt, False, 'Brief recoil, return to neutral'),
    ('death', 37, death, False, 'Fall backwards and hold final grounded pose'),
]
clips = []
for name, frames, fn, loop, description in definitions:
    action = bpy.data.actions.new(name); action.use_fake_user = True
    rig.animation_data_create(); rig.animation_data.action = action
    for frame in range(1, frames + 1):
        scene.frame_set(frame); reset(); fn((frame - 1) / (frames - 1))
        bpy.context.view_layer.update()
        for pb in rig.pose.bones:
            # Quaternion hemisphere continuity prevents component interpolation flips.
            q = pb.rotation_quaternion.copy()
            if frame > 1 and previous[pb.name].dot(q) < 0:
                q.negate(); pb.rotation_quaternion = q
            pb.keyframe_insert(data_path='rotation_quaternion', frame=frame, group=pb.name)
            pb.keyframe_insert(data_path='location', frame=frame, group=pb.name)
        previous = {pb.name: pb.rotation_quaternion.copy() for pb in rig.pose.bones}
    for layer in action.layers:
        for strip in layer.strips:
            for bag in strip.channelbags:
                for curve in bag.fcurves:
                    for key in curve.keyframe_points:
                        key.interpolation = 'LINEAR'
    clips.append(dict(name=name, duration_s=(frames - 1) / 30, loop=loop,
                      motion='in_place', description=description))
    print('AUTHORED', name, frames, flush=True)

events = {
    'schema_version': 1, 'fps': 30, 'time_unit': 'seconds_from_clip_start',
    'status': 'Suggested initial timings; gameplay controller not implemented or playtested',
    'root_motion': False, 'forward_blender': [0, -1, 0],
    'run_reference_speed_m_s': .60 / (.44 * .60),
    'clips': {
        'attack_1': dict(startup=[0, .10], active=[.10, .20], recovery=[.20, .40], hit=.1667,
                         combo_next='attack_2', combo_handoff=.40, input_buffer=[.16, .40], dodge_cancel_suggested=[.24, .40]),
        'attack_2': dict(startup=[0, .08], active=[.08, .23], recovery=[.23, .40], hit=.1667,
                         combo_next='attack_3', combo_handoff=.40, input_buffer=[.16, .40], dodge_cancel_suggested=[.27, .40]),
        'attack_3': dict(startup=[0, .20], active=[.20, .34], recovery=[.34, 20 / 30], hit=10 / 30,
                         contact_pose_hold=[10 / 30, 12 / 30], heavy=True, dodge_cancel_suggested=[.46, 20 / 30]),
        'dodge': dict(movement_window=[.0333, .2667], invulnerability_suggested=[.0667, .2333], distance_owned_by_controller=True),
        'piercing_lunge': dict(startup=[0, .1333], active=[.1333, .2667], recovery=[.2667, 16 / 30],
                               hit=.2333, movement_window=[.1333, .2667], distance_owned_by_controller=True),
        'hurt': dict(duration=7 / 30), 'death': dict(duration=1.2, hold_last_pose=True),
    },
    'gameplay_only': ['damage', 'hitboxes', 'hitstop', 'camera shake', 'knockback', 'invulnerability', 'dash/lunge displacement'],
    'deferred': ['circular_slash'], 'not_requested': ['walk', 'block', 'parry', 'heavy_attack', 'jump', 'crouch'],
}
spec = json.loads((ROOT / 'tools/character_pipeline/swordsman.example.json').read_text(encoding='utf-8'))
spec['asset_id'] = 'swordsman-combat-v006'; spec['animations'] = clips
spec['target'] = 'MVP mobile melee combat; portable GLB/FBX, code-driven motion; engine validation pending'
for name, data in [('spec.json', spec), ('combat_events.json', events)]:
    (OUT / name).write_text(json.dumps(data, indent=2), encoding='utf-8')
for filename in ('swordsman_basecolor_2048.png', 'swordsman_normal_2048.png', 'swordsman_roughness_2048.png'):
    shutil.copyfile(source.parent / filename, OUT / filename)
for im in bpy.data.images:
    if im.type == 'IMAGE' and im.users:
        im.pack()
rig.animation_data.action = bpy.data.actions['idle']
scene.frame_set(1); scene.frame_start = 1; scene.frame_end = 61
scene.render.engine = 'BLENDER_EEVEE'
for screen in bpy.data.screens:
    for area in screen.areas:
        if area.type == 'VIEW_3D':
            area.spaces.active.shading.type = 'SOLID'
            area.spaces.active.shading.color_type = 'TEXTURE'
bpy.ops.wm.save_as_mainfile(filepath=str(OUT / 'swordsman_combat_v006.blend'))
receipt = dict(source=str(source.relative_to(ROOT)), source_sha256=hashlib.sha256(source.read_bytes()).hexdigest(),
               method='Authored grip/weapon paths and analytic limb IK baked to FK at 30fps',
               root_fixed=True, clips=clips, max_limb_reach_clamp_m=max(ik_errors, default=0),
               limb_reach_clamp_m=ik_clamps,
               limitations=['No articulated fingers', 'No runtime cloth physics', 'Timings require gameplay testing'])
(OUT / 'build_receipt.json').write_text(json.dumps(receipt, indent=2), encoding='utf-8')
print('COMBAT_BUILD_READY', flush=True)
