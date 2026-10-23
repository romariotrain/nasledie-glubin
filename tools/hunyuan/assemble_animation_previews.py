from pathlib import Path
from PIL import Image,ImageDraw
ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/'art/characters/swordsman/hunyuan_textured_v001'
names=['Idle','Walk_InPlace','Slash_01'];clips={}
for name in names:
    images=[Image.open(p).convert('RGB') for p in sorted((OUT/f'frames_{name}').glob('*.png'))]
    assert images,name
    images[0].save(OUT/f'{name}.gif',save_all=True,append_images=images[1:],duration=67,loop=0,optimize=True)
    clips[name]=images
combined=[]
for frame in range(30):
    image=Image.new('RGB',(1080,480),'#1c2530');draw=ImageDraw.Draw(image)
    for column,name in enumerate(names):
        index=frame%len(clips[name]) if name!='Slash_01' else min(frame,len(clips[name])-1)
        image.paste(clips[name][index],(column*360,30));draw.text((column*360+16,10),name,fill='white')
    combined.append(image)
combined[0].save(OUT/'animation_preview.gif',save_all=True,append_images=combined[1:],duration=67,loop=0,optimize=True)
print({name:len(frames) for name,frames in clips.items()})
