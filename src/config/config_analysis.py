# src/config/analysis_config.py

"""
이 파일은 분석 파이프라인의 각 단계에서 사용되는
세부 파라미터와 설정을 중앙에서 관리합니다.
"""

# --- Smoothing Parameters ---
SMOOTHING_METHOD_SEQUENCE = ['butterworth', 'moving_average']
BUTTERWORTH_CUTOFF_FREQ_HZ = 10.0
BUTTERWORTH_ORDER = 4
MA_WINDOW_SIZE = 3

# 스무딩 시 경계 효과를 줄이기 위한 패딩 사이즈.
# scipy.signal.filtfilt의 기본 패딩 길이(3 * (order+1))를 따름.
SMOOTHING_PADDING_SIZE = 3 * (BUTTERWORTH_ORDER + 1)

# --- Slicing Parameters (향후 추가될 수 있음) ---
# ...

# --- Pose Optimization Parameters ---
OPTIMIZER_MAX_ITERATIONS = 1500  # `scipy.optimize.minimize`의 최대 반복 횟수
OPTIMIZER_XTOL = 1e-4             # 수렴 기준으로 사용되는 파라미터의 허용 오차
OPTIMIZER_FATOL = 1e-4            # 수렴 기준으로 사용되는 비용 함수의 허용 오차

# --- Velocity Calculation Parameters ---
VELOCITY_CALCULATION_METHOD = 'spline'  # 'finite_difference' 또는 'spline'

# STAGE 1: Pose Data Pre-processing: Initial Low-Pass Filter
USE_POSE_LOWPASS_FILTER = False
POSE_LPF_CUTOFF_HZ = 20.0
POSE_LPF_ORDER = 4

# STAGE 2: Pose Data Pre-processing: Moving Average
USE_POSE_MOVING_AVERAGE = True
POSE_MA_WINDOW = 3

# STAGE 3a: Spline Method Specific Parameters
SPLINE_S_FACTOR_POSITION = 1e-2
SPLINE_S_FACTOR_ROTATION = 1e-3
SPLINE_DEGREE = 3

# STAGE 3b: Finite Difference Method Specific Parameters
FD_ANGULAR_METHOD = 'quaternion' # 'matrix' 또는 'quaternion'

# STAGE 4: Velocity Data Post-processing: Final Low-Pass Filter
USE_VELOCITY_LOWPASS_FILTER = False
VELOCITY_LPF_CUTOFF_HZ = 8.0
VELOCITY_LPF_ORDER = 4
