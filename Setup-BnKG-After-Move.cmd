@echo off
setlocal
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\Setup-BnKG.ps1" %*
set "setup_result=%errorlevel%"
if not "%setup_result%"=="0" echo Setup did not complete. Read the failed step and recovery instructions above.
echo.
pause
exit /b %setup_result%
