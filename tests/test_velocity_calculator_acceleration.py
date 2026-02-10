import numpy as np
import pandas as pd
from unittest.mock import patch

from src.analysis.velocity_calculator import VelocityCalculator
from src.config.data_columns import PoseCols, VelocityCols


def test_velocity_calculator_adds_acceleration_columns():
    time_s = np.linspace(0.0, 1.0, 11)
    df = pd.DataFrame(
        {
            PoseCols.POS_X: time_s ** 2,
            PoseCols.POS_Y: np.zeros_like(time_s),
            PoseCols.POS_Z: np.zeros_like(time_s),
            PoseCols.ROT_X: np.zeros_like(time_s),
            PoseCols.ROT_Y: np.zeros_like(time_s),
            PoseCols.ROT_Z: np.zeros_like(time_s),
        },
        index=time_s,
    )

    calc = VelocityCalculator()
    calc.method = "numerical"
    calc.use_pose_lpf = False
    calc.use_pose_ma = False
    calc.use_vel_lpf = False

    result = calc.process(df)

    for col in [
        VelocityCols.COM_AX,
        VelocityCols.COM_AY,
        VelocityCols.COM_AZ,
        VelocityCols.COM_A_NORM,
        VelocityCols.ANG_AX,
        VelocityCols.ANG_AY,
        VelocityCols.ANG_AZ,
        VelocityCols.ANG_A_NORM,
    ]:
        assert col in result.columns

    # x(t)=t^2 => v=2t, a=2 (endpoints may differ due to gradient edge scheme)
    np.testing.assert_allclose(result[VelocityCols.COM_AX].iloc[2:-2], 2.0, atol=1e-6)
    np.testing.assert_allclose(result[VelocityCols.COM_AY], 0.0, atol=1e-6)
    np.testing.assert_allclose(result[VelocityCols.COM_AZ], 0.0, atol=1e-6)
    np.testing.assert_allclose(result[VelocityCols.COM_A_NORM].iloc[2:-2], 2.0, atol=1e-6)


def test_velocity_calculator_uses_spline_derivative_for_acceleration():
    time_s = np.linspace(0.0, 1.0, 11)
    df = pd.DataFrame(
        {
            PoseCols.POS_X: time_s ** 2,
            PoseCols.POS_Y: np.zeros_like(time_s),
            PoseCols.POS_Z: np.zeros_like(time_s),
            PoseCols.ROT_X: np.zeros_like(time_s),
            PoseCols.ROT_Y: np.zeros_like(time_s),
            PoseCols.ROT_Z: np.zeros_like(time_s),
        },
        index=time_s,
    )

    calc = VelocityCalculator()
    calc.method = "spline"
    calc.use_pose_lpf = False
    calc.use_pose_ma = False
    calc.use_vel_lpf = False

    with patch("src.analysis.velocity_calculator._numerical_derivative", side_effect=AssertionError("finite-difference should not be used in spline mode")):
        result = calc.process(df)

    assert VelocityCols.COM_AX in result.columns
    assert VelocityCols.ANG_A_NORM in result.columns
