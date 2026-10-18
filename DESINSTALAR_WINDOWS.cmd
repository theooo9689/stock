@echo off
setlocal
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\windows\uninstall.ps1"
set "RADAR_RESULT=%ERRORLEVEL%"
pause
exit /b %RADAR_RESULT%
