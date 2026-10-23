"""Compose labeled contact sheets/GIFs from actual Blender renders."""
import json, argparse
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[2]
p=argparse.ArgumentParser();p.add_argument('--folder',type=Path,default=ROOT/'art/characters/swordsman/hunyuan_combat_v006')
OUT=p.parse_args().folder.resolve()
font = ImageFont.truetype('C:/Windows/Fonts/arial.ttf', 18)
keys = json.loads((OUT / 'keyframes.json').read_text(encoding='utf-8'))
sheet = Image.new('RGB', (1024, ((len(keys) + 3) // 4) * 280), '#202832')
for i, item in enumerate(keys):
    with Image.open(OUT / item['file']) as source:
        thumb = source.convert('RGB').resize((256, 256))
    x, y = i % 4 * 256, i // 4 * 280
    sheet.paste(thumb, (x, y))
    ImageDraw.Draw(sheet).text((x + 6, y + 258), f"{item['clip']}  f{item['frame']}", font=font, fill='white')
sheet.save(OUT / 'pose_contact_sheet.jpg', quality=92)
if (OUT / 'preview_frames.json').exists():
    all_frames = []
    for clip in json.loads((OUT / 'spec.json').read_text(encoding='utf-8'))['animations']:
        frames = []
        for path in sorted((OUT / 'preview_frames' / clip['name']).glob('*.png')):
            with Image.open(path) as source: image = source.convert('RGB')
            draw = ImageDraw.Draw(image)
            draw.rectangle((0, 0, 512, 32), fill='#202832')
            draw.text((12, 5), clip['name'], font=font, fill='white')
            frames.append(image)
        duration = round(clip['duration_s'] * 1000 / max(1, len(frames) - 1))
        delays = [duration] * len(frames)
        if not clip['loop']: delays[-1] = 450
        frames[0].save(OUT / f"{clip['name']}.gif", save_all=True, append_images=frames[1:],
                       duration=delays, loop=0, disposal=2)
        all_frames.extend([(im, delay) for im, delay in zip(frames, delays)])
    all_frames[0][0].save(OUT / 'animation_set_preview.gif', save_all=True,
                         append_images=[x[0] for x in all_frames[1:]],
                         duration=[x[1] for x in all_frames], loop=0, disposal=2)
print('COMBAT_MEDIA_ASSEMBLED')
if (OUT / 'combo_frames.json').exists():
    frames = []
    for item in json.loads((OUT / 'combo_frames.json').read_text(encoding='utf-8')):
        with Image.open(OUT / item['file']) as source: image = source.convert('RGB')
        draw = ImageDraw.Draw(image); draw.rectangle((0, 0, 512, 32), fill='#202832')
        draw.text((12, 5), item['clip'], font=font, fill='white'); frames.append(image)
    frames[0].save(OUT / 'combo_preview.gif', save_all=True, append_images=frames[1:], duration=33,
                   loop=0, disposal=2)
