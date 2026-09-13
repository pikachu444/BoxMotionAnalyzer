import csv
import hashlib
import json
import math
import os
import tempfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

import pandas as pd

from src.analysis.pipeline.marker_flip import (
    MARKER_FLIP_ALGORITHM_VERSION,
    MarkerCorrectionDecision,
    deserialize_marker_corrections,
    normalize_marker_corrections,
    serialize_marker_corrections,
)
from src.analysis.pipeline.face_assignment import FACE_ASSIGNMENT_ALGORITHM_VERSION
from src.config.data_columns import MarkerCorrectionMetaCols, TimeCols, TimelineMetaCols
from src.utils.header_converter import convert_to_multi_header
from src.utils.artifact_metadata import add_artifact_columns, metadata_json, normalize_metadata, validate_declared_dimensions
from src.utils.processing_settings import SETTINGS_ATTR, processing_record


CSV_FILE_EXTENSION = ".csv"
SLICE_FILE_EXTENSION = ".slice"
PROC_FILE_EXTENSION = ".proc"
RESULT_FILE_EXTENSIONS = (PROC_FILE_EXTENSION,)
SLICE_FILE_MAGIC = "BoxMotionAnalyzer Slice File"
SLICE_FILE_VERSION = "1"
CORRECTED_SOURCE_FILE_MAGIC = "BoxMotionAnalyzer Corrected Source File"
CORRECTED_SOURCE_FILE_VERSION = "2"
MARKER_CORRECTION_SCHEMA_VERSION = "2"
DEFAULT_SLICE_PADDING_ROWS = 50

SLICE_META_PREFIX_KEYS = ("magic", "version", "source", "created")
SLICE_META_DETAIL_KEYS = (
    "artifact_metadata",
    "SceneReviewJson",
    "scene",
    "box_l",
    "box_w",
    "box_h",
    "full_start",
    "full_end",
    "user_start",
    "user_end",
    "padded_start",
    "padded_end",
    "pad_rows",
    "row_count",
    "correction_schema",
    "correction_algorithm",
    "correction_original_source",
    "correction_original_source_sha256",
    "correction_reviewed_source",
    "correction_event_count",
    "correction_approved_event_count",
    "correction_events",
    "correction_context",
)

CORRECTED_SOURCE_META_PREFIX_KEYS = (
    "magic",
    "version",
    "source",
    "source_sha256",
    "reviewed_source",
    "created",
)
CORRECTED_SOURCE_META_DETAIL_KEYS = (
    "artifact_metadata",
    "correction_schema",
    "correction_algorithm",
    "correction_event_count",
    "correction_approved_event_count",
    "correction_events",
    "correction_context",
)


@dataclass(frozen=True)
class SliceMetadata:
    source: str
    created: str
    scene: str
    box_l: float | None
    box_w: float | None
    box_h: float | None
    full_start: float | None
    full_end: float | None
    user_start: float
    user_end: float
    padded_start: float
    padded_end: float
    pad_rows: int
    row_count: int
    correction_schema_version: str = ""
    correction_algorithm_version: str = ""
    correction_original_source: str = ""
    correction_original_source_sha256: str = ""
    correction_reviewed_source: str = ""
    correction_event_count: int = 0
    correction_approved_event_count: int = 0
    correction_events_json: str = ""
    correction_context_json: str = ""
    artifact_metadata_json: str = ""
    scene_review_json: str = ""


@dataclass(frozen=True)
class CorrectionSourceMetadata:
    source: str
    source_sha256: str
    reviewed_source: str
    created: str
    schema_version: str
    algorithm_version: str
    decisions: tuple[MarkerCorrectionDecision, ...]
    context_json: str = ""

    @property
    def event_count(self) -> int:
        return len(self.decisions)

    @property
    def approved_event_count(self) -> int:
        return sum(decision.approved for decision in self.decisions)

    @property
    def events_json(self) -> str:
        return serialize_marker_corrections(self.decisions)


def _safe_float(value) -> float | None:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _safe_int(value, default=0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _format_value(value) -> str:
    if isinstance(value, float):
        # Bounds are used for inclusive slicing after reload. Decimal rounding
        # can move an endpoint inside the data and silently discard its row.
        return repr(float(value))
    if value is None:
        return ""
    return str(value)


def _metadata_row_from_mapping(mapping: dict[str, object], keys: tuple[str, ...]) -> list[str]:
    return [f"{key}={_format_value(mapping.get(key))}" for key in keys]


def _parse_metadata_row(row: list[str]) -> dict[str, str]:
    parsed = {}
    for value in row:
        if "=" not in value:
            continue
        key, parsed_value = value.split("=", 1)
        parsed[key.strip()] = parsed_value.strip()
    return parsed


def _canonical_scene_review(value, *, start=None, end=None) -> str:
    if value is None or value == "":
        return ""
    from .scene_review import validate_scene_review_json
    return validate_scene_review_json(value, start=start, end=end)


def _slice_scene_review(detail_meta: dict) -> str:
    value = detail_meta.get("SceneReviewJson", "")
    if not value:
        return ""
    start = _safe_float(detail_meta.get("user_start"))
    end = _safe_float(detail_meta.get("user_end"))
    if start is None or end is None or not math.isfinite(start) or not math.isfinite(end):
        raise ValueError("Reviewed slice requires finite user_start and user_end.")
    return _canonical_scene_review(value, start=start, end=end)


def _replace_csv_rows(filepath: str, rows) -> None:
    """Publish a complete slice without truncating a previous saved result."""
    target = Path(filepath)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w", encoding="utf-8", newline="", delete=False,
            dir=target.parent, prefix=".bma-slice-", suffix=".tmp",
        ) as outfile:
            temporary = Path(outfile.name)
            csv.writer(outfile).writerows(rows)
            outfile.flush()
            os.fsync(outfile.fileno())
        os.replace(temporary, target)
    except BaseException as error:
        if temporary is not None:
            try:
                temporary.unlink(missing_ok=True)
            except OSError as cleanup_error:
                error.add_note(f"Could not remove temporary slice {temporary}: {cleanup_error}")
        raise


def _sha256_file(filepath: str) -> str:
    if not filepath:
        return ""
    path = Path(filepath)
    if not path.is_file():
        return ""
    digest = hashlib.sha256()
    with path.open("rb") as infile:
        for chunk in iter(lambda: infile.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _slice_time_bounds(raw_data: pd.DataFrame, start: float, end: float, pad_rows: int) -> tuple[int, int, float, float]:
    numeric_time = pd.to_numeric(raw_data[TimeCols.TIME], errors="coerce")
    valid_mask = numeric_time.notna()
    if not valid_mask.any():
        raise ValueError("Slice save failed: no numeric time values were found in the loaded raw data.")

    numeric_time = numeric_time[valid_mask]
    matching_indices = numeric_time[(numeric_time >= float(start)) & (numeric_time <= float(end))].index
    if len(matching_indices) == 0:
        raise ValueError("Slice save failed: the selected range does not overlap any raw data rows.")

    raw_start_index = max(0, int(matching_indices[0]) - int(pad_rows))
    raw_end_index = min(len(raw_data) - 1, int(matching_indices[-1]) + int(pad_rows))

    padded_time = pd.to_numeric(raw_data[TimeCols.TIME], errors="coerce")
    padded_start = float(padded_time.iloc[raw_start_index])
    padded_end = float(padded_time.iloc[raw_end_index])
    return raw_start_index, raw_end_index, padded_start, padded_end


def _build_slice_metadata(
    *,
    source_name: str,
    scene_name: str,
    box_dims: tuple[float, float, float] | list[float] | None,
    full_start: float | None,
    full_end: float | None,
    user_start: float,
    user_end: float,
    padded_start: float,
    padded_end: float,
    pad_rows: int,
    row_count: int,
    marker_correction_metadata: CorrectionSourceMetadata | None = None,
    artifact_metadata_json: str = "",
    scene_review_json: str = "",
) -> SliceMetadata:
    correction_events_json = (
        marker_correction_metadata.events_json if marker_correction_metadata is not None else ""
    )
    return SliceMetadata(
        source=source_name,
        created=datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        scene=scene_name,
        box_l=_safe_float(box_dims[0]) if box_dims and len(box_dims) >= 1 else None,
        box_w=_safe_float(box_dims[1]) if box_dims and len(box_dims) >= 2 else None,
        box_h=_safe_float(box_dims[2]) if box_dims and len(box_dims) >= 3 else None,
        full_start=full_start,
        full_end=full_end,
        user_start=float(user_start),
        user_end=float(user_end),
        padded_start=float(padded_start),
        padded_end=float(padded_end),
        pad_rows=int(pad_rows),
        row_count=int(row_count),
        correction_schema_version=(
            marker_correction_metadata.schema_version
            if marker_correction_metadata is not None
            else ""
        ),
        correction_algorithm_version=(
            marker_correction_metadata.algorithm_version
            if marker_correction_metadata is not None
            else ""
        ),
        correction_original_source=(
            marker_correction_metadata.source
            if marker_correction_metadata is not None
            else ""
        ),
        correction_original_source_sha256=(
            marker_correction_metadata.source_sha256
            if marker_correction_metadata is not None
            else ""
        ),
        correction_reviewed_source=(
            marker_correction_metadata.reviewed_source
            if marker_correction_metadata is not None
            else ""
        ),
        correction_event_count=(
            marker_correction_metadata.event_count
            if marker_correction_metadata is not None
            else 0
        ),
        correction_approved_event_count=(
            marker_correction_metadata.approved_event_count
            if marker_correction_metadata is not None
            else 0
        ),
        correction_events_json=correction_events_json,
        artifact_metadata_json=artifact_metadata_json,
        scene_review_json=scene_review_json,
        correction_context_json=marker_correction_metadata.context_json if marker_correction_metadata else "",
    )


def build_slice_default_name(source_path: str, scene_name: str | None = None) -> str:
    source_stem = Path(source_path).stem if source_path else "scene"
    normalized_scene = (scene_name or "slice").strip().replace(" ", "_")
    return f"{source_stem}_{normalized_scene}{SLICE_FILE_EXTENSION}"


def build_corrected_source_default_name(source_path: str) -> str:
    source_stem = Path(source_path).stem if source_path else "source"
    if source_stem.lower().endswith(".corrected"):
        source_stem = source_stem[: -len(".corrected")]
    return f"{source_stem}.corrected{CSV_FILE_EXTENSION}"


def build_proc_default_name(slice_path: str, processing_mode: str) -> str:
    source_stem = Path(slice_path).stem if slice_path else "processed"
    normalized_mode = (processing_mode or "proc").strip().replace(" ", "_")
    return f"{source_stem}_{normalized_mode}{PROC_FILE_EXTENSION}"


def build_batch_proc_path(slice_path: str) -> str:
    return str(Path(slice_path).with_suffix(PROC_FILE_EXTENSION))


def raw_csv_file_filter() -> str:
    return f"CSV Files (*{CSV_FILE_EXTENSION})"


def corrected_source_file_filter() -> str:
    return f"Corrected CSV Files (*.corrected{CSV_FILE_EXTENSION})"


def slice_file_filter() -> str:
    return f"Slice Files (*{SLICE_FILE_EXTENSION})"


def proc_file_filter() -> str:
    return f"Processed Files (*{PROC_FILE_EXTENSION})"


def result_file_filter() -> str:
    patterns = " ".join(f"*{extension}" for extension in RESULT_FILE_EXTENSIONS)
    return f"Result Files ({patterns})"


def is_result_file(filename: str) -> bool:
    return Path(filename).suffix.lower() in RESULT_FILE_EXTENSIONS


def is_slice_file(filename: str) -> bool:
    return Path(filename).suffix.lower() == SLICE_FILE_EXTENSION


def list_result_files(folder_path: str) -> list[str]:
    return sorted(
        filename
        for filename in os.listdir(folder_path)
        if is_result_file(filename)
    )


def list_slice_files(folder_path: str) -> list[str]:
    return sorted(
        filename
        for filename in os.listdir(folder_path)
        if is_slice_file(filename)
    )


def read_corrected_source_metadata(filepath: str) -> CorrectionSourceMetadata:
    with open(filepath, mode="r", encoding="utf-8-sig", newline="") as infile:
        reader = csv.reader(infile)
        first_row = next(reader, [])
        second_row = next(reader, [])

    prefix_meta = _parse_metadata_row(first_row)
    detail_meta = _parse_metadata_row(second_row)
    magic = prefix_meta.get("magic") or (first_row[0].strip() if first_row else "")
    if magic != CORRECTED_SOURCE_FILE_MAGIC:
        raise ValueError(f"Invalid corrected source header: {filepath}")
    file_version = prefix_meta.get("version", "")
    if file_version not in (CORRECTED_SOURCE_FILE_VERSION, "3"):
        raise ValueError(
            f"Unsupported corrected source version {file_version or 'missing'}: {filepath}"
        )
    schema_version = detail_meta.get("correction_schema", "")
    if schema_version not in (MARKER_CORRECTION_SCHEMA_VERSION, "3") or schema_version != file_version:
        raise ValueError(
            f"Unsupported marker correction schema {schema_version or 'missing'}: {filepath}"
        )

    decisions = deserialize_marker_corrections(detail_meta.get("correction_events"))
    expected_kind = "face_assignment" if schema_version == "3" else "marker_permutation"
    if any(d.correction_kind != expected_kind for d in decisions):
        raise ValueError("Correction kinds conflict with artifact schema.")
    if schema_version == "3":
        validate_face_context(detail_meta.get("correction_context", ""))
    declared_count = _safe_int(detail_meta.get("correction_event_count"), default=len(decisions))
    if declared_count != len(decisions):
        raise ValueError(
            "Corrected source metadata event count does not match the serialized decisions."
        )
    approved_count = sum(decision.approved for decision in decisions)
    declared_approved_count = _safe_int(
        detail_meta.get("correction_approved_event_count"),
        default=approved_count,
    )
    if declared_approved_count != approved_count:
        raise ValueError(
            "Corrected source metadata approved-event count does not match the decisions."
        )
    return CorrectionSourceMetadata(
        source=prefix_meta.get("source", ""),
        source_sha256=prefix_meta.get("source_sha256", ""),
        reviewed_source=Path(filepath).name,
        created=prefix_meta.get("created", ""),
        schema_version=schema_version,
        algorithm_version=detail_meta.get(
            "correction_algorithm",
            MARKER_FLIP_ALGORITHM_VERSION,
        ),
        decisions=tuple(decisions),
        context_json=detail_meta.get("correction_context", ""),
    )


def try_read_corrected_source_metadata(filepath: str) -> CorrectionSourceMetadata | None:
    try:
        return read_corrected_source_metadata(filepath)
    except ValueError as exc:
        if str(exc).startswith("Invalid corrected source header:"):
            return None
        raise


def save_corrected_source_file(
    *,
    filepath: str,
    header_info: dict[str, list[str]],
    raw_data: pd.DataFrame,
    original_source_path: str,
    decisions: Iterable[MarkerCorrectionDecision | dict[str, object]],
    original_source_sha256: str = "",
    context_json: str = "",
) -> CorrectionSourceMetadata:
    normalized_decisions = normalize_marker_corrections(decisions)
    is_face = bool(context_json) or any(d.correction_kind == "face_assignment" for d in normalized_decisions)
    if is_face:
        context = validate_face_context(context_json)
        from .face_assignment import face_columns, validate_materialized_faces
        if not face_columns(header_info):
            raise ValueError("Face corrected CSV requires materialized assignments.")
        if any(d.correction_kind != "face_assignment" for d in normalized_decisions):
            raise ValueError("Cannot mix face assignments and legacy correction history.")
        validate_materialized_faces(header_info, raw_data, normalized_decisions, context['base_faces'])
    current_hash = _sha256_file(original_source_path)
    if current_hash and original_source_sha256 and current_hash != original_source_sha256:
        raise ValueError("Original source changed since loading; reload before saving.")

    target_path = Path(filepath)
    original_path = Path(original_source_path) if original_source_path else None
    same_source_name = (
        original_path is not None
        and target_path.name.casefold() == original_path.name.casefold()
    )
    same_source_path = (
        original_path is not None
        and original_path.is_file()
        and target_path.resolve() == original_path.resolve()
    )
    if same_source_name or same_source_path:
        raise ValueError("Corrected source must be saved separately from the original CSV.")
    target_path.parent.mkdir(parents=True, exist_ok=True)
    source_sha256 = original_source_sha256 or _sha256_file(original_source_path)
    metadata = CorrectionSourceMetadata(
        source=Path(original_source_path).name if original_source_path else "",
        source_sha256=source_sha256,
        reviewed_source=target_path.name,
        created=datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        schema_version="3" if is_face else MARKER_CORRECTION_SCHEMA_VERSION,
        algorithm_version=FACE_ASSIGNMENT_ALGORITHM_VERSION if is_face else MARKER_FLIP_ALGORITHM_VERSION,
        decisions=tuple(normalized_decisions),
        context_json=context_json,
    )
    header_rows = [
        _metadata_row_from_mapping(
            {
                "magic": CORRECTED_SOURCE_FILE_MAGIC,
                "version": metadata.schema_version,
                "source": metadata.source,
                "source_sha256": metadata.source_sha256,
                "reviewed_source": metadata.reviewed_source,
                "created": metadata.created,
            },
            CORRECTED_SOURCE_META_PREFIX_KEYS,
        ),
        _metadata_row_from_mapping(
            {
                "correction_schema": metadata.schema_version,
                "correction_algorithm": metadata.algorithm_version,
                "correction_event_count": metadata.event_count,
                "correction_approved_event_count": metadata.approved_event_count,
                "correction_events": metadata.events_json,
                "correction_context": metadata.context_json,
                "artifact_metadata": metadata_json(header_info.get('artifact_metadata')),
            },
            CORRECTED_SOURCE_META_DETAIL_KEYS,
        ),
    ]

    temporary_path = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            newline="",
            delete=False,
            dir=target_path.parent,
            prefix=f".{target_path.name}.",
            suffix=".tmp",
        ) as outfile:
            temporary_path = Path(outfile.name)
            writer = csv.writer(outfile)
            writer.writerows(header_rows)
            for key in ("type", "name", "id", "parent", "category", "component"):
                writer.writerow(header_info.get(key, []))
            writer.writerows(raw_data.fillna("").values.tolist())
        os.replace(temporary_path, target_path)
        temporary_path = None
    finally:
        if temporary_path is not None and temporary_path.exists():
            temporary_path.unlink()
    return metadata


def read_slice_metadata(filepath: str) -> SliceMetadata:
    with open(filepath, mode="r", encoding="utf-8-sig", newline="") as infile:
        reader = csv.reader(infile)
        first_row = next(reader, [])
        second_row = next(reader, [])

    prefix_meta = _parse_metadata_row(first_row)
    detail_meta = _parse_metadata_row(second_row)
    magic = prefix_meta.get("magic") or (first_row[0].strip() if first_row else "")
    if magic != SLICE_FILE_MAGIC:
        raise ValueError(f"Invalid slice file header: {filepath}")

    if detail_meta.get('correction_schema') == '3':
        context = validate_face_context(detail_meta.get('correction_context', ''))
        if tuple(context['box_dims_mm']) != tuple(_safe_float(detail_meta.get(k)) for k in ('box_l', 'box_w', 'box_h')):
            raise ValueError('Slice dimensions differ from approved face correction context.')
        decisions = deserialize_marker_corrections(detail_meta.get('correction_events'))
        if any(d.correction_kind != 'face_assignment' for d in decisions):
            raise ValueError('Slice correction kind conflicts with schema.')
        if (_safe_int(detail_meta.get('correction_event_count'), default=-1) != len(decisions)
                or _safe_int(detail_meta.get('correction_approved_event_count'), default=-1)
                != sum(d.approved for d in decisions)):
            raise ValueError('Slice correction counts conflict with history.')

    return SliceMetadata(
        source=prefix_meta.get("source", ""),
        created=prefix_meta.get("created", ""),
        scene=detail_meta.get("scene", ""),
        box_l=_safe_float(detail_meta.get("box_l")),
        box_w=_safe_float(detail_meta.get("box_w")),
        box_h=_safe_float(detail_meta.get("box_h")),
        full_start=_safe_float(detail_meta.get("full_start")),
        full_end=_safe_float(detail_meta.get("full_end")),
        user_start=_safe_float(detail_meta.get("user_start")) or 0.0,
        user_end=_safe_float(detail_meta.get("user_end")) or 0.0,
        padded_start=_safe_float(detail_meta.get("padded_start")) or 0.0,
        padded_end=_safe_float(detail_meta.get("padded_end")) or 0.0,
        pad_rows=_safe_int(detail_meta.get("pad_rows"), default=DEFAULT_SLICE_PADDING_ROWS),
        row_count=_safe_int(detail_meta.get("row_count"), default=0),
        correction_schema_version=detail_meta.get("correction_schema", ""),
        correction_algorithm_version=detail_meta.get("correction_algorithm", ""),
        correction_original_source=detail_meta.get("correction_original_source", ""),
        correction_original_source_sha256=detail_meta.get(
            "correction_original_source_sha256",
            "",
        ),
        correction_reviewed_source=detail_meta.get("correction_reviewed_source", ""),
        correction_event_count=_safe_int(detail_meta.get("correction_event_count"), default=0),
        correction_approved_event_count=_safe_int(
            detail_meta.get("correction_approved_event_count"),
            default=0,
        ),
        correction_events_json=detail_meta.get("correction_events", ""),
        correction_context_json=detail_meta.get("correction_context", ""),
        artifact_metadata_json=detail_meta.get("artifact_metadata", ""),
        scene_review_json=_slice_scene_review(detail_meta),
    )


def update_slice_box_dimensions(filepath: str, box_dims: tuple[float, float, float] | list[float]) -> SliceMetadata:
    if box_dims is None or len(box_dims) != 3:
        raise ValueError("Box dimensions must include L, W, and H.")

    normalized_dims = tuple(float(value) for value in box_dims)
    if any(value <= 0 for value in normalized_dims):
        raise ValueError("Box dimensions must be positive values.")

    with open(filepath, mode="r", encoding="utf-8-sig", newline="") as infile:
        rows = list(csv.reader(infile))

    if not rows:
        raise ValueError(f"Invalid slice file header: {filepath}")

    prefix_meta = _parse_metadata_row(rows[0])
    magic = prefix_meta.get("magic") or (rows[0][0].strip() if rows[0] else "")
    if magic != SLICE_FILE_MAGIC:
        raise ValueError(f"Invalid slice file header: {filepath}")

    while len(rows) < 2:
        rows.append([])

    detail_meta = _parse_metadata_row(rows[1])
    validate_declared_dimensions(detail_meta.get('artifact_metadata'), normalized_dims)
    if detail_meta.get('correction_schema') == '3':
        context = validate_face_context(detail_meta.get('correction_context', ''))
        if tuple(context['box_dims_mm']) != normalized_dims:
            raise ValueError('Review the original source before changing corrected slice dimensions.')
    scene_review_json = _slice_scene_review(detail_meta)
    old_dims = tuple(_safe_float(detail_meta.get(key)) for key in ("box_l", "box_w", "box_h"))
    if scene_review_json and old_dims != normalized_dims:
        review = json.loads(scene_review_json)
        if review.get('trial_record') is not None:
            from .scene_review import previous_review_snapshot
            review['candidate']['previous_review'] = previous_review_snapshot(
                dict(review['candidate'], identity=review['identity']), ['geometry_changed'], review['trial_record'])
            for key in ('record_evidence', 'observed_consistency', 'posture_candidates'):
                review['candidate'].pop(key, None)
            review['candidate']['evidence_status'] = 'geometry_changed'
            review['identity'].pop('record_reference', None)
        review['candidate'].pop('intended_contact', None)
        if 'motion_geometry' in review['candidate']:
            review['candidate']['motion_geometry'] = {'version': 1, 'status': 'geometry_changed'}
        if 'support_cycle' in review['candidate']:
            review['candidate']['support_cycle'] = {'version': 1, 'status': 'geometry_changed'}
        review["identity"].update(confirmed=False, scenario_id=None, scenario_kind=None)
        review["candidate"]["item_candidates"] = []
        review["candidate"]["geometry"] = {}
        if review["detection"].get("registration_sha256"):
            review["detection"]["registration_sha256"] = None
            review["detection"]["registration"] = None
            review["candidate"]["evidence_status"] = "geometry_changed"
            tags = review["candidate"].setdefault("tags", [])
            if "geometry_changed" not in tags:
                tags.append("geometry_changed")
        detail_meta["SceneReviewJson"] = _canonical_scene_review(review)
        artifact = normalize_metadata(detail_meta.get("artifact_metadata"))
        artifact.update(ScenarioId=None, ScenarioKind=None)
        detail_meta["artifact_metadata"] = metadata_json(artifact)
    detail_meta.update(
        {
            "box_l": normalized_dims[0],
            "box_w": normalized_dims[1],
            "box_h": normalized_dims[2],
        }
    )
    rows[1] = _metadata_row_from_mapping(detail_meta, SLICE_META_DETAIL_KEYS)

    _replace_csv_rows(filepath, rows)

    return read_slice_metadata(filepath)


def save_slice_file(
    *,
    filepath: str,
    header_info: dict[str, list[str]],
    raw_data: pd.DataFrame,
    source_path: str,
    full_start: float | None,
    full_end: float | None,
    user_start: float,
    user_end: float,
    box_dims: tuple[float, float, float] | list[float] | None = None,
    pad_rows: int = DEFAULT_SLICE_PADDING_ROWS,
    scene_name: str = "scene",
    marker_correction_metadata: CorrectionSourceMetadata | None = None,
    scene_review_json: str = "",
) -> SliceMetadata:
    scene_review_json = _canonical_scene_review(scene_review_json, start=user_start, end=user_end)
    row_start, row_end, padded_start, padded_end = _slice_time_bounds(raw_data, user_start, user_end, pad_rows)
    if marker_correction_metadata is not None and marker_correction_metadata.schema_version == '3':
        context = validate_face_context(marker_correction_metadata.context_json)
        from .face_assignment import validate_materialized_faces
        validate_materialized_faces(header_info, raw_data, marker_correction_metadata.decisions, context['base_faces'])
        if box_dims is None or tuple(context['box_dims_mm']) != tuple(box_dims):
            raise ValueError('Slice dimensions differ from approved face correction context.')
    slice_raw_df = raw_data.iloc[row_start : row_end + 1].copy()
    if box_dims is not None:
        validate_declared_dimensions(header_info.get('artifact_metadata'), box_dims)
    metadata = _build_slice_metadata(
        source_name=Path(source_path).name if source_path else "",
        scene_name=scene_name,
        box_dims=box_dims,
        full_start=full_start,
        full_end=full_end,
        user_start=user_start,
        user_end=user_end,
        padded_start=padded_start,
        padded_end=padded_end,
        pad_rows=pad_rows,
        row_count=len(slice_raw_df),
        marker_correction_metadata=marker_correction_metadata,
        artifact_metadata_json=metadata_json(header_info.get('artifact_metadata')),
        scene_review_json=scene_review_json,
    )

    header_rows = [
        _metadata_row_from_mapping(
            {
                "magic": SLICE_FILE_MAGIC,
                "version": SLICE_FILE_VERSION,
                "source": metadata.source,
                "created": metadata.created,
            },
            SLICE_META_PREFIX_KEYS,
        ),
        _metadata_row_from_mapping(
            {
                "scene": metadata.scene,
                "box_l": metadata.box_l,
                "box_w": metadata.box_w,
                "box_h": metadata.box_h,
                "full_start": metadata.full_start,
                "full_end": metadata.full_end,
                "user_start": metadata.user_start,
                "user_end": metadata.user_end,
                "padded_start": metadata.padded_start,
                "padded_end": metadata.padded_end,
                "pad_rows": metadata.pad_rows,
                "row_count": metadata.row_count,
                "correction_schema": metadata.correction_schema_version,
                "correction_algorithm": metadata.correction_algorithm_version,
                "correction_original_source": metadata.correction_original_source,
                "correction_original_source_sha256": (
                    metadata.correction_original_source_sha256
                ),
                "correction_reviewed_source": metadata.correction_reviewed_source,
                "correction_event_count": metadata.correction_event_count,
                "correction_approved_event_count": (
                    metadata.correction_approved_event_count
                ),
                "correction_events": metadata.correction_events_json,
                "correction_context": metadata.correction_context_json,
                "artifact_metadata": metadata.artifact_metadata_json,
                "SceneReviewJson": metadata.scene_review_json,
            },
            SLICE_META_DETAIL_KEYS,
        ),
    ]

    header_keys = ("type", "name", "id", "parent", "category", "component")
    from itertools import chain
    _replace_csv_rows(filepath, chain(
        header_rows,
        (header_info.get(key, []) for key in header_keys),
        slice_raw_df.fillna("").values.tolist(),
    ))

    return metadata


def add_timeline_context_columns(df: pd.DataFrame, timeline_context: dict[str, object]) -> pd.DataFrame:
    artifact = normalize_metadata(timeline_context.get('artifact_metadata'))
    # Only the actual pipeline's execution record may label a newly processed
    # result. Raw-file declarations and current defaults are not execution proof.
    artifact['ProcessingSemanticsVersion'], artifact['ProcessingSettingsJson'] = processing_record(df.attrs.get(SETTINGS_ATTR))
    export_df = add_artifact_columns(df, artifact)
    export_df[TimelineMetaCols.FULL_START_SEC] = timeline_context.get("full_start_sec")
    export_df[TimelineMetaCols.FULL_END_SEC] = timeline_context.get("full_end_sec")
    export_df[TimelineMetaCols.SLICE_START_SEC] = timeline_context.get("slice_start_sec")
    export_df[TimelineMetaCols.SLICE_END_SEC] = timeline_context.get("slice_end_sec")
    scene_review_json = _canonical_scene_review(
        timeline_context.get("scene_review_json"),
        start=timeline_context.get("slice_start_sec"),
        end=timeline_context.get("slice_end_sec"),
    )
    if scene_review_json:
        export_df["SceneReview_Json"] = scene_review_json
    correction_schema = str(
        timeline_context.get("marker_correction_schema_version") or ""
    )
    if correction_schema:
        correction_event_count = int(
            timeline_context.get("marker_correction_event_count") or 0
        )
        approved_event_count = int(
            timeline_context.get("marker_correction_approved_event_count") or 0
        )
        export_df[MarkerCorrectionMetaCols.SCHEMA_VERSION] = timeline_context.get(
            "marker_correction_schema_version",
            "",
        )
        export_df[MarkerCorrectionMetaCols.ALGORITHM_VERSION] = timeline_context.get(
            "marker_correction_algorithm_version",
            "",
        )
        export_df[MarkerCorrectionMetaCols.ORIGINAL_SOURCE] = timeline_context.get(
            "marker_correction_original_source",
            "",
        )
        export_df[MarkerCorrectionMetaCols.ORIGINAL_SOURCE_SHA256] = timeline_context.get(
            "marker_correction_original_source_sha256",
            "",
        )
        export_df[MarkerCorrectionMetaCols.REVIEWED_SOURCE] = timeline_context.get(
            "marker_correction_reviewed_source",
            "",
        )
        export_df[MarkerCorrectionMetaCols.EVENT_COUNT] = correction_event_count
        export_df[MarkerCorrectionMetaCols.APPROVED_EVENT_COUNT] = approved_event_count
        export_df[MarkerCorrectionMetaCols.CONTEXT_JSON] = timeline_context.get("marker_correction_context_json", "")
        export_df[MarkerCorrectionMetaCols.EVENTS_JSON] = timeline_context.get(
            "marker_correction_events_json",
            "",
        )
    return export_df


def save_proc_file(filepath: str, processed_df: pd.DataFrame) -> None:
    if 'Artifact_SourceKind' not in processed_df.columns:
        processed_df = add_artifact_columns(processed_df)
    if SETTINGS_ATTR in processed_df.attrs:
        processed_df = processed_df.copy()
        version, settings = processing_record(processed_df.attrs[SETTINGS_ATTR])
        processed_df['Artifact_ProcessingSemanticsVersion'] = version
        processed_df['Artifact_ProcessingSettingsJson'] = settings
    export_df = convert_to_multi_header(processed_df)
    target_path = Path(filepath).resolve()
    temporary_path = None
    try:
        with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', newline='', delete=False,
                                         dir=target_path.parent, prefix='.proc-',
                                         suffix='.tmp') as outfile:
            temporary_path = Path(outfile.name)
            export_df.to_csv(outfile, index=False)
        os.replace(temporary_path, target_path)
    finally:
        if temporary_path is not None and temporary_path.exists():
            temporary_path.unlink()


def validate_face_context(value):
    import numpy as np
    try:
        context = json.loads(value)
        dims = np.asarray(context["box_dims_mm"], dtype=float)
        if dims.shape != (3,) or not np.isfinite(dims).all() or (dims <= 0).any():
            raise ValueError("Invalid dimensions")
        if context["coordinate_policy"] != "global-y-up-box-xyz-mm":
            raise ValueError("Unsupported coordinate policy")
        if not isinstance(context["base_faces"], dict) or not context["base_faces"]:
            raise ValueError("Missing original analysis faces")
    except (ValueError, TypeError, KeyError) as exc:
        raise ValueError("Invalid face correction context.") from exc
    return context
