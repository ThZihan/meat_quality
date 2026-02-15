@echo off
REM Upload script for ESP32 project
REM This script handles path issues with spaces and special characters

echo ========================================
echo ESP32 Project Upload Script
echo ========================================
echo.

REM Change to project directory
cd /d "%~dp0"

echo Current directory: %CD%
echo.

REM Run PlatformIO upload
echo Uploading to ESP32 (COM7)...
C:\Users\tahfi\.platformio\penv\Scripts\platformio.exe run --target upload --upload-port COM7

if %ERRORLEVEL% EQU 0 (
    echo.
    echo ========================================
    echo Upload SUCCESS!
    echo ========================================
) else (
    echo.
    echo ========================================
    echo Upload FAILED!
    echo ========================================
)

echo.
pause
