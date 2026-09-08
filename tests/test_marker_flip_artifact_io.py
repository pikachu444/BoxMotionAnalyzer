import csv
import hashlib
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import pandas as pd

from src.analysis.pipeline.artifact_io import (
    MARKER_CORRECTION_SCHEMA_VERSION,
    add_timeline_context_columns,
    read_corrected_source_metadata,
    read_slice_metadata,
    save_corrected_source_file,
    save_proc_file,
    save_slice_file,
)
from src.analysis.pipeline.data_loader import DataLoader
from src.analysis.pipeline.marker_flip import (
    MARKER_FLIP_ALGORITHM_VERSION,
    MarkerCorrectionDecision,
    apply_approved_marker_permutations,
    marker_triplet_indices,
)
from src.config.data_columns import (
    HeaderL1,
    HeaderL2,
    HeaderL3,
    MarkerCorrectionMetaCols,
    TimeCols,
)


def test_slice_reload_preserves_full_precision_endpoints(tmp_path):
    from src.analysis.pipeline.slicer import Slicer
    from src.analysis.pipeline.parser import Parser
    header, raw = _raw_bundle()
    times = [0.008000000000000002, .016, .024, .032, .040, .04800000000000003]
    raw.iloc[:, 1] = times
    path = tmp_path / 'precision.slice'
    save_slice_file(filepath=str(path), header_info=header, raw_data=raw,
                    source_path='observed.csv', box_dims=(200., 120., 80.),
                    full_start=times[0], full_end=times[-1], user_start=times[0],
                    user_end=times[-1], pad_rows=0)
    metadata = read_slice_metadata(str(path))
    assert metadata.user_start == times[0] and metadata.user_end == times[-1]
    loaded_header, loaded = DataLoader().load_csv(str(path))
    frame = Parser({}).process(loaded_header, loaded)
    result = Slicer('time', metadata.user_start, metadata.user_end).process(frame)
    assert len(result) == len(times)
    # A real interval difference must still exclude the endpoint.
    assert len(Slicer('time', times[0] + 1e-10, times[-1] - 1e-10).process(frame)) == 4


def _raw_bundle() -> tuple[dict[str, list[str]], pd.DataFrame]:
    marker_ids = ["A", "B", "C", "D"]
    type_header = ["", ""]
    name_header = ["Frame", "Time"]
    id_header = ["", ""]
    parent_header = ["", ""]
    category_header = ["", ""]
    component_header = [TimeCols.FRAME, TimeCols.TIME]
    for marker_id in marker_ids:
        type_header.extend(["Rigid Body Marker"] * 3)
        name_header.extend([f"Box:{marker_id}"] * 3)
        id_header.extend([marker_id] * 3)
        parent_header.extend(["Box"] * 3)
        category_header.extend(["Position"] * 3)
        component_header.extend(["X", "Y", "Z"])

    rows = []
    for row_index in range(6):
        row = [float(row_index), float(row_index)]
        for marker_index in range(len(marker_ids)):
            base = row_index * 1000.0 + marker_index * 10.0
            row.extend([base + 1.0, base + 2.0, base + 3.0])
        rows.append(row)

    return (
        {
            "type": type_header,
            "name": name_header,
            "id": id_header,
            "parent": parent_header,
            "category": category_header,
            "component": component_header,
        },
        pd.DataFrame(rows, columns=component_header),
    )


def _decisions() -> list[MarkerCorrectionDecision]:
    permutation = (("A", "B"), ("B", "A"), ("C", "D"), ("D", "C"))
    return [
        MarkerCorrectionDecision(
            event_id="event-off",
            boundary_time_sec=1.0,
            approved=False,
            recommendation_axis="X",
            recommendation_reason="Recommendation retained while operator leaves correction OFF.",
            evidence_json='{"fixture":"off"}',
        ),
        MarkerCorrectionDecision(
            event_id="event-override",
            boundary_time_sec=3.0,
            approved=True,
            axis="Y",
            recommendation_axis="X",
            permutation=permutation,
            recommendation_reason="Operator selected Y instead of recommended X.",
            evidence_json='{"fixture":"override"}',
        ),
    ]


class TestMarkerFlipArtifactIo(unittest.TestCase):
    def test_corrected_source_refuses_to_overwrite_original_csv(self):
        header_info, raw_df = _raw_bundle()

        with tempfile.TemporaryDirectory() as temp_dir:
            original_path = Path(temp_dir) / "capture.csv"
            original_bytes = b"original-must-remain\n"
            original_path.write_bytes(original_bytes)

            with self.assertRaisesRegex(ValueError, "saved separately"):
                save_corrected_source_file(
                    filepath=str(original_path),
                    header_info=header_info,
                    raw_data=raw_df,
                    original_source_path=str(original_path),
                    decisions=_decisions(),
                )

            self.assertEqual(original_path.read_bytes(), original_bytes)

    def test_corrected_source_refuses_original_filename_when_only_identity_is_known(self):
        header_info, raw_df = _raw_bundle()

        with tempfile.TemporaryDirectory() as temp_dir:
            target_path = Path(temp_dir) / "capture.csv"

            with self.assertRaisesRegex(ValueError, "saved separately"):
                save_corrected_source_file(
                    filepath=str(target_path),
                    header_info=header_info,
                    raw_data=raw_df,
                    original_source_path="capture.csv",
                    original_source_sha256="known-original-hash",
                    decisions=_decisions(),
                )

            self.assertFalse(target_path.exists())

    def test_corrected_source_round_trip_preserves_values_decisions_and_identity(self):
        header_info, raw_df = _raw_bundle()
        decisions = _decisions()
        corrected_raw = apply_approved_marker_permutations(
            raw_df,
            header_info,
            decisions,
        )

        with tempfile.TemporaryDirectory() as temp_dir:
            original_path = Path(temp_dir) / "capture.csv"
            original_bytes = b"independent-original-source-identity\n"
            original_path.write_bytes(original_bytes)
            corrected_path = Path(temp_dir) / "capture.corrected.csv"

            written_metadata = save_corrected_source_file(
                filepath=str(corrected_path),
                header_info=header_info,
                raw_data=corrected_raw,
                original_source_path=str(original_path),
                decisions=decisions,
            )
            read_metadata = read_corrected_source_metadata(str(corrected_path))

            self.assertEqual(read_metadata, written_metadata)
            self.assertEqual(read_metadata.source, original_path.name)
            self.assertEqual(read_metadata.reviewed_source, corrected_path.name)
            self.assertEqual(
                read_metadata.source_sha256,
                hashlib.sha256(original_bytes).hexdigest(),
            )
            self.assertEqual(read_metadata.schema_version, MARKER_CORRECTION_SCHEMA_VERSION)
            self.assertEqual(read_metadata.algorithm_version, MARKER_FLIP_ALGORITHM_VERSION)
            self.assertEqual(read_metadata.event_count, 2)
            self.assertEqual(read_metadata.approved_event_count, 1)
            self.assertFalse(read_metadata.decisions[0].approved)
            self.assertIsNone(read_metadata.decisions[0].axis)
            self.assertEqual(read_metadata.decisions[0].recommendation_axis, "X")
            self.assertEqual(read_metadata.decisions[1].axis, "Y")
            self.assertEqual(read_metadata.decisions[1].recommendation_axis, "X")

            loaded_header, loaded_raw = DataLoader().load_csv(str(corrected_path))
            self.assertEqual(loaded_header["name"], header_info["name"])
            triplets = marker_triplet_indices(header_info)
            source_values = raw_df.iloc[3, list(triplets["B"])].astype(float).to_numpy()
            corrected_values = loaded_raw.iloc[3, list(triplets["A"])].astype(float).to_numpy()
            self.assertEqual(corrected_values.tolist(), source_values.tolist())

    def test_loaded_metadata_uses_the_actual_corrected_filename_after_rename(self):
        header_info, raw_df = _raw_bundle()

        with tempfile.TemporaryDirectory() as temp_dir:
            original_path = Path(temp_dir) / "capture.csv"
            original_path.write_text("source", encoding="utf-8")
            saved_path = Path(temp_dir) / "capture.corrected.csv"
            renamed_path = Path(temp_dir) / "renamed.corrected.csv"
            save_corrected_source_file(
                filepath=str(saved_path),
                header_info=header_info,
                raw_data=raw_df,
                original_source_path=str(original_path),
                decisions=_decisions(),
            )
            saved_path.rename(renamed_path)

            metadata = read_corrected_source_metadata(str(renamed_path))

            self.assertEqual(metadata.reviewed_source, renamed_path.name)

    def test_atomic_save_failure_preserves_existing_target_and_removes_temp_file(self):
        header_info, raw_df = _raw_bundle()
        decisions = _decisions()

        with tempfile.TemporaryDirectory() as temp_dir:
            original_path = Path(temp_dir) / "capture.csv"
            original_path.write_text("source", encoding="utf-8")
            target_path = Path(temp_dir) / "capture.corrected.csv"
            target_path.write_text("existing-target", encoding="utf-8")

            with patch(
                "src.analysis.pipeline.artifact_io.os.replace",
                side_effect=OSError("simulated replace failure"),
            ):
                with self.assertRaisesRegex(OSError, "simulated replace failure"):
                    save_corrected_source_file(
                        filepath=str(target_path),
                        header_info=header_info,
                        raw_data=raw_df,
                        original_source_path=str(original_path),
                        decisions=decisions,
                    )

            self.assertEqual(target_path.read_text(encoding="utf-8"), "existing-target")
            self.assertEqual(
                list(Path(temp_dir).glob(f".{target_path.name}.*.tmp")),
                [],
            )

    def test_slice_and_proc_keep_actual_corrected_source_provenance(self):
        header_info, raw_df = _raw_bundle()
        decisions = _decisions()
        corrected_raw = apply_approved_marker_permutations(
            raw_df,
            header_info,
            decisions,
        )

        with tempfile.TemporaryDirectory() as temp_dir:
            original_path = Path(temp_dir) / "capture.csv"
            original_path.write_text("source", encoding="utf-8")
            corrected_path = Path(temp_dir) / "capture.corrected.csv"
            correction_metadata = save_corrected_source_file(
                filepath=str(corrected_path),
                header_info=header_info,
                raw_data=corrected_raw,
                original_source_path=str(original_path),
                decisions=decisions,
            )
            slice_path = Path(temp_dir) / "capture_scene.slice"
            save_slice_file(
                filepath=str(slice_path),
                header_info=header_info,
                raw_data=corrected_raw,
                source_path=str(corrected_path),
                full_start=0.0,
                full_end=5.0,
                user_start=1.0,
                user_end=4.0,
                box_dims=(100.0, 80.0, 60.0),
                pad_rows=0,
                scene_name="scene",
                marker_correction_metadata=correction_metadata,
            )
            slice_metadata = read_slice_metadata(str(slice_path))

            self.assertEqual(slice_metadata.source, corrected_path.name)
            self.assertEqual(
                slice_metadata.correction_reviewed_source,
                corrected_path.name,
            )
            self.assertEqual(
                slice_metadata.correction_original_source,
                original_path.name,
            )
            self.assertEqual(
                slice_metadata.correction_original_source_sha256,
                correction_metadata.source_sha256,
            )
            self.assertEqual(slice_metadata.correction_event_count, 2)
            self.assertEqual(slice_metadata.correction_approved_event_count, 1)

            context = {
                "full_start_sec": slice_metadata.full_start,
                "full_end_sec": slice_metadata.full_end,
                "slice_start_sec": slice_metadata.user_start,
                "slice_end_sec": slice_metadata.user_end,
                "marker_correction_schema_version": (
                    slice_metadata.correction_schema_version
                ),
                "marker_correction_algorithm_version": (
                    slice_metadata.correction_algorithm_version
                ),
                "marker_correction_original_source": (
                    slice_metadata.correction_original_source
                ),
                "marker_correction_original_source_sha256": (
                    slice_metadata.correction_original_source_sha256
                ),
                "marker_correction_reviewed_source": (
                    slice_metadata.correction_reviewed_source
                ),
                "marker_correction_event_count": (
                    slice_metadata.correction_event_count
                ),
                "marker_correction_approved_event_count": (
                    slice_metadata.correction_approved_event_count
                ),
                "marker_correction_events_json": (
                    slice_metadata.correction_events_json
                ),
            }
            processed = add_timeline_context_columns(
                pd.DataFrame({"Metric": [1.0, 2.0]}),
                context,
            )
            self.assertEqual(
                processed[MarkerCorrectionMetaCols.REVIEWED_SOURCE].iloc[0],
                corrected_path.name,
            )
            self.assertEqual(
                processed[MarkerCorrectionMetaCols.APPROVED_EVENT_COUNT].iloc[0],
                1,
            )

            proc_path = Path(temp_dir) / "capture_scene.proc"
            save_proc_file(str(proc_path), processed)
            loaded_proc = pd.read_csv(proc_path, header=[0, 1, 2])
            reviewed_source_column = (
                HeaderL1.INFO,
                HeaderL2.MARKER_CORRECTION,
                HeaderL3.MARKER_CORRECTION_REVIEWED_SOURCE,
            )
            schema_column = (
                HeaderL1.INFO,
                HeaderL2.MARKER_CORRECTION,
                HeaderL3.MARKER_CORRECTION_SCHEMA_VERSION,
            )
            algorithm_column = (
                HeaderL1.INFO,
                HeaderL2.MARKER_CORRECTION,
                HeaderL3.MARKER_CORRECTION_ALGORITHM_VERSION,
            )
            original_source_column = (
                HeaderL1.INFO,
                HeaderL2.MARKER_CORRECTION,
                HeaderL3.MARKER_CORRECTION_ORIGINAL_SOURCE,
            )
            original_hash_column = (
                HeaderL1.INFO,
                HeaderL2.MARKER_CORRECTION,
                HeaderL3.MARKER_CORRECTION_ORIGINAL_SOURCE_SHA256,
            )
            event_count_column = (
                HeaderL1.INFO,
                HeaderL2.MARKER_CORRECTION,
                HeaderL3.MARKER_CORRECTION_EVENT_COUNT,
            )
            approved_count_column = (
                HeaderL1.INFO,
                HeaderL2.MARKER_CORRECTION,
                HeaderL3.MARKER_CORRECTION_APPROVED_EVENT_COUNT,
            )
            events_json_column = (
                HeaderL1.INFO,
                HeaderL2.MARKER_CORRECTION,
                HeaderL3.MARKER_CORRECTION_EVENTS_JSON,
            )
            self.assertEqual(str(loaded_proc[schema_column].iloc[0]), "2")
            self.assertEqual(str(loaded_proc[algorithm_column].iloc[0]), "2.0")
            self.assertEqual(
                loaded_proc[original_source_column].iloc[0],
                original_path.name,
            )
            self.assertEqual(
                loaded_proc[original_hash_column].iloc[0],
                correction_metadata.source_sha256,
            )
            self.assertEqual(loaded_proc[reviewed_source_column].iloc[0], corrected_path.name)
            self.assertEqual(int(loaded_proc[event_count_column].iloc[0]), 2)
            self.assertEqual(int(loaded_proc[approved_count_column].iloc[0]), 1)
            self.assertEqual(
                loaded_proc[events_json_column].iloc[0],
                correction_metadata.events_json,
            )

            with slice_path.open("r", encoding="utf-8", newline="") as infile:
                rows = list(csv.reader(infile))
            self.assertIn(
                f"correction_reviewed_source={corrected_path.name}",
                rows[1],
            )


if __name__ == "__main__":
    unittest.main()
