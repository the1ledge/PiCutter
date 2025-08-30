import sys
import serial.tools.list_ports
import re
import time
from PySide2.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
                               QComboBox, QPushButton, QLabel, QGroupBox, QGridLayout,
                               QProgressBar, QFileDialog, QTextEdit)
from PySide2.QtCore import Qt, QThread, QObject, Signal, QTimer

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
                    # Port might have been closed
                    break
        print("Serial worker finished.")

    def stop(self):
        self._is_running = False

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("GRBL CNC Controller")
        self.resize(800, 600)

        # Main widget and layout
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)

        # Connection UI
        connection_layout = QHBoxLayout()
        self.port_combobox = QComboBox()
        self.refresh_button = QPushButton("Refresh")
        self.connect_button = QPushButton("Connect")
        self.status_label = QLabel("Status: Disconnected")

        connection_layout.addWidget(QLabel("Port:"))
        connection_layout.addWidget(self.port_combobox)

        connection_layout.addWidget(QLabel("Baud:"))
        self.baud_combobox = QComboBox()
        self.baud_combobox.addItems(["9600", "19200", "38400", "57600", "115200"])
        self.baud_combobox.setCurrentText("115200")
        connection_layout.addWidget(self.baud_combobox)

        connection_layout.addWidget(self.refresh_button)
        connection_layout.addWidget(self.connect_button)
        connection_layout.addStretch()
        connection_layout.addWidget(self.status_label)

        main_layout.addLayout(connection_layout)

        # --- Control and DRO ---
        control_dro_layout = QHBoxLayout()

        # Jogging Group
        jog_group = QGroupBox("Manual Control (Jogging)")
        jog_layout = QGridLayout()

        self.step_size_combo = QComboBox()
        self.step_size_combo.addItems(["0.1", "1", "10", "100"])
        self.step_size_combo.setCurrentText("10")

        jog_layout.addWidget(QLabel("Step Size (mm):"), 0, 0, 1, 2)
        jog_layout.addWidget(self.step_size_combo, 0, 2, 1, 2)

        self.y_plus_button = QPushButton("Y+")
        self.y_minus_button = QPushButton("Y-")
        self.x_minus_button = QPushButton("X-")
        self.x_plus_button = QPushButton("X+")
        self.z_plus_button = QPushButton("Z+")
        self.z_minus_button = QPushButton("Z-")

        jog_layout.addWidget(self.y_plus_button, 1, 1)
        jog_layout.addWidget(self.y_minus_button, 3, 1)
        jog_layout.addWidget(self.x_minus_button, 2, 0)
        jog_layout.addWidget(self.x_plus_button, 2, 2)
        jog_layout.addWidget(self.z_plus_button, 1, 3)
        jog_layout.addWidget(self.z_minus_button, 3, 3)

        jog_group.setLayout(jog_layout)
        control_dro_layout.addWidget(jog_group)

        # DRO Group
        dro_group = QGroupBox("Digital Readout (Machine Pos)")
        dro_layout = QGridLayout()
        self.x_pos_label = QLabel("0.000")
        self.y_pos_label = QLabel("0.000")
        self.z_pos_label = QLabel("0.000")
        dro_layout.addWidget(QLabel("MPos X:"), 0, 0)
        dro_layout.addWidget(self.x_pos_label, 0, 1)
        dro_layout.addWidget(QLabel("MPos Y:"), 1, 0)
        dro_layout.addWidget(self.y_pos_label, 1, 1)
        dro_layout.addWidget(QLabel("MPos Z:"), 2, 0)
        dro_layout.addWidget(self.z_pos_label, 2, 1)
        dro_group.setLayout(dro_layout)
        control_dro_layout.addWidget(dro_group)

        actions_group = QGroupBox("Actions")
        actions_layout = QVBoxLayout()
        self.home_button = QPushButton("Home ($H)")
        self.unlock_button = QPushButton("Unlock ($X)")
        self.set_zero_button = QPushButton("Set Zero (G10)")
        actions_layout.addWidget(self.home_button)
        actions_layout.addWidget(self.unlock_button)
        actions_layout.addWidget(self.set_zero_button)
        actions_group.setLayout(actions_layout)
        control_dro_layout.addWidget(actions_group)

        main_layout.addLayout(control_dro_layout)

        # G-Code Sending Group
        gcode_group = QGroupBox("G-Code Sending")
        gcode_layout = QVBoxLayout()

        gcode_file_layout = QHBoxLayout()
        self.load_file_button = QPushButton("Load File")
        self.gcode_file_label = QLabel("No file loaded.")
        gcode_file_layout.addWidget(self.load_file_button)
        gcode_file_layout.addWidget(self.gcode_file_label)
        gcode_file_layout.addStretch()

        self.gcode_progress = QProgressBar()

        gcode_actions_layout = QHBoxLayout()
        self.start_button = QPushButton("Start")
        self.pause_button = QPushButton("Pause")
        self.stop_button = QPushButton("Stop")
        gcode_actions_layout.addWidget(self.start_button)
        gcode_actions_layout.addWidget(self.pause_button)
        gcode_actions_layout.addWidget(self.stop_button)
        gcode_actions_layout.addStretch()

        gcode_layout.addLayout(gcode_file_layout)
        gcode_layout.addWidget(self.gcode_progress)
        gcode_layout.addLayout(gcode_actions_layout)
        gcode_group.setLayout(gcode_layout)

        main_layout.addWidget(gcode_group)

        # Console Group
        console_group = QGroupBox("Console")
        console_layout = QVBoxLayout()
        self.console_output = QTextEdit()
        self.console_output.setReadOnly(True)
        console_layout.addWidget(self.console_output)
        console_group.setLayout(console_layout)

        main_layout.addWidget(console_group)
        main_layout.addStretch() # Add a spacer

        # --- Connections ---
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

        # --- State ---
        self.serial_connection = None
        self.serial_thread = None
        self.serial_worker = None

        # G-code state
        self.gcode_lines = []
        self.gcode_current_line = 0
        self.gcode_is_running = False
        self.gcode_is_paused = False

        self.populate_ports()
        self.update_ui_states()

        # --- DRO Timer ---
        self.dro_timer = QTimer(self)
        self.dro_timer.setInterval(200) # 200ms update rate
        self.dro_timer.timeout.connect(lambda: self.send_command("?"))

    def handle_serial_data(self, data):
        self.console_output.append(f"RX: {data}")
        # Example GRBL status: <Idle|MPos:0.000,0.000,0.000|FS:0,0>
        if data.startswith("<"):
            match = re.search(r"MPos:([\d.-]+),([\d.-]+),([\d.-]+)", data)
            if match:
                x, y, z = match.groups()
                self.x_pos_label.setText(f"{float(x):.3f}")
                self.y_pos_label.setText(f"{float(y):.3f}")
                self.z_pos_label.setText(f"{float(z):.3f}")
        elif data.lower() == "ok":
            self.send_next_gcode_line()

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

        # G-code buttons
        self.start_button.setEnabled(is_connected and file_loaded and not self.gcode_is_running)
        self.pause_button.setEnabled(is_connected and self.gcode_is_running)
        self.stop_button.setEnabled(is_connected and self.gcode_is_running)

        # Action buttons
        self.home_button.setEnabled(is_connected)
        self.unlock_button.setEnabled(is_connected)
        self.set_zero_button.setEnabled(is_connected)

        if self.gcode_is_running and not self.gcode_is_paused:
            self.pause_button.setText("Pause")
        else:
            self.pause_button.setText("Resume")

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
            self.send_command("!") # Feed hold
        else:
            self.send_command("~") # Resume
        self.update_ui_states()

    def stop_gcode(self):
        self.gcode_is_running = False
        self.gcode_is_paused = False
        self.send_command("\x18") # Soft-reset
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
            # End of file
            self.gcode_is_running = False
            self.update_ui_states()
            print("G-code sending finished.")

    def send_command(self, command):
        if self.serial_connection and self.serial_connection.is_open:
            self.console_output.append(f"TX: {command}")
            # GRBL expects a newline character to execute a command
            self.serial_connection.write((command + '\n').encode('utf-8'))
        else:
            self.console_output.append(f"INFO: Not connected. Command '{command}' not sent.")

    def send_jog_command(self, axis, direction):
        step_size = float(self.step_size_combo.currentText())
        distance = step_size * direction
        # Using the new GRBL jogging command $J=
        # G91 sets relative mode, G21 sets units to mm
        # F sets the feed rate (speed). Let's use a default value for now.
        command = f"$J=G91 G21 {axis}{distance} F1000"
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

            # Wake up GRBL
            self.serial_connection.write(b"\r\n\r\n")
            time.sleep(2) # Wait for GRBL to initialize
            self.serial_connection.flushInput()

            self.serial_thread = QThread()
            self.serial_worker = SerialWorker(self.serial_connection)
            self.serial_worker.moveToThread(self.serial_thread)

            self.serial_thread.started.connect(self.serial_worker.run)
            self.serial_worker.serial_data_received.connect(self.handle_serial_data)

            self.serial_thread.start()
            self.dro_timer.start()

            self.status_label.setText(f"Status: Connected to {port}")
            self.connect_button.setText("Disconnect")
            self.port_combobox.setEnabled(False)
            self.baud_combobox.setEnabled(False)
            self.refresh_button.setEnabled(False)
            self.update_ui_states()

        except (serial.SerialException, FileNotFoundError) as e:
            self.status_label.setText(f"Status: Error - {e}")

    def disconnect_serial(self):
        self.dro_timer.stop()
        if self.serial_thread and self.serial_thread.isRunning():
            self.serial_worker.stop()
            self.serial_thread.quit()
            self.serial_thread.wait()

        if self.serial_connection and self.serial_connection.is_open:
            self.serial_connection.close()

        self.status_label.setText("Status: Disconnected")
        self.connect_button.setText("Connect")
        self.port_combobox.setEnabled(True)
        self.baud_combobox.setEnabled(True)
        self.refresh_button.setEnabled(True)
        self.serial_connection = None
        self.serial_thread = None
        self.serial_worker = None
        self.update_ui_states()

    def closeEvent(self, event):
        self.disconnect_serial()
        super().closeEvent(event)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec_())
