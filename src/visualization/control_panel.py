from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QSpinBox,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from src.config import config_visualization as config


ENTITY_ID_ROLE = Qt.ItemDataRole.UserRole
ENTITY_TYPE_ROLE = Qt.ItemDataRole.UserRole + 1


class ControlPanel(QWidget):
    frame_changed = Signal(int)
    play_toggled = Signal(bool)
    visibility_changed = Signal(str, bool)
    object_selected = Signal(list)

    def __init__(self, parent=None):
        super().__init__(parent)

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(10, 10, 10, 10)

        display_group = self._create_display_group()
        inspector_group = self._create_inspector_group()

        main_layout.addWidget(display_group)
        main_layout.addWidget(inspector_group)
        main_layout.addStretch()

    def _create_display_group(self):
        group = QGroupBox(config.LBL_DISPLAY_OPTIONS)
        layout = QHBoxLayout(group)

        self.box_checkbox = QCheckBox("Box")
        self.box_checkbox.setChecked(True)
        self.box_checkbox.toggled.connect(
            lambda checked: self.visibility_changed.emit(config.SK_ACTOR_BOX, checked)
        )

        self.markers_checkbox = QCheckBox("Markers")
        self.markers_checkbox.setChecked(True)
        self.markers_checkbox.toggled.connect(
            lambda checked: self.visibility_changed.emit(config.SK_ACTOR_MARKERS, checked)
        )

        self.labels_checkbox = QCheckBox("Labels")
        self.labels_checkbox.setChecked(True)
        self.labels_checkbox.toggled.connect(
            lambda checked: self.visibility_changed.emit(config.SK_ACTOR_LABELS, checked)
        )

        layout.addWidget(self.box_checkbox)
        layout.addWidget(self.markers_checkbox)
        layout.addWidget(self.labels_checkbox)
        layout.addStretch()
        return group

    def _create_inspector_group(self):
        group = QGroupBox(config.LBL_OBJECT_INSPECTOR)
        layout = QVBoxLayout(group)

        self.plot_data_combobox = QComboBox()
        self._refresh_metric_options(config.ENTITY_TYPE_COM)
        self.inspector_help_label = QLabel(config.get_inspector_help_text(config.ENTITY_TYPE_COM))
        self.inspector_help_label.setWordWrap(True)

        self.object_tree = QTreeWidget()
        self.object_tree.setHeaderHidden(True)
        self.object_tree.setSelectionMode(QTreeWidget.SelectionMode.ExtendedSelection)
        self.object_tree.itemSelectionChanged.connect(self.on_object_selection_changed)

        range_layout = QHBoxLayout()
        self.range_checkbox = QCheckBox(config.LBL_USE_FRAME_RANGE)
        self.start_frame_spinbox = QSpinBox()
        self.end_frame_spinbox = QSpinBox()

        self.start_frame_spinbox.setEnabled(False)
        self.end_frame_spinbox.setEnabled(False)

        range_layout.addWidget(self.range_checkbox)
        range_layout.addWidget(QLabel(config.LBL_START))
        range_layout.addWidget(self.start_frame_spinbox)
        range_layout.addWidget(QLabel(config.LBL_END))
        range_layout.addWidget(self.end_frame_spinbox)
        range_layout.addStretch()

        self.range_checkbox.toggled.connect(self.start_frame_spinbox.setEnabled)
        self.range_checkbox.toggled.connect(self.end_frame_spinbox.setEnabled)

        layout.addWidget(QLabel(config.LBL_PLOT_DATA))
        layout.addWidget(self.plot_data_combobox)
        layout.addWidget(self.inspector_help_label)
        layout.addLayout(range_layout)
        layout.addWidget(self.object_tree)
        return group

    def _refresh_metric_options(self, entity_type: str | None):
        current_metric = self.plot_data_combobox.currentData()
        metric_options = config.get_metric_options(entity_type)

        self.plot_data_combobox.blockSignals(True)
        self.plot_data_combobox.clear()
        for label, metric_key in metric_options:
            self.plot_data_combobox.addItem(label, metric_key)

        if current_metric is not None:
            index = self.plot_data_combobox.findData(current_metric)
            if index >= 0:
                self.plot_data_combobox.setCurrentIndex(index)
        self.plot_data_combobox.blockSignals(False)

    def _iter_leaf_items(self):
        for i in range(self.object_tree.topLevelItemCount()):
            group_item = self.object_tree.topLevelItem(i)
            for j in range(group_item.childCount()):
                yield group_item.child(j)

    def _selected_leaf_items(self):
        return [item for item in self.object_tree.selectedItems() if item.childCount() == 0]

    def _current_leaf_item(self):
        current_item = self.object_tree.currentItem()
        if current_item is not None and current_item.childCount() == 0:
            return current_item
        selected_items = self._selected_leaf_items()
        if selected_items:
            return selected_items[-1]
        return None

    def on_object_selection_changed(self):
        selected_items = self._selected_leaf_items()
        current_leaf = self._current_leaf_item()

        if current_leaf is not None and selected_items:
            allowed_type = current_leaf.data(0, ENTITY_TYPE_ROLE)
            selected_types = {item.data(0, ENTITY_TYPE_ROLE) for item in selected_items}
            if len(selected_types) > 1:
                self.object_tree.blockSignals(True)
                for item in selected_items:
                    if item.data(0, ENTITY_TYPE_ROLE) != allowed_type:
                        item.setSelected(False)
                self.object_tree.blockSignals(False)
                selected_items = self._selected_leaf_items()

        selected_type = None
        if selected_items:
            selected_type = selected_items[0].data(0, ENTITY_TYPE_ROLE)
        self._refresh_metric_options(selected_type)
        self.inspector_help_label.setText(config.get_inspector_help_text(selected_type))
        self.object_selected.emit([item.data(0, ENTITY_ID_ROLE) for item in selected_items])

    def populate_scene_inspector(self, grouped_entity_ids: dict[str, list[str]]):
        self.object_tree.clear()

        for group_label, entity_type in config.ENTITY_GROUP_LABELS.items():
            group_item = QTreeWidgetItem([group_label])
            group_flags = group_item.flags()
            group_item.setFlags(group_flags & ~Qt.ItemFlag.ItemIsSelectable)
            self.object_tree.addTopLevelItem(group_item)

            for entity_id in grouped_entity_ids.get(entity_type, []):
                child_item = QTreeWidgetItem([entity_id])
                child_item.setData(0, ENTITY_ID_ROLE, entity_id)
                child_item.setData(0, ENTITY_TYPE_ROLE, entity_type)
                group_item.addChild(child_item)

            group_item.setExpanded(True)

        self._refresh_metric_options(config.ENTITY_TYPE_COM)
        self.inspector_help_label.setText(config.get_inspector_help_text(config.ENTITY_TYPE_COM))

    def populate_object_list(self, object_ids: list[str]):
        grouped = {
            config.ENTITY_TYPE_COM: [],
            config.ENTITY_TYPE_CORNER: [],
            config.ENTITY_TYPE_MARKER: [],
        }
        for entity_id in object_ids:
            grouped[config.classify_entity_id(entity_id)].append(entity_id)
        self.populate_scene_inspector(grouped)

    def get_selected_entity_ids(self) -> list[str]:
        return [item.data(0, ENTITY_ID_ROLE) for item in self._selected_leaf_items()]

    def get_selected_entity_type(self) -> str | None:
        selected_items = self._selected_leaf_items()
        if not selected_items:
            return None
        return selected_items[0].data(0, ENTITY_TYPE_ROLE)
