def build_effective_analysis_options(analysis_options: dict, resampling_factor: int) -> dict:
    effective = dict(analysis_options)
    if resampling_factor <= 1:
        return effective

    for key in ("marker_moving_average_window", "pose_moving_average_window"):
        if key in effective:
            effective[key] = max(1, int(round(float(effective[key]) * resampling_factor)))

    for key in ("spline_s_factor_position", "spline_s_factor_rotation"):
        if key in effective:
            effective[key] = float(effective[key]) * float(resampling_factor)

    return effective
