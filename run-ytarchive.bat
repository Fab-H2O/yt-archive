@echo off
setlocal
set "SCRIPT_DIR=%~dp0"
cd /d "%SCRIPT_DIR%"
python "%SCRIPT_DIR%archive.py" %*
set "RC=%errorlevel%"
if not "%RC%"=="0" (
    echo.
    echo Exit code %RC%. Press any key to close this window.
    pause >nul
)
exit /b %RC%
