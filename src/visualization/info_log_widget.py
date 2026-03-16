from PySide6.QtWidgets import (
    QGroupBox, QVBoxLayout, QHBoxLayout, QCheckBox, QTableWidget,
    QHeaderView, QTableWidgetItem
)
from src.config import config_visualization as config

class InfoLogWidget(QGroupBox):
    """Displays current-frame values for the selected scene entities."""

    def __init__(self, parent=None):
        super().__init__(config.LBL_INFO_LOG, parent)

        layout = QVBoxLayout(self)

        # --- Checkboxes for log options ---
        options_layout = QHBoxLayout()
        self.log_pos_checkbox = QCheckBox(config.LBL_POSITION)
        self.log_pos_checkbox.setChecked(True)
        self.log_vel_checkbox = QCheckBox(config.LBL_VELOCITY)
        self.log_acc_checkbox = QCheckBox(config.LBL_ACCELERATION)
        options_layout.addWidget(self.log_pos_checkbox)
        options_layout.addWidget(self.log_vel_checkbox)
        options_layout.addWidget(self.log_acc_checkbox)
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
        Updates the frame inspector table with the given data.
        Each dictionary represents one selected entity and should include 'entity_id'.
        """
        self.info_table.clear()
        if not data:
            self.info_table.setColumnCount(1)
            self.info_table.setRowCount(0)
            self.info_table.setHorizontalHeaderLabels([config.LBL_PROPERTY])
            return

        entity_ids = [d.get(config.DF_ENTITY_ID, config.LBL_EMPTY_VALUE) for d in data]
        self.info_table.setColumnCount(1 + len(entity_ids))
        self.info_table.setHorizontalHeaderLabels([config.LBL_PROPERTY] + entity_ids)

        properties = []
        for obj_data in data:
            for key in obj_data.keys():
                if key == config.DF_ENTITY_ID or key in properties:
                    continue
                properties.append(key)

        self.info_table.setRowCount(len(properties))
        for row_idx, prop in enumerate(properties):
            self.info_table.setItem(row_idx, 0, QTableWidgetItem(prop))
            for col_idx, obj_data in enumerate(data):
                value = obj_data.get(prop, config.LBL_EMPTY_VALUE)
                if isinstance(value, float):
                    value_str = f"{value:.2f}"
                else:
                    value_str = str(value)
                self.info_table.setItem(row_idx, col_idx + 1, QTableWidgetItem(value_str))
