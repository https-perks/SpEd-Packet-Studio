@echo off
setlocal
cd /d "%~dp0"
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "scripts\build-windows-release.ps1" -Bundle nsis
if errorlevel 1 (
  echo.
  echo Release build failed. Review the error above.
  pause
  exit /b 1
)
echo.
echo Release build completed successfully.
pause
