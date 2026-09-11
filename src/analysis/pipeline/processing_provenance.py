"""Capture configured production objects; never substitute raw declarations."""
import copy


def capture_single_pass(controller, *, trimming_strategy, padding_frames, filter_by):
    smoother = controller.smoother
    velocity = controller.velocity_calculator
    marker = {'enabled': bool(smoother.enabled)}
    if smoother.enabled:
        marker['sequence'] = list(smoother.method_sequence)
        if 'butterworth' in smoother.method_sequence:
            marker['butterworth'] = {'cutoff_hz': float(smoother.cutoff_freq), 'order': int(smoother.order)}
        if 'moving_average' in smoother.method_sequence:
            marker['moving_average_window'] = int(smoother.ma_window)
        if 'savitzky_golay' in smoother.method_sequence:
            marker['savgol'] = {'window': smoother._normalize_odd_window(smoother.savgol_window_length),
                                'polyorder': max(1, int(smoother.savgol_polyorder)),
                                'short_segment_policy': 'clamp-window-and-polyorder-to-segment'}
    derivative = {
        'velocity_method': str(velocity.velocity_method),
        'acceleration_method': str(velocity.acceleration_method),
        'time_policy': 'actual-dt;finite-difference-numpy-gradient;finite-angle-matrix',
        'segmentation_policy': 'face-boundaries-and-finite-contiguous-pose-v3',
        'pose_lowpass': {'enabled': bool(velocity.use_pose_lpf)},
        'pose_moving_average': {'enabled': bool(velocity.use_pose_ma)},
        'velocity_lowpass': {'enabled': bool(velocity.use_vel_lpf)},
        'acceleration_lowpass': {'enabled': bool(velocity.use_acc_lpf)},
    }
    if 'spline' in (velocity.velocity_method, velocity.acceleration_method):
        derivative['spline'] = {'degree': int(velocity.spline_k),
                                'position_s': float(velocity.spline_s_pos),
                                'rotation_s': float(velocity.spline_s_rot)}
    for group, enabled, cutoff, order in (
        ('pose_lowpass', velocity.use_pose_lpf, velocity.pose_lpf_cutoff, velocity.pose_lpf_order),
        ('velocity_lowpass', velocity.use_vel_lpf, velocity.vel_lpf_cutoff, velocity.vel_lpf_order),
        ('acceleration_lowpass', velocity.use_acc_lpf, velocity.acc_lpf_cutoff, velocity.acc_lpf_order),
    ):
        if enabled:
            derivative[group].update(cutoff_hz=float(cutoff), order=int(order))
    if velocity.use_pose_ma:
        derivative['pose_moving_average']['window'] = int(velocity.pose_ma_window)
    return {
        'marker_smoothing': marker,
        'derivatives': derivative,
        'pose_optimizer': dict(controller.pose_optimizer.optimizer_options),
        'face_definitions': copy.deepcopy(controller.pose_optimizer.face_definitions),
        'geometry_mm': controller.pose_optimizer.local_box_corners.tolist(),
        'frame_analysis': {'vertical_axis': int(controller.frame_analyzer.vertical_axis_idx),
                           'floor_policy': 'explicit-horizontal-plane',
                           'floor_level_mm': float(controller.frame_analyzer.floor_level)},
        'slice_policy': {'filter_by': filter_by, 'trimming': trimming_strategy,
                         'padding_frames': int(padding_frames)},
    }


def capture_postprocess(processor, threshold):
    return {'contact_threshold_mm': float(threshold),
            'vertical_axis': int(processor.vertical_axis_idx),
            'floor_policy': 'explicit-horizontal-plane', 'floor_level_mm': float(processor.floor_level),
            'geometry_mm': processor.local_box_corners.tolist(),
            'face_definitions': copy.deepcopy(processor.face_definitions),
            'contact_policy': 'drop-posture-evidence-v1'}
