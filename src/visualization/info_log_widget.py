from PySide6.QtWidgets import (
    QGroupBox, QVBoxLayout, QHBoxLayout, QCheckBox, QTableWidget,
    QHeaderView, QTableWidgetItem
)
from . import config

class InfoLogWidget(QGroupBox):
    """A widget to display detailed information about selected objects in a table."""

    def __init__(self, parent=None):
        super().__init__(config.LBL_INFO_LOG, parent)

        layout = QVBoxLayout(self)

        # --- Checkboxes for log options ---
        options_layout = QHBoxLayout()
        self.log_pos_checkbox = QCheckBox(config.LBL_POSITION)
        self.log_pos_checkbox.setChecked(True)
        self.log_vel_checkbox = QCheckBox(config.LBL_VELOCITY)
        self.log_speed_checkbox = QCheckBox(config.LBL_SPEED)
        options_layout.addWidget(self.log_pos_checkbox)
        options_layout.addWidget(self.log_vel_checkbox)
        options_layout.addWidget(self.log_speed_checkbox)
        options_layout.addStretch()

        # --- Table for displaying data ---
        self.info_table = QTableWidget()
        self.info_table.setColumnCount(1)
        self.info_table.setHorizontalHeaderLabels([config.LBL_PROPERTY])
        self.info_table.verticalHeader().setVisible(False)
        self.info_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.info_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)

        layout.addLayout(options_layout)
        layout.addWidget(self.info_table)

    def update_info_log(self, data: list[dict]):
        """
        Updates the info log table with the given data.
        'data' is a list of dictionaries, where each dict represents a selected object.
        """
        self.info_table.clear()
        if not data:
            self.info_table.setColumnCount(1)
            self.info_table.setRowCount(0)
            self.info_table.setHorizontalHeaderLabels([config.LBL_PROPERTY])
            return

        # --- Setup columns ---
        object_ids = [d.get('object_id', 'N/A') for d in data]
        self.info_table.setColumnCount(1 + len(object_ids))
        self.info_table.setHorizontalHeaderLabels([config.LBL_PROPERTY] + object_ids)

        # --- Populate rows ---
        if not data:
            return

        properties = list(data[0].keys())
        if 'object_id' in properties:
            properties.remove('object_id')

        self.info_table.setRowCount(len(properties))

        for row_idx, prop in enumerate(properties):
            self.info_table.setItem(row_idx, 0, QTableWidgetItem(prop))
            for col_idx, obj_data in enumerate(data):
                value = obj_data.get(prop, "N/A")
                if isinstance(value, float):
                    value_str = f"{value:.2f}"
                else:
                    value_str = str(value)
                self.info_table.setItem(row_idx, col_idx + 1, QTableWidgetItem(value_str))
