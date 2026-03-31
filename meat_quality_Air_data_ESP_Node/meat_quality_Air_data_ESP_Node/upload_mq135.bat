@echo off
REM ========================================
REM Simple Upload Script for MQ135 Sensor
REM ESP32 NodeMCU - Meat Quality Air Data
REM ========================================

echo.
echo ========================================
echo MQ135 Sensor Upload Script
echo ========================================
echo.

REM Show current directory
echo Current directory: %CD%
echo.

REM Check if we're in the right directory
if not exist "src_mq135\main.cpp" (
    echo ERROR: src_mq135\main.cpp not found!
    echo.
    echo You must run this script from the project root directory.
    echo Current directory should be: d:\projects\meat_quality_Air_data
    echo.
    echo If you're in a different directory, navigate to:
    echo   cd /d d:\projects\meat_quality_Air_data
    echo.
    pause
    exit /b 1
)

if not exist "src_mq135\platformio.ini" (
    echo ERROR: src_mq135\platformio.ini not found!
    echo.
    pause
    exit /b 1
)

echo ✓ Found MQ135 project files
echo.

REM Change to MQ135 directory
echo Changing to MQ135 project directory...
cd src_mq135
echo New directory: %CD%
echo.

REM Check for PlatformIO
where pio >nul 2>nul
if %ERRORLEVEL% NEQ 0 (
    echo ERROR: PlatformIO (pio) not found!
    echo.
    echo Please install PlatformIO or use VSCode PlatformIO extension.
    echo.
    echo Alternative: Use VSCode terminal:
    echo   1. Open VSCode
    echo   2. Press Ctrl + ~ to open terminal
    echo   3. Run: cd src_mq135
    echo   4. Run: pio run --target upload
    echo.
    pause
    exit /b 1
)

echo ✓ PlatformIO found
echo.

REM Show what we're about to upload
echo ========================================
echo About to upload MQ135 sensor code
echo ========================================
echo.
echo Source file: main.cpp
echo Target: ESP32 NodeMCU (COM7)
echo.
echo Expected output after upload:
echo   - MQ135 Air Quality Sensor
echo   - Circuit wiring information
echo   - CO2 and NH3 readings
echo   - Meat quality assessment
echo.
echo ========================================
echo.

REM Ask for confirmation
set /p confirm="Ready to upload? (Y/N): "
if /i not "%confirm%"=="Y" (
    echo Upload cancelled.
    pause
    exit /b 0
)

echo.
echo ========================================
echo Building MQ135 sensor code...
echo ========================================
echo.

pio run
if %ERRORLEVEL% NEQ 0 (
    echo.
    echo ERROR: Build failed!
    echo Check the error messages above.
    echo.
    cd ..
    pause
    exit /b 1
)

echo.
echo ========================================
echo Build successful!
echo ========================================
echo.

echo ========================================
echo Uploading to ESP32 NodeMCU...
echo ========================================
echo.
echo Make sure:
echo   1. ESP32 is connected via USB
echo   2. COM port is correct (COM7)
echo   3. ESP32 is ready to receive
echo.

pio run --target upload
if %ERRORLEVEL% NEQ 0 (
    echo.
    echo ERROR: Upload failed!
    echo.
    echo Troubleshooting:
    echo   1. Check ESP32 is connected via USB
    echo   2. Try different USB cable
    echo   3. Press BOOT button on ESP32
    echo   4. Check COM port in src_mq135\platformio.ini
    echo   5. Try restarting VSCode
    echo.
    cd ..
    pause
    exit /b 1
)

echo.
echo ========================================
echo Upload successful!
echo ========================================
echo.

REM Return to root directory
cd ..

echo.
echo ========================================
echo Next Steps:
echo ========================================
echo.
echo 1. Run monitor_mq135.bat to view sensor readings
echo 2. Or open VSCode Serial Monitor at 115200 baud
echo 3. Verify you see MQ135 sensor output
echo.
echo Expected output:
echo   ========================================
echo   MQ135 Air Quality Sensor - ESP32 NodeMCU
echo   ========================================
echo.
echo   CIRCUIT WIRING:
echo   MQ135 VCC  → 5V
echo   MQ135 GND  → GND
echo   ...
echo.
echo ========================================
echo.

pause
