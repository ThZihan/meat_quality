# ========================================
# Serial Monitor Script for MQ137 Sensor
# ESP32 NodeMCU - Meat Quality Air Data
# ========================================

Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "MQ137 Sensor Serial Monitor" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# Show current directory
$currentDir = Get-Location
Write-Host "Current directory: $currentDir" -ForegroundColor Yellow
Write-Host ""

# Check if we're in the right directory
if (-not (Test-Path "src_mq137\src\main.cpp")) {
    Write-Host "ERROR: src_mq137\src\main.cpp not found!" -ForegroundColor Red
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

Write-Host "✓ Found MQ137 project files" -ForegroundColor Green
Write-Host ""

# Change to MQ137 directory
Write-Host "Changing to MQ137 project directory..." -ForegroundColor Yellow
Set-Location "src_mq137"
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
    Write-Host "  1. Open src_mq137\src\main.cpp in VSCode" -ForegroundColor White
    Write-Host "  2. Press Ctrl + Shift + P" -ForegroundColor White
    Write-Host "  3. Type: PlatformIO: Serial Monitor" -ForegroundColor White
    Write-Host "  4. Set baud rate to 115200" -ForegroundColor White
    Write-Host ""
    Write-Host "OPTION 2: Use VSCode Terminal" -ForegroundColor Cyan
    Write-Host "  1. Open src_mq137\src\main.cpp in VSCode" -ForegroundColor White
    Write-Host "  2. Press Ctrl + ~ to open terminal" -ForegroundColor White
    Write-Host "  3. Run: pio device monitor -b 115200" -ForegroundColor White
    Write-Host ""
    Set-Location ".."
    Read-Host "Press Enter to exit"
    exit 1
}

Write-Host "✓ PlatformIO found" -ForegroundColor Green
Write-Host ""

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "Opening serial monitor at 115200 baud..." -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "Press Ctrl + C to exit monitor." -ForegroundColor Yellow
Write-Host ""

# Start serial monitor
pio device monitor -b 115200

# Return to root directory when monitor exits
Set-Location ".."

Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "Serial Monitor Closed" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""
Read-Host "Press Enter to exit"
