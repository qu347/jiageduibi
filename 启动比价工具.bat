@echo off
setlocal
cd /d "%~dp0"

powershell.exe -NoProfile -ExecutionPolicy Bypass -Command "try { $health = Invoke-RestMethod -Uri 'http://127.0.0.1:8765/api/health' -TimeoutSec 2; if ($health.status -eq 'ok') { Start-Process 'http://127.0.0.1:8765/'; exit 0 } } catch {}; exit 1"
if not errorlevel 1 (
  echo Price comparison tool is already running. Opening the page...
  exit /b 0
)

echo Starting the personal subsidy price comparison tool...
echo Keep this window open while using the tool.
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\demo.ps1"
set "launcherExitCode=%ERRORLEVEL%"

if not "%launcherExitCode%"=="0" (
  echo.
  echo Startup failed. See the error message above.
  pause
)

exit /b %launcherExitCode%
