@echo off
setlocal
cd /d "%~dp0"
echo Campus Portal: http://127.0.0.1:5500/
echo Stop VS Code Live Server before starting this server on port 5500.
echo Keep this window open while using the portal. Press Ctrl+C to stop.
if exist ".venv\Scripts\python.exe" (
  ".venv\Scripts\python.exe" app.py %*
) else if exist ".runtime\python\python.exe" (
  ".runtime\python\python.exe" app.py %*
) else (
  python app.py %*
)
if errorlevel 1 (
  echo Startup failed. See README.md for Python and dependency setup.
  pause
)
endlocal
