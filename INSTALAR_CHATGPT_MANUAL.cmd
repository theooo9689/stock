@echo off
setlocal
set "PYTHONUTF8=1"
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\windows\install.ps1" -Mode ChatGPT
set "RADAR_RESULT=%ERRORLEVEL%"
echo.
pause
exit /b %RADAR_RESULT%
