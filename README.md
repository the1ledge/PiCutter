# PiCutter - Raspberry Pi GRBL CNC Controller

PiCutter is a lightweight, touch-friendly CNC control software designed for the Raspberry Pi (optimized for Pi 3B/4) and 7-inch touchscreens (800x480 resolution). It interfaces with GRBL controllers via USB to provide a robust machine control interface.

## Features

*   **Touch-Optimized UI:** Large buttons and clean layout designed for 800x480 screens.
*   **Robust Streaming:** "Ping-Pong" protocol with auto-retry for transient transmission errors.
*   **Camera Support:** Integrated support for Raspberry Pi Camera (libcamera/picamera2) and USB Webcams.
*   **Smart Resume:** Resume jobs from any line with automatic state restoration (Modes, Spindle, Work Offsets).
*   **Advanced Probing:** Built-in macros for Z-Probe and 3-Axis Corner Finding.
*   **Visual G-Code Check:** Pre-flight checker to identify potential errors before running a job.

## Hardware Requirements

*   **Raspberry Pi:** Model 3B or 4 is recommended.
*   **Display:** 7-inch Touchscreen (Official Raspberry Pi Display or HDMI equivalent) with 800x480 resolution.
*   **Controller:** GRBL 1.1f or later compatible CNC controller (Arduino/Atmega328p based).
*   **Camera (Optional):** Raspberry Pi Camera Module v2/v3 or standard USB Webcam.

## Software Requirements

*   **OS:** Raspberry Pi OS (Legacy/Buster or Bullseye/Bookworm) - **32-bit recommended for compatibility**.
*   **Python:** Python 3.7+

## Installation

1.  **Update System:**
    ```bash
    sudo apt update
    sudo apt upgrade
    ```

2.  **Install System Dependencies:**
    You need PyQt5, libcamera support, and other utilities.
    ```bash
    sudo apt install python3-pyqt5 python3-pyqt5.qtquick python3-serial python3-opencv libcamera-tools
    ```
    *(Note: If you are on a very new OS version, you might need to use a virtual environment or `pip` with `--break-system-packages`, but installing via `apt` is preferred for stability on Pi.)*

3.  **Install Python Libraries:**
    If not installed via apt:
    ```bash
    pip3 install pyserial opencv-python-headless
    ```

4.  **Clone the Repository:**
    ```bash
    git clone https://github.com/YourUsername/PiCutter.git
    cd PiCutter
    ```

## Usage

1.  **Start the Application:**
    Run the main script from the terminal or create a desktop shortcut.
    ```bash
    python3 src/main.py
    ```

2.  **Headless / Remote Mode (Optional):**
    If running without a display for testing:
    ```bash
    QT_QPA_PLATFORM=offscreen python3 src/main.py
    ```

## Troubleshooting

*   **"Slow cam update" Warnings:** The application automatically throttles the camera to 15FPS to save CPU on the Pi 3B. If sluggishness persists, try disabling the camera in Settings.
*   **Connection Issues:** Use the "View System Log" button in Settings to check `dmesg` for USB cable faults or EMI disconnects.
*   **Controller Reset:** If the job stops with "Controller Reset Detected", it indicates strong electrical noise (EMI) triggered the controller's reset pin. Check your wiring, shielding, and USB cable quality.

## License

[MIT License](LICENSE)
