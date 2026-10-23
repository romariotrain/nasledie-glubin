# Swordsman v008 — graphic material study

Preserved v007 proportions, skeleton, weights, nine clips, timing and UVs.
**11,980 triangles including sword, 31 bones, at most four weights per vertex.**
No triangle reduction or new rig. No new provider generation or external assets.

New procedural material palette is baked into the original 2048 px UV atlas:
cool charcoal cloth, warm dark leather, crimson accents, retained face identity
and belt detail. The original fine normal relief is replaced by a neutral map;
roughness is consistently high. Cloth/leather micro-folds are softened with bounded
Taubin smoothing, max 7 mm (boots max 4 mm), retaining topology and protected edges.
`build_receipt.json` records original source hash, palette and displacement.

Blender source, GLB and FBX are validated separately. All clip frames are sampled
for the existing lower-coat/leg contact audit; this excludes upper-body intersections
and arbitrary runtime blends. Roundtrip checks bone heads and sword bounds at
sampled times. Material classification is heuristic; face details are reused.
This is a first graphic style study, not a claim of final hand-painted art polish.

Unity uses the same gameplay configuration and graphic character shader as v007.
Effects, speed, scale, attack recovery and movement distances are unchanged.
Unity GPU captures and 18 functional checks are in `unity/SwordsmanCombatTest/Validation`;
historical v007 evidence is archived in its version subfolder. `before_after.png`
uses identical Blender cameras/light; engine captures establish actual game appearance.
