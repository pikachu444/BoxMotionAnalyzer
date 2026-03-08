import pandas as pd
import numpy as np
from src.config.data_columns import TimeCols

class Slicer:
    """
    DataFrame을 시간 또는 프레임 기준으로 슬라이싱하는 기능을 제공합니다.
    필터링을 위한 패딩(padding)을 지원합니다.
    """
    def __init__(self, filter_by: str, start_val, end_val, padding_size: int = 0):
        """
        Slicer를 초기화합니다.

        Args:
            filter_by (str): 필터링 기준 ('time' 또는 'frame').
            start_val: 필터링 시작 값.
            end_val: 필터링 끝 값.
            padding_size (int): 슬라이싱 구간의 양 끝에 추가할 데이터 샘플 수.
        """
        if filter_by not in ['time', 'frame']:
            raise ValueError("filter_by는 'time' 또는 'frame' 이어야 합니다.")

        self.filter_by = filter_by
        self.start_val = float(start_val)
        self.end_val = float(end_val)
        self.padding_size = int(padding_size)

    def process(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        입력된 DataFrame을 슬라이싱합니다. 패딩이 지정된 경우, 슬라이싱 구간을 확장합니다.

        Args:
            df (pd.DataFrame): 원본 DataFrame.

        Returns:
            pd.DataFrame: 슬라이싱된 DataFrame.
        """
        if self.padding_size == 0:
            # 패딩이 없으면 기존 로직 수행
            return self._slice(df, self.start_val, self.end_val)

        if self.filter_by == 'time':
            time_col = TimeCols.TIME
            if df.index.name != time_col:
                raise TypeError("시간 기반 패딩 슬라이싱은 'Time' 컬럼이 인덱스로 설정되어 있어야 합니다.")

            # 시간 기반 패딩 계산
            sampling_rate = 1 / np.mean(np.diff(df.index))
            padding_time = self.padding_size / sampling_rate

            padded_start = self.start_val - padding_time
            padded_end = self.end_val + padding_time

            # 경계 조건은 loc가 자동으로 처리 (범위를 벗어나면 있는 데이터까지만 슬라이싱)
            return self._slice(df, padded_start, padded_end)

        elif self.filter_by == 'frame':
            # 프레임 기반 패딩 계산 (정수 인덱스로 변환하여 처리)
            start_idx, end_idx = self._get_indices_from_frame_values(df, self.start_val, self.end_val)

            padded_start_idx = start_idx - self.padding_size
            padded_end_idx = end_idx + self.padding_size

            # 경계 조건 처리
            padded_start_idx = max(0, padded_start_idx)
            padded_end_idx = min(len(df) - 1, padded_end_idx)

            return df.iloc[padded_start_idx:padded_end_idx + 1].copy()

    def _slice(self, df: pd.DataFrame, start, end) -> pd.DataFrame:
        """주어진 시작/종료 값으로 데이터프레임을 슬라이싱하는 내부 헬퍼 메서드."""
        if self.filter_by == 'time':
            time_col = TimeCols.TIME
            if df.index.name == time_col:
                return df.loc[start:end].copy()
            elif time_col in df.columns:
                mask = (df[time_col] >= start) & (df[time_col] <= end)
                return df[mask].copy()
            else:
                raise KeyError(f"'{time_col}' 컬럼을 찾을 수 없어 시간 슬라이싱을 수행할 수 없습니다.")
        elif self.filter_by == 'frame':
            frame_col = TimeCols.FRAME
            if frame_col not in df.columns:
                raise KeyError(f"'{frame_col}' 컬럼을 찾을 수 없어 프레임 슬라이싱을 수행할 수 없습니다.")
            mask = (df[frame_col] >= int(start)) & (df[frame_col] <= int(end))
            return df[mask].copy()
        return df

    def _get_indices_from_frame_values(self, df: pd.DataFrame, start_frame: int, end_frame: int) -> tuple[int, int]:
        """프레임 값에 해당하는 DataFrame의 정수 인덱스를 찾습니다."""
        frame_col = TimeCols.FRAME
        if frame_col not in df.columns:
            raise KeyError(f"'{frame_col}' 컬럼을 찾을 수 없습니다.")

        # 'Frame' 컬럼에서 시작 및 종료 값과 일치하는 첫 번째 인덱스를 찾음
        start_indices = df.index[df[frame_col] >= start_frame].tolist()
        end_indices = df.index[df[frame_col] <= end_frame].tolist()

        if not start_indices or not end_indices:
            raise ValueError("지정된 프레임 범위에 해당하는 데이터가 없습니다.")

        # DataFrame의 실제 정수 위치를 얻기 위해 get_loc 사용
        start_idx = df.index.get_loc(start_indices[0])
        end_idx = df.index.get_loc(end_indices[-1])

        return start_idx, end_idx
