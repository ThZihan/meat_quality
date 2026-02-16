@echo off
REM ========================================
REM Serial Monitor Script for MQ135 Sensor
REM ESP32 NodeMCU - Meat Quality Air Data
REM ========================================

echo.
echo ========================================
echo MQ135 Sensor Serial Monitor
echo ESP32 NodeMCU
echo ========================================
echo.

REM Check if PlatformIO is available
where pio >nul 2>nul
if %ERRORLEVEL% NEQ 0 (
    echo ERROR: PlatformIO (pio) not found!
    echo Please install PlatformIO: https://platformio.org/
    pause
    exit /b 1
)

REM Change to MQ135 sensor directory
cd /d "%~dp0src_mq135"
if %ERRORLEVEL% NEQ 0 (
    echo ERROR: Cannot find src_mq135 directory!
    pause
    exit /b 1
)

echo Working directory: %CD%
echo.
echo Opening serial monitor at 115200 baud...
echo Press Ctrl+C to exit monitor.
echo.

REM Start serial monitor
pio device monitor -b 115200

REM Return to original directory when monitor exits
cd /d "%~dp0"

echo.
echo ========================================
echo Serial Monitor Closed
echo ========================================
echo.
pause
