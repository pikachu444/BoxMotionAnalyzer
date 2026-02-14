import numpy as np
import pandas as pd

from src.analysis.velocity_calculator import VelocityCalculator
from src.config.data_columns import PoseCols, VelocityCols


def test_velocity_calculator_outputs_tr_velocity_and_acceleration_columns():
    n = 10
    t = np.linspace(0.0, 0.9, n)

    df = pd.DataFrame(
        {
            PoseCols.POS_X: t,
            PoseCols.POS_Y: 2.0 * t,
            PoseCols.POS_Z: 3.0 * t,
            PoseCols.ROT_X: np.zeros(n),
            PoseCols.ROT_Y: np.zeros(n),
            PoseCols.ROT_Z: np.zeros(n),
        },
        index=t,
    )

    result = VelocityCalculator().process(df)

    expected_cols = [
        VelocityCols.T_VX,
        VelocityCols.T_VY,
        VelocityCols.T_VZ,
        VelocityCols.T_V_NORM,
        VelocityCols.T_AX,
        VelocityCols.T_AY,
        VelocityCols.T_AZ,
        VelocityCols.T_A_NORM,
        VelocityCols.R_VX,
        VelocityCols.R_VY,
        VelocityCols.R_VZ,
        VelocityCols.R_V_NORM,
        VelocityCols.R_AX,
        VelocityCols.R_AY,
        VelocityCols.R_AZ,
        VelocityCols.R_A_NORM,
    ]

    for col in expected_cols:
        assert col in result.columns

    assert result.columns.get_loc(VelocityCols.T_V_NORM) == result.columns.get_loc(VelocityCols.T_VZ) + 1
    assert result.columns.get_loc(VelocityCols.T_A_NORM) == result.columns.get_loc(VelocityCols.T_AZ) + 1
    assert result.columns.get_loc(VelocityCols.R_V_NORM) == result.columns.get_loc(VelocityCols.R_VZ) + 1
    assert result.columns.get_loc(VelocityCols.R_A_NORM) == result.columns.get_loc(VelocityCols.R_AZ) + 1
