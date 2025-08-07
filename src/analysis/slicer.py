import pandas as pd
from src.config.data_columns import TimeCols

class Slicer:
    """
    DataFrame을 시간 또는 프레임 기준으로 슬라이싱하는 기능을 제공합니다.
    """
    def __init__(self, filter_by: str, start_val, end_val):
        """
        Slicer를 초기화합니다.

        Args:
            filter_by (str): 필터링 기준 ('time' 또는 'frame').
            start_val: 필터링 시작 값.
            end_val: 필터링 끝 값.
        """
        if filter_by not in ['time', 'frame']:
            raise ValueError("filter_by는 'time' 또는 'frame' 이어야 합니다.")

        self.filter_by = filter_by
        self.start_val = float(start_val)
        self.end_val = float(end_val)

    def process(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        입력된 DataFrame을 슬라이싱합니다.

        Args:
            df (pd.DataFrame): 원본 DataFrame.

        Returns:
            pd.DataFrame: 슬라이싱된 DataFrame.
        """
        if self.filter_by == 'time':
            time_col = TimeCols.TIME
            # 'Time' 컬럼을 기준으로 슬라이싱
            if df.index.name == time_col:
                # 인덱스가 Time이면 loc를 사용 (더 효율적)
                return df.loc[self.start_val:self.end_val].copy()
            elif time_col in df.columns:
                # Time이 컬럼에 있으면 boolean 마스킹 사용
                mask = (df[time_col] >= self.start_val) & (df[time_col] <= self.end_val)
                return df[mask].copy()
            else:
                raise KeyError(f"'{time_col}' 컬럼을 찾을 수 없어 시간 슬라이싱을 수행할 수 없습니다.")

        elif self.filter_by == 'frame':
            frame_col = TimeCols.FRAME
            # 'Frame' 컬럼을 기준으로 슬라이싱
            if frame_col not in df.columns:
                raise KeyError(f"'{frame_col}' 컬럼을 찾을 수 없어 프레임 슬라이싱을 수행할 수 없습니다.")

            mask = (df[frame_col] >= int(self.start_val)) & (df[frame_col] <= int(self.end_val))
            return df[mask].copy()

        return df # Should not be reached
