import csv
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from src.config.data_columns import TimeCols, TimelineMetaCols
from src.utils.header_converter import convert_to_multi_header


SLICE_FILE_EXTENSION = ".slice"
PROC_FILE_EXTENSION = ".proc"
SLICE_FILE_MAGIC = "BoxMotionAnalyzer Slice File"
SLICE_FILE_VERSION = "1"
DEFAULT_SLICE_PADDING_ROWS = 50

SLICE_META_PREFIX_KEYS = ("magic", "version", "source", "created")
SLICE_META_DETAIL_KEYS = (
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
        return f"{value:.6f}"
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
) -> SliceMetadata:
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
    )


def build_slice_default_name(source_path: str, scene_name: str | None = None) -> str:
    source_stem = Path(source_path).stem if source_path else "scene"
    normalized_scene = (scene_name or "slice").strip().replace(" ", "_")
    return f"{source_stem}_{normalized_scene}{SLICE_FILE_EXTENSION}"


def build_proc_default_name(slice_path: str, processing_mode: str) -> str:
    source_stem = Path(slice_path).stem if slice_path else "processed"
    normalized_mode = (processing_mode or "proc").strip().replace(" ", "_")
    return f"{source_stem}_{normalized_mode}{PROC_FILE_EXTENSION}"


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
    )


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
) -> SliceMetadata:
    row_start, row_end, padded_start, padded_end = _slice_time_bounds(raw_data, user_start, user_end, pad_rows)
    slice_raw_df = raw_data.iloc[row_start : row_end + 1].copy()
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
            },
            SLICE_META_DETAIL_KEYS,
        ),
    ]

    header_keys = ("type", "name", "id", "parent", "category", "component")
    with open(filepath, mode="w", encoding="utf-8", newline="") as outfile:
        writer = csv.writer(outfile)
        for row in header_rows:
            writer.writerow(row)
        for key in header_keys:
            writer.writerow(header_info.get(key, []))
        writer.writerows(slice_raw_df.fillna("").values.tolist())

    return metadata


def add_timeline_context_columns(df: pd.DataFrame, timeline_context: dict[str, float | None]) -> pd.DataFrame:
    export_df = df.copy()
    export_df[TimelineMetaCols.FULL_START_SEC] = timeline_context.get("full_start_sec")
    export_df[TimelineMetaCols.FULL_END_SEC] = timeline_context.get("full_end_sec")
    export_df[TimelineMetaCols.SLICE_START_SEC] = timeline_context.get("slice_start_sec")
    export_df[TimelineMetaCols.SLICE_END_SEC] = timeline_context.get("slice_end_sec")
    return export_df


def save_proc_file(filepath: str, processed_df: pd.DataFrame) -> None:
    export_df = convert_to_multi_header(processed_df)
    export_df.to_csv(filepath, index=False)
