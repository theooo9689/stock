@echo off
setlocal
set "RADAR_APP=%LOCALAPPDATA%\RadarInvestimentos"
if not exist "%RADAR_APP%\.venv\Scripts\python.exe" (
  echo Execute INSTALAR_WINDOWS.cmd primeiro.
  pause
  exit /b 1
)
cd /d "%RADAR_APP%"
".venv\Scripts\python.exe" -m radar.cli run --refresh --send
set "RADAR_RESULT=%ERRORLEVEL%"
pause
exit /b %RADAR_RESULT%
