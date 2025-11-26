@echo off
setlocal

echo ==========================================
echo      BoxMotionAnalyzer Build Script
echo ==========================================
echo.
echo Select build mode:
echo 1. Folder (onedir) - Faster build, faster startup (Recommended for dev/internal)
echo 2. Single File (onefile) - Easy distribution, slower startup
echo.

set /p choice="Enter choice (1 or 2): "

if "%choice%"=="1" (
    set MODE=onedir
) else if "%choice%"=="2" (
    set MODE=onefile
) else (
    echo Invalid choice. Exiting.
    pause
    exit /b 1
)

echo.
echo Building in %MODE% mode...
echo.

python build.py %MODE%

if %ERRORLEVEL% NEQ 0 (
    echo.
    echo Build failed!
    pause
    exit /b %ERRORLEVEL%
)

echo.
echo Build finished successfully!
pause
