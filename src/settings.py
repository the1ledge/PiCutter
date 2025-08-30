from PySide2.QtWidgets import (QDialog, QVBoxLayout, QPushButton, QFormLayout,
                               QLineEdit, QGroupBox, QDialogButtonBox)
from PySide2.QtCore import QSettings, Signal

class SettingsDialog(QDialog):
    read_grbl_settings = Signal()
    write_grbl_setting = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.initial_grbl_settings = {}
        self.setWindowTitle("Settings")
        self.setMinimumWidth(400)

        # Use QSettings to store app-specific settings persistently
        self.settings = QSettings("MyCompany", "PiGRBLCNC")

        layout = QVBoxLayout(self)

        # --- Probe Settings ---
        probe_group = QGroupBox("Probe Settings")
        probe_layout = QFormLayout()
        self.probe_dist_input = QLineEdit()
        self.probe_feed_input = QLineEdit()
        self.probe_thickness_input = QLineEdit()
        probe_layout.addRow("Probe Travel Distance (mm):", self.probe_dist_input)
        probe_layout.addRow("Probe Feed Rate:", self.probe_feed_input)
        probe_layout.addRow("Probe Plate Thickness (mm):", self.probe_thickness_input)
        probe_group.setLayout(probe_layout)
        layout.addWidget(probe_group)

        # --- GRBL Settings ---
        grbl_group = QGroupBox("GRBL Settings")
        grbl_layout = QFormLayout()
        self.read_button = QPushButton("Read Settings From Machine")
        grbl_layout.addWidget(self.read_button)
        self.read_button.clicked.connect(self.read_grbl_settings.emit)

        # Example GRBL setting
        self.max_spindle_speed_input = QLineEdit() # $30
        self.x_accel_input = QLineEdit() # $120
        self.y_accel_input = QLineEdit() # $121
        self.z_accel_input = QLineEdit() # $122
        grbl_layout.addRow("Max Spindle Speed ($30):", self.max_spindle_speed_input)
        grbl_layout.addRow("X Acceleration ($120):", self.x_accel_input)
        grbl_layout.addRow("Y Acceleration ($121):", self.y_accel_input)
        grbl_layout.addRow("Z Acceleration ($122):", self.z_accel_input)
        grbl_group.setLayout(grbl_layout)
        layout.addWidget(grbl_group)

        # --- Save/Cancel Buttons ---
        button_box = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        button_box.accepted.connect(self.save_and_accept)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)

        self.load_settings()

    def load_settings(self):
        """Load settings from QSettings and populate fields."""
        self.probe_dist_input.setText(self.settings.value("probe/distance", "-25"))
        self.probe_feed_input.setText(self.settings.value("probe/feedrate", "100"))
        self.probe_thickness_input.setText(self.settings.value("probe/thickness", "1.0"))

    def save_settings(self):
        """Save settings from fields to QSettings."""
        self.settings.setValue("probe/distance", self.probe_dist_input.text())
        self.settings.setValue("probe/feedrate", self.probe_feed_input.text())
        self.settings.setValue("probe/thickness", self.probe_thickness_input.text())
        # Note: Saving GRBL settings will be handled by sending $$ commands
        # and is not part of the local QSettings persistence.

    def update_grbl_setting(self, setting, value):
        """Update a GRBL setting field and store its initial value."""
        self.initial_grbl_settings[setting] = value
        if setting == "$30":
            self.max_spindle_speed_input.setText(value)
        elif setting == "$120":
            self.x_accel_input.setText(value)
        elif setting == "$121":
            self.y_accel_input.setText(value)
        elif setting == "$122":
            self.z_accel_input.setText(value)

    def save_and_accept(self):
        """Save settings and then close the dialog."""
        self.save_settings() # Save app-specific settings (like probe)

        # Save GRBL settings that have changed
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
                command = f"{setting}={current_value}"
                self.write_grbl_setting.emit(command)

        self.accept()
