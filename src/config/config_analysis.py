# src/config/analysis_config.py

"""
이 파일은 분석 파이프라인의 각 단계에서 사용되는
세부 파라미터와 설정을 중앙에서 관리합니다.
"""

# --- Smoothing Parameters ---
SMOOTHING_METHOD_SEQUENCE = ['butterworth', 'moving_average']
BUTTERWORTH_CUTOFF_FREQ_HZ = 10.0
BUTTERWORTH_ORDER = 4
# Butterworth 필터의 경계 효과를 줄이기 위한 패딩 사이즈.
# Scipy의 filtfilt 기본값인 3 * (order + 1)을 따름.
BUTTERWORTH_PAD_SIZE = 3 * (BUTTERWORTH_ORDER + 1)
MA_WINDOW_SIZE = 3
SAVGOL_WINDOW_LENGTH = 7
SAVGOL_POLYORDER = 3

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
ACCELERATION_CALCULATION_METHOD = 'spline'  # 'finite_difference' 또는 'spline'

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

# STAGE 5: Acceleration Data Post-processing: Final Low-Pass Filter
USE_ACCELERATION_LOWPASS_FILTER = False
ACCELERATION_LPF_CUTOFF_HZ = 8.0
ACCELERATION_LPF_ORDER = 4


# --- Pipeline Strategy Parameters ---
# 파이프라인에서 최종 데이터 슬라이스를 어느 시점에 할지 결정합니다.
# - 'early': 스무딩 직후. 후속 계산(자세/속도)은 더 작은 데이터셋에서 수행되어 빠르지만, 경계면 정확도가 낮을 수 있음.
# - 'late': 모든 계산(자세/속도 포함)이 끝난 마지막에 수행. 계산 시간은 더 걸리지만 경계면 정확도가 높음.
TRIMMING_STRATEGY = 'late'  # 'early' 또는 'late'
