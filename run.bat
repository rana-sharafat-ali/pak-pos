@echo off
title PakPOS - Retail & Point of Sale Server
cd /d "%~dp0"

echo ======================================================
echo           Starting PakPOS Management Server
echo ======================================================
echo.

:: 1. Activate Python Virtual Environment
if exist "%~dp0venv\Scripts\activate.bat" (
    echo [1/3] Activating Virtual Environment...
    call "%~dp0venv\Scripts\activate.bat"
) else (
    echo [ERROR] Virtual environment 'venv' not found!
    echo Please make sure 'venv' folder exists in project root.
    echo.
    pause
    exit /b 1
)

:: 2. Apply Database Migrations (if any pending)
echo [2/3] Checking and applying database migrations...
python manage.py migrate --noinput
echo.

:: 3. Launch Default Web Browser
echo [3/3] Opening PakPOS in browser...
start http://127.0.0.1:8000/

echo.
echo ======================================================
echo    Server is live at: http://127.0.0.1:8000/
echo    POS Terminal:      http://127.0.0.1:8000/sales/
echo    Press CTRL + C to stop the server.
echo ======================================================
echo.

:: 4. Start Django Development Server
python manage.py runserver 0.0.0.0:8000

if %ERRORLEVEL% NEQ 0 (
    echo.
    echo [NOTICE] Server has stopped.
    pause
)
