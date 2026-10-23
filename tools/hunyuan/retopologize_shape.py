"""Non-destructive cleanup and feature-weighted quadric triangle reduction."""
import argparse
import hashlib
import json
from pathlib import Path
import time
import numpy as np
import pymeshlab
from scipy.spatial import cKDTree
import trimesh
from PIL import Image, ImageDraw

parser = argparse.ArgumentParser()
parser.add_argument('--source', type=Path, required=True)
parser.add_argument('--output', type=Path, required=True)
args = parser.parse_args()
args.output.mkdir(parents=True, exist_ok=False)
source = trimesh.load(args.source, force='mesh')
parts = sorted(source.split(only_watertight=False), key=lambda m: len(m.faces), reverse=True)
clean = parts[0].copy()
assert all(len(part.faces) < len(clean.faces)*0.001 for part in parts[1:]), 'Review detached components before deletion'
clean.remove_unreferenced_vertices()
assert clean.is_watertight and np.isfinite(clean.vertices).all()
clean.export(args.output / 'swordsman_clean_high.glb')

# MeshLab's quality-weighted QEM makes errors on head/hands more expensive.
v = clean.vertices
weight = np.ones(len(v))
weight[v[:, 1] > 0.62] = 2.0
weight[(np.abs(v[:, 0]) > 0.30) & (v[:, 1] > -0.30) & (v[:, 1] < 0.28)] = 2.0
weight[v[:, 1] < -0.73] = 1.5
# Broad costume landmarks on the front deserve budget as well as extremities.
front = (v[:,2]>0.04) & (np.abs(v[:,0])<0.30)
weight[front & (v[:,1]>-0.12) & (v[:,1]<0.65)] = 3.0
weight[front & (v[:,1]>0.0) & (v[:,1]<0.17)] = 5.0
weight[front & (v[:,1]>0.43) & (v[:,1]<0.65)] = 4.0

center = clean.bounds.mean(axis=0)
extent = np.ptp(clean.vertices, axis=0).max()
def silhouette(mesh, degrees):
    angle = np.deg2rad(degrees)
    rotation = np.array([[np.cos(angle),0,np.sin(angle)],[0,1,0],[-np.sin(angle),0,np.cos(angle)]])
    points = ((mesh.vertices-center) @ rotation.T)[:, :2] * [220/extent, -220/extent] + [128,128]
    image = Image.new('1', (256,256))
    draw = ImageDraw.Draw(image)
    for face in mesh.faces:
        draw.polygon([tuple(x) for x in points[face]], fill=1)
    return np.array(image, dtype=bool)

angles = [0,45,90,135,180,225,270,315]
reference_masks = [silhouette(clean,a) for a in angles]
reference_points, _ = trimesh.sample.sample_surface(clean, 60000, seed=12345)
reference_tree = cKDTree(reference_points)
results = []
for target in (10000, 12000):
    started = time.time()
    ms = pymeshlab.MeshSet()
    ms.add_mesh(pymeshlab.Mesh(vertex_matrix=clean.vertices, face_matrix=clean.faces, v_scalar_array=weight))
    ms.apply_filter('meshing_decimation_quadric_edge_collapse',
                    targetfacenum=target, qualitythr=0.3, preserveboundary=True,
                    boundaryweight=5.0, preservenormal=True, preservetopology=True,
                    optimalplacement=True, planarquadric=True, planarweight=0.001,
                    qualityweight=True, autoclean=True)
    reduced = ms.current_mesh()
    mesh = trimesh.Trimesh(vertices=reduced.vertex_matrix(), faces=reduced.face_matrix(), process=True)
    assert 6000 <= len(mesh.faces) <= 12000, 'Triangle budget not reached'
    assert mesh.is_watertight and mesh.is_winding_consistent
    assert len(mesh.split(only_watertight=False)) == 1
    assert np.isfinite(mesh.vertices).all() and mesh.area_faces.min() > 1e-14
    path = args.output / f'swordsman_{target//1000}k.glb'
    mesh.export(path)
    reread = trimesh.load(path, force='mesh')
    assert len(reread.faces) == len(mesh.faces) and reread.is_watertight
    ious=[]
    for a,ref in zip(angles,reference_masks):
        actual=silhouette(reread,a)
        ious.append(float(np.logical_and(ref,actual).sum()/np.logical_or(ref,actual).sum()))
    sample, _ = trimesh.sample.sample_surface(reread, 60000, seed=12345)
    errors = np.concatenate([reference_tree.query(sample)[0],cKDTree(sample).query(reference_points)[0]]) / extent
    report=dict(file=path.name, triangles=len(mesh.faces), vertices=len(mesh.vertices),
                watertight=bool(mesh.is_watertight), consistent_winding=bool(mesh.is_winding_consistent),
                connected_components=1, bounds=mesh.bounds.tolist(),
                silhouette_iou_256px=dict(zip(map(str,angles),ious)),
                mean_silhouette_iou=float(np.mean(ious)), min_silhouette_iou=min(ious),
                approximate_symmetric_surface_sample_distance_fraction_height=dict(
                    mean=float(errors.mean()),p95=float(np.percentile(errors,95)),maximum=float(errors.max())),
                distance_note='Nearest points between two seeded 60k surface samples; includes sampling error, not exact Hausdorff distance.',
                seconds=time.time()-started, sha256=hashlib.sha256(path.read_bytes()).hexdigest())
    results.append(report)
    print(json.dumps(report,indent=2),flush=True)

receipt=dict(source=str(args.source.resolve()), source_sha256=hashlib.sha256(args.source.read_bytes()).hexdigest(),
             source_triangles=len(source.faces), original_components=len(parts),
             removed_components=len(parts)-1, removed_triangles=sum(len(p.faces) for p in parts[1:]),
             clean_triangles=len(clean.faces), method='MeshLab feature-weighted quadric edge collapse',
             feature_weights='base=1; head/hands=2; boots=1.5; front torso=3; belt=5; scarf/collar=4',
             limitations='Automatic triangle reduction; no animation edge-loop retopology, UVs, rig, texture, or engine import.',
             outputs=results)
(args.output/'cleanup_report.json').write_text(json.dumps(receipt,indent=2),encoding='utf-8')
