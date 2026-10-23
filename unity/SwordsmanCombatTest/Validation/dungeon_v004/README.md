# dungeon_v004 — hero material v003 (posterized colour zones)

Hero renders with `Art/Dungeon/Hero graphic v003.mat`: same shader values as v002
(three light steps, 0.85 px outline) with `Art/swordsman_basecolor_poster_v001.png`
as basecolour, normal detail off (`_BumpScale` 0) and `_RedBoost` 1. The texture
comes from `art/characters/swordsman/poster_zones_v001` (see its receipt); mesh,
rig, UVs and clips are v010 unchanged.

Produced by `CombatSceneBuilder.BuildDungeon` in the service copy
`work/UnityDungeonPreview_v001`, built from the committed project plus the change,
without another agent's uncommitted files. The scene, `SwordsmanPlayer_v010.prefab`,
`CombatTuning_v010.asset` and the v003 material were copied back exactly as
`tools/unity/Build-Dungeon.ps1` does. The runtime smoke test here ran from that
build (25 checks); the build's smoke test also captured extra storyboard frames,
which are not kept. Not sealed with `seal_dungeon_validation.py`; the sealed
baseline used by `audit_baseline.py` is still `dungeon_v003`.

A normal launch (no command-line flags) matches the frame chosen by the user via
the StylePost override: 3 of 86,016 hero-area pixels differ (idle motion).
