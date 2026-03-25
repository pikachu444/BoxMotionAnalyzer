import pandas as pd
import csv
from src.config.data_columns import TimeCols, RawMarkerCols, RigidBodyCols, DisplayNames

class DataLoader:
    def load_csv(self, filepath: str) -> tuple[dict[str, list[str]], pd.DataFrame]:
        """
        원본 CSV 파일을 읽어, 헤더 정보와 원본 데이터 DataFrame을 반환합니다.
        """
        try:
            with open(filepath, mode='r', encoding='utf-8-sig') as infile:
                lines = infile.readlines()
        except FileNotFoundError:
            raise FileNotFoundError(f"파일을 찾을 수 없습니다: {filepath}")

        if len(lines) < 8:
            raise ValueError("CSV 파일에 헤더 정보(최소 7줄)와 데이터(최소 1줄)가 부족합니다.")

        header_info = {}
        header_lines = [line.strip().split(',') for line in lines[2:8]]
        max_len = max(len(line) for line in header_lines)
        padded_headers = [[item.strip() for item in line] + [''] * (max_len - len(line)) for line in header_lines]
        header_keys = ['type', 'name', 'id', 'parent', 'category', 'component']
        for i, key in enumerate(header_keys):
            header_info[key] = padded_headers[i]

        component_header = header_info['component']
        data_lines_raw = lines[8:]
        reader = csv.reader(data_lines_raw)
        data_as_list = list(reader)

        if not data_as_list:
            return header_info, pd.DataFrame()

        num_columns = max_len
        df_cols = component_header[:num_columns]
        df_cols += [f'col_{i}' for i in range(len(df_cols), num_columns)]
        raw_df = pd.DataFrame(data_as_list)

        if raw_df.shape[1] < num_columns:
            for i in range(raw_df.shape[1], num_columns):
                raw_df[i] = pd.NA
        raw_df.columns = df_cols

        if len(raw_df.columns) > 1:
            rename_map = {raw_df.columns[0]: TimeCols.FRAME, raw_df.columns[1]: TimeCols.TIME}
            raw_df.rename(columns=rename_map, inplace=True)

        print(f"[DataLoader INFO] CSV loaded. Headers parsed, and {len(raw_df)} data rows prepared for Parser.")

        # Validate Raw Data Structure immediately
        self.validate_raw_data(raw_df)

        header_info['component'] = component_header
        return header_info, raw_df

    def validate_raw_data(self, raw_df: pd.DataFrame) -> None:
        """
        Validates that the raw DataFrame contains essential columns like 'Time'.
        Performs a fuzzy check (case-insensitive, substring).
        """
        if raw_df is None or raw_df.empty:
            return # Let Parser handle empty data or empty check logic elsewhere

        # Check for Time column
        # Matches: "Time", "time", "Time (Seconds)", "Frame", "frame", etc.
        has_time = any("time" in str(col).lower() for col in raw_df.columns)
        has_frame = any("frame" in str(col).lower() for col in raw_df.columns)

        if not has_time and not has_frame:
            # Check for standard constants just in case fuzzy match failed (unlikely)
            if TimeCols.TIME not in raw_df.columns and TimeCols.FRAME not in raw_df.columns:
                raise ValueError("Invalid CSV format: Missing 'Time' or 'Frame' column in raw data headers.")

    def load_result_csv(self, filepath: str) -> pd.DataFrame:
        """
        분석 완료 후 Export된 멀티헤더 결과 파일을 읽어 DataFrame으로 반환합니다.
        """
        try:
            # 멀티헤더(3줄)를 올바르게 읽기 위해 header=[0, 1, 2] 옵션을 사용합니다.
            df = pd.read_csv(filepath, header=[0, 1, 2])

            # 'Time' 컬럼을 찾아서 인덱스로 설정합니다.
            # 결과 CSV의 Time 컬럼은 ('Time', 'Time', 'Time') 튜플 형태의 멀티레벨 헤더를 가집니다.
            # 'Time' 컬럼을 찾아서 인덱스로 설정합니다.
            # 멀티레벨 헤더의 ('Time', 'Time', 'Time') 또는 단일 'Time' 컬럼을 순차적으로 확인합니다.
            time_col_tuple = (TimeCols.TIME, TimeCols.TIME, TimeCols.TIME)
            if time_col_tuple in df.columns:
                df.set_index(time_col_tuple, inplace=True)
                df.index.name = TimeCols.TIME
            elif TimeCols.TIME in df.columns:
                df.set_index(TimeCols.TIME, inplace=True)
                df.index.name = TimeCols.TIME

            print(f"[DataLoader INFO] Result file loaded successfully from {filepath}")
            return df
        except FileNotFoundError:
            raise FileNotFoundError(f"결과 파일을 찾을 수 없습니다: {filepath}")
        except Exception as e:
            raise ValueError(f"결과 파일을 읽는 중 오류가 발생했습니다: {e}")

    def get_plottable_targets(self, processed_df: pd.DataFrame) -> list[str]:
        """
        파싱이 완료된 "wide-format" DataFrame에서 플로팅할 대상의 '표시용 이름' 목록을 생성합니다.
        """
        if processed_df is None or processed_df.empty:
            return []

        # 1. 데이터프레임의 모든 컬럼을 순회하며, '_X', '_Y', '_Z'로 끝나는 컬럼의 기본 이름을 추출합니다.
        #    'set'을 사용하여 중복을 자동으로 제거합니다. (예: 'B1_X', 'B1_Y' -> 'B1')
        base_names = set()
        for col in processed_df.columns:
            if col.endswith((RawMarkerCols.X_SUFFIX, RawMarkerCols.Y_SUFFIX, RawMarkerCols.Z_SUFFIX)):
                base_name = col.rsplit('_', 1)[0]
                base_names.add(base_name)

        # 2. 요구사항에 따라 표시용 이름으로 변환하고 정렬합니다.
        final_targets = []        
        # 2a. 'RigidBody_Position'이 있으면, 'Rigid Body Center'로 이름을 바꿔 최상단에 위치시킵니다.
        if RigidBodyCols.BASE_NAME in base_names:
            final_targets.append(DisplayNames.RB_CENTER)
            base_names.remove(RigidBodyCols.BASE_NAME) # 나머지 마커 목록과 중복되지 않도록 제거

        # 2b. 나머지 타겟(마커)들은 이름 앞에 'Marker '를 붙이고, 알파벳 순으로 정렬합니다.
        #     ':'가 포함된 이름은 레거시 또는 다른 종류의 마커일 수 있으므로, 예외적으로 그대로 둡니다.
        marker_targets = []
        for name in sorted(list(base_names)):
            if ':' in name:
                marker_targets.append(name)
            else:
                marker_targets.append(f"{DisplayNames.MARKER_PREFIX}{name}")

        # 2c. 'Rigid Body Center'와 정렬된 마커 목록을 합칩니다.
        final_targets.extend(marker_targets)
        
        return final_targets
