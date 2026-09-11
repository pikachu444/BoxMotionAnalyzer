"""Save operator work; rebuild motion evidence from the referenced observations."""
from copy import deepcopy
from dataclasses import asdict
import hashlib
import json
import math
import os
from pathlib import Path
import re
import tempfile

from .scene_detection import VERSION, DetectionSettings, Registration
from .scene_review import REFERENCE_EDITION, SceneReviewSession


KIND = 'boxmotion-scene-review'
OPERATOR_KEYS = {'id', 'origin', 'start', 'end', 'auto_start', 'auto_end',
                 'decision', 'identity', 'previous_review'}
DECISIONS = {'unreviewed', 'include', 'exclude'}
_USE_RESULT_REGISTRATION = object()


def _json(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False)


def _digest(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(chunk)
    return digest.hexdigest()


def _finite(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def _identity(value):
    if (not isinstance(value, dict) or value.get('ista_type') not in ('Unknown', 'G', 'H')
            or not isinstance(value.get('confirmed'), bool)):
        raise ValueError('Invalid saved scene identity.')
    for key in ('scenario_id', 'scenario_kind', 'reference_edition', 'applied_edition'):
        if key not in value or (value[key] is not None and not isinstance(value[key], str)):
            raise ValueError('Invalid saved scene identity.')


def _validate(data):
    """Structural checks only. Cached motion values are checked by recomputation."""
    try:
        if data['kind'] != KIND or type(data['version']) is not int or data['version'] != 1:
            raise ValueError('Unsupported scene workspace.')
        source = data['source']
        if not isinstance(source['path'], str) or not source['path'] or '\x00' in source['path']:
            raise ValueError('Workspace needs its observed source path.')
        if not isinstance(source['sha256'], str) or not re.fullmatch('[0-9a-f]{64}', source['sha256']):
            raise ValueError('Workspace needs the observed source SHA-256.')
        dims = data['box_dims_mm']
        if not isinstance(dims, list) or len(dims) != 3 or any(not _finite(v) or v <= 0 for v in dims):
            raise ValueError('Workspace needs three finite positive box dimensions.')
        settings = DetectionSettings(**data['settings'])
        if set(data['settings']) != set(asdict(settings)):
            raise ValueError('Workspace detection settings are incomplete.')
        for key, value in asdict(settings).items():
            if key == 'minimum_points':
                if type(value) is not int or value < 5:
                    raise ValueError('Detection requires at least five points per fit.')
            elif not _finite(value) or value <= 0:
                raise ValueError('Detection settings must be finite positive values.')
        if data['registration'] is not None:
            registration = Registration(**data['registration'])
            registration.validate()
            if list(registration.profile['box_dims_mm']) != dims:
                raise ValueError('Workspace dimensions differ from marker registration.')
        if not isinstance(data['detection_version'], str) or not data['detection_version']:
            raise ValueError('Workspace needs its detection version.')
        context = data['context']
        if (context['ista_type'] not in ('Unknown', 'G', 'H')
                or (context['applied_edition'] is not None and not isinstance(context['applied_edition'], str))):
            raise ValueError('Invalid workspace test context.')
        rows = data['rows']
        if not isinstance(rows, list):
            raise ValueError('Workspace rows must be a list.')
        ids = []
        for row in rows:
            if (row['origin'] not in ('automatic', 'manual') or row['decision'] not in DECISIONS
                    or row['evidence_mode'] not in ('automatic', 'range')):
                raise ValueError('Invalid saved scene review state.')
            id_pattern = r'scene_[0-9]{3,}' if row['origin'] == 'automatic' else r'manual_[0-9]{3,}'
            if not isinstance(row['id'], str) or not re.fullmatch(id_pattern, row['id']):
                raise ValueError('Workspace scene IDs must match their automatic or manual origin.')
            ids.append(row['id'])
            for first, last in (('start', 'end'), ('auto_start', 'auto_end')):
                if first == 'auto_start' and row[first] is None and row[last] is None:
                    continue
                if not _finite(row[first]) or not _finite(row[last]) or row[first] > row[last]:
                    raise ValueError('Invalid saved scene range.')
            _identity(row['identity'])
            previous = row.get('previous_review')
            if previous is not None:
                if previous['decision'] not in DECISIONS or not isinstance(previous['reasons'], list):
                    raise ValueError('Invalid previous scene review.')
                if any(not isinstance(reason, str) for reason in previous['reasons']):
                    raise ValueError('Invalid previous scene review reasons.')
                _identity(previous['identity'])
        deleted = data['deleted_ids']
        if not isinstance(deleted, list) or any(not isinstance(item, str)
                or not re.fullmatch(r'(scene|manual)_[0-9]{3,}', item) for item in deleted):
            raise ValueError('Invalid removed scene IDs.')
        if len(set(ids)) != len(ids) or len(set(deleted)) != len(deleted) or set(ids) & set(deleted):
            raise ValueError('Workspace scene IDs must be distinct, including removed scenes.')
        serial = data['manual_serial']
        if type(serial) is not int or serial < 0:
            raise ValueError('Invalid manual scene counter.')
        counters = [int(item[7:]) for item in ids + deleted if re.fullmatch(r'manual_\d+', item)]
        if counters and serial < max(counters):
            raise ValueError('Manual scene counter would reuse a saved ID.')
        view = data['view']
        if view['selected_id'] is not None and view['selected_id'] not in ids:
            raise ValueError('Selected scene is absent from the workspace.')
        if view['signal'] is not None and not isinstance(view['signal'], str):
            raise ValueError('Invalid saved plot signal.')
        targets = view.setdefault('targets', [])
        if not isinstance(targets, list) or any(not isinstance(target, str) for target in targets):
            raise ValueError('Saved plot targets must be a list of names.')
        # Reject NaN in any cached field, without trusting that field as evidence.
        _json(data)
    except (KeyError, TypeError, AttributeError, OverflowError) as error:
        raise ValueError('Incomplete or invalid scene workspace.') from error
    return data


def save_workspace(path, session, source_path, box_dims, *, selected_id=None, signal=None,
                   registration=_USE_RESULT_REGISTRATION, targets=None):
    """Keep pending geometry even when the session still has old computed evidence."""
    target, source = Path(path).resolve(), Path(source_path).resolve()
    if (target.suffix.lower() == '.csv' or target == source
            or (target.is_file() and source.is_file() and target.samefile(source))):
        raise ValueError('Save the workspace separately from the observed source.')
    actual_hash = _digest(source)
    if actual_hash != session.source_sha256:
        raise ValueError('Observed source changed. Reload it before saving the workspace.')
    try:
        source_reference = os.path.relpath(source, target.parent)
    except ValueError:  # Different Windows drives cannot have a relative path.
        source_reference = str(source)
    result = session.result
    if registration is _USE_RESULT_REGISTRATION:
        registration = result.registration
    data = _validate({
        'kind': KIND, 'version': 1,
        'source': {'path': source_reference, 'sha256': actual_hash},
        'box_dims_mm': list(box_dims),
        'registration': asdict(registration) if registration is not None else None,
        'settings': asdict(result.settings), 'detection_version': VERSION,
        'context': {'ista_type': session.ista_type, 'applied_edition': session.applied_edition},
        'rows': deepcopy(session.rows), 'deleted_ids': sorted(session.deleted_ids),
        'manual_serial': session.manual_serial,
        'view': {'selected_id': selected_id if selected_id in {r['id'] for r in session.rows} else None,
                 'signal': signal, 'targets': [] if targets is None else deepcopy(targets)},
    })
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', newline='\n',
                                        dir=target.parent, prefix='.bma-review-', suffix='.tmp', delete=False) as stream:
            temporary = Path(stream.name)
            stream.write(_json(data) + '\n')
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, target)
    except BaseException as error:
        if temporary is not None:
            try:
                temporary.unlink(missing_ok=True)
            except OSError as cleanup_error:
                error.add_note(f'Could not remove temporary workspace {temporary}: {cleanup_error}')
        raise
    return data


def read_workspace(path):
    return _validate(json.loads(Path(path).read_text(encoding='utf-8-sig')))


def workspace_source_path(path, data):
    source = Path(data['source']['path'])
    return (source if source.is_absolute() else Path(path).resolve().parent / source).resolve()


def restore_session(data, result, source_sha256):
    data = _validate(deepcopy(data))
    if source_sha256 != data['source']['sha256']:
        raise ValueError('Observed source differs from the saved workspace.')
    session = SceneReviewSession(result, source_sha256)
    session.set_context(**data['context'])
    context_reasons = []
    if data['detection_version'] != VERSION:
        context_reasons.append('detection_version_changed')
    if _json(data['settings']) != _json(asdict(result.settings)):
        context_reasons.append('detection_settings_changed')
    registration = asdict(result.registration) if result.registration else None
    if _json(data['registration']) != _json(registration):
        context_reasons.append('registration_changed')
    start, end = float(result.signals.index[0]), float(result.signals.index[-1])
    restored, changed_ids = [], set()
    for saved in data['rows']:
        if not start <= saved['start'] <= saved['end'] <= end:
            raise ValueError(f"Saved scene {saved['id']} is outside the observed capture.")
        fresh = session.recompute_saved_row(saved)
        reasons = list(context_reasons)
        computed_keys = (set(saved) | set(fresh)) - OPERATOR_KEYS
        changed_fields = sorted(key for key in computed_keys
                                if key not in saved or key not in fresh or _json(saved[key]) != _json(fresh[key]))
        if changed_fields:
            reasons.append('recomputed_evidence_changed: ' + ', '.join(changed_fields))
        identity = saved['identity']
        if (identity['ista_type'] != session.ista_type
                or identity['applied_edition'] != session.applied_edition):
            reasons.append('test_context_changed')
        if identity['reference_edition'] != REFERENCE_EDITION:
            reasons.append('reference_edition_changed')
        if identity['confirmed'] and not (
            saved['decision'] == 'include' and fresh['evidence_status'] == 'current'
            and identity['scenario_id'] in fresh['item_candidates']
            and identity['scenario_kind'] == 'free_fall'
            and identity['ista_type'] == session.ista_type != 'Unknown'
            and identity['applied_edition'] == session.applied_edition == REFERENCE_EDITION
            and identity['reference_edition'] == REFERENCE_EDITION
        ):
            reasons.append('confirmed_item_no_longer_supported')
        if reasons:
            changed_ids.add(saved['id'])
            previous = deepcopy(saved.get('previous_review')) if saved['decision'] == 'unreviewed' else None
            if previous is None:
                previous = {'decision': saved['decision'], 'identity': deepcopy(identity), 'reasons': []}
            previous['reasons'] = list(dict.fromkeys(previous['reasons'] + reasons))
            fresh['decision'] = 'unreviewed'
            fresh['previous_review'] = previous
        else:
            fresh['identity'] = deepcopy(identity)
            if 'previous_review' in saved:
                fresh['previous_review'] = deepcopy(saved['previous_review'])
        restored.append(fresh)
    session.rows = restored
    session.deleted_ids = set(data['deleted_ids'])
    session.manual_serial = data['manual_serial']
    return session, changed_ids
