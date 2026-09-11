"""Public artifact identity only. Never read simulation truth or event manifests."""
import json
import math
import re
from dataclasses import dataclass

import pandas as pd
from src.utils.processing_settings import validate_processing_record

FIELDS = (
    'SchemaVersion', 'SourceKind', 'ModelId', 'BoxLengthMm', 'BoxWidthMm',
    'BoxHeightMm', 'IstaType', 'ScenarioId', 'ScenarioKind', 'MarkerLayoutId',
    'MarkerLayoutHash', 'ProcessingSemanticsVersion', 'CoordinatePolicy',
    'UnitsPolicy', 'GeneratorVersion', 'ProcessingSettingsJson',
)
DIMENSIONS = ('BoxLengthMm', 'BoxWidthMm', 'BoxHeightMm')
SOURCE_KINDS = {'real', 'public_external', 'mujoco_synthetic', 'handcrafted_dummy', 'unknown_legacy'}
SCHEMA_VERSION = '1'
RAW_KEY = 'Artifact Metadata'
FLAT_PREFIX = 'Artifact_'


def validate_declared_dimensions(metadata, dimensions):
    declared = normalize_metadata(metadata)
    for field, dimension in zip(DIMENSIONS, dimensions):
        if not math.isfinite(float(dimension)) or float(dimension) <= 0:
            raise ValueError('Box dimensions must be finite positive values.')
        if declared[field] is not None and declared[field] != float(dimension):
            raise ValueError(f'Box dimensions conflict with declared artifact {field}.')


def normalize_metadata(value=None, *, new=False):
    """Preserve known fields, including invalid declarations for exclusion reports."""
    if value is None or value == '':
        value = {}
    if isinstance(value, str):
        value = json.loads(value)
    if not isinstance(value, dict):
        raise ValueError('Artifact metadata must be a JSON object.')
    result = {}
    for field in FIELDS:
        item = value.get(field)
        if item is None or (not isinstance(item, (dict, list)) and pd.isna(item)) or item == '':
            item = None
        elif isinstance(item, (dict, list, bool)):
            raise ValueError(f'Artifact {field} must be a scalar value.')
        elif field in DIMENSIONS:
            try:
                item = float(item)
            except (TypeError, ValueError):
                raise ValueError(f'Artifact {field} must be numeric.')
        else:
            item = str(item).strip()
        result[field] = item
    if new and not result['SchemaVersion']:
        result['SchemaVersion'] = SCHEMA_VERSION
    if not result['SourceKind']:
        result['SourceKind'] = 'unknown_legacy'
    return result


def metadata_json(value=None):
    return json.dumps(normalize_metadata(value, new=True), sort_keys=True, separators=(',', ':'), allow_nan=False)


def metadata_from_source_rows(rows):
    declarations = []
    for row in rows:
        for i, cell in enumerate(row):
            if cell == RAW_KEY and i + 1 < len(row):
                declarations.append(row[i + 1])
            elif cell.startswith('artifact_metadata='):
                declarations.append(cell.split('=', 1)[1])
    values = [normalize_metadata(value) for value in declarations]
    if values and any(value != values[0] for value in values[1:]):
        raise ValueError('Conflicting artifact metadata declarations.')
    return values[0] if values else normalize_metadata()


def add_artifact_columns(df, value=None):
    result = df.copy()
    metadata = normalize_metadata(value, new=True)
    for field in FIELDS:
        result[FLAT_PREFIX + field] = metadata[field]
    return result


@dataclass(frozen=True)
class ArtifactIdentity:
    values: dict
    errors: tuple[str, ...] = ()

    @property
    def source_kind(self):
        return self.values.get('SourceKind') or 'unknown_legacy'

    def exclusion_reasons(self):
        reasons = list(self.errors)
        for field in FIELDS:
            value = self.values.get(field)
            if field == 'GeneratorVersion' and self.source_kind not in {'mujoco_synthetic', 'handcrafted_dummy'}:
                continue
            if value is None or value == '':
                reasons.append(f'{field}: missing')
        if self.values.get('SchemaVersion') != SCHEMA_VERSION:
            reasons.append('SchemaVersion: unsupported')
        if self.source_kind not in SOURCE_KINDS:
            reasons.append('SourceKind: invalid')
        if self.source_kind == 'unknown_legacy':
            reasons.append('SourceKind: unknown; individual review only')
        for field in DIMENSIONS:
            value = self.values.get(field)
            if value is not None and (not isinstance(value, (float, int)) or not math.isfinite(value) or value <= 0):
                reasons.append(f'{field}: must be finite and positive')
        layout_hash = self.values.get('MarkerLayoutHash')
        if layout_hash and not re.fullmatch(r'[0-9a-f]{64}', str(layout_hash)):
            reasons.append('MarkerLayoutHash: expected a lowercase SHA-256 digest')
        processing_error = validate_processing_record(self.values.get('ProcessingSemanticsVersion'), self.values.get('ProcessingSettingsJson'))
        if processing_error:
            reasons.append(processing_error)
        return list(dict.fromkeys(reasons))


def read_identity(df):
    values, errors = {}, []
    for field in FIELDS:
        col = ('Info', 'Artifact', field)
        positions = [i for i, column in enumerate(df.columns) if column == col]
        if not positions:
            continue
        if len(positions) != 1:
            errors.append(f'{field}: duplicate column')
            continue
        series = df.iloc[:, positions[0]]
        # Missing rows are not silently filled from the first nonmissing row.
        if series.nunique(dropna=False) != 1:
            errors.append(f'{field}: not constant across rows')
            continue
        values[field] = series.iloc[0] if len(series) else None
    try:
        values = normalize_metadata(values)
    except ValueError as error:
        errors.append(str(error))
    return ArtifactIdentity(values, tuple(errors))


def compatibility_reasons(baseline, candidate):
    reasons = [f'baseline {reason}' for reason in baseline.exclusion_reasons()]
    reasons += [f'file {reason}' for reason in candidate.exclusion_reasons()]
    for field in FIELDS:
        # Generator builds may differ if the explicit processing/units/schema contracts match.
        if field == 'GeneratorVersion':
            continue
        if baseline.values.get(field) != candidate.values.get(field):
            if field == 'ProcessingSettingsJson':
                reasons.append('ProcessingSettingsJson: executed settings differ (see declared metadata)')
            else:
                reasons.append(f'{field}: mismatch ({baseline.values.get(field)!r} / {candidate.values.get(field)!r})')
    return reasons
