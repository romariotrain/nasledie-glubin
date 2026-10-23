# Swordsman v010 — longer stride, lower cadence

Based on preserved v009; no new geometry, texture maps or provider generation.
Run is rebuilt with greater forward reach, rear push-off and heel pickup.
Cycle duration is 0.7333 s at a 3.9 m/s reference; code matches playback to actual
speed. Default movement speed is now 4.3 m/s, giving about 180 steps/min and
1.43 m per footfall instead of 240 steps/min and 0.90 m. These are in-game
trajectory measurements, not biomechanical claims or a motion-capture recording.

The quieter free arm and weapon carry from v009 are retained. The pelvis follows
leg reach without IK clipping; coat bones open with the larger stride. Other
eight clips and combat timings are unchanged. `build_receipt.json` records
source hash, gait parameters and IK reach clamps. Body: 11,980 triangles including
sword, 31 bones, four influences maximum; maps 2048 px.

Run preview is regenerated. Unchanged clip previews are reused from v009.
Source/export audits are new and hash-bound. Contact tests cover sampled lower
coat/leg pairs, not all body contacts or arbitrary runtime blends.

Dungeon v003 also removes idle cursor-follow rotation: locomotion faces movement,
standing preserves facing, attack/lunge aim at cursor, stationary dodge uses
current facing. Six new runtime facing checks supplement the 18 prior checks.
The existing v002 character light, outline and materials are retained.
