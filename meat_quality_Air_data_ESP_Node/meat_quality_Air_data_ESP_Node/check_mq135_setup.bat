@echo off
REM ========================================
REM Diagnostic Script for MQ135 Setup
REM ESP32 NodeMCU - Meat Quality Air Data
REM ========================================

echo.
echo ========================================
echo MQ135 Setup Diagnostic Tool
echo ========================================
echo.

REM Check current directory
echo [1/7] Checking current directory...
echo Current directory: %CD%
if "%CD%"=="d:\projects\meat_quality_Air_data" (
    echo ✓ Correct directory
) else (
    echo ⚠ WARNING: Not in project root directory
    echo   Expected: d:\projects\meat_quality_Air_data
    echo   Actual: %CD%
)
echo.

REM Check for src_mq135 directory
echo [2/7] Checking for src_mq135 directory...
if exist "src_mq135" (
    echo ✓ src_mq135 directory exists
) else (
    echo ✗ ERROR: src_mq135 directory NOT found
    echo   This is required for MQ135 sensor project
    goto :error
)
echo.

REM Check for MQ135 main.cpp
echo [3/7] Checking for src_mq135\main.cpp...
if exist "src_mq135\main.cpp" (
    echo ✓ src_mq135\main.cpp exists
) else (
    echo ✗ ERROR: src_mq135\main.cpp NOT found
    goto :error
)
echo.

REM Check for MQ135 platformio.ini
echo [4/7] Checking for src_mq135\platformio.ini...
if exist "src_mq135\platformio.ini" (
    echo ✓ src_mq135\platformio.ini exists
) else (
    echo ✗ ERROR: src_mq135\platformio.ini NOT found
    goto :error
)
echo.

REM Check for upload scripts
echo [5/7] Checking for upload scripts...
if exist "upload_mq135.bat" (
    echo ✓ upload_mq135.bat exists
) else (
    echo ⚠ WARNING: upload_mq135.bat NOT found
)
if exist "build_mq135.bat" (
    echo ✓ build_mq135.bat exists
) else (
    echo ⚠ WARNING: build_mq135.bat NOT found
)
if exist "monitor_mq135.bat" (
    echo ✓ monitor_mq135.bat exists
) else (
    echo ⚠ WARNING: monitor_mq135.bat NOT found
)
echo.

REM Check for PlatformIO
echo [6/7] Checking for PlatformIO...
where pio >nul 2>nul
if %ERRORLEVEL% EQU 0 (
    echo ✓ PlatformIO (pio) found in PATH
) else (
    echo ⚠ PlatformIO (pio) NOT found in PATH
    echo   You can still use VSCode PlatformIO extension
)
echo.

REM Check for main project files (to avoid confusion)
echo [7/7] Checking for main project files...
if exist "src\main.cpp" (
    echo ✓ src\main.cpp exists (main MQTT project)
    echo   ⚠ NOTE: This is the OLD code, NOT the MQ135 code
    echo   To upload MQ135 code, use upload_mq135.bat
) else (
    echo ⚠ src\main.cpp NOT found (main project may not exist)
)
echo.

echo ========================================
echo Diagnostic Summary
echo ========================================
echo.

echo MQ135 Sensor Project:
echo   Location: src_mq135\
echo   Main file: src_mq135\main.cpp
echo   Config: src_mq135\platformio.ini
echo.

echo Upload Scripts:
echo   Simple upload: upload_mq135.bat
echo   Full build+upload: build_mq135.bat
echo   Serial monitor: monitor_mq135.bat
echo.

echo Main Project (MQTT):
echo   Location: src\
echo   Main file: src\main.cpp
echo   Config: platformio.ini (in root)
echo.

echo ========================================
echo How to Upload MQ135 Code
echo ========================================
echo.
echo Method 1 (Recommended):
echo   Run: upload_mq135.bat
echo.
echo Method 2 (Full build):
echo   Run: build_mq135.bat
echo.
echo Method 3 (Manual):
echo   1. cd src_mq135
echo   2. pio run --target upload
echo.
echo Method 4 (VSCode):
echo   1. Open src_mq135\main.cpp in VSCode
echo   2. Press Ctrl + ~ to open terminal
echo   3. Run: pio run --target upload
echo.

echo ========================================
echo Common Mistakes to AVOID
echo ========================================
echo.
echo ❌ DON'T use VSCode PlatformIO upload button
echo    (It uploads src\main.cpp, NOT src_mq135\main.cpp)
echo.
echo ❌ DON'T run build.bat or upload.bat
echo    (These are for the main MQTT project)
echo.
echo ❌ DON'T run pio run --target upload from root
echo    (You must be in src_mq135 directory)
echo.
echo ✅ DO run upload_mq135.bat from project root
echo ✅ DO run build_mq135.bat from project root
echo ✅ DO run pio run --target upload from src_mq135
echo.

echo ========================================
echo Next Steps
echo ========================================
echo.
echo 1. Connect MQ135 sensor with voltage divider
echo 2. Run: upload_mq135.bat
echo 3. Run: monitor_mq135.bat
echo 4. Verify sensor readings appear
echo.

goto :end

:error
echo.
echo ========================================
echo SETUP INCOMPLETE
echo ========================================
echo.
echo Please fix the errors above before proceeding.
echo.
pause
exit /b 1

:end
echo ========================================
echo Diagnostic Complete
echo ========================================
echo.
pause
