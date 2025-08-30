import sys
import serial.tools.list_ports
import re
import time
import os
from PySide2.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
                               QComboBox, QPushButton, QLabel, QGroupBox, QGridLayout,
                               QProgressBar, QFileDialog, QTextEdit, QLineEdit, QTabWidget,
                               QMessageBox, QFormLayout)
from PySide2.QtCore import Qt, QThread, QObject, Signal, QTimer, QSettings

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

    def __init__(self):
        super().__init__()
        self.setWindowTitle("PiGRBL CNC Controller")
        self.resize(800, 480)

        self.settings = QSettings("MyCompany", "PiGRBLCNC")

        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)

        # --- Top Bar ---
        top_bar_layout = QHBoxLayout()
        self.e_stop_button = QPushButton("EMERGENCY STOP")
        self.e_stop_button.setStyleSheet("background-color: red; color: white; font-weight: bold;")
        self.e_stop_button.setFixedHeight(40)
        top_bar_layout.addWidget(self.e_stop_button)

        connection_group = QGroupBox("Connection")
        connection_layout = QHBoxLayout()
        self.connect_button = QPushButton("Connect")
        connection_layout.addWidget(self.connect_button)
        connection_group.setLayout(connection_layout)
        top_bar_layout.addWidget(connection_group)

        self.connection_status_indicator = QPushButton("Disconnected")
        self.connection_status_indicator.setCheckable(False)
        self.connection_status_indicator.setEnabled(False) # Make it non-interactive
        top_bar_layout.addWidget(self.connection_status_indicator)

        top_bar_layout.addStretch()

        system_buttons_layout = QVBoxLayout()
        self.exit_button = QPushButton("Exit Application")
        self.shutdown_button = QPushButton("Shutdown Pi")
        system_buttons_layout.addWidget(self.exit_button)
        system_buttons_layout.addWidget(self.shutdown_button)
        top_bar_layout.addLayout(system_buttons_layout)
        main_layout.addLayout(top_bar_layout)

        # --- Main Tabs ---
        self.tabs = QTabWidget()
        main_layout.addWidget(self.tabs)
        self.build_manual_control_tab()
        self.build_gcode_tab()
        self.build_console_tab()
        self.build_settings_tab()

        # --- Connections ---
        self.connect_signals()

        # --- Initial State ---
        self.serial_connection = None
        self.serial_thread = None
        self.serial_worker = None
        self.gcode_lines = []
        self.gcode_current_line = 0
        self.gcode_is_running = False
        self.gcode_is_paused = False
        self.machine_state = "Unknown"
        self.populate_ports()
        self.update_ui_states()

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

    def build_manual_control_tab(self):
        manual_tab = QWidget()
        manual_layout = QHBoxLayout(manual_tab)
        self.tabs.addTab(manual_tab, "Manual Control")

        jog_group = QGroupBox("Jogging")
        jog_layout = QGridLayout()
        self.step_size_combo = QComboBox()
        self.step_size_combo.addItems(["0.1", "1", "10", "100"])
        jog_layout.addWidget(QLabel("Step (mm):"), 0, 0)
        jog_layout.addWidget(self.step_size_combo, 0, 1)
        self.y_plus_button, self.y_minus_button = QPushButton("Y+"), QPushButton("Y-")
        self.x_minus_button, self.x_plus_button = QPushButton("X-"), QPushButton("X+")
        self.z_plus_button, self.z_minus_button = QPushButton("Z+"), QPushButton("Z-")

        for button in [self.y_plus_button, self.y_minus_button, self.x_minus_button,
                       self.x_plus_button, self.z_plus_button, self.z_minus_button]:
            button.setMinimumSize(60, 60) # Make buttons larger for touch

        jog_layout.addWidget(self.y_plus_button, 1, 1)
        jog_layout.addWidget(self.y_minus_button, 3, 1)
        jog_layout.addWidget(self.x_minus_button, 2, 0)
        jog_layout.addWidget(self.x_plus_button, 2, 2)
        jog_layout.addWidget(self.z_plus_button, 1, 3)
        jog_layout.addWidget(self.z_minus_button, 3, 3)
        jog_group.setLayout(jog_layout)
        manual_layout.addWidget(jog_group)

        dro_group = QGroupBox("DRO (Machine Pos)")
        dro_layout = QFormLayout()
        self.x_pos_label, self.y_pos_label, self.z_pos_label = QLabel("0.000"), QLabel("0.000"), QLabel("0.000")
        dro_layout.addRow("X:", self.x_pos_label)
        dro_layout.addRow("Y:", self.y_pos_label)
        dro_layout.addRow("Z:", self.z_pos_label)
        dro_group.setLayout(dro_layout)
        manual_layout.addWidget(dro_group)

        manual_right_col_layout = QVBoxLayout()
        actions_group = QGroupBox("Actions")
        actions_layout = QVBoxLayout()
        self.home_button, self.unlock_button = QPushButton("Home ($H)"), QPushButton("Unlock ($X)")
        self.set_zero_button, self.run_probe_button = QPushButton("Set Zero (G10)"), QPushButton("Run Probing Cycle")
        actions_layout.addWidget(self.home_button)
        actions_layout.addWidget(self.unlock_button)
        actions_layout.addWidget(self.set_zero_button)
        actions_layout.addWidget(self.run_probe_button)
        actions_group.setLayout(actions_layout)
        manual_right_col_layout.addWidget(actions_group)

        spindle_group = QGroupBox("Spindle")
        spindle_layout = QFormLayout()
        self.spindle_speed_input = QLineEdit("1000")
        self.spindle_on_button, self.spindle_off_button = QPushButton("On (M3)"), QPushButton("Off (M5)")
        spindle_layout.addRow("Speed (RPM):", self.spindle_speed_input)
        spindle_layout.addRow(self.spindle_on_button, self.spindle_off_button)
        spindle_group.setLayout(spindle_layout)
        manual_right_col_layout.addWidget(spindle_group)
        manual_layout.addLayout(manual_right_col_layout)

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
        self.console_output = QTextEdit()
        self.console_output.setReadOnly(True)
        console_layout.addWidget(self.console_output)

    def build_settings_tab(self):
        self.settings_tab = QWidget()
        self.tabs.addTab(self.settings_tab, "Settings")
        layout = QVBoxLayout(self.settings_tab)

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
        layout.addWidget(connection_settings_group)

        probe_group = QGroupBox("Probe Settings")
        probe_layout = QFormLayout()
        self.probe_dist_input, self.probe_feed_input, self.probe_thickness_input = QLineEdit(), QLineEdit(), QLineEdit()
        probe_layout.addRow("Probe Travel (mm):", self.probe_dist_input)
        probe_layout.addRow("Probe Feed Rate:", self.probe_feed_input)
        probe_layout.addRow("Probe Thickness (mm):", self.probe_thickness_input)
        probe_group.setLayout(probe_layout)
        layout.addWidget(probe_group)

        self.initial_grbl_settings = {}
        grbl_group = QGroupBox("GRBL Settings")
        grbl_layout = QFormLayout()
        read_button = QPushButton("Read Settings From Machine")
        read_button.clicked.connect(lambda: self.send_command("$$"))
        grbl_layout.addWidget(read_button)
        self.max_spindle_speed_input, self.x_accel_input, self.y_accel_input, self.z_accel_input = QLineEdit(), QLineEdit(), QLineEdit(), QLineEdit()
        grbl_layout.addRow("Max Spindle ($30):", self.max_spindle_speed_input)
        grbl_layout.addRow("X Accel ($120):", self.x_accel_input)
        grbl_layout.addRow("Y Accel ($121):", self.y_accel_input)
        grbl_layout.addRow("Z Accel ($122):", self.z_accel_input)
        grbl_group.setLayout(grbl_layout)
        layout.addWidget(grbl_group)

        save_button = QPushButton("Save All Settings")
        save_button.clicked.connect(self.save_settings)
        layout.addWidget(save_button)
        layout.addStretch()
        self.load_settings()

    def connect_signals(self):
        self.refresh_button.clicked.connect(self.populate_ports)
        self.connect_button.clicked.connect(self.toggle_connection)
        self.x_plus_button.clicked.connect(lambda: self.send_jog_command("X", 1))
        self.x_minus_button.clicked.connect(lambda: self.send_jog_command("X", -1))
        self.y_plus_button.clicked.connect(lambda: self.send_jog_command("Y", 1))
        self.y_minus_button.clicked.connect(lambda: self.send_jog_command("Y", -1))
        self.z_plus_button.clicked.connect(lambda: self.send_jog_command("Z", 1))
        self.z_minus_button.clicked.connect(lambda: self.send_jog_command("Z", -1))
        self.load_file_button.clicked.connect(self.load_gcode_file)
        self.start_button.clicked.connect(self.start_gcode)
        self.pause_button.clicked.connect(self.pause_gcode)
        self.stop_button.clicked.connect(self.stop_gcode)
        self.home_button.clicked.connect(lambda: self.send_command("$H"))
        self.unlock_button.clicked.connect(lambda: self.send_command("$X"))
        self.set_zero_button.clicked.connect(lambda: self.send_command("G10 L20 P1 X0 Y0 Z0"))
        self.run_probe_button.clicked.connect(self.run_probe_cycle)
        self.spindle_on_button.clicked.connect(self.spindle_on)
        self.spindle_off_button.clicked.connect(lambda: self.send_command("M5"))
        self.exit_button.clicked.connect(self.close)
        self.shutdown_button.clicked.connect(self.shutdown_pi)
        self.e_stop_button.clicked.connect(self.emergency_stop)
        self.grbl_setting_received.connect(self.update_grbl_setting)

    def handle_serial_data(self, data):
        self.console_output.append(f"RX: {data}")
        if data.startswith("<"):
            # Extract machine state
            state_match = re.search(r"<(\w+)", data)
            if state_match:
                new_state = state_match.group(1)
                if new_state != self.machine_state:
                    self.machine_state = new_state
                    self.update_ui_states() # Update UI when state changes

            # Extract position
            match = re.search(r"MPos:([\d.-]+),([\d.-]+),([\d.-]+)", data)
            if match:
                x, y, z = match.groups()
                self.x_pos_label.setText(f"{float(x):.3f}")
                self.y_pos_label.setText(f"{float(y):.3f}")
                self.z_pos_label.setText(f"{float(z):.3f}")
        elif data.lower() == "ok":
            self.send_next_gcode_line()
        elif data.startswith("$"):
            parts = data.split("=")
            if len(parts) == 2:
                self.grbl_setting_received.emit(parts[0], parts[1])
        elif data.startswith("[PRB:"):
            probe_thickness = float(self.settings.value("probe/thickness", 1.0))
            self.send_command(f"G10 L20 P1 Z{probe_thickness}")
            self.console_output.append(f"INFO: Probe successful. Z-axis zeroed to {probe_thickness}mm.")

    def run_probe_cycle(self):
        probe_dist = self.settings.value("probe/distance", -25)
        probe_feed = self.settings.value("probe/feedrate", 100)
        self.send_command(f"G38.2 Z{probe_dist} F{probe_feed}")

    def load_gcode_file(self):
        filepath, _ = QFileDialog.getOpenFileName(self, "Load G-Code File", "", "G-Code Files (*.gcode *.nc);;All Files (*)")
        if filepath:
            with open(filepath, 'r') as f:
                self.gcode_lines = [line.strip() for line in f if line.strip() and not line.strip().startswith(';')]
            self.gcode_file_label.setText(filepath.split('/')[-1])
            self.gcode_current_line = 0
            self.gcode_progress.setMaximum(len(self.gcode_lines))
            self.gcode_progress.setValue(0)
            self.update_ui_states()

    def update_ui_states(self):
        is_connected = bool(self.serial_connection and self.serial_connection.is_open)
        file_loaded = bool(self.gcode_lines)
        self.start_button.setEnabled(is_connected and file_loaded and not self.gcode_is_running)
        self.pause_button.setEnabled(is_connected and self.gcode_is_running)
        self.stop_button.setEnabled(is_connected and self.gcode_is_running)
        self.home_button.setEnabled(is_connected)
        self.unlock_button.setEnabled(is_connected)
        self.set_zero_button.setEnabled(is_connected)
        self.e_stop_button.setEnabled(is_connected)
        self.spindle_on_button.setEnabled(is_connected)
        self.spindle_off_button.setEnabled(is_connected)
        self.spindle_speed_input.setEnabled(is_connected)
        self.run_probe_button.setEnabled(is_connected)
        if self.gcode_is_running and not self.gcode_is_paused:
            self.pause_button.setText("Pause")
        else:
            self.pause_button.setText("Resume")

        # Handle button animations based on machine state
        if self.machine_state == "Home":
            self.home_pulse_timer.start()
        else:
            self.home_pulse_timer.stop()
            # Set final color after homing or if not homing
            if "WCO" in self.console_output.toPlainText(): # A simple way to check if homing has been done
                 self.home_button.setStyleSheet("background-color: lightgreen;")
            else:
                 self.home_button.setStyleSheet("") # Reset to default

        if self.machine_state == "Alarm":
            self.alarm_pulse_timer.start()
        else:
            self.alarm_pulse_timer.stop()
            self.unlock_button.setStyleSheet("") # Reset to default

    def start_gcode(self):
        if self.gcode_lines:
            self.gcode_is_running = True
            self.gcode_is_paused = False
            self.gcode_current_line = 0
            self.update_ui_states()
            self.send_next_gcode_line()

    def pause_gcode(self):
        if not self.gcode_is_running:
            return
        self.gcode_is_paused = not self.gcode_is_paused
        if self.gcode_is_paused:
            self.send_command("!")
        else:
            self.send_command("~")
        self.update_ui_states()

    def emergency_stop(self):
        self.send_command("\x18")
        self.gcode_is_running = False
        self.gcode_is_paused = False
        self.gcode_current_line = 0
        self.gcode_progress.setValue(0)
        self.update_ui_states()

    def spindle_on(self):
        try:
            speed = int(self.spindle_speed_input.text())
            self.send_command(f"M3 S{speed}")
        except ValueError:
            self.console_output.append("INFO: Invalid spindle speed.")

    def stop_gcode(self):
        self.gcode_is_running = False
        self.gcode_is_paused = False
        self.send_command("\x18")
        self.gcode_current_line = 0
        self.gcode_progress.setValue(0)
        self.update_ui_states()

    def send_next_gcode_line(self):
        if not self.gcode_is_running or self.gcode_is_paused:
            return
        if self.gcode_current_line < len(self.gcode_lines):
            line = self.gcode_lines[self.gcode_current_line]
            self.send_command(line)
            self.gcode_progress.setValue(self.gcode_current_line + 1)
            self.gcode_current_line += 1
        else:
            self.gcode_is_running = False
            self.update_ui_states()
            self.console_output.append("INFO: G-code sending finished.")

    def send_command(self, command):
        if self.serial_connection and self.serial_connection.is_open:
            self.console_output.append(f"TX: {command}")
            self.serial_connection.write((command + '\n').encode('utf-8'))
        else:
            self.console_output.append(f"INFO: Not connected. Command '{command}' not sent.")

    def send_jog_command(self, axis, direction):
        step = float(self.step_size_combo.currentText())
        command = f"$J=G91 G21 {axis}{step * direction} F1000"
        self.send_command(command)

    def populate_ports(self):
        self.port_combobox.clear()
        ports = serial.tools.list_ports.comports()
        for port in ports:
            self.port_combobox.addItem(port.device)

    def toggle_connection(self):
        if self.serial_connection and self.serial_connection.is_open:
            self.disconnect_serial()
        else:
            self.connect_serial()

    def connect_serial(self):
        port = self.port_combobox.currentText()
        baud = int(self.baud_combobox.currentText())
        if not port:
            self.status_label.setText("Status: No port selected")
            return
        try:
            self.serial_connection = serial.Serial(port, baud, timeout=1)
            self.serial_connection.write(b"\r\n\r\n")
            time.sleep(2)
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
            self.console_output.append(f"ERROR: Failed to connect - {e}")
            self.update_connection_indicator(False)
        self.update_ui_states()

    def disconnect_serial(self):
        self.dro_timer.stop()
        self.update_connection_indicator(False)
        if self.serial_thread and self.serial_thread.isRunning():
            self.serial_worker.stop()
            self.serial_thread.quit()
            self.serial_thread.wait()
        if self.serial_connection and self.serial_connection.is_open:
            self.serial_connection.close()
        self.connect_button.setText("Connect")
        self.serial_connection = None
        self.serial_thread = None
        self.serial_worker = None
        self.update_ui_states()

    def pulse_home_button(self):
        if self.home_pulse_state == 0:
            self.home_button.setStyleSheet("background-color: #4CAF50; color: white;") # Green
            self.home_pulse_state = 1
        else:
            self.home_button.setStyleSheet("background-color: #8BC34A; color: white;") # Lighter Green
            self.home_pulse_state = 0

    def pulse_alarm_button(self):
        if self.alarm_pulse_state == 0:
            self.unlock_button.setStyleSheet("background-color: #F44336; color: white;") # Red
            self.alarm_pulse_state = 1
        else:
            self.unlock_button.setStyleSheet("background-color: #FF7043; color: white;") # Lighter Red
            self.alarm_pulse_state = 0

    def update_connection_indicator(self, is_connected):
        if is_connected:
            self.connection_status_indicator.setText("Connected")
            self.connection_status_indicator.setStyleSheet("background-color: green; color: white; font-weight: bold;")
        else:
            self.connection_status_indicator.setText("Disconnected")
            self.connection_status_indicator.setStyleSheet("background-color: red; color: white; font-weight: bold;")

    def load_settings(self):
        self.probe_dist_input.setText(self.settings.value("probe/distance", "-25"))
        self.probe_feed_input.setText(self.settings.value("probe/feedrate", "100"))
        self.probe_thickness_input.setText(self.settings.value("probe/thickness", "1.0"))

    def save_settings(self):
        self.settings.setValue("probe/distance", self.probe_dist_input.text())
        self.settings.setValue("probe/feedrate", self.probe_feed_input.text())
        self.settings.setValue("probe/thickness", self.probe_thickness_input.text())
        grbl_fields = {
            "$30": self.max_spindle_speed_input,
            "$120": self.x_accel_input,
            "$121": self.y_accel_input,
            "$122": self.z_accel_input,
        }
        for setting, field in grbl_fields.items():
            initial_value = self.initial_grbl_settings.get(setting)
            current_value = field.text()
            if initial_value is not None and current_value != initial_value:
                self.send_command(f"{setting}={current_value}")
        self.console_output.append("INFO: Settings saved.")

    def update_grbl_setting(self, setting, value):
        self.initial_grbl_settings[setting] = value
        if setting == "$30":
            self.max_spindle_speed_input.setText(value)
        elif setting == "$120":
            self.x_accel_input.setText(value)
        elif setting == "$121":
            self.y_accel_input.setText(value)
        elif setting == "$122":
            self.z_accel_input.setText(value)

    def shutdown_pi(self):
        reply = QMessageBox.question(self, 'Confirm Shutdown',
                                     "Are you sure you want to shut down the Raspberry Pi?",
                                     QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        if reply == QMessageBox.Yes:
            self.console_output.append("INFO: Shutting down Raspberry Pi.")
            os.system("sudo shutdown -h now")

    def closeEvent(self, event):
        self.disconnect_serial()
        super().closeEvent(event)

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec_())
