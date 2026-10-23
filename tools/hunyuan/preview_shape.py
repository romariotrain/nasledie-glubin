"""Render two orthographic mesh inspection views on CPU without modifying GLB."""
import argparse
from pathlib import Path
import numpy as np
from PIL import Image, ImageDraw
import trimesh

parser = argparse.ArgumentParser()
parser.add_argument('model', type=Path)
parser.add_argument('--output', type=Path)
parser.add_argument('--wireframe', action='store_true')
parser.add_argument('--label', default='Hunyuan3D-2mini | untextured')
args = parser.parse_args()
mesh = trimesh.load(args.model, force='mesh')
vertices = mesh.vertices - mesh.bounds.mean(axis=0)
extent = max(np.ptp(vertices, axis=0))
vertices /= extent
canvas = Image.new('RGB', (1200, 720), '#18212b')
draw = ImageDraw.Draw(canvas)
light = np.array([-0.4, 0.8, 0.7])
light /= np.linalg.norm(light)
for index, angle in enumerate((0, 35)):
    theta = np.deg2rad(angle)
    rotation = np.array([[np.cos(theta), 0, np.sin(theta)], [0, 1, 0], [-np.sin(theta), 0, np.cos(theta)]])
    rotated = vertices @ rotation.T
    triangles = rotated[mesh.faces]
    normals = np.cross(triangles[:, 1]-triangles[:, 0], triangles[:, 2]-triangles[:, 0])
    normals /= np.maximum(np.linalg.norm(normals, axis=1, keepdims=True), 1e-12)
    brightness = 0.25 + 0.75 * np.clip(normals @ light, 0, 1)
    projected = triangles[:, :, :2] * np.array([570, -570]) + np.array([300 + index*600, 360])
    smooth_normals = mesh.vertex_normals @ rotation.T
    framebuffer = np.asarray(canvas).copy()
    depthbuffer = np.full((720,1200), -np.inf)
    for face in np.argsort(triangles[:, :, 2].mean(axis=1)):
        if not args.wireframe:
            # Z-buffer and interpolated vertex normals reproduce GLB smooth shading.
            points = projected[face]
            xmin=max(0,int(np.floor(points[:,0].min())))
            xmax=min(1199,int(np.ceil(points[:,0].max())))
            ymin=max(0,int(np.floor(points[:,1].min())))
            ymax=min(719,int(np.ceil(points[:,1].max())))
            if xmin>xmax or ymin>ymax:
                continue
            x,y=np.meshgrid(np.arange(xmin,xmax+1)+0.5,np.arange(ymin,ymax+1)+0.5)
            a,b,c=points
            denominator=(b[1]-c[1])*(a[0]-c[0])+(c[0]-b[0])*(a[1]-c[1])
            if abs(denominator)<1e-10:
                continue
            u=((b[1]-c[1])*(x-c[0])+(c[0]-b[0])*(y-c[1]))/denominator
            v=((c[1]-a[1])*(x-c[0])+(a[0]-c[0])*(y-c[1]))/denominator
            w=1-u-v
            z=triangles[face,:,2]
            depth=u*z[0]+v*z[1]+w*z[2]
            depthpatch=depthbuffer[ymin:ymax+1,xmin:xmax+1]
            visible=(u>=0)&(v>=0)&(w>=0)&(depth>depthpatch)
            if not visible.any():
                continue
            n=smooth_normals[mesh.faces[face]]
            interpolated=u[...,None]*n[0]+v[...,None]*n[1]+w[...,None]*n[2]
            interpolated/=np.maximum(np.linalg.norm(interpolated,axis=-1,keepdims=True),1e-12)
            value=0.25+0.75*np.clip(interpolated@light,0,1)
            colors=(value[...,None]*np.array([212,220,230])).astype(np.uint8)
            framebuffer[ymin:ymax+1,xmin:xmax+1][visible]=colors[visible]
            depthpatch[visible]=depth[visible]
            continue
        value = brightness[face]
        color = tuple(int(c * value) for c in (212, 220, 230))
        draw.polygon([tuple(p) for p in projected[face]], fill=color,
                     outline='#253341' if args.wireframe else None)
    if not args.wireframe:
        canvas=Image.fromarray(framebuffer)
        draw=ImageDraw.Draw(canvas)
    draw.text((index*600+24, 24), 'FRONT' if index == 0 else 'THREE-QUARTER', fill='#d4dce6')
draw.text((24, 684), f'{args.label} | {len(mesh.vertices):,} vertices | {len(mesh.faces):,} triangles', fill='#d4dce6')
output = args.output or args.model.with_name('preview.png')
canvas.save(output)
print(output)
