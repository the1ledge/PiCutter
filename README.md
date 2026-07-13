# PiCutter

PiCutter is a modern, lightweight PyQt5-based CNC controller specifically optimized for the Raspberry Pi 3B+ and GRBL-based CNC machines. It features a responsive UI, real-time DRO, visual G-code parsing, and an advanced 3-axis automated probing cycle.

## Interface

*(Add screenshots here by placing images in an `images/` folder)*

![Main Interface](images/main_ui.png)
*PiCutter Main Dashboard*

![Probe Cycle](images/probe_ui.png)
*Automated 3-Axis Probing UI*

## Features
* **Optimized for Raspberry Pi 3B+**: Camera frame rates and serial buffers are explicitly tuned to keep the Pi's CPU usage low so your CNC never stutters.
* **Advanced 3-Axis Zeroing**: Fully automated Z, X, and Y touch probe macro with customizable clearances and tool radius dropdowns.
* **Ping-Pong Serial Flow**: Bulletproof G-code streaming that ensures every line is perfectly acknowledged by GRBL before the next is sent.
* **Dual Camera Support**: Supports both standard USB Webcams and the official Raspberry Pi Camera module (via `picamera2`).
* **Log Rotation**: Automatic session log rotation keeps your SD card healthy and your log files manageable.

## Raspberry Pi 3B+ Installation Guide

We highly recommend installing PyQt5 and OpenCV via the `apt` package manager on the Raspberry Pi rather than `pip`, as compiling these massive libraries from source on a 3B+ can take hours.

### 1. Update your system
```bash
sudo apt update
sudo apt upgrade -y
```

### 2. Install System Dependencies
Install PyQt5, OpenCV, and Git:
```bash
sudo apt install python3-pyqt5 python3-opencv python3-pip git -y
```

*(Note: If you plan to use the official Pi Camera, make sure `picamera2` and its dependencies are also installed via your Raspberry Pi OS).*

### 3. Install Python Dependencies
Install the required python libraries (like `pyserial` for GRBL communication):
```bash
pip3 install pyserial
```
*(Note: If you are using Raspberry Pi OS Bookworm or newer, you may need to add the `--break-system-packages` flag, or use a python virtual environment: `pip3 install pyserial --break-system-packages`)*

### 4. Clone the Repository
```bash
git clone https://github.com/the1ledge/PiCutter.git
cd PiCutter
```

### 5. Launch PiCutter
```bash
python3 src/main.py
```

## GRBL Configuration Notes
* Ensure your GRBL soft limits (`$20=1`) are configured correctly. PiCutter's automated probing macros rely on accurate machine boundaries to prevent crashes.
* The default baud rate is `115200`.
