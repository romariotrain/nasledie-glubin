# Swordsman v007 — lighter silhouette

Local revision of the preserved v006 character, following the user's run/action references and request for lighter, graphic proportions. No new provider generation or downloaded character assets.

Boots are narrower, shallower and slightly lower; hips, legs, torso and shoulders are slimmer. Lower coat volume is reduced. Existing joint topology and UVs are retained: **11,980 triangles including sword, 31 bones, maximum four influences**. This iteration changes silhouette, not polygon count. Painted maps remain 2048 px; stronger graphic lighting is implemented in the Unity character shader.

Nine clips: idle, run, attack_1, attack_2, attack_3, dodge, piercing_lunge, hurt, death. Run has a 21 cm foot track, heel pickup, forward lean and downward sword carry; reference movement speed is 3 m/s. Combo uses opposing body rotations and a held heavy impact pose. Dash leans forward with a trailing leg and braking pose. Runtime displacement remains controlled by code.

`refinement_report.json` records source hash and deformation parameters. Source validation samples all clip frames for lower-coat/leg contact; export roundtrip compares bone heads and sword bounds in GLB and FBX. Reports are hash-bound. These tests do not prove collision-free arbitrary blends, perfect fingers or final animation polish. No physical cloth simulation. Original baked-light texture limitations remain.

`comparison/` uses identical cameras and lighting for v006/v007. `before_after.png` compares the silhouettes. Unity import and runtime evidence are stored separately in `unity/SwordsmanCombatTest/Validation`.
