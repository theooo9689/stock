@echo off
setlocal
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\windows\install.ps1"
set "RADAR_RESULT=%ERRORLEVEL%"
echo.
pause
exit /b %RADAR_RESULT%
