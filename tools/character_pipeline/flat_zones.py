"""Classify hero faces into flat colour zones and bake a flat basecolour on the existing UVs.

Input is the dump from tools/blender/export_face_zones_data.py. Faces are labelled by body part (dominant
deform bone) plus the hue/value of the old painted texture, then cleaned on the mesh graph so zone borders
follow edges instead of texture noise. Output: flat texture, zone labels and a receipt in a new folder.
"""
import argparse, collections, colorsys, hashlib, json
from pathlib import Path
import numpy as np
from PIL import Image, ImageDraw, ImageFilter

ROOT = Path(__file__).resolve().parents[2]
p = argparse.ArgumentParser()
p.add_argument('--faces', type=Path, required=True)
p.add_argument('--out', type=Path, default=ROOT / 'art/characters/swordsman/flat_zones_v001')
p.add_argument('--size', type=int, default=2048)
p.add_argument('--source', type=Path, default=ROOT / 'art/characters/swordsman/hunyuan_combat_v010/swordsman_basecolor_2048.png')
args = p.parse_args()

# Palette after the concept sheet (#2 simplified + #4 outlined): near-black coat, one strong red, warm leather.
PALETTE = {
    # Charcoal rather than pure black, so the lit/shadow bands still read on the coat.
    'coat': (46, 42, 50), 'red': (158, 20, 24), 'cloth': (64, 62, 76), 'leather': (86, 50, 30),
    'boot': (92, 56, 34), 'glove': (56, 38, 28), 'skin': (222, 156, 118), 'hair': (72, 44, 28),
}


def part(bone):
    for prefix, name in [('Head', 'head'), ('Neck', 'head'), ('Hand', 'hand'), ('Foot', 'boot'), ('Toe', 'boot'),
                         ('Shin', 'shin'), ('Thigh', 'thigh'), ('Coat', 'coat'), ('UpperArm', 'arm'), ('Forearm', 'arm')]:
        if bone.startswith(prefix): return name
    return 'torso'


def colour_class(rgb):
    h, s, v = colorsys.rgb_to_hsv(*rgb); h *= 360
    if s > .35 and v > .12 and (h >= 340 or h < 14): return 'red'
    if s > .28 and 14 <= h < 48: return 'warm'
    return 'neutral'


def classify(f):
    kind = colour_class(f['rgb']); v = max(f['rgb']); where = part(f['bone'])
    if where == 'head':
        if kind == 'red': return 'red'
        if kind == 'warm' and v > .45: return 'skin'
        return 'hair'
    if where == 'hand': return 'skin' if kind == 'warm' and v > .42 else 'glove'
    if where in ('boot', 'shin'):
        return 'cloth' if kind == 'neutral' and where == 'shin' else 'boot'
    if where == 'thigh': return {'red': 'red', 'warm': 'leather'}.get(kind, 'cloth')
    if where == 'coat':
        # Shadowed coat cloth reads dark maroon in the painted map; only clearly saturated red is trim/lining.
        h, s, _ = colorsys.rgb_to_hsv(*f['rgb'])
        if kind == 'red' and (s < .45 or v < .18): return 'coat'
        return {'red': 'red', 'warm': 'leather'}.get(kind, 'coat')
    if where == 'arm':
        if kind == 'warm': return 'skin' if v > .45 else 'glove'
        return 'red' if kind == 'red' else 'coat'
    # Torso: shirt shows in the open front of the coat; belts and straps are warm.
    if kind == 'red': return 'red'
    if kind == 'warm': return 'leather'
    return 'cloth' if abs(f['x']) < .085 and f['y'] < 0 and .95 < f['z'] < 1.38 else 'coat'


data = json.loads(args.faces.read_text())
faces = data['faces']; zones = [classify(f) for f in faces]
raw = collections.Counter(zones)

# Face adjacency through shared edges.
edge_faces = collections.defaultdict(list)
for i, f in enumerate(faces):
    vs = f['verts']
    for a, b in zip(vs, vs[1:] + vs[:1]): edge_faces[(min(a, b), max(a, b))].append(i)
neighbours = [set() for _ in faces]
for linked in edge_faces.values():
    for i in linked: neighbours[i].update(j for j in linked if j != i)

# Mode filter: a face follows its neighbourhood unless its own label is shared by enough neighbours.
for _ in range(2):
    changed = 0; new = list(zones)
    for i, ns in enumerate(neighbours):
        if not ns: continue
        votes = collections.Counter(zones[j] for j in ns); votes[zones[i]] += 1.5
        best = votes.most_common(1)[0][0]
        if best != zones[i]: new[i] = best; changed += 1
    zones = new
    if not changed: break

# Merge islands smaller than a few faces into the surrounding zone.
MIN_ISLAND = 6
for _ in range(4):
    seen = [False] * len(faces); merged = 0
    for start in range(len(faces)):
        if seen[start]: continue
        label = zones[start]; stack = [start]; island = []; seen[start] = True
        while stack:
            i = stack.pop(); island.append(i)
            for j in neighbours[i]:
                if not seen[j] and zones[j] == label: seen[j] = True; stack.append(j)
        if len(island) < MIN_ISLAND:
            border = collections.Counter(zones[j] for i in island for j in neighbours[i] if zones[j] != label)
            if border:
                target = border.most_common(1)[0][0]
                for i in island: zones[i] = target
                merged += 1
    if not merged: break

size = args.size
names = list(PALETTE); index = {n: i for i, n in enumerate(names)}
# Label maps in UV space: zone per pixel and owning face (+1, 0 = empty).
label = Image.new('L', (size, size), index['coat']); owner = Image.new('I', (size, size), 0)
dl, do = ImageDraw.Draw(label), ImageDraw.Draw(owner)
polys = [[(u * size, (1 - v) * size) for u, v in f['uv']] for f in faces]
for pts, z in zip(polys, zones): dl.polygon(pts, fill=index[z], outline=index[z], width=4)  # seam padding
for i, (pts, z) in enumerate(zip(polys, zones)):
    dl.polygon(pts, fill=index[z]); do.polygon(pts, fill=i + 1)

# Border refinement: where a face touches another zone, each pixel picks the closer of those zones by the
# painted colour, so thin trims follow the painted line instead of the triangle edges.
source = np.asarray(Image.open(args.source).convert('RGB').resize((size, size)), dtype=np.float32) / 255
lab = np.asarray(label).copy(); own = np.asarray(owner).astype(np.int64)
mean = {}
for n in names:
    picks = [faces[i]['rgb'] for i, z in enumerate(zones) if z == n]
    mean[n] = np.mean(picks, axis=0) if picks else np.zeros(3)
allowed = np.zeros((len(faces) + 1, len(names)), dtype=bool)
for i, ns in enumerate(neighbours):
    for o in {zones[i]} | {zones[j] for j in ns}: allowed[i + 1, index[o]] = True
border = allowed.sum(axis=1) > 1
mask = border[own]
ys, xs = np.nonzero(mask)
centres = np.array([mean[n] for n in names])
dist = ((source[ys, xs][:, None, :] - centres[None]) ** 2).sum(axis=2)
dist[~allowed[own[ys, xs]]] = np.inf
lab[ys, xs] = dist.argmin(axis=1)
smooth = np.asarray(Image.fromarray(lab).filter(ImageFilter.ModeFilter(7)))
lab = np.where(mask, smooth, lab)

# Face features (eyes, brows, mouth) survive as two tones inside the skin of the head.
head_skin = np.zeros(len(faces) + 1, dtype=bool)
for i, (f, z) in enumerate(zip(faces, zones)): head_skin[i + 1] = z == 'skin' and part(f['bone']) == 'head'
features = head_skin[own] & (source.max(axis=2) < .46)
lab = np.where(features, index['hair'], lab)

rgb = np.array([PALETTE[n] for n in names], dtype=np.uint8)[lab]
image = Image.fromarray(rgb, 'RGB')
args.out.mkdir(parents=True, exist_ok=True)
texture = args.out / 'swordsman_basecolor_flat_v001.png'; image.save(texture)
(args.out / 'face_zones.json').write_text(json.dumps(dict(palette=PALETTE, zones=zones)), encoding='utf-8')
final = collections.Counter(zones)
receipt = dict(source_faces=str(args.faces.name), source_texture=data['image'], faces=len(faces),
               method='Per-face body part (dominant deform bone) + hue/value of the old painted map, '
                      'mode filter on edge adjacency, islands < %d faces merged; border faces refined per pixel '
                      'between their own and neighbouring zones by painted colour, 7px mode filter; '
                      'dark painted features kept inside head skin' % MIN_ISLAND,
               source_map=str(args.source.relative_to(ROOT)), source_map_sha256=hashlib.sha256(args.source.read_bytes()).hexdigest(),
               palette=PALETTE, raw_counts=raw, final_counts=final,
               texture_sha256=hashlib.sha256(texture.read_bytes()).hexdigest(),
               limits='Same mesh and UVs; zone borders follow existing triangles; no new geometry')
(args.out / 'receipt.json').write_text(json.dumps(receipt, indent=2), encoding='utf-8')
print('FLAT_ZONES', json.dumps(dict(raw=raw, final=final)))
