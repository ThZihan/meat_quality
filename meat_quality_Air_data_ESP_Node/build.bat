@echo off
REM Build script for ESP32 project
REM This script handles path issues with spaces and special characters

echo ========================================
echo ESP32 Project Build Script
echo ========================================
echo.

REM Change to project directory
cd /d "%~dp0"

echo Current directory: %CD%
echo.

REM Run PlatformIO build
echo Building project...
C:\Users\tahfi\.platformio\penv\Scripts\platformio.exe run

if %ERRORLEVEL% EQU 0 (
    echo.
    echo ========================================
    echo Build SUCCESS!
    echo ========================================
) else (
    echo.
    echo ========================================
    echo Build FAILED!
    echo ========================================
)

echo.
pause
