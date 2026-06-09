from dataclasses import dataclass
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
        display_name="Beta at t1-",
        group=DropPostureSummaryGroup.POSTURE,
        unit="deg",
        priority=10,
        short_description="Box reference-face tilt just before the first impact event.",
        long_description=(
            "Beta is the angle between the selected reference face and the floor just before "
            "the first detected impact. It answers how tilted the box was when it entered impact."
        ),
        visual_guide=DropPostureVisualGuide.BETA,
        t1_based=True,
    ),
    ResultMetricDescriptor(
        column=_summary_column(HeaderL3.DROP_THETA_LONG_AT_T1_MINUS_DEG),
        display_name="Long angle at t1-",
        group=DropPostureSummaryGroup.POSTURE,
        unit="deg",
        priority=20,
        short_description="Tilt component along the long direction of the reference face at t1-.",
        long_description=(
            "ThetaLong is the signed slope angle along the long in-plane direction of the "
            "reference face. It separates long-direction tilt from the overall Beta angle."
        ),
        visual_guide=DropPostureVisualGuide.THETA,
        t1_based=True,
    ),
    ResultMetricDescriptor(
        column=_summary_column(HeaderL3.DROP_THETA_SHORT_AT_T1_MINUS_DEG),
        display_name="Short angle at t1-",
        group=DropPostureSummaryGroup.POSTURE,
        unit="deg",
        priority=30,
        short_description="Tilt component along the short direction of the reference face at t1-.",
        long_description=(
            "ThetaShort is the signed slope angle along the short in-plane direction of the "
            "reference face. Together with ThetaLong, it describes the tilt direction."
        ),
        visual_guide=DropPostureVisualGuide.THETA,
        t1_based=True,
    ),
    ResultMetricDescriptor(
        column=_summary_column(HeaderL3.DROP_CMIN_AT_T1_MINUS_INDEX),
        display_name="Lowest corner at t1-",
        group=DropPostureSummaryGroup.POSTURE,
        unit="",
        priority=40,
        short_description="Corner closest to the floor just before the first impact event.",
        long_description=(
            "Cmin identifies the corner with the lowest floor-normal height at t1-. It is a "
            "candidate for the first physical contact point."
        ),
        visual_guide=DropPostureVisualGuide.CMIN,
        t1_based=True,
    ),
    ResultMetricDescriptor(
        column=_summary_column(HeaderL3.DROP_DELTA_H_AT_T1_MINUS_MM),
        display_name="Face DeltaH at t1-",
        group=DropPostureSummaryGroup.POSTURE,
        unit="mm",
        priority=50,
        short_description="Height spread across the reference-face corners at t1-.",
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
            "The reference face is selected from the processed pose/corner history. Beta, "
            "ThetaLong, ThetaShort, and DeltaH are interpreted relative to this face."
        ),
        visual_guide=DropPostureVisualGuide.REFERENCE_FACE,
    ),
    ResultMetricDescriptor(
        column=_summary_column(HeaderL3.DROP_T1_MINUS_TIME_SEC),
        display_name="t1-",
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
            "ImpactEvent, or SustainedContact."
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
        display_name="Sustained contact",
        group=DropPostureSummaryGroup.CONTACT,
        unit="",
        priority=30,
        short_description="Whether the slice contains low, stable floor-contact evidence.",
        long_description=(
            "Sustained contact indicates that the box appears to remain near the floor without "
            "a newly detected impact event inside the selected time window."
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
