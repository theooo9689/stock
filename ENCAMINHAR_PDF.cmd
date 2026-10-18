@echo off
setlocal
set "PYTHONUTF8=1"
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\windows\forward-pdf.ps1"
set "RADAR_RESULT=%ERRORLEVEL%"
echo.
pause
exit /b %RADAR_RESULT%
