"""Project front/rear concept colours into the actual 3D mesh UV atlas."""
from pathlib import Path
import json
import numpy as np
from PIL import Image
from scipy.ndimage import distance_transform_edt,binary_erosion
ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/'art/characters/swordsman/hunyuan_textured_v001'
OUT.mkdir(parents=True,exist_ok=True)
data=np.load(ROOT/'work/hunyuan2mini/texture_mesh.npz')
vertices=data['positions'];normals=data['normals'];triangles=data['triangles'];uvs=data['uvs']
def reference(path):
    rgba=np.asarray(Image.open(path).convert('RGBA'))
    mask=rgba[:,:,3]>220
    yy,xx=np.where(mask)
    bounds=(int(xx.min()),int(yy.min()),int(xx.max()),int(yy.max()))
    safe=binary_erosion(mask,iterations=3)
    _,nearest=distance_transform_edt(~safe,return_indices=True)
    rgb=rgba[:,:,:3][nearest[0],nearest[1]]
    return rgb,bounds
front,fb=reference(ROOT/'art/characters/swordsman/reference/swordsman_simplified_v001.png')
back,bb=reference(ROOT/'art/characters/swordsman/reference/swordsman_back_texture_v001.png')
size=2048
atlas=np.zeros((size,size,3),dtype=np.uint8)
covered=np.zeros((size,size),dtype=bool)
minimum=vertices.min(axis=0);maximum=vertices.max(axis=0)
def project(image,bounds,points,reverse=False):
    x=(points[...,0]-minimum[0])/(maximum[0]-minimum[0])
    y=(maximum[2]-points[...,2])/(maximum[2]-minimum[2])
    if reverse:x=1-x
    ix=np.clip(np.rint(bounds[0]+x*(bounds[2]-bounds[0])).astype(int),0,image.shape[1]-1)
    iy=np.clip(np.rint(bounds[1]+y*(bounds[3]-bounds[1])).astype(int),0,image.shape[0]-1)
    return image[iy,ix].astype(float)
for indices,uv in zip(triangles,uvs):
    points=uv*np.array([size-1,-(size-1)])+np.array([0,size-1])
    xmin=max(0,int(np.floor(points[:,0].min())));xmax=min(size-1,int(np.ceil(points[:,0].max())))
    ymin=max(0,int(np.floor(points[:,1].min())));ymax=min(size-1,int(np.ceil(points[:,1].max())))
    if xmin>xmax or ymin>ymax:continue
    x,y=np.meshgrid(np.arange(xmin,xmax+1)+.5,np.arange(ymin,ymax+1)+.5)
    a,b,c=points
    denominator=(b[1]-c[1])*(a[0]-c[0])+(c[0]-b[0])*(a[1]-c[1])
    if abs(denominator)<1e-10:continue
    u=((b[1]-c[1])*(x-c[0])+(c[0]-b[0])*(y-c[1]))/denominator
    v=((c[1]-a[1])*(x-c[0])+(a[0]-c[0])*(y-c[1]))/denominator;w=1-u-v
    mask=(u>=0)&(v>=0)&(w>=0)
    if not mask.any():continue
    p=u[...,None]*vertices[indices[0]]+v[...,None]*vertices[indices[1]]+w[...,None]*vertices[indices[2]]
    n=u[...,None]*normals[indices[0]]+v[...,None]*normals[indices[1]]+w[...,None]*normals[indices[2]]
    # Front is Blender -Y; softly blend side projections across UV seams.
    blend=np.clip(.5-n[...,1]*1.5,0,1)[...,None]
    colour=project(front,fb,p)*blend+project(back,bb,p,True)*(1-blend)
    atlas[ymin:ymax+1,xmin:xmax+1][mask]=np.clip(colour[mask],0,255).astype(np.uint8)
    covered[ymin:ymax+1,xmin:xmax+1][mask]=True
distance,nearest=distance_transform_edt(~covered,return_indices=True)
padding=(~covered)&(distance<=12)
atlas[padding]=atlas[nearest[0][padding],nearest[1][padding]]
Image.fromarray(atlas).save(OUT/'swordsman_basecolor_2048.png')
# A restrained roughness map; no photographic microdetail added to the style.
r,g,b=atlas[:,:,0].astype(float),atlas[:,:,1].astype(float),atlas[:,:,2].astype(float)
skin=(r>100)&(g>55)&(b>30)&(r>g*1.18)&(g>b*1.1)
leather=(r>g*1.10)&(g>b*1.04)&~skin
roughness=np.full((size,size),218,dtype=np.uint8)
roughness[skin]=170;roughness[leather]=185
Image.fromarray(roughness).save(OUT/'swordsman_roughness_2048.png')
(OUT/'texture_projection.json').write_text(json.dumps(dict(size=size,
    front=str(ROOT/'art/characters/swordsman/reference/swordsman_simplified_v001.png'),
    rear=str(ROOT/'art/characters/swordsman/reference/swordsman_back_texture_v001.png'),
    front_bounds=fb,rear_bounds=bb,coverage=float(covered.mean()),padding_pixels=12,
    method='Two-view colour projection, front/back normal blending, UV rasterization. Rear view is generated, not observed.'),indent=2),encoding='utf-8')
print('TEXTURES_READY',float(covered.mean()),flush=True)
