import pandas as pd
import numpy as np
from pathlib import Path
from src.config.data_columns import HeaderL1, HeaderL2, HeaderL3

class DataExporter:
    """
    Exports simulation history directly to the final .proc CSV format
    (multi-level header) compatible with 3D Visualization and downstream analysis.
    """
    def __init__(self, history: list, add_noise=False, noise_std=1.0):
        self.history = history
        self.add_noise = add_noise
        self.noise_std = noise_std
        self.dt = 1/120.0 # Standard simulation frame rate is 120 FPS

    def calculate_derivatives(self):
        """
        Calculates velocities and accelerations using numerical differentiation
        (finite differences) for the CoM and all corners.
        """
        for i in range(len(self.history)):
            frame = self.history[i]

            if i == 0:
                frame['Center_V'] = np.zeros(3)
                frame['Center_A'] = np.zeros(3)
                for j in range(1, 9):
                    frame[f'C{j}_V'] = np.zeros(3)
                    frame[f'C{j}_A'] = np.zeros(3)
            else:
                prev = self.history[i-1]
                frame['Center_V'] = (frame['Center'] - prev['Center']) / self.dt
                for j in range(1, 9):
                    frame[f'C{j}_V'] = (frame[f'C{j}'] - prev[f'C{j}']) / self.dt

                if i == 1:
                    frame['Center_A'] = np.zeros(3)
                    for j in range(1, 9):
                        frame[f'C{j}_A'] = np.zeros(3)
                else:
                    prev_v = self.history[i-1]
                    frame['Center_A'] = (frame['Center_V'] - prev_v['Center_V']) / self.dt
                    for j in range(1, 9):
                        frame[f'C{j}_A'] = (frame[f'C{j}_V'] - prev_v[f'C{j}_V']) / self.dt

    def export_proc_csv(self, filepath: str):
        """
        Exports the data to a 3-level header CSV format matching DataProcessing results (.proc).
        """
        self.calculate_derivatives()

        columns = []
        # Info
        columns.append((HeaderL1.INFO, HeaderL2.FRAME, HeaderL2.FRAME))
        columns.append((HeaderL1.INFO, HeaderL2.TIME, HeaderL3.TIME))

        # Position CoM
        columns.extend([
            (HeaderL1.POS, HeaderL2.COM, HeaderL3.P_TX),
            (HeaderL1.POS, HeaderL2.COM, HeaderL3.P_TY),
            (HeaderL1.POS, HeaderL2.COM, HeaderL3.P_TZ),
            (HeaderL1.POS, HeaderL2.COM, HeaderL3.P_RX),
            (HeaderL1.POS, HeaderL2.COM, HeaderL3.P_RY),
            (HeaderL1.POS, HeaderL2.COM, HeaderL3.P_RZ),
        ])

        # Velocities CoM
        columns.extend([
            (HeaderL1.VEL, HeaderL2.COM, HeaderL3.V_TX),
            (HeaderL1.VEL, HeaderL2.COM, HeaderL3.V_TY),
            (HeaderL1.VEL, HeaderL2.COM, HeaderL3.V_TZ),
            (HeaderL1.VEL, HeaderL2.COM, HeaderL3.V_TNORM),
        ])

        # Accelerations CoM
        columns.extend([
            (HeaderL1.ACC, HeaderL2.COM, HeaderL3.A_TX),
            (HeaderL1.ACC, HeaderL2.COM, HeaderL3.A_TY),
            (HeaderL1.ACC, HeaderL2.COM, HeaderL3.A_TZ),
            (HeaderL1.ACC, HeaderL2.COM, HeaderL3.A_TNORM),
        ])

        # Corners
        for j in range(1, 9):
            prefix = f'C{j}'
            columns.extend([
                # Position
                (HeaderL1.POS, prefix, HeaderL3.P_TX),
                (HeaderL1.POS, prefix, HeaderL3.P_TY),
                (HeaderL1.POS, prefix, HeaderL3.P_TZ),
                # Velocity
                (HeaderL1.VEL, prefix, HeaderL3.V_TX),
                (HeaderL1.VEL, prefix, HeaderL3.V_TY),
                (HeaderL1.VEL, prefix, HeaderL3.V_TZ),
                (HeaderL1.VEL, prefix, HeaderL3.V_TNORM),
                # Acceleration
                (HeaderL1.ACC, prefix, HeaderL3.A_TX),
                (HeaderL1.ACC, prefix, HeaderL3.A_TY),
                (HeaderL1.ACC, prefix, HeaderL3.A_TZ),
                (HeaderL1.ACC, prefix, HeaderL3.A_TNORM),
                # Analysis (Relative Height)
                (HeaderL1.ANALYSIS, prefix, HeaderL3.REL_H)
            ])

        data_rows = []
        for i, frame in enumerate(self.history):
            time = frame['time']
            center = frame['Center']
            cv = frame['Center_V']
            ca = frame['Center_A']

            row = [
                i, time,
                center[0], center[1], center[2], 0, 0, 0, # Pos CoM
                cv[0], cv[1], cv[2], np.linalg.norm(cv), # Vel CoM
                ca[0], ca[1], ca[2], np.linalg.norm(ca), # Acc CoM
            ]

            # Ground Z is assumed to be 0 for relative height calculation
            for j in range(1, 9):
                cpos = frame[f'C{j}']
                if self.add_noise:
                    cpos = cpos + np.random.normal(0, self.noise_std, 3)

                cv_c = frame[f'C{j}_V']
                ca_c = frame[f'C{j}_A']
                rel_h = cpos[2] # Z is height

                row.extend([
                    cpos[0], cpos[1], cpos[2],
                    cv_c[0], cv_c[1], cv_c[2], np.linalg.norm(cv_c),
                    ca_c[0], ca_c[1], ca_c[2], np.linalg.norm(ca_c),
                    rel_h
                ])
            data_rows.append(row)

        # Create MultiIndex DataFrame
        multi_columns = pd.MultiIndex.from_tuples(columns)
        df = pd.DataFrame(data_rows, columns=multi_columns)

        output_path = Path(filepath)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        df.to_csv(output_path, index=False)

        return str(output_path.absolute())
