@echo off
set "COMBAT_EXE=%~dp0..\..\work\unity-test\Build\SwordsmanCombatTest.exe"
if not exist "%COMBAT_EXE%" (
  echo Build missing. Run tools\unity\Build-Swordsman.ps1 first.
  pause
  exit /b 1
)
start "" "%COMBAT_EXE%" -force-d3d11 -screen-width 1280 -screen-height 800 -screen-fullscreen 0
