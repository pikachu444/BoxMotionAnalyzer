from dataclasses import dataclass, replace
from enum import Enum

from src.config.data_columns import HeaderL1, HeaderL2, HeaderL3


class DropPostureSummaryGroup(str, Enum):
    POSTURE = "Posture"
    IMPACT = "Impact"
    CONTACT = "Contact"


class DropPostureVisualGuide(str, Enum):
    BETA = "beta"
    THETA = "theta"
    DELTA_H = "delta_h"
    CMIN = "cmin"
    TIMING = "timing"
    IMPACT_SEQUENCE = "impact_sequence"
    CONTACT_STATE = "contact_state"
    REFERENCE_FACE = "reference_face"


@dataclass(frozen=True)
class ResultMetricDescriptor:
    column: tuple[str, str, str]
    display_name: str
    group: DropPostureSummaryGroup
    unit: str
    priority: int
    short_description: str
    long_description: str
    visual_guide: DropPostureVisualGuide
    t1_based: bool = False
    stable_id: str = ''
    context: str = 'step2:summary'
    source_key: str = ''
    label_ko: str = ''
    definition_ko: str = ''
    caution: str = ''
    caution_ko: str = ''
    unavailable_reason: str = 'Required recorded evidence is unavailable'
    unavailable_reason_ko: str = '필요한 기록 근거가 없습니다'
    value_kind: str = 'numeric'
    engineering_role: str = 'Physical'
    comparison_role: str = 'supporting'
    evidence_status: str = 'experimental'
    calibration_status: str = 'not measured'
    time_reference: str = ''
    time_reference_ko: str = ''
    reference: str = ''
    reference_ko: str = ''
    aliases: tuple[str, ...] = ()


DROP_POSTURE_SUMMARY_GROUP_ORDER = (
    DropPostureSummaryGroup.POSTURE,
    DropPostureSummaryGroup.IMPACT,
    DropPostureSummaryGroup.CONTACT,
)


def _summary_column(l3: str) -> tuple[str, str, str]:
    return (HeaderL1.ANALYSIS, HeaderL2.DROP_POSTURE_SUMMARY, l3)


DROP_POSTURE_SUMMARY_DESCRIPTORS = (
    ResultMetricDescriptor(
        column=_summary_column(HeaderL3.DROP_BETA_AT_T1_MINUS_DEG),
        display_name="Pre-contact face tilt",
        group=DropPostureSummaryGroup.POSTURE,
        unit="°",
        priority=10,
        short_description="Box reference-face tilt just before the first impact event.",
        long_description=(
            "The angle between the reference face's outward normal and downward at the last "
            "sample before first impact. A downward-facing normal is 0°; an upward-facing "
            "normal is 180°. This is the observed posture, not an error from a target angle."
        ),
        visual_guide=DropPostureVisualGuide.BETA,
        t1_based=True,
    ),
    ResultMetricDescriptor(
        column=_summary_column(HeaderL3.DROP_THETA_LONG_AT_T1_MINUS_DEG),
        display_name="Pre-contact long axis tilt",
        group=DropPostureSummaryGroup.POSTURE,
        unit="°",
        priority=20,
        short_description="Signed slope along the long reference-face axis at the last sample before impact.",
        long_description=(
            "ThetaLong is the signed slope angle along the long in-plane direction of the "
            "reference face. It separates long-direction tilt from the overall Beta angle."
        ),
        visual_guide=DropPostureVisualGuide.THETA,
        t1_based=True,
    ),
    ResultMetricDescriptor(
        column=_summary_column(HeaderL3.DROP_THETA_SHORT_AT_T1_MINUS_DEG),
        display_name="Pre-contact short axis tilt",
        group=DropPostureSummaryGroup.POSTURE,
        unit="°",
        priority=30,
        short_description="Signed slope along the short reference-face axis at the last sample before impact.",
        long_description=(
            "ThetaShort is the signed slope angle along the short in-plane direction of the "
            "reference face. Together with ThetaLong, it describes the tilt direction."
        ),
        visual_guide=DropPostureVisualGuide.THETA,
        t1_based=True,
    ),
    ResultMetricDescriptor(
        column=_summary_column(HeaderL3.DROP_CMIN_AT_T1_MINUS_INDEX),
        display_name="Pre-contact lowest corner",
        group=DropPostureSummaryGroup.POSTURE,
        unit="",
        priority=40,
        short_description="Corner closest to the floor just before the first impact event.",
        long_description=(
            "One corner with the lowest floor-normal height at the last sample before impact. "
            "Tied corners can alternate; the ID is not a distance or the complete contact set."
        ),
        visual_guide=DropPostureVisualGuide.CMIN,
        t1_based=True,
    ),
    ResultMetricDescriptor(
        column=_summary_column(HeaderL3.DROP_DELTA_H_AT_T1_MINUS_MM),
        display_name="Pre-contact height difference",
        group=DropPostureSummaryGroup.POSTURE,
        unit="mm",
        priority=50,
        short_description="Height difference across the four reference-face corners just before impact.",
        long_description=(
            "DeltaH is the height difference between the highest and lowest corners on the "
            "reference face. It translates a posture angle into a directly visible height gap."
        ),
        visual_guide=DropPostureVisualGuide.DELTA_H,
        t1_based=True,
    ),
    ResultMetricDescriptor(
        column=_summary_column(HeaderL3.DROP_REFERENCE_FACE),
        display_name="Reference face",
        group=DropPostureSummaryGroup.POSTURE,
        unit="",
        priority=60,
        short_description="Box face used as the posture reference for Beta and direction angles.",
        long_description=(
            "The reference face is the box face whose outward normal points most strongly downward "
            "at the t1- frame (just before first impact). It defines the approach posture — the face "
            "the box was presenting toward the floor before contact. "
            "Beta, ThetaLong, ThetaShort, and DeltaH are all interpreted relative to this face. "
            "Note: this is the approach reference face, not the actual impact contact corner or face. "
            "The actual first contact corner is recorded separately in 'First impact contact'."
        ),
        visual_guide=DropPostureVisualGuide.REFERENCE_FACE,
    ),
    ResultMetricDescriptor(
        column=_summary_column(HeaderL3.DROP_T1_MINUS_TIME_SEC),
        display_name="Pre-contact sample time",
        group=DropPostureSummaryGroup.IMPACT,
        unit="s",
        priority=10,
        short_description="Frame time immediately before the first detected impact event.",
        long_description=(
            "t1- is the time sample just before the first impact event. t1-based posture values "
            "are intentionally N/A when no impact event is detected."
        ),
        visual_guide=DropPostureVisualGuide.TIMING,
        t1_based=True,
    ),
    ResultMetricDescriptor(
        column=_summary_column(HeaderL3.DROP_FIRST_IMPACT_TIME_SEC),
        display_name="First impact time",
        group=DropPostureSummaryGroup.IMPACT,
        unit="s",
        priority=20,
        short_description="Time of the first accepted impact event.",
        long_description=(
            "First impact time is the first contact event that passes the contact-evidence "
            "rules, including persistence checks that reduce one-frame noise."
        ),
        visual_guide=DropPostureVisualGuide.TIMING,
    ),
    ResultMetricDescriptor(
        column=_summary_column(HeaderL3.DROP_FIRST_IMPACT_CONTACT),
        display_name="First impact contact",
        group=DropPostureSummaryGroup.IMPACT,
        unit="",
        priority=30,
        short_description="Corner or simultaneous corner set at the first accepted impact.",
        long_description=(
            "First impact contact names the corner or grouped simultaneous corners detected at "
            "the first impact event, for example C2 or {C1,C2}."
        ),
        visual_guide=DropPostureVisualGuide.IMPACT_SEQUENCE,
    ),
    ResultMetricDescriptor(
        column=_summary_column(HeaderL3.DROP_IMPACT_SEQUENCE),
        display_name="Impact sequence",
        group=DropPostureSummaryGroup.IMPACT,
        unit="",
        priority=40,
        short_description="Ordered contact event sequence during the analyzed slice.",
        long_description=(
            "Impact sequence records accepted contact events in order. It helps identify when "
            "two repeated drops share the first contact but diverge afterward."
        ),
        visual_guide=DropPostureVisualGuide.IMPACT_SEQUENCE,
    ),
    ResultMetricDescriptor(
        column=_summary_column(HeaderL3.DROP_CONTACT_STATE),
        display_name="Contact state",
        group=DropPostureSummaryGroup.CONTACT,
        unit="",
        priority=10,
        short_description="Overall contact classification for the analyzed slice.",
        long_description=(
            "Contact state summarizes the evidence found in the slice: NoContact, Approach, "
            "ImpactEvent, or SustainedContact. Unavailable means pose or corner observations "
            "are incomplete; it does not mean there was no contact."
        ),
        visual_guide=DropPostureVisualGuide.CONTACT_STATE,
    ),
    ResultMetricDescriptor(
        column=_summary_column(HeaderL3.DROP_IMPACT_DETECTED),
        display_name="Impact detected",
        group=DropPostureSummaryGroup.CONTACT,
        unit="",
        priority=20,
        short_description="Whether a new impact event was detected in the slice.",
        long_description=(
            "Impact detected is true only when the contact evidence identifies a new impact "
            "event, not merely a low stable plateau."
        ),
        visual_guide=DropPostureVisualGuide.CONTACT_STATE,
    ),
    ResultMetricDescriptor(
        column=_summary_column(HeaderL3.DROP_SUSTAINED_CONTACT_DETECTED),
        display_name="Stable floor contact",
        group=DropPostureSummaryGroup.CONTACT,
        unit="",
        priority=30,
        short_description="Whether the slice contains low, stable floor-contact evidence.",
        long_description=(
            "The end of the selected window contains low, stable contact evidence. This can "
            "coexist with an earlier impact and its pre-contact sample. Stable contact alone "
            "does not establish a new impact or t1."
        ),
        visual_guide=DropPostureVisualGuide.CONTACT_STATE,
    ),
    ResultMetricDescriptor(
        column=_summary_column(HeaderL3.DROP_CONTACT_CONFIDENCE),
        display_name="Contact confidence",
        group=DropPostureSummaryGroup.CONTACT,
        unit="",
        priority=40,
        short_description="Diagnostic confidence score for the contact classification.",
        long_description=(
            "Contact confidence is a diagnostic score derived from the contact evidence. It is "
            "shown after the physical posture and impact fields because it is algorithm-facing."
        ),
        visual_guide=DropPostureVisualGuide.CONTACT_STATE,
    ),
    ResultMetricDescriptor(
        column=_summary_column(HeaderL3.DROP_CONTACT_DETECTION_METHOD),
        display_name="Detection method",
        group=DropPostureSummaryGroup.CONTACT,
        unit="",
        priority=50,
        short_description="Diagnostic evidence labels used for the contact classification.",
        long_description=(
            "Detection method names the evidence used by the hybrid contact summary, such as "
            "threshold, motion, relative low band, or plateau evidence."
        ),
        visual_guide=DropPostureVisualGuide.CONTACT_STATE,
    ),
)


def _extend_descriptors():
    from src.config.summary_metric_definitions import DEFINITIONS

    definitions = DEFINITIONS
    descriptors = {d.column[2]: d for d in DROP_POSTURE_SUMMARY_DESCRIPTORS}
    for index, definition in enumerate(definitions):
        key = definition['key']
        group = (DropPostureSummaryGroup.CONTACT if definition['engineering_role'] == 'Diagnostic'
                 else DropPostureSummaryGroup.IMPACT if index >= 10 else DropPostureSummaryGroup.POSTURE)
        original = descriptors.get(key) or ResultMetricDescriptor(
            _summary_column(key), definition['name'], group, definition['unit'], 100 + index,
            definition['definition'], definition['definition'],
            DropPostureVisualGuide.CONTACT_STATE if group == DropPostureSummaryGroup.CONTACT
            else DropPostureVisualGuide.TIMING if group == DropPostureSummaryGroup.IMPACT
            else DropPostureVisualGuide.BETA)
        descriptors[key] = replace(original, stable_id='step2:summary:' + key,
            display_name=definition['name'] or original.display_name, unit=definition['unit'],
            source_key=definition['source'], label_ko=definition['ko'], definition_ko=definition['definition_ko'],
            long_description=definition['definition'], caution=definition['caution'], caution_ko=definition['caution_ko'],
            value_kind=definition['kind'], engineering_role=definition['engineering_role'],
            comparison_role=definition['comparison_role'], time_reference=definition['time'],
            time_reference_ko={'t1-':'접촉 직전', 'whole slice':'전체 구간', 't1- or first usable frame':'접촉 직전 또는 첫 유효 표본',
                'settled tail':'안정 높이 끝 구간', 'pre-onset sample':'검출 시작 직전 표본', 'slice':'처리 구간',
                'first accepted contact set':'첫 인정 접촉', 't1- sample':'접촉 직전 실제 표본',
                'slice start through t1-':'구간 시작부터 접촉 직전까지', 't1- geometric-centre sample':'접촉 직전 기하중심 표본',
                'accepted-event path':'인정 접촉 경로', 'tail':'끝 구간',
                'validated first accepted contact':'검증된 첫 인정 접촉'}.get(definition['time'], definition['time']),
            reference='recorded box local / world Y up', aliases=(key, definition['source']))
        descriptors[key] = replace(descriptors[key], reference_ko='기록된 박스 로컬 좌표 / 월드 Y 위쪽')
    # Preserve existing public whole-window extras as distinct entries.
    for key, name, ko in (('MaxBetaDeg', 'Whole-window max Beta', '전체 구간 최대 기준면 기울기'),
                           ('MaxAbsThetaLongDeg', 'Whole-window max absolute long tilt', '전체 구간 최대 긴 축 기울기'),
                           ('MaxAbsThetaShortDeg', 'Whole-window max absolute short tilt', '전체 구간 최대 짧은 축 기울기')):
        descriptors[key] = ResultMetricDescriptor(_summary_column(key), name, DropPostureSummaryGroup.POSTURE,
            'deg', 200, 'Whole-window maximum of the recorded fixed-face geometry.',
            'Whole-window maximum of the recorded fixed-face geometry; repeats require equivalent reviewed windows.',
            DropPostureVisualGuide.THETA, stable_id='step2:summary:' + key, label_ko=ko,
            definition_ko='고정 기준면의 전체 구간 최대값이며 반복 비교는 같은 검토 구간을 요구합니다.',
            time_reference='whole slice', source_key='compare whole-window posture owner')
        descriptors[key] = replace(descriptors[key], time_reference_ko='전체 구간')
    return tuple(descriptors.values())


DROP_POSTURE_SUMMARY_DESCRIPTORS = _extend_descriptors()

_DROP_POSTURE_DESCRIPTOR_BY_COLUMN = {
    descriptor.column: descriptor for descriptor in DROP_POSTURE_SUMMARY_DESCRIPTORS
}


def get_drop_posture_summary_descriptors() -> tuple[ResultMetricDescriptor, ...]:
    return tuple(
        sorted(
            DROP_POSTURE_SUMMARY_DESCRIPTORS,
            key=lambda descriptor: (
                DROP_POSTURE_SUMMARY_GROUP_ORDER.index(descriptor.group),
                descriptor.priority,
            ),
        )
    )


def get_result_metric_descriptor(
    column: tuple[str, str, str],
) -> ResultMetricDescriptor | None:
    return _DROP_POSTURE_DESCRIPTOR_BY_COLUMN.get(tuple(column))


METRIC_DESCRIPTORS = {
    desc.column[2]: {
        "display_name": desc.display_name,
        "unit": desc.unit,
        "tooltip": desc.short_description
    }
    for desc in DROP_POSTURE_SUMMARY_DESCRIPTORS
}


def get_metric_registry():
    """Context-qualified identities; comparison owners remain authoritative."""
    from src.analysis.compare.impact_metrics import METRICS
    from src.analysis.compare.posture_metrics import POSTURE_METRICS

    entries = list(get_drop_posture_summary_descriptors())
    for key, item in {**METRICS, **POSTURE_METRICS}.items():
        source = item.get('column') or {'first_contact':'FirstImpactContact', 'final_face':'FinalFace',
            'contact_confidence':'ContactConfidence', 'corner_gap':'CminMargin_mm'}.get(key)
        summary = _DROP_POSTURE_DESCRIPTOR_BY_COLUMN.get(_summary_column(source)) if source else None
        definition = item['tooltip']
        fitted = key in ('vertical_velocity', 'horizontal_speed', 'angular_speed', 'equivalent_height')
        if fitted:
            definition += (' One-sided quadratic endpoint fit to observed pose. Stored snapshots differ in method/time. '
                           'Historical CoM translation is geometric centre; equivalent height fits the explicitly '
                           'registered inertial COM position path, uses g=9.80665 m/s² and already returns mm.')
        entries.append(ResultMetricDescriptor(summary.column if summary else ('', '', key), item['label'],
            summary.group if summary else DropPostureSummaryGroup.IMPACT, item['unit'], 300,
            item['tooltip'], definition, summary.visual_guide if summary else DropPostureVisualGuide.TIMING,
            stable_id='compare:' + key, context='compare', source_key=key,
            label_ko=summary.label_ko if summary else {'vertical_velocity':'편측 추정 수직속도',
                'horizontal_speed':'편측 추정 수평속력','angular_speed':'편측 추정 각속력',
                'equivalent_height':'등록 질량중심 속도 환산높이','first_contact':'첫 접촉',
                'final_face':'최종 면','contact_confidence':'충격 사건 진단 점수','corner_gap':'최저 꼭짓점 간격'}.get(key, item['label']),
            definition_ko=(summary.definition_ko if summary else '기존 비교 owner가 검증한 기록 값입니다.') +
                (' 관측 경로의 편측 2차 fit을 끝 시각에서 평가합니다. 저장 표본 미분과 방식·시각이 다릅니다. '
                 '환산높이는 등록 질량중심 경로와 중력 9.80665를 사용하며 이미 mm입니다.' if fitted else ''),
            caution=summary.caution if summary else 'Diagnostic/experimental quantity; not an automatic verdict.',
            caution_ko=summary.caution_ko if summary else '진단·실험적 값이며 자동 판정이 아닙니다.',
            value_kind=item['kind'], engineering_role=item['role'], time_reference='one-sided precontact fit' if fitted else
            ('whole slice' if item.get('whole') else 'recorded precontact/event'),
            time_reference_ko='접촉 직전 편측 fit' if fitted else '전체 구간' if item.get('whole') else '기록된 접촉 직전·사건',
            reference='registered inertial COM position path' if key == 'equivalent_height' else 'box geometric centre / world Y up',
            reference_ko='등록 관성 질량중심 위치 경로' if key == 'equivalent_height' else '기하중심 / 월드 Y 위쪽',
            aliases=(key, source or key)))
    # Legacy comparison fallback IDs stay addressable.
    existing = {d.stable_id for d in entries}
    contact = _DROP_POSTURE_DESCRIPTOR_BY_COLUMN[_summary_column('IntendedContactMatch')]
    entries.append(replace(contact, stable_id='compare:contact', context='compare',
        source_key='contact', display_name='Intended contact comparison',
        long_description=contact.long_description + ' Owner API retains Match/Different/Unclear; only the base summary adapter translates these categories.'))
    for descriptor in get_drop_posture_summary_descriptors():
        if descriptor.column[2] not in LEGACY_SUMMARY_FALLBACKS:
            continue
        identity = 'compare:summary:' + descriptor.column[2]
        if identity not in existing:
            entries.append(replace(descriptor, stable_id=identity, context='compare', source_key='summary:' + descriptor.column[2]))
    return tuple(entries)


LEGACY_SUMMARY_FALLBACKS = frozenset(('ReferenceFace', 'T1MinusTimeSec', 'FirstImpactTimeSec', 'T1Detected', 'ImpactEventCount',
    'ContactState', 'ImpactDetected', 'SustainedContactDetected', 'ContactDetectionMethod'))


def get_series_metric_descriptor(column):
    """A saved row quantity is a separate context, never a t1/peak/fit alias."""
    from urllib.parse import quote
    from src.config.data_columns import DISPLAY_RESULT_COLUMNS, get_result_column_unit, get_result_metric_display_name
    from src.utils.ui_text_ko import KOREAN

    if not isinstance(column, (tuple, list)) or len(column) != 3 or not all(isinstance(v, str) for v in column):
        return None
    column = tuple(column)
    if column not in DISPLAY_RESULT_COLUMNS:
        return None
    l1, l2, component = column
    unit = get_result_column_unit(column)
    label = get_result_metric_display_name(*column)
    if unit:
        label = label.removesuffix(' (' + unit + ')')
    label_ko = KOREAN.get(label, label)
    object_label = 'Box centre' if l2 == 'CoM' else 'Box posture' if l2 == 'DropPosture' else l2
    object_ko = '기하중심' if l2 == 'CoM' else '박스 자세' if l2 == 'DropPosture' else KOREAN.get(l2, l2)
    definition = 'Saved value of this selected series at an actual recorded row. Missing samples remain unavailable.'
    ko = '실제 기록 행에서 읽는 선택 시계열 값입니다. 결측 표본은 미산출 상태로 유지합니다.'
    caution = 'The selected time need not be t1-. This is not a precontact snapshot, whole-window peak or fitted comparison estimate.'
    caution_ko = '선택 시각은 t1-와 다를 수 있습니다. 접촉 직전 요약·전체 최대·비교 fit과 구분합니다.'
    reference = 'declared result coordinates and units'
    reference_ko = '기록된 결과 좌표·단위'
    visual = DropPostureVisualGuide.TIMING
    kind = 'numeric'
    if l2 == 'DropPosture':
        visual = DropPostureVisualGuide.BETA
        definition = {'BetaDeg':'Angle between the fixed recorded reference-face normal and world down at this row.',
            'ThetaLongDeg':'Signed long local-axis face tilt at this row, from opposite-side mean heights.',
            'ThetaShortDeg':'Signed short local-axis face tilt at this row, from opposite-side mean heights.',
            'DeltaH_mm':'Highest minus lowest of the four fixed reference-face heights at this row.',
            'CminIndex':'Legacy scalar ID of one minimum-height corner at this row.'}.get(component, definition)
        ko = {'BetaDeg':'이 행에서 고정 기준면 법선과 월드 아래 방향 사이 각도입니다.',
            'ThetaLongDeg':'이 행의 기준면 긴 로컬 축 양·음쪽 평균 높이로 구한 부호 있는 경사각입니다.',
            'ThetaShortDeg':'이 행의 기준면 짧은 로컬 축 양·음쪽 평균 높이로 구한 부호 있는 경사각입니다.',
            'DeltaH_mm':'이 행에서 고정 기준면 네 꼭짓점의 최대 높이와 최소 높이 차이입니다.',
            'CminIndex':'이 행의 최저 꼭짓점 하나를 저장한 과거 단일 번호입니다.'}.get(component, ko)
        label_ko = {'BetaDeg':'기준면 기울기', 'ThetaLongDeg':'긴 축 기울기', 'ThetaShortDeg':'짧은 축 기울기',
                    'DeltaH_mm':'기준면 높이 차이', 'CminIndex':'최저 꼭짓점 번호'}.get(component, label_ko)
        reference, reference_ko = 'fixed saved reference face / world Y up', '고정된 기록 기준면 / 월드 Y 위쪽'
        if component == 'CminIndex':
            kind = 'categorical'
            caution += ' Exact ties are shown as non-unique in the summary; this legacy scalar does not establish unique-corner agreement.'
            caution_ko += ' 요약은 정확한 동률 집합을 비유일로 표시합니다. 단일 저장 번호만으로 유일 꼭짓점 일치를 부여하지 않습니다.'
    elif l1 in ('Velocity', 'Acceleration'):
        local = component.startswith('BoxLocal_')
        reference = 'FrameAnalyzer analysis frame' if local else 'world frame'
        reference_ko = 'FrameAnalyzer 분석 프레임' if local else '월드 프레임'
        definition = 'Stored derivative component or norm in the ' + reference + ' at this recorded sample.'
        ko = reference_ko + '에서 저장한 미분 성분 또는 크기를 이 기록 표본에서 읽습니다.'
        axis = component.rsplit('_', 1)[-1]
        magnitude = component.endswith('_Norm')
        axis = {'TX':'X','TY':'Y','TZ':'Z','RX':'X','RY':'Y','RZ':'Z'}.get(axis, axis)
        quantity = ('각' if '_R' in component else '') + ('속력' if l1 == 'Velocity' and magnitude else '속도' if l1 == 'Velocity' else '가속도')
        label_ko = reference_ko + ' ' + quantity + ('' if magnitude else ' ' + axis)
        if l2 == 'CoM':
            caution += ' Historical CoM headers describe the geometric centre, not an explicitly registered inertial COM.'
            caution_ko += ' 과거 CoM 헤더는 기하중심이며 명시적으로 등록한 관성 질량중심을 뜻하지 않습니다.'
    elif l1 == 'Position' and component.startswith('P_R'):
        definition = 'Saved local-to-world rotation-vector component in radians at the recorded row; not an Euler angle.'
        ko = '기록 행의 로컬→월드 회전벡터 성분(rad)이며 Euler 각도가 아닙니다.'
        label_ko = component[-1] + ' 회전벡터 성분'
        reference, reference_ko = 'local-to-world rotation', '로컬→월드 회전'
    elif l1 == 'Position':
        definition = 'Saved world-coordinate position component at this actual recorded row.'
        ko = '실제 기록 행에서 저장한 월드 좌표 위치 성분입니다.'
        reference = 'geometric centre in world frame' if l2 == 'CoM' else 'world frame'
        reference_ko = '월드 프레임의 기하중심' if l2 == 'CoM' else '월드 프레임'
        if l2 == 'CoM':
            caution += ' Historical CoM position is the geometric centre, not a registered inertial COM.'
            caution_ko += ' 과거 CoM 위치는 기하중심이며 등록 관성 질량중심이 아닙니다.'
    elif component in ('RelativeHeight', 'AnalysisInputHeight'):
        definition = 'Saved corner vertical coordinate, subtracting the current eight-corner minimum only when that minimum is at or below the executed floor; otherwise the world vertical coordinate is retained.'
        ko = '현재 8개 꼭짓점의 최저값이 실행 바닥 이하일 때만 그 최저값을 뺍니다. 그 밖에는 월드 수직 좌표를 유지한 꼭짓점 높이입니다.'
        label_ko = '저장 꼭짓점 높이'
    return ResultMetricDescriptor(column, object_label + ' / ' + label, DropPostureSummaryGroup.POSTURE, unit, 400,
        definition, definition, visual, stable_id='step2:series:' + ':'.join(quote(v, safe='') for v in column),
        context='step2:series', source_key='/'.join(column), label_ko=object_ko + ' / ' + label_ko, definition_ko=ko,
        caution=caution, caution_ko=caution_ko, value_kind=kind, time_reference='selected recorded sample',
        time_reference_ko='선택한 실제 기록 표본', reference=object_label + ' / ' + reference,
        reference_ko=object_ko + ' / ' + reference_ko, aliases=column)
