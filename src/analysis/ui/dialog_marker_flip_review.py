from __future__ import annotations

from typing import Iterable

from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QGroupBox,
    QHeaderView,
    QLabel,
    QMessageBox,
    QPlainTextEdit,
    QSizePolicy,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from src.analysis.pipeline.marker_flip import (
    MarkerCorrectionDecision,
    MarkerFlipCandidate,
    SUPPORTED_LOCAL_AXES,
    normalize_marker_corrections,
)


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

        self.setWindowTitle("Marker Flip Review")
        self.resize(960, 680)
        self.setMinimumSize(820, 600)
        self._setup_ui()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        intro = QLabel(
            "Recommendations are evidence only. Every correction is OFF until you explicitly "
            "check Apply and choose a local X, Y, or Z axis. The axis identifies the box-local "
            "half-turn for analysis. Face review preserves solved marker XYZ and changes their "
            "analysis face assignments in a separate file. It does not restore physical marker positions."
        )
        intro.setWordWrap(True)
        layout.addWidget(intro)

        self.table = QTableWidget(len(self.candidates), 4, self)
        self.table.setHorizontalHeaderLabels(
            ["Boundary (s)", "Recommendation", "Apply", "Selected local axis"]
        )
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setAlternatingRowColors(True)
        self.table.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.table.setMinimumHeight(125)
        self.table.setMaximumHeight(210)
        self.table.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
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
                f"Local {candidate.recommendation_axis} (180°)"
                if candidate.recommendation_axis is not None
                else "No recommendation"
            )
            recommendation_item = QTableWidgetItem(recommendation_text)
            recommendation_item.setToolTip(candidate.reason)
            self.table.setItem(row, 1, recommendation_item)

            approval = QCheckBox('OFF')
            approval.setAccessibleName(f"Apply correction at {candidate.boundary_time_sec:.6f} seconds")
            approval.toggled.connect(lambda checked, checkbox=approval: checkbox.setText('ON' if checked else 'OFF'))
            approval.setChecked(bool(existing and existing.approved))
            approval_container = QWidget()
            approval_layout = QVBoxLayout(approval_container)
            approval_layout.setContentsMargins(8, 0, 8, 0)
            approval_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
            approval_layout.addWidget(approval)
            self.table.setCellWidget(row, 2, approval_container)

            axis_combo = QComboBox()
            axis_combo.setAccessibleName(
                f"Local correction axis at {candidate.boundary_time_sec:.6f} seconds"
            )
            axis_combo.addItem("No correction", userData=None)
            for axis in SUPPORTED_LOCAL_AXES:
                axis_combo.addItem(f"Local {axis} (180°)", userData=axis)
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
            axis_combo.currentIndexChanged.connect(lambda _index, r=row: self._update_evidence_plot(r))

        layout.addWidget(self.table, 1)

        details_group = QGroupBox("Selected candidate details")
        details_layout = QVBoxLayout(details_group)
        self.candidate_details = QPlainTextEdit()
        self.candidate_details.setReadOnly(True)
        self.candidate_details.setLineWrapMode(QPlainTextEdit.LineWrapMode.WidgetWidth)
        self.candidate_details.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )
        self.candidate_details.setMinimumHeight(82)
        self.candidate_details.setMaximumHeight(115)
        self.candidate_details.setAccessibleName("Selected marker flip candidate details")
        details_layout.addWidget(self.candidate_details)
        layout.addWidget(details_group)

        self.evidence_figure = Figure(figsize=(8, 2.4), dpi=100)
        self.evidence_canvas = FigureCanvas(self.evidence_figure)
        self.evidence_canvas.setMinimumHeight(170)
        self.evidence_canvas.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Expanding,
        )
        layout.addWidget(self.evidence_canvas, 2)
        self.table.currentCellChanged.connect(self._update_evidence_plot)
        if self.candidates:
            self.table.selectRow(0)
            self._update_evidence_plot(0)

        self.button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel,
            parent=self,
        )
        self.button_box.accepted.connect(self.accept)
        self.button_box.rejected.connect(self.reject)
        layout.addWidget(self.button_box)

    def _update_evidence_plot(self, current_row: int, *_args) -> None:
        self.evidence_figure.clear()
        axis = self.evidence_figure.add_subplot(111)
        if current_row < 0 or current_row >= len(self.candidates):
            axis.text(0.5, 0.5, "Select a candidate to inspect its evidence.", ha="center", va="center")
            axis.set_axis_off()
            self.candidate_details.clear()
            self.evidence_canvas.draw()
            return

        candidate = self.candidates[current_row]
        selected_axis = self._axis_combos[current_row].currentData()
        selected = candidate.hypothesis(selected_axis)
        marker_rmse = (
            "N/A" if candidate.marker_rmse_mm is None else f"{candidate.marker_rmse_mm:.2f} mm"
        )
        self.candidate_details.setPlainText(
            "\n".join(
                (
                    f"Trigger: {candidate.trigger}",
                    "Recommendation: "
                    f"{candidate.recommendation_axis or 'none'} — {candidate.reason}",
                    "Evidence: "
                    f"jump {candidate.no_correction_residual_deg:.1f}° → "
                    f"{candidate.best_residual_deg:.1f}°; reduction="
                    f"{candidate.discontinuity_reduction_deg:.1f}°; "
                    f"best={candidate.best_hypothesis_label}; "
                    f"match={candidate.correspondence_ratio:.0%}; "
                    f"coverage={candidate.coverage_ratio:.0%}; "
                    f"margin={candidate.confidence_margin:.0%}; "
                    f"markers={candidate.common_marker_count}; RMSE={marker_rmse}",
                    "Stable windows: "
                    f"pre={candidate.pre_stability_deg:.1f}°; "
                    f"post={candidate.post_stability_deg:.1f}° | "
                    f"algorithm={candidate.algorithm_version}; gates={candidate.gate_version}",
                )
            )
        )
        if candidate.correction_kind == "face_assignment":
            residual = f"{selected.residual_deg:.2f}°" if selected and selected.trace_deg else "unavailable"
            fit = f"{selected.marker_rmse_mm:.3f} mm" if selected and selected.marker_rmse_mm is not None else "unavailable"
            self.candidate_details.setPlainText(
                f"Trigger: {candidate.trigger}\nRecommendation: none — validation pending.\n"
                f"Selected: {selected_axis or 'NONE'}; actual bounded refit residual: {residual}; face fit RMSE: {fit}.\n"
                f"{selected.mapping_reason if selected else 'No valid refit window.'}\n"
                "Face fit is not marker correspondence or physical truth. Original Motive pose remains unchanged."
            )

        if not candidate.pre_window_time_offsets_sec or not candidate.post_window_time_offsets_sec:
            axis.text(
                0.5,
                0.5,
                "Stable-window traces are unavailable for this candidate.",
                ha="center",
                va="center",
            )
            axis.set_axis_off()
            self.evidence_figure.tight_layout()
            self.evidence_canvas.draw()
            return

        axis.plot(
            candidate.pre_window_time_offsets_sec,
            candidate.pre_window_residual_deg,
            marker="o",
            label="Pre stable window",
        )
        axis.plot(
            candidate.post_window_time_offsets_sec,
            candidate.post_window_raw_residual_deg,
            marker="o",
            label="Post window: raw",
        )
        if candidate.correction_kind == "face_assignment" and selected and selected.trace_deg:
            # A partial failed refit has no complete time trace; never attach it to wrong samples.
            if len(selected.trace_deg) == len(candidate.post_window_time_offsets_sec):
                axis.plot(candidate.post_window_time_offsets_sec, selected.trace_deg, marker="o",
                    linestyle="--", label=f"Selected {selected_axis or 'NONE'}: actual pose refit")
        elif candidate.correction_kind != "face_assignment" and selected_axis:
            # Legacy view labels the mathematical prediction explicitly.
            hypothesis = candidate.hypothesis(selected_axis)
            if hypothesis:
                axis.axhline(hypothesis.residual_deg, linestyle="--",
                    label=f"Selected {selected_axis}: predicted mean residual")
        if candidate.correction_kind != "face_assignment" and candidate.best_hypothesis_label != "NONE":
            axis.plot(
                candidate.post_window_time_offsets_sec,
                candidate.post_window_best_residual_deg,
                marker="o",
                linestyle="--",
                label=f"Post window: {candidate.best_hypothesis_label} hypothesis",
            )
        axis.axvline(0.0, linestyle=":", linewidth=1.0, label="Candidate boundary")
        axis.set_xlabel("Time from candidate boundary (s)")
        axis.set_ylabel("Orientation residual (deg)")
        axis.grid(True, alpha=0.25)
        axis.legend(loc="best", fontsize=8)
        self.evidence_figure.tight_layout()
        self.evidence_canvas.draw()

    def _dispose_evidence_canvas(self) -> None:
        if self._evidence_canvas_disposed:
            return
        self._evidence_canvas_disposed = True
        try:
            self.table.currentCellChanged.disconnect(self._update_evidence_plot)
        except (RuntimeError, TypeError):
            pass
        try:
            self.evidence_canvas.close()
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
            QMessageBox.warning(self, "Correction Axis Required", str(exc))
            return
        super().accept()
