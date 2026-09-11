"""Identity of executed processing policy, independent of per-trial results."""
import hashlib
import json

PROCESSING_VERSION = 'analysis-face-v3-time-v2'
SETTINGS_ATTR = 'executed_processing_settings'
REQUIRED_STAGES = {'single_pass', 'result_resampling', 'postprocess'}


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
