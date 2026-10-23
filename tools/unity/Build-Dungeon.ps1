param([switch]$Test,[string]$Revision='v003')
$ErrorActionPreference='Stop'
$taskRepo=Split-Path (Split-Path $PSScriptRoot -Parent) -Parent
$taskOriginal=Join-Path $taskRepo 'unity/SwordsmanCombatTest'
$taskPreview=Join-Path $taskRepo 'work/UnityDungeonPreview_v001'
$taskWork=Join-Path $taskRepo 'work/unity-dungeon-test'
$taskUnity='C:/Program Files/Unity/Hub/Editor/6000.6.6f1/Editor/Unity.exe'
New-Item -ItemType Directory -Force $taskPreview,$taskWork | Out-Null
foreach($taskFolder in @('Assets','Packages','ProjectSettings')){
    Copy-Item -LiteralPath (Join-Path $taskOriginal $taskFolder) -Destination $taskPreview -Recurse -Force
}
$taskArgs='-batchmode -nographics -projectPath "{0}" -executeMethod SwordsmanTest.Editor.CombatSceneBuilder.BuildDungeon -logFile "{1}"' -f $taskPreview,(Join-Path $taskWork 'build.log')
$taskBuild=Start-Process -FilePath $taskUnity -ArgumentList $taskArgs -WindowStyle Hidden -Wait -PassThru
if($taskBuild.ExitCode -ne 0){throw 'Dungeon build failed; see work/unity-dungeon-test/build.log'}
# Only admit this new scene and its own generated asset directory to the open project.
$taskAssets='Assets/SwordsmanTest'
Copy-Item -Path (Join-Path $taskPreview "$taskAssets/Art/Dungeon/*") -Destination (Join-Path $taskOriginal "$taskAssets/Art/Dungeon") -Force
foreach($taskFile in @('Scenes/DungeonCombatTest.unity','Scenes/DungeonCombatTest.unity.meta','Runtime/TorchFlicker.cs.meta','Prefabs/SwordsmanPlayer_v010.prefab','Prefabs/SwordsmanPlayer_v010.prefab.meta','Data/CombatTuning_v010.asset','Data/CombatTuning_v010.asset.meta')){
    Copy-Item -LiteralPath (Join-Path $taskPreview "$taskAssets/$taskFile") -Destination (Join-Path $taskOriginal "$taskAssets/$taskFile") -Force
}
if($Test){
    $taskOutput=Join-Path $taskOriginal ('Validation/dungeon_'+$Revision)
    New-Item -ItemType Directory -Force $taskOutput | Out-Null
    $taskArgs='-batchmode -force-d3d11 -screen-width 1280 -screen-height 800 -combatSmoke -testOutput "{0}" -logFile "{1}"' -f $taskOutput,(Join-Path $taskWork 'runtime.log')
    $taskRun=Start-Process -FilePath (Join-Path $taskWork 'Build/SwordsmanCombatTest.exe') -ArgumentList $taskArgs -WindowStyle Hidden -Wait -PassThru
    if($taskRun.ExitCode -ne 0){throw 'Dungeon runtime checks failed'}
}
Write-Output 'Ready: unity/SwordsmanCombatTest/PlayDungeon.cmd'
