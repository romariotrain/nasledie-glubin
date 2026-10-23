"""Local Hunyuan3D-2mini shape-only experiment; caches stay in work/."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parents[2]
WORK = ROOT / 'work' / 'hunyuan2mini'
os.environ['HF_HOME'] = str(WORK / 'hf-cache')
os.environ['HY3DGEN_MODELS'] = str(WORK / 'models')
os.environ['U2NET_HOME'] = str(WORK / 'rembg-cache')
os.environ['HF_HUB_DISABLE_XET'] = '1'
sys.path.insert(0, str(WORK / 'repo'))

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--image', type=Path, default=ROOT / 'art/characters/swordsman/reference/user_concept_2026-10-15.png')
    parser.add_argument('--output', type=Path, default=WORK / 'outputs' / 'swordsman-test-001')
    parser.add_argument('--steps', type=int, default=30)
    parser.add_argument('--resolution', type=int, default=256)
    parser.add_argument('--seed', type=int, default=12345)
    parser.add_argument('--prepare-only', action='store_true')
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    if not args.prepare_only and (args.output / 'swordsman_untextured.glb').exists():
        raise FileExistsError('Choose a new --output directory; existing GLB is preserved.')
    from PIL import Image
    image = Image.open(args.image).convert('RGBA')
    # Isolate the full-body idle front view on the supplied concept sheet.
    crop = (20, 679, 175, 865) if args.image.name == 'user_concept_2026-10-15.png' else (0, 0, *image.size)
    image = image.crop(crop)
    image.save(args.output / 'input_crop.png')
    # Preserve a supplied cutout's alpha instead of segmenting it again.
    if image.getchannel('A').getextrema()[0] == 255:
        from rembg import remove, new_session
        image = remove(image.convert('RGB'), session=new_session('u2net', providers=['CPUExecutionProvider']))
    image.save(args.output / 'input_rgba.png')
    if args.prepare_only:
        return
    import torch
    from hy3dgen.shapegen import Hunyuan3DDiTFlowMatchingPipeline
    import requests
    assert torch.cuda.is_available(), 'CUDA is unavailable in PyTorch'
    print('GPU:', torch.cuda.get_device_name(), 'free/total:', torch.cuda.mem_get_info(), flush=True)
    # Upstream snapshot download fetches both ckpt and safetensors (~7.6 GB).
    # Only the safe FP16 weights and configuration are needed here.
    model_dir = WORK / 'models' / 'tencent' / 'Hunyuan3D-2mini'
    entries = None
    for filename in ('config.yaml', 'model.fp16.safetensors'):
        print('Downloading/checking', filename, flush=True)
        destination = model_dir / 'hunyuan3d-dit-v2-mini' / filename
        destination.parent.mkdir(parents=True, exist_ok=True)
        if not destination.exists():
            if entries is None:
                entries = requests.get('https://huggingface.co/api/models/tencent/Hunyuan3D-2mini/tree/main/hunyuan3d-dit-v2-mini?expand=true', timeout=30).json()
            metadata = next(x for x in entries if x['path'].endswith('/' + filename))
            partial = destination.with_suffix(destination.suffix + '.partial')
            url = 'https://huggingface.co/tencent/Hunyuan3D-2mini/resolve/main/hunyuan3d-dit-v2-mini/' + filename
            with requests.get(url, stream=True, timeout=(30, 60)) as response:
                response.raise_for_status()
                done = 0
                report = time.time()
                with partial.open('wb') as target:
                    for chunk in response.iter_content(4 * 1024 * 1024):
                        target.write(chunk)
                        done += len(chunk)
                        if time.time() - report > 15:
                            print(f'{filename}: {done / 1e6:.0f}/{metadata["size"] / 1e6:.0f} MB', flush=True)
                            report = time.time()
            if partial.stat().st_size != metadata['size']:
                raise RuntimeError('Downloaded model size mismatch')
            if metadata.get('lfs'):
                with partial.open('rb') as stream:
                    digest = hashlib.sha256()
                    for chunk in iter(lambda: stream.read(8 * 1024 * 1024), b''):
                        digest.update(chunk)
                if digest.hexdigest() != metadata['lfs']['oid']:
                    raise RuntimeError('Downloaded model SHA256 mismatch')
            partial.replace(destination)
    pipeline = Hunyuan3DDiTFlowMatchingPipeline.from_pretrained(
        'tencent/Hunyuan3D-2mini', subfolder='hunyuan3d-dit-v2-mini',
        variant='fp16', device='cpu', dtype=torch.float16,
    )
    # Upstream's offload helper assumes a DiffusionPipeline-style components map.
    if not hasattr(pipeline, 'components'):
        pipeline.components = {name: getattr(pipeline, name) for name in ('conditioner', 'model', 'vae')}
    pipeline.enable_model_cpu_offload()
    # Upstream __call__ reads device directly instead of _execution_device.
    pipeline.device = torch.device('cuda:0')
    start = time.time()
    mesh = pipeline(image=image, num_inference_steps=args.steps,
                    octree_resolution=args.resolution, num_chunks=8000,
                    generator=torch.Generator().manual_seed(args.seed),
                    output_type='trimesh')[0]
    if mesh is None or not len(mesh.faces):
        raise RuntimeError('Generation returned an empty mesh')
    output = args.output / 'swordsman_untextured.glb'
    if output.exists():
        raise FileExistsError(output)
    mesh.export(output)
    import trimesh
    loaded = trimesh.load(output, force='mesh')
    import numpy as np
    assert len(loaded.faces) > 0 and np.isfinite(loaded.vertices).all()
    receipt = dict(model='tencent/Hunyuan3D-2mini', subfolder='hunyuan3d-dit-v2-mini',
                   source=str(args.image), source_sha256=hashlib.sha256(args.image.read_bytes()).hexdigest(),
                   crop=crop, seed=args.seed, steps=args.steps, resolution=args.resolution,
                   seconds=time.time()-start, vertices=len(loaded.vertices), faces=len(loaded.faces),
                   bounds=loaded.bounds.tolist(), watertight=bool(loaded.is_watertight),
                   textures=False, rig=False, gpu=torch.cuda.get_device_name(),
                   peak_vram_bytes=torch.cuda.max_memory_allocated(),
                   output_sha256=hashlib.sha256(output.read_bytes()).hexdigest())
    (args.output / 'receipt.json').write_text(json.dumps(receipt, indent=2), encoding='utf-8')
    print(json.dumps(receipt, indent=2), flush=True)

if __name__ == '__main__':
    main()
