# PiCutter - Raspberry Pi GRBL CNC Controller

PiCutter is a lightweight, touch-friendly CNC control software designed for the Raspberry Pi (optimized for Pi 3B/4) and 7-inch touchscreens (800x480 resolution). It interfaces with GRBL controllers via USB to provide a robust machine control interface.

## Features

*   **Touch-Optimized UI:** Large buttons and clean layout designed for 800x480 screens.
*   **Robust Flow Control:** Advanced character-counting streaming with "Smart Recovery" for transient errors (EMI/Noise).
*   **Camera Support:** Integrated support for Raspberry Pi Camera (libcamera/picamera2) and USB Webcams.
*   **Smart Resume:** Resume jobs from any line with automatic state restoration (Motion Modes, Spindle Speed, Work Offsets, Coolant).
*   **Advanced Probing:** Built-in macros for Z-Probe and 3-Axis Corner Finding.
*   **G-Code Checker:** Pre-flight checker (`$C` Check Mode integration) to identify potential errors before running a job.
*   **Auto-Retry:** Automatically detects transient transmission errors (e.g., "Bad Arc", "Expected Command") and retries the command sequence without ruining the part.

## Hardware Requirements

*   **Raspberry Pi:** Model 3B or 4 is recommended.
*   **Display:** 7-inch Touchscreen (Official Raspberry Pi Display or HDMI equivalent) with 800x480 resolution.
*   **Controller:** GRBL 1.1f or later compatible CNC controller (Arduino/Atmega328p based).
*   **Camera (Optional):** Raspberry Pi Camera Module v2/v3 or standard USB Webcam.

## Software Requirements

*   **OS:** Raspberry Pi OS (Legacy/Buster or Bullseye/Bookworm/Trixie) - **32-bit recommended**.
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

3.  **Permissions:**
    Ensure your user (usually `pi` or `cncpi`) has permission to access the serial port (dialout) and video devices.
    ```bash
    sudo usermod -a -G dialout,video $USER
    ```
    *Log out and back in for changes to take effect.*

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

## Troubleshooting Common Issues

### "Error 9: G-code Lockout"
This error occurs when the machine has been in an Alarm state (e.g., after a Limit Switch hit or Soft Reset) and has not fully unlocked before receiving new commands.
*   **Solution:** The software now includes an extended delay (3 seconds) during recovery to ensure the `$X` (Unlock) command is fully processed. If this persists, manually press "Unlock" before starting.

### "Bad Arc" or "Illegal Target" Errors (EMI/Noise)
If your G-code file passes "Check Mode" but fails during a cut with random errors like `error:33` (Bad Arc) or `error:1` (Expected Word), you likely have electrical noise (EMI) corrupting the USB data stream.
*   **Software Fix:** PiCutter's **Auto-Retry** feature will attempt to detect these specific errors, perform a Soft Reset (`\x18`) to clear the corrupted buffer, and resume cutting automatically.
*   **Hardware Fixes:**
    *   Use a high-quality **Shielded USB Cable** with ferrite beads.
    *   Install **Ferrite Cores** on your spindle cable and stepper motor cables.
    *   Separate your USB cable from high-voltage cables (Spindle/VFD).
    *   Ensure your machine frame and controller are properly **Grounded**.

### "Slow cam update"
The application throttles the camera to 15FPS to save CPU on the Pi 3B. If the interface becomes sluggish, disable the camera in the 'Settings' tab.

### Connection Issues
Use the "View System Log" button in the Settings tab to check `dmesg`.
*   **`usb 1-1: device descriptor read/64, error -71`**: This confirms serious EMI interference disconnecting the USB device.

## License

[MIT License](LICENSE)
