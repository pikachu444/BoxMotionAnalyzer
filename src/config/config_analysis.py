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

# --- Slicing Parameters (향후 추가될 수 있음) ---
# ...

# --- Pose Optimization Parameters (향후 추가될 수 있음) ---
# ...

# --- Velocity Calculation Parameters (향후 추가될 수 있음) ---
# ...
