import pandas as pd
import numpy as np
from pathlib import Path

class DataExporter:
    """
    Exports simulation history to Raw CSV format matching real motion capture data.
    Also handles adding Gaussian noise to simulate realistic sensor imperfections.
    """
    def __init__(self, history: list, add_noise=False, noise_std=1.0):
        self.history = history
        self.add_noise = add_noise
        self.noise_std = noise_std

    def export_raw_csv(self, filepath: str):
        """
        Exports the data to a raw CSV format with multi-level headers.
        Matches the format loaded by Parser in Step 1.
        """
        # 1. Create Data
        data = []
        for i, frame in enumerate(self.history):
            time = frame['time']
            row = [i, time]

            # The parser expects C1, C2, C3, C4, C5, C6, C7, C8 (and possibly other markers)
            for j in range(1, 9):
                pos = frame[f'C{j}']

                # Add noise if enabled
                if self.add_noise:
                    pos = pos + np.random.normal(0, self.noise_std, 3)

                row.extend([pos[0], pos[1], pos[2]])

            data.append(row)

        # 2. Create Headers
        # First header row: Info, Info, Position, Position, Position...
        header_1 = ["Info", "Info"]
        # Second header row: Frame, Time, C1, C1, C1, C2, C2, C2...
        header_2 = ["Frame", "Time"]
        # Third header row: Number, Time, PX, PY, PZ, PX, PY, PZ...
        header_3 = ["Number", "Time"]

        for j in range(1, 9):
            header_1.extend(["Position", "Position", "Position"])
            header_2.extend([f"C{j}", f"C{j}", f"C{j}"])
            header_3.extend(["PX", "PY", "PZ"])

        # 3. Create DataFrame
        df = pd.DataFrame(data, columns=pd.MultiIndex.from_tuples(list(zip(header_1, header_2, header_3))))

        # 4. Save to CSV
        output_path = Path(filepath)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        df.to_csv(filepath, index=False)
        return str(output_path.absolute())
