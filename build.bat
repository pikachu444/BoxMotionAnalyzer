@echo off
setlocal

echo ==========================================
echo      BoxMotionAnalyzer Build Script
echo ==========================================
echo.

rem --- Virtual Environment Detection & Setup ---

set "VENV_DIR="

rem 1. Check current directory for .venv
if exist ".venv" (
    echo Found virtual environment in current directory.
    set "VENV_DIR=.venv"
) else (
    rem 2. Check parent directory for .venv
    if exist "..\.venv" (
        echo Found virtual environment in parent directory.
        set "VENV_DIR=..\.venv"
    ) else (
        rem 3. Create new .venv if requirements.txt exists
        if exist "requirements.txt" (
            echo Virtual environment not found. Creating new one in .venv...
            python -m venv .venv
            if %ERRORLEVEL% NEQ 0 (
                echo Failed to create virtual environment.
                pause
                exit /b %ERRORLEVEL%
            )
            set "VENV_DIR=.venv"
        ) else (
            echo Error: Virtual environment not found and requirements.txt missing.
            echo Cannot proceed with auto-setup.
            pause
            exit /b 1
        )
    )
)

rem --- Configuration ---
set "PYTHON_EXE=%VENV_DIR%\Scripts\python.exe"

rem --- Activation ---
echo Activating virtual environment: %VENV_DIR%
echo Using Python executable: %PYTHON_EXE%

rem Still activate to set environment variables (PATH, etc.)
call "%VENV_DIR%\Scripts\activate.bat"
if %ERRORLEVEL% NEQ 0 (
    echo Failed to activate virtual environment.
    pause
    exit /b %ERRORLEVEL%
)

rem --- Dependency Installation ---
echo.
echo Checking and installing dependencies...
if exist "requirements.txt" (
    "%PYTHON_EXE%" -m pip install -r requirements.txt
    if %ERRORLEVEL% NEQ 0 (
        echo Failed to install dependencies.
        pause
        exit /b %ERRORLEVEL%
    )
) else (
    echo Warning: requirements.txt not found. Skipping dependency check.
)

rem --- Build Mode Selection ---
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

rem Run the Python build script using the explicit venv python
"%PYTHON_EXE%" build.py %MODE%

if %ERRORLEVEL% NEQ 0 (
    echo.
    echo Build failed!
    pause
    exit /b %ERRORLEVEL%
)

echo.
echo Build finished successfully!
pause
