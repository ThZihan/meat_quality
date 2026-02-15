# ========================================
# Upload Script for MQ135 Sensor (PowerShell)
# ESP32 NodeMCU - Meat Quality Air Data
# ========================================

Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "MQ135 Sensor Upload Script" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# Show current directory
$currentDir = Get-Location
Write-Host "Current directory: $currentDir" -ForegroundColor Yellow
Write-Host ""

# Check if we're in the right directory
if (-not (Test-Path "src_mq135\main.cpp")) {
    Write-Host "ERROR: src_mq135\main.cpp not found!" -ForegroundColor Red
    Write-Host ""
    Write-Host "You must run this script from the project root directory." -ForegroundColor Yellow
    Write-Host "Current directory should be: D:\projects\meat_quality_Air_data" -ForegroundColor Yellow
    Write-Host ""
    Write-Host "If you're in a different directory, navigate to:" -ForegroundColor Yellow
    Write-Host "  Set-Location D:\projects\meat_quality_Air_data" -ForegroundColor Yellow
    Write-Host ""
    Read-Host "Press Enter to exit"
    exit 1
}

if (-not (Test-Path "src_mq135\platformio.ini")) {
    Write-Host "ERROR: src_mq135\platformio.ini not found!" -ForegroundColor Red
    Write-Host ""
    Read-Host "Press Enter to exit"
    exit 1
}

Write-Host "✓ Found MQ135 project files" -ForegroundColor Green
Write-Host ""

# Change to MQ135 directory
Write-Host "Changing to MQ135 project directory..." -ForegroundColor Yellow
Set-Location "src_mq135"
$currentDir = Get-Location
Write-Host "New directory: $currentDir" -ForegroundColor Yellow
Write-Host ""

# Check for PlatformIO
$pioPath = Get-Command pio -ErrorAction SilentlyContinue
if (-not $pioPath) {
    Write-Host "ERROR: PlatformIO (pio) not found in PATH!" -ForegroundColor Red
    Write-Host ""
    Write-Host "Since you're using VSCode, please use the VSCode PlatformIO extension:" -ForegroundColor Yellow
    Write-Host ""
    Write-Host "OPTION 1: Use VSCode PlatformIO Extension (Recommended)" -ForegroundColor Cyan
    Write-Host "  1. Open src_mq135\main.cpp in VSCode" -ForegroundColor White
    Write-Host "  2. Press Ctrl + Shift + P" -ForegroundColor White
    Write-Host "  3. Type: PlatformIO: Upload" -ForegroundColor White
    Write-Host "  4. Select 'Upload'" -ForegroundColor White
    Write-Host ""
    Write-Host "OPTION 2: Use VSCode Terminal" -ForegroundColor Cyan
    Write-Host "  1. Open src_mq135\main.cpp in VSCode" -ForegroundColor White
    Write-Host "  2. Press Ctrl + ~ to open terminal" -ForegroundColor White
    Write-Host "  3. Run: pio run --target upload" -ForegroundColor White
    Write-Host ""
    Write-Host "OPTION 3: Add PlatformIO to PATH" -ForegroundColor Cyan
    Write-Host "  1. Open VSCode" -ForegroundColor White
    Write-Host "  2. Press Ctrl + Shift + P" -ForegroundColor White
    Write-Host "  3. Type: PlatformIO: Install Shell Commands" -ForegroundColor White
    Write-Host "  4. Restart VSCode and PowerShell" -ForegroundColor White
    Write-Host ""
    Set-Location ".."
    Read-Host "Press Enter to exit"
    exit 1
}

Write-Host "✓ PlatformIO found" -ForegroundColor Green
Write-Host ""

# Show what we're about to upload
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "About to upload MQ135 sensor code" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "Source file: main.cpp" -ForegroundColor White
Write-Host "Target: ESP32 NodeMCU (COM7)" -ForegroundColor White
Write-Host ""
Write-Host "Expected output after upload:" -ForegroundColor White
Write-Host "  - MQ135 Air Quality Sensor" -ForegroundColor White
Write-Host "  - Circuit wiring information" -ForegroundColor White
Write-Host "  - CO2 and NH3 readings" -ForegroundColor White
Write-Host "  - Meat quality assessment" -ForegroundColor White
Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# Ask for confirmation
$confirm = Read-Host "Ready to upload? (Y/N)"
if ($confirm -ne "Y" -and $confirm -ne "y") {
    Write-Host "Upload cancelled." -ForegroundColor Yellow
    Set-Location ".."
    Read-Host "Press Enter to exit"
    exit 0
}

Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "Building MQ135 sensor code..." -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

$buildResult = pio run
if ($LASTEXITCODE -ne 0) {
    Write-Host ""
    Write-Host "ERROR: Build failed!" -ForegroundColor Red
    Write-Host "Check the error messages above." -ForegroundColor Yellow
    Write-Host ""
    Set-Location ".."
    Read-Host "Press Enter to exit"
    exit 1
}

Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "Build successful!" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "Uploading to ESP32 NodeMCU..." -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "Make sure:" -ForegroundColor Yellow
Write-Host "  1. ESP32 is connected via USB" -ForegroundColor White
Write-Host "  2. COM port is correct (COM7)" -ForegroundColor White
Write-Host "  3. ESP32 is ready to receive" -ForegroundColor White
Write-Host ""

$uploadResult = pio run --target upload
if ($LASTEXITCODE -ne 0) {
    Write-Host ""
    Write-Host "ERROR: Upload failed!" -ForegroundColor Red
    Write-Host ""
    Write-Host "Troubleshooting:" -ForegroundColor Yellow
    Write-Host "  1. Check ESP32 is connected via USB" -ForegroundColor White
    Write-Host "  2. Try different USB cable" -ForegroundColor White
    Write-Host "  3. Press BOOT button on ESP32" -ForegroundColor White
    Write-Host "  4. Check COM port in src_mq135\platformio.ini" -ForegroundColor White
    Write-Host "  5. Try restarting VSCode" -ForegroundColor White
    Write-Host ""
    Set-Location ".."
    Read-Host "Press Enter to exit"
    exit 1
}

Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "Upload successful!" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# Return to root directory
Set-Location ".."

Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "Next Steps:" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "1. Open VSCode Serial Monitor:" -ForegroundColor White
Write-Host "   - Press Ctrl + Shift + P" -ForegroundColor White
Write-Host "   - Type: PlatformIO: Serial Monitor" -ForegroundColor White
Write-Host "   - Set baud rate to 115200" -ForegroundColor White
Write-Host ""
Write-Host "2. Or run: monitor_mq135.bat" -ForegroundColor White
Write-Host ""
Write-Host "3. Verify you see MQ135 sensor output" -ForegroundColor White
Write-Host ""
Write-Host "Expected output:" -ForegroundColor White
Write-Host "  ========================================" -ForegroundColor Gray
Write-Host "  MQ135 Air Quality Sensor - ESP32 NodeMCU" -ForegroundColor Gray
Write-Host "  ========================================" -ForegroundColor Gray
Write-Host ""
Write-Host "  CIRCUIT WIRING:" -ForegroundColor Gray
Write-Host "  MQ135 VCC  → 5V" -ForegroundColor Gray
Write-Host "  MQ135 GND  → GND" -ForegroundColor Gray
Write-Host "  ..." -ForegroundColor Gray
Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

Read-Host "Press Enter to exit"
