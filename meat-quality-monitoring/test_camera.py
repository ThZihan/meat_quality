#!/usr/bin/env python3
"""
Test script to verify camera functionality
Tests both V4L2 and Pi Camera V2.1
"""

import os
import sys
import time
from datetime import datetime
import cv2
import subprocess

# Create images directory
images_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "images")
os.makedirs(images_dir, exist_ok=True)

print("=" * 60)
print("Camera Test Script")
print("=" * 60)

# Test 1: Check if rpicam-still is available
print("\n[1] Checking rpicam-still availability...")
result = subprocess.run(["which", "rpicam-still"], capture_output=True, text=True)
if result.returncode == 0:
    print(f"✓ rpicam-still found at: {result.stdout.strip()}")
else:
    print("✗ rpicam-still not found")

# Test 2: Check video devices
print("\n[2] Checking available video devices...")
video_devices = []
for i in range(10):
    dev_path = f"/dev/video{i}"
    if os.path.exists(dev_path):
        video_devices.append(dev_path)
        print(f"✓ Found: {dev_path}")

if not video_devices:
    print("✗ No video devices found")

# Test 3: Test rpicam-still capture
print("\n[3] Testing rpicam-still capture...")
timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
rpicam_output = os.path.join(images_dir, f"rpicam_test_{timestamp}.jpg")

try:
    cmd = [
        "rpicam-still",
        "-t", "5000",
        "-o", rpicam_output,
        "--nopreview"
    ]
    print(f"Running: {' '.join(cmd)}")
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
    
    if result.returncode == 0 and os.path.exists(rpicam_output):
        file_size = os.path.getsize(rpicam_output)
        print(f"✓ rpicam-still capture successful!")
        print(f"  Output: {rpicam_output}")
        print(f"  Size: {file_size} bytes")
        
        # Try to read with OpenCV to verify
        img = cv2.imread(rpicam_output)
        if img is not None:
            print(f"  Dimensions: {img.shape[1]}x{img.shape[0]}")
        else:
            print(f"  ✗ Failed to read image with OpenCV")
    else:
        print(f"✗ rpicam-still capture failed")
        print(f"  Return code: {result.returncode}")
        if result.stderr:
            print(f"  Error: {result.stderr}")
except subprocess.TimeoutExpired:
    print("✗ rpicam-still capture timed out")
except Exception as e:
    print(f"✗ rpicam-still capture error: {e}")

# Test 4: Test V4L2 capture with OpenCV
print("\n[4] Testing V4L2 capture with OpenCV...")
for i in range(min(3, len(video_devices))):
    print(f"\n  Testing {video_devices[i]}...")
    try:
        cap = cv2.VideoCapture(i)
        if cap.isOpened():
            ret, frame = cap.read()
            if ret and frame is not None:
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                v4l2_output = os.path.join(images_dir, f"v4l2_test_{i}_{timestamp}.jpg")
                cv2.imwrite(v4l2_output, frame)
                file_size = os.path.getsize(v4l2_output)
                print(f"  ✓ V4L2 capture successful!")
                print(f"    Output: {v4l2_output}")
                print(f"    Size: {file_size} bytes")
                print(f"    Dimensions: {frame.shape[1]}x{frame.shape[0]}")
            else:
                print(f"  ✗ Failed to read frame")
            cap.release()
        else:
            print(f"  ✗ Failed to open camera")
    except Exception as e:
        print(f"  ✗ Error: {e}")

# Test 5: Check libcamera devices
print("\n[5] Checking libcamera devices...")
try:
    result = subprocess.run(["libcamera-hello", "--list-cameras"], capture_output=True, text=True, timeout=5)
    if result.returncode == 0:
        print("✓ libcamera-hello output:")
        for line in result.stdout.split('\n'):
            if line.strip():
                print(f"  {line}")
    else:
        print("libcamera-hello not available or failed")
except FileNotFoundError:
    print("libcamera-hello not found")
except Exception as e:
    print(f"Error running libcamera-hello: {e}")

print("\n" + "=" * 60)
print("Test completed!")
print(f"Images saved to: {images_dir}")
print("=" * 60)
