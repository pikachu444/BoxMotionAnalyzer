"""Explicit marker draft preview/apply with an independent display-only viewport."""
from __future__ import annotations

from copy import deepcopy
import numpy as np

from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg, NavigationToolbar2QT
from matplotlib.figure import Figure
from matplotlib.font_manager import FontProperties
from matplotlib.patches import Rectangle
from PySide6.QtCore import Qt, QTimer, QSignalBlocker
from PySide6.QtGui import QColor, QBrush
from PySide6.QtWidgets import (QApplication, QComboBox, QDialog, QFileDialog, QFormLayout,
    QHBoxLayout, QHeaderView, QLabel, QLineEdit, QMenu, QPushButton, QScrollArea,
    QSplitter, QTableWidget, QTableWidgetItem, QTabWidget, QVBoxLayout, QWidget, QSizePolicy)
from src.utils.qt_sections import ElidedPathLabel

from src.config.marker_semantics import FACE_NORMALS
from src.simulation.profile_document import ProfileEditorState, save_document
from src.utils.marker_profile_identity import POLICY_VERSION, layout_support, compatibility, profile_identity
from .profile_preview import ProfilePreviewNavigation, FACES, COLORS, PLANE_AXES, box_at, intersects


class MarkerProfileDialog(QDialog):
    def __init__(self, source, *, applied=None, document=None, copy_source=True,
                 previous_result_identity=None, parent=None):
        super().__init__(parent)
        self.state = (ProfileEditorState(source, applied=applied, copy_source=copy_source)
                      if document is None else ProfileEditorState.from_document(deepcopy(document)))
        self.previous_result_identity = deepcopy(previous_result_identity)
        self.current_face = 'BACK'; self.selected_row = 0; self._loading = True
        self._narrow = None; self.face_views = {}; self._face_key = None; self._label_key = None
        self._face_press = None; self.pick_menu = None
        self.setWindowTitle('Marker profile'); self.setMinimumSize(820, 600)
        self.resize(1280, 960)
        outer = QVBoxLayout(self)
        row = QHBoxLayout(); row.addWidget(QLabel('Profile ID'))
        self.profile_id = QLineEdit(self.state.draft['profile_id']); row.addWidget(self.profile_id, 1)
        outer.addLayout(row)
        self.lineage = ElidedPathLabel('Copy of '+self.state.source['profile_id']); outer.addWidget(self.lineage)
        self.applied_label = ElidedPathLabel(); outer.addWidget(self.applied_label)
        for label in (self.lineage, self.applied_label): label.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
        self.lineage.setToolTip('Copy of '+self.state.source['profile_id'])
        self.table = QTableWidget(0, 5); self.table.setHorizontalHeaderLabels(['Name', 'Face', 'X (mm)', 'Y (mm)', 'Z (mm)'])
        self.table.setSelectionBehavior(QTableWidget.SelectRows); self.table.verticalHeader().hide()
        self.table.verticalHeader().setDefaultSectionSize(26)
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        for col in range(1, 5):
            self.table.horizontalHeader().setSectionResizeMode(col, QHeaderView.Fixed)
            self.table.setColumnWidth(col, 88 if col == 1 else 72)
        self.table.setMinimumWidth(440)
        self.tabs = QTabWidget(); self.wide_splitter = QSplitter(Qt.Horizontal)
        outer.addWidget(self.wide_splitter, 1); outer.addWidget(self.tabs, 1)
        self.preview_panel = QWidget(); self.preview_layout = QVBoxLayout(self.preview_panel)
        self.preview_layout.setContentsMargins(0, 0, 0, 0)
        self.preview_title = QLabel(); self.preview_layout.addWidget(self.preview_title)
        facebar = QHBoxLayout(); self.face_caption = QLabel('View face (marker count)'); facebar.addWidget(self.face_caption)
        self.view_combo = QComboBox(); self.view_combo.addItems([f.title() for f in FACES]); self.view_combo.setCurrentText('Back')
        facebar.addWidget(self.view_combo); self.face_buttons = {}
        for face in FACES:
            button = QPushButton(); button.setCheckable(True)
            button.clicked.connect(lambda checked=False, f=face:self.view_combo.setCurrentText(f.title()))
            facebar.addWidget(button); self.face_buttons[face] = button
        facebar.addStretch(); self.preview_layout.addLayout(facebar)
        self.selected_readout = QLabel(); self.preview_layout.addWidget(self.selected_readout)
        self.plot_splitter = QSplitter(Qt.Vertical); self.plot_splitter.setChildrenCollapsible(False)
        self.top = QWidget(); top_layout = QVBoxLayout(self.top); top_layout.setContentsMargins(0, 0, 0, 0)
        topbar = QHBoxLayout(); topbar.addWidget(QLabel('3D View'))
        self.mode_combo = QComboBox(); self.mode_combo.addItems(['Box', 'Exploded faces']); self.mode_combo.setCurrentIndex(1)
        topbar.addWidget(self.mode_combo); display = QLabel('Display only')
        display.setToolTip('View gestures keep table, selected mm values and saved profile unchanged.'); topbar.addWidget(display)
        topbar.addWidget(QLabel('Names')); self.names3 = QComboBox(); self.names3.addItems(['All', 'View face', 'Selected'])
        topbar.addWidget(self.names3); topbar.addStretch()
        self.fit3_button = QPushButton('Fit'); self.reset_view_button = QPushButton('Reset view')
        topbar.addWidget(self.fit3_button); topbar.addWidget(self.reset_view_button); top_layout.addLayout(topbar)
        self.scene = ProfilePreviewNavigation(self.state.preview, self); top_layout.addWidget(self.scene, 1)
        self.bottom = QWidget(); self.bottom_layout = QVBoxLayout(self.bottom); self.bottom_layout.setContentsMargins(0, 0, 0, 0)
        self.bottom_controls = QWidget(); bottom_bar = QHBoxLayout(self.bottom_controls); bottom_bar.setContentsMargins(8, 0, 8, 0)
        self.face_title = QLabel(); bottom_bar.addWidget(self.face_title); bottom_bar.addStretch(); bottom_bar.addWidget(QLabel('Names'))
        self.names2 = QComboBox(); self.names2.addItems(['All', 'Selected']); bottom_bar.addWidget(self.names2)
        self.pan_button = QPushButton('Pan'); self.zoom_button = QPushButton('Zoom'); self.fit2_button = QPushButton('Fit')
        for button in (self.pan_button, self.zoom_button): button.setCheckable(True)
        for button in (self.pan_button, self.zoom_button, self.fit2_button): bottom_bar.addWidget(button)
        self.figure2 = Figure(); self.canvas2 = FigureCanvasQTAgg(self.figure2)
        self.face_axes = self.figure2.add_axes((.09, .14, .86, .81))
        self.nav = NavigationToolbar2QT(self.canvas2, self); self.nav.hide()
        self.bottom_layout.addWidget(self.bottom_controls); self.bottom_layout.addWidget(self.canvas2, 1)
        self.plot_splitter.addWidget(self.top); self.plot_splitter.addWidget(self.bottom)
        self.plot_scroll = QScrollArea(); self.plot_scroll.setFrameShape(QScrollArea.NoFrame); self.plot_scroll.setWidgetResizable(True)
        self.rules = QWidget(); form = QFormLayout(self.rules)
        for label, text in (('Origin', 'Box geometric center'), ('Units', 'mm; recorded time in seconds'),
                ('Local X', '+Right / −Left'), ('Local Y', '+Top / −Bottom'), ('Local Z', '+Front / −Back'),
                ('World vertical', '+Y'), ('Names', 'F / B / R / L / T / M identify the declared face'),
                ('Local X half-turn', 'Front ↔ Back; Top ↔ Bottom'), ('Local Y half-turn', 'Front ↔ Back; Left ↔ Right'),
                ('Local Z half-turn', 'Left ↔ Right; Top ↔ Bottom'),
                ('Correction', 'Analysis face assignment; measured XYZ and IDs preserved'), ('Meaning version', POLICY_VERSION)):
            value = QLabel(text); value.setWordWrap(True); form.addRow(label, value)
        self.compatibility = QLabel(); self.compatibility.setWordWrap(True); outer.addWidget(self.compatibility)
        self.status = QLabel(); self.status.setWordWrap(True); self.status.setTextFormat(Qt.PlainText); outer.addWidget(self.status)
        actions = QHBoxLayout(); self.preview_button = QPushButton('Preview'); self.reset_button = QPushButton('Reset to source')
        self.reset_button.setToolTip('Restore source geometry into the draft. Keep custom ID; Preview and Apply are still required.')
        self.save_button = QPushButton('Save JSON…'); self.apply_button = QPushButton('Apply'); self.cancel_button = QPushButton('Cancel')
        for button in (self.preview_button, self.reset_button, self.save_button): actions.addWidget(button)
        actions.addStretch()
        for button in (self.apply_button, self.cancel_button): actions.addWidget(button)
        outer.addLayout(actions)
        self.preview_button.clicked.connect(self.preview); self.reset_button.clicked.connect(self.reset)
        self.save_button.clicked.connect(self.save); self.apply_button.clicked.connect(self.apply); self.cancel_button.clicked.connect(self.reject)
        self.profile_id.textChanged.connect(self.changed); self.table.itemChanged.connect(self.changed)
        self.table.itemSelectionChanged.connect(self.select_row); self.view_combo.currentTextChanged.connect(self.change_face)
        self.mode_combo.currentTextChanged.connect(self.scene.set_mode); self.names3.currentTextChanged.connect(self.scene.set_names)
        self.scene.markerSelected.connect(self.table.selectRow); self.fit3_button.clicked.connect(self.scene.fit)
        self.reset_view_button.clicked.connect(self.scene.reset_view)
        self.names2.currentTextChanged.connect(self._refresh_face_selection)
        self.pan_button.clicked.connect(lambda:self._set_tool('pan')); self.zoom_button.clicked.connect(lambda:self._set_tool('zoom'))
        self.fit2_button.clicked.connect(self.fit_face)
        self.canvas2.mpl_connect('button_press_event', self._press_face); self.canvas2.mpl_connect('button_release_event', self._release_face)
        self.canvas2.mpl_connect('draw_event', self._place_face_labels)
        self._fill_table(); self._loading = False; self._relayout(); self._render_preview(); self._validate_form()
        QTimer.singleShot(0, self.scene.fit)

    def _relayout(self):
        narrow = self.width() < 1100
        if narrow == self._narrow: return
        self._narrow = narrow
        while self.tabs.count(): self.tabs.removeTab(0)
        if narrow:
            self.wide_splitter.hide(); self.layout().insertWidget(3, self.tabs, 1); self.tabs.show()
            self.tabs.addTab(self.table, 'Markers'); self.tabs.addTab(self.preview_panel, 'Preview'); self.tabs.addTab(self.rules, 'Rules')
            self.preview_layout.insertWidget(3, self.bottom_controls)
            self.top.setMinimumHeight(355); self.bottom.setMinimumHeight(275)
            self.plot_scroll.setWidget(self.plot_splitter); self.preview_layout.addWidget(self.plot_scroll, 1); self.plot_scroll.show()
        else:
            if self.plot_scroll.widget() is not None: self.plot_scroll.takeWidget()
            self.plot_scroll.hide(); self.preview_layout.addWidget(self.plot_splitter, 1)
            self.top.setMinimumHeight(180); self.bottom.setMinimumHeight(180)
            self.bottom_layout.insertWidget(0, self.bottom_controls)
            self.tabs.addTab(self.preview_panel, 'Preview'); self.tabs.addTab(self.rules, 'Rules')
            self.wide_splitter.addWidget(self.table); self.wide_splitter.addWidget(self.tabs); self.wide_splitter.show()
            self.wide_splitter.setStretchFactor(0, 0); self.wide_splitter.setStretchFactor(1, 1)
            self.wide_splitter.setSizes([480, self.width()-500])
        self.view_combo.setVisible(narrow); self.face_caption.setText('View face' if narrow else 'View face (marker count)')
        for button in self.face_buttons.values(): button.setVisible(not narrow)
        self.tabs.setCurrentWidget(self.preview_panel); self.plot_splitter.setSizes([550, 450])
        if hasattr(self, 'face_markers'): self._face_caption()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if hasattr(self, 'rules'): self._relayout()

    def _fill_table(self):
        self._loading = True; self.table.setRowCount(len(self.state.draft['markers']))
        for row, marker in enumerate(self.state.draft['markers']):
            for col, text in enumerate([marker['id'], marker['face'], *[f'{v:g}' for v in marker['xyz_mm']]]):
                self.table.setItem(row, col, QTableWidgetItem(text))
        self.profile_id.setText(self.state.draft['profile_id']); self._loading = False

    def changed(self, *args):
        if self._loading: return
        draft = deepcopy(self.state.draft); draft['profile_id'] = self.profile_id.text().strip()
        for row, marker in enumerate(draft['markers']):
            marker['id'] = self.table.item(row, 0).text().strip(); marker['face'] = self.table.item(row, 1).text().strip().upper()
            marker['xyz_mm'] = []
            for col in (2, 3, 4):
                text = self.table.item(row, col).text()
                try:
                    number = float(text); value = number if np.isfinite(number) else text
                except ValueError: value = text
                marker['xyz_mm'].append(value)
        self.state.edit(draft); self._validate_form(args[0] if args else None)

    def _validate_form(self, changed_item=None):
        error = None
        try: self.state.validate_draft()
        except (ValueError, TypeError, KeyError) as failure: error = str(failure)
        blocker = QSignalBlocker(self.table)
        for row in range(self.table.rowCount()):
            for col in range(5): self.table.item(row, col).setBackground(QBrush())
            for col in (2, 3, 4):
                try: valid = np.isfinite(float(self.table.item(row, col).text()))
                except ValueError: valid = False
                if not valid:
                    self.table.item(row, col).setBackground(QColor('#ffe0e0'))
                    error = f'{self.table.item(row, 0).text()}: {"XYZ"[col-2]} must be a finite number.'
        if error and isinstance(changed_item, QTableWidgetItem): changed_item.setBackground(QColor('#ffe0e0'))
        del blocker
        self.preview_button.setEnabled(error is None); self.save_button.setEnabled(error is None)
        support = layout_support(self.state.preview)
        self.apply_button.setEnabled(error is None and self.state.preview_fresh and support['status'] == 'supported')
        self.preview_title.setText('Last valid preview — invalid edits' if error else
                                   'Preview — not applied' if self.state.preview_fresh else 'Preview outdated — edits changed')
        self.status.setText(error or (support['reason'] if support['status'] != 'supported' else
                                      'Draft ready. Preview and Apply are separate.'))
        current = profile_identity(self.state.preview)
        check = compatibility(self.previous_result_identity, current)
        self.compatibility.setText('Previous result: '+check['status'])
        self.compatibility.setToolTip(' '.join(check['reasons'])+' Apply does not approve a previous result.')

    def preview(self):
        try: self.state.refresh_preview()
        except (ValueError, KeyError, TypeError) as error:
            self.status.setText(str(error)); return
        if self.pick_menu is not None: self.pick_menu.close()
        self._render_preview(); self._validate_form()

    def reset(self):
        self.state.reset_to_source(); self._fill_table(); self._validate_form()

    def apply(self):
        try: self.state.apply()
        except ValueError as error:
            self.status.setText(str(error)); return
        self.accept()

    def save_to(self, path):
        try: save_document(path, self.state)
        except (OSError, ValueError) as error:
            self.status.setText('Save failed: '+str(error)); return False
        self.status.setText('Profile saved. Apply remains separate.'); return True

    def save(self):
        path, _ = QFileDialog.getSaveFileName(self, 'Save marker profile', self.state.draft['profile_id']+'.json', 'JSON files (*.json)')
        if path: self.save_to(path)

    def _render_preview(self):
        self.scene.set_profile(self.state.preview)
        self.selected_row = min(self.selected_row, len(self.state.preview['markers'])-1)
        markers = self.state.preview['markers']
        if self.table.currentRow() < 0:
            self.selected_row = next((i for i, m in enumerate(markers) if m['id'] == 'B1'), 0)
            self.table.selectRow(self.selected_row)
        dims = ' × '.join(f'{d:g}' for d in self.state.preview['box_dims_mm'])
        self.applied_label.setText(f'Box: {dims} mm    Source unchanged    Applied: {self.state.applied["profile_id"]}')
        self.applied_label.setToolTip(f'Applied: {self.state.applied["profile_id"]}')
        for face, button in self.face_buttons.items():
            button.setText(face.title()+f' ({sum(m["face"] == face for m in markers)})')
            button.setChecked(face == self.current_face)
        self._refresh_selection(); self._render_face()

    def select_row(self):
        if self._loading or self.table.currentRow() < 0: return
        self.selected_row = min(self.table.currentRow(), len(self.state.preview['markers'])-1)
        face = self.state.preview['markers'][self.selected_row]['face']
        self.view_combo.setCurrentText(face.title()); self._refresh_selection(); self._render_face()

    def _refresh_selection(self):
        marker = self.state.preview['markers'][self.selected_row]
        self.scene.set_selected(self.selected_row, self.current_face)
        self.selected_readout.setText(f'Selected: {marker["id"]}  {marker["face"].title()}  ('+
            ', '.join(f'{v:g}' for v in marker['xyz_mm'])+') mm    Normal: ('+
            ', '.join(str(v) for v in FACE_NORMALS[marker['face']])+')')
        self._refresh_face_selection()

    def change_face(self):
        if self._loading: return
        if self._face_key is not None: self.face_views[self.current_face] = (self.face_axes.get_xlim(), self.face_axes.get_ylim())
        self.current_face = self.view_combo.currentText().upper()
        for face, button in self.face_buttons.items(): button.setChecked(face == self.current_face)
        self.scene.set_selected(self.selected_row, self.current_face); self._render_face()

    def _face_caption(self):
        axis = next(i for i in range(3) if i not in PLANE_AXES[self.current_face])
        value = FACE_NORMALS[self.current_face][axis]*self.state.preview['box_dims_mm'][axis]/2
        self.face_title.setText(('2D ' if self._narrow else '')+self.current_face.title()+f' / {"XYZ"[axis]}={value:g} mm ({len(self.face_markers)})')

    def _render_face(self):
        key = (self.scene.profile_hash, self.current_face)
        if key == self._face_key:
            self._refresh_face_selection(); return
        self._face_key = key; self._label_key = None; self.face_axes.clear()
        a, b = PLANE_AXES[self.current_face]; dims = self.state.preview['box_dims_mm']
        self.face_rows = [i for i, m in enumerate(self.state.preview['markers']) if m['face'] == self.current_face]
        self.face_markers = [self.state.preview['markers'][i] for i in self.face_rows]
        self.face_points = np.asarray([[m['xyz_mm'][a], m['xyz_mm'][b]] for m in self.face_markers]).reshape(-1, 2)
        self.face_axes.add_patch(Rectangle((-dims[a]/2, -dims[b]/2), dims[a], dims[b], fill=False, edgecolor='#999999'))
        if len(self.face_points): self.face_axes.scatter(*self.face_points.T, s=85, c=COLORS[self.current_face], edgecolors='#262626', linewidths=.9)
        self.face_ring = self.face_axes.scatter([], [], s=240, facecolors='none', edgecolors='#111111', linewidths=2.2, zorder=5)
        self.face_axes.set(xlim=(-dims[a]*.6, dims[a]*.6), ylim=(-dims[b]*.6, dims[b]*.6), xlabel=f'Local {"XYZ"[a]} (mm)', ylabel=f'Local {"XYZ"[b]} (mm)')
        self.face_axes.set_aspect('equal', adjustable='box'); self.face_axes.grid(True, alpha=.12); self.face_axes.tick_params(labelsize=9)
        if self.current_face in self.face_views:
            self.face_axes.set_xlim(self.face_views[self.current_face][0]); self.face_axes.set_ylim(self.face_views[self.current_face][1])
        self.face_labels = [self.face_axes.annotate(m['id'], xy=p, xytext=(8, 8), textcoords='offset points', fontsize=11,
            bbox=dict(boxstyle='round,pad=.15', fc='white', ec='none', alpha=.94),
            arrowprops=dict(arrowstyle='-', color='#666666', linewidth=.65), zorder=8) for m,p in zip(self.face_markers, self.face_points)]
        self._face_caption(); self._refresh_face_selection(); self.canvas2.draw_idle()

    def _refresh_face_selection(self, *args):
        if not hasattr(self, 'face_labels'): return
        selected = self.state.preview['markers'][self.selected_row]['id']
        points = [p for m,p in zip(self.face_markers, self.face_points) if m['id'] == selected]
        self.face_ring.set_offsets(np.asarray(points).reshape(-1, 2))
        for marker, label in zip(self.face_markers, self.face_labels):
            label.set_fontweight('bold' if marker['id'] == selected else 'normal')
            label.set_visible(self.names2.currentText() == 'All' or marker['id'] == selected)
        self.canvas2.draw_idle()

    def _place_face_labels(self, event):
        if not hasattr(self, 'face_labels'): return
        key = (*self.face_axes.get_xlim(), *self.face_axes.get_ylim(), *self.face_axes.bbox.bounds, self.figure2.dpi, self._face_key)
        if key == self._label_key: return
        self._label_key = key; pixels = self.face_axes.transData.transform(self.face_points); occupied = []
        offsets = [(x, y) for radius in (12, 24, 36, 48) for x,y in ((radius, radius), (radius,-radius), (-radius,radius), (-radius,-radius))]
        font = FontProperties(size=11, weight='bold'); renderer = event.renderer; factor = self.figure2.dpi/72
        for i, (marker, label) in enumerate(zip(self.face_markers, self.face_labels)):
            width, height, _ = renderer.get_text_width_height_descent(marker['id'], font, False)
            size = np.array([width+8, height+8]); best = None
            for offset in offsets:
                center = pixels[i]+np.asarray(offset)*factor; bounds = box_at(center, size)
                points = np.column_stack((pixels-7*factor, pixels+7*factor))
                score = 1000*np.count_nonzero(intersects(bounds, np.asarray(occupied).reshape(-1, 4)))
                score += 1000*np.count_nonzero(intersects(bounds, points))
                score += 10000*int(not self.face_axes.bbox.contains(bounds[0], bounds[1]) or not self.face_axes.bbox.contains(bounds[2], bounds[3]))
                if best is None or score < best[0]: best = (score, offset, bounds)
                if score == 0: break
            label.set_position(best[1]); label.set_horizontalalignment('center'); label.set_verticalalignment('center')
            occupied.append(best[2])
        self.canvas2.draw_idle()

    def fit_face(self):
        self.face_views.pop(self.current_face, None); self._face_key = None; self._render_face()

    def _set_tool(self, tool):
        getattr(self.nav, tool)(); self.pan_button.setChecked(str(self.nav.mode) == 'pan/zoom'); self.zoom_button.setChecked(str(self.nav.mode) == 'zoom rect')

    def _press_face(self, event):
        self._face_press = (event.x, event.y) if event.button == 1 and not self.nav.mode and event.inaxes is self.face_axes else None

    def _release_face(self, event):
        press, self._face_press = self._face_press, None
        if press is None or event.button != 1 or self.nav.mode: return
        if np.linalg.norm(np.asarray(press)-[event.x, event.y]) >= QApplication.styleHints().startDragDistance()*self.canvas2.devicePixelRatioF(): return
        pixels = self.face_axes.transData.transform(self.face_points)
        rows = [self.face_rows[i] for i,p in enumerate(pixels) if np.linalg.norm(p-[event.x, event.y]) <= 12*self.canvas2.devicePixelRatioF()]
        if len(rows) == 1: self.table.selectRow(rows[0])
        elif rows:
            self.pick_menu = QMenu(self); revision = self.scene.profile_revision
            for row in rows:
                action = self.pick_menu.addAction(self.state.preview['markers'][row]['id'])
                action.triggered.connect(lambda checked=False, r=row, rev=revision:self.table.selectRow(r) if self.scene.profile_revision == rev else None)
            menu = self.pick_menu
            menu.aboutToHide.connect(lambda: self._forget_menu(menu))
            menu.aboutToHide.connect(menu.deleteLater)
            self.pick_menu.popup(self.canvas2.mapToGlobal(event.guiEvent.position().toPoint()))

    def _forget_menu(self, menu):
        if self.pick_menu is menu: self.pick_menu = None

    def reject(self):
        self.scene.cancel_gesture()
        if self.pick_menu is not None: self.pick_menu.close(); self.pick_menu = None
        super().reject()
