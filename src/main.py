# v0.16.8
import sys
import os

# Minimal Qt imports to create an early splash immediately
from PySide2.QtCore import Qt, QTimer
from PySide2.QtWidgets import QApplication, QSplashScreen
from PySide2.QtGui import QPixmap, QPainter, QColor, QFont

# Create QApplication early so the splash can appear before heavier imports
app = QApplication(sys.argv)
app.setStyle("Fusion")

# Prepare paths and an initial lightweight base pixmap to reveal.
logo_path = os.path.join(os.path.dirname(__file__), "assets", "logo.png")
# splash_base_pix is the pixmap that will be progressively revealed by the carving animation.
# Start with a compact generated base so the splash shows immediately; defer loading the real logo.
splash_base_pix = QPixmap(320, 200)
splash_base_pix.fill(QColor('#2E3440'))
_tmp_p = QPainter(splash_base_pix)
_font = QFont()
_font.setPointSize(16)
_font.setBold(True)
_tmp_p.setFont(_font)
_tmp_p.setPen(QColor('white'))
_tmp_p.drawText(splash_base_pix.rect(), Qt.AlignCenter, "PiGRBL CNC Controller\nLoading...")
_tmp_p.end()

# Defer heavy logo load/scale to a short single-shot timer so the splash shows immediately
def _load_real_logo():
    global splash_base_pix
    try:
        if os.path.exists(logo_path):
            pm = QPixmap(logo_path)
            if not pm.isNull():
                splash_base_pix = pm.scaled(320, 200, Qt.KeepAspectRatio, Qt.SmoothTransformation)
    except Exception:
        # ignore and keep fallback
        pass


# Use the prepared base pixmap for the initial splash instance
splash = QSplashScreen(splash_base_pix, Qt.WindowStaysOnTopHint)
# Initially show the pixmap fully covered so the carving animation reveals it
_initial_pm = QPixmap(splash_base_pix)
init_painter = QPainter(_initial_pm)
init_painter.fillRect(0, 0, _initial_pm.width(), _initial_pm.height(), QColor('white'))
init_painter.end()
splash.setPixmap(_initial_pm)
splash.showMessage("Starting... 0%", Qt.AlignBottom | Qt.AlignLeft, Qt.black)
splash.show()
app.processEvents()

# Carving animation state for the splash: reveal the logo from top->bottom
_splash_carve_progress = 0.0  # 0.0 = fully covered, 1.0 = fully revealed
_splash_carve_timer = QTimer()
_splash_reveal_done = False
_splash_finish_pending = None

def _request_finish_after_reveal(window):
    """Request that the splash be finished and the main window shown.
    If the 100% reveal wait has already completed, finish immediately. Otherwise queue the
    window and it will be shown after the reveal wait timer fires.
    """
    global _splash_reveal_done, _splash_finish_pending
    if _splash_reveal_done:
        splash.finish(window)
        window.show()
    else:
        # store the pending window; when the reveal wait completes it will be shown
        _splash_finish_pending = window

def _splash_carve_step():
    """Advance the carving progress and repaint the splash.
    Draw a white rectangle covering the remaining (1-progress) top portion of the pixmap.
    """
    global _splash_carve_progress
    # advance progress smoothly
    _splash_carve_progress = min(1.0, _splash_carve_progress + 0.02)
    # create an overlayed pixmap to draw the cover
    base = splash_base_pix
    pm = QPixmap(base)
    painter = QPainter(pm)
    painter.setCompositionMode(QPainter.CompositionMode_SourceOver)
    cover_height = int(pm.height() * (1.0 - _splash_carve_progress))
    if cover_height > 0:
        painter.fillRect(0, 0, pm.width(), cover_height, QColor('white'))
    painter.end()
    splash.setPixmap(pm)
    # make sure any messages are still visible
    splash.showMessage(f"Starting... {int(_splash_carve_progress*100)}%", Qt.AlignBottom | Qt.AlignLeft, Qt.black)
    app.processEvents()
    if _splash_carve_progress >= 1.0:
        _splash_carve_timer.stop()
        # start a 1 second wait at 100% so the user can see the fully revealed logo
        def _reveal_done():
            global _splash_reveal_done, _splash_finish_pending
            _splash_reveal_done = True
            if _splash_finish_pending:
                try:
                    splash.finish(_splash_finish_pending)
                    _splash_finish_pending.show()
                finally:
                    _splash_finish_pending = None

        QTimer.singleShot(1000, _reveal_done)

# Start the carving timer with a short interval to show progress while startup work runs
_splash_carve_timer.setInterval(40)
_splash_carve_timer.timeout.connect(_splash_carve_step)
_splash_carve_timer.start()

# Schedule loading the real logo shortly after the splash so it doesn't delay initial display
QTimer.singleShot(80, _load_real_logo)

# Now import heavier modules and the rest of the PySide2 widgets
import serial.tools.list_ports
import re
import time
import cv2
import math
import numpy as np
from PySide2.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QComboBox, QPushButton, QLabel, QGroupBox, QGridLayout, QProgressBar, QFileDialog, QTextEdit, QLineEdit, QTabWidget, QMessageBox, QFormLayout, QCheckBox, QDialog, QDialogButtonBox, QScrollArea, QToolTip, QTableWidget, QTableWidgetItem, QAbstractItemView, QHeaderView, QSizePolicy
)
from PySide2.QtCore import QThread, QObject, Signal, QSettings, QEvent, Slot
from PySide2.QtGui import QTextCursor, QImage

class CameraWorker(QThread):
    frame_ready = Signal(QImage)
    camera_error = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._is_running = True
        self.picam2 = None

    def run(self):
        try:
            from picamera2 import Picamera2
            self.picam2 = Picamera2()
            config = self.picam2.create_preview_configuration(main={"format": "RGB888"})
            self.picam2.configure(config)
            self.picam2.start()
        except Exception as e:
            self.camera_error.emit(f"Error: Failed to initialize Picamera2: {e}")
            return
        time.sleep(1.0)
        while self._is_running:
            rgb_array = self.picam2.capture_array()
            if rgb_array is not None:
                h, w, ch = rgb_array.shape
                bytes_per_line = ch * w
                qt_image = QImage(rgb_array.data, w, h, bytes_per_line, QImage.Format_RGB888)
                self.frame_ready.emit(qt_image.copy())
            time.sleep(1/60)
        if self.picam2:
            self.picam2.stop()

    def stop(self):
        self._is_running = False
        self.wait()

class ProbeVerifyDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Verify Probe")
        self.setModal(True)
        self.is_verified = False
        layout = QVBoxLayout(self)
        info_label = QLabel("Touch the probe to the contact plate.\nThe indicator should turn green.\nThen lift the probe to continue.")
        info_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(info_label)
        self.indicator = QLabel("Probe Not Detected")
        self.indicator.setAlignment(Qt.AlignCenter)
        self.indicator.setStyleSheet("background-color: #F44336; color: white; font-weight: bold; padding: 10px; border-radius: 5px;")
        layout.addWidget(self.indicator)
        self.button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        self.ok_button = self.button_box.button(QDialogButtonBox.Ok)
        self.ok_button.setText("Continue")
        self.ok_button.setEnabled(False)
        self.button_box.accepted.connect(self.accept)
        self.button_box.rejected.connect(self.reject)
        self.e_stop_button = QPushButton("EMERGENCY STOP\n(Reset)")
        self.e_stop_button.setStyleSheet("background-color: red; color: white; font-weight: bold;")
        self.e_stop_button.setFixedHeight(40)
        button_layout = QHBoxLayout()
        button_layout.addWidget(self.e_stop_button)
        button_layout.addWidget(self.button_box)
        layout.addLayout(button_layout)

    def update_probe_status(self, is_triggered):
        if is_triggered:
            self.is_verified = True
            self.indicator.setText("Probe Connection Verified")
            self.indicator.setStyleSheet("background-color: #4CAF50; color: white; font-weight: bold; padding: 10px; border-radius: 5px;")
        else:
            self.indicator.setText("Probe Not Detected")
            self.indicator.setStyleSheet("background-color: #F44336; color: white; font-weight: bold; padding: 10px; border-radius: 5px;")
        self.ok_button.setEnabled(self.is_verified and not is_triggered)

class ProbeArmDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Verify Tool and Plate")
        self.setModal(True)
        self.is_verified = False
        layout = QVBoxLayout(self)
        instructions = ("1. Attach the probe lead to the cutting bit.\n"
                        "2. Touch the bit to the contact plate to verify.\n"
                        "3. Lift the probe. The button will enable.")
        info_label = QLabel(instructions)
        info_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(info_label)
        self.indicator = QLabel("Probe Not Detected")
        self.indicator.setAlignment(Qt.AlignCenter)
        self.indicator.setStyleSheet("background-color: #F44336; color: white; font-weight: bold; padding: 10px; border-radius: 5px;")
        layout.addWidget(self.indicator)
        self.button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        self.ok_button = self.button_box.button(QDialogButtonBox.Ok)
        self.ok_button.setText("Ready to Probe")
        self.ok_button.setEnabled(False)
        self.button_box.accepted.connect(self.accept)
        self.button_box.rejected.connect(self.reject)
        self.e_stop_button = QPushButton("EMERGENCY STOP\n(Reset)")
        self.e_stop_button.setStyleSheet("background-color: red; color: white; font-weight: bold;")
        self.e_stop_button.setFixedHeight(40)
        button_layout = QHBoxLayout()
        button_layout.addWidget(self.e_stop_button)
        button_layout.addWidget(self.button_box)
        layout.addLayout(button_layout)

    def update_probe_status(self, is_triggered):
        if is_triggered:
            self.is_verified = True
            self.indicator.setText("Tool Connection Verified")
            self.indicator.setStyleSheet("background-color: #4CAF50; color: white; font-weight: bold; padding: 10px; border-radius: 5px;")
        else:
            self.indicator.setText("Probe Not Detected")
            self.indicator.setStyleSheet("background-color: #F44336; color: white; font-weight: bold; padding: 10px; border-radius: 5px;")
        self.ok_button.setEnabled(self.is_verified and not is_triggered)

class LocationDialog(QDialog):
    def __init__(self, parent, title, locations, prompt):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setModal(True)
        self.selected_index = -1
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel(prompt))
        self.location_combo = QComboBox()
        self.location_combo.addItems(locations)
        layout.addWidget(self.location_combo)
        button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)

    def accept(self):
        self.selected_index = self.location_combo.currentIndex()
        super().accept()

    @staticmethod
    def get_selected_index(parent, title, locations, prompt):
        dialog = LocationDialog(parent, title, locations, prompt)
        return dialog.selected_index if dialog.exec_() == QDialog.Accepted else -1

class NumberPadDialog(QDialog):
    def __init__(self, initial_value="", parent=None):
        super().__init__(parent)
        self.setWindowTitle("Number Pad")
        self.setModal(True)
        layout = QGridLayout(self)
        self.display = QLineEdit(initial_value)
        self.display.setReadOnly(True)
        self.display.setAlignment(Qt.AlignRight)
        layout.addWidget(self.display, 0, 0, 1, 4)
        button_map = {'7':(1,0),'8':(1,1),'9':(1,2),'4':(2,0),'5':(2,1),'6':(2,2),'1':(3,0),'2':(3,1),'3':(3,2),'0':(4,0),'.':(4,1),'Backspace':(1,3),'Clear':(2,3),'Enter':(3,3),'Cancel':(4,3)}
        for text, pos in button_map.items():
            button = QPushButton(text)
            if text.isdigit() or text=='.': button.clicked.connect(self.on_digit_pressed)
            elif text=='Backspace': button.clicked.connect(self.on_backspace_pressed)
            elif text=='Clear': button.clicked.connect(self.on_clear_pressed)
            elif text=='Enter': button.clicked.connect(self.accept)
            elif text=='Cancel': button.clicked.connect(self.reject)
            layout.addWidget(button, pos[0], pos[1])

    def on_digit_pressed(self):
        button = self.sender()
        if button.text() == '.' and '.' in self.display.text(): return
        self.display.setText(self.display.text() + button.text())

    def on_backspace_pressed(self): self.display.setText(self.display.text()[:-1])
    def on_clear_pressed(self): self.display.clear()
    def get_value(self): return self.display.text()

class SerialWorker(QObject):
    serial_data_received = Signal(str)
    def __init__(self, serial_connection):
        super().__init__()
        self.serial_connection = serial_connection
        self._is_running = True
    def run(self):
        while self._is_running:
            if self.serial_connection and self.serial_connection.is_open:
                try:
                    line = self.serial_connection.readline().decode('utf-8').strip()
                    if line: self.serial_data_received.emit(line)
                except serial.SerialException: break
    def stop(self): self._is_running = False

class MainWindow(QMainWindow):
    grbl_setting_received = Signal(str, str)
    probe_status_changed = Signal(bool)
    gcode_line_sent = Signal(int)
    gcode_line_executed = Signal(int)
    gcode_job_error = Signal(str)

    def __init__(self, splash=None):
        super().__init__()
        self.splash = splash
        if self.splash:
            self.splash.showMessage("Initializing...", Qt.AlignBottom | Qt.AlignLeft, Qt.white)
            QApplication.processEvents()
        self.alarm_codes = {1:"Hard limit.",2:"Soft limit.",3:"Reset in motion.",4:"Probe fail (initial).",5:"Probe fail (no contact).",6:"Homing fail (reset).",7:"Homing fail (door).",8:"Homing fail (pull-off).",9:"Homing fail (no switch).",15:"Jog exceeds travel."}

        # --- THIS IS THE CORRECTED, COMPLETE DICTIONARY ---
        self.GRBL_SETTINGS_INFO = {
            "$0": {"label": "Step pulse time (μs)", "tooltip": "Sets the step pulse duration. A value around 10 microseconds is recommended."},
            "$1": {"label": "Step idle delay (ms)", "tooltip": "Delays disabling steppers after a motion. Set to 255 to keep steppers always enabled."},
            "$2": {"label": "Step port invert (mask)", "tooltip": "Inverts the step pulse signal. Useful for certain stepper drivers."},
            "$3": {"label": "Direction port invert (mask)", "tooltip": "Inverts the direction signal for each axis."},
            "$4": {"label": "Step enable invert (boolean)", "tooltip": "Inverts the stepper enable pin. High to disable, low to enable. $4=1 to invert."},
            "$5": {"label": "Limit pins invert (boolean)", "tooltip": "Inverts the limit pins. Requires external pull-down resistors if inverted."},
            "$6": {"label": "Probe pin invert (boolean)", "tooltip": "Inverts the probe pin. Requires an external pull-down resistor if inverted."},
            "$10": {"label": "Status report (mask)", "tooltip": "Determines what real-time data Grbl reports back. Default is $10=1 (MPos and no buffer data)."},
            "$11": {"label": "Junction deviation (mm)", "tooltip": "Controls how fast the machine moves through corners. Lower values are slower and safer."},
            "$12": {"label": "Arc tolerance (mm)", "tooltip": "Defines the accuracy of G2/G3 arcs. Default (0.002mm) is usually sufficient."},
            "$13": {"label": "Report inches (boolean)", "tooltip": "When enabled ($13=1), Grbl reports positions in inches, not mm."},
            "$20": {"label": "Soft limits (boolean)", "tooltip": "Prevents the machine from exceeding travel limits. Requires homing and max travel settings."},
            "$21": {"label": "Hard limits (boolean)", "tooltip": "Uses physical switches to prevent exceeding travel limits. Requires normally-open switches."},
            "$22": {"label": "Homing cycle (boolean)", "tooltip": "Enables homing ($H). Locks G-code commands until homing is performed."},
            "$23": {"label": "Homing dir invert (mask)", "tooltip": "Inverts the homing direction for axes with limit switches in the negative direction."},
            "$24": {"label": "Homing feed (mm/min)", "tooltip": "The slower feed rate used to precisely locate machine zero during homing."},
            "$25": {"label": "Homing seek (mm/min)", "tooltip": "The faster seek rate used to find the limit switches during homing."},
            "$26": {"label": "Homing debounce (ms)", "tooltip": "A short delay to handle electrical/mechanical noise on limit switches. 5-25ms is typical."},
            "$27": {"label": "Homing pull-off (mm)", "tooltip": "Distance to move off limit switches after homing to prevent accidental triggering."},
            "$30": {"label": "Max spindle speed (RPM)", "tooltip": "Sets the spindle speed for the maximum 5V PWM pin output."},
            "$31": {"label": "Min spindle speed (RPM)", "tooltip": "Sets the spindle speed for the minimum PWM pin output (0.02V). 0 RPM disables the spindle."},
            "$32": {"label": "Laser mode (boolean)", "tooltip": "Enables continuous motion for laser engraving. Use with caution."},
            "$100": {"label": "X-axis steps/mm", "tooltip": "Number of steps required to move the X-axis by 1mm."},
            "$101": {"label": "Y-axis steps/mm", "tooltip": "Number of steps required to move the Y-axis by 1mm."},
            "$102": {"label": "Z-axis steps/mm", "tooltip": "Number of steps required to move the Z-axis by 1mm."},
            "$110": {"label": "X-axis max rate (mm/min)", "tooltip": "Maximum rate the X-axis can move. Also sets G0 seek rate."},
            "$111": {"label": "Y-axis max rate (mm/min)", "tooltip": "Maximum rate the Y-axis can move. Also sets G0 seek rate."},
            "$112": {"label": "Z-axis max rate (mm/min)", "tooltip": "Maximum rate the Z-axis can move. Also sets G0 seek rate."},
            "$120": {"label": "X-axis acceleration (mm/sec^2)", "tooltip": "Acceleration for the X-axis. Lower values are gentler."},
            "$121": {"label": "Y-axis acceleration (mm/sec^2)", "tooltip": "Acceleration for the Y-axis. Lower values are gentler."},
            "$122": {"label": "Z-axis acceleration (mm/sec^2)", "tooltip": "Acceleration for the Z-axis. Lower values are gentler."},
            "$130": {"label": "X-axis max travel (mm)", "tooltip": "Maximum travel for the X-axis. Used for soft limits."},
            "$131": {"label": "Y-axis max travel (mm)", "tooltip": "Maximum travel for the Y-axis. Used for soft limits."},
            "$132": {"label": "Z-axis max travel (mm)", "tooltip": "Maximum travel for the Z-axis. Used for soft limits."}
        }

        self.setWindowTitle("PiGRBL CNC Controller")
        self.resize(800, 480)
        QApplication.setStyle("Fusion")
        QApplication.instance().setStyleSheet("QToolTip { color: #000000; background-color: #ffffff; border: 1px solid black; }")
        self.settings = QSettings("MyCompany", "PiGRBLCNC")
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)
        top_bar_layout = QHBoxLayout()
        self.e_stop_button = QPushButton("EMERGENCY STOP\n(Reset)")
        self.e_stop_button.setStyleSheet("background-color: red; color: white; font-weight: bold;")
        self.e_stop_button.setFixedHeight(40)
        top_bar_layout.addWidget(self.e_stop_button)
        self.unlock_button = QPushButton("Unlock ($X)")
        self.unlock_button.setFixedHeight(40)
        top_bar_layout.addWidget(self.unlock_button)
        top_bar_layout.addStretch()
        self.connect_button = QPushButton("Connect")
        self.connection_status_indicator = QPushButton("Disconnected")
        self.connection_status_indicator.setCheckable(False)
        self.connection_status_indicator.setEnabled(False)
        system_buttons_layout = QGridLayout()
        self.exit_button = QPushButton("Exit Application")
        self.shutdown_button = QPushButton("Shutdown Pi")
        system_buttons_layout.addWidget(self.connect_button, 0, 0)
        system_buttons_layout.addWidget(self.exit_button, 0, 1)
        system_buttons_layout.addWidget(self.connection_status_indicator, 1, 0)
        system_buttons_layout.addWidget(self.shutdown_button, 1, 1)
        top_bar_layout.addLayout(system_buttons_layout)
        main_layout.addLayout(top_bar_layout)
        self.tabs = QTabWidget()
        main_layout.addWidget(self.tabs)
        self.numpad_enabled_fields = []
        if self.splash:
            self.splash.showMessage("Building UI components...", Qt.AlignBottom | Qt.AlignLeft, Qt.white)
            QApplication.processEvents()
        self.build_manual_control_tab()
        self.build_gcode_tab()
        self.build_console_tab()
        self.build_settings_tab()
        if self.splash:
            self.splash.showMessage("Connecting signals...", Qt.AlignBottom | Qt.AlignLeft, Qt.white)
            QApplication.processEvents()
        self.connect_signals()
        self.serial_connection = None
        self.serial_thread = None
        self.serial_worker = None
        self.gcode_lines = []
        self.gcode_current_line = 0
        self.gcode_is_running = False
        self.gcode_is_paused = False
        self.machine_state = "Unknown"
        self.current_alarm_code = None
        self.last_jog_button = None
        self.is_homed = False
        self.is_manually_zeroed = False
        self.z_is_auto_zeroed = False
        self.is_probing = False
        self.probe_succeeded = False
        self.last_probe_state = False
        self.is_advanced_probing = False
        self.is_parking = False
        self.parking_command_queue = []
        self.xyz_probe_stage = None
        self.probe_command_queue = []
        self.probe_results = []
        self.probe_response_count = 0
        self.probe_phase = None
        self.wco_x, self.wco_y, self.wco_z = 0.0, 0.0, 0.0
        self.mpos_x, self.mpos_y, self.mpos_z = 0.0, 0.0, 0.0
        self.grbl_settings_count = 0
        self.gcode_start_time = None
        self.gcode_estimated_time = 0
        self.gcode_line_times = []
        self.command_pending = False
        self.planner_buffer_blocks = 0
        self.rx_buffer_bytes = 0
        self.dro_timer = QTimer(self)
        self.dro_timer.setInterval(100) # Faster timer for smoother streaming
        self.dro_timer.timeout.connect(self.request_status_and_send_next)
        self.home_pulse_timer = QTimer(self)
        self.home_pulse_timer.setInterval(500)
        self.home_pulse_timer.timeout.connect(self.pulse_home_button)
        self.home_pulse_state = 0
        self.alarm_pulse_timer = QTimer(self)
        self.alarm_pulse_timer.setInterval(500)
        self.alarm_pulse_timer.timeout.connect(self.pulse_alarm_button)
        self.alarm_pulse_state = 0
        self.populate_ports()
        self.update_connection_indicator(False)
        self.update_ui_states()
        self.camera_thread = None
        self.camera_worker = None
        if self.splash:
            self.splash.showMessage("Initializing camera...", Qt.AlignBottom | Qt.AlignLeft, Qt.white)
            QApplication.processEvents()
        self.start_camera()
        if self.splash:
            self.splash.showMessage("Ready.", Qt.AlignBottom | Qt.AlignLeft, Qt.white)
            QApplication.processEvents()
            time.sleep(1)

    def build_manual_control_tab(self):
        manual_tab = QWidget()
        self.tabs.addTab(manual_tab, "Manual Control")
        main_layout = QHBoxLayout(manual_tab)
        self.home_button = QPushButton("Home ($H)")
        self.run_probe_button = QPushButton("Auto Zero Z")
        self.run_3axis_probe_button = QPushButton("3-Axis\nAuto Zero")
        self.set_location_button = QPushButton("Set Location")
        self.go_to_location_button = QPushButton("Go To Location")
        self.spindle_on_button, self.spindle_off_button = QPushButton("On (M3)"), QPushButton("Off (M5)")
        left_column_layout = QVBoxLayout()
        left_column_layout.setAlignment(Qt.AlignTop)
        spindle_group = QGroupBox()
        spindle_layout = QFormLayout()
        self.spindle_speed_input = QLineEdit("1000")
        self.numpad_enabled_fields.append(self.spindle_speed_input)
        self.spindle_speed_input.installEventFilter(self)
        spindle_layout.addRow("Spindle Speed (RPM):", self.spindle_speed_input)
        spindle_layout.addRow(self.spindle_on_button, self.spindle_off_button)
        spindle_group.setLayout(spindle_layout)
        left_column_layout.addWidget(spindle_group)
        video_group = QGroupBox()
        video_layout = QVBoxLayout()
        self.video_label = QLabel("Initializing Camera...")
        self.video_label.setAlignment(Qt.AlignCenter)
        self.video_label.setStyleSheet("border: 1px solid black; background-color: #333; color: white;")
        self.video_label.setMinimumSize(320, 240)
        self.video_label.setMaximumSize(640, 480)
        self.video_label.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        self.video_label.setScaledContents(False)
        video_layout.addWidget(self.video_label)
        video_group.setLayout(video_layout)
        left_column_layout.addWidget(video_group)
        left_column_layout.addStretch(1)
        main_layout.addLayout(left_column_layout)
        middle_column_layout = QVBoxLayout()
        middle_column_layout.setAlignment(Qt.AlignTop)
        dro_group = QGroupBox("Machine Pos")
        dro_layout = QFormLayout()
        self.x_pos_label, self.y_pos_label, self.z_pos_label = QLabel("0.000"), QLabel("0.000"), QLabel("0.000")
        dro_layout.addRow("X:", self.x_pos_label)
        dro_layout.addRow("Y:", self.y_pos_label)
        dro_layout.addRow("Z:", self.z_pos_label)
        dro_group.setLayout(dro_layout)
        middle_column_layout.addWidget(dro_group)
        wpos_dro_group = QGroupBox("Work Pos")
        wpos_dro_layout = QFormLayout()
        self.wpos_x_label, self.wpos_y_label, self.wpos_z_label = QLabel("0.000"), QLabel("0.000"), QLabel("0.000")
        wpos_dro_layout.addRow("X:", self.wpos_x_label)
        wpos_dro_layout.addRow("Y:", self.wpos_y_label)
        wpos_dro_layout.addRow("Z:", self.wpos_z_label)
        wpos_dro_group.setLayout(wpos_dro_layout)
        middle_column_layout.addWidget(wpos_dro_group)
        self.set_location_button.setFixedHeight(60)
        self.go_to_location_button.setFixedHeight(60)
        middle_column_layout.addWidget(self.set_location_button)
        middle_column_layout.addWidget(self.go_to_location_button)
        middle_column_layout.addStretch(1)
        main_layout.addLayout(middle_column_layout)
        right_column_layout = QVBoxLayout()
        jog_group = QGroupBox("Jogging")
        jog_layout = QGridLayout()
        jog_layout.setSpacing(0)
        jog_group.setLayout(jog_layout)
        jog_group.layout().setContentsMargins(10, 10, 10, 10)
        self.step_size_combo = QComboBox()
        self.step_size_combo.addItems(["0.1", "1", "10", "100"])
        self.step_size_combo.setMinimumWidth(40)
        self.step_size_combo.setMinimumHeight(40)
        self.y_plus_button, self.y_minus_button = QPushButton("Y+"), QPushButton("Y-")
        self.x_minus_button, self.x_plus_button = QPushButton("X-"), QPushButton("X+")
        self.z_plus_button, self.z_minus_button = QPushButton("Z+"), QPushButton("Z-")
        jog_buttons = [self.y_plus_button, self.y_minus_button, self.x_minus_button, self.x_plus_button, self.z_plus_button, self.z_minus_button]
        for button in jog_buttons:
            button.setMinimumSize(60, 60)
        step_control_layout = QVBoxLayout()
        step_control_layout.setSpacing(0)
        step_label = QLabel("Step")
        step_label.setAlignment(Qt.AlignCenter)
        step_control_layout.addWidget(step_label)
        step_control_layout.addWidget(self.step_size_combo)
        jog_layout.addWidget(self.x_minus_button, 2, 1)
        jog_layout.addWidget(self.x_plus_button, 2, 3)
        jog_layout.addLayout(step_control_layout, 2, 2)
        jog_layout.addWidget(self.y_minus_button, 3, 2)
        jog_layout.addWidget(self.y_plus_button, 1, 2)
        jog_layout.addWidget(self.z_plus_button, 1, 4)
        jog_layout.addWidget(self.z_minus_button, 3, 4)
        jog_layout.setColumnStretch(5, 1)
        jog_layout.setColumnStretch(0, 1)
        jog_layout.setRowStretch(5, 1)
        jog_layout.setRowStretch(0, 1)
        right_column_layout.addWidget(jog_group)
        actions_group = QGroupBox()
        actions_layout = QGridLayout()
        actions_group.setLayout(actions_layout)
        action_buttons = [self.home_button, self.run_probe_button, self.run_3axis_probe_button]
        for button in action_buttons:
            button.setMinimumSize(60, 60)
            button.setMaximumSize(80, 80)
        actions_layout.addWidget(self.home_button, 0, 0)
        actions_layout.addWidget(self.run_probe_button, 0, 1)
        actions_layout.addWidget(self.run_3axis_probe_button, 0, 2)
        right_column_layout.addWidget(actions_group)
        right_column_layout.addStretch(1)
        main_layout.addLayout(right_column_layout)

    def build_gcode_tab(self):
        gcode_tab = QWidget()
        self.tabs.addTab(gcode_tab, "G-Code Sender")
        main_gcode_layout = QHBoxLayout(gcode_tab)
        left_panel_layout = QVBoxLayout()
        gcode_group = QGroupBox()
        gcode_group_layout = QVBoxLayout()
        gcode_file_layout = QHBoxLayout()
        self.load_file_button = QPushButton("Load G-code")
        self.gcode_file_label = QLabel("No file loaded.")
        gcode_file_layout.addWidget(self.load_file_button)
        gcode_file_layout.addWidget(self.gcode_file_label, 1)
        self.gcode_progress = QProgressBar()
        gcode_actions_layout = QHBoxLayout()
        self.start_button, self.pause_button, self.stop_button = QPushButton("Start"), QPushButton("Pause"), QPushButton("Stop")
        gcode_actions_layout.addWidget(self.start_button)
        gcode_actions_layout.addWidget(self.pause_button)
        gcode_actions_layout.addWidget(self.stop_button)
        self.park_on_finish_checkbox = QCheckBox("Park on Finish")
        gcode_actions_layout.addWidget(self.park_on_finish_checkbox)
        gcode_actions_layout.addStretch()
        gcode_group_layout.addLayout(gcode_file_layout)
        gcode_group_layout.addLayout(gcode_actions_layout)
        gcode_group_layout.addWidget(self.gcode_progress)
        gcode_group.setLayout(gcode_group_layout)
        left_panel_layout.addWidget(gcode_group)
        self.gcode_table = QTableWidget()
        self.gcode_table.setColumnCount(3)
        self.gcode_table.setHorizontalHeaderLabels(["Line #", "Command", "Status"])
        self.gcode_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.gcode_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.gcode_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.gcode_table.setSelectionMode(QAbstractItemView.SingleSelection)
        left_panel_layout.addWidget(self.gcode_table)
        video_group = QGroupBox()
        video_layout = QVBoxLayout()
        self.gcode_video_label = QLabel("Initializing Camera...")
        self.gcode_video_label.setAlignment(Qt.AlignCenter)
        self.gcode_video_label.setStyleSheet("border: 1px solid black; background-color: #333; color: white;")
        # Use a fixed size for the G-Code tab video to prevent uncontrolled expansion on small screens
        self.gcode_video_label.setScaledContents(False)
        self.gcode_video_label.setFixedSize(320, 240)
        video_layout.addWidget(self.gcode_video_label)
        video_group.setLayout(video_layout)
        # Keep the video group narrow and give most horizontal space to the left panel
        video_group.setFixedWidth(340)
        video_group.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        main_gcode_layout.addLayout(left_panel_layout, 3)
        main_gcode_layout.addWidget(video_group, 0)

    def build_console_tab(self):
        console_tab = QWidget()
        console_layout = QVBoxLayout(console_tab)
        self.tabs.addTab(console_tab, "Console")
        input_layout = QHBoxLayout()
        self.command_input = QLineEdit()
        self.send_button = QPushButton("Send")
        self.filter_ok_checkbox = QCheckBox("Filter ok/?")
        self.filter_pos_checkbox = QCheckBox("Filter position")
        self.filter_ok_checkbox.setChecked(True)
        self.filter_pos_checkbox.setChecked(True)
        input_layout.addWidget(self.command_input, 1)
        input_layout.addWidget(self.send_button)
        input_layout.addWidget(self.filter_ok_checkbox)
        input_layout.addWidget(self.filter_pos_checkbox)
        input_layout.addStretch(1)
        console_layout.addLayout(input_layout)
        self.console_output = QTextEdit()
        self.console_output.setReadOnly(True)
        console_layout.addWidget(self.console_output, 1)

    def build_settings_tab(self):
        settings_tab = QWidget()
        self.tabs.addTab(settings_tab, "Settings")
        tab_layout = QVBoxLayout(settings_tab)
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        tab_layout.addWidget(scroll_area)
        content_widget = QWidget()
        layout = QHBoxLayout(content_widget)
        scroll_area.setWidget(content_widget)
        left_column_widget = QWidget()
        left_column_layout = QVBoxLayout(left_column_widget)
        left_column_layout.setContentsMargins(0, 0, 0, 0)
        connection_settings_group = QGroupBox("Serial Connection")
        connection_settings_layout = QFormLayout()
        self.port_combobox = QComboBox()
        self.baud_combobox = QComboBox()
        self.baud_combobox.addItems(["9600", "19200", "38400", "57600", "115200"])
        self.baud_combobox.setCurrentText("115200")
        self.refresh_button = QPushButton("Refresh Port List")
        connection_settings_layout.addRow("Port:", self.port_combobox)
        connection_settings_layout.addRow("Baud Rate:", self.baud_combobox)
        connection_settings_layout.addRow(self.refresh_button)
        connection_settings_group.setLayout(connection_settings_layout)
        left_column_layout.addWidget(connection_settings_group)
        probe_group = QGroupBox("Probe Settings")
        probe_layout = QFormLayout()
        self.probe_dist_input, self.probe_feed_input, self.probe_thickness_input = QLineEdit(), QLineEdit(), QLineEdit()
        self.slow_probe_feed_input, self.probe_retract_input, self.tool_radius_input = QLineEdit(), QLineEdit(), QLineEdit()
        probe_layout.addRow("Probe Travel (mm):", self.probe_dist_input)
        probe_layout.addRow("Fast Probe Feed Rate:", self.probe_feed_input)
        probe_layout.addRow("Slow Probe Feed Rate:", self.slow_probe_feed_input)
        probe_layout.addRow("Probe Retraction (mm):", self.probe_retract_input)
        probe_layout.addRow("Probe Thickness (mm):", self.probe_thickness_input)
        probe_layout.addRow("Tool Radius (mm):", self.tool_radius_input)
        probe_group.setLayout(probe_layout)
        left_column_layout.addWidget(probe_group)
        probe_fields = [self.probe_dist_input, self.probe_feed_input, self.slow_probe_feed_input, self.probe_retract_input, self.probe_thickness_input, self.tool_radius_input]
        self.numpad_enabled_fields.extend(probe_fields)
        for field in probe_fields:
            field.installEventFilter(self)
        left_column_layout.addStretch(1)
        self.initial_grbl_settings = {}
        self.grbl_setting_widgets = {}
        grbl_group = QGroupBox("GRBL Settings")
        self.grbl_layout = QGridLayout()
        read_button = QPushButton("Read Settings From Machine")
        read_button.clicked.connect(lambda: self.send_command("$$"))
        self.grbl_layout.addWidget(read_button, 0, 0, 1, 4)
        grbl_group.setLayout(self.grbl_layout)
        layout.addWidget(left_column_widget, 1)
        layout.addWidget(grbl_group, 2)
        save_button = QPushButton("Save All Settings")
        save_button.clicked.connect(self.save_settings)
        tab_layout.addWidget(save_button)
        self.load_settings()

    def connect_signals(self):
        self.refresh_button.clicked.connect(self.populate_ports)
        self.connect_button.clicked.connect(self.toggle_connection)
        self.x_plus_button.clicked.connect(lambda:self.send_jog_command("X",1,self.x_plus_button))
        self.x_minus_button.clicked.connect(lambda:self.send_jog_command("X",-1,self.x_minus_button))
        self.y_plus_button.clicked.connect(lambda:self.send_jog_command("Y",1,self.y_plus_button))
        self.y_minus_button.clicked.connect(lambda:self.send_jog_command("Y",-1,self.y_minus_button))
        self.z_plus_button.clicked.connect(lambda:self.send_jog_command("Z",1,self.z_plus_button))
        self.z_minus_button.clicked.connect(lambda:self.send_jog_command("Z",-1,self.z_minus_button))
        self.load_file_button.clicked.connect(self.load_gcode_file)
        self.start_button.clicked.connect(self.start_gcode)
        self.pause_button.clicked.connect(self.pause_gcode)
        self.stop_button.clicked.connect(self.stop_gcode)
        self.home_button.clicked.connect(self.run_homing_cycle)
        self.unlock_button.clicked.connect(lambda:self.send_command("$X"))
        self.set_location_button.clicked.connect(self.set_location)
        self.go_to_location_button.clicked.connect(self.go_to_location)
        self.run_probe_button.clicked.connect(self.run_probe_cycle)
        self.run_3axis_probe_button.clicked.connect(self.run_3axis_probe_cycle)
        self.spindle_on_button.clicked.connect(self.spindle_on)
        self.spindle_off_button.clicked.connect(lambda:self.send_command("M5"))
        self.exit_button.clicked.connect(self.close)
        self.shutdown_button.clicked.connect(self.shutdown_pi)
        self.e_stop_button.clicked.connect(self.emergency_stop)
        self.grbl_setting_received.connect(self.update_grbl_setting)
        self.send_button.clicked.connect(self.send_console_command)
        self.command_input.returnPressed.connect(self.send_console_command)
        self.gcode_line_sent.connect(self.on_gcode_line_sent)
        self.gcode_line_executed.connect(self.on_gcode_line_executed)
        self.gcode_job_error.connect(self.on_gcode_job_error)

    def on_gcode_line_sent(self, line_index):
        if line_index >= 0:
            item = QTableWidgetItem("Sent")
            self.gcode_table.setItem(line_index, 2, item)
            self.gcode_table.item(line_index, 2).setBackground(QColor("yellow"))
            self.gcode_table.scrollToItem(item, QAbstractItemView.PositionAtCenter)

    def on_gcode_line_executed(self, line_index):
        if line_index >= 0:
            item = QTableWidgetItem("Executed")
            self.gcode_table.setItem(line_index, 2, item)
            self.gcode_table.item(line_index, 2).setBackground(QColor("lightgreen"))
            self.update_progress_display()

    def on_gcode_job_error(self, error_message):
        if self.gcode_is_running:
            self.gcode_is_running = False
            self.gcode_is_paused = False
            self.update_ui_states()
            self.log_to_console(f"ERROR: G-code job stopped due to GRBL error: {error_message}")
            # Use a non-modal dialog to avoid freezing the app
            error_dialog = QMessageBox(self)
            error_dialog.setIcon(QMessageBox.Critical)
            error_dialog.setText("G-Code Job Error")
            error_dialog.setInformativeText(f"The job was halted due to a GRBL error:\n\n{error_message}")
            error_dialog.setStandardButtons(QMessageBox.Ok)
            error_dialog.setModal(False)
            error_dialog.show()

    def run_auto_connect_with_splash(self, splash, timeout_ms=3000):
        """Attempt an automatic connection while the provided splash is visible.
        If a connection is established before timeout_ms, show the UI immediately.
        Otherwise, show the UI after timeout_ms and allow manual connect.
        """
        splash.showMessage("Attempting auto-connect...", Qt.AlignBottom | Qt.AlignLeft, Qt.white)
        QApplication.processEvents()

        def finish_no_conn():
            splash.showMessage("Auto-connect timed out. Starting UI...", Qt.AlignBottom | Qt.AlignLeft, Qt.white)
            QApplication.processEvents()
            QTimer.singleShot(200, lambda: _request_finish_after_reveal(self))

        def attempt_connect():
            try:
                # Refresh port list first
                self.populate_ports()
                splash.showMessage("Scanning serial ports...", Qt.AlignBottom | Qt.AlignLeft, Qt.white)
                QApplication.processEvents()

                connected = False
                # Prefer real serial ports if available
                if self.port_combobox.count() > 0:
                    # choose the first available port
                    self.port_combobox.setCurrentIndex(0)
                    self.connect_serial()
                    connected = bool(self.serial_connection and getattr(self.serial_connection, 'is_open', False))
                else:
                    # No ports found
                    connected = False

                if connected:
                    splash.showMessage("Auto-connect succeeded.", Qt.AlignBottom | Qt.AlignLeft, Qt.white)
                    QApplication.processEvents()
                    # show UI shortly after success (respect reveal hold)
                    QTimer.singleShot(200, lambda: _request_finish_after_reveal(self))
                    if hasattr(self, '_splash_timeout_timer') and self._splash_timeout_timer.isActive():
                        self._splash_timeout_timer.stop()
            except Exception:
                # any error -> let timeout handle it
                pass

        # Start the attempt shortly after to ensure splash paints
        QTimer.singleShot(50, attempt_connect)
        # Start timeout fallback
        self._splash_timeout_timer = QTimer(self)
        self._splash_timeout_timer.setSingleShot(True)
        self._splash_timeout_timer.timeout.connect(finish_no_conn)
        self._splash_timeout_timer.start(timeout_ms)

    @Slot(QImage)
    def update_camera_feed(self, image):
        if image.isNull():
            return
        pixmap = QPixmap.fromImage(image)
        if hasattr(self, 'video_label') and self.video_label.isVisible():
            w = max(1, min(self.video_label.width(), self.video_label.maximumWidth()))
            h = max(1, min(self.video_label.height(), self.video_label.maximumHeight()))
            self.video_label.setPixmap(pixmap.scaled(w, h, Qt.KeepAspectRatio, Qt.SmoothTransformation))
        if hasattr(self, 'gcode_video_label') and self.gcode_video_label.isVisible():
            w = max(1, min(self.gcode_video_label.width(), self.gcode_video_label.maximumWidth()))
            h = max(1, min(self.gcode_video_label.height(), self.gcode_video_label.maximumHeight()))
            self.gcode_video_label.setPixmap(pixmap.scaled(w, h, Qt.KeepAspectRatio, Qt.SmoothTransformation))

    @Slot(str)
    def handle_camera_error(self, error_message):
        self.log_to_console(f"CAMERA_ERROR: {error_message}")
        self.video_label.setText(f"{error_message}\n\nIs camera connected?\nIs libcamera running?")

    def start_camera(self):
        if self.camera_thread and self.camera_thread.isRunning(): return
        self.camera_thread = QThread(self)
        self.camera_worker = CameraWorker()
        self.camera_worker.moveToThread(self.camera_thread)
        self.camera_thread.started.connect(self.camera_worker.run)
        self.camera_worker.frame_ready.connect(self.update_camera_feed)
        self.camera_worker.camera_error.connect(self.handle_camera_error)
        self.camera_thread.finished.connect(self.camera_worker.deleteLater)
        self.camera_thread.start()

    def stop_camera(self):
        if self.camera_worker: self.camera_worker.stop()
        if self.camera_thread:
            self.camera_thread.quit()
            self.camera_thread.wait()

    def log_to_console(self, message):
        if self.filter_ok_checkbox.isChecked() and (message == 'RX: ok' or message == 'TX: ?'): return
        if self.filter_pos_checkbox.isChecked() and message.startswith('RX: <') and 'MPos:' in message: return
        self.console_output.moveCursor(QTextCursor.Start)
        self.console_output.insertPlainText(message + '\n')

    def handle_serial_data(self, data):
        self.log_to_console(f"RX: {data}")
        if data.startswith("<"):
            # Parse buffer status if present
            buffer_match = re.search(r"Bf:(\d+),(\d+)", data)
            if buffer_match:
                self.planner_buffer_blocks = int(buffer_match.group(1))
                self.rx_buffer_bytes = int(buffer_match.group(2))
                # Now that we have fresh buffer data, try to send the next line.
                if self.gcode_is_running:
                    self.send_next_gcode_line()

            if data.startswith("<Home"):
                self.home_pulse_timer.stop()
                self.is_homed = True
            state_match = re.search(r"<([^|:]+)", data)
            if state_match:
                new_state = state_match.group(1)
                if new_state != self.machine_state:
                    self.machine_state = new_state
                    if self.machine_state == "Alarm":
                        alarm_match = re.search(r"Alarm:(\d+)", data)
                        if alarm_match: self.current_alarm_code = int(alarm_match.group(1))
                        self.is_probing = False
                    else:
                        self.current_alarm_code = None
                    self.update_ui_states()
            probe_match = re.search(r"\|Pn:([^|]+)", data)
            probe_triggered = 'P' in probe_match.group(1) if probe_match else False
            self.last_probe_state = probe_triggered
            self.probe_status_changed.emit(probe_triggered)
            pos_match = re.search(r"MPos:([\d.-]+),([\d.-]+),([\d.-]+)", data)
            if pos_match:
                self.mpos_x,self.mpos_y,self.mpos_z = (float(c) for c in pos_match.groups())
                self.x_pos_label.setText(f"{self.mpos_x:.3f}")
                self.y_pos_label.setText(f"{self.mpos_y:.3f}")
                self.z_pos_label.setText(f"{self.mpos_z:.3f}")
                wco_match = re.search(r"WCO:([\d.-]+),([\d.-]+),([\d.-]+)", data)
                if wco_match:
                    self.wco_x,self.wco_y,self.wco_z = (float(c) for c in wco_match.groups())
                wpos_x,wpos_y,wpos_z = self.mpos_x-self.wco_x, self.mpos_y-self.wco_y, self.mpos_z-self.wco_z
                self.wpos_x_label.setText(f"{wpos_x:.3f}")
                self.wpos_y_label.setText(f"{wpos_y:.3f}")
                self.wpos_z_label.setText(f"{wpos_z:.3f}")
        elif data.lower() == "ok":
            self.command_pending = False
            if self.is_advanced_probing:
                self.send_next_probe_command()
            elif self.is_parking:
                self.send_next_parking_command()
            elif self.gcode_is_running and not self.gcode_is_paused:
                # Emit a signal to update the UI from the main thread
                self.gcode_line_executed.emit(self.gcode_current_line - 1)
                self.send_next_gcode_line()
        elif data.startswith("error:"):
            self.log_to_console(f"DEBUG: Received '{data}', clearing command_pending.")
            self.command_pending = False

            # If a G-code job was running, HALT THE MACHINE IMMEDIATELY.
            if self.gcode_is_running:
                self.serial_connection.write(b'\x18') # Send soft-reset
                self.serial_connection.flush() # Ensure the halt command is sent immediately.
                self.log_to_console("CRITICAL: GRBL error during job. Sent immediate soft-reset (\\x18) to halt machine.")
                # Then, signal the main thread to update the UI and notify the user.
                self.gcode_job_error.emit(data)

            # Special UI handling for jog errors (can happen outside of a job)
            if "error:15" in data and self.last_jog_button:
                self.flash_jog_button(self.last_jog_button)
                self.last_jog_button = None
        elif data.startswith("ALARM:"):
            try:
                code = int(data.split(':')[1])
                if code == 15 and self.last_jog_button:
                    self.flash_jog_button(self.last_jog_button)
                    self.last_jog_button = None
                else:
                    self.current_alarm_code = code
                    self.machine_state = "Alarm"
                    # Reset any special sequences that might have been running
                    if self.is_parking:
                        self.is_parking = False
                        self.parking_command_queue = []
                    if self.is_advanced_probing:
                        self.end_probe_cycle() # Use existing method to clean up
                    self.update_ui_states()
                self.log_to_console(f"ALARM: {self.alarm_codes.get(code, 'Unknown alarm code.')}")
            except (ValueError, IndexError):
                self.log_to_console(f"Could not parse alarm code from: {data}")
        elif data.startswith("$"):
            parts = data.split("=")
            if len(parts) == 2: self.grbl_setting_received.emit(parts[0], parts[1])
        elif data.startswith("[PRB:"):
            if self.is_advanced_probing:
                self.probe_response_count += 1
                prb_match = re.search(r"\[PRB:([\d.-]+),([\d.-]+),([\d.-]+):", data)
                if prb_match and self.probe_response_count > 1: # Ignore fast probe
                    if self.xyz_probe_stage == 'Z': val = float(prb_match.group(3))
                    elif self.xyz_probe_stage == 'X': val = float(prb_match.group(1))
                    elif self.xyz_probe_stage == 'Y': val = float(prb_match.group(2))
                    else: val = float(prb_match.group(3)) # Fallback for Z-only
                    self.probe_results.append(val)
            else: # Legacy single-probe logic
                self.is_probing = False
                self.probe_succeeded = True
                self.update_ui_states()
                probe_thickness = float(self.settings.value("probe/thickness", 1.0))
                self.send_command(f"G10 L2 P1 Z{probe_thickness}")
                self.log_to_console(f"INFO: Probe successful. Z-axis zeroed to {probe_thickness}mm.")

    def run_probe_cycle(self):
        self.is_manually_zeroed = self.z_is_auto_zeroed = False
        arm_dialog = ProbeArmDialog(self)
        arm_dialog.e_stop_button.clicked.connect(self.emergency_stop)
        self.probe_status_changed.connect(arm_dialog.update_probe_status)
        self.send_command("?")
        try:
            if arm_dialog.exec_() != QDialog.Accepted: return
        finally:
            self.probe_status_changed.disconnect(arm_dialog.update_probe_status)
        self.dro_timer.stop()
        self.is_probing = self.is_advanced_probing = True
        self.probe_phase = 'probing'
        self.probe_succeeded = False
        self.probe_results, self.probe_response_count = [], 0
        self.update_ui_states()
        try:
            fast_feed = float(self.settings.value("probe/feedrate", "25"))
            slow_feed = float(self.settings.value("probe/slow_feedrate", "10"))
            retract = float(self.settings.value("probe/retract_dist", "2"))
            dist = float(self.settings.value("probe/distance", "-25"))
        except (ValueError, TypeError):
            QMessageBox.critical(self, "Probe Error", "Invalid probe settings.")
            self.end_probe_cycle()
            return
        self.probe_command_queue = [f"G91",f"G38.2 Z{dist} F{fast_feed}",f"G90",f"G91",f"G0 Z{retract}",f"G90",f"G91",f"G38.2 Z{dist} F{slow_feed}",f"G90",f"G91",f"G0 Z{retract}",f"G90",f"G91",f"G38.2 Z{dist} F{slow_feed}",f"G90",f"G91",f"G0 Z{retract}",f"G90",f"G91",f"G38.2 Z{dist} F{slow_feed}",f"G90"]
        self.send_next_probe_command()

    def send_next_probe_command(self):
        if self.probe_command_queue:
            self.send_command(self.probe_command_queue.pop(0))
        else:
            if self.probe_phase == 'probing': self.start_probe_finalization()
            elif self.probe_phase == 'finalizing':
                if self.xyz_probe_stage in ['X_TRANSITION', 'Y_TRANSITION', 'FINALIZE']:
                    self.handle_probe_transition()
                else: self.end_probe_cycle()

    def send_next_parking_command(self):
        if self.parking_command_queue:
            command = self.parking_command_queue.pop(0)
            self.send_command(command)
        else:
            self.is_parking = False
            self.gcode_is_running = False  # Now the job is truly over
            self.gcode_start_time = None
            self.update_ui_states()
            self.log_to_console("INFO: Parking sequence complete.")

    def start_parking_sequence(self):
        self.log_to_console("INFO: G-code file processed. Starting parking sequence.")
        self.parking_command_queue = [
            "M5",              # Stop spindle
            "G4 P0.1",        # Dwell for 0.1s to ensure spindle stops
            "G90",            # Absolute positioning
            "G53 G0 Z-1",     # Move to machine Z-1 (safe height) in machine coordinates
            "G4 P0.1",        # Dwell for 0.1s to ensure Z move completes
            "G28"             # Return to predefined parking position
        ]
        self.send_next_parking_command()

    def start_probe_finalization(self):
        if len(self.probe_results) != 3:
            self.log_to_console(f"ERROR: Probe failed. Expected 3 results, got {len(self.probe_results)}.")
            self.end_probe_cycle()
            return
        self.probe_phase = 'finalizing'
        avg_pos = sum(self.probe_results) / len(self.probe_results)
        try:
            thickness = float(self.settings.value("probe/thickness", 1.0))
            radius = float(self.settings.value("probe/tool_radius", 3.15))
        except (ValueError, TypeError):
            QMessageBox.critical(self, "Probe Error", "Invalid probe settings.")
            self.end_probe_cycle()
            return
        if not self.xyz_probe_stage or self.xyz_probe_stage == 'Z':
            offset = avg_pos - thickness
            self.log_to_console(f"INFO: Z-Probe successful. Avg: {avg_pos:.4f}mm. Setting Z-WCO.")
            if not self.xyz_probe_stage:
                self.probe_command_queue = [f"G10 L2 P1 Z{offset:.4f}", f"G90 G0 Z{thickness + 10}"]
            else:
                self.probe_command_queue = [f"G10 L2 P1 Z{offset:.4f}","G91 G0 Z10","G91 G0 X-25"]
                self.xyz_probe_stage = 'X_TRANSITION'
            self.send_next_probe_command()
        elif self.xyz_probe_stage == 'X':
            offset = avg_pos + radius
            self.log_to_console(f"INFO: X-Probe successful. Avg: {avg_pos:.4f}mm. Setting X-WCO.")
            self.probe_command_queue = [f"G10 L2 P1 X{offset:.4f}","G91 G0 X-30","G91 G0 Y-25"]
            self.xyz_probe_stage = 'Y_TRANSITION'
            self.send_next_probe_command()
        elif self.xyz_probe_stage == 'Y':
            offset = avg_pos + radius
            self.log_to_console(f"INFO: Y-Probe successful. Avg: {avg_pos:.4f}mm. Setting Y-WCO.")
            self.probe_command_queue = [f"G10 L2 P1 Y{offset:.4f}"]
            self.xyz_probe_stage = 'FINALIZE'
            self.send_next_probe_command()

    def handle_probe_transition(self):
        if self.xyz_probe_stage == 'X_TRANSITION':
            QMessageBox.information(self, "Reposition", "Reposition probe for X-axis and press OK.")
            self.xyz_probe_stage = 'X'; self.execute_probe_stage()
        elif self.xyz_probe_stage == 'Y_TRANSITION':
            QMessageBox.information(self, "Reposition", "Reposition probe for Y-axis and press OK.")
            self.xyz_probe_stage = 'Y'; self.execute_probe_stage()
        elif self.xyz_probe_stage == 'FINALIZE':
            self.log_to_console("INFO: 3-Axis Probing Complete.")
            self.probe_command_queue = ["G53 G0 Z-10.0", "G90 G0 X0 Y0"]
            self.xyz_probe_stage = 'DONE'
            self.send_next_probe_command()

    def end_probe_cycle(self):
        if self.probe_phase == 'finalizing':
            self.probe_succeeded = self.z_is_auto_zeroed = True
        self.is_probing = self.is_advanced_probing = False
        self.probe_phase = self.xyz_probe_stage = None
        self.probe_command_queue, self.probe_results, self.probe_response_count = [], [], 0
        self.dro_timer.start()
        self.update_ui_states()

    def run_3axis_probe_cycle(self):
        self.is_manually_zeroed = self.z_is_auto_zeroed = False
        arm_dialog = ProbeArmDialog(self)
        arm_dialog.e_stop_button.clicked.connect(self.emergency_stop)
        self.probe_status_changed.connect(arm_dialog.update_probe_status)
        self.send_command("?")
        try:
            if arm_dialog.exec_() != QDialog.Accepted: return
        finally:
            self.probe_status_changed.disconnect(arm_dialog.update_probe_status)
        self.dro_timer.stop()
        self.is_probing = self.is_advanced_probing = True
        self.probe_succeeded = False
        self.xyz_probe_stage = 'Z'
        self.execute_probe_stage()
        self.update_ui_states()

    def execute_probe_stage(self):
        self.probe_phase = 'probing'
        self.probe_results, self.probe_response_count = [], 0
        try:
            fast_feed = float(self.settings.value("probe/feedrate","25"))
            slow_feed = float(self.settings.value("probe/slow_feedrate","10"))
            retract = float(self.settings.value("probe/retract_dist","2"))
            dist = float(self.settings.value("probe/distance","-25"))
        except (ValueError,TypeError):
            QMessageBox.critical(self, "Probe Error", "Invalid probe settings.")
            self.end_probe_cycle()
            return
        axis = self.xyz_probe_stage
        p_dist = dist if axis == 'Z' else abs(dist)
        r_dist = retract if axis == 'Z' else -retract
        probe_commands=[f"G91 G38.2 {axis}{p_dist} F{fast_feed}",f"G91 G0 {axis}{r_dist}",f"G91 G38.2 {axis}{p_dist} F{slow_feed}",f"G91 G0 {axis}{r_dist}",f"G91 G38.2 {axis}{p_dist} F{slow_feed}",f"G91 G0 {axis}{r_dist}",f"G91 G38.2 {axis}{p_dist} F{slow_feed}",f"G91 G0 {axis}{r_dist}"]
        self.probe_command_queue = ["G91 G0 X45"] + probe_commands if axis == 'Y' else probe_commands
        self.send_next_probe_command()

    def run_homing_cycle(self):
        self.is_homed=self.probe_succeeded=self.is_manually_zeroed=self.z_is_auto_zeroed=False
        self.home_pulse_timer.start()
        self.send_command("$H")

    def set_location(self):
        locations = [f"Work Origin G{54+i} (P{i+1})" for i in range(6)]+["Safe Position (G28.1)"]
        choice = LocationDialog.get_selected_index(self, "Set Location", locations, "Select location to set:")
        if choice == -1: return
        if choice < 6:
            p = choice + 1
            self.send_command(f"G10 L2 P{p} X{self.mpos_x} Y{self.mpos_y} Z{self.mpos_z}")
            self.log_to_console(f"INFO: Set WCS for G{53+p} (P{p}).")
        else:
            self.send_command("G28.1")
            self.log_to_console("INFO: Position saved as G28.")

    def go_to_location(self):
        locations = [f"Work Origin G{54+i}" for i in range(6)] + ["Safe Position (G28)"]
        choice = LocationDialog.get_selected_index(self, "Go To", locations, "Select destination:")
        if choice == -1: return
        if choice < 6:
            self.send_command(f"G{54+choice}")
            self.send_command("G90 G0 X0 Y0")
        else:
            self.send_command("G28")

    def load_gcode_file(self):
        filepath, _ = QFileDialog.getOpenFileName(self, "Load G-Code", "", "*.gcode *.nc;;*.*")
        if filepath:
            with open(filepath, 'r') as f:
                self.gcode_lines = [line.strip() for line in f if line.strip() and not line.strip().startswith(';')]
            self.gcode_file_label.setText(os.path.basename(filepath))
            self.gcode_progress.setMaximum(len(self.gcode_lines))
            self.gcode_current_line = 0
            self.gcode_progress.setValue(0)
            self.gcode_estimated_time = self.estimate_gcode_time()
            if self.gcode_estimated_time > 0:
                mins, secs = divmod(self.gcode_estimated_time, 60)
                time_str = f"{int(mins)}m {int(secs)}s"
                self.gcode_progress.setFormat(f"0.0% | Est. {time_str} remaining")
                self.log_to_console(f"DEBUG: Initial time estimated: {time_str}")
            else:
                self.gcode_progress.setFormat("0.0%")
            self.gcode_table.setRowCount(len(self.gcode_lines))
            for i, line in enumerate(self.gcode_lines):
                self.gcode_table.setItem(i, 0, QTableWidgetItem(str(i + 1)))
                self.gcode_table.setItem(i, 1, QTableWidgetItem(line))
                self.gcode_table.setItem(i, 2, QTableWidgetItem("Queued"))
            self.gcode_table.resizeColumnsToContents()
            self.update_ui_states()

    def update_ui_states(self):
        is_connected = bool(self.serial_connection and self.serial_connection.is_open)
        file_loaded = bool(self.gcode_lines)
        job_running = self.gcode_is_running

        # G-code execution controls
        self.start_button.setEnabled(is_connected and file_loaded and not job_running)
        self.pause_button.setEnabled(is_connected and job_running)
        self.stop_button.setEnabled(is_connected and job_running)

        # Manual and setup controls are disabled during a job, except for critical overrides
        can_use_manual_controls = is_connected and not job_running
        for w in [self.home_button, self.unlock_button, self.run_probe_button, self.run_3axis_probe_button,
                  self.set_location_button, self.go_to_location_button,
                  self.x_plus_button, self.x_minus_button, self.y_plus_button, self.y_minus_button,
                  self.z_plus_button, self.z_minus_button, self.step_size_combo]:
            w.setEnabled(can_use_manual_controls)

        # Spindle and E-Stop are always available when connected
        for w in [self.e_stop_button, self.spindle_on_button, self.spindle_off_button, self.spindle_speed_input]:
            w.setEnabled(is_connected)

        self.pause_button.setText("Resume" if self.gcode_is_paused else "Pause")
        self.home_pulse_timer.stop(); self.alarm_pulse_timer.stop()
        self.home_button.setStyleSheet(""); self.unlock_button.setStyleSheet(""); self.run_probe_button.setStyleSheet("")
        if not is_connected: self.is_homed = self.is_manually_zeroed = False
        if self.machine_state == "Home": self.home_pulse_timer.start()
        else: self.home_button.setText("Homed" if self.is_homed else "Home ($H)")
        if self.is_homed: self.home_button.setStyleSheet("background-color:darkgreen;color:white;font-weight:bold;")
        if self.machine_state == "Alarm":
            self.alarm_pulse_timer.start()
            self.unlock_button.setText(f"ALARM: {self.alarm_codes.get(self.current_alarm_code, 'UNLOCK')}")
            self.is_homed = False
        else:
            self.unlock_button.setText("Unlock ($X)" if not is_connected else "No Alarm")
            if is_connected: self.unlock_button.setStyleSheet("background-color:darkgreen;color:white;font-weight:bold;")
        probe_enabled = is_connected and not self.is_probing and self.machine_state != "Alarm"
        self.run_probe_button.setEnabled(probe_enabled)
        self.run_3axis_probe_button.setEnabled(probe_enabled)
        if self.is_probing:
            text = f"Probing {self.xyz_probe_stage}..." if self.xyz_probe_stage else "Probing..."
            self.run_probe_button.setText(text); self.run_3axis_probe_button.setText(text)
        elif self.z_is_auto_zeroed:
            self.run_probe_button.setText("Z Zeroed"); self.run_probe_button.setStyleSheet("background-color:darkgreen;color:white;font-weight:bold;"); self.run_3axis_probe_button.setText("3-Axis\nAuto Zero")
        else:
            self.run_probe_button.setText("Auto Zero Z"); self.run_3axis_probe_button.setText("3-Axis\nAuto Zero")

    def start_gcode(self):
        if self.gcode_lines:
            for i in range(self.gcode_table.rowCount()):
                item = QTableWidgetItem("Queued"); self.gcode_table.setItem(i, 2, item); self.gcode_table.item(i, 2).setBackground(QColor("white"))
            self.probe_succeeded = self.is_manually_zeroed = False
            self.gcode_is_running, self.gcode_is_paused, self.gcode_current_line = True, False, 0
            self.gcode_start_time = time.time()
            self.update_ui_states()
            self.send_next_gcode_line()

    def pause_gcode(self):
        if self.gcode_is_running:
            self.gcode_is_paused = not self.gcode_is_paused
            self.send_command("!" if self.gcode_is_paused else "~")
            self.update_ui_states()

    def emergency_stop(self):
        self.send_command("\x18")
        self.gcode_is_running=self.gcode_is_paused=self.gcode_current_line=0
        self.gcode_progress.setValue(0); self.gcode_progress.setFormat("%p%")
        self.update_ui_states()

    def spindle_on(self):
        try: self.send_command(f"M3 S{int(self.spindle_speed_input.text())}")
        except ValueError: self.log_to_console("INFO: Invalid spindle speed.")

    def stop_gcode(self): self.emergency_stop()

    def estimate_gcode_time(self):
        try:
            max_x=float(self.grbl_setting_widgets["$110"].text()); max_y=float(self.grbl_setting_widgets["$111"].text()); max_z=float(self.grbl_setting_widgets["$112"].text()); src="GRBL"
        except (KeyError, ValueError):
            max_x,max_y,max_z=5000,5000,1000; src="Defaults"
        self.log_to_console(f"DEBUG: Estimating time with Max Rates (X,Y,Z): {max_x}, {max_y}, {max_z} from {src}")
        x,y,z,feed,total_time=0,0,0,1000,0; is_abs=True; self.gcode_line_times=[]
        for line in self.gcode_lines:
            line_time = 0; cmd = line.upper().split(';')[0]
            if "G90" in cmd: is_abs=True
            if "G91" in cmd: is_abs=False
            if cmd.startswith(("G0","G1")):
                tx,ty,tz=x,y,z
                if "X" in cmd: tx=float(re.search(r'X([-\d.]+)',cmd).group(1)) if is_abs else x+float(re.search(r'X([-\d.]+)',cmd).group(1))
                if "Y" in cmd: ty=float(re.search(r'Y([-\d.]+)',cmd).group(1)) if is_abs else y+float(re.search(r'Y([-\d.]+)',cmd).group(1))
                if "Z" in cmd: tz=float(re.search(r'Z([-\d.]+)',cmd).group(1)) if is_abs else z+float(re.search(r'Z([-\d.]+)',cmd).group(1))
                if "F" in cmd: feed=float(re.search(r'F([-\d.]+)',cmd).group(1))
                dist=math.sqrt((tx-x)**2+(ty-y)**2+(tz-z)**2)
                if dist > 0:
                    if cmd.startswith("G0"):
                        line_time = max(abs(tx-x)/max_x if max_x>0 else 0, abs(ty-y)/max_y if max_y>0 else 0, abs(tz-z)/max_z if max_z>0 else 0) * 60
                    else: line_time = dist/(feed/60)
                x,y,z = tx,ty,tz
            total_time+=line_time; self.gcode_line_times.append(line_time)
        return total_time

    def update_progress_display(self):
        if not self.gcode_is_running or not self.gcode_line_times or self.gcode_estimated_time==0: return
        executed = min(self.gcode_current_line, len(self.gcode_line_times))
        self.gcode_progress.setValue(executed)
        time_done = sum(self.gcode_line_times[:executed])
        time_left = self.gcode_estimated_time - time_done
        if time_left < 0: time_left = 0
        percent = (time_done / self.gcode_estimated_time) * 100
        mins, secs = divmod(time_left, 60)
        time_str = f"{int(mins)}m {int(secs)}s"
        self.gcode_progress.setFormat(f"{percent:.1f}% | Est. {time_str} remaining")

    def request_status_and_send_next(self):
        """Periodically called by a timer to request machine status."""
        self.send_command("?")

    def send_next_gcode_line(self):
        if self.gcode_is_running and not self.gcode_is_paused:
            if self.gcode_current_line < len(self.gcode_lines):
                # Full Hybrid Flow Control:
                # 1. Check if we are waiting for an 'ok' from a previous command.
                if self.command_pending:
                    return

                # 2. Check if GRBL's planner buffer has a safety margin.
                if self.planner_buffer_blocks < 3: # Wait for at least 3 free blocks.
                    return

                # 3. Check if GRBL's RX buffer has space for the next command.
                cmd = self.gcode_lines[self.gcode_current_line]
                if (len(cmd) + 1) >= self.rx_buffer_bytes:
                    return

                self.log_to_console(f"DEBUG: Sending L:{self.gcode_current_line + 1}/{len(self.gcode_lines)} -> {cmd} (Bf:{self.planner_buffer_blocks},{self.rx_buffer_bytes})")
                if self.send_command(cmd):
                    self.gcode_line_sent.emit(self.gcode_current_line)
                    self.gcode_current_line += 1
            else:
                # G-code file is done, transition to parking or finish up.
                if self.park_on_finish_checkbox.isChecked() and not self.is_parking:
                    self.is_parking = True
                    self.start_parking_sequence()
                elif not self.is_parking:
                    self.gcode_is_running = False
                    self.gcode_start_time = None
                    self.update_ui_states()
                    self.gcode_progress.setFormat("Complete!")
                    self.log_to_console("INFO: G-code finished.")

    def send_command(self, command):
        if not self.serial_connection or not self.serial_connection.is_open:
            self.log_to_console(f"INFO: Not connected. Cmd '{command}' not sent.")
            return False

        if self.command_pending and command not in ['?', '!', '~', '\x18']:
            self.log_to_console(f"DEBUG: Command '{command}' blocked, command_pending is True.")
            return False

        self.log_to_console(f"TX: {command}")
        self.serial_connection.write((command + '\n').encode('utf-8'))

        if command not in ['?', '!', '~', '\x18']:
            self.command_pending = True
            self.log_to_console(f"DEBUG: Set command_pending=True for '{command}'")

        return True

    def send_console_command(self):
        cmd = self.command_input.text()
        if cmd: self.send_command(cmd); self.command_input.clear()

    def send_jog_command(self, axis, direction, button):
        self.last_jog_button = button; self.is_manually_zeroed = False
        step = float(self.step_size_combo.currentText())
        self.send_command(f"$J=G91 G21 {axis}{step * direction} F1000")

    def populate_ports(self): self.port_combobox.clear(); self.port_combobox.addItems([p.device for p in serial.tools.list_ports.comports()])
    def toggle_connection(self):
        if self.serial_connection and self.serial_connection.is_open: self.disconnect_serial()
        else: self.connect_serial()

    def connect_serial(self):
        port, baud = self.port_combobox.currentText(), int(self.baud_combobox.currentText())
        if not port: return
        try:
            self.serial_connection=serial.Serial(port,baud,timeout=1); time.sleep(2); self.serial_connection.write(b"\r\n\r\n"); self.serial_connection.flushInput(); self.serial_thread=QThread(); self.serial_worker=SerialWorker(self.serial_connection); self.serial_worker.moveToThread(self.serial_thread); self.serial_thread.started.connect(self.serial_worker.run); self.serial_worker.serial_data_received.connect(self.handle_serial_data); self.serial_thread.start(); self.dro_timer.start(); self.connect_button.setText("Disconnect"); self.update_connection_indicator(True)
        except (serial.SerialException, FileNotFoundError) as e:
            self.log_to_console(f"ERROR: Failed to connect - {e}"); self.update_connection_indicator(False)
        self.update_ui_states()

    def disconnect_serial(self):
        self.dro_timer.stop()
        if self.serial_thread:
            self.serial_worker.stop(); self.serial_thread.quit(); self.serial_thread.wait()
        if self.serial_connection: self.serial_connection.close()
        self.connect_button.setText("Connect"); self.serial_connection=self.serial_thread=self.serial_worker=None; self.update_connection_indicator(False); self.update_ui_states()

    def pulse_home_button(self):
        self.home_button.setText("Homing"); self.home_pulse_state = 1-self.home_pulse_state; self.home_button.setStyleSheet(f"background-color: {'#4CAF50' if self.home_pulse_state==0 else '#8BC34A'}; color: white;")

    def pulse_alarm_button(self):
        self.unlock_button.setText(f"ALARM: {self.alarm_codes.get(self.current_alarm_code, 'UNLOCK')}"); self.alarm_pulse_state=1-self.alarm_pulse_state; self.unlock_button.setStyleSheet(f"background-color: {'#F44336' if self.alarm_pulse_state==0 else '#FF7043'}; color: white; font-weight: bold;")

    def update_connection_indicator(self, is_connected):
        if is_connected:
            self.connection_status_indicator.setText("Connected"); self.connection_status_indicator.setStyleSheet("background-color:green;color:white;font-weight:bold;")
        else:
            self.connection_status_indicator.setText("Disconnected"); self.connection_status_indicator.setStyleSheet("background-color:red;color:white;font-weight:bold;")

    def load_settings(self):
        defaults={"probe/distance":"-25","probe/feedrate":"25","probe/thickness":"1.0","probe/slow_feedrate":"10","probe/retract_dist":"2","probe/tool_radius":"3.15"}
        for key,widget in self.get_settings_widgets().items(): widget.setText(self.settings.value(key, defaults.get(key)))
        self.park_on_finish_checkbox.setChecked(self.settings.value("gcode/park_on_finish", True, type=bool))

    def save_settings(self):
        for key,widget in self.get_settings_widgets().items(): self.settings.setValue(key, widget.text())
        self.settings.setValue("gcode/park_on_finish", self.park_on_finish_checkbox.isChecked())
        for setting,field in self.get_grbl_fields().items():
            if field.text() != self.initial_grbl_settings.get(setting,''): self.send_command(f"{setting}={field.text()}")
        self.log_to_console("INFO: Settings saved.")

    def update_grbl_setting(self, setting, value):
        self.initial_grbl_settings[setting]=value
        if setting in self.grbl_setting_widgets: self.grbl_setting_widgets[setting].setText(value)
        else:
            info=self.GRBL_SETTINGS_INFO.get(setting,{}); lbl_txt=f"{info.get('label',setting)}:"; tip_txt=info.get('tooltip',"No description.")
            label=QLabel(lbl_txt); field=QLineEdit(value); field.setToolTip(tip_txt); field.installEventFilter(self)
            row=(self.grbl_settings_count//2)+1; col=self.grbl_settings_count%2
            self.grbl_layout.addWidget(label,row,col*2); self.grbl_layout.addWidget(field,row,col*2+1); self.grbl_setting_widgets[setting]=field; self.numpad_enabled_fields.append(field); self.grbl_settings_count+=1

    def get_settings_widgets(self): return {"probe/distance":self.probe_dist_input,"probe/feedrate":self.probe_feed_input,"probe/thickness":self.probe_thickness_input,"probe/slow_feedrate":self.slow_probe_feed_input,"probe/retract_dist":self.probe_retract_input,"probe/tool_radius":self.tool_radius_input}
    def get_grbl_fields(self): return self.grbl_setting_widgets

    def show_number_pad(self, line_edit):
        dialog = NumberPadDialog(line_edit.text(), self)
        if dialog.exec_() == QDialog.Accepted: line_edit.setText(dialog.get_value())
        line_edit.clearFocus()

    def flash_jog_button(self, button):
        orig_txt,orig_style = button.text(),button.styleSheet()
        button.setText("Soft Limit"); button.setStyleSheet("background-color:red;color:white;font-weight:bold;")
        QTimer.singleShot(2000, lambda: self.restore_jog_button(button, orig_txt, orig_style))

    def restore_jog_button(self, button, text, stylesheet): button.setText(text); button.setStyleSheet(stylesheet)
    def shutdown_pi(self):
        if QMessageBox.question(self, 'Confirm Shutdown', "Are you sure?", QMessageBox.Yes|QMessageBox.No, QMessageBox.No)==QMessageBox.Yes: os.system("sudo shutdown -h now")

    def closeEvent(self, event):
        self.stop_camera(); self.disconnect_serial(); super().closeEvent(event)

    def eventFilter(self, obj, event):
        if event.type() == QEvent.FocusIn and isinstance(obj, QLineEdit) and obj in self.numpad_enabled_fields:
            if event.reason() == Qt.MouseFocusReason:
                obj.setReadOnly(True)
                self.show_number_pad(obj)
                return True
            # For non-mouse focus events on touch-enabled fields, make them read-only
            # to prevent the virtual keyboard from appearing, but don't show the numpad.
            # The user can still tap the field to bring up the numpad.
            obj.setReadOnly(True)
            return False # Allow event to propagate to not break focus chains
        elif event.type() == QEvent.FocusOut and isinstance(obj, QLineEdit) and obj in self.numpad_enabled_fields:
            obj.setReadOnly(False)
        return super().eventFilter(obj, event)
if __name__ == "__main__":
    # Reuse the early-created QApplication and splash shown at module import time.
    window = MainWindow(splash)
    # Let the window attempt auto-connect while the splash is visible
    window.run_auto_connect_with_splash(splash, timeout_ms=3000)
    sys.exit(app.exec_())