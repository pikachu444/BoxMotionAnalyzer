"""Execution evidence, distinct from numerical approval and measured accuracy."""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone, timedelta
import importlib.metadata
import os
from pathlib import Path
import platform
import subprocess
import sys
import xml.etree.ElementTree as ET

from .contracts import (envelope, digest, file_digest, write_new_json, read_json, validate_envelope, anchor, boundary,
                        validate_fixture, validate_reference, SEMANTIC_VERSION)

CAPTURE_CASES = ('two_drops', 'supported_H', 'handling_only', 'tracking_OFF', 'partial', 'two_flips')
CAPTURE_SCENES = ('two_drops-scene-0', 'two_drops-scene-1', 'supported_H-scene-0',
                  'tracking_OFF-scene-0', 'partial-scene-0', 'two_flips-scene-0')
REQUIRED_METRICS = {'t1','t2','reference_face','contact_state','equivalent_height','observed_first_contact',
    'vertical_velocity','horizontal_speed','angular_speed','final_face','first_contact','final_rotation_deg',
    'maximum_rotation_deg','BetaAtT1MinusDeg','ThetaLongAtT1MinusDeg','ThetaShortAtT1MinusDeg',
    'DeltaHAtT1Minus_mm','MaxBetaDeg','MaxAbsThetaLongDeg','MaxAbsThetaShortDeg','MaxDeltaH_mm'}


def source_state():
    paths = sorted(Path('src').rglob('*.py'))
    paths += sorted(Path('src').rglob('*.json'))
    paths += [Path('requirements.txt')]
    hashes = {p.as_posix(): file_digest(p) for p in paths}
    return dict(commit=subprocess.check_output(['git', 'rev-parse', 'HEAD'], text=True).strip(),
                dirty=bool(subprocess.check_output(['git', 'status', '--porcelain', '--untracked-files=no'], text=True)),
                content_sha256=digest(hashes), source_sha256=hashes, semantics=SEMANTIC_VERSION)


def environment():
    return dict(python=sys.version, executable=sys.executable, platform=platform.platform(),
                machine=platform.machine(), dependencies={n: importlib.metadata.version(n)
                for n in ('numpy', 'scipy', 'pandas', 'PySide6', 'mujoco', 'pytest')},
                numerical_environment={k: os.environ.get(k, 'unset') for k in
                ('OMP_NUM_THREADS', 'OPENBLAS_NUM_THREADS', 'MKL_NUM_THREADS')})


def new_report(tier, command):
    stamp = datetime.now(timezone.utc)
    import uuid
    return envelope('RunReport', run_id=str(uuid.uuid4()), utc=stamp.isoformat(),
        kst=stamp.astimezone(timezone(timedelta(hours=9))).isoformat(), tier=tier,
        command=command, code=source_state(), environment=environment(),
        ci_context={k:os.environ.get(k,'unavailable') for k in ('GITHUB_RUN_ID','GITHUB_RUN_ATTEMPT','GITHUB_JOB','GITHUB_SHA')},
        status='fail', exit_code=1, independent_review=dict(status='pending', reason='Separate read-only review'),
        experimental=dict(status='pending', reason='No verified measured dataset and independent labels; #104'),
        gui=dict(widget='not_executed', render_buffer='not_executed', native_window='not_executed',
                 native_input='not_executed', human_review='pending', reason='CLI is not native GUI evidence'))


def cache_identity(fixture, corpus, code, runtime):
    # Locations and interpreter installation paths are not source identity.
    value = deepcopy(fixture)
    value.pop('relative_path')
    value['reference'].pop('relative_path')
    env = {k: v for k, v in runtime.items() if k != 'executable'}
    return dict(version='pub11-replay-identity-v1', fixture=digest(value),
                approval=digest(corpus['approval']), approved_scenes=digest(corpus['approved_scene_ids']),
                required_cases=digest([c['case_id'] for c in corpus['cases']]),
                baseline=value['reference']['sha256'], tolerance=digest(value['tolerance']),
                code=code['content_sha256'], semantics=code['semantics'], environment=digest(env))


def capture_protocol(manifest, root, tier, select, code, runtime, loads=None):
    """Explicit adapter for PUB02 v2. Unsupported inventories need a reviewed protocol."""
    from .runner import approval_check, validate_tolerance, ReferenceMissing
    if manifest['version'] != 'public-analytic-corpus-v2':
        raise ValueError('No approved required-case adapter for corpus version.')
    if sorted(c['case_id'] for c in manifest['cases']) != sorted(CAPTURE_CASES):
        raise ValueError('Required capture case population differs, including excluded-only files.')
    if sorted(manifest['approved_scene_ids']) != sorted(CAPTURE_SCENES):
        raise ValueError('Required approved scene population differs.')
    approval_check(manifest['approval'], 'Corpus')
    specs = []
    for entry in manifest['cases']:
        path = Path(entry['fixture'])
        if path.is_absolute() or '..' in path.parts:
            raise ValueError('Fixture path must remain inside explicit asset root.')
        fixture = read_json(Path(root) / path, 'CaptureReviewFixture')
        validate_fixture(fixture)
        if fixture['case_id'] != entry['case_id']:
            raise ValueError('Manifest/fixture case identity mismatch.')
        approval_check(fixture['approval'], 'Replay')
        validate_tolerance(fixture['tolerance'])
        source = Path(root) / fixture['relative_path']
        if file_digest(source) != fixture['raw_sha256']:
            raise ValueError('Required Raw source changed.')
        from src.analysis.pipeline.data_loader import DataLoader
        header, raw = DataLoader().load_csv(str(source))
        if loads is not None:
            loads.append(dict(case_id=entry['case_id'],raw_sha256=fixture['raw_sha256'],rows=len(raw),scope='source_contract_preflight'))
        if digest(fixture['capture_end_raw_time_s']) != digest(boundary(raw.iloc[:,1].to_numpy(dtype=float),len(raw))):
            raise ValueError('Capture EOF boundary must retain the original unavailable timestamp/basis.')
        for d in fixture['scene_decisions']:
            for key in ('anchor','detected_anchor'):
                if key in d:
                    saved=d[key]
                    if digest(anchor(raw,saved['start_record'],saved['end_record_exclusive']))!=digest(saved):
                        raise ValueError('Source-bound include/exclude anchor or raw timestamp differs.')
        for f in fixture['flip_decisions']:
            i=f['original_record_index']
            if (digest(anchor(raw,i,i+1))!=digest(f['anchor']) or type(f['raw_time_s']) not in (int,float)
                    or f['raw_time_s']!=float(raw.iloc[i,1])):
                raise ValueError('Source-bound flip anchor/raw time differs.')
        declaration=header['artifact_metadata']
        if (declaration.get('MarkerLayoutHash')!=fixture['marker_profile_hash'] or
                declaration.get('MarkerLayoutId')!=fixture['marker_profile_id'] or
                declaration.get('SchemaVersion')!='1' or declaration.get('SourceKind')!='handcrafted_dummy' or
                declaration.get('CoordinatePolicy')!='world-y-up-box-local-fixed-center-v1' or
                declaration.get('UnitsPolicy')!='bma-mm-s-rotvec-rad-summary-deg-v1'):
            raise ValueError('Required Raw profile/frame/units declaration differs.')
        ref_path = Path(fixture['reference']['relative_path'])
        if ref_path.is_absolute() or '..' in ref_path.parts:
            raise ValueError('Reference path must remain inside asset root.')
        ref_path = Path(root) / ref_path
        if not ref_path.is_file():
            raise ReferenceMissing('Required trajectory reference is missing.')
        if file_digest(ref_path) != fixture['reference']['sha256']:
            raise ValueError('Required baseline content changed.')
        reference = read_json(ref_path, 'TrajectoryReference')
        validate_reference(reference)
        if (reference['generator']!=manifest['version'] or type(reference['seed']) is not int or
                type(reference['sample_count']) is not int or reference['sample_count']!=len(raw)):
            raise ValueError('Required baseline generator/seed/source sample population differs.')
        approval_check(reference['approval'], 'Reference')
        if reference['raw_sha256'] != fixture['raw_sha256'] or digest(reference['geometry']) != digest(fixture['geometry']):
            raise ValueError('Reference source/frame/geometry mismatch.')
        scenes = [d for d in fixture['scene_decisions'] if d['decision'] == 'include']
        if set(reference['scenes']) != {d['review_id'] for d in scenes}:
            raise ValueError('Corpus/fixture approved scene set mismatch with required baseline.')
        for d in scenes:
            a,b=d['anchor']['start_record'],d['anchor']['end_record_exclusive']
            ref=reference['scenes'][d['review_id']]
            if type(a) is not int or type(b) is not int or not 0<=a<b<=reference['sample_count']:
                raise ValueError('Invalid required original half-open interval.')
            if ref['trajectory']['original_record_index']!=list(range(a,b)):
                raise ValueError('Baseline/approval original record interval differs.')
            if ref['trajectory']['raw_time_s'][0]!=d['anchor']['start_raw_time_s']:
                raise ValueError('Baseline/approval raw start timestamp differs.')
            if ref['trajectory']['raw_time_s']!=raw.iloc[a:b,1].astype(float).tolist():
                raise ValueError('Baseline/approval full original raw timestamp correspondence differs.')
            if not REQUIRED_METRICS.issubset(ref['metrics']):
                raise ReferenceMissing('Reference is missing required representative metrics.')
        specs.append(dict(case_id=entry['case_id'], identity=cache_identity(fixture, manifest, code, runtime),
            raw_sha256=fixture['raw_sha256'], reference_sha256=fixture['reference']['sha256'],
            motion_group=entry['case_id'], profile=fixture['marker_profile_hash'],
            seed=reference['seed'], approval=fixture['approval'], tolerance=fixture['tolerance'],
            scenes=[dict(review_id=d['review_id'], anchor=d['anchor'], required=tier not in ('capture', 'fast')
                and (not select or d['review_id'] in select), expected=reference['scenes'][d['review_id']]['metrics']) for d in scenes]))
    if sorted(s['review_id'] for c in specs for s in c['scenes']) != sorted(CAPTURE_SCENES):
        raise ValueError('Corpus/fixture approved scene set mismatch (deletion/addition).')
    return envelope('EvaluationProtocol', version='pub11-capture-scope-v1', adapter='public-analytic-corpus-v2',
                    tier=tier, required_cases=list(CAPTURE_CASES), approved_scene_ids=list(CAPTURE_SCENES),
                    selected_scene_ids=list(select or CAPTURE_SCENES) if tier not in ('fast', 'capture') else [],
                    cases=specs, numeric_comparisons_required=tier not in ('fast', 'capture'))


def validate_capture_report(path, *, expected_tier=None, selection=None):
    """CI reopens immutable evidence; declared coverage alone is not acceptance."""
    from .runner import reuse_scene
    from .signatures import pose_trajectory, residual_guard, scene_signature, compare_metrics, scenario_guard
    from src.analysis.pipeline.data_loader import DataLoader
    report=read_json(path,'RunReport')
    if report['status']!='pass' or report['exit_code']!=0 or report['tier']!=expected_tier:
        raise ValueError('Required capture verdict/tier differs.')
    validate_envelope(report['protocol'],'EvaluationProtocol')
    if read_json(Path(path).parent/'protocol.json','EvaluationProtocol')!=report['protocol']:
        raise ValueError('Stored capture protocol differs from report.')
    inputs=report['input_files'];root=Path(inputs['asset_root'])
    if file_digest(inputs['manifest'])!=report['manifest_sha256']:
        raise ValueError('Required corpus manifest changed.')
    manifest=read_json(inputs['manifest'],'CaptureCorpus')
    loads=[]
    protocol=capture_protocol(manifest,root,expected_tier,selection,report['code'],report['environment'],loads)
    if digest(loads)!=digest(report['preflight_loaded_files']):
        raise ValueError('Actual preflight file-load evidence differs from original inputs.')
    if digest(protocol)!=report['protocol_sha256'] or digest(report['protocol'])!=digest(protocol):
        raise ValueError('Required capture protocol/population/identity differs.')
    if sorted(c['case_id'] for c in report['cases'])!=sorted(CAPTURE_CASES):
        raise ValueError('Required capture case omitted/duplicated.')
    expected_coverage=coverage(report['cases'],len(CAPTURE_SCENES),len(protocol['selected_scene_ids']),loads)
    if digest(expected_coverage)!=digest(report['coverage']):
        raise ValueError('Capture declared coverage differs from actual scene states.')
    report['_path']=str(Path(path).resolve())
    for case in report['cases']:
        spec=next(c for c in protocol['cases'] if c['case_id']==case['case_id'])
        loaded=next(v for v in loads if v['case_id']==case['case_id'])
        if case.get('loaded') is not True or type(case.get('loaded_rows')) is not int or case['loaded_rows']!=loaded['rows']:
            raise ValueError('Required capture case load status/row scope differs.')
        if case['status']!='pass' or case['cache_identity']!=spec['identity']:
            raise ValueError('Required capture case failed/stale.')
        if expected_tier=='fast':
            if case['scenes']:raise ValueError('Fast must not claim scene processing.')
            continue
        if sorted(s['review_id'] for s in case['scenes'])!=sorted(s['review_id'] for s in spec['scenes']):
            raise ValueError('Required capture scene omitted/duplicated.')
        entry=next(e for e in manifest['cases'] if e['case_id']==case['case_id'])
        fixture=read_json(root/entry['fixture'],'CaptureReviewFixture')
        _,original=DataLoader().load_csv(str(root/fixture['relative_path']))
        signature=read_json(Path(path).parent/case['case_id']/'capture.signature.json','CaptureSignature')
        if digest(signature)!=digest(case['signature']) or signature['raw_rows']!=len(original):
            raise ValueError('Capture signature/input rows changed.')
        if digest(signature['coverage'])!=digest(coverage([case],len(spec['scenes']),sum(s['required'] for s in spec['scenes']))):
            raise ValueError('Capture signature scene coverage differs.')
        for item in case['scenes']:
            rule=next(s for s in spec['scenes'] if s['review_id']==item['review_id'])
            if item['required'] is not rule['required']:
                raise ValueError('Required scene flag differs.')
            if not rule['required']:
                if item['status']!='skipped' or item['processing']!='unexecuted':
                    raise ValueError('Unselected scene falsely promoted.')
                continue
            if (item['status']!='pass' or item['completed'] is not True or item['evaluable'] is not True
                    or (expected_tier=='full' and (item['processing']!='fresh' or item['origin_run_id']!=report['run_id']))):
                raise ValueError('Required scene incomplete/reused/failed.')
            decision=next(d for d in fixture['scene_decisions'] if d['review_id']==item['review_id'])
            df,impact,artifact=reuse_scene(report,case,{},fixture,decision,original,publish=False)
            reference=read_json(root/fixture['reference']['relative_path'],'TrajectoryReference')['scenes'][item['review_id']]
            residual=residual_guard(pose_trajectory(df,fixture['geometry']),reference['trajectory'],fixture['tolerance'])
            current=scene_signature(df,fixture,decision,impact,artifact,residual)
            comparisons=compare_metrics(reference['metrics'],current['metrics'],fixture['tolerance'])
            if residual['status']!='pass' or scenario_guard(artifact,reference['trajectory'],fixture['tolerance'])['status']!='pass' or any(c['status']!='pass' for c in comparisons.values()):
                raise ValueError('Reopened required scene failed current comparison guards.')
            if digest(comparisons)!=digest(item['comparisons']):
                raise ValueError('Stored required comparison payload changed.')
    report.pop('_path')
    return report


def coverage(cases, approved, selected, loads=()):
    scenes = [s for c in cases for s in c['scenes']]
    loaded={v['case_id'] for v in loads}|{c['case_id'] for c in cases if c.get('loaded',False)}
    return dict(loaded=len(loaded), approved=approved, selected=selected,
                started=sum(s.get('started', False) for s in scenes),
                completed=sum(s.get('completed', False) for s in scenes),
                fresh=sum(s['processing'] == 'fresh' for s in scenes),
                reused=sum(s['processing'] == 'reused' for s in scenes),
                failed=sum(s['status'] == 'fail' for s in scenes),
                unexecuted=max(0, approved - sum(s.get('started', False) or s['processing'] == 'reused' for s in scenes)),
                required=selected, evaluable=sum(s.get('evaluable', False) for s in scenes),
                passed=sum(s['status'] == 'pass' for s in scenes))


def write_reports(output, report):
    """One run-level verdict plus individual cases; required skips never pass."""
    output = Path(output)
    write_new_json(output / 'run_report.json', report)
    suite = ET.Element('testsuite', name='regression.' + report['tier'])
    entries = [('run', report)] + [(c['case_id'], c) for c in report.get('cases', [])]
    entries += [(s['review_id'], s) for c in report.get('cases', []) for s in c['scenes']]
    for name, entry in entries:
        case = ET.SubElement(suite, 'testcase', classname='regression.' + report['tier'], name=name)
        props = ET.SubElement(case, 'properties')
        ET.SubElement(props, 'property', name='evidence_level', value='synthetic_integration')
        if entry['status'] != 'pass':
            tag = 'skipped' if entry['status'] == 'skipped' and not entry.get('required', True) else 'failure'
            ET.SubElement(case, tag, message=str(entry.get('reason', entry['status']))).text = entry.get('traceback', '')
    suite.set('tests', str(len(entries)))
    suite.set('failures', str(len(suite.findall('./testcase/failure'))))
    suite.set('skipped', str(len(suite.findall('./testcase/skipped'))))
    with (output / 'junit.xml').open('xb') as stream:
        stream.write(ET.tostring(suite, encoding='utf-8', xml_declaration=True))
    lines = ['# Regression execution', '', 'Last Reviewed: ' + report['kst'][:10], '',
             f"Tier: {report['tier']} / verdict: {report['status']} / exit: {report['exit_code']}",
             f"Source: {report['code']['commit']} / dirty: {report['code']['dirty']}",
             f"Scope: {report.get('pass_scope', report['tier'])}",
             'Coverage: ' + str(report.get('coverage', {})),
             'Numerical acceptance: ' + str(report.get('numerical_acceptance','Approved PUB02 gates apply only to selected production comparisons')),
             'Cache origin: ' + str(report.get('cache_origin','unavailable')),
             'GUI evidence: ' + str(report.get('gui',{})),
             f"Duration: {report.get('duration_s')} s / process peak: {report.get('peak_memory_bytes')} bytes",
             'Optimizer: ' + str(report.get('optimizer_calls', 'unavailable')),
             'Experimental: pending #104. Native/human GUI evidence has its own scope.', '']
    for name, entry in entries:
        lines.append(f"- {name}: {entry['status']} — {entry.get('reason', entry.get('boundary', 'See JSON evidence'))}")
    with (output / 'summary.md').open('x', encoding='utf-8') as stream:
        stream.write('\n'.join(lines) + '\n')
