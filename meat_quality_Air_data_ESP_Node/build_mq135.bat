@echo off
REM ========================================
REM Build and Upload Script for MQ135 Sensor
REM ESP32 NodeMCU - Meat Quality Air Data
REM ========================================

echo.
echo ========================================
echo MQ135 Sensor Build Script
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

echo [1/3] Cleaning previous build...
pio run --target clean
if %ERRORLEVEL% NEQ 0 (
    echo ERROR: Clean failed!
    cd /d "%~dp0"
    pause
    exit /b 1
)
echo Clean complete.
echo.

echo [2/3] Building MQ135 sensor code...
pio run
if %ERRORLEVEL% NEQ 0 (
    echo ERROR: Build failed!
    echo Check the error messages above.
    cd /d "%~dp0"
    pause
    exit /b 1
)
echo Build successful!
echo.

echo [3/3] Uploading to ESP32 NodeMCU...
pio run --target upload
if %ERRORLEVEL% NEQ 0 (
    echo ERROR: Upload failed!
    echo Check:
    echo   1. ESP32 is connected via USB
    echo   2. Correct COM port in platformio.ini (currently COM7)
    echo   3. ESP32 is in bootloader mode (press BOOT button)
    cd /d "%~dp0"
    pause
    exit /b 1
)
echo Upload successful!
echo.

REM Return to original directory
cd /d "%~dp0"

echo ========================================
echo Build and Upload Complete!
echo ========================================
echo.
echo To view serial output, run:
echo   cd src_mq135 && pio device monitor -b 115200
echo.
echo Or open Serial Monitor in VSCode:
echo   Press Ctrl+Shift+P, then "Serial Monitor: Open"
echo   Set baud rate to 115200
echo.
echo ========================================
echo MQ135 Sensor Wiring:
echo ========================================
echo MQ135 VCC  → 5V
echo MQ135 GND  → GND
echo MQ135 AOUT → Voltage Divider (2x 10kΩ)
echo               └─ ESP32 GPIO 34 (ADC1_CH6)
echo.
echo Voltage Divider:
echo   MQ135 AOUT ──[10kΩ]─┬─[10kΩ]─ GND
echo                         │
echo                         └─ ESP32 GPIO 34
echo.
echo CRITICAL: NEVER connect MQ135 AOUT directly to ESP32!
echo The voltage divider is MANDATORY for 5V → 3.3V conversion.
echo.
echo ========================================
echo Calibration:
echo ========================================
echo 1. Set calibrationMode = true in code
echo 2. Upload and run in clean air
echo 3. Note the R0 value from Serial Monitor
echo 4. Update R0 constant in code
echo 5. Set calibrationMode = false
echo 6. Re-upload for normal operation
echo.
pause
