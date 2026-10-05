"""Draft/preview/apply state and atomic local profile documents. No trial approval."""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
import json
import os
import re
from pathlib import Path
import tempfile

from src.simulation.marker_fixtures import validate_profile
from src.utils.marker_profile_identity import (canonical, envelope, validate_envelope,
    interpretation_policy, profile_identity, validate_identity, layout_support, compatibility)


def profile_changes(before, after):
    changes = []
    for key in sorted(set(before) | set(after)):
        if key != 'markers' and before.get(key) != after.get(key):
            changes.append(dict(field=key, before=before.get(key), after=after.get(key)))
    old, new = before.get('markers', []), after.get('markers', [])
    if len(old) != len(new):
        changes.append(dict(field='markers', before=old, after=new))
    else:
        for row, (a, b) in enumerate(zip(old, new)):
            for field in sorted(set(a) | set(b)):
                if a.get(field) != b.get(field):
                    changes.append(dict(row=row, field=field, before=a.get(field), after=b.get(field)))
    return deepcopy(changes)


def _hash_or_none(profile):
    try:
        return validate_profile(profile)
    except (ValueError, TypeError, KeyError, AttributeError, IndexError):
        return None


class ProfileEditorState:
    def __init__(self, source, *, applied=None, copy_source=True):
        validate_profile(source)
        self.source = deepcopy(source)
        self.source_identity = profile_identity(source)
        self.draft = deepcopy(source)
        if copy_source:
            self.draft['profile_id'] = 'custom-'+source['profile_id']
        self.applied = deepcopy(source if applied is None else applied)
        self.applied_identity = profile_identity(self.applied)
        self.preview = deepcopy(self.draft)
        self.revision = 0; self.preview_revision = 0; self.history = []

    def _event(self, operation, before, after, changes=None):
        self.history.append(envelope('MarkerProfileEditEvent', sequence=len(self.history)+1,
            utc=datetime.now(timezone.utc).isoformat(), operation=operation,
            source_hash=self.source_identity['profile_hash'], revision=self.revision,
            before_hash=_hash_or_none(before), after_hash=_hash_or_none(after),
            changes=deepcopy(changes or [])))

    def edit(self, profile):
        if profile == self.draft:
            return
        before = self.draft; self.draft = deepcopy(profile); self.revision += 1
        self._event('edit', before, self.draft, profile_changes(before, self.draft))

    def validate_draft(self):
        validate_identity(self.source_identity)  # Never silently adopt changed fixed-code meanings.
        return profile_identity(self.draft)

    @property
    def preview_fresh(self):
        return self.preview_revision == self.revision and self.preview == self.draft

    def refresh_preview(self):
        self.validate_draft()
        before = self.preview; self.preview = deepcopy(self.draft); self.preview_revision = self.revision
        self._event('preview', before, self.preview)

    def apply(self):
        identity = self.validate_draft()
        if not self.preview_fresh:
            raise ValueError('Preview the current edits before Apply.')
        support = layout_support(self.preview)
        if support['status'] != 'supported':
            raise ValueError(support['reason'])
        before = self.applied; self.applied = deepcopy(self.preview); self.applied_identity = identity
        self._event('apply', before, self.applied, profile_changes(before, self.applied))
        return deepcopy(self.applied)

    def reset_to_source(self):
        before = self.draft; custom_id = self.draft['profile_id']
        self.draft = deepcopy(self.source); self.draft['profile_id'] = custom_id
        self.revision += 1
        self._event('reset', before, self.draft, profile_changes(before, self.draft))
        # Reset changes the draft only; Preview/Apply remain explicit operations.

    def previous_result_compatibility(self, previous):
        return compatibility(previous, profile_identity(self.preview))

    def document(self):
        self.validate_draft(); validate_profile(self.preview); validate_identity(self.applied_identity)
        return deepcopy(envelope('MarkerProfileDocument', source=self.source, source_identity=self.source_identity,
            draft=self.draft, preview=self.preview, applied=self.applied, applied_identity=self.applied_identity,
            draft_identity=profile_identity(self.draft), preview_identity=profile_identity(self.preview),
            revision=self.revision, preview_revision=self.preview_revision, history=self.history,
            units='mm', coordinate_policy=self.source_identity['policy']['coordinate_policy'],
            time_semantics='static-profile; edit UTC is wall-clock history', approval_status='not_evaluated'))

    @classmethod
    def from_document(cls, value):
        validate_envelope(value, 'MarkerProfileDocument')
        if (value.get('units') != 'mm' or value.get('time_semantics') != 'static-profile; edit UTC is wall-clock history'
                or value.get('approval_status') != 'not_evaluated'
                or value.get('coordinate_policy') != interpretation_policy()['coordinate_policy']):
            raise ValueError('Unsupported profile document units/frame/time/approval.')
        for key in ('source', 'draft', 'preview', 'applied'):
            if not isinstance(value.get(key), dict):
                raise ValueError('Missing profile document '+key)
            identity = value.get(key+'_identity')
            validate_identity(identity)
            if canonical(identity['source_profile']) != canonical(value[key]):
                raise ValueError('Stale profile document '+key)
        revision, preview_revision = value.get('revision'), value.get('preview_revision')
        if type(revision) is not int or type(preview_revision) is not int or not 0 <= preview_revision <= revision:
            raise ValueError('Invalid draft/preview revision.')
        if preview_revision == revision and value['draft'] != value['preview']:
            raise ValueError('Stale preview declared current.')
        history = value.get('history')
        if not isinstance(history, list):
            raise ValueError('Missing profile edit history.')
        for index, event in enumerate(history, 1):
            validate_envelope(event, 'MarkerProfileEditEvent')
            if (type(event.get('sequence')) is not int or event['sequence'] != index or event.get('operation') not in ('edit', 'preview', 'apply', 'reset')
                    or event.get('source_hash') != value['source_identity']['profile_hash']
                    or type(event.get('revision')) is not int or not 0 <= event['revision'] <= revision
                    or not isinstance(event.get('changes'), list)):
                raise ValueError('Invalid profile edit history.')
            for field in ('before_hash', 'after_hash'):
                if field not in event or (event[field] is not None and not re.fullmatch(r'[0-9a-f]{64}', str(event[field]))):
                    raise ValueError('Missing or invalid edit history identity.')
            try:
                stamp = datetime.fromisoformat(event['utc'])
            except (KeyError, TypeError, ValueError) as error:
                raise ValueError('Invalid edit history UTC timestamp.') from error
            if stamp.tzinfo is None or stamp.utcoffset().total_seconds() != 0:
                raise ValueError('Edit history requires UTC wall-clock time.')
        state = cls(value['source'], applied=value['applied'], copy_source=False)
        for key in ('draft', 'preview', 'history', 'revision', 'preview_revision', 'source_identity', 'applied_identity'):
            setattr(state, key, deepcopy(value[key]))
        return state


def read_document(path):
    value = json.loads(Path(path).read_text(encoding='utf-8-sig'),
                       parse_constant=lambda token: (_ for _ in ()).throw(ValueError(token)))
    return ProfileEditorState.from_document(value)


def save_document(path, state):
    """Failure keeps prior file bytes and all current editing decisions intact."""
    payload = canonical(state.document())+'\n'; target = Path(path); temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', newline='', dir=target.parent,
                                          prefix='.bma-profile-', suffix='.tmp', delete=False) as stream:
            temporary = Path(stream.name); stream.write(payload); stream.flush(); os.fsync(stream.fileno())
        os.replace(temporary, target)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
