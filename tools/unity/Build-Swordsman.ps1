param(
    [string]$Unity = 'C:\Program Files\Unity\Hub\Editor\6000.6.6f1\Editor\Unity.exe',
    [switch]$Test
)
$ErrorActionPreference = 'Stop'
$taskRepo = Split-Path (Split-Path $PSScriptRoot -Parent) -Parent
$taskProject = Join-Path $taskRepo 'unity/SwordsmanCombatTest'
$taskWork = Join-Path $taskRepo 'work/unity-test'
if (-not (Test-Path -LiteralPath $Unity)) { throw "Unity editor missing: $Unity" }
$taskArguments = '-batchmode -nographics -projectPath "{0}" -executeMethod SwordsmanTest.Editor.CombatSceneBuilder.Build -logFile "{1}"' -f $taskProject, (Join-Path $taskWork 'build.log')
$taskBuild = Start-Process -FilePath $Unity -ArgumentList $taskArguments -WindowStyle Hidden -Wait -PassThru
if ($taskBuild.ExitCode -ne 0) { throw 'Unity build failed. See work/unity-test/build.log' }
if ($Test) {
    $taskExecutable = Join-Path $taskWork 'Build/SwordsmanCombatTest.exe'
    $taskValidation = Join-Path $taskProject 'Validation'
    $taskArguments = '-batchmode -force-d3d11 -screen-width 1280 -screen-height 800 -combatSmoke -testOutput "{0}" -logFile "{1}"' -f $taskValidation, (Join-Path $taskWork 'runtime.log')
    $taskRun = Start-Process -FilePath $taskExecutable -ArgumentList $taskArguments -WindowStyle Hidden -Wait -PassThru
    if ($taskRun.ExitCode -ne 0) { throw 'Runtime checks failed. See Validation/runtime-test-report.json and work/unity-test/runtime.log' }
}
Write-Output 'Ready: unity/SwordsmanCombatTest/Play.cmd'
