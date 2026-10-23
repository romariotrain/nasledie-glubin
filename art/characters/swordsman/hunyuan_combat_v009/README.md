# Swordsman v009 — lower, quieter free arm

Preserved v007 body, rest skeleton, UVs, maps and all nine clip durations.
Only the UpperArm.L and Forearm.L quaternion tracks in `run` are changed:
shoulder swing 14 degrees instead of 60, elbow bend 22–28 instead of 64–80.
Periodic cosine motion, matching cycle endpoints, and the existing transition
crossfades keep the hand low and reduce excessive pumping. Weapon arm and leg
gait are unchanged. Source hash and hand trajectories: `build_receipt.json`.

11,980 triangles including sword; 31 bones; at most four weights. Existing
maps are unchanged 2048 px. No provider generation and no new geometry.
Unchanged clip previews are reused from v007; run frames are newly rendered.
Source/export reports are regenerated for the final source and both exports.
Lower-coat/leg contact sampling does not audit every arm/body contact or arbitrary
blend. Engine rendering/functional evidence is recorded separately.

Dungeon v002 adds a dedicated character material and light in Unity: thin dark
outline, crisper lighting bands, boosted crimson accents, brighter blade.
These are shader/material settings, not modifications of the source texture maps.
