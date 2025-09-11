# v0.14.2
import sys
import serial.tools.list_ports
import re
import time
import os
from PySide2.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QComboBox, QPushButton, QLabel, QGroupBox, QGridLayout, QProgressBar, QFileDialog, QTextEdit, QLineEdit, QTabWidget, QMessageBox, QFormLayout, QCheckBox, QDialog, QDialogButtonBox, QScrollArea, QToolTip
)
from PySide2.QtCore import Qt, QThread, QObject, Signal, QTimer, QSettings, QEvent
from PySide2.QtGui import QTextCursor

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

        self.e_stop_button = QPushButton("EMERGENCY STOP")
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

        if self.is_verified and not is_triggered:
            self.ok_button.setEnabled(True)
        else:
            self.ok_button.setEnabled(False)


class ProbeArmDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Verify Tool and Plate")
        self.setModal(True)
        self.is_verified = False
        layout = QVBoxLayout(self)

        instructions = (
            "1. Attach the probe lead to the cutting bit.\n"
            "2. Touch the bit to the contact plate to verify.\n"
            "3. Lift the probe. The button will enable."
        )
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

        self.e_stop_button = QPushButton("EMERGENCY STOP")
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

        if self.is_verified and not is_triggered:
            self.ok_button.setEnabled(True)
        else:
            self.ok_button.setEnabled(False)


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
        if dialog.exec_() == QDialog.Accepted:
            return dialog.selected_index
        return -1


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

        button_map = {
            '7': (1, 0), '8': (1, 1), '9': (1, 2),
            '4': (2, 0), '5': (2, 1), '6': (2, 2),
            '1': (3, 0), '2': (3, 1), '3': (3, 2),
            '0': (4, 0), '.': (4, 1),
            'Backspace': (1, 3), 'Clear': (2, 3),
            'Enter': (3, 3), 'Cancel': (4, 3)
        }

        for text, pos in button_map.items():
            button = QPushButton(text)
            if text.isdigit() or text == '.':
                button.clicked.connect(self.on_digit_pressed)
            elif text == 'Backspace':
                button.clicked.connect(self.on_backspace_pressed)
            elif text == 'Clear':
                button.clicked.connect(self.on_clear_pressed)
            elif text == 'Enter':
                button.clicked.connect(self.accept)
            elif text == 'Cancel':
                button.clicked.connect(self.reject)
            layout.addWidget(button, pos[0], pos[1])

    def on_digit_pressed(self):
        button = self.sender()
        if button.text() == '.' and '.' in self.display.text():
            return
        new_text = self.display.text() + button.text()
        self.display.setText(new_text)

    def on_backspace_pressed(self):
        self.display.setText(self.display.text()[:-1])

    def on_clear_pressed(self):
        self.display.clear()

    def get_value(self):
        return self.display.text()


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
                    if line:
                        self.serial_data_received.emit(line)
                except serial.SerialException:
                    break
        print("Serial worker finished.")

    def stop(self):
        self._is_running = False

class MainWindow(QMainWindow):
    grbl_setting_received = Signal(str, str)
    probe_status_changed = Signal(bool)

    def __init__(self):
        super().__init__()
        self.alarm_codes = {
            1: "Hard limit triggered. Position Lost.",
            2: "Soft limit alarm, position kept. Unlock is Safe.",
            3: "Reset while in motion. Position lost.",
            4: "Probe fail. Probe not in expected initial state.",
            5: "Probe fail. Probe did not contact the work.",
            6: "Homing fail. The active homing cycle was reset.",
            7: "Homing fail. Door opened during homing cycle.",
            8: "Homing fail. Pull off failed to clear limit switch.",
            9: "Homing fail. Could not find limit switch.",
            15: "Jog target exceeds machine travel."
        }
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
        self.e_stop_button = QPushButton("EMERGENCY STOP")
        self.e_stop_button.setStyleSheet("background-color: red; color: white; font-weight: bold;")
        self.e_stop_button.setFixedHeight(40)
        top_bar_layout.addWidget(self.e_stop_button)
        connection_layout = QHBoxLayout()
        self.connect_button = QPushButton("Connect")
        connection_layout.addWidget(self.connect_button)
        self.connection_status_indicator = QPushButton("Disconnected")
        self.connection_status_indicator.setCheckable(False)
        self.connection_status_indicator.setEnabled(False)
        connection_layout.addWidget(self.connection_status_indicator)
        top_bar_layout.addLayout(connection_layout)
        top_bar_layout.addStretch()
        system_buttons_layout = QVBoxLayout()
        self.exit_button = QPushButton("Exit Application")
        self.shutdown_button = QPushButton("Shutdown Pi")
        system_buttons_layout.addWidget(self.exit_button)
        system_buttons_layout.addWidget(self.shutdown_button)
        top_bar_layout.addLayout(system_buttons_layout)
        main_layout.addLayout(top_bar_layout)
        self.tabs = QTabWidget()
        main_layout.addWidget(self.tabs)
        self.numpad_enabled_fields = []
        self.build_manual_control_tab()
        self.build_gcode_tab()
        self.build_console_tab()
        self.build_settings_tab()
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
        self.xyz_probe_stage = None
        self.probe_command_queue = []
        self.probe_results = []
        self.probe_response_count = 0
        self.probe_phase = None
        self.wco_x, self.wco_y, self.wco_z = 0.0, 0.0, 0.0
        self.mpos_x, self.mpos_y, self.mpos_z = 0.0, 0.0, 0.0
        self.grbl_settings_count = 0
        self.dro_timer = QTimer(self)
        self.dro_timer.setInterval(200)
        self.dro_timer.timeout.connect(lambda: self.send_command("?"))
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

    def build_manual_control_tab(self):
        manual_tab = QWidget()
        self.tabs.addTab(manual_tab, "Manual Control")
        main_layout = QHBoxLayout(manual_tab)

        # --- Left Column (Spindle & Actions) ---
        left_column_layout = QVBoxLayout()
        left_column_layout.setAlignment(Qt.AlignTop)

        spindle_group = QGroupBox("Spindle")
        spindle_layout = QFormLayout()
        self.spindle_speed_input = QLineEdit("1000")
        self.numpad_enabled_fields.append(self.spindle_speed_input)
        self.spindle_speed_input.installEventFilter(self)
        self.spindle_on_button, self.spindle_off_button = QPushButton("On (M3)"), QPushButton("Off (M5)")
        spindle_layout.addRow("Speed (RPM):", self.spindle_speed_input)
        spindle_layout.addRow(self.spindle_on_button, self.spindle_off_button)
        spindle_group.setLayout(spindle_layout)
        left_column_layout.addWidget(spindle_group)

        actions_group = QGroupBox("Actions")
        actions_layout = QVBoxLayout()
        self.home_button, self.unlock_button = QPushButton("Home ($H)"), QPushButton("Unlock ($X)")
        self.run_probe_button = QPushButton("Auto Zero Z")
        self.run_3axis_probe_button = QPushButton("3-Axis XYZ Probe")
        self.set_location_button = QPushButton("Set Location")
        self.go_to_location_button = QPushButton("Go To Location")

        actions_layout.addWidget(self.home_button)
        actions_layout.addWidget(self.unlock_button)
        actions_layout.addWidget(self.run_probe_button)
        actions_layout.addWidget(self.run_3axis_probe_button)
        actions_layout.addWidget(self.set_location_button)
        actions_layout.addWidget(self.go_to_location_button)
        actions_group.setLayout(actions_layout)
        left_column_layout.addWidget(actions_group)
        
        main_layout.addLayout(left_column_layout)

        # --- Middle Column (DROs) ---
        middle_column_layout = QVBoxLayout()
        middle_column_layout.setAlignment(Qt.AlignTop)

        dro_group = QGroupBox("DRO (Machine Pos)")
        dro_layout = QFormLayout()
        self.x_pos_label, self.y_pos_label, self.z_pos_label = QLabel("0.000"), QLabel("0.000"), QLabel("0.000")
        dro_layout.addRow("X:", self.x_pos_label)
        dro_layout.addRow("Y:", self.y_pos_label)
        dro_layout.addRow("Z:", self.z_pos_label)
        dro_group.setLayout(dro_layout)
        middle_column_layout.addWidget(dro_group)

        wpos_dro_group = QGroupBox("DRO (Work Pos)")
        wpos_dro_layout = QFormLayout()
        self.wpos_x_label, self.wpos_y_label, self.wpos_z_label = QLabel("0.000"), QLabel("0.000"), QLabel("0.000")
        wpos_dro_layout.addRow("X:", self.wpos_x_label)
        wpos_dro_layout.addRow("Y:", self.wpos_y_label)
        wpos_dro_layout.addRow("Z:", self.wpos_z_label)
        wpos_dro_group.setLayout(wpos_dro_layout)
        middle_column_layout.addWidget(wpos_dro_group)

        main_layout.addLayout(middle_column_layout)

        # --- Right Column (Jogging) ---
        right_column_layout = QVBoxLayout()
        
        jog_group = QGroupBox("Jogging")
        jog_layout = QGridLayout()
        jog_layout.setSpacing(0)
        jog_group.setLayout(jog_layout)
        jog_group.layout().setContentsMargins(10,10,10,10)
        self.step_size_combo = QComboBox()
        self.step_size_combo.addItems(["0.1", "1", "10", "100"])
        self.step_size_combo.setMinimumWidth(40)
        self.step_size_combo.setMinimumHeight(40)
        self.y_plus_button, self.y_minus_button = QPushButton("Y+"), QPushButton("Y-")
        self.x_minus_button, self.x_plus_button = QPushButton("X-"), QPushButton("X+")
        self.z_plus_button, self.z_minus_button = QPushButton("Z+"), QPushButton("Z-")
        for button in [self.y_plus_button, self.y_minus_button, self.x_minus_button, self.x_plus_button, self.z_plus_button, self.z_minus_button]:
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
        right_column_layout.addStretch(1)
        main_layout.addLayout(right_column_layout)

    def build_gcode_tab(self):
        gcode_tab = QWidget()
        gcode_layout = QVBoxLayout(gcode_tab)
        self.tabs.addTab(gcode_tab, "G-Code Sender")
        gcode_group = QGroupBox("G-Code File")
        gcode_group_layout = QVBoxLayout()
        gcode_file_layout = QHBoxLayout()
        self.load_file_button = QPushButton("Load File")
        self.gcode_file_label = QLabel("No file loaded.")
        gcode_file_layout.addWidget(self.load_file_button)
        gcode_file_layout.addWidget(self.gcode_file_label, 1)
        self.gcode_progress = QProgressBar()
        gcode_actions_layout = QHBoxLayout()
        self.start_button, self.pause_button, self.stop_button = QPushButton("Start"), QPushButton("Pause"), QPushButton("Stop")
        gcode_actions_layout.addWidget(self.start_button)
        gcode_actions_layout.addWidget(self.pause_button)
        gcode_actions_layout.addWidget(self.stop_button)
        gcode_actions_layout.addStretch()
        gcode_group_layout.addLayout(gcode_file_layout)
        gcode_group_layout.addWidget(self.gcode_progress)
        gcode_group_layout.addLayout(gcode_actions_layout)
        gcode_group.setLayout(gcode_group_layout)
        gcode_layout.addWidget(gcode_group)
        gcode_layout.addStretch()

    def build_console_tab(self):
        console_tab = QWidget()
        console_layout = QVBoxLayout(console_tab)
        self.tabs.addTab(console_tab, "Console")
        input_layout = QHBoxLayout()
        self.command_input = QLineEdit()
        self.send_button = QPushButton("Send")
        self.filter_ok_checkbox = QCheckBox("Filter ok/?")
        self.filter_pos_checkbox = QCheckBox("Filter position")
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

        # --- Left Column ---
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
        probe_fields = [
            self.probe_dist_input, self.probe_feed_input,
            self.slow_probe_feed_input, self.probe_retract_input,
            self.probe_thickness_input, self.tool_radius_input
        ]
        self.numpad_enabled_fields.extend(probe_fields)
        for field in probe_fields:
            field.installEventFilter(self)
        left_column_layout.addStretch(1)

        # --- Right Column (GRBL Settings) ---
        self.initial_grbl_settings = {}
        self.grbl_setting_widgets = {}
        grbl_group = QGroupBox("GRBL Settings")
        self.grbl_layout = QGridLayout()
        read_button = QPushButton("Read Settings From Machine")
        read_button.clicked.connect(lambda: self.send_command("$$"))
        self.grbl_layout.addWidget(read_button, 0, 0, 1, 4)
        grbl_group.setLayout(self.grbl_layout)

        # Add columns to main layout
        layout.addWidget(left_column_widget, 1)
        layout.addWidget(grbl_group, 2)

        # --- Save Button ---
        save_button = QPushButton("Save All Settings")
        save_button.clicked.connect(self.save_settings)
        tab_layout.addWidget(save_button)

        self.load_settings()

    def connect_signals(self):
        self.refresh_button.clicked.connect(self.populate_ports)
        self.connect_button.clicked.connect(self.toggle_connection)
        self.x_plus_button.clicked.connect(lambda: self.send_jog_command("X", 1, self.x_plus_button))
        self.x_minus_button.clicked.connect(lambda: self.send_jog_command("X", -1, self.x_minus_button))
        self.y_plus_button.clicked.connect(lambda: self.send_jog_command("Y", 1, self.y_plus_button))
        self.y_minus_button.clicked.connect(lambda: self.send_jog_command("Y", -1, self.y_minus_button))
        self.z_plus_button.clicked.connect(lambda: self.send_jog_command("Z", 1, self.z_plus_button))
        self.z_minus_button.clicked.connect(lambda: self.send_jog_command("Z", -1, self.z_minus_button))
        self.load_file_button.clicked.connect(self.load_gcode_file)
        self.start_button.clicked.connect(self.start_gcode)
        self.pause_button.clicked.connect(self.pause_gcode)
        self.stop_button.clicked.connect(self.stop_gcode)
        self.home_button.clicked.connect(self.run_homing_cycle)
        self.unlock_button.clicked.connect(lambda: self.send_command("$X"))
        self.set_location_button.clicked.connect(self.set_location)
        self.go_to_location_button.clicked.connect(self.go_to_location)
        self.run_probe_button.clicked.connect(self.run_probe_cycle)
        self.run_3axis_probe_button.clicked.connect(self.run_3axis_probe_cycle)
        self.spindle_on_button.clicked.connect(self.spindle_on)
        self.spindle_off_button.clicked.connect(lambda: self.send_command("M5"))
        self.exit_button.clicked.connect(self.close)
        self.shutdown_button.clicked.connect(self.shutdown_pi)
        self.e_stop_button.clicked.connect(self.emergency_stop)
        self.grbl_setting_received.connect(self.update_grbl_setting)
        self.send_button.clicked.connect(self.send_console_command)
        self.command_input.returnPressed.connect(self.send_console_command)

    def log_to_console(self, message):
        if self.filter_ok_checkbox.isChecked() and (message == 'RX: ok' or message == 'TX: ?'):
            return
        if self.filter_pos_checkbox.isChecked() and message.startswith('RX: <') and 'MPos:' in message:
            return
        self.console_output.moveCursor(QTextCursor.Start)
        self.console_output.insertPlainText(message + '\n')

    def handle_serial_data(self, data):
        self.log_to_console(f"RX: {data}")
        if data.startswith("<"):
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
                        if alarm_match:
                            self.current_alarm_code = int(alarm_match.group(1))
                        self.is_probing = False
                    else:
                        self.current_alarm_code = None
                    self.update_ui_states()

            probe_match = re.search(r"\|Pn:([^|]+)", data)
            probe_triggered = False
            if probe_match:
                if 'P' in probe_match.group(1):
                    probe_triggered = True
            self.last_probe_state = probe_triggered
            self.probe_status_changed.emit(probe_triggered)

            pos_match = re.search(r"MPos:([\d.-]+),([\d.-]+),([\d.-]+)", data)
            if pos_match:
                self.mpos_x, self.mpos_y, self.mpos_z = (float(c) for c in pos_match.groups())
                self.x_pos_label.setText(f"{self.mpos_x:.3f}")
                self.y_pos_label.setText(f"{self.mpos_y:.3f}")
                self.z_pos_label.setText(f"{self.mpos_z:.3f}")

                wco_match = re.search(r"WCO:([\d.-]+),([\d.-]+),([\d.-]+)", data)
                if wco_match:
                    self.wco_x, self.wco_y, self.wco_z = (float(c) for c in wco_match.groups())

                wpos_x = self.mpos_x - self.wco_x
                wpos_y = self.mpos_y - self.wco_y
                wpos_z = self.mpos_z - self.wco_z
                self.wpos_x_label.setText(f"{wpos_x:.3f}")
                self.wpos_y_label.setText(f"{wpos_y:.3f}")
                self.wpos_z_label.setText(f"{wpos_z:.3f}")

        elif data.lower() == "ok":
            if self.is_advanced_probing:
                self.send_next_probe_command()
            elif self.gcode_is_running:
                self.send_next_gcode_line()
        elif data.startswith("error:15"):
            if self.last_jog_button:
                self.flash_jog_button(self.last_jog_button)
                self.last_jog_button = None # Reset it
            self.log_to_console(f"ERROR: {self.alarm_codes.get(15, 'Jog target exceeds machine travel.')}")
        elif data.startswith("ALARM:"):
            try:
                code = int(data.split(':')[1])
                if code == 15 and self.last_jog_button:
                    self.flash_jog_button(self.last_jog_button)
                    self.last_jog_button = None
                else:
                    self.current_alarm_code = code
                    self.machine_state = "Alarm"
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
                if prb_match:
                    if self.probe_response_count > 1: # Ignore the first fast probe result
                        if self.xyz_probe_stage == 'Z':
                            val = float(prb_match.group(3))
                        elif self.xyz_probe_stage == 'X':
                            val = float(prb_match.group(1))
                        elif self.xyz_probe_stage == 'Y':
                            val = float(prb_match.group(2))
                        else: # Fallback for old probe cycle
                            val = float(prb_match.group(3))
                        self.probe_results.append(val)
            else:
                self.is_probing = False
                self.probe_succeeded = True
                self.update_ui_states()
                probe_thickness = float(self.settings.value("probe/thickness", 1.0))
                self.send_command(f"G10 L2 P1 Z{probe_thickness}")
                self.log_to_console(f"INFO: Probe successful. Z-axis zeroed to {probe_thickness}mm.")

    def run_probe_cycle(self):
        self.is_manually_zeroed = False
        self.z_is_auto_zeroed = False
        # --- Step 2: Verify tool is armed ---
        arm_dialog = ProbeArmDialog(self)
        arm_dialog.e_stop_button.clicked.connect(self.emergency_stop)
        self.probe_status_changed.connect(arm_dialog.update_probe_status)
        self.send_command("?")

        try:
            result = arm_dialog.exec_()
            if result != QDialog.Accepted:
                return
        finally:
            self.probe_status_changed.disconnect(arm_dialog.update_probe_status)

        # --- Command Queue Phase ---
        self.dro_timer.stop()

        # --- Step 4: Build and Run the Advanced Probe Sequence ---
        self.is_probing = True
        self.is_advanced_probing = True
        self.probe_phase = 'probing'
        self.probe_succeeded = False
        self.probe_results = []
        self.probe_response_count = 0
        self.update_ui_states()

        try:
            fast_feed = float(self.settings.value("probe/feedrate", "25"))
            slow_feed = float(self.settings.value("probe/slow_feedrate", "10"))
            retract_dist = float(self.settings.value("probe/retract_dist", "2"))
            probe_dist = float(self.settings.value("probe/distance", "-25"))
        except (ValueError, TypeError):
            QMessageBox.critical(self, "Probe Error", "Invalid probe settings. Please check values in the Settings tab.")
            self.is_probing = False
            self.is_advanced_probing = False
            self.update_ui_states()
            self.dro_timer.start()
            return

        self.probe_command_queue = [
            "G91", f"G38.2 Z{probe_dist} F{fast_feed}", "G90",
            "G91", f"G0 Z{retract_dist}", "G90",
            "G91", f"G38.2 Z{probe_dist} F{slow_feed}", "G90",
            "G91", f"G0 Z{retract_dist}", "G90",
            "G91", f"G38.2 Z{probe_dist} F{slow_feed}", "G90",
            "G91", f"G0 Z{retract_dist}", "G90",
            "G91", f"G38.2 Z{probe_dist} F{slow_feed}", "G90",
        ]

        self.send_next_probe_command()

    def send_next_probe_command(self):
        if self.probe_command_queue:
            command = self.probe_command_queue.pop(0)
            self.send_command(command)
        else:
            if self.probe_phase == 'probing':
                self.start_probe_finalization()
            elif self.probe_phase == 'finalizing':
                if self.xyz_probe_stage in ['X_TRANSITION', 'Y_TRANSITION', 'FINALIZE']:
                    self.handle_probe_transition()
                else:
                    self.end_probe_cycle()

    def start_probe_finalization(self):
        if len(self.probe_results) != 3:
            self.log_to_console(f"ERROR: Advanced probe failed. Expected 3 results, got {len(self.probe_results)}.")
            self.probe_succeeded = False
            self.end_probe_cycle()
            return

        self.probe_phase = 'finalizing'
        avg_pos = sum(self.probe_results) / len(self.probe_results)

        try:
            probe_thickness = float(self.settings.value("probe/thickness", 1.0))
            tool_radius = float(self.settings.value("probe/tool_radius", 3.15))
        except (ValueError, TypeError):
            QMessageBox.critical(self, "Probe Error", "Invalid Probe Thickness or Tool Radius setting.")
            self.end_probe_cycle()
            return

        if not self.xyz_probe_stage or self.xyz_probe_stage == 'Z':
            final_offset = avg_pos - probe_thickness
            self.log_to_console(f"INFO: Z-Probe successful. Average: {avg_pos:.4f}mm. Setting Z-Work-Offset.")

            if not self.xyz_probe_stage: # Standard Z-Probe
                safe_retract_height = probe_thickness + 10
                self.probe_command_queue = [f"G10 L2 P1 Z{final_offset:.4f}", f"G90 G0 Z{safe_retract_height}"]
            else: # 3-Axis Z-Probe
                self.probe_command_queue = [
                    f"G10 L2 P1 Z{final_offset:.4f}",
                    "G91 G0 Z30",
                    "G91 G0 X-25"
                ]
                self.xyz_probe_stage = 'X_TRANSITION'
            self.send_next_probe_command()

        elif self.xyz_probe_stage == 'X':
            # Note: Probing is in the +X direction. The tool is to the left of the probe plate.
            # The probed X position is workpiece_edge_X + tool_radius.
            # Therefore, workpiece_edge_X = probed_X - tool_radius.
            # The user has requested avg_pos + tool_radius, which is implemented below.
            # This will likely result in the work offset being set incorrectly.
            final_offset = avg_pos + tool_radius
            self.log_to_console(f"INFO: X-Probe successful. Average: {avg_pos:.4f}mm. Setting X-Work-Offset.")
            self.probe_command_queue = [
                f"G10 L2 P1 X{final_offset:.4f}",
                "G91 G0 X-30",
                "G91 G0 Y25"
            ]
            self.xyz_probe_stage = 'Y_TRANSITION'
            self.send_next_probe_command()
        elif self.xyz_probe_stage == 'Y':
            final_offset = avg_pos + tool_radius
            self.log_to_console(f"INFO: Y-Probe successful. Average: {avg_pos:.4f}mm. Setting Y-Work-Offset.")
            self.probe_command_queue = [
                f"G10 L2 P1 Y{final_offset:.4f}"
            ]
            self.xyz_probe_stage = 'FINALIZE'
            self.send_next_probe_command()

    def handle_probe_transition(self):
        if self.xyz_probe_stage == 'X_TRANSITION':
            msg = "Probe Z complete. Reposition probe for X-axis probing (to the right of the tool) and press OK."
            QMessageBox.information(self, "Probe Reposition", msg)
            self.xyz_probe_stage = 'X'
            self.execute_probe_stage()
        elif self.xyz_probe_stage == 'Y_TRANSITION':
            msg = "Probe X complete. Reposition probe for Y-axis probing (in front of the tool) and press OK."
            QMessageBox.information(self, "Probe Reposition", msg)
            self.xyz_probe_stage = 'Y'
            self.execute_probe_stage()
        elif self.xyz_probe_stage == 'FINALIZE':
            self.log_to_console("INFO: 3-Axis Probing Complete. Finalizing...")
            try:
                z_max = self.grbl_setting_widgets['$132'].text()
            except KeyError:
                self.log_to_console("WARN: Z-Max ($132) not available. Reading from machine.")
                self.send_command("$$")
                QMessageBox.warning(self, "Z-Max Required", "Could not determine Z-Max ($132). Please ensure settings have been read from the machine, then try again.")
                self.end_probe_cycle()
                return

            self.probe_command_queue = [
                f"G90 G0 Z{z_max}",
                "G90 G0 X0 Y0"
            ]
            self.xyz_probe_stage = 'DONE'
            self.send_next_probe_command()

    def end_probe_cycle(self):
        if self.probe_phase == 'finalizing':
            self.probe_succeeded = True
            self.z_is_auto_zeroed = True

        self.is_probing = False
        self.is_advanced_probing = False
        self.probe_phase = None
        self.xyz_probe_stage = None
        self.probe_command_queue = []
        self.probe_results = []
        self.probe_response_count = 0

        self.dro_timer.start()

        self.update_ui_states()

    def run_3axis_probe_cycle(self):
        self.is_manually_zeroed = False
        self.z_is_auto_zeroed = False

        arm_dialog = ProbeArmDialog(self)
        arm_dialog.e_stop_button.clicked.connect(self.emergency_stop)
        self.probe_status_changed.connect(arm_dialog.update_probe_status)
        self.send_command("?")

        try:
            result = arm_dialog.exec_()
            if result != QDialog.Accepted:
                return
        finally:
            self.probe_status_changed.disconnect(arm_dialog.update_probe_status)

        self.dro_timer.stop()
        self.is_probing = True
        self.is_advanced_probing = True
        self.probe_succeeded = False
        self.probe_results = []
        self.probe_response_count = 0

        self.xyz_probe_stage = 'Z'
        self.execute_probe_stage()
        self.update_ui_states()

    def execute_probe_stage(self):
        self.probe_phase = 'probing'
        self.probe_results = []
        self.probe_response_count = 0

        try:
            fast_feed = float(self.settings.value("probe/feedrate", "25"))
            slow_feed = float(self.settings.value("probe/slow_feedrate", "10"))
            retract_dist = float(self.settings.value("probe/retract_dist", "2"))
            probe_dist = float(self.settings.value("probe/distance", "-25"))
        except (ValueError, TypeError):
            QMessageBox.critical(self, "Probe Error", "Invalid probe settings. Please check values in the Settings tab.")
            self.end_probe_cycle()
            return

        axis = self.xyz_probe_stage

        if axis == 'Z':
            p_dist = probe_dist
            r_dist = retract_dist
        else:
            p_dist = abs(probe_dist)
            r_dist = -retract_dist

        probe_commands = [
            f"G91 G38.2 {axis}{p_dist} F{fast_feed}",
            f"G91 G0 {axis}{r_dist}",
            f"G91 G38.2 {axis}{p_dist} F{slow_feed}",
            f"G91 G0 {axis}{r_dist}",
            f"G91 G38.2 {axis}{p_dist} F{slow_feed}",
            f"G91 G0 {axis}{r_dist}",
            f"G91 G38.2 {axis}{p_dist} F{slow_feed}",
        ]

        if axis == 'Y':
            self.probe_command_queue = ["G91 G0 X45"] + probe_commands
        else:
            self.probe_command_queue = probe_commands

        self.send_next_probe_command()

    def run_homing_cycle(self):
        self.is_homed = False
        self.probe_succeeded = False
        self.is_manually_zeroed = False
        self.z_is_auto_zeroed = False
        self.home_pulse_timer.start()
        self.send_command("$H")

    def set_location(self):
        locations = [f"Work Origin G{54+i} (P{i+1})" for i in range(6)] + ["Safe Position (G28.1)"]
        prompt = "Select which location you would like to set:"
        choice_index = LocationDialog.get_selected_index(self, "Set Location", locations, prompt)

        if choice_index == -1:
            return # User cancelled

        if choice_index < 6: # Corresponds to G54-G59
            p_number = choice_index + 1
            command = f"G10 L2 P{p_number} X{self.mpos_x} Y{self.mpos_y} Z{self.mpos_z}"
            self.send_command(command)
            self.log_to_console(f"INFO: Set work origin for G{53 + p_number} (P{p_number}).")
        else: # Corresponds to Safe Position
            self.send_command("G28.1")
            self.log_to_console("INFO: Current position saved as safe position (G28).")

    def go_to_location(self):
        locations = [f"Work Origin G{54+i}" for i in range(6)] + ["Safe Position (G28)"]
        prompt = "Select which location you would like to go to:"
        choice_index = LocationDialog.get_selected_index(self, "Go To Location", locations, prompt)

        if choice_index == -1:
            return # User cancelled

        if choice_index < 6: # Corresponds to G54-G59
            wcs_command = f"G{54+choice_index}"
            self.send_command(wcs_command)
            self.send_command("G90 G0 X0 Y0")
        else: # Corresponds to Safe Position
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
            self.update_ui_states()

    def update_ui_states(self):
        is_connected = bool(self.serial_connection and self.serial_connection.is_open)
        file_loaded = bool(self.gcode_lines)
        self.start_button.setEnabled(is_connected and file_loaded and not self.gcode_is_running)
        self.pause_button.setEnabled(is_connected and self.gcode_is_running)
        self.stop_button.setEnabled(is_connected and self.gcode_is_running)
        for button in [self.home_button, self.unlock_button, self.run_probe_button, self.run_3axis_probe_button, self.set_location_button, self.go_to_location_button, self.e_stop_button, self.spindle_on_button, self.spindle_off_button, self.spindle_speed_input]:
            button.setEnabled(is_connected)
        self.pause_button.setText("Resume" if self.gcode_is_paused else "Pause")

        self.home_pulse_timer.stop()
        self.alarm_pulse_timer.stop()
        self.home_button.setStyleSheet("")
        self.unlock_button.setStyleSheet("")
        self.run_probe_button.setStyleSheet("")


        if not is_connected:
            self.is_homed = False
            self.is_manually_zeroed = False

        # --- HOME BUTTON ---
        if self.machine_state == "Home":
            self.home_pulse_timer.start()
        else:
            if self.is_homed:
                self.home_button.setText("Homed")
                self.home_button.setStyleSheet("background-color: darkgreen; color: white; font-weight: bold;")
            else:
                self.home_button.setText("Home ($H)")

        # --- UNLOCK BUTTON ---
        if self.machine_state == "Alarm":
            self.alarm_pulse_timer.start()
            if self.current_alarm_code in self.alarm_codes:
                alarm_message = self.alarm_codes[self.current_alarm_code]
                self.unlock_button.setText(f"ALARM: {alarm_message}")
            else:
                self.unlock_button.setText("UNLOCK")
            self.is_homed = False
        else:
            if is_connected:
                self.unlock_button.setText("No Alarm")
                self.unlock_button.setStyleSheet("background-color: darkgreen; color: white; font-weight: bold;")
            else:
                self.unlock_button.setText("Unlock ($X)")

        # --- SET ZERO BUTTON ---
        # This logic has been removed and replaced by the new unified
        # "Set Location" and "Go To Location" buttons.

        # --- PROBE BUTTON ---
        if self.machine_state == "Alarm":
            self.run_probe_button.setEnabled(False)
            self.run_probe_button.setText("Unlock to Probe")
            self.run_3axis_probe_button.setEnabled(False)
            self.run_3axis_probe_button.setText("Unlock to Probe")
        elif self.is_probing:
            self.run_probe_button.setEnabled(False)
            self.run_3axis_probe_button.setEnabled(False)
            if self.xyz_probe_stage:
                self.run_probe_button.setText("Probing...")
                self.run_3axis_probe_button.setText(f"Probing {self.xyz_probe_stage}...")
            else:
                self.run_probe_button.setText("Probing...")
                self.run_3axis_probe_button.setText("Probing...")
        elif self.z_is_auto_zeroed:
            self.run_probe_button.setText("Z Zeroed")
            self.run_probe_button.setStyleSheet("background-color: darkgreen; color: white; font-weight: bold;")
            self.run_probe_button.setEnabled(is_connected)
            self.run_3axis_probe_button.setEnabled(is_connected)
            self.run_3axis_probe_button.setText("3-Axis XYZ Probe")
        else:
            self.run_probe_button.setText("Auto Zero Z")
            self.run_probe_button.setEnabled(is_connected)
            self.run_3axis_probe_button.setText("3-Axis XYZ Probe")
            self.run_3axis_probe_button.setEnabled(is_connected)


    def start_gcode(self):
        if self.gcode_lines:
            self.probe_succeeded = False
            self.is_manually_zeroed = False
            self.gcode_is_running, self.gcode_is_paused, self.gcode_current_line = True, False, 0
            self.update_ui_states()
            self.send_next_gcode_line()

    def pause_gcode(self):
        if self.gcode_is_running:
            self.gcode_is_paused = not self.gcode_is_paused
            self.send_command("!" if self.gcode_is_paused else "~")
            self.update_ui_states()

    def emergency_stop(self):
        self.send_command("\x18")
        self.gcode_is_running, self.gcode_is_paused, self.gcode_current_line = False, False, 0
        self.gcode_progress.setValue(0)
        self.update_ui_states()

    def spindle_on(self):
        try: self.send_command(f"M3 S{int(self.spindle_speed_input.text())}")
        except ValueError: self.log_to_console("INFO: Invalid spindle speed.")

    def stop_gcode(self):
        self.emergency_stop()

    def send_next_gcode_line(self):
        if self.gcode_is_running and not self.gcode_is_paused:
            if self.gcode_current_line < len(self.gcode_lines):
                self.send_command(self.gcode_lines[self.gcode_current_line])
                self.gcode_progress.setValue(self.gcode_current_line + 1)
                self.gcode_current_line += 1
            else:
                self.gcode_is_running = False
                self.update_ui_states()
                self.log_to_console("INFO: G-code sending finished.")

    def send_command(self, command):
        if self.serial_connection and self.serial_connection.is_open:
            self.log_to_console(f"TX: {command}")
            self.serial_connection.write((command + '\n').encode('utf-8'))
        else:
            self.log_to_console(f"INFO: Not connected. Command '{command}' not sent.")

    def send_console_command(self):
        command = self.command_input.text()
        if command:
            self.send_command(command)
            self.command_input.clear()

    def send_jog_command(self, axis, direction, button):
        self.last_jog_button = button
        self.is_manually_zeroed = False
        step = float(self.step_size_combo.currentText())
        self.send_command(f"$J=G91 G21 {axis}{step * direction} F1000")

    def populate_ports(self):
        self.port_combobox.clear()
        self.port_combobox.addItems([port.device for port in serial.tools.list_ports.comports()])

    def toggle_connection(self):
        if self.serial_connection and self.serial_connection.is_open: self.disconnect_serial()
        else: self.connect_serial()

    def connect_serial(self):
        port, baud = self.port_combobox.currentText(), int(self.baud_combobox.currentText())
        if not port: return
        try:
            self.serial_connection = serial.Serial(port, baud, timeout=1)
            time.sleep(2)
            self.serial_connection.write(b"\r\n\r\n")
            self.serial_connection.flushInput()
            self.serial_thread = QThread()
            self.serial_worker = SerialWorker(self.serial_connection)
            self.serial_worker.moveToThread(self.serial_thread)
            self.serial_thread.started.connect(self.serial_worker.run)
            self.serial_worker.serial_data_received.connect(self.handle_serial_data)
            self.serial_thread.start()
            self.dro_timer.start()
            self.connect_button.setText("Disconnect")
            self.update_connection_indicator(True)
        except (serial.SerialException, FileNotFoundError) as e:
            self.log_to_console(f"ERROR: Failed to connect - {e}")
            self.update_connection_indicator(False)
        self.update_ui_states()

    def disconnect_serial(self):
        self.dro_timer.stop()
        if self.serial_thread: self.serial_worker.stop(); self.serial_thread.quit(); self.serial_thread.wait()
        if self.serial_connection: self.serial_connection.close()
        self.connect_button.setText("Connect")
        self.serial_connection = self.serial_thread = self.serial_worker = None
        self.update_connection_indicator(False)
        self.update_ui_states()

    def pulse_home_button(self):
        self.home_button.setText("Homing")
        self.home_pulse_state = 1 - self.home_pulse_state
        self.home_button.setStyleSheet(f"background-color: {'#4CAF50' if self.home_pulse_state == 0 else '#8BC34A'}; color: white;")

    def pulse_alarm_button(self):
        if self.current_alarm_code in self.alarm_codes:
            alarm_message = self.alarm_codes[self.current_alarm_code]
            base_text = f"ALARM: {alarm_message}"
        else:
            base_text = "UNLOCK"
        self.unlock_button.setText(base_text)
        self.alarm_pulse_state = 1 - self.alarm_pulse_state
        self.unlock_button.setStyleSheet(f"background-color: {'#F44336' if self.alarm_pulse_state == 0 else '#FF7043'}; color: white; font-weight: bold;")

    def update_connection_indicator(self, is_connected):
        self.connection_status_indicator.setText("Connected" if is_connected else "Disconnected")
        self.connection_status_indicator.setStyleSheet(f"background-color: {'green' if is_connected else 'red'}; color: white; font-weight: bold;")

    def load_settings(self):
        defaults = {
            "probe/distance": "-25",
            "probe/feedrate": "25",
            "probe/thickness": "1.0",
            "probe/slow_feedrate": "10",
            "probe/retract_dist": "2",
            "probe/tool_radius": "3.15"
        }
        for key, widget in self.get_settings_widgets().items():
            widget.setText(self.settings.value(key, defaults.get(key)))

    def save_settings(self):
        for key, widget in self.get_settings_widgets().items():
            self.settings.setValue(key, widget.text())
        for setting, field in self.get_grbl_fields().items():
            if field.text() != self.initial_grbl_settings.get(setting, ''):
                self.send_command(f"{setting}={field.text()}")
        self.log_to_console("INFO: Settings saved.")

    def update_grbl_setting(self, setting, value):
        self.initial_grbl_settings[setting] = value
        if setting in self.grbl_setting_widgets:
            self.grbl_setting_widgets[setting].setText(value)
        else:
            setting_info = self.GRBL_SETTINGS_INFO.get(setting)
            if not setting_info:
                label_text = f"{setting}:"
                tooltip_text = "No description available."
            else:
                label_text = f"{setting_info['label']}:"
                tooltip_text = setting_info['tooltip']

            label = QLabel(label_text)
            field = QLineEdit(value)
            field.setToolTip(tooltip_text)
            field.installEventFilter(self)

            row = (self.grbl_settings_count // 2) + 1
            col = self.grbl_settings_count % 2
            self.grbl_layout.addWidget(label, row, col * 2)
            self.grbl_layout.addWidget(field, row, col * 2 + 1)
            self.grbl_setting_widgets[setting] = field
            self.numpad_enabled_fields.append(field)
            self.grbl_settings_count += 1

    def get_settings_widgets(self):
        return {
            "probe/distance": self.probe_dist_input,
            "probe/feedrate": self.probe_feed_input,
            "probe/thickness": self.probe_thickness_input,
            "probe/slow_feedrate": self.slow_probe_feed_input,
            "probe/retract_dist": self.probe_retract_input,
            "probe/tool_radius": self.tool_radius_input
        }

    def get_grbl_fields(self):
        return self.grbl_setting_widgets

    def show_number_pad(self, line_edit):
        dialog = NumberPadDialog(line_edit.text(), self)
        if dialog.exec_() == QDialog.Accepted:
            new_value = dialog.get_value()
            line_edit.setText(new_value)
        line_edit.clearFocus()

    def flash_jog_button(self, button):
        original_text = button.text()
        original_stylesheet = button.styleSheet()
        button.setText("Soft Limit")
        button.setStyleSheet("background-color: red; color: white; font-weight: bold;")
        QTimer.singleShot(2000, lambda: self.restore_jog_button(button, original_text, original_stylesheet))

    def restore_jog_button(self, button, text, stylesheet):
        button.setText(text)
        button.setStyleSheet(stylesheet)

    def shutdown_pi(self):
        if QMessageBox.question(self, 'Confirm Shutdown', "Are you sure?", QMessageBox.Yes | QMessageBox.No, QMessageBox.No) == QMessageBox.Yes:
            os.system("sudo shutdown -h now")

    def closeEvent(self, event):
        self.disconnect_serial()
        super().closeEvent(event)

    def eventFilter(self, obj, event):
        if event.type() == QEvent.FocusIn:
            if isinstance(obj, QLineEdit) and obj in self.numpad_enabled_fields:
                obj.setReadOnly(True)
                self.show_number_pad(obj)
                return True
        elif event.type() == QEvent.FocusOut:
            if isinstance(obj, QLineEdit) and obj in self.numpad_enabled_fields:
                obj.setReadOnly(False)
        return super().eventFilter(obj, event)

if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    window = MainWindow()
    window.show()
    sys.exit(app.exec_())