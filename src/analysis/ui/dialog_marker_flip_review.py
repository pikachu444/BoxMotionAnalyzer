from __future__ import annotations

from typing import Iterable
import numpy as np
import pandas as pd

from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
from src.utils.plot_toolbar import PlotToolbar as NavigationToolbar2QT
from matplotlib.figure import Figure
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFrame,
    QHeaderView,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)
from src.utils.qt_sections import CollapsibleSection, set_path_label
from src.config.data_columns import RigidBodyCols

from src.analysis.pipeline.marker_flip import (
    MarkerCorrectionDecision,
    MarkerFlipCandidate,
    SUPPORTED_LOCAL_AXES,
    normalize_marker_corrections,
)
from src.utils.ui_language import tr


class _ElidedSourceLabel(QLabel):
    """Keep the existing path tooltip/menu while fitting the visible filename."""

    def setText(self, text):
        self._filename = text
        self._elide()

    def _elide(self):
        super().setText(self.fontMetrics().elidedText(
            getattr(self, '_filename', ''), Qt.TextElideMode.ElideMiddle,
            max(0, self.contentsRect().width())))

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._elide()


class MarkerFlipReviewDialog(QDialog):
    """Operator review surface for marker flip candidates."""

    def __init__(
        self,
        candidates: Iterable[MarkerFlipCandidate],
        existing_decisions: Iterable[MarkerCorrectionDecision] | None = None,
        parent: QWidget | None = None,
    ):
        super().__init__(parent)
        self.candidates = list(candidates)
        self.existing_decisions = {
            decision.event_id: decision
            for decision in normalize_marker_corrections(existing_decisions)
        }
        self._approval_checkboxes: list[QCheckBox] = []
        self._axis_combos: list[QComboBox] = []
        self._evidence_canvas_disposed = False
        self._context_row = None
        self._context_data = None
        self._context_unit = 'unit unknown'
        self._tabbed_plots = False
        self._active_plot_tab = 0

        self.setWindowTitle(tr("Marker correction"))
        self.resize(960, 680)
        self.setMinimumSize(820, 600)
        self._setup_ui()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        if not self.candidates:
            message = QLabel(tr('No candidates for the current source and dimensions.\nDone records a review with no approvals; Cancel keeps the previous review.'))
            message.setWordWrap(True)
            layout.addWidget(message)
        self.table = QTableWidget(len(self.candidates), 4, self)
        self.table.setHorizontalHeaderLabels(
            [tr("Event (s)"), tr("Recommendation"), tr("Apply"), tr("Local axis")]
        )
        self.table.horizontalHeaderItem(1).setToolTip(tr("Recommended half-turn restores continuity conditionally; it does not confirm a tracking error."))
        self.table.horizontalHeaderItem(3).setToolTip(tr("180° about the selected box-local axis."))
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setAlternatingRowColors(True)
        self.table.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.table.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.table.verticalHeader().setVisible(False)
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        header.setStretchLastSection(True)

        for row, candidate in enumerate(self.candidates):
            existing = self.existing_decisions.get(candidate.event_id)
            boundary_item = QTableWidgetItem(f"{candidate.boundary_time_sec:.6f}")
            boundary_item.setToolTip(candidate.trigger)
            self.table.setItem(row, 0, boundary_item)
            recommendation_text = (
                candidate.recommendation_axis
                if candidate.recommendation_axis is not None
                else "No recommendation"
            )
            recommendation_item = QTableWidgetItem(recommendation_text)
            recommendation_item.setToolTip(candidate.reason)
            self.table.setItem(row, 1, recommendation_item)

            approval = QCheckBox(tr('OFF'))
            approval.setAccessibleName(tr('Apply correction at {} seconds').format(f'{candidate.boundary_time_sec:.6f}'))
            approval.toggled.connect(lambda checked, checkbox=approval: checkbox.setText(tr('ON') if checked else tr('OFF')))
            approval.setChecked(bool(existing and existing.approved))
            approval_container = QWidget()
            approval_layout = QVBoxLayout(approval_container)
            approval_layout.setContentsMargins(8, 0, 8, 0)
            approval_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
            approval_layout.addWidget(approval)
            self.table.setCellWidget(row, 2, approval_container)

            axis_combo = QComboBox()
            axis_combo.setAccessibleName(
                tr('Local correction axis at {} seconds').format(f'{candidate.boundary_time_sec:.6f}')
            )
            axis_combo.setToolTip(tr("180° about the selected box-local axis. Changing the preview does not enable Apply."))
            axis_combo.addItem(tr("None"), userData=None)
            for axis in SUPPORTED_LOCAL_AXES:
                axis_combo.addItem(axis, userData=axis)
            axis_combo.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
            selected_axis = (
                existing.axis
                if existing is not None and existing.axis is not None
                else candidate.recommendation_axis
            )
            if selected_axis in SUPPORTED_LOCAL_AXES:
                axis_combo.setCurrentIndex(axis_combo.findData(selected_axis))
            self.table.setCellWidget(row, 3, axis_combo)

            self._approval_checkboxes.append(approval)
            self._axis_combos.append(axis_combo)
            axis_combo.currentIndexChanged.connect(lambda _index, r=row: self._select_event(r))
            approval.toggled.connect(lambda _checked, r=row: self._select_event(r))

        self.table.resizeRowsToContents()
        visible_rows = min(5, len(self.candidates))
        self.table.setFixedHeight(self.table.horizontalHeader().sizeHint().height()
                                  + sum(self.table.rowHeight(row) for row in range(visible_rows))
                                  + 2 * self.table.frameWidth())
        layout.addWidget(self.table)

        self.candidate_summary = QWidget()
        summary = QHBoxLayout(self.candidate_summary)
        summary.setContentsMargins(0, 0, 0, 0)
        summary.setSpacing(24)
        self.no_correction_summary = QLabel()
        self.preview_summary = QLabel()
        self.coverage_summary = QLabel()
        for label in (self.no_correction_summary, self.preview_summary, self.coverage_summary):
            summary.addWidget(label)
        summary.addStretch()
        layout.addWidget(self.candidate_summary)

        self.candidate_details = QLabel()
        self.candidate_details.setWordWrap(True)
        self.candidate_details.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.candidate_details.setTextFormat(Qt.TextFormat.PlainText)
        self.candidate_details.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse | Qt.TextInteractionFlag.TextSelectableByKeyboard
        )
        self.candidate_details.setAccessibleName(tr("Selected marker flip candidate details"))
        self.details_scroll = QScrollArea()
        self.details_scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.details_scroll.setWidgetResizable(True)
        self.details_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.details_scroll.setMaximumHeight(96)
        self.details_scroll.setWidget(self.candidate_details)
        self.details_section = CollapsibleSection(tr("Details"), self.details_scroll)
        self.details_section.button.setSizePolicy(QSizePolicy.Policy.Maximum, QSizePolicy.Policy.Fixed)

        self.preview_status = QLabel()
        self.preview_status.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignBottom)
        self.preview_status.setStyleSheet("color: #916000;")

        self.plots = QHBoxLayout()
        self.plot_tabs = QTabWidget()
        self.plot_tabs.setAccessibleName(tr('Marker review graphs'))
        self.plot_tabs.currentChanged.connect(self._plot_tab_changed)
        self.plot_tabs.hide()
        self.plots.addWidget(self.plot_tabs)
        self.context_panel = QWidget()
        context_layout = QVBoxLayout(self.context_panel)
        context_layout.setContentsMargins(0, 0, 0, 0)
        self.context_header = QWidget()
        context_header_layout = QVBoxLayout(self.context_header)
        context_header_layout.setContentsMargins(0, 0, 0, 0)
        context_layout.addWidget(self.context_header)
        self.context_source = _ElidedSourceLabel()
        set_path_label(self.context_source, '')
        context_header_layout.addWidget(self.context_source)
        controls = QHBoxLayout()
        self.context_target = QComboBox()
        self.context_target.setAccessibleName(tr('Original observation target'))
        self.context_target.setMinimumContentsLength(14)
        self.context_target.setSizeAdjustPolicy(QComboBox.AdjustToMinimumContentsLengthWithIcon)
        self.around_event_button = QPushButton(tr('Around event'))
        controls.addWidget(self.context_target, 1)
        controls.addWidget(self.around_event_button)
        context_header_layout.addLayout(controls)
        self.context_figure = Figure(figsize=(6, 3), dpi=100, layout='constrained')
        self.context_canvas = FigureCanvas(self.context_figure)
        self.context_canvas.setMinimumHeight(170)
        self.context_toolbar = NavigationToolbar2QT(self.context_canvas, self.context_header, coordinates=False)
        context_header_layout.addWidget(self.context_toolbar)
        context_layout.addWidget(self.context_canvas, 1)
        self.context_target.currentIndexChanged.connect(self._draw_context)
        self.around_event_button.clicked.connect(self._center_context)
        self.context_panel.hide()
        self.plots.addWidget(self.context_panel, 1)
        self.evidence_panel = QWidget()
        evidence_layout = QVBoxLayout(self.evidence_panel)
        evidence_layout.setContentsMargins(0, 0, 0, 0)
        evidence_layout.addWidget(self.preview_status)

        self.evidence_figure = Figure(figsize=(8, 2.4), dpi=100, layout='constrained')
        self.evidence_canvas = FigureCanvas(self.evidence_figure)
        self.evidence_canvas.setMinimumHeight(170)
        self.evidence_canvas.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Expanding,
        )
        evidence_layout.addWidget(self.evidence_canvas, 1)
        self.plots.addWidget(self.evidence_panel, 1)
        layout.addLayout(self.plots, 2)
        layout.addWidget(self.details_section)
        self.table.currentCellChanged.connect(self._update_evidence_plot)
        if self.candidates:
            self.table.selectRow(0)
        self._update_evidence_plot(self.table.currentRow())

        self.button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel,
            parent=self,
        )
        self.button_box.accepted.connect(self.accept)
        self.button_box.rejected.connect(self.reject)
        self.button_box.button(QDialogButtonBox.StandardButton.Ok).setText(tr("Done"))
        layout.addWidget(self.button_box)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if hasattr(self, 'plot_tabs'):
            self._sync_plot_layout()

    def _sync_plot_layout(self):
        if self._context_data is None or self._evidence_canvas_disposed:
            return
        tabbed = self.width() < 1100
        self.preview_status.setMinimumHeight(0 if tabbed else self.context_header.sizeHint().height())
        if tabbed == self._tabbed_plots:
            return
        self._tabbed_plots = tabbed
        self.plot_tabs.blockSignals(True)
        if tabbed:
            for panel, title in ((self.context_panel, tr('Original trajectories')),
                                 (self.evidence_panel, tr('Axis preview'))):
                self.plots.removeWidget(panel)
                self.plot_tabs.addTab(panel, title)
            self.plot_tabs.setCurrentIndex(self._active_plot_tab)
            self.plot_tabs.show()
        else:
            self._active_plot_tab = self.plot_tabs.currentIndex()
            for panel in (self.context_panel, self.evidence_panel):
                self.plot_tabs.removeTab(0)
                self.plots.addWidget(panel, 1)
                panel.show()
            self.plot_tabs.hide()
        self.plot_tabs.blockSignals(False)
        self.context_canvas.draw_idle()
        self.evidence_canvas.draw_idle()

    def _plot_tab_changed(self, index):
        if self._evidence_canvas_disposed or index < 0:
            return
        self._active_plot_tab = index
        (self.context_canvas if index == 0 else self.evidence_canvas).draw_idle()

    def _select_event(self, row):
        if self.table.currentRow() != row:
            self.table.setCurrentCell(row, 3)
        else:
            self._update_evidence_plot(row)
        self.table.scrollToItem(self.table.item(row, 0))

    def set_observation_context(self, data, *, source_path='', units='', preferred_target=None):
        """Copy only original position columns; never fit, correct or read truth."""
        targets = sorted({column[:-2] for column in data.columns
            if isinstance(column, str) and column.endswith('_X')
            and all(column[:-2] + '_' + axis in data for axis in 'XYZ')}) if data is not None else []
        columns = [target + '_' + axis for target in targets for axis in 'XYZ']
        self._context_data = data[columns].copy(deep=True) if data is not None else pd.DataFrame()
        self._context_unit = {'Millimeters': 'mm', 'Centimeters': 'cm', 'Meters': 'm'}.get(units, 'unit unknown')
        set_path_label(self.context_source, source_path, 'Original trajectories')
        self.context_source.setToolTip(source_path + '\nUnmodified observations; physical cause is not independently verified.')
        self.context_target.blockSignals(True)
        self.context_target.clear()
        for target in targets:
            label = 'Rigid body' if target == RigidBodyCols.BASE_NAME else 'Marker ' + target
            self.context_target.addItem(label, target)
        selected = preferred_target if preferred_target in targets else (
            RigidBodyCols.BASE_NAME if RigidBodyCols.BASE_NAME in targets else (targets[0] if targets else None))
        self.context_target.setCurrentIndex(self.context_target.findData(selected))
        self.context_target.blockSignals(False)
        self.context_target.setEnabled(bool(targets))
        self.context_panel.show()
        visible_rows = min(3, len(self.candidates))
        self.table.setFixedHeight(self.table.horizontalHeader().sizeHint().height()
            + sum(self.table.rowHeight(row) for row in range(visible_rows)) + 2 * self.table.frameWidth())
        self.context_canvas.setMinimumHeight(140)
        self.evidence_canvas.setMinimumHeight(140)
        self._context_row = self.table.currentRow()
        self.resize(1280, 740)
        self._sync_plot_layout()
        self._draw_context(recenter=True)

    def _draw_context(self, *_args, recenter=False):
        if self._context_data is None or self._evidence_canvas_disposed:
            return
        old_limits = self.context_figure.axes[0].get_xlim() if self.context_figure.axes else None
        self.context_figure.clear()
        axis = self.context_figure.add_subplot(111)
        target = self.context_target.currentData()
        available = False
        if target is not None:
            times = np.asarray(self._context_data.index, dtype=float)
            for component, color in zip('XYZ', ('#c62828', '#2e7d32', '#1565c0')):
                values = pd.to_numeric(self._context_data[target + '_' + component], errors='coerce').to_numpy(float)
                axis.plot(times, values, label=component, color=color)
                available |= bool(np.any(np.isfinite(times) & np.isfinite(values)))
        if not available:
            axis.text(.5, .5, tr('Original trajectories unavailable'), transform=axis.transAxes, ha='center')
        else:
            axis.legend(loc='best', fontsize=8)
        row = self.table.currentRow()
        self.around_event_button.setEnabled(0 <= row < len(self.candidates))
        if 0 <= row < len(self.candidates):
            candidate = self.candidates[row]
            boundary = candidate.boundary_time_sec
            axis.axvline(boundary, color='0.4', linestyle=':', label='Selected event')
            if recenter:
                # Display context only; this never changes review window/gates.
                offsets = (*candidate.pre_window_time_offsets_sec, *candidate.post_window_time_offsets_sec)
                extent = max([abs(t) for t in offsets if np.isfinite(t)] or [0.])
                radius = max(.25, 2 * extent)
                axis.set_xlim(boundary - radius, boundary + radius)
        if old_limits is not None and not recenter:
            axis.set_xlim(old_limits)
        axis.set(title=tr('Original trajectories'), xlabel=tr('Time (s)'),
                 ylabel=tr(f'Position ({self._context_unit})'))
        axis.grid(True, alpha=.25)
        self.context_toolbar.update()
        self.context_toolbar.push_current()
        self.context_canvas.draw()

    def _center_context(self):
        self._draw_context(recenter=True)

    @staticmethod
    def _trace_available(times, values):
        return (len(times) == len(values) and len(times) > 0
                and np.any(np.isfinite(times) & np.isfinite(values)))

    @staticmethod
    def _number(value, suffix="°"):
        return f"{value:.6g}{suffix}" if value is not None and np.isfinite(value) else tr("Unavailable")

    def _update_evidence_plot(self, current_row: int, *_args) -> None:
        if current_row != self._context_row:
            self._context_row = current_row
            self._draw_context(recenter=True)
        self.evidence_figure.clear()
        axis = self.evidence_figure.add_subplot(111)
        if current_row < 0 or current_row >= len(self.candidates):
            axis.text(0.5, 0.5, "No event selected", ha="center", va="center")
            axis.set_axis_off()
            self.candidate_summary.hide()
            self.details_section.hide()
            self.candidate_details.clear()
            self.preview_status.clear()
            self.preview_status.setToolTip("")
            self.evidence_canvas.draw()
            return

        candidate = self.candidates[current_row]
        selected_axis = self._axis_combos[current_row].currentData()
        selected = candidate.hypothesis(selected_axis)
        post_times = candidate.post_window_time_offsets_sec
        actual_refit = candidate.correction_kind == "face_assignment"
        selected_trace = bool(selected and self._trace_available(post_times, selected.trace_deg))
        none = candidate.hypothesis(None)
        none_trace = bool(none and self._trace_available(post_times, none.trace_deg))
        preview_available = selected_trace if actual_refit else bool(
            selected_axis and selected and np.isfinite(selected.residual_deg)
            and any(np.isfinite(post_times)))
        self.preview_status.setText("" if preview_available else tr("Preview unavailable"))
        self.preview_status.setToolTip("" if preview_available else
            f"Comparison samples: {len(candidate.pre_window_time_offsets_sec)} before, {len(post_times)} after. {candidate.reason}")

        self.candidate_summary.show()
        self.details_section.show()
        self.no_correction_summary.setVisible(actual_refit)
        if actual_refit:
            baseline = self._number(none.residual_deg if none_trace else None)
            self.no_correction_summary.setText(tr("No correction  {}").format(baseline))
        self.preview_summary.setVisible(selected_axis is not None)
        if selected_axis is not None:
            template = "{} preview  {}" if actual_refit else "{} prediction  {}"
            preview = self._number(selected.residual_deg if preview_available else None)
            self.preview_summary.setText(tr(template).format(selected_axis, preview))
        coverage = selected.coverage_ratio if selected else candidate.coverage_ratio
        coverage_text = f"{coverage:.0%}" if np.isfinite(coverage) else tr("Unavailable")
        self.coverage_summary.setText(tr("Marker coverage  {}").format(coverage_text))
        fit = selected.marker_rmse_mm if selected else None
        self.candidate_details.setText("\n".join(filter(None, (
            candidate.trigger, candidate.reason,
            tr("Marker fit error  {}").format(self._number(fit, ' mm')),
        ))))
        self.details_scroll.verticalScrollBar().setValue(0)

        for times, values, label in (
            (candidate.pre_window_time_offsets_sec, candidate.pre_window_residual_deg, "Before"),
            (post_times, candidate.post_window_raw_residual_deg, "Original"),
        ):
            if self._trace_available(times, values):
                axis.plot(times, values, marker="o", label=label)
        if actual_refit and selected_trace:
            axis.plot(post_times, selected.trace_deg, marker="o", linestyle="--",
                      label=f"Preview {selected_axis}" if selected_axis else "Refit none")
        elif not actual_refit and preview_available:
            if selected_axis == candidate.best_hypothesis_label and self._trace_available(post_times, candidate.post_window_best_residual_deg):
                axis.plot(post_times, candidate.post_window_best_residual_deg, marker="o", linestyle="--", label=f"Predicted {selected_axis}")
            else:
                axis.axhline(selected.residual_deg, linestyle="--", label=f"Predicted {selected_axis} mean")
        axis.axvline(0.0, linestyle=":", linewidth=1.0, color="0.5")
        axis.set_title(tr("Axis preview"))
        axis.set_xlabel(tr("Time from event (s)"))
        axis.set_ylabel(tr("Relative rotation (°)"))
        axis.grid(True, alpha=0.25)
        if axis.get_legend_handles_labels()[0]:
            axis.legend(loc="best", fontsize=8)
        low, high = axis.get_ylim()
        if high - low < 1.0:
            centre = (low + high) / 2.0
            axis.set_ylim(centre - .5, centre + .5)
        self.evidence_canvas.draw()

    def _dispose_evidence_canvas(self) -> None:
        if self._evidence_canvas_disposed:
            return
        self._evidence_canvas_disposed = True
        self._context_data = None
        self.context_toolbar.update()
        self.context_figure.clear()
        try:
            self.table.currentCellChanged.disconnect(self._update_evidence_plot)
        except (RuntimeError, TypeError):
            pass
        try:
            self.evidence_canvas.close()
            self.context_toolbar.close()
            self.context_canvas.close()
        except RuntimeError:
            pass

    def done(self, result: int) -> None:
        self._dispose_evidence_canvas()
        super().done(result)

    def closeEvent(self, event) -> None:
        self._dispose_evidence_canvas()
        super().closeEvent(event)

    def approval_checkbox(self, row: int) -> QCheckBox:
        return self._approval_checkboxes[row]

    def axis_combo(self, row: int) -> QComboBox:
        return self._axis_combos[row]

    def get_decisions(self) -> list[MarkerCorrectionDecision]:
        decisions = []
        for row, candidate in enumerate(self.candidates):
            approved = self._approval_checkboxes[row].isChecked()
            selected_axis = self._axis_combos[row].currentData()
            permutation = ()
            if approved:
                if selected_axis is None:
                    raise ValueError(
                        f"Select local X, Y, or Z for the approved event at "
                        f"{candidate.boundary_time_sec:.6f} s."
                    )
                hypothesis = candidate.hypothesis(selected_axis)
                permutation = candidate.permutation_for_axis(selected_axis)
                if candidate.correction_kind == "face_assignment":
                    if hypothesis is None or not hypothesis.applicable:
                        raise ValueError("The selected axis has no valid face assignment. "
                                         + (hypothesis.mapping_reason if hypothesis else "No evidence window."))
                elif not permutation:
                    raise ValueError(
                        f"Local {selected_axis} does not have a valid marker-label "
                        f"permutation at {candidate.boundary_time_sec:.6f} s."
                    )
            decisions.append(
                MarkerCorrectionDecision(
                    event_id=candidate.event_id,
                    boundary_time_sec=candidate.boundary_time_sec,
                    approved=approved,
                    axis=selected_axis if approved else None,
                    recommendation_axis=candidate.recommendation_axis,
                    permutation=permutation,
                    recommendation_reason=candidate.reason,
                    evidence_json=candidate.evidence_json(),
                    algorithm_version=candidate.algorithm_version,
                    gate_version=candidate.gate_version,
                    correction_kind=candidate.correction_kind,
                )
            )
        return decisions

    def accept(self) -> None:
        try:
            self.get_decisions()
        except ValueError as exc:
            QMessageBox.warning(self, tr("Correction Axis Required"), str(exc))
            return
        super().accept()
