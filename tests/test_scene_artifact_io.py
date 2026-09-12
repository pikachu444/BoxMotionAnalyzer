"""Selected observed intervals keep review meaning through slice/proc files."""
import csv
import json
from pathlib import Path
from types import SimpleNamespace

import pandas as pd
import pytest

from src.analysis.pipeline.artifact_io import (
    add_timeline_context_columns,
    read_slice_metadata,
    save_proc_file,
    save_slice_file,
    update_slice_box_dimensions,
)
from src.analysis.pipeline.data_loader import DataLoader
from test_marker_flip_artifact_io import _raw_bundle


START = 1.123456789012345
END = 3.876543210987654


def _review(*, registered=False, identified=False):
    return {
        "version": 1,
        "source_sha256": "f" * 64,
        "candidate": {
            "id": "candidate-2", "auto_start": 1.0, "auto_end": 4.0,
            "start": START, "end": END,
            "evidence_class": "free_fall" if identified else "tip_or_rotation",
            "motion": "free_fall" if identified else "tip_or_rotation", "tags": ["partial_capture"],
            "origin": "automatic", "decision": "include",
            "evidence_status": "current", "rotation_deg": 89.5,
        },
        "detection": {
            "version": "observed-motion-v1", "settings": {"window_s": .08},
            "registration_sha256": "a" * 64 if registered else None,
        },
        "identity": {
            "ista_type": "G" if identified else "Unknown",
            "scenario_id": "G01" if identified else None,
            "scenario_kind": "free_fall" if identified else None,
            "confirmed": identified, "reference_edition": "2018-03",
            "applied_edition": "2018-03" if identified else None,
        },
    }


def _save(path, review=None, *, artifact=None):
    header, raw = _raw_bundle()
    raw.iloc[:, 1] = [0.0, START, 2.0, END, 4.0, 5.0]
    if artifact is not None:
        header["artifact_metadata"] = artifact
    return save_slice_file(
        filepath=str(path), header_info=header, raw_data=raw,
        source_path="observed.csv", full_start=0.0, full_end=5.0,
        user_start=START, user_end=END, pad_rows=1,
        box_dims=(300., 180., 90.), scene_name="rotation",
        scene_review_json="" if review is None else json.dumps(review),
    )


def _rows(path):
    with path.open(encoding="utf-8", newline="") as infile:
        return list(csv.reader(infile))


def test_included_unknown_trial_keeps_exact_review_and_bounds_through_proc(tmp_path):
    path = tmp_path / "rotation.slice"
    saved = _save(path, _review())
    reopened = read_slice_metadata(str(path))
    assert reopened == saved
    assert json.loads(reopened.scene_review_json) == _review()
    assert (reopened.user_start, reopened.user_end) == (START, END)
    _, raw = DataLoader().load_csv(str(path))
    # Padded context remains distinct from the user-reviewed interval.
    assert list(pd.to_numeric(raw["Time"])) == [0.0, START, 2.0, END, 4.0]
    from src.analysis.ui.widget_slice_processing import WidgetSliceProcessing
    context = WidgetSliceProcessing._build_timeline_context(
        SimpleNamespace(slice_metadata=reopened)
    )
    assert context["scene_review_json"] == saved.scene_review_json
    frame = pd.DataFrame({"Frame": [1, 2, 3]}, index=pd.Index([START, 2.0, END], name="Time"))
    proc = tmp_path / "rotation.proc"
    save_proc_file(str(proc), add_timeline_context_columns(frame, context))
    result = DataLoader().load_result_csv(str(proc))
    assert result[("Info", "SceneReview", "Json")].tolist() == [saved.scene_review_json] * 3
    assert json.loads(result[("Info", "SceneReview", "Json")].iloc[0])["identity"]["scenario_id"] is None


def test_legacy_slice_stays_usable_without_scene_review_metadata(tmp_path):
    path = tmp_path / "legacy.slice"
    _save(path)
    assert read_slice_metadata(str(path)).scene_review_json == ""
    _, raw = DataLoader().load_csv(str(path))
    assert len(raw) == 5
    frame = add_timeline_context_columns(pd.DataFrame({"Frame": [1]}), {})
    assert "SceneReview_Json" not in frame


@pytest.mark.parametrize("change", ["unreviewed", "exclude", "bounds"])
def test_unapproved_or_different_interval_cannot_replace_saved_slice(tmp_path, change):
    path = tmp_path / "reviewed.slice"
    _save(path, _review())
    before = path.read_bytes()
    review = _review()
    if change == "bounds":
        review["candidate"]["start"] = START + .1
    else:
        review["candidate"]["decision"] = change
    with pytest.raises(ValueError):
        _save(path, review)
    assert path.read_bytes() == before


@pytest.mark.parametrize("change", ["decision", "missing_bounds"])
def test_unapproved_metadata_is_rejected_when_a_slice_is_reopened(tmp_path, change):
    path = tmp_path / "unreviewed.slice"
    _save(path, _review())
    rows = _rows(path)
    review = _review()
    if change == "decision":
        review["candidate"]["decision"] = "unreviewed"
    rows[1] = [
        "SceneReviewJson=" + json.dumps(review) if cell.startswith("SceneReviewJson=") else cell
        for cell in rows[1]
    ]
    if change == "missing_bounds":
        rows[1] = [cell for cell in rows[1] if not cell.startswith("user_start=")]
    with path.open("w", encoding="utf-8", newline="") as outfile:
        csv.writer(outfile).writerows(rows)
    with pytest.raises(ValueError):
        DataLoader().load_csv(str(path))


def test_dimension_rewrite_preserves_interval_but_clears_geometry_identity(tmp_path):
    path = tmp_path / "registered.slice"
    original_review = _review(registered=True, identified=True)
    original_review["candidate"].update(
        item_candidates=["G01", "G10"],
        geometry={"status": "registered", "floor_crossings": [{"time_after": 2.0}]},
        support_cycle={"version": 1, "status": "complete_cycle", "returned": True},
    )
    _save(path, original_review, artifact={
        "IstaType": "G", "ScenarioId": "G01", "ScenarioKind": "free_fall",
    })
    old = read_slice_metadata(str(path))
    raw_before = _rows(path)[2:]
    same = update_slice_box_dimensions(str(path), (300., 180., 90.))
    assert same.scene_review_json == old.scene_review_json
    updated = update_slice_box_dimensions(str(path), (310., 180., 90.))
    review = json.loads(updated.scene_review_json)
    assert review["candidate"]["decision"] == "include"
    assert (review["candidate"]["start"], review["candidate"]["end"]) == (START, END)
    assert review["candidate"]["evidence_status"] == "geometry_changed"
    assert review["detection"]["registration_sha256"] is None
    assert review["candidate"]["item_candidates"] == []
    assert review["candidate"]["geometry"] == {}
    assert review["candidate"]["support_cycle"] == {"version": 1, "status": "geometry_changed"}
    assert review["identity"]["ista_type"] == "G"
    assert review["identity"]["confirmed"] is False
    assert review["identity"]["scenario_id"] is None
    assert review["identity"]["scenario_kind"] is None
    assert json.loads(updated.artifact_metadata_json)["ScenarioId"] is None
    assert _rows(path)[2:] == raw_before
    assert read_slice_metadata(str(path)) == updated


def test_failed_slice_publication_preserves_existing_file_and_removes_temporary(tmp_path, monkeypatch):
    path = tmp_path / "reviewed.slice"
    _save(path, _review())
    before = path.read_bytes()
    def fail_replace(*args):
        raise PermissionError("Destination is open")
    monkeypatch.setattr("src.analysis.pipeline.artifact_io.os.replace", fail_replace)
    with pytest.raises(PermissionError, match="Destination is open"):
        _save(path, _review())
    assert path.read_bytes() == before
    assert list(tmp_path.iterdir()) == [path]


def test_valid_long_slice_filename_saves_and_reopens(tmp_path):
    path = tmp_path / ("a" * 244 + ".slice")
    saved = _save(path, _review())
    assert read_slice_metadata(str(path)) == saved
    assert list(tmp_path.iterdir()) == [path]


def test_cleanup_failure_does_not_replace_the_original_save_error(tmp_path, monkeypatch):
    path = tmp_path / "reviewed.slice"
    _save(path, _review())
    before = path.read_bytes()
    original_error = PermissionError("Destination is open")
    def fail_replace(*args):
        raise original_error
    def fail_unlink(*args, **kwargs):
        raise PermissionError("Temporary file is open")
    with monkeypatch.context() as scoped:
        scoped.setattr("src.analysis.pipeline.artifact_io.os.replace", fail_replace)
        scoped.setattr(Path, "unlink", fail_unlink)
        with pytest.raises(PermissionError) as failure:
            _save(path, _review())
    assert failure.value is original_error
    assert path.read_bytes() == before
    temporary_files = [item for item in tmp_path.iterdir() if item != path]
    assert len(temporary_files) == 1
    assert any(str(temporary_files[0]) in note and "Temporary file is open" in note
               for note in failure.value.__notes__)
    temporary_files[0].unlink()
