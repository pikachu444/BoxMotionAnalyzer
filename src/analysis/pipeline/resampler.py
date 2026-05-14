import numpy as np
import pandas as pd

from src.config.data_columns import TimeCols


class UniformResampler:
    def __init__(self, factor: int = 2):
        self.factor = max(1, int(factor))

    def process(self, df: pd.DataFrame) -> pd.DataFrame:
        if df.empty or self.factor <= 1:
            return df.copy()

        original_index = df.index.to_numpy(dtype=float)
        if len(original_index) < 2:
            return df.copy()
        if not np.all(np.diff(original_index) > 0):
            raise ValueError("Resampling requires a strictly increasing time index.")

        new_size = (len(original_index) - 1) * self.factor + 1
        new_index_parts = []
        for start, end in zip(original_index[:-1], original_index[1:]):
            step = (end - start) / self.factor
            new_index_parts.extend(start + step * offset for offset in range(self.factor))
        new_index_parts.append(original_index[-1])
        new_index = np.asarray(new_index_parts, dtype=float)
        resampled_columns = {}

        for column in df.columns:
            series = df[column]
            numeric_series = pd.to_numeric(series, errors="coerce")

            if numeric_series.notna().any():
                valid = numeric_series.dropna()
                if len(valid) == 1:
                    resampled_columns[column] = np.full(new_size, float(valid.iloc[0]))
                else:
                    resampled_columns[column] = np.interp(
                        new_index,
                        valid.index.to_numpy(dtype=float),
                        valid.to_numpy(dtype=float),
                    )
                continue

            expanded = series.reindex(series.index.union(new_index)).sort_index()
            filled = expanded.ffill().bfill()
            resampled_columns[column] = filled.reindex(new_index).to_numpy()

        resampled = pd.DataFrame(resampled_columns, index=pd.Index(new_index, name=df.index.name))

        if TimeCols.FRAME in resampled.columns:
            resampled[TimeCols.FRAME] = np.arange(len(resampled), dtype=int)
        else:
            resampled.insert(0, TimeCols.FRAME, np.arange(len(resampled), dtype=int))

        for column in resampled.columns:
            if resampled[column].dtype.kind not in {"i", "u", "f"}:
                resampled[column] = resampled[column].ffill().bfill()

        return resampled
