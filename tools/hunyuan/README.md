# Local Hunyuan3D-2mini experiment

Shape-only generation. Runtime, model caches and test output live under the
git-ignored `work/hunyuan2mini/` directory. No texture, rig or game import is performed.

Upstream: https://github.com/Tencent-Hunyuan/Hunyuan3D-2

Checked-out revision: `f8db63096c8282cb27354314d896feba5ba6ff8a`.

Environment: Python 3.10, PyTorch 2.5.1 / CUDA 12.4, torchvision 0.20.1.
Additional dependencies: `requirements-shape.txt`.

Run from PowerShell:

```powershell
& .\tools\hunyuan\run-shape.ps1
```

After the first output exists, choose a new output directory:

```powershell
& .\tools\hunyuan\run-shape.ps1 -Output .\work\hunyuan2mini\outputs\swordsman-test-002
```

The default source is the original swordsman concept sheet. The script crops
the idle front view and uses rembg/u2net on CPU to remove its background.
The crop is only 155 × 186 pixels, so this is a technical feasibility test;
a dedicated larger character concept should improve the input quality.

For another image, pass `-Image` with an absolute path and `-Output` with a new
output directory. The default output is `work/hunyuan2mini/outputs/swordsman-test-001`.
Existing GLB output is never overwritten. Successful generation writes a
GLB and `receipt.json` with parameters, source/output hashes and static mesh checks.

CPU offload keeps model components in system memory between their GPU stages.
The launcher does not close other applications or change GPU settings.

Model terms: Tencent Hunyuan3D 2.0 Community License, retained in the upstream
checkout. This is not an MIT/Apache model; review its terms before distribution.

## Verified first run — 2026-10-23

- NVIDIA RTX 3060 Ti 8 GB; CUDA detected successfully.
- 30 steps, resolution 256, chunks 8000, FP16 with model CPU offload.
- Generation: 23.85 seconds (excludes loading weights and input preparation).
- Peak PyTorch allocated GPU memory: 2.20 GiB (not total system GPU usage).
- GLB: 5,608,108 bytes; 155,759 vertices; 311,518 triangles.
- GLB reloaded successfully; finite vertex coordinates; watertight mesh.
- Two-view CPU preview: `work/hunyuan2mini/outputs/swordsman-test-001/preview.png`.
- No texture, rigging, retopology or engine validation. Sword and clothing are
  part of the generated mesh; this is a shape prototype, not a modular game character.
- The upstream CPU-offload helper required a `components` map and explicit
  execution device; the launcher supplies both without modifying upstream.
- The upstream downloader stalled and fetched duplicate formats. The launcher
  downloads only safetensors directly from the official Hugging Face model,
  checks size and LFS SHA256, and reuses local weights on subsequent runs.
- Environment package versions: `work/hunyuan2mini/installed-packages.txt`.
