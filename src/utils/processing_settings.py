"""Identity of executed processing policy, independent of per-trial results."""
import hashlib
import json
import math
from decimal import Decimal, localcontext

PROCESSING_VERSION = 'analysis-face-v3-time-v2'
SETTINGS_ATTR = 'executed_processing_settings'
REQUIRED_STAGES = {'single_pass', 'result_resampling', 'postprocess'}


def normalized_range_offset(endpoint, origin):
    """Shortest decimal offset within the binary input rounding uncertainty.

    This only canonicalizes provenance; selection/interpolation uses raw times.
    Resolution is limited by the input clocks, not a fixed decimal-place grid.
    """
    endpoint, origin = float(endpoint), float(origin)
    if not math.isfinite(endpoint) or not math.isfinite(origin):
        raise ValueError('Resampling range times must be finite')
    with localcontext() as context:
        context.prec = 1100  # Exact binary64 subtraction, including subnormals.
        offset = Decimal.from_float(endpoint) - Decimal.from_float(origin)
        if not offset:
            return 0.0
        uncertainty = (Decimal.from_float(math.ulp(endpoint))
                       + Decimal.from_float(math.ulp(origin))) / 2
        # Prefer the fewest significant decimal digits consistent with both
        # inputs rounded to binary64. Never round outside that uncertainty.
        for digits in range(1, 18):
            quantum = Decimal(1).scaleb(offset.adjusted() - digits + 1)
            candidate = offset.quantize(quantum)
            if abs(candidate - offset) <= uncertainty:
                return float(candidate)
        return float(offset)


def canonical_settings(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=True, allow_nan=False)


def processing_record(value):
    if not isinstance(value, dict) or not REQUIRED_STAGES.issubset(value):
        return None, None
    if any(not isinstance(value[stage], dict) or not value[stage] for stage in REQUIRED_STAGES):
        return None, None
    text = canonical_settings(value)
    digest = hashlib.sha256(text.encode('utf-8')).hexdigest()
    return f'{PROCESSING_VERSION}:sha256:{digest}', text


def validate_processing_record(version, text):
    if not version or not text:
        return 'ProcessingSettingsJson: executed processing record missing'
    try:
        value = json.loads(text)
        expected, canonical = processing_record(value)
    except (TypeError, ValueError):
        return 'ProcessingSettingsJson: invalid JSON/settings'
    if expected is None or version != expected:
        return 'ProcessingSemanticsVersion: settings hash/version mismatch or incomplete execution record'
    if text != canonical:
        return 'ProcessingSettingsJson: noncanonical encoding'
    return ''
