from src.config import config_analysis

PROCESSING_MODE_STANDARD = "standard"
PROCESSING_MODE_RAW = "raw"
PROCESSING_MODE_ADVANCED = "advanced"

PROCESSING_MODE_GROUP_TITLE = "Processing Mode"
ADVANCED_DIALOG_TITLE = "Advanced Processing Settings"
ADVANCED_BUTTON_TEXT = "Advanced Settings..."

PROCESSING_MODE_LABELS = {
    PROCESSING_MODE_STANDARD: "Standard",
    PROCESSING_MODE_RAW: "Raw",
    PROCESSING_MODE_ADVANCED: "Advanced",
}

PROCESSING_MODE_DESCRIPTIONS = {
    PROCESSING_MODE_STANDARD: "Standard uses smoothing and filtering for more stable results.",
    PROCESSING_MODE_RAW: "Raw minimizes processing and may produce noisier velocity and acceleration.",
    PROCESSING_MODE_ADVANCED: "Advanced lets you customize each processing stage.",
}


# Step 1 layout tuning constants (Raw Data Processing bottom controls)
RAW_DATA_PROCESSING_LAYOUT = {
    "plot_options_group_min_width": 360,
    "slice_group_min_width": 280,
    "processing_group_min_width": 360,
    "processing_mode_description_fixed_height": 42,
    "bottom_controls_stretch": [4, 3, 4, 2],
}

SECTION_TITLES = {
    "marker_smoothing": "Marker Smoothing",
    "range_edge_handling": "Range Edge Handling",
    "pose": "Pose",
    "derivative_method": "Derivative Method",
    "velocity": "Velocity",
    "acceleration": "Acceleration",
}

SECTION_DESCRIPTIONS = {
    "marker_smoothing": "Controls how raw marker tracks are smoothed before pose estimation begins.",
    "range_edge_handling": "Controls how the selected time range is handled near the start and end boundaries.",
    "pose": "Pose options affect the rigid-body position and orientation before velocity and acceleration are derived.",
    "derivative_method": "Selects how velocity and acceleration are derived from pose data.",
    "velocity": "Post-processing applied after velocity has been calculated.",
    "acceleration": "Post-processing applied after acceleration has been calculated.",
}

FIELD_LABELS = {
    "enable_marker_smoothing": "Enable marker smoothing",
    "marker_smoothing_method": "Method:",
    "marker_butterworth_cutoff": "Butterworth cutoff (Hz):",
    "marker_butterworth_order": "Butterworth order:",
    "marker_ma_window": "Moving average window:",
    "range_edge_handling": "Mode:",
    "pose_lowpass_filter": "Pose low-pass filter",
    "pose_moving_average": "Pose moving average",
    "pose_lpf_cutoff": "Low-pass cutoff (Hz):",
    "pose_lpf_order": "Low-pass order:",
    "pose_ma_window": "Moving average window:",
    "velocity_method": "Velocity:",
    "acceleration_method": "Acceleration:",
    "spline_position_factor": "Position spline factor:",
    "spline_rotation_factor": "Rotation spline factor:",
    "spline_degree": "Spline degree:",
    "velocity_lowpass_filter": "Velocity low-pass filter",
    "velocity_lpf_cutoff": "Low-pass cutoff (Hz):",
    "velocity_lpf_order": "Low-pass order:",
    "acceleration_lowpass_filter": "Acceleration low-pass filter",
    "acceleration_lpf_cutoff": "Low-pass cutoff (Hz):",
    "acceleration_lpf_order": "Low-pass order:",
    "cancel": "Cancel",
    "ok": "OK",
}

FIELD_HINTS = {
    "enable_marker_smoothing": "Recommended for standard processing. Disabling this keeps the marker data closer to the raw input.",
    "range_edge_handling": "Stable keeps a small hidden margin around the selected range during calculations. Fast trims earlier and can be less reliable near the boundaries.",
    "pose_lowpass_filter": "Reduces fast pose jitter before derivatives are computed.",
    "pose_moving_average": "Applies a small moving average to pose data for additional stabilization.",
    "derivative_method": "Spline is smoother and more stable. Finite Difference is closer to raw derivatives but noisier.",
    "velocity_lowpass_filter": "Useful when the derived velocity still contains rapid oscillations.",
    "acceleration_lowpass_filter": "Recommended when acceleration is too noisy. Corner acceleration is derived from the filtered CoM and angular acceleration.",
    "spline_parameters": "These spline parameters are used when either derivative method is set to Spline.",
}

RANGE_EDGE_HANDLING_CHOICES = [
    ("Stable (recommended)", "late"),
    ("Fast (less accurate near range edges)", "early"),
]

DERIVATIVE_METHOD_CHOICES = [
    ("Spline", "spline"),
    ("Finite Difference", "finite_difference"),
]

MARKER_SMOOTHING_METHOD_CHOICES = [
    ("Butterworth -> Moving Average", ["butterworth", "moving_average"]),
    ("Butterworth", ["butterworth"]),
    ("Moving Average", ["moving_average"]),
]


def get_default_advanced_options():
    return {
        "enable_marker_smoothing": True,
        "marker_smoothing_method_sequence": list(config_analysis.SMOOTHING_METHOD_SEQUENCE),
        "marker_butterworth_cutoff_hz": config_analysis.BUTTERWORTH_CUTOFF_FREQ_HZ,
        "marker_butterworth_order": config_analysis.BUTTERWORTH_ORDER,
        "marker_moving_average_window": config_analysis.MA_WINDOW_SIZE,
        "trimming_strategy": config_analysis.TRIMMING_STRATEGY,
        "use_pose_lowpass_filter": config_analysis.USE_POSE_LOWPASS_FILTER,
        "pose_lpf_cutoff_hz": config_analysis.POSE_LPF_CUTOFF_HZ,
        "pose_lpf_order": config_analysis.POSE_LPF_ORDER,
        "use_pose_moving_average": config_analysis.USE_POSE_MOVING_AVERAGE,
        "pose_moving_average_window": config_analysis.POSE_MA_WINDOW,
        "velocity_method": config_analysis.VELOCITY_CALCULATION_METHOD,
        "acceleration_method": config_analysis.ACCELERATION_CALCULATION_METHOD,
        "spline_s_factor_position": config_analysis.SPLINE_S_FACTOR_POSITION,
        "spline_s_factor_rotation": config_analysis.SPLINE_S_FACTOR_ROTATION,
        "spline_degree": config_analysis.SPLINE_DEGREE,
        "use_velocity_lowpass_filter": config_analysis.USE_VELOCITY_LOWPASS_FILTER,
        "velocity_lpf_cutoff_hz": config_analysis.VELOCITY_LPF_CUTOFF_HZ,
        "velocity_lpf_order": config_analysis.VELOCITY_LPF_ORDER,
        "use_acceleration_lowpass_filter": config_analysis.USE_ACCELERATION_LOWPASS_FILTER,
        "acceleration_lpf_cutoff_hz": config_analysis.ACCELERATION_LPF_CUTOFF_HZ,
        "acceleration_lpf_order": config_analysis.ACCELERATION_LPF_ORDER,
    }


def get_raw_mode_options():
    return {
        "enable_marker_smoothing": False,
        "marker_smoothing_method_sequence": [],
        "marker_butterworth_cutoff_hz": config_analysis.BUTTERWORTH_CUTOFF_FREQ_HZ,
        "marker_butterworth_order": config_analysis.BUTTERWORTH_ORDER,
        "marker_moving_average_window": config_analysis.MA_WINDOW_SIZE,
        "trimming_strategy": "early",
        "use_pose_lowpass_filter": False,
        "pose_lpf_cutoff_hz": config_analysis.POSE_LPF_CUTOFF_HZ,
        "pose_lpf_order": config_analysis.POSE_LPF_ORDER,
        "use_pose_moving_average": False,
        "pose_moving_average_window": config_analysis.POSE_MA_WINDOW,
        "velocity_method": "finite_difference",
        "acceleration_method": "finite_difference",
        "spline_s_factor_position": config_analysis.SPLINE_S_FACTOR_POSITION,
        "spline_s_factor_rotation": config_analysis.SPLINE_S_FACTOR_ROTATION,
        "spline_degree": config_analysis.SPLINE_DEGREE,
        "use_velocity_lowpass_filter": False,
        "velocity_lpf_cutoff_hz": config_analysis.VELOCITY_LPF_CUTOFF_HZ,
        "velocity_lpf_order": config_analysis.VELOCITY_LPF_ORDER,
        "use_acceleration_lowpass_filter": False,
        "acceleration_lpf_cutoff_hz": config_analysis.ACCELERATION_LPF_CUTOFF_HZ,
        "acceleration_lpf_order": config_analysis.ACCELERATION_LPF_ORDER,
    }
